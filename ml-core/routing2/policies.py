"""Baseline routing policies for the meso simulator.

All of them see only what a real system can measure (link travel times as a
probe fleet reports them, `MesoSim.link_tt_now`), never the simulator's
internals. Distances to destination zones come from batched Bellman-Ford.

- ShortestPath: free-flow shortest path (fixed routes, no information).
- AppReroute: navigation-app behaviour. Every `refresh_s` it recomputes
  shortest paths on current link times; at each node a vehicle takes the exit
  minimising current link time + current distance to its zone (selfish).
- RandomExit: uniform random exit, for tests only.
- Mixed: one policy for the controlled fleet, another for the rest.

A U-turn onto the reverse of the current link is taken only when no other exit exists.
"""

from __future__ import annotations

import math

import torch

from .meso_gpu import MesoSim

UTURN_PENALTY = 1.0e6


def bellman_ford(
    src: torch.Tensor, dst: torch.Tensor, cost: torch.Tensor, zones: torch.Tensor, n_nodes: int
) -> torch.Tensor:
    """Shortest time to each zone. cost [B, E] -> dist [B, Z, n]."""
    B, E = cost.shape
    Z = zones.numel()
    D = torch.full((B, Z, n_nodes), math.inf, device=cost.device)
    D[:, torch.arange(Z, device=cost.device), zones] = 0.0
    idx = src.view(1, 1, E).expand(B, Z, E)
    c = cost.view(B, 1, E)
    for it in range(n_nodes):
        via = c + D[:, :, dst]
        nd = D.scatter_reduce(2, idx, via, reduce="amin", include_self=True)
        if it % 8 == 7 and torch.equal(nd, D):
            break
        D = nd
    return D


def choose_exit(
    sim: MesoSim, idx: torch.Tensor, node: torch.Tensor, edge_cost: torch.Tensor, dist: torch.Tensor
) -> torch.Tensor:
    """argmin over exits of edge_cost[b, e] + dist[b, zone, dst(e)]; -1 if the node has no exit.

    edge_cost: [B or 1, E], dist: [B or 1, Z, n].
    """
    g = sim.g
    cand = g.out_edges[node]  # [M, D]
    valid = cand >= 0
    c = cand.clamp(min=0)
    b = sim.env_of[idx] if edge_cost.shape[0] > 1 else torch.zeros_like(idx)
    bd = sim.env_of[idx] if dist.shape[0] > 1 else torch.zeros_like(idx)
    z = sim.dest_zone[idx]
    score = edge_cost[b.unsqueeze(1), c] + dist[bd.unsqueeze(1), z.unsqueeze(1), g.dst[c]]
    cur = sim.link[idx]
    rev = g.rev[cur.clamp(min=0)]
    uturn = (cur >= 0).unsqueeze(1) & (c == rev.unsqueeze(1))
    score = score + uturn * UTURN_PENALTY
    score = torch.where(valid, score, torch.full_like(score, math.inf))
    best = torch.nan_to_num(score, posinf=1e30).argmin(1)
    out = c.gather(1, best.unsqueeze(1)).squeeze(1)
    return torch.where(valid.any(1), out, torch.full_like(out, -1))


class ShortestPath:
    def __init__(self) -> None:
        self._cost: torch.Tensor | None = None
        self._dist: torch.Tensor | None = None

    def decide(self, sim: MesoSim, idx: torch.Tensor, node: torch.Tensor) -> torch.Tensor:
        if self._dist is None:
            g = sim.g
            self._cost = sim.free_tt().unsqueeze(0)
            self._dist = bellman_ford(g.src, g.dst, self._cost, sim.zones, g.n_nodes)
        return choose_exit(sim, idx, node, self._cost, self._dist)


class AppReroute:
    def __init__(self, refresh_s: float = 60.0) -> None:
        self.refresh_s = refresh_s
        self._t = -math.inf
        self._cost: torch.Tensor | None = None
        self._dist: torch.Tensor | None = None

    def decide(self, sim: MesoSim, idx: torch.Tensor, node: torch.Tensor) -> torch.Tensor:
        if sim.t - self._t >= self.refresh_s or self._dist is None:
            g = sim.g
            self._cost = sim.link_tt_now()
            self._dist = bellman_ford(g.src, g.dst, self._cost, sim.zones, g.n_nodes)
            self._t = sim.t
        return choose_exit(sim, idx, node, self._cost, self._dist)


class RandomExit:
    def __init__(self, seed: int = 0) -> None:
        self.gen: torch.Generator | None = None
        self.seed = seed

    def decide(self, sim: MesoSim, idx: torch.Tensor, node: torch.Tensor) -> torch.Tensor:
        if self.gen is None:
            self.gen = torch.Generator(device=sim.dev).manual_seed(self.seed)
        g = sim.g
        cand = g.out_edges[node]
        valid = (cand >= 0).float()
        cur = sim.link[idx]
        rev = g.rev[cur.clamp(min=0)]
        uturn = (cur >= 0).unsqueeze(1) & (cand == rev.unsqueeze(1))
        w = valid * torch.where(uturn, 1e-6, 1.0)
        has = valid.sum(1) > 0
        w = torch.where(has.unsqueeze(1), w, torch.ones_like(w))
        pick = torch.multinomial(w, 1, generator=self.gen).squeeze(1)
        out = cand.gather(1, pick.unsqueeze(1)).squeeze(1)
        return torch.where(has, out, torch.full_like(out, -1))


class Mixed:
    def __init__(self, ctrl_policy, bg_policy) -> None:
        self.ctrl_policy = ctrl_policy
        self.bg_policy = bg_policy

    def decide(self, sim: MesoSim, idx: torch.Tensor, node: torch.Tensor) -> torch.Tensor:
        out = torch.empty_like(idx)
        c = sim.ctrl[idx]
        if bool(c.any()):
            out[c] = self.ctrl_policy.decide(sim, idx[c], node[c])
        if bool((~c).any()):
            out[~c] = self.bg_policy.decide(sim, idx[~c], node[~c])
        return out
