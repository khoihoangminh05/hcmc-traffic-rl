"""Part 1 gate, criterion A3: reactive navigation apps on the same trips as routing2.gate_msa (batch).

Every trip is a user of the app (p = 1). Link times come from SUMO's current edge estimates,
as probe speeds would, smoothed by an EMA and refreshed every `--live-every` seconds.
- ff: free-flow next hop (sanity: must match the free-flow replay in gate_msa);
- app_cont: at every node take the exit minimising live link time + live time to destination;
- app_sticky: keep the planned route unless the best one saves at least `--theta` of its
  remaining time. Closer to a real app, which does not reroute at every junction.
TTT counts trips until arrival or the end of the simulation, from the planned departure, as in
gate_msa. Writes gate_app_<tag>_<stamp>_<pid>.json; reports mean, sd and the mean of the worst
25% per policy and level. No training, no GPU.

    python -u -m routing2.gate_app --tph 6000 --seeds 61000 --horizon 3600 --drain 1800 --jobs 24
"""

from __future__ import annotations

import argparse
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import torch

from .demand import make_demand, pick_zones
from .graph import DEFAULT_GRAPH, load_graph
from .params import SimConfig
from .sumo_env import Request, SumoEnvConfig, SumoRoutingEnv
from .sumo_net import build_net


class FreeFlow:
    def act(self, req: Request) -> torch.Tensor:
        s = req.feat[..., 0] + req.feat[..., 3]
        return torch.where(req.cand >= 0, s, torch.full_like(s, math.inf)).argmin(1)


class AppContinuous:
    def act(self, req: Request) -> torch.Tensor:
        return req.live_cost.argmin(1)


class AppSticky:
    """Follows its planned route unless the live best saves at least theta of the remaining time."""

    def __init__(self, env: SumoRoutingEnv, theta: float):
        self.env, self.theta = env, theta
        self.plan: dict[str, list[int]] = {}

    def act(self, req: Request) -> torch.Tensor:
        best = req.live_cost.argmin(1)
        out = best.clone()
        tt = self.env.live_tt
        for i, vid in enumerate(req.vid):
            z = int(req.dest_zone[i])
            cand = [int(c) for c in req.cand[i].tolist() if c >= 0]
            plan = self.plan.get(vid)
            b = int(best[i])
            if plan and plan[0] in cand:
                keep = float(tt[plan].sum())
                if float(req.live_cost[i, b]) >= (1.0 - self.theta) * keep:
                    out[i] = cand.index(plan[0])
                    self.plan[vid] = plan[1:]
                    continue
            self.plan[vid] = self.env.live_path(z, cand[b])
        return out


def run_one(job: dict) -> dict:
    torch.set_num_threads(1)
    cfg = replace(SimConfig(), horizon_s=job["horizon"])
    g = load_graph(DEFAULT_GRAPH, cfg)
    zones = pick_zones(g, job["zones"], seed=0)
    env = SumoRoutingEnv(g, zones, SumoEnvConfig(
        net=Path(job["net"]), horizon_s=job["horizon"] + job["drain"], sumo_seed=job["sumo_seed"],
        work_dir=Path(job["work"]) / f"w{os.getpid()}", live_every_s=job["live_every"],
        live_source=job["live_source"], live_mask=job["live_mask"],
        incident_rate_per_h=job["incident_rate"], incident_seed=job["seed"]))
    d = make_demand(g, zones, [job["seed"]], job["tph"], job["horizon"], 1.0)
    pol = {"ff": lambda: FreeFlow(), "app_cont": lambda: AppContinuous(),
           "app_sticky": lambda: AppSticky(env, job["theta"])}[job["policy"].split("|")[0]]()
    ep = env.run(d, 0, pol, record=False)
    return {k: job[k] for k in ("policy", "tph", "seed", "sumo_seed")} | {
        "ttt_h": round(ep.ttt_s / 3600, 3), "trips": ep.n_trips, "arrived": ep.arrived,
        "teleports": ep.teleports, "decisions": ep.n_decisions, "km": round(ep.km, 1), "wall_s": round(ep.wall_s, 1)}


def tail_mean(x: list[float], frac: float = 0.25) -> float:
    v = sorted(x, reverse=True)
    return sum(v[: max(1, round(len(v) * frac))]) / max(1, round(len(v) * frac))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tph", type=float, nargs="+", default=[6000.0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[61000])
    ap.add_argument("--sumo-seeds", type=int, nargs="+", default=[71, 72, 73, 74, 75, 76])
    ap.add_argument("--policies", nargs="+", default=["ff", "app_cont", "app_sticky"])
    ap.add_argument("--horizon", type=float, default=3600.0)
    ap.add_argument("--drain", type=float, default=1800.0)
    ap.add_argument("--live-every", type=float, default=30.0)
    ap.add_argument("--theta", type=float, default=0.1)
    ap.add_argument("--live-source", default="probe", choices=["edge", "probe"])
    ap.add_argument("--live-mask", nargs="+", default=["all"], choices=["all", "roads"],
                    help="each mask is its own set of runs for the app policies")
    ap.add_argument("--incident-rate", type=float, default=0.0, help="hidden alley incidents per hour")
    ap.add_argument("--zones", type=int, default=32)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--tag", default="run")
    ap.add_argument("--net-dir", type=Path, default=Path("../sumo-env/networks/v4"))
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/out/quan4/routing2"))
    args = ap.parse_args()

    net = str(build_net(DEFAULT_GRAPH, args.net_dir).resolve())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"gate_app_{args.tag}_{stamp}_{os.getpid()}"
    work = (args.out_dir / name).resolve()
    work.mkdir(parents=True, exist_ok=False)
    masks = {p: (["all"] if p == "ff" else args.live_mask) for p in args.policies}
    jobs = [{"policy": p if mk == "all" else f"{p}|{mk}", "tph": t, "seed": s, "sumo_seed": ss, "horizon": args.horizon,
             "drain": args.drain, "zones": args.zones, "net": net, "work": str(work), "theta": args.theta,
             "live_every": args.live_every, "live_source": args.live_source, "live_mask": mk,
             "incident_rate": args.incident_rate}
            for t in args.tph for s in args.seeds for p in args.policies for mk in masks[p] for ss in args.sumo_seeds]
    names = sorted({j["policy"] for j in jobs})
    print(f"[app] {len(jobs)} runs -> {work} (jobs={args.jobs})", flush=True)
    rows = []
    with ProcessPoolExecutor(args.jobs) as ex:
        for f in as_completed([ex.submit(run_one, j) for j in jobs]):
            r = f.result()
            rows.append(r)
            print(f"[app] {json.dumps(r)}", flush=True)
    summ = []
    for t in args.tph:
        for p in names:
            v = [r["ttt_h"] for r in rows if r["tph"] == t and r["policy"] == p]
            m = sum(v) / len(v)
            sd = (sum((x - m) ** 2 for x in v) / max(1, len(v) - 1)) ** 0.5
            summ.append({"tph": t, "policy": p, "n": len(v), "ttt_h_mean": round(m, 2), "sd": round(sd, 2),
                         "worst25_mean": round(tail_mean(v), 2), "max": max(v), "min": min(v),
                         "km_mean": round(sum(r["km"] for r in rows if r["tph"] == t and r["policy"] == p) / len(v), 1),
                         "teleports_mean": round(sum(r["teleports"] for r in rows if r["tph"] == t and r["policy"] == p) / len(v), 1)})
            print(f"[app] summary {json.dumps(summ[-1])}", flush=True)
    (work / "gate_app.json").write_text(json.dumps({"args": {k: str(v) for k, v in vars(args).items()},
                                                    "runs": rows, "summary": summ}, indent=2), encoding="utf-8")
    print(f"[app] wrote {work / 'gate_app.json'}", flush=True)


if __name__ == "__main__":
    main()
