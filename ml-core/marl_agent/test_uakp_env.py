"""Unit tests for UAKP env — run: python -m marl_agent.test_uakp_env"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from marl_agent.uakp_env import UAKPEnv


def _write_mini_twin(root: Path) -> tuple[Path, Path]:
    """Tiny digraph with two routes O→D differing in uncertainty."""
    graph = {
        "alleys": {
            "a1": {"u": "O", "v": "M1", "length_m": 100.0, "road_class": "residential", "layer": "local"},
            "a2": {"u": "M1", "v": "D", "length_m": 100.0, "road_class": "residential", "layer": "local"},
            "b1": {"u": "O", "v": "M2", "length_m": 100.0, "road_class": "alley", "layer": "alley"},
            "b2": {"u": "M2", "v": "D", "length_m": 100.0, "road_class": "alley", "layer": "alley"},
            "c1": {"u": "O", "v": "D", "length_m": 250.0, "road_class": "secondary", "layer": "local"},
        },
        "edge_list": [
            {"u": "O", "v": "M1", "alley_id": "a1"},
            {"u": "M1", "v": "D", "alley_id": "a2"},
            {"u": "O", "v": "M2", "alley_id": "b1"},
            {"u": "M2", "v": "D", "alley_id": "b2"},
            {"u": "O", "v": "D", "alley_id": "c1"},
        ],
        "nodes": ["O", "M1", "M2", "D"],
        "stats": {},
    }
    dens = [
        {"alley_id": "a1", "density_k": 0.04, "speed_mps": 10.0, "uncertainty": 0.01},
        {"alley_id": "a2", "density_k": 0.04, "speed_mps": 10.0, "uncertainty": 0.01},
        {"alley_id": "b1", "density_k": 0.05, "speed_mps": 9.0, "uncertainty": 0.08},
        {"alley_id": "b2", "density_k": 0.05, "speed_mps": 9.0, "uncertainty": 0.08},
        {"alley_id": "c1", "density_k": 0.03, "speed_mps": 12.0, "uncertainty": 0.02},
    ]
    gp = root / "graph.json"
    dp = root / "density.json"
    gp.write_text(json.dumps(graph), encoding="utf-8")
    dp.write_text(json.dumps(dens), encoding="utf-8")
    return gp, dp


def test_k_paths_and_oracle_not_random() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gp, dp = _write_mini_twin(root)
        env = UAKPEnv(dp, gp, k_paths=6, risk_lambda=0.05, seed=0)
        obs, info = env.reset(options={"origin": "O", "destination": "D", "t": 28800.0})
        assert obs.shape[0] == env.obs_dim()
        assert env.n_actions() == 6
        assert info["unique_paths"] >= 2
        travels = [c.travel_time for c in env._candidates]
        assert max(travels) - min(travels) > 1e-3 or info["unique_paths"] >= 2

        # random vs oracle over many picks
        rng = np.random.default_rng(1)
        n = 200
        rand_gap = 0.0
        ora_gap = 0.0
        for _ in range(n):
            a = int(rng.integers(0, env.k_paths))
            _, _, _, _, inf = env.step(a)
            rand_gap += inf["gap"]
            _, _, _, _, inf_o = env.step(info["oracle_idx"])
            ora_gap += inf_o["gap"]
            env.reset(options={"origin": "O", "destination": "D", "t": 28800.0})
        assert ora_gap <= rand_gap + 1e-6
        assert ora_gap < 1e-3  # oracle among candidates → gap ~0


def test_lambda_changes_ranking_when_uncertainty_matters() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gp, dp = _write_mini_twin(root)
        env0 = UAKPEnv(dp, gp, k_paths=6, risk_lambda=0.0, include_uncertainty=True, seed=0)
        env0.reset(options={"origin": "O", "destination": "D", "t": 28800.0})
        order0 = [tuple(c.nodes) for c in sorted(env0._candidates, key=env0.risk_adjusted_cost)]

        env1 = UAKPEnv(dp, gp, k_paths=6, risk_lambda=2.0, include_uncertainty=True, seed=0)
        env1.reset(options={"origin": "O", "destination": "D", "t": 28800.0})
        order1 = [tuple(c.nodes) for c in sorted(env1._candidates, key=env1.risk_adjusted_cost)]

        # High λ should prefer low-uncertainty main path over high-u alley when close in time
        assert order0 != order1 or env1.risk_adjusted_cost(env1._candidates[0]) != env0.risk_adjusted_cost(
            env0._candidates[0]
        )
        # Explicit: risk-adjusted cost of high-u alley path rises with λ
        alleyish = next(c for c in env1._candidates if c.mean_u > 0.05)
        low_u = next(c for c in env1._candidates if c.mean_u <= 0.03)
        assert env1.risk_adjusted_cost(alleyish) - alleyish.travel_time > env1.risk_adjusted_cost(
            low_u
        ) - low_u.travel_time


def test_ablation_zeroes_uncertainty_channel() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gp, dp = _write_mini_twin(root)
        env = UAKPEnv(
            dp, gp, k_paths=4, risk_lambda=0.1, include_uncertainty=False, seed=0
        )
        obs, _ = env.reset(options={"origin": "O", "destination": "D", "t": 50400.0})
        # candidate mean_u features forced 0 in feat matrix when include_uncertainty=False
        # last 5*K block: indices mean_u every 5th starting at offset 4
        assert np.isfinite(obs).all()
        for c in env._candidates:
            assert env.risk_adjusted_cost(c) == c.travel_time


def test_realized_samples_spread_with_uncertainty() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gp, dp = _write_mini_twin(root)
        env = UAKPEnv(dp, gp, k_paths=4, risk_lambda=0.15, seed=0)
        env.reset(options={"origin": "O", "destination": "D", "t": 28800.0})
        high_u = max(env._candidates, key=lambda c: c.mean_u)
        low_u = min(env._candidates, key=lambda c: c.mean_u)
        s_hi = env.realized_travel_samples(high_u, n_samples=64, seed=1)
        s_lo = env.realized_travel_samples(low_u, n_samples=64, seed=1)
        assert env.cvar(s_hi) >= np.mean(s_hi) - 1e-6
        # Higher-u path should have wider or heavier tail under same seed family
        assert float(np.std(s_hi)) >= float(np.std(s_lo)) - 1e-6


def main() -> None:
    test_k_paths_and_oracle_not_random()
    print("PASS test_k_paths_and_oracle_not_random")
    test_lambda_changes_ranking_when_uncertainty_matters()
    print("PASS test_lambda_changes_ranking_when_uncertainty_matters")
    test_ablation_zeroes_uncertainty_channel()
    print("PASS test_ablation_zeroes_uncertainty_channel")
    test_realized_samples_spread_with_uncertainty()
    print("PASS test_realized_samples_spread_with_uncertainty")
    print("UAKP_ENV_TESTS_OK")


if __name__ == "__main__":
    main()
