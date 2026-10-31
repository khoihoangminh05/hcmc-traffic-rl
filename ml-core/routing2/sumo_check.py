"""Meso vs SUMO on the same trips and routes (P2 gate: trip-time R^2 >= 0.8).

For each demand level and seed: the meso demand, the free-flow shortest routes
(what ShortestPath drives), the meso run with FixedRoute, and a SUMO run of the
same vehicles on the same routes (motorbikes, sublane model). Trip time is
arrival minus planned departure, so waiting to enter counts in both.

Reports, per level: trip-time R^2 of meso against SUMO (1 - SSres/SStot) and
squared Pearson r on trips that arrived in both, and the same for delay (trip
time minus the route's free-flow time): at low demand trip time is mostly
length / speed in both models, so the delay R^2 is the real test of congestion, mean trip time and arrived
share in each, SUMO teleports. Never overwrites: the file name has a UTC stamp.

    python -u -m routing2.sumo_check --tph 500 1000 1500 2000 --seeds 61000 61001 \
        --horizon 1800 --out-dir artifacts/out/quan4/routing2
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import torch

from .demand import make_demand, pick_zones
from .graph import DEFAULT_GRAPH, load_graph
from .meso_gpu import ARRIVED, MesoSim
from .params import SimConfig
from .policies import FixedRoute, free_flow_routes
from .sumo_net import build_net, sumo_binary

MOTO_VTYPE = (
    '<vType id="moto" vClass="motorcycle" length="1.9" width="0.8" minGap="0.5" '
    'maxSpeed="15" accel="2.5" decel="4.5" sigma="0.5" speedDev="0" '
    'latAlignment="arbitrary" minGapLat="0.3" lcSublane="1.0" lcPushy="0.5"/>'
)


def write_routes(path: Path, edge_ids: list[str], routes: torch.Tensor, dep_t: torch.Tensor) -> list[int]:
    """One <vehicle> per trip with a non-empty route; returns the trip indices written."""
    order = torch.argsort(dep_t).tolist()
    kept = []
    with path.open("w", encoding="utf-8") as f:
        f.write("<routes>\n  " + MOTO_VTYPE + "\n")
        for i in order:
            r = [edge_ids[e] for e in routes[i].tolist() if e >= 0]
            if not r:
                continue
            kept.append(i)
            f.write(
                f'  <vehicle id="v{i}" type="moto" depart="{float(dep_t[i]):.2f}" departLane="best" '
                f'departSpeed="max"><route edges="{" ".join(r)}"/></vehicle>\n'
            )
        f.write("</routes>\n")
    return kept


def run_sumo(net: Path, rou: Path, horizon: float, step: float, lateral: float, teleport: float) -> dict:
    try:
        import libsumo  # type: ignore[import-not-found]
    except ImportError:  # no libsumo wheel for this Python (e.g. 3.13 on Windows): slower TraCI
        import traci as libsumo  # type: ignore[import-not-found,no-redef]

    libsumo.start([
        sumo_binary("sumo"), "-n", str(net), "-r", str(rou),
        "--step-length", str(step), "--lateral-resolution", str(lateral),
        "--time-to-teleport", str(teleport), "--no-step-log", "true", "--no-warnings", "true",
        "--end", str(horizon),
    ])
    arrived: dict[int, float] = {}
    try:
        while libsumo.simulation.getTime() < horizon - 1e-9:
            libsumo.simulationStep()
            t = libsumo.simulation.getTime()
            for vid in libsumo.simulation.getArrivedIDList():
                arrived[int(vid[1:])] = t
        teleports = libsumo.simulation.getStartingTeleportNumber()
    finally:
        libsumo.close()
    return {"arrived": arrived, "teleports_last_step": teleports}


def r2(ref: list[float], est: list[float]) -> tuple[float, float]:
    n = len(ref)
    if n < 3:
        return math.nan, math.nan
    mr = sum(ref) / n
    me = sum(est) / n
    ss_tot = sum((r - mr) ** 2 for r in ref)
    ss_res = sum((r - e) ** 2 for r, e in zip(ref, est))
    cov = sum((r - mr) * (e - me) for r, e in zip(ref, est))
    ve = sum((e - me) ** 2 for e in est)
    det = 1.0 - ss_res / ss_tot if ss_tot > 0 else math.nan
    pear = cov * cov / (ss_tot * ve) if ss_tot > 0 and ve > 0 else math.nan
    return det, pear


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tph", type=float, nargs="+", default=[500.0, 1000.0, 1500.0, 2000.0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[61000, 61001])
    ap.add_argument("--horizon", type=float, default=1800.0)
    ap.add_argument("--zones", type=int, default=32)
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--lateral", type=float, default=0.8)
    ap.add_argument("--teleport", type=float, default=180.0)
    ap.add_argument("--net-dir", type=Path, default=Path("../sumo-env/networks/v4"))
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/out/quan4/routing2"))
    args = ap.parse_args()

    cfg = replace(SimConfig(), horizon_s=args.horizon, stuck_time_s=args.teleport)
    g = load_graph(DEFAULT_GRAPH, cfg)
    zones = pick_zones(g, args.zones, seed=0)
    net = build_net(DEFAULT_GRAPH, args.net_dir)
    work = args.out_dir / "sumo_check_work"
    work.mkdir(parents=True, exist_ok=True)
    report = {"args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
              "net": str(net), "levels": []}

    for tph in args.tph:
        d = make_demand(g, zones, args.seeds, tph, cfg.horizon_s, 1.0)
        sim = MesoSim(g, d, zones, cfg)
        routes = free_flow_routes(g, sim.free_tt(), zones, sim.orig, sim.dest_zone)
        meso = MesoSim(g, d, zones, cfg)
        meso.run(FixedRoute(routes))
        m_arr = (meso.status == ARRIVED)
        m_tt = meso.arrive_t - meso.dep_t
        ff_edge = g.length / g.v_free
        ff = torch.where(routes >= 0, ff_edge[routes.clamp(min=0)], 0.0).sum(1)
        ref, est, s_all, m_all = [], [], [], []
        dref, dest = [], []
        teleports = 0
        n_s_arr = 0
        for b, seed in enumerate(args.seeds):
            lo, hi = b * sim.N, (b + 1) * sim.N
            rou = work / f"tph{int(tph)}_seed{seed}.rou.xml"
            kept = write_routes(rou, g.edge_ids, routes[lo:hi], meso.dep_t[lo:hi])
            t0 = time.perf_counter()
            res = run_sumo(net, rou, cfg.horizon_s, args.step, args.lateral, args.teleport)
            wall = time.perf_counter() - t0
            teleports += res["teleports_last_step"]
            n_s_arr += len(res["arrived"])
            for i in kept:
                dep = float(meso.dep_t[lo + i])
                s_end = res["arrived"].get(i, cfg.horizon_s)
                m_end = float(meso.arrive_t[lo + i]) if bool(m_arr[lo + i]) else cfg.horizon_s
                s_all.append(s_end - dep)
                m_all.append(m_end - dep)
                if i in res["arrived"] and bool(m_arr[lo + i]):
                    ref.append(res["arrived"][i] - dep)
                    est.append(float(m_tt[lo + i]))
                    dref.append(ref[-1] - float(ff[lo + i]))
                    dest.append(est[-1] - float(ff[lo + i]))
            print(f"[sumo] tph={tph:g} seed={seed} trips={len(kept)} sumo_arrived={len(res['arrived'])} "
                  f"wall={wall:.1f}s", flush=True)
        det, pear = r2(ref, est)
        det_all, pear_all = r2(s_all, m_all)
        det_d, pear_d = r2(dref, dest)
        row = {
            "tph": tph, "trips": len(s_all),
            "both_arrived": len(ref),
            "r2_trip_tt_both_arrived": round(det, 4), "pearson2_both_arrived": round(pear, 4),
            "r2_delay_both_arrived": round(det_d, 4), "pearson2_delay": round(pear_d, 4),
            "mean_delay_sumo_s": round(sum(dref) / max(len(dref), 1), 1),
            "mean_delay_meso_s": round(sum(dest) / max(len(dest), 1), 1),
            "r2_trip_tt_all_capped": round(det_all, 4), "pearson2_all_capped": round(pear_all, 4),
            "mean_tt_sumo_s": round(sum(s_all) / len(s_all), 1),
            "mean_tt_meso_s": round(sum(m_all) / len(m_all), 1),
            "arrived_share_sumo": round(n_s_arr / len(s_all), 3),
            "arrived_share_meso": round(float(m_arr.float().mean()), 3),
            "sumo_teleports": teleports,
            "meso_forced_moves": meso.n_forced,
        }
        report["levels"].append(row)
        print(f"[check] {row}", flush=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out_dir / f"sumo_check_{stamp}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[check] wrote {out}", flush=True)


if __name__ == "__main__":
    main()
