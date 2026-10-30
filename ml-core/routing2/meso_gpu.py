"""Batched mesoscopic queue simulator on GPU (PyTorch).

B independent episodes x N vehicles run as tensors. The model is a spatial
queue (MATSim QSim style) with motorbike-unit parameters:

- A vehicle entering link e at time t is ready to leave at
  t + length / v, with v = v_free * max(floor, 1 - occupancy / storage) taken at entry.
- A ready vehicle at the head of e leaves when (a) it has chosen its next link,
  (b) the light at the downstream node is green for e's phase group,
  (c) e's outflow budget (cap * dt per step, carried up to max(1, cap * dt))
  is not used up, in order of readiness, and (d) the next link has storage
  space at the start of the sub-step, in order of readiness among entrants.
  After `stuck_time_s` of waiting, (d) is waived for one vehicle per full link per
  sub-step, and only while that link holds at most one vehicle over its storage
  (gridlock release, counted as forced).
  A vehicle blocked at (d) does not block others turning elsewhere (motorbikes filter).
- A vehicle that reaches its destination node leaves the network at once.
- Entry time is max(ready time, step start), so sub-second link times do not
  round up. A vehicle can cross up to `hops_per_step` links per step.

Routing is external: when a vehicle at a node has no next link, the simulator
asks `policy.decide(sim, idx, node)` for all such vehicles at once.

Vehicle status: 0 not departed, 1 waiting at origin, 2 on a link, 3 arrived,
4 stuck (no exit at its node).
"""

from __future__ import annotations

import math
from typing import Protocol

import torch

from .demand import Demand
from .graph import MesoGraph
from .params import SimConfig

NOT_DEPARTED, WAITING, ON_LINK, ARRIVED, STUCK = 0, 1, 2, 3, 4


class Policy(Protocol):
    def decide(self, sim: MesoSim, idx: torch.Tensor, node: torch.Tensor) -> torch.Tensor:
        """Next edge per vehicle (flat index into B*N), -1 if none exists."""
        ...


def group_rank(group: torch.Tensor, order: torch.Tensor) -> torch.Tensor:
    """0-based rank of each item within its group, ascending `order`, ties by position."""
    n = group.numel()
    if n == 0:
        return group.clone()
    o = torch.argsort(order, stable=True)
    s = o[torch.argsort(group[o], stable=True)]
    gs = group[s]
    pos = torch.arange(n, device=group.device)
    start = torch.ones(n, dtype=torch.bool, device=group.device)
    start[1:] = gs[1:] != gs[:-1]
    first = torch.cummax(torch.where(start, pos, torch.zeros_like(pos)), 0).values
    rank = torch.empty_like(pos)
    rank[s] = pos - first
    return rank


class MesoSim:
    def __init__(self, g: MesoGraph, demand: Demand, zones: torch.Tensor, cfg: SimConfig):
        self.g = g
        self.cfg = cfg
        self.zones = zones
        self.dev = g.src.device
        self.B, self.N = demand.dep_t.shape
        self.E = g.n_edges
        self.demand = demand
        self.dep_t = demand.dep_t.reshape(-1).float()
        self.orig = demand.orig.reshape(-1)
        self.dest_zone = demand.dest_zone.reshape(-1)
        self.dest_node = zones[self.dest_zone]
        self.ctrl = demand.ctrl.reshape(-1)
        self.env_of = torch.arange(self.B * self.N, device=self.dev) // self.N
        self.reset()

    def reset(self) -> None:
        BN, BE = self.B * self.N, self.B * self.E
        d = self.dev
        self.t = 0.0
        self.status = torch.zeros(BN, dtype=torch.long, device=d)
        self.link = torch.full((BN,), -1, dtype=torch.long, device=d)
        self.next_edge = torch.full((BN,), -1, dtype=torch.long, device=d)
        self.t_enter = torch.zeros(BN, device=d)
        self.t_ready = torch.zeros(BN, device=d)
        self.arrive_t = torch.full((BN,), math.inf, device=d)
        self.dist_m = torch.zeros(BN, device=d)
        self.alley_m = torch.zeros(BN, device=d)
        self.occ = torch.zeros(BE, device=d)
        self.budget = torch.zeros(BE, device=d)
        self.entered = torch.zeros(BE, device=d)
        self.n_decisions = 0
        self.n_forced = 0
        self.max_occ_ratio = torch.zeros(BE, device=d)
        self._cap_dt = (self.g.cap * self.cfg.dt).repeat(self.B)
        self._budget_max = torch.clamp(self._cap_dt, min=1.0)
        self._storage = self.g.storage.repeat(self.B)

    # ------------------------------------------------------------ observables

    def occupancy(self) -> torch.Tensor:
        return self.occ.view(self.B, self.E)

    def link_tt_now(self) -> torch.Tensor:
        """[B, E] travel time a probe would report now: running + queue + mean red wait."""
        g, cfg = self.g, self.cfg
        dens = self.occupancy() / g.storage
        v = g.v_free * torch.clamp(1.0 - dens, min=cfg.speed_floor)
        tt = g.length / v
        on = self.status == ON_LINK
        waiting = on & (self.t_ready <= self.t)
        q = torch.zeros(self.B * self.E, device=self.dev)
        flat = self.env_of[waiting] * self.E + self.link[waiting]
        q.index_add_(0, flat, torch.ones_like(flat, dtype=q.dtype))
        tt = tt + q.view(self.B, self.E) / g.cap
        return tt + self.mean_red_wait()

    def mean_red_wait(self) -> torch.Tensor:
        """[E] expected red wait for a random arrival on signalized approaches."""
        cfg = self.cfg
        if not cfg.signals:
            return torch.zeros(self.E, device=self.dev)
        w = cfg.signal_red_s**2 / (2.0 * cfg.signal_cycle_s)
        return torch.where(self.g.sig_group >= 0, w, 0.0)

    def free_tt(self) -> torch.Tensor:
        return self.g.length / self.g.v_free + self.mean_red_wait()

    def _green(self, e: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        g, cfg = self.g, self.cfg
        grp = g.sig_group[e]
        phase = torch.remainder(t - g.sig_offset[e], cfg.signal_cycle_s)
        red0 = phase < cfg.signal_red_s
        return (grp < 0) | ((grp == 0) & ~red0) | ((grp == 1) & red0)

    # ------------------------------------------------------------------- step

    def step(self, policy: Policy) -> None:
        cfg = self.cfg
        t0, t1 = self.t, self.t + cfg.dt
        self.budget = torch.minimum(self.budget + self._cap_dt, self._budget_max)
        dep = (self.status == NOT_DEPARTED) & (self.dep_t < t1)
        self.status[dep] = WAITING
        for _ in range(cfg.hops_per_step):
            if not self._substep(policy, t0, t1):
                break
        self.t = t1
        self.max_occ_ratio = torch.maximum(self.max_occ_ratio, self.occ / self._storage)

    def _substep(self, policy: Policy, t0: float, t1: float) -> bool:
        g, E = self.g, self.E
        st = self.status
        e = self.link.clamp(min=0)
        ready = (st == ON_LINK) & (self.t_ready < t1)

        arr = ready & (g.dst[e] == self.dest_node)
        if bool(arr.any()):
            ai = arr.nonzero().squeeze(1)
            st[ai] = ARRIVED
            self.arrive_t[ai] = self.t_ready[ai]
            self.occ.index_add_(0, self.env_of[ai] * E + e[ai], -torch.ones(len(ai), device=self.dev))
            self.link[ai] = -1
            ready = ready & ~arr

        heads = (st == WAITING) | ready
        need = heads & (self.next_edge < 0)
        if bool(need.any()):
            ni = need.nonzero().squeeze(1)
            node = torch.where(st[ni] == WAITING, self.orig[ni], g.dst[e[ni]])
            choice = policy.decide(self, ni, node)
            self.n_decisions += int(ni.numel())
            self.next_edge[ni] = choice
            stuck = ni[choice < 0]
            if stuck.numel():
                on = stuck[st[stuck] == ON_LINK]
                self.occ.index_add_(0, self.env_of[on] * E + e[on], -torch.ones(len(on), device=self.dev))
                st[stuck] = STUCK
                heads[stuck] = False

        cand = heads & (self.next_edge >= 0)
        if self.cfg.signals:
            cand = cand & ((st != ON_LINK) | self._green(e, torch.clamp(self.t_ready, min=t0)))
        ci = cand.nonzero().squeeze(1)
        if ci.numel() == 0:
            return False

        b = self.env_of[ci]
        on_link = st[ci] == ON_LINK
        ne = self.next_edge[ci]
        tgt = b * E + ne
        src = b * E + e[ci]
        t_rdy = torch.where(on_link, self.t_ready[ci], self.dep_t[ci])

        space = torch.floor(self._storage[tgt] - self.occ[tgt] + 1e-6)
        fits = group_rank(tgt, t_rdy) < space
        forced = ~fits & ((t1 - t_rdy) > self.cfg.stuck_time_s) & (space > -1.0)
        uniq_f = self.B * E + torch.arange(len(ci), device=self.dev)
        forced = forced & (group_rank(torch.where(forced, tgt, uniq_f), t_rdy) == 0)
        ok = fits | forced
        part = ok & on_link
        uniq = self.B * E + torch.arange(len(ci), device=self.dev)
        r_src = group_rank(torch.where(part, src, uniq), t_rdy)
        ok = ok & (~on_link | (r_src < torch.floor(self.budget[src])))
        if not bool(ok.any()):
            return False

        m, tg, ne_m = ci[ok], tgt[ok], ne[ok]
        self.n_forced += int((ok & ~fits).sum())
        lm = on_link[ok]
        one = torch.ones(int(lm.sum()), device=self.dev)
        self.occ.index_add_(0, src[ok][lm], -one)
        self.budget.index_add_(0, src[ok][lm], -one)
        self.occ.index_add_(0, tg, torch.ones(len(tg), device=self.dev))
        self.entered.index_add_(0, tg, torch.ones(len(tg), device=self.dev))

        t_ent = torch.clamp(t_rdy[ok], min=t0)
        dens = torch.clamp(self.occ[tg] / self._storage[tg], max=1.0)
        v = g.v_free[ne_m] * torch.clamp(1.0 - dens, min=self.cfg.speed_floor)
        L = g.length[ne_m]
        self.t_enter[m] = t_ent
        self.t_ready[m] = t_ent + L / v
        self.link[m] = ne_m
        self.next_edge[m] = -1
        st[m] = ON_LINK
        self.dist_m[m] += L
        self.alley_m[m] += L * g.is_alley[ne_m]
        return True

    def run(self, policy: Policy, horizon_s: float | None = None) -> dict:
        T = self.cfg.horizon_s if horizon_s is None else horizon_s
        while self.t < T - 1e-9:
            self.step(policy)
        return self.summary()

    # --------------------------------------------------------------- metrics

    def per_vehicle_tt(self) -> torch.Tensor:
        """[B*N] experienced time (arrival or now, minus departure); nan if not departed."""
        started = self.dep_t < self.t
        end = torch.where(self.status == ARRIVED, self.arrive_t, torch.full_like(self.arrive_t, self.t))
        return torch.where(started, end - self.dep_t, torch.full_like(end, math.nan))

    def summary(self) -> dict:
        tt = self.per_vehicle_tt().view(self.B, self.N)
        started = ~torch.isnan(tt)
        arrived = (self.status == ARRIVED).view(self.B, self.N)
        ctrl = self.ctrl.view(self.B, self.N)

        def env_mean(x: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
            return torch.where(mask, x, 0.0).sum(1) / mask.sum(1).clamp(min=1)

        tt0 = torch.nan_to_num(tt)
        dist = self.dist_m.view(self.B, self.N)
        alley = self.alley_m.view(self.B, self.N)
        return {
            "t": self.t,
            "ttt_s": tt0.sum(1).tolist(),
            "mean_tt_started_s": env_mean(tt0, started).tolist(),
            "mean_tt_arrived_s": env_mean(tt0, arrived).tolist(),
            "mean_tt_ctrl_s": env_mean(tt0, started & ctrl).tolist(),
            "mean_tt_bg_s": env_mean(tt0, started & ~ctrl).tolist(),
            "arrived_share": (arrived.sum(1) / started.sum(1).clamp(min=1)).tolist(),
            "stuck": (self.status == STUCK).view(self.B, self.N).sum(1).tolist(),
            "alley_dist_share": (alley.sum(1) / dist.sum(1).clamp(min=1e-9)).tolist(),
            "max_alley_occ_ratio": self.max_occ_ratio.view(self.B, self.E)[:, self.g.is_alley]
            .max(1)
            .values.tolist(),
            "decisions": self.n_decisions,
            "forced_moves": self.n_forced,
        }
