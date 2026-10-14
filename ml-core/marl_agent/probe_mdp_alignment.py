"""MDP alignment probe — run BEFORE paying for a sol1 run.

  python -m marl_agent.probe_mdp_alignment --config marl_agent/configs/quan4_mappo_micro.yaml

Answers, on the exact env/OD split/eval seeds the trainer uses:
  1. graph: nodes, max out-degree, #nodes whose exits are truncated by max_degree
  2. reward alignment: per agent-step correlation of the v2h legacy reward and of
     the current reward with the true cost (-BPR travel time) — the objective
  3. headroom: paired fleet of dijkstra (free-flow) vs dijkstra_bpr (static
     congestion-aware) vs greedy_load, plus the pre-v3 Dijkstra next-hop rule
     (argmin remain only, ignored edge cost) to size that bug
  4. how often the congested-best / load-aware hop differs from the Dijkstra hop
     (= decisions where a router can beat Dijkstra at all)
  5. obs sanity: argmin of the regret feature reproduces greedy_load (should be 1.0)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from .mappo_micro_env import MicroAlleyEnv
from .mappo_micro_train import (
    EVAL_SEED_BASE,
    _load_density_catalog,
    _repo_ml_core,
    _resolve,
    env_kwargs_from_cfg,
    load_config,
    run_episode_baseline,
)
from .od_split import build_connected_od_pool, split_od_pairs


def _legacy_dijkstra_actions(env: MicroAlleyEnv) -> dict[str, int]:
    """v1–v2h next-hop rule: argmin remain_free(nxt), edge cost ignored."""
    acts = {}
    for i, a in enumerate(env.agents):
        if env._done[i]:
            acts[a] = 0
            continue
        curr, dest = env._pos[i], env._ods[i][1]
        cand = env._neighbors(curr)[: env.max_degree]
        if not cand:
            acts[a] = 0
            continue
        acts[a] = int(np.argmin([env._remain_free(n, dest) for n in cand]))
    return acts


def _run(env: MicroAlleyEnv, picker, seed: int, t: float, ods) -> dict[str, float]:
    env.reset(seed=seed, options={"t": t, "ods": ods})
    info: dict[str, Any] = {}
    for _ in range(env.max_steps):
        _, _, _, _, _, info = env.step(picker(env))
        if info["all_done"]:
            break
    return {
        "fleet_mean": float(np.mean(env._travel)),
        "arrival_rate": float(info.get("arrival_rate", 0.0)),
    }


def _corr(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None
    x, y = np.asarray(a), np.asarray(b)
    if x.std() < 1e-12 or y.std() < 1e-12:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config", type=Path, default=Path("marl_agent/configs/quan4_mappo_micro.yaml")
    )
    ap.add_argument("--episodes", type=int, default=24)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    base = _repo_ml_core()
    data_cfg = cfg["data"]
    graph = _resolve(data_cfg["graph"], base, must_exist=True)
    density = _resolve(data_cfg["density"], base, must_exist=True)
    seeds_p = _resolve(data_cfg["seeds"], base, must_exist=True)
    catalog = _load_density_catalog(data_cfg, base)
    seed = int(cfg.get("experiment", {}).get("seed", 42))
    split_cfg = data_cfg.get("split", {})
    pool = build_connected_od_pool(
        graph,
        seeds_p,
        require_path=bool(split_cfg.get("require_path", True)),
        min_path_edges=int(split_cfg.get("min_path_edges", 6)),
        max_pairs=int(split_cfg.get("max_pairs", 500)),
        min_length_m=float(split_cfg.get("min_length_m", 400)),
    )
    split = split_od_pairs(
        pool,
        train_ratio=float(split_cfg.get("train_ratio", 0.7)),
        val_ratio=float(split_cfg.get("val_ratio", 0.15)),
        test_ratio=float(split_cfg.get("test_ratio", 0.15)),
        seed=seed,
    )
    val_ods = [(p.origin, p.destination) for p in split["val"]] or [
        (p.origin, p.destination) for p in split["train"]
    ]
    t_eval = [float(x) for x in data_cfg.get("t_eval", [28800])]
    env_cfg = cfg.get("env", {})
    kw = env_kwargs_from_cfg(
        env_cfg, density=density, graph=graph, density_catalog=catalog, seed=seed
    )
    env = MicroAlleyEnv(**kw)
    env_legacy = MicroAlleyEnv(**{**kw, "reward_mode": "legacy"})
    env.warmup_peak_caches()
    env_legacy.warmup_peak_caches()
    env.set_od_pool(val_ods)

    out_deg = [len(v) for v in env._out.values()]
    report: dict[str, Any] = {
        "graph": {
            "nodes": len(env._nodes),
            "edges": len(env._edge_index),
            "max_out_degree": int(max(out_deg, default=0)),
            "mean_out_degree": float(np.mean(out_deg)) if out_deg else 0.0,
            "max_degree_action": env.max_degree,
            "nodes_truncated": int(env._n_truncated_nodes),
        },
        "reward_mode": env.reward_mode,
        "episodes": int(args.episodes),
    }

    fleets: dict[str, list[dict[str, float]]] = {
        "dijkstra": [],
        "dijkstra_bpr": [],
        "greedy_load": [],
        "dijkstra_legacy_rule": [],
    }
    neg_tt: list[float] = []
    r_new: list[float] = []
    r_legacy: list[float] = []
    r_progress_only: list[float] = []
    n_dec = 0
    n_bpr_diff = 0
    n_legacy_diff = 0
    n_regret_match = 0
    n_grd_diff = 0
    w_prog = float((env_cfg.get("reward_weights") or {}).get("w_progress", 0.4))

    for ep in range(int(args.episodes)):
        t = float(t_eval[ep % len(t_eval)])
        s = int(EVAL_SEED_BASE + ep)
        env.reset(seed=s, options={"t": t})
        ods = [(str(o), str(d)) for o, d in env._ods]
        for mode in ("dijkstra", "dijkstra_bpr", "greedy_load"):
            fleets[mode].append(run_episode_baseline(env, mode, val_ods, t, s, ods=ods))
        fleets["dijkstra_legacy_rule"].append(
            _run(env, _legacy_dijkstra_actions, s, t, ods)
        )

        # Reward alignment + hop disagreement along the free-flow Dijkstra trajectory.
        obs, _, _ = env.reset(seed=s, options={"t": t, "ods": ods})
        env_legacy.reset(seed=s, options={"t": t, "ods": ods})
        for _ in range(env.max_steps):
            acts = env.baseline_dijkstra_actions()
            bpr = env.baseline_dijkstra_bpr_actions()
            grd = env.baseline_greedy_load_actions()
            leg = _legacy_dijkstra_actions(env)
            active = [not d for d in env._done]
            rem_before = [
                env._remain_free(env._pos[i], env._ods[i][1]) for i in range(env.n_agents)
            ]
            for i, a in enumerate(env.agents):
                n_valid = min(len(env._neighbors(env._pos[i])), env.max_degree)
                if not active[i] or n_valid == 0:
                    continue
                n_dec += 1
                n_bpr_diff += int(acts[a] != bpr[a])
                n_legacy_diff += int(acts[a] != leg[a])
                n_grd_diff += int(acts[a] != grd[a])
                reg = env.neighbor_block(obs[a])[:n_valid, env.REGRET_IDX]
                n_regret_match += int(int(np.argmin(reg)) == grd[a])
            travel_before = list(env._travel)
            obs, rew, _, _, _, info = env.step(acts)
            _, rew_l, _, _, _, _ = env_legacy.step(acts)
            for i, a in enumerate(env.agents):
                if not active[i]:
                    continue
                tt = env._travel[i] - travel_before[i]
                neg_tt.append(-tt)
                r_new.append(float(rew[a]))
                r_legacy.append(float(rew_l[a]))
                rem_after = (
                    0.0 if env._true_arrived[i] else env._remain_free(env._pos[i], env._ods[i][1])
                )
                r_progress_only.append(w_prog * (rem_before[i] - rem_after) / 50.0)
            if info["all_done"]:
                break

    def _agg(rows: list[dict[str, float]]) -> dict[str, float]:
        return {
            "fleet_mean": float(np.mean([r["fleet_mean"] for r in rows])),
            "arrival_rate": float(np.mean([r.get("arrival_rate", 0.0) for r in rows])),
        }

    agg = {k: _agg(v) for k, v in fleets.items()}
    djk = agg["dijkstra"]["fleet_mean"]
    report["paired_fleet"] = agg
    report["headroom_dijkstra_bpr_vs_dijkstra_pct"] = float(
        100.0 * (djk - agg["dijkstra_bpr"]["fleet_mean"]) / max(djk, 1.0)
    )
    report["legacy_rule_vs_fixed_dijkstra_pct"] = float(
        100.0 * (agg["dijkstra_legacy_rule"]["fleet_mean"] - djk) / max(djk, 1.0)
    )
    report["reward_alignment_corr_with_neg_tt"] = {
        "current_reward": _corr(r_new, neg_tt),
        "legacy_v2h_reward": _corr(r_legacy, neg_tt),
        "legacy_progress_term_only": _corr(r_progress_only, neg_tt),
        "n_agent_steps": len(neg_tt),
    }
    report["decisions"] = {
        "n": n_dec,
        "bpr_hop_differs_from_dijkstra": float(n_bpr_diff / max(n_dec, 1)),
        "legacy_rule_differs_from_dijkstra": float(n_legacy_diff / max(n_dec, 1)),
        "greedy_load_differs_from_dijkstra": float(n_grd_diff / max(n_dec, 1)),
        "obs_regret_argmin_matches_greedy_load": float(n_regret_match / max(n_dec, 1)),
    }
    report["headroom_greedy_load_vs_dijkstra_pct"] = float(
        100.0 * (djk - agg["greedy_load"]["fleet_mean"]) / max(djk, 1.0)
    )
    txt = json.dumps(report, indent=2)
    print(txt, flush=True)
    if args.out:
        args.out.write_text(txt, encoding="utf-8")
    print("PROBE_MDP_ALIGNMENT_OK", flush=True)


if __name__ == "__main__":
    main()
