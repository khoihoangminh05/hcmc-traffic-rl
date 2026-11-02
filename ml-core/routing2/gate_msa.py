"""Part 1 gate with our own MSA assignment loop in SUMO (batch).

Why not duaIterate --marginal-cost: its slope is a finite difference between two iterations.
Locally (6000 trips/h) it gave a "system optimum" 17-23% WORSE than user equilibrium, which
cannot be a system optimum, so it says nothing about the gap.

Loop, for mode ue or so:
  1. SUMO runs the current routes and writes edgeData per 5-min interval.
  2. Link cost per (link, interval), averaged over iterations (MSA):
     ue: mean travel time tt;
     so: tt + q * d(tt)/dq (marginal travel time, Peeta & Mahmassani style), with the slope
     from a per-link non-negative fit tt - ff = a q + b q^2 over all (q, tt) points seen so
     far, capped at `--mc-cap-s`.
  3. duarouter gives each trip its best route on those costs; with probability 1/(k+1)
     (at most 1/2) the trip switches to it.

Reported: TTT per iteration; relative gap (ue convergence); and, to avoid selection bias, the
final and the best-iteration route sets replayed on fresh SUMO seeds. Any route set that beats
UE on fresh seeds is a valid lower bound on the UE-SO gap, whatever the quality of the slope.

`--vtype-extra` adds attributes to the motorbike vType (e.g. jmTimegapMinor, impatience): how
hard alleys yield at merges is unknown, so the gate sweeps it.

    python -u -m routing2.gate_msa --tph 4000 6000 8000 --seeds 61000 61001 --modes ue so \\
        --iters 40 --horizon 3600 --jobs 12
"""

from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .demand import pick_zones
from .gate_assign import route_stats, tripinfo_stats, write_trips
from .graph import DEFAULT_GRAPH, load_graph
from .params import SimConfig
from .sumo_check import MOTO_VTYPE
from .sumo_net import build_net, sumo_binary

BIN_S = 300.0
EDGEDATA = '<a><edgeData id="d" freq="{f}" file="dump.xml" excludeEmpty="true" minSamples="1"/></a>\n'


def vtype(extra: str) -> str:
    return MOTO_VTYPE.replace("/>", f" {extra}/>") if extra else MOTO_VTYPE


def write_routes(path: Path, routes: dict[str, list[str]], dep: dict[str, float], vt: str) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("<routes>\n  " + vt + "\n")
        for v in sorted(routes, key=lambda k: dep[k]):
            f.write(f'  <vehicle id="{v}" type="moto" depart="{dep[v]:.2f}" departLane="best" departSpeed="max">'
                    f'<route edges="{" ".join(routes[v])}"/></vehicle>\n')
        f.write("</routes>\n")


def run_sumo(wd: Path, net: str, rou: Path, end: float, seed: int) -> tuple[Path, Path]:
    (wd / "ed.add.xml").write_text(EDGEDATA.format(f=int(BIN_S)), encoding="utf-8")
    ti = wd / "tripinfo.xml"
    subprocess.run([
        sumo_binary("sumo"), "-n", net, "-r", rou.name, "-a", "ed.add.xml", "--tripinfo-output", ti.name,
        "--tripinfo-output.write-unfinished", "true", "--step-length", "0.5", "--lateral-resolution", "0.8",
        "--time-to-teleport", "180", "--end", str(end), "--seed", str(seed), "--no-step-log", "true",
        "--no-warnings", "true",
    ], cwd=wd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ti, wd / "dump.xml"


def read_dump(path: Path) -> dict[tuple[str, float], tuple[float, float]]:
    """(edge, interval begin) -> (mean travel time, vehicles entered)."""
    out = {}
    for iv in ET.parse(path).getroot():
        b = float(iv.get("begin"))
        for e in iv.iter("edge"):
            if e.get("traveltime") is not None:
                out[(e.get("id"), b)] = (float(e.get("traveltime")), float(e.get("entered", "0")))
    return out


def fit_slopes(points: dict[str, list[tuple[float, float]]], ff: dict[str, float]) -> dict[str, tuple[float, float]]:
    """Per link a, b >= 0 of tt - ff = a q + b q^2 (least squares, then clipped and refit)."""
    out = {}
    for e, pts in points.items():
        if len(pts) < 8:
            continue
        s11 = s12 = s22 = y1 = y2 = 0.0
        for q, tt in pts:
            d = tt - ff[e]
            s11 += q * q
            s12 += q**3
            s22 += q**4
            y1 += q * d
            y2 += q * q * d
        det = s11 * s22 - s12 * s12
        if s11 <= 0:
            continue
        a, b = 0.0, 0.0
        if det > 1e-9:
            a = (y1 * s22 - y2 * s12) / det
            b = (y2 * s11 - y1 * s12) / det
        if a < 0 or b < 0 or det <= 1e-9:  # one term only, the better of the two
            a1 = max(0.0, y1 / s11)
            b1 = max(0.0, y2 / s22) if s22 > 0 else 0.0
            r1 = sum((tt - ff[e] - a1 * q) ** 2 for q, tt in pts)
            r2 = sum((tt - ff[e] - b1 * q * q) ** 2 for q, tt in pts)
            a, b = (a1, 0.0) if r1 <= r2 else (0.0, b1)
        out[e] = (a, b)
    return out


def write_weights(path: Path, cost: dict[tuple[str, float], float], end: float) -> None:
    by = defaultdict(list)
    for (e, b), c in cost.items():
        by[b].append((e, c))
    with path.open("w", encoding="utf-8") as f:
        f.write("<meandata>\n")
        for b in sorted(by):
            f.write(f'  <interval begin="{b}" end="{min(b + BIN_S, end)}">\n')
            for e, c in by[b]:
                f.write(f'    <edge id="{e}" traveltime="{c:.3f}"/>\n')
            f.write("  </interval>\n")
        f.write("</meandata>\n")


def best_routes(wd: Path, net: str, trips: Path, weights: Path | None, seed: int) -> dict[str, list[str]]:
    out = wd / "best.rou.xml"
    cmd = [sumo_binary("duarouter"), "-n", net, "-r", str(trips), "-o", out.name, "--junction-taz", "true",
           "--ignore-errors", "true", "--no-step-log", "true", "--no-warnings", "true", "--seed", str(seed)]
    if weights is not None:
        cmd += ["--weight-files", str(weights), "--weight-attribute", "traveltime"]
    subprocess.run(cmd, cwd=wd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    res = {}
    for v in ET.parse(out).getroot():
        if v.tag == "vehicle":
            res[v.get("id")] = v.find("route").get("edges").split()
    return res


def route_cost(r: list[str], t: float, cost: dict, ff: dict[str, float]) -> float:
    t0 = t
    for e in r:
        t += cost.get((e, math.floor(t / BIN_S) * BIN_S), ff.get(e, 1.0))
    return t - t0


def run_one(job: dict) -> dict:
    wd = Path(job["dir"])
    wd.mkdir(parents=True, exist_ok=True)
    trips, net, end = wd / "trips.xml", job["net"], job["horizon"] + job["drain"]
    ff, mode = job["ff"], job["mode"]
    vt = vtype(job["vtype_extra"])
    trips.write_text(Path(job["trips"]).read_text(encoding="utf-8").replace(MOTO_VTYPE, vt), encoding="utf-8")
    dep = {el.get("id"): float(el.get("depart")) for el in ET.parse(trips).getroot() if el.tag == "trip"}
    rng = random.Random(job["seed"] * 7 + (0 if mode == "ue" else 1))
    t0 = time.perf_counter()
    routes = best_routes(wd, net, trips, None, job["seed"])
    dep = {v: d for v, d in dep.items() if v in routes}
    cost: dict[tuple[str, float], float] = {}
    pts: dict[str, list[tuple[float, float]]] = defaultdict(list)
    hist, gaps = [], []
    best_ttt, best_routes_set = math.inf, dict(routes)
    for k in range(job["iters"]):
        rou = wd / "cur.rou.xml"
        write_routes(rou, routes, dep, vt)
        ti, dump = run_sumo(wd, net, rou, end, job["seed"])
        ttt = tripinfo_stats(str(ti), end)["ttt_h"]
        hist.append(round(ttt, 3))
        if ttt < best_ttt:
            best_ttt, best_routes_set = ttt, dict(routes)
        obs = read_dump(dump)
        for (e, _b), (tt, q) in obs.items():
            if e in ff and q > 0:
                pts[e].append((q, tt))
        slopes = fit_slopes(pts, ff) if mode == "so" else {}
        w = 1.0 / (k + 1)
        for key, (tt, q) in obs.items():
            e = key[0]
            c = tt
            if mode == "so" and e in slopes:
                a, b = slopes[e]
                c = tt + min(job["mc_cap_s"], q * (a + 2.0 * b * q))
            cost[key] = (1 - w) * cost.get(key, ff.get(e, tt)) + w * c
        wfile = wd / "weights.xml"
        write_weights(wfile, cost, end)
        new = best_routes(wd, net, trips, wfile, job["seed"] + k + 1)
        p = min(0.5, 1.0 / (k + 1))
        num = den = 0.0
        for v, r in new.items():
            if v not in routes:
                continue
            c_new = route_cost(r, dep[v], cost, ff)
            num += max(0.0, route_cost(routes[v], dep[v], cost, ff) - c_new)
            den += c_new
            if rng.random() < p:
                routes[v] = r
        gaps.append(round(num / max(den, 1e-9), 4))
    # replay on fresh SUMO seeds (the search never saw them)
    fresh = {}
    for name, rs in (("final", routes), ("best", best_routes_set)):
        rou = wd / f"{name}.rou.xml"
        write_routes(rou, rs, dep, vt)
        vals = []
        for s in job["fresh_seeds"]:
            ti, _ = run_sumo(wd, net, rou, end, s)
            vals.append(tripinfo_stats(str(ti), end)["ttt_h"])
        fresh[name] = {"ttt_h_mean": round(sum(vals) / len(vals), 3), "ttt_h": [round(x, 3) for x in vals],
                       **route_stats(str(rou), job["alley"], job["length"], job["horizon"] / 3600.0)}
    return {"mode": mode, "tph": job["tph"], "seed": job["seed"], "vtype_extra": job["vtype_extra"],
            "wall_s": round(time.perf_counter() - t0, 1), "ttt_h_by_iter": hist, "rel_gap_by_iter": gaps,
            "n_trips": len(routes), "fresh": fresh}


def summary(rows: list[dict]) -> list[dict]:
    out = []
    for key in sorted({(r["vtype_extra"], r["tph"]) for r in rows}):
        sel = [r for r in rows if (r["vtype_extra"], r["tph"]) == key]

        def m(mode, which):
            v = [r["fresh"][which]["ttt_h_mean"] for r in sel if r["mode"] == mode]
            return sum(v) / len(v) if v else math.nan

        ff = [r["ttt_h_by_iter"][0] for r in sel if r["mode"] == "ue"]
        ff = sum(ff) / len(ff) if ff else math.nan
        ue, so_f, so_b = min(m("ue", "final"), m("ue", "best")), m("so", "final"), m("so", "best")
        so = min(so_f, so_b)
        out.append({"vtype_extra": key[0], "tph": key[1], "ttt_h_freeflow": round(ff, 2), "ttt_h_ue": round(ue, 2),
                    "ttt_h_so_final": round(so_f, 2), "ttt_h_so_best": round(so_b, 2),
                    "gap_ff_ue_pct": round(100 * (ff - ue) / ff, 2), "gap_ue_so_pct": round(100 * (ue - so) / ue, 2)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tph", type=float, nargs="+", default=[4000.0, 6000.0, 8000.0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[61000, 61001])
    ap.add_argument("--modes", nargs="+", default=["ue", "so"], choices=["ue", "so"])
    ap.add_argument("--iters", type=int, default=40)
    ap.add_argument("--horizon", type=float, default=3600.0)
    ap.add_argument("--drain", type=float, default=1800.0)
    ap.add_argument("--zones", type=int, default=32)
    ap.add_argument("--mc-cap-s", type=float, default=300.0)
    ap.add_argument("--fresh-seeds", type=int, nargs="+", default=[71, 72, 73])
    ap.add_argument("--vtype-extra", nargs="+", default=[""],
                    help='extra vType attributes per scenario, e.g. "" \'jmTimegapMinor="0.5" impatience="0.5"\'')
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--net-dir", type=Path, default=Path("../sumo-env/networks/v4"))
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/out/quan4/routing2"))
    args = ap.parse_args()

    cfg = replace(SimConfig(), horizon_s=args.horizon)
    g = load_graph(DEFAULT_GRAPH, cfg)
    zones = pick_zones(g, args.zones, seed=0)
    net = str(build_net(DEFAULT_GRAPH, args.net_dir).resolve())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = (args.out_dir / f"gate_msa_{stamp}").resolve()
    root.mkdir(parents=True, exist_ok=True)
    ff = {e: float(x) for e, x in zip(g.edge_ids, (g.length / g.v_free).tolist())}
    alley = {e: bool(a) for e, a in zip(g.edge_ids, g.is_alley.tolist())}
    length = {e: float(x) / 1000.0 for e, x in zip(g.edge_ids, g.length.tolist())}
    jobs = []
    for vi, ex in enumerate(args.vtype_extra):
        for tph in args.tph:
            for s in args.seeds:
                d = root / f"v{vi}_tph{int(tph)}_seed{s}"
                d.mkdir(parents=True, exist_ok=True)
                write_trips(d / "trips0.xml", g, zones, tph, s, args.horizon)
                for mode in args.modes:
                    jobs.append({"mode": mode, "tph": tph, "seed": s, "iters": args.iters, "horizon": args.horizon,
                                 "drain": args.drain, "dir": str(d / mode), "trips": str(d / "trips0.xml"), "net": net,
                                 "ff": ff, "alley": alley, "length": length, "mc_cap_s": args.mc_cap_s,
                                 "fresh_seeds": args.fresh_seeds, "vtype_extra": ex})
    print(f"[msa] {len(jobs)} runs -> {root} (jobs={args.jobs})", flush=True)
    rows = []
    with ProcessPoolExecutor(args.jobs) as ex:
        for f in as_completed([ex.submit(run_one, j) for j in jobs]):
            r = f.result()
            rows.append(r)
            print(f"[msa] {json.dumps({k: v for k, v in r.items() if k != 'rel_gap_by_iter'})}", flush=True)
    summ = summary(rows)
    for s in summ:
        print(f"[msa] summary {json.dumps(s)}", flush=True)
    (root / "gate_msa.json").write_text(json.dumps({"args": {k: str(v) for k, v in vars(args).items()},
                                                    "runs": rows, "summary": summ}, indent=2), encoding="utf-8")
    print(f"[msa] wrote {root / 'gate_msa.json'}", flush=True)


if __name__ == "__main__":
    main()
