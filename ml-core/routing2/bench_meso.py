"""Speed and sanity benchmark for the meso simulator (P2 gate: >= 1e4 decisions/s).

For each batch size: run AppReroute (controlled share) + ShortestPath (rest)
for the horizon and report wall time, simulated seconds per wall second,
decisions per second, peak GPU memory, and the episode metrics. A demand sweep
runs both baselines alone at a few demand levels, to see congestion appear.

    python -u -m routing2.bench_meso --device cuda --batches 64 256 1024 \
        --out artifacts/out/quan4/routing2/bench.json
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import time
from dataclasses import replace
from pathlib import Path

import torch

from .demand import make_demand, pick_zones
from .graph import DEFAULT_GRAPH, load_graph
from .meso_gpu import MesoSim
from .params import SimConfig
from .policies import AppReroute, Mixed, ShortestPath


def _sync(dev: str) -> None:
    if dev.startswith("cuda"):
        torch.cuda.synchronize()


def run_once(g, zones, cfg, seeds, tph, pen, policy, dev):
    d = make_demand(g, zones, seeds, tph, cfg.horizon_s, pen)
    sim = MesoSim(g, d, zones, cfg)
    if dev.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats()
    _sync(dev)
    t0 = time.perf_counter()
    r = sim.run(policy)
    _sync(dev)
    wall = time.perf_counter() - t0
    mem = torch.cuda.max_memory_allocated() / 2**20 if dev.startswith("cuda") else 0.0
    return r, wall, mem, sim.N


def med(x):
    return round(st.median(x), 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--batches", type=int, nargs="+", default=[8, 64])
    ap.add_argument("--horizon", type=float, default=1800.0)
    ap.add_argument("--tph", type=float, default=3000.0, help="trips per hour per env")
    ap.add_argument("--penetration", type=float, default=0.3)
    ap.add_argument("--sweep-tph", type=float, nargs="*", default=[1000.0, 3000.0, 6000.0])
    ap.add_argument("--sweep-batch", type=int, default=16)
    ap.add_argument("--zones", type=int, default=32)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    dev = args.device
    cfg = replace(SimConfig(), horizon_s=args.horizon)
    g = load_graph(DEFAULT_GRAPH, cfg, device=dev)
    zones = pick_zones(g, args.zones, seed=0)
    print(f"[bench] device={dev} nodes={g.n_nodes} edges={g.n_edges} zones={args.zones} "
          f"horizon={cfg.horizon_s}s dt={cfg.dt}", flush=True)
    out = {"device": dev, "horizon_s": cfg.horizon_s, "speed": [], "sweep": []}

    for B in args.batches:
        seeds = list(range(1000, 1000 + B))
        pol = Mixed(AppReroute(60.0), ShortestPath())
        r, wall, mem, N = run_once(g, zones, cfg, seeds, args.tph, args.penetration, pol, dev)
        row = {
            "batch": B, "vehicles_per_env": N, "wall_s": round(wall, 2),
            "sim_s_per_wall_s": round(B * cfg.horizon_s / wall, 1),
            "decisions_per_s": round(r["decisions"] / wall, 1),
            "peak_mem_mb": round(mem, 1),
            "mean_tt_ctrl_s": med(r["mean_tt_ctrl_s"]), "mean_tt_bg_s": med(r["mean_tt_bg_s"]),
            "arrived_share": med(r["arrived_share"]), "forced_moves": r["forced_moves"],
        }
        out["speed"].append(row)
        print(f"[speed] {row}", flush=True)

    for tph in args.sweep_tph:
        seeds = list(range(2000, 2000 + args.sweep_batch))
        for name, pol in (("shortest", ShortestPath()), ("app60", AppReroute(60.0))):
            r, wall, _, N = run_once(g, zones, cfg, seeds, tph, 1.0, pol, dev)
            row = {
                "tph": tph, "policy": name, "vehicles_per_env": N,
                "mean_tt_started_s": med(r["mean_tt_started_s"]),
                "mean_tt_arrived_s": med(r["mean_tt_arrived_s"]),
                "arrived_share": med(r["arrived_share"]),
                "alley_dist_share": med(r["alley_dist_share"]),
                "max_alley_occ_ratio": med(r["max_alley_occ_ratio"]),
                "stuck": sum(r["stuck"]), "forced_moves": r["forced_moves"], "wall_s": round(wall, 2),
            }
            out["sweep"].append(row)
            print(f"[sweep] {row}", flush=True)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"[bench] wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
