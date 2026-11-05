"""Where the full network jams at a given alley width: lanes of teleports and edge waiting times.

ff only, the width_sweep scenario, lateral fixed per run. Keeps per-lane teleports from SUMO's
log and edge waiting time from edgeData, so widths can be compared link by link.

    python -u -m routing2.width_diag --out artifacts/out/quan4/routing2_review/width_diag \\
        --widths 1.25 1.5 1.75 2.0 2.5 --lat 0.4 --seeds 70000 70001 70002 70003 --jobs 8
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import xml.etree.ElementTree as ET
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
from .width_sweep import DRAIN_S, HORIZON_S, FreeFlow


def run_one(job: dict) -> dict:
    torch.set_num_threads(1)
    out = Path(job["out"])
    name = f"{job['width']}_{job['lat']}_{job['seed']}"
    wd = out / "w" / name
    wd.mkdir(parents=True, exist_ok=True)
    log, edata, add = wd / "s.log", wd / "edge.xml", wd / "add.xml"
    add.write_text(f'<additional><edgeData id="e" file="{edata.name}" freq="3600" excludeEmpty="true"/></additional>')
    g = load_graph(DEFAULT_GRAPH, replace(SimConfig(), horizon_s=HORIZON_S))
    zones = pick_zones(g, 32, seed=0)

    class Env(SumoRoutingEnv):
        def _start(self, rou):
            c = self.cfg
            self.sumo.start([
                sumo_binary("sumo"), "-n", str(c.net), "-r", str(rou), "-a", str(add),
                "--step-length", str(c.step_s), "--lateral-resolution", str(c.lateral_m),
                "--time-to-teleport", str(c.teleport_s), "--no-step-log", "true",
                "--end", str(c.horizon_s), "--seed", str(c.sumo_seed),
                "--device.rerouting.period", str(c.bg_reroute_period_s), "--log", str(log),
            ])

    env = Env(g, zones, SumoEnvConfig(
        net=Path(job["net"]), lateral_m=job["lat"], horizon_s=HORIZON_S + DRAIN_S,
        sumo_seed=job["seed"], work_dir=wd / "e", live_every_s=10.0, live_source="probe",
        micro=True, teleport_s=300.0, max_detour=0.5, report_drop=0.2, report_noise=0.1,
        fleet_snapshot=True, compliance=0.9, bg_reroute_share=0.3, incident_rate_per_h=2.0,
        school_rate_per_h=1.0, incident_seed=job["seed"],
    ))
    d = make_demand(g, zones, [job["seed"]], job["tph"], HORIZON_S, 0.5, depart_window_s=600.0,
                    hot_share=0.6, n_hot=4, peak_sd=0.25)
    ep = env.run(d, 0, FreeFlow(), record=False)
    env.sumo.close() if getattr(env.sumo, "isLoaded", lambda: False)() else None
    txt = log.read_text(encoding="utf-8", errors="ignore")
    tele = collections.Counter(
        (re.sub(r" with vehicle '[^']+'", "", c), lane)
        for c, lane in re.findall(r"Teleporting vehicle '[^']+'; ([^,]+), lane='([^']+)'", txt))
    wait: dict[str, float] = collections.defaultdict(float)
    if edata.exists():
        for _, el in ET.iterparse(edata):
            if el.tag == "edge":
                wait[el.get("id")] += float(el.get("waitingTime", 0))
    m = ep.metrics
    return {"width": job["width"], "lat": job["lat"], "seed": job["seed"], "J": round(objective(m, 0.5), 1),
            "arrived": round(m["arrived_share_all"], 3), "tele_1k": round(m["teleports_per_1k_trips"], 1),
            "tele": [[c, la, n] for (c, la), n in tele.items()],
            "wait_top": sorted(wait.items(), key=lambda x: -x[1])[:80], "wait_total": round(sum(wait.values()))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--widths", type=float, nargs="*", default=[])
    ap.add_argument("--net-files", nargs="*", default=[], help="label=net.xml, for hand-edited nets")
    ap.add_argument("--lat", type=float, default=0.4)
    ap.add_argument("--seeds", type=int, nargs="+", required=True)
    ap.add_argument("--tph", type=float, default=8000.0)
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    result = args.out / "width_diag.json"
    if result.exists():
        raise SystemExit(f"{result} exists; pick a new --out")
    nets = {}
    for w in args.widths:
        sumo_net.WIDTH_PER_LANE["alley"] = w
        nets[w] = str(sumo_net.build_net(DEFAULT_GRAPH, args.out / f"net_{w}"))
    for item in args.net_files:
        label, path = item.split("=", 1)
        nets[label] = str(Path(path).resolve())
    jobs = [{"width": w, "lat": args.lat, "seed": s, "tph": args.tph, "net": n, "out": str(args.out)}
            for w, n in nets.items() for s in args.seeds]
    rows = []
    with ProcessPoolExecutor(args.jobs) as ex:
        for f in as_completed([ex.submit(run_one, j) for j in jobs]):
            r = f.result()
            rows.append(r)
            print(json.dumps({k: v for k, v in r.items() if k not in ("tele", "wait_top")}), flush=True)
            result.write_text(json.dumps(rows), encoding="utf-8")
    print("WIDTH_DIAG_DONE", flush=True)


if __name__ == "__main__":
    main()
