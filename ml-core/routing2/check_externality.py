"""Check of the delay charges (sumo_env._attribute) against reruns without the charged vehicles (batch).

For each demand seed: play the demand in full, then replay it without the most charged trips, the
least charged trips and a random group of the same size. The measured externality of a group is how
much longer all other trips took in the full run. If the charges carry information, removing the
most charged trips must help the others more than removing the least charged. The ratio of measured
to charged shows the level. Groups, because one vehicle's effect is lost in SUMO's chaos. No training.

    python -u -m routing2.check_externality --tph 6000 --horizon 600 --seeds 61000 61001 61002 --frac 0.1
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from .demand import Demand, make_demand, pick_zones
from .graph import DEFAULT_GRAPH, load_graph
from .params import SimConfig
from .sumo_env import SumoEnvConfig, SumoRoutingEnv
from .sumo_net import build_net


class FreeFlow:
    def act(self, req):
        s = req.feat[..., 0] + req.feat[..., 3]
        return s.masked_fill(req.cand < 0, math.inf).argmin(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tph", type=float, default=6000.0)
    ap.add_argument("--horizon", type=float, default=600.0)
    ap.add_argument("--drain", type=float, default=900.0)
    ap.add_argument("--frac", type=float, default=0.1)
    ap.add_argument("--seeds", type=int, nargs="+", default=[61000, 61001, 61002])
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/out/quan4/routing2"))
    args = ap.parse_args()
    H = args.horizon
    g = load_graph(DEFAULT_GRAPH, replace(SimConfig(), horizon_s=H))
    zones = pick_zones(g, 32, seed=0)
    net = build_net(DEFAULT_GRAPH, Path("../sumo-env/networks/v4"))
    env = SumoRoutingEnv(g, zones, SumoEnvConfig(net=net, horizon_s=H + args.drain, micro=True, attribute_every_s=5.0,
                                                 live_every_s=10.0, live_source="probe",
                                                 work_dir=args.out_dir / "check_externality_work"))
    rows = []
    for seed in args.seeds:
        d = make_demand(g, zones, [seed], args.tph, H, 1.0)
        full = env.run(d, 0, FreeFlow(), record=True)
        t = full.trip_tt
        print(f"[ext] seed {seed}: trips={len(t)} delay seen={full.delay_seen_s:.0f}s "
              f"charged={sum(full.caused_s.values()):.0f}s unfinished={full.metrics['unfinished_all']}", flush=True)
        N = d.dep_t.shape[1]
        size = max(1, int(args.frac * N))
        charge = np.array([full.caused_s.get(f"c{i}", 0.0) for i in range(N)])
        rank = np.argsort(charge)
        groups = {"top": rank[-size:], "bottom": rank[:size],
                  "random": np.random.default_rng(seed).choice(N, size=size, replace=False)}
        for name, drop in groups.items():
            keep = np.setdiff1d(np.arange(N), drop)
            ki = torch.from_numpy(keep)
            sub = Demand(d.dep_t[:, ki], d.orig[:, ki], d.dest_zone[:, ki], d.ctrl[:, ki], d.seeds)
            ep = env.run(sub, 0, FreeFlow(), record=False)
            # the replay numbers its trips 0..len(keep)-1, in the order of keep
            measured = sum(t[int(i)] - ep.trip_tt[k] for k, i in enumerate(keep) if int(i) in t and k in ep.trip_tt)
            rows.append({"seed": seed, "group": name, "charged_s": round(float(charge[drop].sum()), 1),
                         "measured_s": round(measured, 1)})
            print(f"[ext] {json.dumps(rows[-1])}", flush=True)
    by = {n: [r for r in rows if r["group"] == n] for n in ("top", "bottom", "random")}
    summary = {n: {"charged_s": float(np.mean([r["charged_s"] for r in v])),
                   "measured_s": float(np.mean([r["measured_s"] for r in v]))} for n, v in by.items()}
    wins = sum(a["measured_s"] > b["measured_s"] for a, b in zip(by["top"], by["bottom"]))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (args.out_dir / f"check_externality_{stamp}.json").write_text(
        json.dumps({"args": {k: str(v) for k, v in vars(args).items()}, "rows": rows, "summary": summary}, indent=2),
        encoding="utf-8")
    print(f"[ext] summary={json.dumps(summary)} top_beats_bottom={wins}/{len(by['top'])}", flush=True)


if __name__ == "__main__":
    main()
