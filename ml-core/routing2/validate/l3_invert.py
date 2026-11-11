"""L3 by inversion: the flow each direction needs, hour by hour, to match its Mapbox speed; then the density this gives
at the corridor cameras against their counts.

Flow is not measured and Mapbox gives only speed, so speed alone cannot test the simulator. The camera count is the
independent check: for each hour and direction, bisect the inflow until the simulated car speed equals Mapbox, then
compare the simulated number of vehicles within --radius m of each camera with what the camera counts, by hour. The
camera's view length is not known, so only the hourly shape is scored (correlation, peak over noon ratio).

    python -m routing2.validate.l3_invert --net DIR --obs edge_obs.csv --axes axes.json --counts counts.csv \\
        --cameras cameras.json --graph graph.json --out DIR --chains "Khánh Hội|324" "Khánh Hội|142" --hours 8 12 17
"""

from __future__ import annotations

import argparse
import json
import math
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from .l3_axis import MOTO, camera_profile, chain_speed, free_speeds, lane_counts, lane_lengths, mapbox_speeds, one

LO, HI = 30.0, 6000.0  # veh/h per direction


def geo_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance in metres between two (lon, lat) points."""
    dx = (a[0] - b[0]) * 111320 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot(dx, (a[1] - b[1]) * 110540)


def ends(edge: str) -> tuple[str, str]:
    _, u, v, _ = edge.split("_")
    return u, v


def view_edges(cam: tuple[float, float], chains: dict[str, list[str]], geo: dict, radius: float) -> list[str]:
    """Corridor edges with both ends within `radius` of the camera."""
    out = []
    for c in chains.values():
        for e in c:
            u, v = ends(e)
            if all(n in geo and geo_m(cam, (float(geo[n]["lon"]), float(geo[n]["lat"]))) <= radius for n in (u, v)):
                out.append(e)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for k in ("net", "obs", "axes", "counts", "cameras", "graph", "out"):
        ap.add_argument(f"--{k}", type=Path, required=True)
    ap.add_argument("--chains", nargs=2, required=True)
    ap.add_argument("--hours", type=int, nargs="+", default=[8, 12, 17])
    ap.add_argument("--iters", type=int, default=7)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--width", type=float, default=7.0)
    ap.add_argument("--radius", type=float, default=100.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--moto", default=MOTO, help="motorcycle vType spec, as in validate.common.moto_attrs")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    axes = json.loads(a.axes.read_text(encoding="utf-8"))
    chains = {k: axes[k] for k in a.chains}
    net = a.net / "quan4_v5.net.xml"
    lengths, lanes = lane_lengths(net), lane_counts(net)
    table = mapbox_speeds(a.obs, {e for c in chains.values() for e in c})
    free = {e: float(table.loc[e, 5]) if e in table.index and pd.notna(table.loc[e, 5]) else 8.0 for c in chains.values() for e in c}
    free, _ = free_speeds(free, chains)
    target = {
        n: {h: chain_speed(c, lengths, {e: float(table.loc[e, h]) for e in c if e in table.index and pd.notna(table.loc[e, h])}, free) for h in a.hours}
        for n, c in chains.items()
    }
    share = camera_profile(a.counts).car_share
    base = dict(moto=a.moto, shape="inv", alpha=1.0, width=a.width, seed=a.seed, green=0.5, arrivals="poisson", net=str(net), tls=str(a.net / f"tls_seed{a.seed}.add.xml"),
                chains=chains, lengths=lengths, lanes=lanes, free=free)

    lo = {(h, n): math.log(LO) for h in a.hours for n in chains}
    hi = {(h, n): math.log(HI) for h in a.hours for n in chains}
    log = (a.out / "iters.jsonl").open("a", encoding="utf-8")
    last: dict[int, dict] = {}
    with Pool(a.workers) as pool:
        for it in range(a.iters + 1):
            jobs = []
            for h in a.hours:
                scale = {n: math.exp((lo[h, n] + hi[h, n]) / 2) for n in chains}
                jobs.append(base | dict(hour=h, profile={str(h): {"q": 1.0, "car_share": float(share[h])}}, scale=scale))
            for job, r in zip(jobs, pool.map(one, jobs)):
                h = job["hour"]
                last[h] = r | {"scale": job["scale"]}
                row = {"iter": it, "hour": h, "teleports": r["teleports"], "depart_delay_s": r["depart_delay_s"]}
                for n in chains:
                    v = r["sim"][f"car:{n}"]
                    row[n] = {"q": round(job["scale"][n]), "sim": v, "map": round(target[n][h], 2)}
                    if it < a.iters and v is not None:
                        if v > target[n][h]:
                            lo[h, n] = math.log(job["scale"][n])
                        else:
                            hi[h, n] = math.log(job["scale"][n])
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                log.flush()
                print(row, flush=True)

    cams = json.loads(a.cameras.read_text(encoding="utf-8"))
    geo = json.loads(a.graph.read_text(encoding="utf-8"))["nodes_geo"]
    counts = pd.read_csv(a.counts)
    counts["h"] = (pd.to_datetime(counts.utc, format="%Y-%m-%dT%H-%M") + pd.Timedelta(hours=7)).dt.hour
    counts["n"] = counts.moto + counts.three + counts.car + counts.bus + counts.truck
    result = {"flows": {}, "cameras": {}}
    for h in a.hours:
        result["flows"][h] = {n: {"q": round(last[h]["scale"][n]), "sim": last[h]["sim"][f"car:{n}"], "map": round(target[n][h], 2),
                                  "at_bound": abs(math.log(last[h]["scale"][n]) - math.log(LO)) < 0.3 or abs(math.log(last[h]["scale"][n]) - math.log(HI)) < 0.3}
                              for n in chains}
    for c in cams:
        cid = c.get("cameraId")
        if "lon" not in c or cid not in set(counts.camera):
            continue
        view = view_edges((float(c["lon"]), float(c["lat"])), chains, geo, a.radius)
        if not view:
            continue
        sim_n = {h: sum(((last[h]["per_edge"][e].get("k_moto") or 0) + (last[h]["per_edge"][e].get("k_car") or 0)) * lengths[e] / 1000 for e in view) for h in a.hours}
        cam_n = counts[counts.camera == cid].groupby("h").n.mean()
        hs = [h for h in a.hours if h in cam_n.index]
        s, m = np.array([sim_n[h] for h in hs]), np.array([cam_n[h] for h in hs])
        result["cameras"][cid] = {
            "view_edges": len(view), "view_m": round(sum(lengths[e] for e in view)),
            "sim_vehicles": {h: round(sim_n[h], 1) for h in hs}, "camera_vehicles": {h: round(float(cam_n[h]), 1) for h in hs},
            "corr": round(float(np.corrcoef(s, m)[0, 1]), 2) if len(hs) > 2 and s.std() > 0 and m.std() > 0 else None,
            "max_over_min_sim": round(float(s.max() / max(s.min(), 1e-6)), 2), "max_over_min_cam": round(float(m.max() / m.min()), 2),
        }
    (a.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1), flush=True)
    print("L3_INVERT_DONE", flush=True)


if __name__ == "__main__":
    main()
