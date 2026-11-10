"""L3: one corridor, selected hours, against Mapbox typical speeds.

Each hour is simulated alone on network v5, 15 minutes of warm-up then one measured hour, with corridor traffic only in
both directions. Inflow has the shape of the camera counts, times the Mapbox speed of the calibration direction if
--flow-shape n_v (flow = density x speed); its level is one number, `alpha`, the mean flow per direction over the day.
Free speed per edge is the Mapbox 5h speed, corrected by free_speeds. `width` is the carriageway width per direction, split equally over the lanes.

`alpha` is chosen on the first direction only. The second direction is the held-out check. Mapbox typical speeds are
car speeds, so the simulated speed compared is the car speed. Side streets are not simulated. A rerun skips finished
runs, so a stopped sweep can continue.

    python -m routing2.validate.l3_axis --net DIR --obs edge_obs.csv --axes axes.json --counts counts.csv --out DIR \\
        --calib "Khánh Hội|324" --holdout "Khánh Hội|142"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from .common import edge_data, run_sumo, sumo_bin, teleport_reasons, teleports, vtypes

KEY = ("shape", "alpha", "width", "seed", "hour", "green")
HOURS = list(range(7, 21))  # the camera frames on hand cover 7h to 20h
WARM_S = 900
FREE_RATIO = 0.6  # below this share of the neighbouring edges, a 5h speed is junction delay
MOTO = (
    "base:maxSpeed=8.5;speedDev=0.2;tau=1.2;minGap=0.3;width=0.8;minGapLat=0.3;"
    "jmIgnoreFoeProb=0.3;jmIgnoreFoeSpeed=3;jmTimegapMinor=0.5;impatience=1"
)


def mapbox_speeds(obs: Path, edges: set[str]) -> pd.DataFrame:
    """Edge x hour table of median Mapbox speed (m/s)."""
    o = pd.read_csv(obs, usecols=["alley_id", "depart_at", "speed_mps"])
    o = o[o.alley_id.isin(edges) & o.depart_at.notna()]
    o["h"] = pd.to_datetime(o.depart_at).dt.hour
    return o.groupby(["alley_id", "h"]).speed_mps.median().unstack()


def chain_speed(chain: list[str], lengths: dict[str, float], v: dict[str, float], fallback: dict[str, float]) -> float:
    """Space-mean speed along a chain in km/h: total length over total time."""
    t = sum(lengths[e] / max(v.get(e) or fallback[e], 0.1) for e in chain)
    return sum(lengths[e] for e in chain) / t * 3.6


def free_speeds(v5: dict[str, float], chains: dict[str, list[str]], ratio: float = FREE_RATIO) -> tuple[dict[str, float], list[str]]:
    """Free speed per edge from the Mapbox 5h speed. An edge far below the median of its neighbours along the chain gets
    that median: the low value is junction delay located on a short edge, and as a speed limit it would cap discharge."""
    out, fixed = dict(v5), []
    for chain in chains.values():
        for i, e in enumerate(chain):
            near = [v5[x] for x in chain[max(0, i - 2): i + 3] if x != e]
            m = float(np.median(near)) if near else v5[e]
            if v5[e] < ratio * m:
                out[e], fixed = m, fixed + [e]
    return out, fixed


def camera_profile(counts: Path) -> pd.DataFrame:
    """Hourly vehicles in view (mean per frame, averaged over cameras after scaling each to its own mean) and car share.

    Index: VN hour. Columns: n (relative, mean 1 over HOURS), car_share.
    """
    c = pd.read_csv(counts)
    t = pd.to_datetime(c.utc, format="%Y-%m-%dT%H-%M") + pd.Timedelta(hours=7)
    c["h"] = t.dt.hour
    c["heavy"] = c.car + c.bus + c.truck
    c["all"] = c.moto + c.three + c.heavy
    per = c[c.h.isin(HOURS)].groupby(["camera", "h"]).agg(n=("all", "mean"), heavy=("heavy", "sum"), total=("all", "sum")).reset_index()
    per["rel"] = per.n / per.groupby("camera").n.transform("mean")
    out = per.groupby("h").agg(n=("rel", "mean"), heavy=("heavy", "sum"), total=("total", "sum"))
    out["car_share"] = (out.heavy / out.total.clip(lower=1)).clip(0, 1)
    out["n"] = out.n / out.n.mean()
    return out[["n", "car_share"]].reindex(HOURS).interpolate().bfill().ffill()


def lane_lengths(net: Path) -> dict[str, float]:
    return {e.get("id"): float(e.find("lane").get("length")) for e in ET.parse(net).getroot().iter("edge") if e.get("function") != "internal"}


def lane_counts(net: Path) -> dict[str, int]:
    return {e.get("id"): len(e.findall("lane")) for e in ET.parse(net).getroot().iter("edge") if e.get("function") != "internal"}


def retime(tls: str, net: str, edges: set[str], share: float) -> str:
    """Two-phase programs with `share` of the green going to the phase that serves `edges`. A sensitivity test: the real
    green split is not measured. Programs where those edges are green in both phases are left alone."""
    links: dict[str, list[int]] = {}
    for c in ET.parse(net).getroot().iter("connection"):
        if c.get("tl") and c.get("from") in edges:
            links.setdefault(c.get("tl"), []).append(int(c.get("linkIndex")))
    root = ET.fromstring(tls)
    for t in root.iter("tlLogic"):
        if t.get("id") not in links:
            continue
        p = t.findall("phase")
        green = [sum(p[k].get("state")[i] in "Gg" for i in links[t.get("id")]) for k in (0, 2)]
        if green[0] == green[1]:
            continue
        a, b = (p[0], p[2]) if green[0] > green[1] else (p[2], p[0])
        total = int(a.get("duration")) + int(b.get("duration"))
        main = round(total * share)
        a.set("duration", str(main))
        b.set("duration", str(total - main))
    return ET.tostring(root, encoding="unicode")


def one(job: dict) -> dict:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        patch = "".join(f'<edge id="{e}" width="{job["width"] / job["lanes"][e]:.2f}" speed="{v:.2f}"/>\n' for e, v in job["free"].items())
        (d / "patch.edg.xml").write_text(f"<edges>\n{patch}</edges>\n", encoding="utf-8")
        subprocess.run(
            [sumo_bin("netconvert"), "-s", job["net"], "-e", "patch.edg.xml", "-o", "net.xml", "--no-internal-links", "true", "--no-warnings", "true"],
            cwd=d, check=True, capture_output=True, text=True,
        )
        rows = [vtypes(MOTO)]
        for name, chain in job["chains"].items():
            r = name.replace("|", "_").replace(" ", "")
            rows.append(f'<route id="r{r}" edges="{" ".join(chain)}"/>\n')
        h = job["hour"]
        q, share = job["alpha"] * job["profile"][str(h)]["q"], job["profile"][str(h)]["car_share"]
        for name in job["chains"]:
            r = name.replace("|", "_").replace(" ", "")
            for kind, v in (("moto", q * (1 - share)), ("car", q * share)):
                if v >= 1:
                    rows.append(
                        f'<flow id="{kind}_{r}" type="{kind}" route="r{r}" begin="0" end="{WARM_S + 3600}" '
                        f'vehsPerHour="{v:.1f}" departLane="best" departPosLat="random_free" departSpeed="max"/>\n'
                    )
        (d / "rou.xml").write_text("<routes>\n" + "".join(rows) + "</routes>\n", encoding="utf-8")
        ids = " ".join(e for c in job["chains"].values() for e in c)
        tls = Path(job["tls"]).read_text(encoding="utf-8")
        if job["green"] != 0.5:
            tls = retime(tls, job["net"], set(ids.split()), job["green"])
        prog = re.sub(r"</?additional>", "", tls)
        (d / "add.xml").write_text(
            f'<additional>\n{prog}<edgeData id="c" file="ed.xml" freq="3600" begin="{WARM_S}" end="{WARM_S + 3600}" vTypes="car" edges="{ids}" excludeEmpty="true"/>\n'
            f'<edgeData id="m" file="edm.xml" freq="3600" begin="{WARM_S}" end="{WARM_S + 3600}" vTypes="moto" edges="{ids}" excludeEmpty="true"/>\n</additional>\n',
            encoding="utf-8",
        )
        extra = ("--ignore-junction-blocker", "5", "--time-to-impatience", "20", "--collision.action", "warn", "--collision.mingap-factor", "0")
        wall, err = run_sumo(d, WARM_S + 3600, 0.5, 0.4, extra)
        ed, edm = edge_data(d / "ed.xml", 0.0), edge_data(d / "edm.xml", 0.0)
        sim: dict[str, float | None] = {}
        for name, chain in job["chains"].items():
            for tag, table in (("car", ed), ("moto", edm)):
                v = {e: next((x["speed"] for x in table.get(e, []) if x.get("speed", 0) > 0), None) for e in chain}
                sim[f"{tag}:{name}"] = round(chain_speed(chain, job["lengths"], v, job["free"]), 2) if any(v.values()) else None
        per_edge = {}
        for e in {x for c in job["chains"].values() for x in c}:
            c0, m0 = (ed.get(e) or [{}])[0], (edm.get(e) or [{}])[0]
            per_edge[e] = {
                "v_car": c0.get("speed"), "v_moto": m0.get("speed"), "n_car": c0.get("entered"), "n_moto": m0.get("entered"),
                "k_moto": m0.get("density"), "wait_moto": m0.get("waitingTime"),
            }
        tr = ET.parse(d / "trip.xml").getroot().findall("tripinfo")
        arrived = [t for t in tr if float(t.get("arrival")) >= 0]
        return {k: job[k] for k in KEY} | {
            "per_edge": per_edge, "sim": sim, "wall_s": round(wall, 1), "teleports": teleports(err), "why": teleport_reasons(err), "trips": len(tr), "arrived": len(arrived),
            "depart_delay_s": round(float(np.mean([float(t.get("departDelay")) for t in tr])), 1) if tr else None,
        }


def score(pred: dict[str, float | None], target: dict[str, float]) -> dict[str, float]:
    """Error against the target, and against its shape: each hour's speed relative to the fastest scored hour."""
    h = [x for x in pred if pred[x] is not None]
    p, m = np.array([pred[x] for x in h]), np.array([target[x] for x in h])
    return {
        "mape": round(float(np.mean(np.abs(p - m) / m)) * 100, 1),
        "peak_drop_sim": round(float(1 - p.min() / p.max()) * 100, 1),
        "peak_drop_map": round(float(1 - m.min() / m.max()) * 100, 1),
        "corr": round(float(np.corrcoef(p, m)[0, 1]), 2) if len(h) > 2 and p.std() > 0 else None,
        "n": len(h),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--net", type=Path, required=True, help="directory of routing2.net_rules output")
    ap.add_argument("--obs", type=Path, required=True)
    ap.add_argument("--axes", type=Path, required=True)
    ap.add_argument("--counts", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--calib", required=True)
    ap.add_argument("--holdout", required=True)
    ap.add_argument("--alpha", type=float, nargs="+", default=[500, 1000, 1500, 2000, 3000, 4000, 5000, 7000])
    ap.add_argument("--width", type=float, nargs="+", default=[7.0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--flow-shape", nargs="+", choices=["n_v", "n"], default=["n_v", "n"], help="hourly inflow proportional to count x speed, or to count")
    ap.add_argument("--green", type=float, nargs="+", default=[0.5], help="share of the green given to the corridor (0.5: as built)")
    ap.add_argument("--raw-free", action="store_true", help="use the Mapbox 5h speed on every edge, without free_speeds")
    ap.add_argument("--hours", type=int, nargs="+", default=[8, 10, 12, 15, 17, 18])
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    axes = json.loads(a.axes.read_text(encoding="utf-8"))
    chains = {k: axes[k] for k in (a.calib, a.holdout)}
    net = a.net / "quan4_v5.net.xml"
    lengths = lane_lengths(net)
    lanes = lane_counts(net)
    table = mapbox_speeds(a.obs, {e for c in chains.values() for e in c})
    free = {e: float(table.loc[e, 5]) if e in table.index and pd.notna(table.loc[e, 5]) else 8.0 for c in chains.values() for e in c}
    if not a.raw_free:
        free, fixed = free_speeds(free, chains)
        print(f"[l3] free speed replaced on {len(fixed)} edges: {fixed}", flush=True)
    target = {
        n: {str(h): round(chain_speed(c, lengths, {e: float(table.loc[e, h]) for e in c if e in table.index and pd.notna(table.loc[e, h])}, free), 2) for h in HOURS}
        for n, c in chains.items()
    }
    cam = camera_profile(a.counts)
    v = pd.Series({h: target[a.calib][str(h)] for h in HOURS})
    profiles = {}
    for sh in a.flow_shape:
        q = cam.n * v if sh == "n_v" else cam.n.copy()
        q = q / q.mean()
        profiles[sh] = {str(h): {"q": round(float(q[h]), 3), "car_share": round(float(cam.car_share[h]), 3)} for h in HOURS}
    (a.out / "target.json").write_text(json.dumps({"target": target, "profiles": profiles}, ensure_ascii=False, indent=1), encoding="utf-8")
    path = a.out / "l3.jsonl"
    done = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    have = {tuple(r[k] for k in KEY) for r in done}
    jobs = [
        dict(shape=sh, alpha=al, width=w, seed=s, hour=h, green=gr, net=str(net), tls=str(a.net / f"tls_seed{s}.add.xml"), chains=chains, lengths=lengths, lanes=lanes, free=free, profile=profiles[sh])
        for sh in a.flow_shape for al in a.alpha for w in a.width for s in a.seeds for h in a.hours for gr in a.green
        if (sh, al, w, s, h, gr) not in have
    ]
    print(f"[l3] {len(jobs)} runs to do, {len(done)} done", flush=True)
    with Pool(a.workers) as p, path.open("a", encoding="utf-8") as f:
        for r in p.imap_unordered(one, jobs, chunksize=1):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            done.append(r)
            print({k: r[k] for k in (*KEY, "teleports", "arrived", "trips", "depart_delay_s", "wall_s")}, flush=True)
    groups: dict[tuple, list[dict]] = {}
    for r in done:
        groups.setdefault((r["shape"], r["alpha"], r["width"], r["green"]), []).append(r)
    rows = []
    for (sh, al, w, gr), rs in sorted(groups.items()):
        out = {"shape": sh, "alpha": al, "width": w, "green": gr, "teleports": sum(r["teleports"] for r in rs), "max_depart_delay_s": max(r["depart_delay_s"] or 0 for r in rs)}
        for tag, name in (("calib", a.calib), ("holdout", a.holdout)):
            mean = {}
            for h in a.hours:
                vals = [r["sim"][f"car:{name}"] for r in rs if r["hour"] == h and r["sim"][f"car:{name}"] is not None]
                mean[str(h)] = round(float(np.mean(vals)), 2) if vals else None
            out[tag] = score(mean, target[name]) | {"speeds": mean}
        rows.append(out)
        print(out, flush=True)
    (a.out / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("L3_DONE", flush=True)


if __name__ == "__main__":
    main()
