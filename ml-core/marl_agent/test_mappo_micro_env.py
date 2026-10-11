"""Tests for micro next-hop env — python -m marl_agent.test_mappo_micro_env"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from marl_agent.mappo_micro_env import MicroAlleyEnv


def _chain_graph(root: Path, n: int = 12) -> tuple[Path, Path, list[str]]:
    """Long chain O=0 -> ... -> D=n-1 plus one bypass edge mid-way."""
    alleys: dict[str, dict] = {}
    edges = []
    nodes = [f"n{i}" for i in range(n)]
    for i in range(n - 1):
        aid = f"e{i}"
        alleys[aid] = {
            "u": nodes[i],
            "v": nodes[i + 1],
            "length_m": 50.0,
            "road_class": "alley" if i % 3 == 0 else "residential",
            "layer": "alley" if i % 3 == 0 else "local",
        }
        edges.append({"u": nodes[i], "v": nodes[i + 1], "alley_id": aid})
    alleys["bypass"] = {
        "u": nodes[2],
        "v": nodes[n - 3],
        "length_m": 80.0,
        "road_class": "secondary",
        "layer": "local",
    }
    edges.append({"u": nodes[2], "v": nodes[n - 3], "alley_id": "bypass"})
    gp = root / "g.json"
    dp = root / "d.json"
    dens = [
        {
            "alley_id": aid,
            "density_k": 0.04,
            "speed_mps": 10.0,
            "uncertainty": 0.03 if aid == "bypass" else 0.06,
        }
        for aid in alleys
    ]
    gp.write_text(json.dumps({"alleys": alleys, "edge_list": edges, "nodes": nodes}), encoding="utf-8")
    dp.write_text(json.dumps(dens), encoding="utf-8")
    return gp, dp, nodes


def test_horizon_and_time_in_obs() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td))
        env = MicroAlleyEnv(dp, gp, n_agents=2, max_degree=3, max_steps=30, seed=0)
        obs, g, info = env.reset(
            options={"t": 28800.0, "ods": [(nodes[0], nodes[-1]), (nodes[0], nodes[-1])]}
        )
        assert obs["agent_0"].shape[0] == env.compact_dim
        # peak one-hot morning at t=28800 -> index in obs after t_feat(2)
        # just ensure finite and masks work
        assert info["masks"]["agent_0"].sum() >= 1
        assert "peak" in info
        steps = 0
        for _ in range(env.max_steps):
            acts = env.baseline_dijkstra_actions()
            obs, rew, terms, _, _, sinfo = env.step(acts)
            steps += 1
            if sinfo["all_done"]:
                break
        assert steps > 1  # micro = multi-step
        assert sinfo["fleet_mean"] > 0


def test_more_agents_slower_on_shared_corridor() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td), n=10)
        od = (nodes[0], nodes[-1])
        env4 = MicroAlleyEnv(dp, gp, n_agents=4, max_steps=40, seed=0)
        env8 = MicroAlleyEnv(dp, gp, n_agents=8, max_steps=40, seed=0)
        env4.reset(options={"t": 50400.0, "ods": [od] * 4})
        env8.reset(options={"t": 50400.0, "ods": [od] * 8})
        for _ in range(40):
            env4.step(env4.baseline_dijkstra_actions())
            if all(env4._done):
                break
        for _ in range(40):
            env8.step(env8.baseline_dijkstra_actions())
            if all(env8._done):
                break
        assert float(np.mean(env8._travel)) >= float(np.mean(env4._travel)) - 1e-3


def test_greedy_not_worse_than_all_dijkstra_crowded() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td), n=10)
        od = (nodes[0], nodes[-1])
        env = MicroAlleyEnv(dp, gp, n_agents=8, max_steps=40, seed=1)
        env.reset(seed=1, options={"t": 64800.0, "ods": [od] * 8})
        # dijkstra episode
        for _ in range(40):
            env.step(env.baseline_dijkstra_actions())
            if all(env._done):
                break
        djk = float(np.mean(env._travel))
        env.reset(seed=1, options={"t": 64800.0, "ods": [od] * 8})
        for _ in range(40):
            env.step(env.baseline_greedy_load_actions())
            if all(env._done):
                break
        grd = float(np.mean(env._travel))
        assert grd <= djk + 1.0


def main() -> None:
    test_horizon_and_time_in_obs()
    print("PASS test_horizon_and_time_in_obs")
    test_more_agents_slower_on_shared_corridor()
    print("PASS test_more_agents_slower_on_shared_corridor")
    test_greedy_not_worse_than_all_dijkstra_crowded()
    print("PASS test_greedy_not_worse_than_all_dijkstra_crowded")
    print("MAPPO_MICRO_ENV_TESTS_OK")


if __name__ == "__main__":
    main()
