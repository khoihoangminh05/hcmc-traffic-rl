"""Paired fair test of a trained micro policy on seeds never used for selection.

    python -m marl_agent.eval_heldout --run <run_dir> [--episodes 30] [--seed-base 60000]

Validation (best.pt selection) uses seeds 50000.. and the in-run final test
starts at the same base, so its first episodes are the selection episodes.
This script reruns the identical paired suite on a disjoint seed range and
writes <run_dir>/heldout_eval.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import yaml

from .mappo_micro_env import MicroAlleyEnv
from .mappo_micro_train import (
    _load_density_catalog,
    _objective,
    _resolve,
    env_kwargs_from_cfg,
    evaluate_fair_suite,
)
from .mappo_nets import SharedActor


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--ckpt", default="best.pt")
    ap.add_argument("--episodes", type=int, default=30)
    ap.add_argument("--seed-base", type=int, default=60_000)
    args = ap.parse_args()

    base = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((args.run / "hyperparameters.snapshot.yaml").read_text(encoding="utf-8"))
    d = cfg["data"]
    env = MicroAlleyEnv(**env_kwargs_from_cfg(
        cfg["env"],
        density=_resolve(d["density"], base),
        graph=_resolve(d["graph"], base),
        density_catalog=_load_density_catalog(d, base),
        seed=0,
    ))
    ck = torch.load(args.run / args.ckpt, map_location="cpu")
    actor = SharedActor(int(ck["obs_dim"]), int(ck["n_actions"]), hidden=int(cfg["model"]["hidden"]))
    actor.load_state_dict(ck["actor"])
    t_eval = [float(x) for x in d.get("t_eval", [28800.0])]
    print(
        f"[heldout] ckpt={args.ckpt} update={ck.get('update')} "
        f"episodes={args.episodes} seed_base={args.seed_base}",
        flush=True,
    )
    fair = evaluate_fair_suite(
        env, actor, [], t_eval, torch.device("cpu"),
        n_episodes=args.episodes, seed_base=args.seed_base,
    )
    for name in ("policy_greedy", "policy_stoch", "greedy_load", "greedy_informed", "dijkstra_bpr", "dijkstra", "random"):
        m = fair.get(name)
        if m:
            print(
                f"[heldout] {name:15s} objective={_objective(m):.1f}s travel={m['fleet_mean']:.1f}s "
                f"city={m.get('city_mean', 0.0):.1f}s arr={m['arrival_rate']:.3f}",
                flush=True,
            )
    for name, st in fair.get("paired_vs_policy_greedy", {}).items():
        if st.get("n"):
            print(
                f"[heldout] policy - {name:15s} delta={st['delta_mean']:+.1f}s ({st['delta_pct']:+.1f}%) "
                f"ci95=[{st['ci95_low']:+.1f}, {st['ci95_high']:+.1f}] win_rate={st['win_rate']:.2f}",
                flush=True,
            )
    out = args.run / "heldout_eval.json"
    out.write_text(json.dumps(fair, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"[heldout] wrote {out}", flush=True)


if __name__ == "__main__":
    main()
