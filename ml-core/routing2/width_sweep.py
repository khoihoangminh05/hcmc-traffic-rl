"""Sensitivity of ff and app to alley width and SUMO lateral resolution.

Each (width, lateral, policy, seed) is one episode at the hard scenario (default 8000 trips/h,
p = 0.5) with the realistic limits every controller has. The demand seed is also the SUMO seed
and the event seed, so driver noise is part of the spread. Teleports are split by cause from
SUMO's log. Never overwrites: fails if <out>/width_sweep.json already exists.

    python -u -m routing2.width_sweep --out artifacts/out/quan4/routing2_review/width_x \\
        --grid 1.75:0.4 --seeds 50010 50011 50012 50013 50014 50015 --jobs 8
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

import torch

from . import sumo_net
from .demand import make_demand, pick_zones
from .graph import DEFAULT_GRAPH, load_graph
from .objectives import objective
from .params import SimConfig
from .sumo_env import SumoEnvConfig, SumoRoutingEnv
from .sumo_net import sumo_binary

HORIZON_S = 1500.0
DRAIN_S = 300.0


class FreeFlow:
    def act(self, r):
        s = r.feat[..., 0] + r.feat[..., 3]
        return torch.where(r.cand >= 0, s, torch.full_like(s, math.inf)).argmin(1)


class App:
    def act(self, r):
        return r.live_cost.argmin(1)


def run_one(job: dict) -> dict:
    torch.set_num_threads(1)
    out = Path(job["out"])
    name = f"{job['width']}_{job['lat']}_{job['pol']}_{job['seed']}"
    g = load_graph(DEFAULT_GRAPH, replace(SimConfig(), horizon_s=HORIZON_S))
    zones = pick_zones(g, 32, seed=0)
    log = out / "logs" / f"{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    class Env(SumoRoutingEnv):
        def _start(self, rou):
            c = self.cfg
            self.sumo.start([
                sumo_binary("sumo"), "-n", str(c.net), "-r", str(rou),
                "--step-length", str(c.step_s), "--lateral-resolution", str(c.lateral_m),
                "--time-to-teleport", str(c.teleport_s), "--no-step-log", "true",
                "--end", str(c.horizon_s), "--seed", str(c.sumo_seed),
                "--device.rerouting.period", str(c.bg_reroute_period_s), "--log", str(log),
            ])

    env = Env(g, zones, SumoEnvConfig(
        net=Path(job["net"]), lateral_m=job["lat"], horizon_s=HORIZON_S + DRAIN_S,
        sumo_seed=job["seed"], work_dir=out / "w" / name, live_every_s=10.0, live_source="probe",
        micro=True, teleport_s=300.0, max_detour=0.5, report_drop=0.2, report_noise=0.1,
        fleet_snapshot=True, compliance=0.9, bg_reroute_share=0.3, incident_rate_per_h=2.0,
        school_rate_per_h=1.0, incident_seed=job["seed"],
    ))
    d = make_demand(g, zones, [job["seed"]], job["tph"], HORIZON_S, 0.5, depart_window_s=600.0,
                    hot_share=0.6, n_hot=4, peak_sd=0.25)
    ep = env.run(d, 0, FreeFlow() if job["pol"] == "ff" else App(), record=False)
    m = ep.metrics
    txt = log.read_text(encoding="utf-8", errors="ignore")
    causes = collections.Counter(
        re.sub(r" with vehicle '[^']+'", "", x)
        for x in re.findall(r"Teleporting vehicle '[^']+'; ([^,]+),", txt)
    )
    log.unlink(missing_ok=True)
    return {
        **{k: job[k] for k in ("width", "lat", "pol", "seed", "tph")},
        "J": round(objective(m, 0.5), 1), "T_all": round(m["T_all_s"], 1),
        "T_cust": round(m["T_cust_s"], 1), "arrived": round(m["arrived_share_all"], 3),
        "tele_1k": round(m["teleports_per_1k_trips"], 1),
        "cong": round(m["congestion_index"], 2), "causes": dict(causes), "wall": round(ep.wall_s),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--grid", nargs="+", required=True, help="width:lateral in metres, e.g. 1.25:0.4")
    ap.add_argument("--seeds", type=int, nargs="+", required=True)
    ap.add_argument("--tph", type=float, default=8000.0)
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    result = args.out / "width_sweep.json"
    if result.exists():
        raise SystemExit(f"{result} exists; pick a new --out")
    grid = [tuple(float(x) for x in c.split(":")) for c in args.grid]
    nets = {}
    for w in sorted({w for w, _ in grid}):
        sumo_net.WIDTH_PER_LANE["alley"] = w
        nets[w] = str(sumo_net.build_net(DEFAULT_GRAPH, args.out / f"net_{w}"))
    jobs = [{"width": w, "lat": la, "pol": p, "seed": s, "tph": args.tph, "net": nets[w], "out": str(args.out)}
            for w, la in grid for p in ("ff", "app") for s in args.seeds]
    rows = []
    with ProcessPoolExecutor(args.jobs) as ex:
        for f in as_completed([ex.submit(run_one, j) for j in jobs]):
            r = f.result()
            rows.append(r)
            print(json.dumps(r), flush=True)
            result.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print("WIDTH_SWEEP_DONE", flush=True)


if __name__ == "__main__":
    main()
