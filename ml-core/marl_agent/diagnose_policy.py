"""Why do cars fail under a trained micro policy?

    python -m marl_agent.diagnose_policy --run <run_dir> [--episodes 4]

Runs the deterministic policy on eval seeds and prints a short report:
arrival, agreement with greedy_load, the probability the policy puts on
greedy_load's hop, and for failing cars whether they loop and where.
"""

from __future__ import annotations

import argparse
import collections
from pathlib import Path

import numpy as np
import torch
import yaml

from .mappo_micro_env import MicroAlleyEnv
from .mappo_micro_train import EVAL_SEED_BASE, _load_density_catalog, _resolve, env_kwargs_from_cfg, masked_categorical
from .mappo_nets import SharedActor


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--ckpt", default="best.pt")
    ap.add_argument("--episodes", type=int, default=4)
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
    actor.eval()
    print(f"[diag] ckpt={args.ckpt} update={ck.get('update')} episodes={args.episodes}", flush=True)

    t_eval = [float(x) for x in d.get("t_eval", [28800.0])]
    agree_ok, agree_fail = [], []
    p_greedy_ok, p_greedy_fail = [], []
    away_fail = []
    loops, distinct_last = [], []
    light_fail = []
    arrived_all = []
    for ep in range(args.episodes):
        obs, _, info = env.reset(seed=EVAL_SEED_BASE + ep, options={"t": t_eval[ep % len(t_eval)]})
        n = env.n_agents
        agree = [[] for _ in range(n)]
        pgr = [[] for _ in range(n)]
        away = [[] for _ in range(n)]
        lit = [[] for _ in range(n)]
        for _ in range(env.max_steps):
            greedy = env.baseline_greedy_load_actions()
            o = torch.tensor(np.stack([obs[a] for a in env.agents]), dtype=torch.float32)
            m = torch.tensor(np.stack([info["masks"][a] for a in env.agents]), dtype=torch.float32)
            with torch.no_grad():
                dist = masked_categorical(actor(o), m)
                probs = dist.probs.numpy()
                act = torch.argmax(dist.logits, dim=-1).numpy()
            for i, a in enumerate(env.agents):
                if not info["agent_acting"][i]:
                    continue
                curr, dest = env._pos[i], env._ods[i][1]
                neigh = env._neighbors(curr)[: env.max_degree]
                g = int(greedy[a])
                agree[i].append(int(act[i]) == g)
                pgr[i].append(float(probs[i, g]))
                if int(act[i]) < len(neigh):
                    nxt = neigh[int(act[i])]
                    away[i].append(env._remain_free(nxt, dest) > env._remain_free(curr, dest))
                    lit[i].append(nxt in env._signals)
            acts = {a: int(act[i]) for i, a in enumerate(env.agents)}
            obs, _, _, _, _, info = env.step(acts)
            if info["all_done"]:
                break
        arr = list(env._true_arrived)
        arrived_all.extend(arr)
        for i in range(n):
            if arr[i]:
                agree_ok.extend(agree[i])
                p_greedy_ok.extend(pgr[i])
            else:
                agree_fail.extend(agree[i])
                p_greedy_fail.extend(pgr[i])
                away_fail.extend(away[i])
                light_fail.extend(lit[i])
                hist = env._path_hist[i]
                tail = hist[-30:]
                distinct_last.append(len(set(tail)))
                cnt = collections.Counter(hist)
                loops.append(max(cnt.values()) if cnt else 0)
        print(
            f"[diag] ep {ep + 1} arrival={np.mean(arr):.2f} "
            f"failed={n - int(sum(arr))} sim_end={env._sim:.0f}s",
            flush=True,
        )

    def mean(x: list) -> float:
        return float(np.mean(x)) if x else float("nan")

    print(f"[diag] arrival overall={mean(arrived_all):.2f}")
    print(
        f"[diag] arriving cars: agree_with_greedy={mean(agree_ok):.3f} "
        f"p(greedy hop)={mean(p_greedy_ok):.3f} decisions={len(agree_ok)}"
    )
    print(
        f"[diag] failing cars:  agree_with_greedy={mean(agree_fail):.3f} "
        f"p(greedy hop)={mean(p_greedy_fail):.3f} decisions={len(agree_fail)}"
    )
    print(
        f"[diag] failing cars:  hops_moving_away={mean(away_fail):.3f} "
        f"hops_into_a_light={mean(light_fail):.3f}"
    )
    if distinct_last:
        print(
            f"[diag] failing cars:  distinct nodes in last 30 = median {np.median(distinct_last):.0f} "
            f"(<=3 means a tight loop: {np.mean(np.asarray(distinct_last) <= 3):.2f}), "
            f"max visits of one node = median {np.median(loops):.0f}"
        )


if __name__ == "__main__":
    main()
