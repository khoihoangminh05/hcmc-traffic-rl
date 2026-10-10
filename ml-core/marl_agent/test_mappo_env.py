"""Unit tests for MultiAgentPathEnv — python -m marl_agent.test_mappo_env"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from marl_agent.mappo_env import MultiAgentPathEnv


def _mini_twin(root: Path) -> tuple[Path, Path]:
    """Corridor O→M→D (alley, low cap) and O→D direct (main, high cap)."""
    graph = {
        "alleys": {
            "a1": {"u": "O", "v": "M", "length_m": 80.0, "road_class": "alley", "layer": "alley"},
            "a2": {"u": "M", "v": "D", "length_m": 80.0, "road_class": "alley", "layer": "alley"},
            "m1": {"u": "O", "v": "D", "length_m": 220.0, "road_class": "secondary", "layer": "local"},
        },
        "edge_list": [
            {"u": "O", "v": "M", "alley_id": "a1"},
            {"u": "M", "v": "D", "alley_id": "a2"},
            {"u": "O", "v": "D", "alley_id": "m1"},
        ],
        "nodes": ["O", "M", "D"],
    }
    dens = [
        {"alley_id": "a1", "density_k": 0.04, "speed_mps": 9.0, "uncertainty": 0.06},
        {"alley_id": "a2", "density_k": 0.04, "speed_mps": 9.0, "uncertainty": 0.06},
        {"alley_id": "m1", "density_k": 0.03, "speed_mps": 12.0, "uncertainty": 0.02},
    ]
    gp = root / "g.json"
    dp = root / "d.json"
    gp.write_text(json.dumps(graph), encoding="utf-8")
    dp.write_text(json.dumps(dens), encoding="utf-8")
    return gp, dp


def test_congestion_increases_with_n() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _mini_twin(Path(td))
        env4 = MultiAgentPathEnv(dp, gp, n_agents=4, k_paths=4, seed=0, corridor_prob=1.0)
        env12 = MultiAgentPathEnv(dp, gp, n_agents=12, k_paths=4, seed=0, corridor_prob=1.0)
        ods = [("O", "D")] * 12
        env4.reset(options={"t": 28800.0, "ods": ods[:4]})
        env12.reset(options={"t": 28800.0, "ods": ods})
        # force all onto alley-ish lowest free_time index 0 after sort — use dijkstra baseline
        a4 = env4.baseline_all_dijkstra()
        a12 = env12.baseline_all_dijkstra()
        _, _, _, _, _, i4 = env4.step(a4)
        _, _, _, _, _, i12 = env12.step(a12)
        assert i12["fleet_mean"] > i4["fleet_mean"]
        assert i12["congestion"] >= i4["congestion"] - 1e-6


def test_mixed_beats_all_dijkstra_when_crowded() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _mini_twin(Path(td))
        env = MultiAgentPathEnv(
            dp, gp, n_agents=10, k_paths=4, seed=1, corridor_prob=1.0, bpr_beta=4.0
        )
        ods = [("O", "D")] * 10
        env.reset(options={"t": 28800.0, "ods": ods})
        # all dijkstra
        _, _, _, _, _, info_d = env.step(env.baseline_all_dijkstra())
        env.reset(options={"t": 28800.0, "ods": ods})
        # greedy load-aware
        _, _, _, _, _, info_g = env.step(env.baseline_greedy_load())
        assert info_g["fleet_mean"] <= info_d["fleet_mean"] + 1e-3


def test_action_mask_and_obs_dims() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _mini_twin(Path(td))
        env = MultiAgentPathEnv(dp, gp, n_agents=3, k_paths=4, compact_dim=96, seed=0)
        obs, gstate, info = env.reset(options={"t": 50400.0, "ods": [("O", "D")] * 3})
        assert len(obs) == 3
        assert obs["agent_0"].shape[0] == 96
        assert gstate.ndim == 1 and gstate.size == env.global_state_dim()
        assert "masks" in info
        assert info["masks"]["agent_0"].sum() >= 1.0


def main() -> None:
    test_congestion_increases_with_n()
    print("PASS test_congestion_increases_with_n")
    test_mixed_beats_all_dijkstra_when_crowded()
    print("PASS test_mixed_beats_all_dijkstra_when_crowded")
    test_action_mask_and_obs_dims()
    print("PASS test_action_mask_and_obs_dims")
    print("MAPPO_ENV_TESTS_OK")


if __name__ == "__main__":
    main()
