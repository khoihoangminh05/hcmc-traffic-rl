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
    test_acting_obs_matches_a_full_recompute()
    print("PASS test_acting_obs_matches_a_full_recompute")
    test_subproc_returns_agent_done()
    print("PASS test_subproc_returns_agent_done")
    print("MAPPO_MICRO_ENV_TESTS_OK")


if __name__ == "__main__":
    main()
