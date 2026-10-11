"""Careful audit of micro MAPPO failure modes — evidence, not slogans.

Run: python -m marl_agent._audit_v1_failure
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import numpy as np

from marl_agent.mappo_micro_env import MicroAlleyEnv
from marl_agent.od_split import build_connected_od_pool, split_od_pairs


def _base() -> Path:
    return Path(__file__).resolve().parents[1] / "artifacts/out/quan4/wcc"


def _make_env(compact_dim: int = 160) -> MicroAlleyEnv:
    base = _base()
    catalog = {
        "morning": base / "alley_density_peak_morning_paper_a_merged_wcc.json",
        "afternoon": base / "alley_density_peak_afternoon_paper_a_merged_wcc.json",
        "evening": base / "alley_density_peak_evening_paper_a_merged_wcc.json",
    }
    return MicroAlleyEnv(
        density_path=base / "alley_density_l4_cam_wcc.json",
        graph_path=base / "alley_graph_wcc.json",
        n_agents=16,
        max_degree=8,
        max_steps=120,
        seed=42,
        compact_dim=compact_dim,
        density_catalog={k: v for k, v in catalog.items() if v.exists()},
        # v1-like reward weights for fair baseline physics
        reward_weights={
            "w_T": 1.0,
            "w_C": 0.08,
            "w_R": 0.05,
            "w_step": 0.01,
            "arrive_bonus": 0.5,
            "w_progress": 0.0,
            "w_revisit": 0.0,
            "w_team": 0.0,
        },
    )


def _train_like_ods(env: MicroAlleyEnv) -> list[tuple[str, str]]:
    ml = Path(__file__).resolve().parents[1]
    graph = _base() / "alley_graph_wcc.json"
    seeds = ml.parent / "ingestion-worker/config/od_pairs.quan4.seeds_l3.json"
    pool = build_connected_od_pool(
        graph, seeds, require_path=True, min_path_edges=6, max_pairs=500, min_length_m=400.0
    )
    split = split_od_pairs(pool, 0.7, 0.15, 0.15, seed=42)
    return [(p.origin, p.destination) for p in split["train"]]


def run_mode(env: MicroAlleyEnv, mode: str, n: int = 30) -> dict:
    means, congs, arrives, steps_l, timeouts, revisits = [], [], [], [], [], []
    t_list = [28800.0, 50400.0, 64800.0]
    for ep in range(n):
        env.reset(seed=70_000 + ep, options={"t": t_list[ep % 3]})
        last = {"congestion": 0.0, "n_arrived": 0}
        for s in range(env.max_steps):
            if mode == "dijkstra":
                acts = env.baseline_dijkstra_actions()
            elif mode == "random":
                acts = env.baseline_random_actions()
            elif mode == "greedy_load":
                acts = env.baseline_greedy_load_actions()
            elif mode == "action0":
                acts = {a: 0 for a in env.agents}
            else:
                raise ValueError(mode)
            _, _, _, _, _, last = env.step(acts)
            if last["all_done"]:
                break
        travels = np.asarray(env._travel, dtype=np.float64)
        means.append(float(np.mean(travels)))
        congs.append(float(last.get("congestion", 0.0)))
        arrives.append(int(last.get("n_arrived", 0)))
        steps_l.append(s + 1)
        # timeout proxy: still had remaining free when forced? we mark done on truncate
        timeouts.append(int(sum(1 for hist in env._path_hist if len(hist) >= env.max_steps)))
        rev = []
        for hist in env._path_hist:
            if len(hist) <= 1:
                rev.append(0.0)
            else:
                rev.append(1.0 - len(set(hist)) / len(hist))
        revisits.append(float(np.mean(rev)))
    return {
        "fleet_mean": float(np.mean(means)),
        "fleet_std": float(np.std(means)),
        "fleet_p10": float(np.percentile(means, 10)),
        "fleet_p90": float(np.percentile(means, 90)),
        "cong": float(np.mean(congs)),
        "arrive_mean": float(np.mean(arrives)),
        "ep_len": float(np.mean(steps_l)),
        "revisit_frac": float(np.mean(revisits)),
        "timeoutish": float(np.mean(timeouts)),
    }


def obs_feature_sanity(env: MicroAlleyEnv) -> dict:
    """Check whether neighbor features actually differ / carry live signal."""
    od = env._od_pool[:16]
    while len(od) < 16:
        od.append(od[0])
    env.reset(seed=1, options={"t": 28800.0, "ods": od})
    # all agents same OD start → crowded origin
    obs0 = {a: env._local_obs(i).copy() for i, a in enumerate(env.agents)}
    # neighbor block starts after fixed prefix; with compact_dim=160 and 11*8 neigh
    # compare variance across neighbor slots for agent_0
    o = obs0["agent_0"]
    # crude: std of whole obs and of last 88 dims (neighbor block if 11*8)
    neigh = o[-88:] if o.size >= 88 else o
    # after one greedy step, live_edge should change obs
    env.step(env.baseline_greedy_load_actions())
    o1 = env._local_obs(0)
    return {
        "obs_dim": int(o.size),
        "obs_std": float(np.std(o)),
        "neigh_std": float(np.std(neigh)),
        "l1_change_after_step": float(np.mean(np.abs(o1 - o))),
        "node_occ_at_start": float(env._node_occ.get(env._pos[0], 0.0))
        if hasattr(env, "_node_occ")
        else None,
    }


def individual_vs_team_reward_dispersion(env: MicroAlleyEnv) -> dict:
    """How different are per-agent rewards within a step under greedy?"""
    env.reset(seed=2, options={"t": 28800.0})
    dispersions = []
    for _ in range(40):
        acts = env.baseline_greedy_load_actions()
        _, rew, _, _, _, info = env.step(acts)
        arr = np.array([rew[a] for a in env.agents], dtype=np.float64)
        active = arr[np.abs(arr) > 1e-12]
        if active.size > 1:
            dispersions.append(float(np.std(active)))
        if info["all_done"]:
            break
    return {
        "reward_std_mean": float(np.mean(dispersions)) if dispersions else 0.0,
        "reward_std_max": float(np.max(dispersions)) if dispersions else 0.0,
        "n_steps_measured": len(dispersions),
    }


def main() -> None:
    env = _make_env()
    ods = _train_like_ods(env)
    env.set_od_pool(ods)
    env.warmup_peak_caches()
    print(f"train_like_ods={len(ods)} nodes={len(env._nodes)} edges={len(env._edge_index)}")

    out: dict = {"baselines": {}, "notes": []}
    for mode in ("dijkstra", "random", "greedy_load", "action0"):
        out["baselines"][mode] = run_mode(env, mode, n=24)
        print(mode, json.dumps(out["baselines"][mode], indent=None))

    out["obs_sanity"] = obs_feature_sanity(env)
    print("obs_sanity", out["obs_sanity"])
    out["reward_dispersion"] = individual_vs_team_reward_dispersion(env)
    print("reward_dispersion", out["reward_dispersion"])

    b = out["baselines"]
    out["notes"].append(
        "If random << dijkstra on fleet_mean, selfish SP congestion is real on this twin."
    )
    out["notes"].append(
        "If action0 cong/fleet explode, collapsed policy to argmax0 would match v1 failure signature."
    )
    out["notes"].append(
        "MAPPO paper (Yu et al.) uses SHARED team reward by default; team-mean is not "
        "automatically a bug — individual GAE is a hypothesis, not proven root cause."
    )
    out["ordering"] = {
        "greedy_best": b["greedy_load"]["fleet_mean"]
        <= b["random"]["fleet_mean"]
        <= b["dijkstra"]["fleet_mean"] + 1e9,
        "action0_worse_than_random": b["action0"]["fleet_mean"] > b["random"]["fleet_mean"],
        "user_v1_signature_action0_like": (
            b["action0"]["cong"] > 10 and b["action0"]["fleet_mean"] > b["dijkstra"]["fleet_mean"] * 0.8
        ),
    }
    print("ordering", out["ordering"])
    print(json.dumps({"notes": out["notes"], "ordering": out["ordering"]}, indent=2))
    print("AUDIT_V1_FAILURE_OK")


if __name__ == "__main__":
    main()
