"""Tests for the GPU meso simulator (run on CPU).

    python -u -m routing2.test_meso   # prints MESO_TESTS_OK
"""

from __future__ import annotations

import math
from dataclasses import replace

import networkx as nx
import torch

from .demand import make_demand, pick_zones
from .graph import DEFAULT_GRAPH, load_graph
from .meso_gpu import ARRIVED, ON_LINK, MesoSim, group_rank
from .params import SimConfig
from .policies import AppReroute, Mixed, RandomExit, ShortestPath, bellman_ford

CFG = SimConfig(horizon_s=900.0)


def _setup(cfg: SimConfig = CFG, seeds=(1, 2), tph: float = 1200.0, pen: float = 0.5, window=None):
    g = load_graph(DEFAULT_GRAPH, cfg)
    zones = pick_zones(g, 16, seed=0)
    d = make_demand(g, zones, list(seeds), tph, cfg.horizon_s, pen, depart_window_s=window)
    return g, zones, d


def test_group_rank() -> None:
    grp = torch.tensor([3, 1, 3, 1, 3])
    order = torch.tensor([5.0, 2.0, 1.0, 2.0, 3.0])
    assert group_rank(grp, order).tolist() == [2, 0, 0, 1, 1]


def test_bellman_ford_matches_dijkstra() -> None:
    g, zones, _ = _setup()
    cost = (g.length / g.v_free).unsqueeze(0)
    D = bellman_ford(g.src, g.dst, cost, zones, g.n_nodes)[0]
    G = nx.DiGraph()
    for s, t, c in zip(g.src.tolist(), g.dst.tolist(), cost[0].tolist()):
        G.add_edge(s, t, w=c)
    for zi in (0, 5):
        z = int(zones[zi])
        ref = nx.single_source_dijkstra_path_length(G.reverse(), z, weight="w")
        for n in list(ref)[:200]:
            assert abs(float(D[zi, n]) - ref[n]) < 1e-3, (n, float(D[zi, n]), ref[n])


def test_conservation_and_storage() -> None:
    cfg = replace(CFG, stuck_time_s=math.inf)  # strict storage: no gridlock release
    g, zones, d = _setup(cfg, tph=6000.0)
    sim = MesoSim(g, d, zones, cfg)
    pol = Mixed(AppReroute(30.0), RandomExit(0))
    while sim.t < 600.0:
        sim.step(pol)
        on = sim.status == ON_LINK
        flat = sim.env_of[on] * sim.E + sim.link[on]
        cnt = torch.bincount(flat, minlength=sim.B * sim.E).float()
        assert torch.equal(cnt, sim.occ), "occupancy != vehicles on links"
        assert bool((sim.occ <= sim._storage + 1e-6).all()), "storage exceeded"
        assert bool((sim.budget >= -1e-6).all()), "outflow budget overdrawn"
    started = int((sim.dep_t < sim.t).sum())
    by_status = torch.bincount(sim.status, minlength=5)
    assert started == int(by_status[1:].sum()), (started, by_status.tolist())
    assert int(by_status[ARRIVED]) > 0


def test_gridlock_release() -> None:
    """At a demand that jams the net, forced moves keep vehicles arriving; storage only
    exceeded by forced entries."""
    g, zones, d = _setup(seeds=(4,), tph=12000.0)
    strict = MesoSim(g, d, zones, replace(CFG, stuck_time_s=math.inf)).run(ShortestPath(), 900.0)
    sim = MesoSim(g, d, zones, CFG)
    rel = sim.run(ShortestPath(), 900.0)
    assert rel["forced_moves"] > 0
    assert rel["arrived_share"][0] >= strict["arrived_share"][0]
    over = torch.clamp(sim.occ - torch.floor(sim._storage + 1e-6), min=0).sum()
    assert float(over) <= rel["forced_moves"]


def test_free_flow_single_vehicle() -> None:
    cfg = replace(CFG, signals=False)
    g, zones, _ = _setup(cfg)
    o = int(g.scc_nodes[10])
    z = 3
    from .demand import Demand

    d = Demand(
        torch.tensor([[2.5]]), torch.tensor([[o]]), torch.tensor([[z]]),
        torch.tensor([[True]]), [0],
    )
    sim = MesoSim(g, d, zones, cfg)
    pol = ShortestPath()
    sim.run(pol, 900.0)
    assert int(sim.status[0]) == ARRIVED
    # expected: free-flow shortest path; occupancy of 1 vehicle slows entry speed a little
    dist = bellman_ford(g.src, g.dst, (g.length / g.v_free).unsqueeze(0), zones, g.n_nodes)
    expect = float(dist[0, z, o])
    got = float(sim.arrive_t[0] - sim.dep_t[0])
    assert expect <= got <= expect * 1.6 + 1.0, (expect, got)


def test_capacity_respected() -> None:
    """Many vehicles from one origin: exits per link per step never exceed the budget rule."""
    cfg = replace(CFG, signals=False)
    g, zones, _ = _setup(cfg)
    from .demand import Demand

    o = int(g.scc_nodes[0])
    n = 200
    d = Demand(
        torch.zeros(1, n), torch.full((1, n), o), torch.full((1, n), 2),
        torch.ones(1, n, dtype=torch.bool), [0],
    )
    sim = MesoSim(g, d, zones, cfg)
    pol = ShortestPath()
    T = 300.0
    while sim.t < T:
        before = sim.entered.clone()
        occ_before = sim.occ.clone()
        sim.step(pol)
        # vehicles leaving a link in one step <= max(1, cap*dt) carried budget, i.e. <= ceil
        left = occ_before + (sim.entered - before) - sim.occ
        assert bool((left <= torch.clamp(sim._cap_dt, min=1.0) + 1e-6).all())
    arrived = int((sim.status == ARRIVED).sum())
    assert 0 < arrived < n or arrived == n


def test_batch_independence_and_determinism() -> None:
    g, zones, d3 = _setup(seeds=(7, 8, 9), tph=3000.0)
    _, _, d1 = _setup(seeds=(8,), tph=3000.0)
    s3 = MesoSim(g, d3, zones, CFG)
    s1 = MesoSim(g, d1, zones, CFG)
    r3 = s3.run(Mixed(AppReroute(60.0), ShortestPath()), 600.0)
    r1 = s1.run(Mixed(AppReroute(60.0), ShortestPath()), 600.0)
    assert math.isclose(r3["ttt_s"][1], r1["ttt_s"][0], rel_tol=1e-5), (r3["ttt_s"], r1["ttt_s"])
    s1b = MesoSim(g, d1, zones, CFG)
    r1b = s1b.run(Mixed(AppReroute(60.0), ShortestPath()), 600.0)
    assert r1b["ttt_s"] == r1["ttt_s"]


def test_signal_mean_wait() -> None:
    """One vehicle per env through a signalized link, departures spread over a cycle:
    the mean extra time is about red^2 / (2 cycle) (= 7.5 s for 30/60)."""
    from .demand import Demand

    g = load_graph(DEFAULT_GRAPH, CFG)
    k = int(torch.nonzero(g.sig_group >= 0)[0])
    nxt = g.out_edges[g.dst[k]]
    nxt = int(nxt[nxt >= 0][0])
    target = int(g.dst[nxt])
    zones = torch.tensor([target])
    B = 60
    d = Demand(
        torch.arange(B, dtype=torch.float).view(B, 1), torch.full((B, 1), int(g.src[k])),
        torch.zeros(B, 1, dtype=torch.long), torch.ones(B, 1, dtype=torch.bool), list(range(B)),
    )

    class Forced:
        def decide(self, sim, idx, node):
            return torch.where(sim.link[idx] < 0, torch.full_like(idx, k), torch.full_like(idx, nxt))

    res = []
    for cfg in (CFG, replace(CFG, signals=False)):
        sim = MesoSim(load_graph(DEFAULT_GRAPH, cfg), d, zones, cfg)
        sim.run(Forced(), 400.0)
        assert bool((sim.status == ARRIVED).all())
        res.append(float((sim.arrive_t - sim.dep_t).mean()))
    extra = res[0] - res[1]
    assert 4.0 < extra < 11.0, res


def main() -> None:
    torch.manual_seed(0)
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}", flush=True)
    print("MESO_TESTS_OK")


if __name__ == "__main__":
    main()
