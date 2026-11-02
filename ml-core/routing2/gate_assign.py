"""Part 1 gate: how far apart are user equilibrium and system optimum on the Q4 alley net?

For each (demand level, seed, mode) SUMO's duaIterate assigns the same motorbike trips
(routing2.demand: origin node -> destination zone node, junction TAZ):
- ue: dynamic user equilibrium (Gawron, the duaIterate default);
- so: system optimum approximated by duaIterate --marginal-cost --marginal-cost.exp 1, so
  link cost = tt + veh * d(tt)/d(veh) with a finite difference between iterations. (With
  duaIterate's default exp 0 the veh factor is missing and SO stays near UE.) The slope is
  noisy, so this gives a lower bound on the true UE-SO gap, not the gap itself;
- so_logit: the same with --logit, which SUMO's tool recommends for marginal cost.
Iteration 0 is every trip on its free-flow fastest path ("no information").

Per run it reads every iteration's tripinfo (unfinished trips count until the end of the
simulation, departure delay included) and the last iteration's routes, and reports
total travel time, the alley share of vehicle-km, and how many alley links carry more
than given hourly flows. `summary` prints UE vs SO gaps per level. Never overwrites:
results go to <out>/gate_<stamp>/.

    python -u -m routing2.gate_assign --tph 2000 4000 6000 8000 --seeds 61000 61001 61002 \\
        --modes ue so --iters 40 --horizon 3600 --jobs 24
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import torch

from .demand import make_demand, pick_zones
from .graph import DEFAULT_GRAPH, load_graph
from .params import SimConfig
from .sumo_check import MOTO_VTYPE
from .sumo_net import build_net

FLOW_THRESHOLDS = (100, 200, 400)  # veh/h on one alley link


def sumo_home() -> str:
    try:
        import sumo  # type: ignore[import-not-found]

        return str(sumo.SUMO_HOME)
    except ImportError:
        return os.environ["SUMO_HOME"]


def write_trips(path: Path, g, zones, tph: float, seed: int, horizon: float) -> int:
    d = make_demand(g, zones, [seed], tph, horizon, 1.0)
    dep = d.dep_t[0].tolist()
    orig = d.orig[0].tolist()
    dz = d.dest_zone[0].tolist()
    zn = zones.tolist()
    n = 0
    with path.open("w", encoding="utf-8") as f:
        f.write("<routes>\n  " + MOTO_VTYPE + "\n")
        for i in sorted(range(len(dep)), key=lambda k: dep[k]):
            o, t = g.node_ids[orig[i]], g.node_ids[zn[dz[i]]]
            if o == t or dep[i] >= horizon:
                continue
            f.write(f'  <trip id="v{i}" type="moto" depart="{dep[i]:.2f}" fromJunction="{o}" '
                    f'toJunction="{t}" departLane="best" departSpeed="max"/>\n')
            n += 1
        f.write("</routes>\n")
    return n


def tripinfo_stats(path: str, end: float) -> dict:
    tt, arrived, n = 0.0, 0, 0
    for _, el in ET.iterparse(path, events=("end",)):
        if el.tag != "tripinfo":
            continue
        dep = float(el.get("depart", "0"))
        dur = float(el.get("duration", "-1"))
        delay = float(el.get("departDelay", "0"))
        arr = float(el.get("arrival", "-1"))
        if arr < 0 or dur < 0:  # unfinished (write-unfinished): count until the end
            t = end - (dep - delay) if dep >= 0 else 0.0
        else:
            t = dur + delay
            arrived += 1
        tt += t
        n += 1
        el.clear()
    return {"ttt_h": tt / 3600.0, "trips": n, "arrived": arrived, "mean_tt_s": tt / max(1, n)}


def route_stats(path: str, alley: dict[str, bool], length: dict[str, float], hours: float) -> dict:
    vkm, vkm_alley = 0.0, 0.0
    flow: dict[str, int] = {}
    for _, el in ET.iterparse(path, events=("end",)):
        if el.tag != "vehicle":
            continue
        r = el.find("route")
        if r is None:
            rd = el.find("routeDistribution")
            r = rd.findall("route")[-1] if rd is not None else None
        if r is None:
            el.clear()
            continue
        for e in r.get("edges", "").split():
            if e not in length:
                continue
            vkm += length[e]
            if alley[e]:
                vkm_alley += length[e]
                flow[e] = flow.get(e, 0) + 1
        el.clear()
    out = {"alley_vkm_share": round(vkm_alley / max(vkm, 1e-9), 4)}
    for th in FLOW_THRESHOLDS:
        out[f"alley_links_over_{th}vph"] = sum(1 for v in flow.values() if v / hours > th)
    out["alley_max_vph"] = round(max(flow.values(), default=0) / hours, 1)
    return out


def run_one(job: dict) -> dict:
    wd = Path(job["dir"])
    wd.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SUMO_HOME=job["sumo_home"])
    dua = Path(job["sumo_home"]) / "tools" / "assign" / "duaIterate.py"
    end = job["horizon"] + job["drain"]
    cmd = [sys.executable, str(dua), "-n", job["net"], "-t", "trips.xml", "-l", str(job["iters"]),
           "-b", "0", "-e", str(end), "--aggregation", "300", "--no-gzip", "--time-to-teleport", "180",
           "sumo--step-length", "0.5", "sumo--lateral-resolution", "0.8",
           "sumo--junction-taz", "true",
           "sumo--tripinfo-output.write-unfinished", "true", "sumo--seed", str(job["sumo_seed"]),
           "duarouter--junction-taz", "true",
           ]
    if job["mode"].startswith("so"):
        extra = ["--marginal-cost", "--marginal-cost.exp", "1"]
        if job["mode"] == "so_logit":
            extra.append("--logit")
        i = cmd.index("--no-gzip")
        cmd[i:i] = extra
    t0 = time.perf_counter()
    with open(wd / "dua_stdout.txt", "w") as so:
        p = subprocess.run(cmd, cwd=wd, env=env, stdout=so, stderr=subprocess.STDOUT)
    row = {k: job[k] for k in ("mode", "tph", "seed", "iters", "horizon")}
    row["wall_s"] = round(time.perf_counter() - t0, 1)
    row["returncode"] = p.returncode
    tis = sorted(glob.glob(str(wd / "**" / "tripinfo_*.xml"), recursive=True))
    row["ttt_h_by_iter"] = [round(tripinfo_stats(f, end)["ttt_h"], 3) for f in tis]
    if tis:
        last = tripinfo_stats(tis[-1], end)
        row.update({k: (round(v, 3) if isinstance(v, float) else v) for k, v in last.items()})
    rous = sorted(glob.glob(str(wd / "**" / "trips_*.rou.xml"), recursive=True))
    if rous:
        row.update(route_stats(rous[-1], job["alley"], job["length"], job["horizon"] / 3600.0))
    return row


def summary(rows: list[dict]) -> list[dict]:
    out = []
    for tph in sorted({r["tph"] for r in rows}):
        def m(mode, key, it=None):
            v = [r[key] if it is None else r["ttt_h_by_iter"][it] for r in rows
                 if r["tph"] == tph and r["mode"] == mode and r.get(key if it is None else "ttt_h_by_iter")]
            return sum(v) / len(v) if v else float("nan")
        ue, ff = m("ue", "ttt_h"), m("ue", "ttt_h", 0)
        row = {"tph": tph, "ttt_h_freeflow": round(ff, 2), "ttt_h_ue": round(ue, 2),
               "gap_ff_ue_pct": round(100 * (ff - ue) / ff, 2) if ff == ff and ue == ue else None,
               "alley_vkm_share_ue": round(m("ue", "alley_vkm_share"), 3)}
        for mode in ("so", "so_logit"):
            so = m(mode, "ttt_h")
            row[f"ttt_h_{mode}"] = round(so, 2)
            row[f"gap_ue_{mode}_pct"] = round(100 * (ue - so) / ue, 2) if ue == ue and so == so else None
            row[f"alley_vkm_share_{mode}"] = round(m(mode, "alley_vkm_share"), 3)
        out.append(row)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tph", type=float, nargs="+", default=[2000.0, 4000.0, 6000.0, 8000.0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[61000, 61001, 61002])
    ap.add_argument("--modes", nargs="+", default=["ue", "so"], choices=["ue", "so", "so_logit"])
    ap.add_argument("--iters", type=int, default=40)
    ap.add_argument("--horizon", type=float, default=3600.0, help="demand period (s)")
    ap.add_argument("--drain", type=float, default=1800.0, help="extra simulated time to let trips finish")
    ap.add_argument("--zones", type=int, default=32)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--net-dir", type=Path, default=Path("../sumo-env/networks/v4"))
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/out/quan4/routing2"))
    args = ap.parse_args()

    cfg = replace(SimConfig(), horizon_s=args.horizon)
    g = load_graph(DEFAULT_GRAPH, cfg)
    zones = pick_zones(g, args.zones, seed=0)
    net = build_net(DEFAULT_GRAPH, args.net_dir).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = (args.out_dir / f"gate_{stamp}").resolve()
    root.mkdir(parents=True, exist_ok=True)
    alley = {e: bool(a) for e, a in zip(g.edge_ids, g.is_alley.tolist())}
    length = {e: float(x) / 1000.0 for e, x in zip(g.edge_ids, g.length.tolist())}
    jobs = []
    for tph in args.tph:
        for s in args.seeds:
            d = root / f"tph{int(tph)}_seed{s}"
            d.mkdir(parents=True, exist_ok=True)
            n = write_trips(d / "trips.xml", g, zones, tph, s, args.horizon)
            for mode in args.modes:
                wd = d / mode
                wd.mkdir(exist_ok=True)
                (wd / "trips.xml").write_bytes((d / "trips.xml").read_bytes())
                jobs.append({"mode": mode, "tph": tph, "seed": s, "iters": args.iters, "horizon": args.horizon,
                             "drain": args.drain, "dir": str(wd), "net": str(net), "sumo_home": sumo_home(),
                             "sumo_seed": s, "alley": alley, "length": length, "trips_written": n})
    print(f"[gate] {len(jobs)} runs -> {root} (jobs={args.jobs})", flush=True)
    rows = []
    with ProcessPoolExecutor(args.jobs) as ex:
        futs = [ex.submit(run_one, j) for j in jobs]
        for f in as_completed(futs):
            r = f.result()
            rows.append(r)
            print(f"[gate] {json.dumps({k: v for k, v in r.items() if k != 'ttt_h_by_iter'})}", flush=True)
    summ = summary(rows)
    for s in summ:
        print(f"[gate] summary {json.dumps(s)}", flush=True)
    (root / "gate.json").write_text(json.dumps({"args": {k: str(v) for k, v in vars(args).items()},
                                                "net": str(net), "runs": rows, "summary": summ}, indent=2),
                                    encoding="utf-8")
    print(f"[gate] wrote {root / 'gate.json'}", flush=True)


if __name__ == "__main__":
    torch.set_num_threads(1)
    main()
