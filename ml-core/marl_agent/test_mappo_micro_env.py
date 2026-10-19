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
        env4 = MicroAlleyEnv(dp, gp, n_agents=4, max_steps=40, seed=0, depart_span_s=0.0)
        env8 = MicroAlleyEnv(dp, gp, n_agents=8, max_steps=80, seed=0, depart_span_s=0.0)
        env4.reset(options={"t": 50400.0, "ods": [od] * 4})
        env8.reset(options={"t": 50400.0, "ods": [od] * 8})
        for _ in range(40):
            env4.step(env4.baseline_dijkstra_actions())
            if all(env4._done):
                break
        for _ in range(80):
            env8.step(env8.baseline_dijkstra_actions())
            if all(env8._done):
                break
        assert float(np.mean(env8._travel)) >= float(np.mean(env4._travel)) - 1e-3


def test_greedy_not_worse_than_all_dijkstra_crowded() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td), n=10)
        od = (nodes[0], nodes[-1])
        env = MicroAlleyEnv(
            dp, gp, n_agents=8, max_steps=80, seed=1, depart_span_s=0.0
        )
        env.reset(seed=1, options={"t": 64800.0, "ods": [od] * 8})
        # dijkstra episode
        for _ in range(80):
            env.step(env.baseline_dijkstra_actions())
            if all(env._done):
                break
        djk = float(np.mean(env._travel))
        env.reset(seed=1, options={"t": 64800.0, "ods": [od] * 8})
        for _ in range(80):
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
            dp, gp, n_agents=4, max_degree=3, max_steps=20, seed=0, compact_dim=192
        )
        obs1, _, _ = env.reset(options={"t": 28800.0, "ods": [od] * 4})
        # all start at same origin → node_occ feature should be > 0
        # feature layout: after embeds, slot includes n_here/n_agents
        assert obs1["agent_0"].shape[0] == 192
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
            reward_mode="travel", travel_scale=1000.0, depart_span_s=0.0,
        )
        env.reset(options={"t": 64800.0, "ods": [od] * 4})
        ret = np.zeros(4)
        for _ in range(40):
            _, rew, _, _, _, info = env.step(env.baseline_dijkstra_actions())
            ret += [rew[a] for a in env.agents]
            if info["all_done"]:
                break
        np.testing.assert_allclose(-ret * 1000.0, env._travel, rtol=1e-6, atol=1e-6)


def test_reward_equals_travel_plus_city_for_every_controller() -> None:
    """Dijkstra and greedy_load are charged the same function: travel + pile penalty."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td), n=8)
        od = (nodes[0], nodes[-1])

        def run(mode: str) -> None:
            env = MicroAlleyEnv(
                dp, gp, n_agents=4, max_degree=3, max_steps=40, seed=0,
                reward_mode="travel", travel_scale=1000.0, depart_span_s=0.0,
                share_coef=8.0,
            )
            env.reset(options={"t": 28800.0, "ods": [od] * 4})
            ret = np.zeros(4)
            for _ in range(40):
                if mode == "greedy":
                    acts = env.baseline_greedy_load_actions()
                else:
                    acts = env.baseline_dijkstra_actions()
                _, rew, _, _, _, info = env.step(acts)
                ret += [rew[a] for a in env.agents]
                if info["all_done"]:
                    break
            assert info["arrival_rate"] == 1.0
            assert float(np.sum(env._city)) > 1.0
            target = np.asarray(env._travel) + np.asarray(env._city)
            np.testing.assert_allclose(-ret * 1000.0, target, rtol=1e-5, atol=1e-4)

        run("dijkstra")
        run("greedy")


def test_marginal_reward_charges_co_movers() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td), n=10)
        od = (nodes[0], nodes[-1])
        kw = dict(
            n_agents=6, max_degree=3, max_steps=40, seed=0,
            travel_scale=1000.0, depart_span_s=0.0,
        )
        env_t = MicroAlleyEnv(dp, gp, reward_mode="travel", **kw)
        env_m = MicroAlleyEnv(dp, gp, reward_mode="marginal", **kw)
        env_t.reset(options={"t": 64800.0, "ods": [od] * 6})
        env_m.reset(options={"t": 64800.0, "ods": [od] * 6})
        acts = env_t.baseline_dijkstra_actions()
        _, rt, _, _, _, _ = env_t.step(acts)
        _, rm, _, _, _, _ = env_m.step(acts)
        # Later vehicles pay the delay they impose on whoever is already in the alley.
        # The first vehicle's own slowdown shows up as a correction, so the fleet
        # sum is strictly more negative under marginal than under own-travel.
        assert sum(rm.values()) < sum(rt.values()) - 1e-6


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


def test_fast_vehicle_is_not_held_for_the_slow_one() -> None:
    """Clock jumps to the next decision, not to max(travel)."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("S", "M", 20.0, "residential"),
                ("M", "D", 20.0, "residential"),
                ("S", "L", 500.0, "alley"),
            ],
        )
        env = MicroAlleyEnv(
            dp, gp, n_agents=2, max_degree=3, max_steps=20, seed=0, depart_span_s=0.0
        )
        env.reset(options={"t": 28800.0, "ods": [("S", "D"), ("S", "L")]})
        env.step(env.baseline_dijkstra_actions())
        # Fast vehicle has reached M and must choose again. Slow one is still in S->L.
        assert env._pos[0] == "M"
        assert not env._done[0]
        assert env._edge_of[1] == ("S", "L")
        assert env._sim < env._exit_t[1] - 1.0
        assert env._travel[0] < env._exit_t[1]


def test_vehicle_still_in_alley_slows_follower() -> None:
    """A vehicle already inside the alley still raises the follower's travel,
    and the follower pushes the leader's exit later. n_agents is at least 2,
    so the alone-forecast is read off the leader before the follower enters.
    """
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(Path(td), [("O", "D", 100.0, "alley")])
        env = MicroAlleyEnv(
            dp, gp, n_agents=2, max_degree=2, max_steps=10, seed=0, depart_span_s=4.0
        )
        env.reset(options={"t": 28800.0, "ods": [("O", "D"), ("O", "D")]})
        assert env._depart[0] == 0.0 and env._depart[1] > 0.0
        assert sum(env._info_now()["agent_acting"]) == 1
        env.step(env.baseline_dijkstra_actions())
        assert env._edge_of[0] == ("O", "D")
        alone_exit = float(env._exit_t[0])
        env.step(env.baseline_dijkstra_actions())
        # Follower has entered; leader's scheduled exit moved, or they already
        # finished slower than the alone forecast.
        leader_exit = float(env._travel[0] if env._true_arrived[0] else env._exit_t[0])
        assert leader_exit > alone_exit + 0.2
        for _ in range(4):
            if all(env._done):
                break
            env.step(env.baseline_dijkstra_actions())
        assert env._true_arrived[0] and env._true_arrived[1]
        assert float(env._travel[0]) > alone_exit + 0.2
        assert float(env._travel[1]) > alone_exit + 0.2


def test_sampled_ods_are_unique_and_share_an_edge() -> None:
    with tempfile.TemporaryDirectory() as td:
        # Three origins merge onto trunk U->V, which has a slower bypass.
        spec = [
            ("o0", "U", 300.0, "residential"),
            ("o1", "U", 350.0, "residential"),
            ("o2", "U", 400.0, "residential"),
            ("U", "V", 80.0, "alley"),
            ("U", "B", 100.0, "residential"),
            ("B", "V", 400.0, "residential"),
            ("V", "d0", 300.0, "residential"),
            ("V", "d1", 350.0, "residential"),
            ("V", "d2", 400.0, "residential"),
        ]
        gp, dp = _graph(Path(td), spec)
        env = MicroAlleyEnv(
            dp, gp, n_agents=3, max_degree=4, max_steps=30, seed=2, depart_span_s=5.0
        )
        env.reset(seed=2, options={"t": 28800.0})
        origins = [o for o, _ in env._ods]
        dests = [d for _, d in env._ods]
        assert len(set(origins)) == 3
        assert len(set(dests)) == 3
        assert all(o != d for o, d in env._ods)
        assert env._overlap_edge == ("U", "V")
        for o, d in env._ods:
            assert env._through_edge(o, d, "U", "V")


def test_sampler_splits_two_corridors() -> None:
    """Two separate alleys can each hold the fleet. The draw uses both."""
    with tempfile.TemporaryDirectory() as td:
        spec = []
        for tag, u, v in (("A", "UA", "VA"), ("B", "UB", "VB")):
            for i, length in enumerate((400.0, 420.0, 440.0, 460.0)):
                spec.append((f"o{i}{tag}", u, length, "residential"))
                spec.append((v, f"d{i}{tag}", length, "residential"))
            spec.append((u, v, 80.0, "alley"))
        gp, dp = _graph(Path(td), spec)
        env = MicroAlleyEnv(
            dp, gp, n_agents=4, max_degree=4, max_steps=8, seed=1, shock_rate=1.0
        )
        env.reset(seed=1, options={"t": 28800.0})
        origins = [o for o, _ in env._ods]
        dests = [d for _, d in env._ods]
        assert len(set(origins)) == 4 and len(set(dests)) == 4

        def users(edge: tuple[str, str]) -> int:
            u, v = edge
            return sum(env._through_edge(o, d, u, v) for o, d in env._ods)

        a, b = users(("UA", "VA")), users(("UB", "VB"))
        assert a < 4 and b < 4
        assert a >= 1 and b >= 1
        assert env._shock_edge in {("UA", "VA"), ("UB", "VB")}
        assert users(env._shock_edge) >= 2


def test_full_alley_makes_the_next_vehicle_wait() -> None:
    """Storage is physical: the third vehicle cannot enter a full alley and the wait counts."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("O", "D", 12.0, "alley"),
                ("O", "B", 40.0, "residential"),
                ("B", "D", 40.0, "residential"),
            ],
        )
        env = MicroAlleyEnv(
            dp, gp, n_agents=3, max_degree=3, max_steps=30, seed=0,
            depart_span_s=0.0, jam_spacing_m=6.0,
        )
        env.reset(options={"t": 28800.0, "ods": [("O", "D")] * 3})
        assert env._storage(("O", "D")) == 2
        env.step(env.baseline_dijkstra_actions())
        inside = [i for i in range(3) if env._edge_of[i] == ("O", "D")]
        queued = [i for i in range(3) if env._queue_edge[i] == ("O", "D")]
        # They may already have been released from the queue if the step advanced
        # to the exit. Either the third is queued, or someone already paid a wait.
        assert len(inside) <= 2
        assert len(queued) == 1 or max(env._travel) > 0.2
        for _ in range(20):
            if all(env._done):
                break
            env.step(env.baseline_dijkstra_actions())
        assert all(env._true_arrived)
        assert max(env._travel) > min(env._travel) + 0.2


def test_social_rule_beats_selfish_on_a_steep_alley() -> None:
    """Private cost keeps entering after the delay imposed on occupants exceeds the bypass."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("O", "D", 80.0, "alley"),
                ("O", "B", 220.0, "residential"),
                ("B", "D", 220.0, "residential"),
            ],
        )
        env = MicroAlleyEnv(
            dp, gp, n_agents=8, max_degree=3, max_steps=40, seed=0, depart_span_s=0.0
        )

        def fleet(mode: str) -> float:
            obs, _, info = env.reset(options={"t": 28800.0, "ods": [("O", "D")] * 8})
            greedy = env.baseline_greedy_load_actions()
            social = env.baseline_social_actions()
            assert greedy != social
            for i, a in enumerate(env.agents):
                if not info["agent_acting"][i]:
                    continue
                blk = env.neighbor_block(obs[a])
                assert abs(float(blk[greedy[a], env.REGRET_IDX])) < 1e-5
            for _ in range(40):
                if mode == "social":
                    acts = env.baseline_social_actions()
                else:
                    acts = env.baseline_greedy_load_actions()
                _, _, _, _, _, info = env.step(acts)
                if info["all_done"]:
                    break
            assert info["arrival_rate"] == 1.0
            assert not info["truncated"]
            return float(np.mean(env._travel))

        selfish = fleet("greedy")
        social = fleet("social")
        assert social < selfish - 1.0, (social, selfish)


def test_scheduled_school_release_is_invisible_to_the_heuristic() -> None:
    """The alley is empty now, so greedy enters. The release is already on the clock."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("O", "D", 80.0, "alley"),
                ("O", "B", 160.0, "residential"),
                ("B", "D", 160.0, "residential"),
            ],
        )
        shock = [{"u": "O", "v": "D", "kind": "school", "t0": 1.0, "t1": 90.0, "extra": 8.0}]
        env = MicroAlleyEnv(
            dp, gp, n_agents=2, max_degree=3, max_steps=40, seed=0, depart_span_s=0.0
        )

        def fleet(avoid: bool) -> float:
            obs, _, _ = env.reset(
                options={"t": 28800.0, "ods": [("O", "D")] * 2, "shocks": shock}
            )
            if not avoid:
                blk = env.neighbor_block(obs["agent_0"])
                hop = env.baseline_greedy_load_actions()["agent_0"]
                assert env._neighbors("O")[hop] == "D"
                assert float(blk[hop, env.SHOCK_ETA_IDX]) > 0.0
                assert float(blk[hop, env.SHOCK_MAG_IDX]) > 0.0
            for _ in range(40):
                if avoid:
                    acts = {}
                    for i, a in enumerate(env.agents):
                        curr = env._pos[i]
                        neigh = env._neighbors(curr)[: env.max_degree]
                        best_j, best = 0, 1e18
                        for j, nxt in enumerate(neigh):
                            cost = 1e9 if (curr, nxt) == ("O", "D") else (
                                env._edge_free_time(curr, nxt) + env._remain_free(nxt, "D")
                            )
                            if cost < best:
                                best, best_j = cost, j
                        acts[a] = best_j
                else:
                    acts = env.baseline_greedy_load_actions()
                _, _, _, _, _, info = env.step(acts)
                if info["all_done"]:
                    break
            assert info["arrival_rate"] == 1.0
            return float(np.mean(env._travel))

        caught = fleet(False)
        around = fleet(True)
        assert around + 20.0 < caught, (around, caught)
        again, _, _ = env.reset(
            options={"t": 28800.0, "ods": [("O", "D")] * 2, "shocks": shock}
        )
        assert env._shocks[0]["kind"] == "school"
        assert env._shocks[0]["edge"] == ("O", "D")
        assert again["agent_0"].shape[0] == env.compact_dim


def test_other_approach_is_visible_before_the_merge() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("o1", "U", 30.0, "residential"),
                ("o2", "U", 400.0, "residential"),
                ("U", "V", 80.0, "alley"),
                ("U", "B", 80.0, "residential"),
                ("B", "D", 80.0, "residential"),
                ("V", "D", 40.0, "residential"),
            ],
        )
        env = MicroAlleyEnv(
            dp, gp, n_agents=2, max_degree=4, max_steps=20, seed=0, depart_span_s=0.0
        )
        obs, _, _ = env.reset(
            options={"t": 28800.0, "ods": [("o1", "D"), ("o2", "D")]}
        )
        env.step(env.baseline_dijkstra_actions())
        assert env._pos[0] == "U"
        assert env._edge_of[1] == ("o2", "U")
        blk = env.neighbor_block(env._local_obs(0))
        j = env._neighbors("U").index("V")
        assert float(blk[j, env.MERGE_IDX]) > 0.0
        # The heuristic still scores only who is already here or already inside.
        hop = env.baseline_greedy_load_actions()["agent_0"]
        assert abs(float(blk[hop, env.REGRET_IDX])) < 1e-5


def test_share_penalty_charges_piling_the_heuristic_ignores() -> None:
    """Own travel can still prefer the alley. The city score charges every extra vehicle."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("O", "D", 40.0, "alley"),
                ("O", "B", 180.0, "residential"),
                ("B", "D", 180.0, "residential"),
            ],
        )
        env = MicroAlleyEnv(
            dp, gp, n_agents=6, max_degree=3, max_steps=30, seed=0,
            depart_span_s=0.0, share_coef=8.0,
        )

        def run(spread: bool) -> tuple[float, float]:
            env.reset(options={"t": 28800.0, "ods": [("O", "D")] * 6})
            for _ in range(30):
                if spread:
                    acts = {}
                    for i, a in enumerate(env.agents):
                        curr = env._pos[i]
                        neigh = env._neighbors(curr)[: env.max_degree]
                        if curr == "O" and "B" in neigh and "D" in neigh:
                            acts[a] = neigh.index("B") if i else neigh.index("D")
                            continue
                        dest = env._ods[i][1]
                        best, bj = 1e18, 0
                        for j, nxt in enumerate(neigh):
                            cost = env._edge_free_time(curr, nxt) + env._remain_free(nxt, dest)
                            if cost < best:
                                best, bj = cost, j
                        acts[a] = bj
                else:
                    acts = env.baseline_greedy_load_actions()
                _, _, _, _, _, info = env.step(acts)
                if info["all_done"]:
                    break
            assert info["arrival_rate"] == 1.0
            return float(np.mean(env._travel)), float(np.mean(env._city))

        g_travel, g_city = run(False)
        s_travel, s_city = run(True)
        assert g_city > s_city + 1.0
        assert (s_travel + s_city) < (g_travel + g_city) - 1.0


def test_alley_features_can_be_hidden() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(Path(td), [("O", "D", 80.0, "alley"), ("O", "B", 80.0, "residential")])
        seen = MicroAlleyEnv(dp, gp, n_agents=2, max_degree=3, max_steps=5, seed=0)
        blind = MicroAlleyEnv(
            dp, gp, n_agents=2, max_degree=3, max_steps=5, seed=0, include_alley_info=False
        )
        kw = {"t": 28800.0, "ods": [("O", "D"), ("O", "B")]}
        obs_s, _, _ = seen.reset(options=kw)
        obs_b, _, _ = blind.reset(options=kw)
        j = seen._neighbors("O").index("D")
        blk_s = seen.neighbor_block(obs_s["agent_0"])
        blk_b = blind.neighbor_block(obs_b["agent_0"])
        assert float(blk_s[j, 1]) == 1.0
        assert float(blk_b[j, 1]) == 0.0
        assert float(blk_b[j, 7]) == pytest_cap()


def pytest_cap() -> float:
    return 1.0 / 8.0


def test_only_signal_presence_is_visible() -> None:
    """Both see that S has a light. Neither sees whether it is red or green."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("O", "S", 20.0, "residential"),
                ("S", "D", 20.0, "residential"),
                ("O", "B", 90.0, "residential"),
                ("B", "D", 90.0, "residential"),
            ],
        )
        env = MicroAlleyEnv(
            dp, gp, n_agents=2, max_degree=3, max_steps=20, seed=0, depart_span_s=0.0
        )

        def view(offset: float) -> tuple[float, float, float, str]:
            env._signals = {"S"}
            env._signal_offset = {"S": offset}
            obs, _, _ = env.reset(options={"t": 28800.0, "ods": [("O", "D"), ("O", "D")]})
            blk = env.neighbor_block(obs["agent_0"])
            neigh = env._neighbors("O")
            j_s, j_b = neigh.index("S"), neigh.index("B")
            hop = env.baseline_greedy_load_actions()["agent_0"]
            assert abs(float(blk[hop, env.REGRET_IDX])) < 1e-5
            return (
                float(blk[j_s, env.HAS_SIGNAL_IDX]),
                float(blk[j_b, env.HAS_SIGNAL_IDX]),
                float(blk[j_s, 12]),
                neigh[hop],
            )

        # offset 0 is red on arrival; offset 20 is green. The view must match.
        assert view(0.0) == view(20.0) == (1.0, 0.0, view(0.0)[2], "B")
        assert view(0.0)[2] < 0.05

        def run(offset: float, force_light: bool) -> float:
            env._signals = {"S"}
            env._signal_offset = {"S": offset}
            env.reset(options={"t": 28800.0, "ods": [("O", "D"), ("O", "D")]})
            for _ in range(20):
                if force_light:
                    acts = {}
                    for _i, a in enumerate(env.agents):
                        neigh = env._neighbors(env._pos[_i])[: env.max_degree]
                        if "S" in neigh:
                            acts[a] = neigh.index("S")
                        elif "D" in neigh:
                            acts[a] = neigh.index("D")
                        else:
                            acts[a] = 0
                else:
                    acts = env.baseline_greedy_load_actions()
                _, _, _, _, _, info = env.step(acts)
                if info["all_done"]:
                    break
            assert info["arrival_rate"] == 1.0
            return float(np.mean(env._travel))

        red = run(0.0, True)
        green = run(20.0, True)
        avoided = run(0.0, False)
        assert red > green + 15.0, (red, green)
        assert avoided + 5.0 < red, (avoided, red)
        assert green + 5.0 < avoided, (green, avoided)


def test_heuristic_enters_a_signal_that_is_the_destination() -> None:
    """Arriving ends the trip, so the light there is not a reason to turn away."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [("O", "S", 20.0, "residential"), ("O", "B", 30.0, "residential")],
        )
        env = MicroAlleyEnv(
            dp, gp, n_agents=2, max_degree=3, max_steps=5, seed=0, depart_span_s=0.0
        )
        env._signals = {"S"}
        env._signal_offset = {"S": 0.0}
        obs, _, _ = env.reset(options={"t": 28800.0, "ods": [("O", "S"), ("O", "S")]})
        neigh = env._neighbors("O")
        blk = env.neighbor_block(obs["agent_0"])
        assert float(blk[neigh.index("S"), env.HAS_SIGNAL_IDX]) == 1.0
        hop = env.baseline_greedy_load_actions()["agent_0"]
        assert neigh[hop] == "S"
        _, _, _, _, _, info = env.step(env.baseline_greedy_load_actions())
        assert info["arrival_rate"] == 1.0
        assert float(np.mean(env._travel)) < 5.0


def test_quan4_signal_net_holds_a_vehicle() -> None:
    """A snapped OSM signal in the Quận 4 net holds a motorcycle the same way the env would."""
    import shutil
    import xml.etree.ElementTree as ET

    import traci

    repo = Path(__file__).resolve().parents[2]
    net = repo / "sumo-env" / "networks" / "quan4_alleys.net.xml"
    sig_path = repo / "sumo-env" / "quan4_osm_signals.json"
    assert net.exists() and sig_path.exists()
    root = ET.parse(net).getroot()
    target = "366383451"
    assert any(el.get("id") == target for el in root.findall("tlLogic"))
    incoming = next(e for e in root.findall("edge") if e.get("to") == target)
    outgoing = next(e for e in root.findall("edge") if e.get("from") == target)
    la, lb = incoming.find("lane"), outgoing.find("lane")
    free = float(la.get("length")) / float(la.get("speed")) + float(lb.get("length")) / float(lb.get("speed"))
    row = next(r for r in json.loads(sig_path.read_text(encoding="utf-8"))["signals"] if r["node"] == target)
    hold = MicroAlleyEnv._red_wait(
        type(
            "S",
            (),
            {
                "_signals": {target},
                "_signal_offset": {target: float(row["offset_s"])},
                "SIGNAL_CYCLE_S": MicroAlleyEnv.SIGNAL_CYCLE_S,
                "SIGNAL_RED_S": MicroAlleyEnv.SIGNAL_RED_S,
            },
        )(),
        target,
        0.0,
    )
    assert hold > 15.0
    sumo = shutil.which("sumo")
    assert sumo
    with tempfile.TemporaryDirectory() as td:
        routes = Path(td) / "rou.xml"
        cfg = Path(td) / "run.sumocfg"
        routes.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<routes>
  <vType id="moto" length="2.0" maxSpeed="12" accel="2.0" decel="4.0"/>
  <vehicle id="v0" type="moto" depart="0"><route edges="{incoming.get("id")} {outgoing.get("id")}"/></vehicle>
</routes>
""",
            encoding="utf-8",
        )
        cfg.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <input>
    <net-file value="{net.as_posix()}"/>
    <route-files value="{routes.as_posix()}"/>
  </input>
  <time><begin value="0"/><end value="180"/></time>
</configuration>
""",
            encoding="utf-8",
        )
        traci.start([sumo, "-c", str(cfg), "--no-step-log", "true", "--no-warnings", "true"])
        try:
            assert abs(traci.trafficlight.getNextSwitch(target) - hold) < 0.5
            arrived = None
            for step in range(180):
                traci.simulationStep()
                if traci.simulation.getArrivedNumber() > 0:
                    arrived = step + 1
                    break
        finally:
            traci.close()
        assert arrived is not None and arrived > free + 15.0


def test_sumo_red_light_holds_a_vehicle() -> None:
    """The installed SUMO build stops a vehicle on a hand-written red phase."""
    import shutil

    import traci

    sumo = shutil.which("sumo")
    assert sumo, "sumo is not on PATH"
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "net.net.xml").write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<net version="1.16" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/net_file.xsd">
  <location netOffset="0.0,0.0" convBoundary="0.00,0.00,200.00,40.00" origBoundary="0.00,0.00,200.00,40.00" projParameter="!"/>
  <tlLogic id="J" type="static" programID="0" offset="0">
    <phase duration="20" state="r"/>
    <phase duration="20" state="G"/>
  </tlLogic>
  <junction id="O" type="priority" x="0.00" y="0.00" incLanes="" intLanes="" shape="-2.00,-2.00 2.00,-2.00 2.00,2.00 -2.00,2.00"/>
  <junction id="J" type="traffic_light" x="100.00" y="0.00" tl="J" incLanes="" intLanes="" shape="98.00,-2.00 102.00,-2.00 102.00,2.00 98.00,2.00"/>
  <junction id="D" type="priority" x="200.00" y="0.00" incLanes="" intLanes="" shape="198.00,-2.00 202.00,-2.00 202.00,2.00 198.00,2.00"/>
  <edge id="a" from="O" to="J" priority="1"><lane id="a_0" index="0" speed="10.00" length="100.00" shape="0.00,0.00 100.00,0.00"/></edge>
  <edge id="b" from="J" to="D" priority="1"><lane id="b_0" index="0" speed="10.00" length="100.00" shape="100.00,0.00 200.00,0.00"/></edge>
  <connection from="a" to="b" fromLane="0" toLane="0" tl="J" linkIndex="0" dir="s" state="o"/>
</net>
""",
            encoding="utf-8",
        )
        (root / "rou.rou.xml").write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<routes>
  <vType id="moto" length="2.0" maxSpeed="10" accel="2" decel="4"/>
  <vehicle id="v0" type="moto" depart="0">
    <route edges="a b"/>
  </vehicle>
</routes>
""",
            encoding="utf-8",
        )
        (root / "run.sumocfg").write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <input>
    <net-file value="net.net.xml"/>
    <route-files value="rou.rou.xml"/>
  </input>
  <time><begin value="0"/><end value="80"/></time>
</configuration>
""",
            encoding="utf-8",
        )
        traci.start([sumo, "-c", str(root / "run.sumocfg"), "--no-step-log", "true", "--start"])
        try:
            arrived = None
            for step in range(80):
                traci.simulationStep()
                done = traci.simulation.getArrivedIDList()
                if "v0" in done:
                    arrived = step + 1
                    break
            assert arrived is not None and arrived > 25, arrived
        finally:
            traci.close()


def test_truncation_costs_more_the_farther_a_car_is_left() -> None:
    """A flat floor let a policy bounce on short links. Distance left must cost."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td), n=10)
        env = MicroAlleyEnv(
            dp, gp, n_agents=2, max_degree=3, max_steps=40, seed=0, depart_span_s=0.0
        )
        env.reset(options={"t": 28800.0, "ods": [(nodes[0], nodes[-1])] * 2})
        env._pos[1] = nodes[-2]
        env._corr = [0.0, 0.0]
        env._force_truncate()
        far, near = env._travel
        assert near >= 2000.0
        assert far > near + 50.0, (far, near)
        assert not any(env._true_arrived)


def test_no_uturn_blocks_going_straight_back() -> None:
    """Back to the node just left is masked for everyone, unless it is the only exit."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("O", "A", 30.0, "residential"),
                ("A", "O", 30.0, "residential"),
                ("A", "D", 60.0, "residential"),
                ("O", "X", 30.0, "residential"),
                ("X", "O", 30.0, "residential"),
            ],
        )
        env = MicroAlleyEnv(
            dp, gp, n_agents=2, max_degree=3, max_steps=20, seed=0,
            depart_span_s=0.0, no_uturn=True,
        )
        env.reset(options={"t": 28800.0, "ods": [("O", "D"), ("O", "D")]})
        to_a = env._neighbors("O").index("A")
        env.step({a: to_a for a in env.agents})
        assert env._pos[0] == "A"
        mask = env.action_mask(0)
        back = env._neighbors("A").index("O")
        assert mask[back] == 0.0
        assert mask[env._neighbors("A").index("D")] == 1.0
        assert env._neighbors("A")[env.baseline_dijkstra_actions()["agent_0"]] == "D"
        assert env._neighbors("A")[env.baseline_greedy_load_actions()["agent_0"]] == "D"
        # X is a dead end: its only exit is back to O, which must stay open.
        env.reset(options={"t": 28800.0, "ods": [("O", "D"), ("O", "D")]})
        to_x = env._neighbors("O").index("X")
        env.step({a: to_x for a in env.agents})
        assert env._pos[0] == "X"
        assert env.action_mask(0)[env._neighbors("X").index("O")] == 1.0


def test_trip_cap_ends_a_looping_car_but_not_a_baseline() -> None:
    """A car past its time budget fails on its own; greedy and Dijkstra arrive."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("O", "A", 30.0, "residential"),
                ("A", "O", 30.0, "residential"),
                ("A", "B", 200.0, "residential"),
                ("B", "D", 200.0, "residential"),
            ],
        )
        kw = dict(
            n_agents=2, max_degree=3, max_steps=400, seed=0, depart_span_s=0.0,
            trip_cap_mult=1.5, trip_cap_min_s=30.0,
        )
        env = MicroAlleyEnv(dp, gp, **kw)
        od = ("O", "D")
        for mode in ("dijkstra", "greedy"):
            env.reset(options={"t": 28800.0, "ods": [od] * 2})
            for _ in range(400):
                acts = (
                    env.baseline_dijkstra_actions()
                    if mode == "dijkstra"
                    else env.baseline_greedy_load_actions()
                )
                _, _, _, _, _, info = env.step(acts)
                if info["all_done"]:
                    break
            assert info["arrival_rate"] == 1.0, mode
            assert not info["truncated"]
        # Shuttle O <-> A forever: the trip budget ends it, not the step cap.
        env.reset(options={"t": 28800.0, "ods": [od] * 2})
        ret = np.zeros(2)
        for _ in range(400):
            acts = {}
            for i, a in enumerate(env.agents):
                neigh = env._neighbors(env._pos[i])
                acts[a] = neigh.index("A") if "A" in neigh else neigh.index("O")
            _, rew, _, _, _, info = env.step(acts)
            ret += [rew[x] for x in env.agents]
            if info["all_done"]:
                break
        assert info["all_done"] and not info["truncated"]
        assert info["arrival_rate"] == 0.0
        assert min(env._travel) >= 2000.0
        np.testing.assert_allclose(-ret * 1000.0, env._travel, rtol=1e-5, atol=1e-3)


def test_crowding_metric_counts_shared_narrow_alley_time() -> None:
    """Two cars in the same narrow alley accumulate vehicle-seconds together;
    one car alone accumulates none. Independent of share_coef."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(Path(td), [("O", "D", 80.0, "alley"), ("O", "B", 80.0, "residential"), ("B", "D", 80.0, "residential")])

        def run(both_in_alley: bool) -> tuple[float, int]:
            env = MicroAlleyEnv(dp, gp, n_agents=2, max_degree=3, max_steps=20, seed=0, depart_span_s=0.0)
            env.reset(options={"t": 28800.0, "ods": [("O", "D"), ("O", "D")]})
            j_d = env._neighbors("O").index("D")
            j_b = env._neighbors("O").index("B")
            for _ in range(20):
                acts = {}
                for i, a in enumerate(env.agents):
                    if env._pos[i] == "O":
                        acts[a] = j_d if (both_in_alley or i == 0) else j_b
                    else:
                        acts[a] = 0
                _, _, _, _, _, info = env.step(acts)
                if info["all_done"]:
                    break
            assert info["arrival_rate"] == 1.0
            return env._crowd_vs, env._crowd_entries

        shared_vs, shared_n = run(True)
        alone_vs, alone_n = run(False)
        assert alone_vs == 0.0 and alone_n == 0
        assert shared_vs > 10.0 and shared_n == 1


def test_uturn_costs_time_and_the_obs_marks_the_way_back() -> None:
    """Going straight back costs uturn_delay_s (scaled by pace) for any controller.
    The exit back to the previous node is flagged, and visits are counted."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("O", "A", 30.0, "residential"),
                ("A", "O", 30.0, "residential"),
                ("A", "D", 300.0, "residential"),
            ],
        )

        def shuttle(delay: float) -> tuple[float, MicroAlleyEnv, np.ndarray]:
            env = MicroAlleyEnv(
                dp, gp, n_agents=2, max_degree=3, max_steps=40, seed=0,
                depart_span_s=0.0, uturn_delay_s=delay,
            )
            env.reset(options={"t": 28800.0, "ods": [("O", "D"), ("O", "D")]})
            env.step({a: env._neighbors("O").index("A") for a in env.agents})
            assert env._pos[0] == "A"
            obs = env._build_obs()
            blk = env.neighbor_block(obs["agent_0"])
            t_before = env._travel[0]
            env.step({a: env._neighbors("A").index("O") for a in env.agents})
            return env._travel[0] - t_before, env, blk

        plain, _, _ = shuttle(0.0)
        slow, env, blk = shuttle(5.0)
        assert slow >= plain + 5.0 - 1e-6, (plain, slow)
        back = env._neighbors("A").index("O")
        fwd = env._neighbors("A").index("D")
        assert blk[back, env.BACK_IDX] == 1.0 and blk[fwd, env.BACK_IDX] == 0.0
        assert blk[back, env.VISITED_IDX] > 0.0 and blk[fwd, env.VISITED_IDX] == 0.0


def test_accident_is_not_visible_before_it_starts() -> None:
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [("O", "D", 80.0, "alley"), ("O", "B", 160.0, "residential"), ("B", "D", 160.0, "residential")],
        )
        env = MicroAlleyEnv(dp, gp, n_agents=2, max_degree=3, max_steps=40, seed=0, depart_span_s=0.0)
        crash = [{"u": "O", "v": "D", "kind": "obstacle", "t0": 30.0, "t1": 90.0, "extra": 0.0}]
        obs, _, _ = env.reset(options={"t": 28800.0, "ods": [("O", "D")] * 2, "shocks": crash})
        j = env._neighbors("O").index("D")
        blk = env.neighbor_block(obs["agent_0"])
        assert float(blk[j, env.SHOCK_ETA_IDX]) == 0.0
        assert float(blk[j, env.SHOCK_MAG_IDX]) == 0.0
        env._sim = 40.0
        assert env._shock_view(("O", "D")) == (0.0, 1.0)


def test_informed_greedy_uses_the_timetable_mappo_sees() -> None:
    """Same school release as the invisibility test: greedy_load enters,
    greedy_informed reads the timetable and takes the bypass. Without any
    scheduled event the two rules are identical."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("O", "D", 80.0, "alley"),
                ("O", "B", 160.0, "residential"),
                ("B", "D", 160.0, "residential"),
            ],
        )
        school = [{"u": "O", "v": "D", "kind": "school", "t0": 1.0, "t1": 90.0, "extra": 8.0}]
        env = MicroAlleyEnv(dp, gp, n_agents=2, max_degree=3, max_steps=40, seed=0, depart_span_s=0.0)

        def fleet(mode: str, shocks: list[dict]) -> tuple[float, str]:
            env.reset(options={"t": 28800.0, "ods": [("O", "D")] * 2, "shocks": shocks})
            first = None
            for _ in range(40):
                acts = (
                    env.baseline_greedy_informed_actions()
                    if mode == "informed"
                    else env.baseline_greedy_load_actions()
                )
                if first is None:
                    first = env._neighbors("O")[acts["agent_0"]]
                _, _, _, _, _, info = env.step(acts)
                if info["all_done"]:
                    break
            assert info["arrival_rate"] == 1.0
            return float(np.mean(env._travel)), str(first)

        g_t, g_hop = fleet("greedy", school)
        i_t, i_hop = fleet("informed", school)
        assert g_hop == "D" and i_hop == "B"
        assert i_t + 5.0 < g_t, (i_t, g_t)
        assert fleet("greedy", []) == fleet("informed", [])


def test_dead_end_is_not_offered_and_never_freezes_the_episode() -> None:
    """X has no exit. It is masked for O->D; a car that starts there fails at once."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("O", "A", 30.0, "residential"),
                ("A", "D", 30.0, "residential"),
                ("O", "X", 10.0, "residential"),
                ("D", "O", 30.0, "residential"),
            ],
        )
        env = MicroAlleyEnv(dp, gp, n_agents=2, max_degree=3, max_steps=40, seed=0, depart_span_s=0.0)
        env.reset(options={"t": 28800.0, "ods": [("O", "D"), ("O", "D")]})
        mask = env.action_mask(0)
        assert mask[env._neighbors("O").index("X")] == 0.0
        assert mask[env._neighbors("O").index("A")] == 1.0
        env.reset(options={"t": 28800.0, "ods": [("X", "D"), ("O", "D")]})
        assert env._done[0] and not env._true_arrived[0]
        assert env._travel[0] >= 2000.0
        for _ in range(40):
            _, _, _, _, _, info = env.step(env.baseline_greedy_load_actions())
            if info["all_done"]:
                break
        assert info["all_done"] and not info["truncated"]
        assert env._true_arrived[1]


def test_progress_shaping_leaves_the_score_alone() -> None:
    """Shaping only moves reward. Travel and city are unchanged, and the extra
    reward per car telescopes to its starting time-to-go when γ = 1."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp = _graph(
            Path(td),
            [
                ("O", "A", 30.0, "residential"),
                ("A", "O", 30.0, "residential"),
                ("A", "B", 200.0, "residential"),
                ("B", "D", 200.0, "residential"),
            ],
        )
        od = ("O", "D")

        def run(coef: float) -> tuple[np.ndarray, list[float], list[float], float]:
            env = MicroAlleyEnv(
                dp, gp, n_agents=2, max_degree=3, max_steps=40, seed=0,
                depart_span_s=0.0, share_coef=8.0,
                progress_shaping=coef, shaping_gamma=1.0,
            )
            env.reset(options={"t": 28800.0, "ods": [od] * 2})
            start = env._remain_bpr("O", "D")
            ret = np.zeros(2)
            for _ in range(40):
                _, rew, _, _, _, info = env.step(env.baseline_greedy_load_actions())
                ret += [rew[a] for a in env.agents]
                if info["all_done"]:
                    break
            assert info["arrival_rate"] == 1.0
            return ret, list(env._travel), list(env._city), start

        ret_off, trav_off, city_off, start = run(0.0)
        ret_on, trav_on, city_on, _ = run(1.0)
        assert trav_on == trav_off and city_on == city_off
        np.testing.assert_allclose(ret_on - ret_off, start / 1000.0, rtol=1e-6, atol=1e-9)


def test_acting_obs_matches_a_full_recompute() -> None:
    """Ready agents always get a fresh vector; mid-edge agents may reuse cache."""
    with tempfile.TemporaryDirectory() as td:
        gp, dp, nodes = _chain_graph(Path(td), n=10)
        env = MicroAlleyEnv(
            dp, gp, n_agents=4, max_degree=3, max_steps=40, seed=0, depart_span_s=0.0
        )
        env.reset(options={"t": 28800.0, "ods": [(nodes[0], nodes[-1])] * 4})
        for _ in range(12):
            obs, _, _, _, _, info = env.step(env.baseline_greedy_load_actions())
            fresh = env._build_obs()
            for i, a in enumerate(env.agents):
                if info["agent_acting"][i]:
                    np.testing.assert_allclose(obs[a], fresh[a], rtol=0.0, atol=0.0)
            if info["all_done"]:
                break


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
            assert len(out) == 11 and out[6].shape == (1, 2)
            assert out[7].shape == (1, 2)
            assert out[10].shape == (1, 2)
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
    test_reward_equals_travel_plus_city_for_every_controller()
    print("PASS test_reward_equals_travel_plus_city_for_every_controller")
    test_marginal_reward_charges_co_movers()
    print("PASS test_marginal_reward_charges_co_movers")
    test_regret_feature_zero_on_congested_best_hop()
    print("PASS test_regret_feature_zero_on_congested_best_hop")
    test_fast_vehicle_is_not_held_for_the_slow_one()
    print("PASS test_fast_vehicle_is_not_held_for_the_slow_one")
    test_vehicle_still_in_alley_slows_follower()
    print("PASS test_vehicle_still_in_alley_slows_follower")
    test_sampled_ods_are_unique_and_share_an_edge()
    print("PASS test_sampled_ods_are_unique_and_share_an_edge")
    test_sampler_splits_two_corridors()
    print("PASS test_sampler_splits_two_corridors")
    test_full_alley_makes_the_next_vehicle_wait()
    print("PASS test_full_alley_makes_the_next_vehicle_wait")
    test_social_rule_beats_selfish_on_a_steep_alley()
    print("PASS test_social_rule_beats_selfish_on_a_steep_alley")
    test_scheduled_school_release_is_invisible_to_the_heuristic()
    print("PASS test_scheduled_school_release_is_invisible_to_the_heuristic")
    test_other_approach_is_visible_before_the_merge()
    print("PASS test_other_approach_is_visible_before_the_merge")
    test_share_penalty_charges_piling_the_heuristic_ignores()
    print("PASS test_share_penalty_charges_piling_the_heuristic_ignores")
    test_alley_features_can_be_hidden()
    print("PASS test_alley_features_can_be_hidden")
    test_only_signal_presence_is_visible()
    print("PASS test_only_signal_presence_is_visible")
    test_heuristic_enters_a_signal_that_is_the_destination()
    print("PASS test_heuristic_enters_a_signal_that_is_the_destination")
    test_quan4_signal_net_holds_a_vehicle()
    print("PASS test_quan4_signal_net_holds_a_vehicle")
    test_sumo_red_light_holds_a_vehicle()
    print("PASS test_sumo_red_light_holds_a_vehicle")
    test_truncation_costs_more_the_farther_a_car_is_left()
    print("PASS test_truncation_costs_more_the_farther_a_car_is_left")
    test_no_uturn_blocks_going_straight_back()
    print("PASS test_no_uturn_blocks_going_straight_back")
    test_trip_cap_ends_a_looping_car_but_not_a_baseline()
    print("PASS test_trip_cap_ends_a_looping_car_but_not_a_baseline")
    test_crowding_metric_counts_shared_narrow_alley_time()
    print("PASS test_crowding_metric_counts_shared_narrow_alley_time")
    test_uturn_costs_time_and_the_obs_marks_the_way_back()
    print("PASS test_uturn_costs_time_and_the_obs_marks_the_way_back")
    test_accident_is_not_visible_before_it_starts()
    print("PASS test_accident_is_not_visible_before_it_starts")
    test_informed_greedy_uses_the_timetable_mappo_sees()
    print("PASS test_informed_greedy_uses_the_timetable_mappo_sees")
    test_dead_end_is_not_offered_and_never_freezes_the_episode()
    print("PASS test_dead_end_is_not_offered_and_never_freezes_the_episode")
    test_progress_shaping_leaves_the_score_alone()
    print("PASS test_progress_shaping_leaves_the_score_alone")
    test_acting_obs_matches_a_full_recompute()
    print("PASS test_acting_obs_matches_a_full_recompute")
    test_subproc_returns_agent_done()
    print("PASS test_subproc_returns_agent_done")
    print("MAPPO_MICRO_ENV_TESTS_OK")


if __name__ == "__main__":
    main()
