"""Tests of routing2.gnn_policy and its use in the SUMO env. Run: python -u -m routing2.test_gnn_policy"""

from __future__ import annotations

import math
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch

from .demand import hot_zone_index, make_demand, pick_zones
from .gnn_policy import N_DYN_ACTOR, N_GLOBAL, N_LOCAL, RoutingNet, prep_local, prior_weights
from .graph import DEFAULT_GRAPH, load_graph
from .params import SimConfig
from .sumo_env import N_FEAT, SumoEnvConfig, SumoRoutingEnv
from .sumo_marl import _RLActor, _tick_groups, fleet_weights, gae, numpy_state, potential_shaping, team_reward
from .sumo_net import build_net

H = 180.0
_g = load_graph(DEFAULT_GRAPH, replace(SimConfig(), horizon_s=H))
_z = pick_zones(_g, 32, seed=0)
_net = build_net(DEFAULT_GRAPH, Path("../sumo-env/networks/v4"))
_work = Path("artifacts/out/quan4/routing2_gnn_test")


def _env(end: float = H, **kw) -> SumoRoutingEnv:
    base = dict(micro=True, live_every_s=10.0, live_source="probe")
    return SumoRoutingEnv(_g, _z, SumoEnvConfig(net=_net, horizon_s=end, work_dir=_work, **{**base, **kw}))


def _tiny() -> RoutingNet:
    # chain of links 0 -> 1 -> 2 -> 3 -> 4
    frm, to = torch.tensor([0, 1, 2, 3]), torch.tensor([1, 2, 3, 4])
    return RoutingNet(frm, to, torch.zeros(5, 3), hidden=16, layers=3).eval()


def test_jam_three_links_ahead_reaches_the_current_link():
    net = _tiny()
    a, b = torch.zeros(1, 5, N_DYN_ACTOR), torch.zeros(1, 5, N_DYN_ACTOR)
    b[0, 3, 0] = 3.0
    ha, _ = net.encode_actor(a)
    hb, _ = net.encode_actor(b)
    assert not torch.allclose(ha[0, 0], hb[0, 0], atol=1e-6), "3 layers must reach 3 links upstream"
    c = torch.zeros(1, 5, N_DYN_ACTOR)
    c[0, 4, 0] = 3.0
    assert torch.allclose(ha[0, 0], net.encode_actor(c)[0][0, 0], atol=1e-6), "4 links is out of reach"


def test_untrained_prior_is_exactly_the_chosen_controller():
    feat, cand = torch.rand(40, 3, N_FEAT) * 50.0 + 1.0, torch.tensor([[0, 1, 2]] * 39 + [[3, 4, -1]])
    mask = cand >= 0
    costs = {"ff": feat[..., 0] + feat[..., 3], "app": feat[..., 1] + feat[..., 6],
             "greedy": feat[..., 1] + feat[..., 6] + 0.5 * (feat[..., 2] + feat[..., 5])}
    for rule, cost in costs.items():
        net = RoutingNet(torch.tensor([0, 1]), torch.tensor([1, 2]), torch.zeros(5, 3), hidden=16, layers=2,
                         prior=prior_weights(rule, 120.0, 0.5)).eval()
        h, z = net.encode_actor(torch.rand(1, 5, N_DYN_ACTOR))
        logits = net.policy(h, z, cand, prep_local(feat, mask), torch.zeros(40, N_GLOBAL), torch.zeros(40, dtype=torch.long))
        assert torch.equal(logits.argmax(1), torch.where(mask, cost, torch.full((40, 3), 1e9)).argmin(1)), rule


def test_fleet_ahead_counts_along_the_live_path():
    env = _env(60.0)
    gen = torch.Generator().manual_seed(1)
    load = torch.randint(0, 4, (env.g.n_edges,), generator=gen).float()
    env.live_tt = env.ff_edge * (1.0 + torch.rand(env.g.n_edges, generator=gen))
    env.live_D = env._time_to_zones(env.live_tt)
    table = env._fleet_ahead_table(load)
    n = 0
    for z in range(len(env.zones)):
        for e in torch.randint(0, env.g.n_edges, (20,), generator=gen).tolist():
            if math.isfinite(float(env.live_D[z, e])):
                assert abs(float(table[z, e]) - sum(float(load[x]) for x in env.live_path(z, e))) < 1e-3
                n += 1
    assert n > 100


def test_exit_order_and_padding_do_not_matter():
    net = _tiny()
    h, z = net.encode_actor(torch.rand(1, 5, N_DYN_ACTOR))
    local = torch.rand(1, 3, N_LOCAL)
    glob = torch.rand(1, N_GLOBAL)
    b = torch.zeros(1, dtype=torch.long)
    cand = torch.tensor([[1, 2, 3]])
    base = net.policy(h, z, cand, local, glob, b)
    perm = [2, 0, 1]
    swapped = net.policy(h, z, cand[:, perm], local[:, perm], glob, b)
    assert torch.allclose(base[0, perm], swapped[0], atol=1e-5)
    pad = torch.cat([cand, torch.tensor([[-1]])], 1)
    padded = net.policy(h, z, pad, torch.cat([local, torch.zeros(1, 1, N_LOCAL)], 1), glob, b)
    assert torch.allclose(base[0], padded[0, :3], atol=1e-5) and padded[0, 3] < -1e8


def test_learner_gets_the_same_logp_as_the_worker_on_the_real_map():
    """PPO is only valid if the stored report-period state reproduces what the vehicle saw."""
    env = _env(H + 200.0, max_detour=0.5)
    net = RoutingNet.from_env(env, 32, 2).eval()
    actor = _RLActor(net, H, 0.5, torch.Generator().manual_seed(3))
    ep = env.run(make_demand(_g, _z, [61000], 3000.0, H, 0.5), 0, actor, record=True)
    M = len(ep.decisions)
    assert M > 100 and len(ep.ticks) > 5
    D = env.Dmax
    feat, cand = torch.zeros(M, D, N_FEAT), torch.full((M, D), -1, dtype=torch.long)
    for j, d in enumerate(ep.decisions):
        k = len(d["cand"])
        feat[j, :k], cand[j, :k] = d["feat"], torch.tensor(d["cand"])
    a = torch.tensor([d["a"] for d in ep.decisions])
    t = torch.tensor([d["t"] for d in ep.decisions], dtype=torch.float32)
    tick = np.array([d["tick"] for d in ep.decisions])
    dyn = torch.stack([x["actor"] for x in ep.ticks])
    true = torch.stack([x["true"] for x in ep.ticks])
    assert dyn.shape[1:] == (env.g.n_edges, N_DYN_ACTOR) and true.shape == dyn.shape
    assert true[..., 0].sum() > dyn[..., 1].sum() * 0.5, "true counts include the background"
    logp_w = torch.cat(actor.logp)
    groups = _tick_groups(tick)
    assert sum(len(g) for g in groups.values()) == M
    worst = 0.0
    with torch.no_grad():
        ids = sorted(groups)
        h, z = net.encode_actor(dyn[ids])
        pos = {k: i for i, k in enumerate(ids)}
        b = torch.tensor([pos[int(x)] for x in tick])
        glob = torch.stack([(t / H).clamp(max=1.0), torch.full((M,), 0.5), torch.full((M,), 0.9)], -1)
        logits = net.policy(h, z, cand, prep_local(feat, cand >= 0), glob, b)
        logp = torch.log_softmax(logits, 1).gather(1, a.unsqueeze(1)).squeeze(1)
        worst = float((logp - logp_w).abs().max())
        hc, zc = net.encode_critic(dyn[ids], true[ids])
        v = net.critic(hc, zc, cand, prep_local(feat, cand >= 0), glob, b)
    assert worst < 1e-3, f"log-prob differs by {worst}"
    assert v.shape == (M,) and torch.isfinite(v).all()
    print(f"  decisions={M} ticks={len(ep.ticks)} worst logp gap={worst:.2e}", flush=True)


def test_detour_limit_holds_and_always_leaves_an_exit():
    class Longest:
        def __init__(self, env):
            self.env, self.over = env, 0

        def act(self, req):
            s = req.feat[..., 0] + req.feat[..., 3]
            assert (req.cand[0] >= 0).any()
            return s.masked_fill(req.cand < 0, -math.inf).argmax(1)  # always the longest allowed exit

    env = _env(H + 1200.0, max_detour=0.5)
    ep = env.run(make_demand(_g, _z, [61000], 1500.0, H, 1.0), 0, Longest(env), record=False)
    assert ep.metrics["unfinished_all"] == 0, ep.metrics  # the worst policy still gets everyone home
    worst = max(env._ff_done[v] / (1.5 * env._ff_orig[v] + 60.0) for v in env._ff_done)
    print(f"  worst policy: T_cust={ep.metrics['T_cust_s']:.0f}s index={ep.metrics['congestion_index']:.2f} "
          f"worst used/limit={worst:.2f}", flush=True)


def test_speed_of_one_gnn_pass_and_one_decision():
    torch.set_num_threads(1)
    env = _env()
    net = RoutingNet.from_env(env, 64, 3).eval()
    dyn = torch.zeros(1, env.g.n_edges, N_DYN_ACTOR)
    with torch.no_grad():
        t0 = time.perf_counter()
        for _ in range(20):
            h, z = net.encode_actor(dyn)
        gnn = (time.perf_counter() - t0) / 20
        cand = torch.zeros(1, env.Dmax, dtype=torch.long)
        cand[0, 2:] = -1
        local = torch.zeros(1, env.Dmax, N_LOCAL)
        glob, b = torch.zeros(1, N_GLOBAL), torch.zeros(1, dtype=torch.long)
        t0 = time.perf_counter()
        for _ in range(200):
            net.policy(h, z, cand, local, glob, b)
        dec = (time.perf_counter() - t0) / 200
    n = sum(p.numel() for p in net.parameters())
    print(f"  params={n} gnn pass={gnn * 1000:.1f} ms decision={dec * 1000:.2f} ms", flush=True)


def test_reward_weights_follow_j():
    assert fleet_weights(0.5, 1.0) == (1.0, 0.5)
    assert fleet_weights(0.5, 0.5) == (0.75, 0.25) and fleet_weights(0.5, 0.25) == (0.625, 0.125)
    assert fleet_weights(0.0, 0.5) == (1.0, 0.0)  # only customers matter


def test_discount_depends_on_seconds():
    r, v = np.array([0.0, 0.0], dtype=np.float32), np.array([0.0, 1.0], dtype=np.float32)
    veh, t, done = np.array([0, 0]), np.array([0.0, 10.0]), np.array([False, True])
    short = gae(r, v, veh, t, done, np.array([10.0, 5.0]), 0.99, 0.0)[0][0]
    long_ = gae(r, v, veh, t, done, np.array([100.0, 5.0]), 0.99, 0.0)[0][0]
    assert math.isclose(short, 0.99**10, rel_tol=1e-5) and math.isclose(long_, 0.99**100, rel_tol=1e-5)


def test_delay_charges_add_up_on_the_real_map():
    class App:
        def act(self, req):
            return req.live_cost.argmin(1)

    env = _env(H + 900.0, max_detour=0.5, attribute_every_s=5.0)
    ep = env.run(make_demand(_g, _z, [61000], 6000.0, H, 0.5), 0, App(), record=True)
    charged = sum(ep.caused_s.values())
    per_decision = sum(d["e_cust"] + d["e_other"] for d in ep.decisions)
    assert ep.delay_seen_s > 0 and 0 < charged <= ep.delay_attributed_s <= ep.delay_seen_s + 1e-6
    assert min(d["e_cust"] for d in ep.decisions) >= -1e-6
    # every second charged lands on one of the vehicle's decisions (origin decisions start at 0)
    assert math.isclose(per_decision, charged, rel_tol=1e-6), (per_decision, charged)
    print(f"  delay seen={ep.delay_seen_s:.0f}s blamed={ep.delay_attributed_s:.0f}s on fleet={charged:.0f}s", flush=True)


def test_system_rate_integrates_to_the_two_objectives():
    """The shared reward term must be J itself, not an approximation of it."""
    class App:
        def act(self, req):
            return req.live_cost.argmin(1)

    env = _env(H + 900.0, max_detour=0.5)
    ep = env.run(make_demand(_g, _z, [61000], 3000.0, H, 0.5), 0, App(), record=True)
    m = ep.metrics
    assert m["unfinished_all"] == 0
    assert abs(ep.system_all_s - m["T_all_s"]) < 1.0, (ep.system_all_s, m["T_all_s"])
    assert abs(ep.system_cust_s - m["T_cust_s"]) < 1.0, (ep.system_cust_s, m["T_cust_s"])
    d = ep.decisions[0]
    assert d["sys_all"] >= 0 and d["sys_cust"] >= 0
    print(f"  integral {ep.system_all_s:.2f} vs T_all {m['T_all_s']:.2f}; "
          f"{ep.system_cust_s:.2f} vs T_cust {m['T_cust_s']:.2f}", flush=True)


def test_team_reward_limits():
    dt, sa, sc = np.array([10.0]), np.array([4.0]), np.array([2.0])
    assert math.isclose(float(team_reward(dt, sa, sc, (0.4, 0.2), 0.5, 0.0)[0]), -10.0 / 60.0)  # rho 0 = selfish
    full = float(team_reward(dt, sa, sc, (0.4, 0.2), 0.5, 1.0)[0])
    assert math.isclose(full, -(0.5 * 4 + 0.5 * 2) / 0.3 / 60.0)


def test_single_exits_are_not_asked():
    class App:
        n_asked = 0

        def act(self, req):
            assert (req.cand >= 0).sum(1).min() > 1
            App.n_asked += len(req.vid)
            return req.live_cost.argmin(1)

    H = 120.0
    env = _env(H)
    ep = env.run(make_demand(_g, _z, [61000], 6000.0, H, 1.0), 0, App(), record=True)
    assert ep.forced > 0 and App.n_asked == ep.n_decisions == len(ep.decisions)
    assert ep.missed_decisions == 0
    print(f"  asked={ep.n_decisions} forced={ep.forced}")


def test_potential_terms_add_up_to_the_first_potential():
    togo = np.array([100.0, 60.0, 30.0, 50.0, 40.0], dtype=np.float32)
    veh = np.array([0, 0, 0, 1, 1])
    t = np.array([0.0, 10.0, 20.0, 5.0, 9.0], dtype=np.float32)
    dt = np.array([10.0, 10.0, 30.0, 4.0, 3.0], dtype=np.float32)
    done = np.array([True, True, True, True, False])
    f = potential_shaping(togo, veh, t, done, dt, 1.0) * 60.0
    assert abs(f[:3].sum() - 100.0) < 1e-3  # arrived: everything from the first R to 0
    assert abs(f[3] - 10.0) < 1e-3 and abs(f[4]) < 1e-3  # cut at the horizon: keeps its own R
    order = np.array([3, 0, 4, 1, 2])  # same result in any row order
    g = potential_shaping(togo[order], veh[order], t[order], done[order], dt[order], 1.0) * 60.0
    assert np.allclose(g, f[order])


def test_peak_demand_goes_to_the_hot_zones_and_bunches():
    H = 600.0
    hot = hot_zone_index(_g, _z, 4)
    plain = make_demand(_g, _z, [1], 6000.0, H, 0.5)
    peak = make_demand(_g, _z, [1], 6000.0, H, 0.5, hot_share=0.6, peak_sd=0.15)
    share = lambda d: float(torch.isin(d.dest_zone, hot).float().mean())  # noqa: E731
    assert share(peak) > 0.35 > 0.25 > share(plain)
    assert peak.dep_t.std() < 0.7 * plain.dep_t.std()
    assert bool((peak.orig != _z[peak.dest_zone]).all())
    again = make_demand(_g, _z, [1], 6000.0, H, 0.5, hot_share=0.6, peak_sd=0.15)
    assert torch.equal(peak.orig, again.orig) and torch.equal(peak.dest_zone, again.dest_zone)


def test_real_world_limits_change_what_is_known_not_the_trips():
    class App:
        def __init__(self):
            self.rows = []

        def act(self, req):
            self.rows.append((req.vid[0], req.cand[0].tolist(), req.feat[0].tolist()))
            return req.live_cost.argmin(1)

    H = 120.0
    d = make_demand(_g, _z, [61000], 6000.0, H, 0.5)
    limits = dict(report_drop=0.5, report_noise=0.2, fleet_snapshot=True, compliance=0.7, bg_reroute_share=0.5,
                  incident_seed=7)
    a, b = App(), App()
    ep = _env(H, **limits).run(d, 0, a, record=False)
    _env(H, **limits).run(d, 0, b, record=False)
    assert ep.n_trips == make_demand(_g, _z, [61000], 6000.0, H, 0.5).dep_t.numel()
    assert ep.missed_decisions == 0 and ep.n_decisions > 0
    full = _env(H, incident_seed=7).run(d, 0, App(), record=False)
    assert full.metrics["T_all_s"] != ep.metrics["T_all_s"]  # the limits reach the simulation
    print(f"  T_all full={full.metrics['T_all_s']:.1f} limited={ep.metrics['T_all_s']:.1f}")


def test_actor_and_critic_learn_at_their_own_rates():
    net = RoutingNet.from_env(_env(60.0))
    a, c = net.param_groups(1e-4, 5e-4)
    assert a["lr"] == 1e-4 and c["lr"] == 5e-4
    assert sum(p.numel() for p in a["params"]) + sum(p.numel() for p in c["params"]) == \
        sum(p.numel() for p in net.parameters())
    assert {id(p) for p in net.value.parameters()} <= {id(p) for p in c["params"]}
    assert not {id(p) for p in net.score.parameters()} & {id(p) for p in c["params"]}


def test_weights_reach_workers_without_tensors():
    a, b = _tiny(), _tiny()
    st = numpy_state(a)
    assert st and all(isinstance(v, np.ndarray) for v in st.values())
    b.load_state_dict({k: torch.from_numpy(v) for k, v in st.items()})
    x = torch.rand(1, 5, N_DYN_ACTOR)
    assert torch.equal(a.encode_actor(x)[1], b.encode_actor(x)[1])


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}", flush=True)
    print("GNN_POLICY_TESTS_OK")


if __name__ == "__main__":
    main()
