"""Baseline routing policies for the meso simulator.

All of them see only what a real system can measure (link travel times as a
probe fleet reports them, `MesoSim.link_tt_now`), never the simulator's
internals. Distances to destination zones come from batched Bellman-Ford.

- ShortestPath: free-flow shortest path (fixed routes, no information).
- AppReroute: navigation-app behaviour. Every `refresh_s` it recomputes
  shortest paths on current link times; at each node a vehicle takes the exit
  minimising current link time + current distance to its zone (selfish).
- FixedRoute: given edge sequences (the SUMO cross-check drives the same routes).
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


def best_exit(
    g,
    node: torch.Tensor,
    cur: torch.Tensor,
    z: torch.Tensor,
    b: torch.Tensor,
    bd: torch.Tensor,
    edge_cost: torch.Tensor,
    dist: torch.Tensor,
) -> torch.Tensor:
    """argmin over exits of edge_cost[b, e] + dist[bd, z, dst(e)]; -1 if the node has no exit.

    `cur` is the link the vehicle is on (-1 at its origin), for the U-turn penalty.
    """
    cand = g.out_edges[node]  # [M, D]
    valid = cand >= 0
    c = cand.clamp(min=0)
    score = edge_cost[b.unsqueeze(1), c] + dist[bd.unsqueeze(1), z.unsqueeze(1), g.dst[c]]
    rev = g.rev[cur.clamp(min=0)]
    uturn = (cur >= 0).unsqueeze(1) & (c == rev.unsqueeze(1))
    score = score + uturn * UTURN_PENALTY
    score = torch.where(valid, score, torch.full_like(score, math.inf))
    best = torch.nan_to_num(score, posinf=1e30).argmin(1)
    out = c.gather(1, best.unsqueeze(1)).squeeze(1)
    return torch.where(valid.any(1), out, torch.full_like(out, -1))


def choose_exit(
    sim: MesoSim, idx: torch.Tensor, node: torch.Tensor, edge_cost: torch.Tensor, dist: torch.Tensor
) -> torch.Tensor:
    """best_exit for simulator vehicles. edge_cost: [B or 1, E], dist: [B or 1, Z, n]."""
    b = sim.env_of[idx] if edge_cost.shape[0] > 1 else torch.zeros_like(idx)
    bd = sim.env_of[idx] if dist.shape[0] > 1 else torch.zeros_like(idx)
    return best_exit(sim.g, node, sim.link[idx], sim.dest_zone[idx], b, bd, edge_cost, dist)


def free_flow_routes(
    g, free_tt: torch.Tensor, zones: torch.Tensor, orig: torch.Tensor, dest_zone: torch.Tensor
) -> torch.Tensor:
    """The routes ShortestPath drives, as edge sequences [M, L] padded with -1."""
    cost = free_tt.unsqueeze(0)
    dist = bellman_ford(g.src, g.dst, cost, zones, g.n_nodes)
    M = orig.numel()
    zero = torch.zeros(M, dtype=torch.long, device=orig.device)
    node = orig.clone()
    cur = torch.full_like(orig, -1)
    target = zones[dest_zone]
    steps = []
    for _ in range(g.n_nodes):
        active = node != target
        if not bool(active.any()):
            break
        e = best_exit(g, node, cur, dest_zone, zero, zero, cost, dist)
        e = torch.where(active, e, torch.full_like(e, -1))
        steps.append(e)
        moved = e >= 0
        node = torch.where(moved, g.dst[e.clamp(min=0)], node)
        cur = torch.where(moved, e, cur)
        if not bool(moved.any()):
            break
    return torch.stack(steps, 1) if steps else torch.full((M, 1), -1, device=orig.device)


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


class FixedRoute:
    """Follow given edge sequences [B*N, L] (-1 padded): for SUMO cross-checks."""

    def __init__(self, routes: torch.Tensor) -> None:
        self.routes = routes
        self.pos: torch.Tensor | None = None

    def decide(self, sim: MesoSim, idx: torch.Tensor, node: torch.Tensor) -> torch.Tensor:
        if self.pos is None:
            self.pos = torch.zeros(self.routes.shape[0], dtype=torch.long, device=self.routes.device)
        p = self.pos[idx]
        L = self.routes.shape[1]
        e = self.routes[idx, p.clamp(max=L - 1)]
        e = torch.where(p < L, e, torch.full_like(e, -1))
        self.pos[idx] = p + 1
        return e


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
