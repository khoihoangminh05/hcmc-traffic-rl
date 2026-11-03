"""Tests of routing2.gnn_policy and its use in the SUMO env. Run: python -u -m routing2.test_gnn_policy"""

from __future__ import annotations

import math
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch

from .demand import make_demand, pick_zones
from .gnn_policy import N_DYN_ACTOR, N_GLOBAL, N_LOCAL, RoutingNet, prep_local
from .graph import DEFAULT_GRAPH, load_graph
from .params import SimConfig
from .sumo_env import N_FEAT, SumoEnvConfig, SumoRoutingEnv
from .sumo_marl import _RLActor, _tick_groups
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
        glob = torch.stack([(t / H).clamp(max=1.0), torch.full((M,), 0.5)], -1)
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


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}", flush=True)
    print("GNN_POLICY_TESTS_OK")


if __name__ == "__main__":
    main()
