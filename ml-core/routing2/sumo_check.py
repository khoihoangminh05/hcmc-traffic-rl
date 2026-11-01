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

With two or more `--sumo-seeds`, SUMO runs again with another driver RNG seed and
`r2_delay_sumo_vs_sumo` is SUMO's own repeatability: the ceiling a meso model can
reach on per-trip delay. Every SUMO arrival is also written to
`sumo_trips_<stamp>.json`, the target `routing2.calib_meso` fits to.

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
from .edge_metrics import cell_delay, cell_mask, cell_scores
from .graph import DEFAULT_GRAPH, load_graph
from .meso_gpu import ARRIVED, MesoSim
from .params import SimConfig
from .policies import FixedRoute, free_flow_routes, noisy_routes, route_noise
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


def read_exits(path: Path) -> dict[int, list[float]]:
    """Per vehicle, the time it left each edge of its route (vehroute exitTimes)."""
    import xml.etree.ElementTree as ET

    out: dict[int, list[float]] = {}
    for _, el in ET.iterparse(path, events=("end",)):
        if el.tag != "vehicle":
            continue
        r = el.find("route")
        ex = (r.get("exitTimes") or "").split() if r is not None else []
        out[int(el.get("id")[1:])] = [float(x) for x in ex if float(x) >= 0]
        el.clear()
    return out


def run_sumo(
    net: Path, rou: Path, horizon: float, step: float, lateral: float, teleport: float,
    seed: int = 23423, vehroute: Path | None = None,
) -> dict:
    try:
        import libsumo  # type: ignore[import-not-found]
    except ImportError:  # no libsumo wheel for this Python (e.g. 3.13 on Windows): slower TraCI
        import traci as libsumo  # type: ignore[import-not-found,no-redef]

    libsumo.start([
        sumo_binary("sumo"), "-n", str(net), "-r", str(rou),
        "--step-length", str(step), "--lateral-resolution", str(lateral),
        "--time-to-teleport", str(teleport), "--no-step-log", "true", "--no-warnings", "true",
        "--end", str(horizon), "--seed", str(seed),
    ] + ([] if vehroute is None else [
        "--vehroute-output", str(vehroute), "--vehroute-output.exit-times", "true",
        "--vehroute-output.write-unfinished", "true",
    ]))
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
    res = {"arrived": arrived, "teleports_last_step": teleports}
    if vehroute is not None:
        res["exits"] = read_exits(vehroute)
    return res


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


def exits_tensor(rows: list[list[float]], L: int) -> torch.Tensor:
    x = torch.full((len(rows), L), math.inf)
    for i, r in enumerate(rows):
        if r:
            x[i, : min(L, len(r))] = torch.tensor(r[:L])
    return x


def cell_row(g, routes, meso, k_rows, s_ex, H: float, bin_s: float) -> dict:
    """Link-delay cell scores of meso against the first SUMO seed, and SUMO's own ceiling."""
    k = torch.tensor(k_rows, dtype=torch.long)
    R = routes[k].cpu()
    dep = meso.dep_t[k].cpu()
    ff_edge = (g.length / g.v_free).cpu()
    L = R.shape[1]
    nb = max(1, math.ceil(H / bin_s))
    mask = cell_mask(R, g.n_edges, nb)
    ref = cell_delay(R, dep, exits_tensor(s_ex[0], L), ff_edge, H, bin_s, g.n_edges)
    est = cell_delay(R, dep, meso.hop_exit[k].cpu(), ff_edge, H, bin_s, g.n_edges)
    sc = cell_scores(ref, est, mask)
    row = {"r2_cell_delay": round(float(sc["r2_cell"]), 4),
           "rel_err_total_delay": round(float(sc["rel_err_total"]), 4),
           "total_delay_sumo_h": round(float(sc["total_delay_ref_s"]) / 3600, 2),
           "total_delay_meso_h": round(float(sc["total_delay_est_s"]) / 3600, 2)}
    if len(s_ex) > 1:
        ss = cell_scores(ref, cell_delay(R, dep, exits_tensor(s_ex[1], L), ff_edge, H, bin_s, g.n_edges), mask)
        row["r2_cell_delay_sumo_vs_sumo"] = round(float(ss["r2_cell"]), 4)
        row["rel_err_total_delay_sumo_vs_sumo"] = round(float(ss["rel_err_total"]), 4)
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tph", type=float, nargs="+", default=[500.0, 1000.0, 1500.0, 2000.0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[61000, 61001])
    ap.add_argument("--horizon", type=float, default=1800.0)
    ap.add_argument("--zones", type=int, default=32)
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--lateral", type=float, default=0.8)
    ap.add_argument("--teleport", type=float, default=180.0)
    ap.add_argument("--sumo-seeds", type=int, nargs="+", default=[23423], help="SUMO driver RNG seeds")
    ap.add_argument("--route-sigma", type=float, default=0.0,
                    help="lognormal noise on link costs per demand seed (0 = free-flow routes)")
    ap.add_argument("--route-seed", type=int, default=0, help="route set id for the noise draw")
    ap.add_argument("--bin", type=float, default=300.0, help="time bin of the link-delay cells (s)")
    ap.add_argument("--net-dir", type=Path, default=Path("../sumo-env/networks/v4"))
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/out/quan4/routing2"))
    args = ap.parse_args()

    cfg = replace(SimConfig(), horizon_s=args.horizon, stuck_time_s=args.teleport)
    g = load_graph(DEFAULT_GRAPH, cfg)
    zones = pick_zones(g, args.zones, seed=0)
    net = build_net(DEFAULT_GRAPH, args.net_dir)
    work = args.out_dir / "sumo_check_work" / f"rs{args.route_seed}_sig{args.route_sigma:g}"
    work.mkdir(parents=True, exist_ok=True)
    report = {"args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
              "net": str(net), "levels": []}
    trips = {"args": report["args"], "graph": str(DEFAULT_GRAPH), "levels": []}

    for tph in args.tph:
        d = make_demand(g, zones, args.seeds, tph, cfg.horizon_s, 1.0)
        sim = MesoSim(g, d, zones, cfg)
        if args.route_sigma > 0:
            noise = torch.stack([route_noise(g.n_edges, args.route_sigma, args.route_seed, tph, s)
                                 for s in args.seeds])
            routes = noisy_routes(g, sim.free_tt(), zones, sim.orig, sim.dest_zone, noise)
        else:
            routes = free_flow_routes(g, sim.free_tt(), zones, sim.orig, sim.dest_zone)
        meso = MesoSim(g, d, zones, cfg, record_hops=routes.shape[1])
        meso.run(FixedRoute(routes))
        m_arr = (meso.status == ARRIVED)
        m_tt = meso.arrive_t - meso.dep_t
        ff_edge = g.length / g.v_free
        ff = torch.where(routes >= 0, ff_edge[routes.clamp(min=0)], 0.0).sum(1)
        ref, est, s_all, m_all = [], [], [], []
        dref, dest = [], []
        d_s0, d_s1 = [], []
        teleports = 0
        n_s_arr = 0
        k_rows, s_ex = [], [[] for _ in args.sumo_seeds]
        for b, seed in enumerate(args.seeds):
            lo, hi = b * sim.N, (b + 1) * sim.N
            rou = work / f"tph{int(tph)}_seed{seed}.rou.xml"
            kept = write_routes(rou, g.edge_ids, routes[lo:hi], meso.dep_t[lo:hi])
            t0 = time.perf_counter()
            runs = [run_sumo(net, rou, cfg.horizon_s, args.step, args.lateral, args.teleport, ss,
                             work / f"tph{int(tph)}_seed{seed}_s{ss}.vehroute.xml")
                    for ss in args.sumo_seeds]
            k_rows += [lo + i for i in kept]
            for j, r in enumerate(runs):
                s_ex[j] += [r["exits"].get(i, []) for i in kept]
            wall = (time.perf_counter() - t0) / len(runs)
            res = runs[0]
            trips["levels"].append({
                "tph": tph, "seed": seed, "kept": kept,
                "dep": [round(float(meso.dep_t[lo + i]), 3) for i in kept],
                "ff": [round(float(ff[lo + i]), 3) for i in kept],
                "routes": [[e for e in routes[lo + i].tolist() if e >= 0] for i in kept],
                "sumo_arrive": {str(ss): [r["arrived"].get(i) for i in kept]
                                for ss, r in zip(args.sumo_seeds, runs)},
                "sumo_exits": {str(ss): [[round(x, 2) for x in r["exits"].get(i, [])] for i in kept]
                               for ss, r in zip(args.sumo_seeds, runs)},
            })
            if len(runs) > 1:
                for i in kept:
                    a0, a1 = runs[0]["arrived"].get(i), runs[1]["arrived"].get(i)
                    if a0 is not None and a1 is not None:
                        base = float(meso.dep_t[lo + i]) + float(ff[lo + i])
                        d_s0.append(a0 - base)
                        d_s1.append(a1 - base)
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
        det_ss, _ = r2(d_s0, d_s1)
        row = {
            "tph": tph, "trips": len(s_all),
            "both_arrived": len(ref),
            "r2_trip_tt_both_arrived": round(det, 4), "pearson2_both_arrived": round(pear, 4),
            "r2_delay_both_arrived": round(det_d, 4), "pearson2_delay": round(pear_d, 4),
            "r2_delay_sumo_vs_sumo": round(det_ss, 4),
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
        row.update(cell_row(g, routes, meso, k_rows, s_ex, cfg.horizon_s, args.bin))
        report["levels"].append(row)
        print(f"[check] {row}", flush=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out_dir / f"sumo_check_{stamp}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    tout = args.out_dir / f"sumo_trips_{stamp}.json"
    tout.write_text(json.dumps(trips), encoding="utf-8")
    print(f"[check] wrote {out} and {tout}", flush=True)


if __name__ == "__main__":
    main()
