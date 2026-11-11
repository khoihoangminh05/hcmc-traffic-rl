"""L1: fundamental diagram of one road section, on a closed ring so density is held fixed.

Motorcycles (and optional cars) drive a 4-edge ring. After a warm-up the mean speed gives flow = density x speed.
A closed ring reaches the congested branch without a bottleneck and has no insertion limit at the inflow.

    python -m routing2.validate.l1_link --out /tmp/l1 --workers 8
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import tempfile
from multiprocessing import Pool
from pathlib import Path

from .common import MOTO_VARIANTS, build_net, edge_data, moto_attrs, run_sumo, teleports, vtypes

SIDE_M = 200.0  # ring is a square of 4 edges, 800 m in all
WARM_S, MEAS_S = 240.0, 240.0
LANE_MAP = {"1x3.5": (1, 3.5), "1x7": (1, 7.0), "2x3.5": (2, 3.5)}


def ring(d: Path, lanes: int, width: float) -> None:
    pts = {"a": (0, 0), "b": (SIDE_M, 0), "c": (SIDE_M, SIDE_M), "d": (0, SIDE_M)}
    nodes = "".join(f'<node id="{k}" x="{x}" y="{y}" type="unregulated"/>\n' for k, (x, y) in pts.items())
    order = ["a", "b", "c", "d", "a"]
    edges = "".join(
        f'<edge id="{u}{v}" from="{u}" to="{v}" numLanes="{lanes}" width="{width}" speed="15"/>\n'
        for u, v in zip(order, order[1:])
    )
    build_net(d, nodes, edges, extra=("--junctions.limit-turn-speed", "-1", "--no-internal-links", "false"))


def one(job: dict) -> dict:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        lanes, width = LANE_MAP[job["road"]]
        ring(d, lanes, width)
        area = 4 * SIDE_M * lanes * width
        # density is motorcycle-equivalent per m2; a car occupies job["car_eq"] motorcycle slots
        n_eq = job["k"] * area
        n_car = int(round(n_eq * job["car_share"] / job["car_eq"]))
        n_moto = int(round(n_eq * (1 - job["car_share"])))
        edges = "ab bc cd da"
        rows = []
        kinds = ["moto"] * n_moto + ["car"] * n_car
        kinds = [kinds[i] for i in sorted(range(len(kinds)), key=lambda i: math.sin(i * 12.9898) % 1)]
        starts = {"ab": "ab bc cd da", "bc": "bc cd da ab", "cd": "cd da ab bc", "da": "da ab bc cd"}
        ring_edges = list(starts)
        if n_car == 0:
            # Motorcycles only: an explicit grid of side-by-side files, since random insertion stops near k = 0.1.
            # No insertion checks: IDM refuses spaced-out standing vehicles otherwise (113 of 353 at k = 0.063, silently).
            attrs = moto_attrs(job["moto"])
            veh_w = float(re.search(r'\bwidth="([^"]+)"', attrs).group(1))
            gap_lat = float(re.search(r'minGapLat="([^"]+)"', attrs).group(1))
            files = max(1, int(width // (veh_w + gap_lat + 0.02)))
            pitch = width / files
            slots_per_edge = max(1, math.ceil(n_moto / (4 * lanes * files)))
            dx = (SIDE_M - 2.0) / slots_per_edge
            i = 0
            for e, lane, f, s in itertools.product(ring_edges, range(lanes), range(files), range(slots_per_edge)):
                if i >= n_moto:
                    break
                lat = -width / 2 + pitch * (f + 0.5)
                stagger = 0.5 * dx if f % 2 else 0.0
                rows.append(
                    f'<vehicle id="{i}" type="moto" depart="0" departLane="{lane}" departPos="{s * dx + stagger + 1:.2f}" '
                    f'departPosLat="{lat:.2f}" departSpeed="0" insertionChecks="none"><route edges="{starts[e]}" repeat="400"/></vehicle>'
                )
                i += 1
        else:
            for i, kind in enumerate(kinds):
                start = starts[ring_edges[i % 4]]
                rows.append(
                    f'<vehicle id="{i}" type="{kind}" depart="{i * 0.05:.2f}" departLane="random" departPos="random_free" '
                    f'departPosLat="random_free" departSpeed="0"><route edges="{start}" repeat="400"/></vehicle>'
                )
        (d / "rou.xml").write_text("<routes>\n" + vtypes(job["moto"]) + "\n".join(rows) + "\n</routes>\n")
        (d / "add.xml").write_text(
            f'<additional><edgeData id="e" file="ed.xml" freq="{MEAS_S / 4}" begin="{WARM_S}" '
            f'end="{WARM_S + MEAS_S}" excludeEmpty="true"/></additional>\n'
        )
        wall, err = run_sumo(d, WARM_S + MEAS_S, job["step"], job["lateral"])
        ed = edge_data(d / "ed.xml", WARM_S)
        # sampledSeconds-weighted mean speed over all ring edges and intervals
        ss, sv = 0.0, 0.0
        for iv in itertools.chain.from_iterable(ed.values()):
            s = iv.get("sampledSeconds", 0.0)
            ss += s
            sv += s * iv.get("speed", 0.0)
        v = sv / ss if ss else 0.0
        n_seen = ss / MEAS_S
        tele = teleports(err)
        k_real = n_seen / (4 * SIDE_M * lanes * width)  # vehicles per m2 actually on the road
        q_per_m = n_seen / (4 * SIDE_M) * v * 3600 / (lanes * width)  # vehicles per hour per metre of width
        return {
            **job, "n_wanted": n_moto + n_car, "n_seen": round(n_seen, 1), "k_real": round(k_real, 4),
            "v_ms": round(v, 2), "q_veh_h_m": round(q_per_m), "teleports": tele, "wall_s": round(wall, 1),
        }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--moto", nargs="+", default=list(MOTO_VARIANTS))
    ap.add_argument("--road", nargs="+", default=list(LANE_MAP))
    ap.add_argument("--lateral", nargs="+", type=float, default=[0.2, 0.4])
    ap.add_argument("--step", nargs="+", type=float, default=[0.25, 0.5])
    ap.add_argument("--car-share", nargs="+", type=float, default=[0.0])
    ap.add_argument("--car-eq", type=float, default=3.4, help="motorcycles per car (Hanoi MEU, cited in the register)")
    ap.add_argument("--k", nargs="+", type=float, default=[0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3, 0.35])
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    jobs = [
        dict(moto=m, road=r, lateral=l, step=s, car_share=c, car_eq=a.car_eq, k=k)
        for m, r, l, s, c, k in itertools.product(a.moto, a.road, a.lateral, a.step, a.car_share, a.k)
    ]
    print(f"[l1] {len(jobs)} runs", flush=True)
    out = a.out / "l1.jsonl"
    with Pool(a.workers) as p, out.open("w") as f:
        for r in p.imap_unordered(one, jobs):
            f.write(json.dumps(r) + "\n")
            f.flush()
            print(r, flush=True)
    print("L1_DONE", flush=True)


if __name__ == "__main__":
    main()
