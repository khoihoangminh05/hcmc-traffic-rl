"""Speed and sanity check of the SUMO routing env (batch).

Same trips in three modes:
- none: every trip on its free-flow route from the route file (no control);
- ff: every trip controlled, choosing the exit on its free-flow shortest path at each node,
  so the routes equal `none` and TTT must agree (checks the control plumbing);
- app: every trip controlled, choosing current link time + free-flow time to go
  (navigation-app behaviour from measurable data).
Reports wall time per episode, decisions per second and TTT. Writes bench_sumo_<stamp>.json.

    python -u -m routing2.bench_sumo --tph 3000 --horizon 1800
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import torch

from .demand import make_demand, pick_zones
from .graph import DEFAULT_GRAPH, load_graph
from .params import SimConfig
from .sumo_env import Request, SumoEnvConfig, SumoRoutingEnv
from .sumo_net import build_net


class ScorePolicy:
    """argmin over candidates of a feature combination."""

    def __init__(self, live: bool):
        self.live = live

    def act(self, req: Request) -> torch.Tensor:
        f = req.feat
        score = (f[..., 1] if self.live else f[..., 0]) + f[..., 3]
        score = torch.where(req.cand >= 0, score, torch.full_like(score, math.inf))
        return score.argmin(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tph", type=float, default=3000.0)
    ap.add_argument("--horizon", type=float, default=1800.0)
    ap.add_argument("--seed", type=int, default=61000)
    ap.add_argument("--zones", type=int, default=32)
    ap.add_argument("--modes", nargs="+", default=["none", "ff", "app"])
    ap.add_argument("--net-dir", type=Path, default=Path("../sumo-env/networks/v4"))
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/out/quan4/routing2"))
    args = ap.parse_args()

    cfg = replace(SimConfig(), horizon_s=args.horizon)
    g = load_graph(DEFAULT_GRAPH, cfg)
    zones = pick_zones(g, args.zones, seed=0)
    net = build_net(DEFAULT_GRAPH, args.net_dir)
    d = make_demand(g, zones, [args.seed], args.tph, args.horizon, 1.0)
    env = SumoRoutingEnv(g, zones, SumoEnvConfig(net=net, horizon_s=args.horizon,
                                                 work_dir=args.out_dir / "sumo_env_work"))
    pols = {"none": None, "ff": ScorePolicy(live=False), "app": ScorePolicy(live=True)}
    rows = []
    for m in args.modes:
        ep = env.run(d, 0, pols[m], record=False)
        row = {"mode": m, "tph": args.tph, "horizon_s": args.horizon, "trips": ep.n_trips,
               "controlled": ep.n_ctrl, "wall_s": round(ep.wall_s, 1),
               "sim_s_per_wall_s": round(args.horizon / ep.wall_s, 1),
               "decisions": ep.n_decisions,
               "decisions_per_s": round(ep.n_decisions / ep.wall_s, 1),
               "mean_tt_s": round(ep.ttt_s / max(1, ep.n_trips), 1),
               "arrived_share": round(ep.arrived / max(1, ep.n_trips), 3), "teleports": ep.teleports}
        rows.append(row)
        print(f"[bench] {row}", flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"bench_sumo_{stamp}.json"
    out.write_text(json.dumps({"args": {k: str(v) for k, v in vars(args).items()}, "rows": rows}, indent=2),
                   encoding="utf-8")
    print(f"[bench] wrote {out}", flush=True)


if __name__ == "__main__":
    main()
