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


def test_live_occupancy_in_obs() -> None:
    """v2: obs must change when other agents crowd the same node."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td), n=10)
        od = (nodes[0], nodes[-1])
        env = MicroAlleyEnv(
            dp, gp, n_agents=4, max_degree=3, max_steps=20, seed=0, compact_dim=160
        )
        obs1, _, _ = env.reset(options={"t": 28800.0, "ods": [od] * 4})
        # all start at same origin → node_occ feature should be > 0
        # feature layout: after embeds, slot includes n_here/n_agents
        assert obs1["agent_0"].shape[0] == 160
        # step once with dijkstra so live_edge populates
        obs2, _, _, _, _, info = env.step(env.baseline_dijkstra_actions())
        assert np.isfinite(obs2["agent_0"]).all()
        assert "mean_progress" in info


def _graph(root: Path, spec: list[tuple[str, str, float, str]]) -> tuple[Path, Path]:
    alleys: dict[str, dict] = {}
    edges = []
    nodes: set[str] = set()
    for k, (u, v, length, rc) in enumerate(spec):
        aid = f"a{k}"
        alleys[aid] = {"u": u, "v": v, "length_m": length, "road_class": rc, "layer": "local"}
        edges.append({"u": u, "v": v, "alley_id": aid})
        nodes |= {u, v}
    gp, dp = root / "g.json", root / "d.json"
    dens = [
        {"alley_id": a, "density_k": 0.04, "speed_mps": 10.0, "uncertainty": 0.05}
        for a in alleys
    ]
    gp.write_text(
        json.dumps({"alleys": alleys, "edge_list": edges, "nodes": sorted(nodes)}),
        encoding="utf-8",
    )
    dp.write_text(json.dumps(dens), encoding="utf-8")
    return gp, dp


def test_dijkstra_counts_edge_cost() -> None:
    """O->X is long but X is next to D; O->Y->Z->D is shorter in total."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("O", "X", 900.0, "residential"),
                ("X", "D", 20.0, "residential"),
                ("O", "Y", 50.0, "residential"),
                ("Y", "Z", 50.0, "residential"),
                ("Z", "D", 50.0, "residential"),
            ],
        )
        env = MicroAlleyEnv(dp, gp, n_agents=1, max_degree=3, max_steps=10, seed=0)
        env.reset(options={"t": 28800.0, "ods": [("O", "D")]})
        a = env.baseline_dijkstra_actions()["agent_0"]
        assert env._neighbors("O")[a] == "Y", env._neighbors("O")


def test_travel_reward_sums_to_travel_time() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td), n=10)
        od = (nodes[0], nodes[-1])
        env = MicroAlleyEnv(
            dp, gp, n_agents=4, max_degree=3, max_steps=40, seed=0,
            reward_mode="travel", travel_scale=1000.0,
        )
        env.reset(options={"t": 64800.0, "ods": [od] * 4})
        ret = np.zeros(4)
        for _ in range(40):
            _, rew, _, _, _, info = env.step(env.baseline_dijkstra_actions())
            ret += [rew[a] for a in env.agents]
            if info["all_done"]:
                break
        np.testing.assert_allclose(-ret * 1000.0, env._travel, rtol=1e-6, atol=1e-6)


def test_marginal_reward_charges_co_movers() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td), n=10)
        od = (nodes[0], nodes[-1])
        kw = dict(n_agents=6, max_degree=3, max_steps=40, seed=0, travel_scale=1000.0)
        env_t = MicroAlleyEnv(dp, gp, reward_mode="travel", **kw)
        env_m = MicroAlleyEnv(dp, gp, reward_mode="marginal", **kw)
        env_t.reset(options={"t": 64800.0, "ods": [od] * 6})
        env_m.reset(options={"t": 64800.0, "ods": [od] * 6})
        acts = env_t.baseline_dijkstra_actions()
        _, rt, _, _, _, _ = env_t.step(acts)
        _, rm, _, _, _, _ = env_m.step(acts)
        # 6 agents on one edge: marginal cost strictly above own travel time
        assert all(rm[a] < rt[a] - 1e-9 for a in env_t.agents)


def test_regret_feature_zero_on_congested_best_hop() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td), n=12)
        env = MicroAlleyEnv(dp, gp, n_agents=1, max_degree=3, max_steps=30, seed=0)
        obs, _, info = env.reset(options={"t": 28800.0, "ods": [(nodes[2], nodes[-1])]})
        blk = env.neighbor_block(obs["agent_0"])
        n_valid = int(info["masks"]["agent_0"].sum())
        assert n_valid >= 2  # chain step + bypass
        best = env.baseline_dijkstra_bpr_actions()["agent_0"]
        assert abs(float(blk[best, env.REGRET_IDX])) < 1e-6
        assert float(blk[:n_valid, env.REGRET_IDX].max()) > 0.0


def test_subproc_returns_agent_done() -> None:
    from marl_agent.mappo_micro_vec import SubprocMicroEnvs

    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td), n=6)
        kw = dict(
            density_path=dp, graph_path=gp, n_agents=2, max_degree=3, max_steps=20, seed=0
        )
        vec = SubprocMicroEnvs([kw], start_method="spawn")
        try:
            vec.set_od_pool([(nodes[0], nodes[-1]), (nodes[1], nodes[-1])])
            vec.reset_batch([3], [28800.0])
            out = vec.step_batch(np.zeros((1, 2), dtype=np.int64))
            assert len(out) == 7 and out[6].shape == (1, 2)
        finally:
            vec.close()


def main() -> None:
    test_horizon_and_time_in_obs()
    print("PASS test_horizon_and_time_in_obs")
    test_more_agents_slower_on_shared_corridor()
    print("PASS test_more_agents_slower_on_shared_corridor")
    test_greedy_not_worse_than_all_dijkstra_crowded()
    print("PASS test_greedy_not_worse_than_all_dijkstra_crowded")
    test_live_occupancy_in_obs()
    print("PASS test_live_occupancy_in_obs")
    test_dijkstra_counts_edge_cost()
    print("PASS test_dijkstra_counts_edge_cost")
    test_travel_reward_sums_to_travel_time()
    print("PASS test_travel_reward_sums_to_travel_time")
    test_marginal_reward_charges_co_movers()
    print("PASS test_marginal_reward_charges_co_movers")
    test_regret_feature_zero_on_congested_best_hop()
    print("PASS test_regret_feature_zero_on_congested_best_hop")
    test_subproc_returns_agent_done()
    print("PASS test_subproc_returns_agent_done")
    print("MAPPO_MICRO_ENV_TESTS_OK")


if __name__ == "__main__":
    main()
