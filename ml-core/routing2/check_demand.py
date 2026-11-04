"""Is there anything to coordinate? Baselines on a synthetic peak, before any training.

For each demand setting: T_all, T_cust, J and the congestion index of ff, app and greedy with a few
queue costs, on the same trips, with the same events. Training is worth it only where free-flow
routing loses clearly to a controller that reacts. The demand numbers are invented.

    python -u -m routing2.check_demand --workers 16 --seeds 2 --json artifacts/out/quan4/routing2_runs/check_demand.json
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import tempfile
from pathlib import Path

import numpy as np

from .graph import DEFAULT_GRAPH
from .objectives import objective
from .sumo_marl import _worker_init, _worker_run
from .sumo_net import build_net


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--tph", type=float, nargs="+", default=[6000.0, 8000.0, 10000.0])
    ap.add_argument("--hot-share", type=float, nargs="+", default=[0.3, 0.6])
    ap.add_argument("--peak-sd", type=float, default=0.15)
    ap.add_argument("--pen", type=float, default=0.5)
    ap.add_argument("--horizon", type=float, default=900.0)
    ap.add_argument("--depart-window", type=float, default=600.0)
    ap.add_argument("--drain", type=float, default=900.0)
    ap.add_argument("--queue", type=float, nargs="+", default=[0.5, 2.0], help="greedy: s per fleet vehicle")
    ap.add_argument("--report-drop", type=float, default=0.2)
    ap.add_argument("--report-noise", type=float, default=0.1)
    ap.add_argument("--compliance", type=float, default=0.9)
    ap.add_argument("--bg-reroute", type=float, default=0.3)
    ap.add_argument("--net-dir", type=Path, default=Path("../sumo-env/networks/v4"))
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()
    net = build_net(DEFAULT_GRAPH, args.net_dir)
    rows = []
    with tempfile.TemporaryDirectory(dir=".") as work:
        for hot in args.hot_share:
            conf = {"horizon": args.horizon, "zones": 32, "net": str(net), "hidden": 64, "layers": 3, "max_detour": 0.5,
                    "reward": "selfish", "live_every": 10.0, "incident_rate": 2.0, "school_rate": 1.0,
                    "depart_window": args.depart_window, "hot_share": hot, "hot_zones": 4, "peak_sd": args.peak_sd,
                    "greedy_queue": 0.0, "report_drop": args.report_drop, "report_noise": args.report_noise,
                    "compliance": args.compliance, "bg_reroute": args.bg_reroute, "work_dir": work}
            pols = [("ff", "ff", 0.0), ("app", "app", 0.0)] + [(f"greedy{q:g}", "greedy", q) for q in args.queue]
            with mp.get_context("spawn").Pool(args.workers, _worker_init, (conf,)) as pool:
                tasks = [{"seed": 50000 + s, "tph": tph, "pen": args.pen, "policy": kind, "record": False,
                          "drain": args.drain, "name": name, "queue_s": q}
                         for tph in args.tph for s in range(args.seeds) for name, kind, q in pols]
                res = pool.map(_worker_run, tasks, chunksize=1)
            for tph in args.tph:
                by = {}
                for name, _, _ in pols:
                    m = [r["metrics"] for r, x in zip(res, tasks) if x["tph"] == tph and x["name"] == name]
                    by[name] = {"J": round(float(np.mean([objective(k, 0.5) for k in m])), 1),
                                "T_all": round(float(np.mean([k["T_all_s"] for k in m])), 1),
                                "T_cust": round(float(np.mean([k["T_cust_s"] for k in m])), 1),
                                "cong": round(float(np.mean([k["congestion_index"] for k in m])), 2),
                                "arr": round(float(np.mean([k["arrived_share_all"] for k in m])), 3),
                                "tele": round(float(np.mean([k["teleports_per_1k_trips"] for k in m])), 1)}
                ff = by["ff"]["J"]
                best = min((v["J"], k) for k, v in by.items() if k != "ff")
                row = {"tph": tph, "hot_share": hot, "ff_vs_best_pct": round(100 * (ff - best[0]) / ff, 1),
                       "best": best[1], "by": by}
                rows.append(row)
                print(json.dumps(row), flush=True)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("CHECK_DEMAND_DONE", flush=True)


if __name__ == "__main__":
    main()
