"""Open-system demand: trips spread over the horizon, to destination zones.

Placeholder until P1.4 (OSM POI + WorldPop gravity): origins are nodes of the
largest SCC weighted by incident alley length (a population proxy), destinations
are `n_zones` zone nodes picked by farthest-point sampling, departures are a
Poisson process (uniform order statistics for a fixed count).

A synthetic peak (hot_share > 0, peak_sd > 0): a share of the trips goes to or leaves the zones
nearest the middle of the network (school, market, bridge), and departures bunch around the middle
of the window. These numbers are invented, not measured.

Each env b uses its own CPU generator seeded with seeds[b], so an env's demand
is the same whatever the batch it runs in, and every controller sees the same
trips for the same seed.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from .graph import MesoGraph


@dataclass
class Demand:
    dep_t: torch.Tensor  # [B, N] s, sorted per env
    orig: torch.Tensor  # [B, N] node index
    dest_zone: torch.Tensor  # [B, N] index into zones
    ctrl: torch.Tensor  # [B, N] bool, vehicle belongs to the controlled fleet
    seeds: list[int]

    def to(self, device: torch.device | str) -> Demand:
        return Demand(
            self.dep_t.to(device), self.orig.to(device), self.dest_zone.to(device),
            self.ctrl.to(device), self.seeds,
        )


def pick_zones(g: MesoGraph, n_zones: int, seed: int = 0) -> torch.Tensor:
    """Farthest-point sampling over SCC nodes (deterministic for a seed).

    Distances in float64 on centred coordinates: node_xy is ~1e7 m, where float32
    cdist (matmul form) is off by kilometres. Before 2026-11-01 this picked 3
    distinct nodes out of 32 zones; every routing2 result before then used that.
    """
    if g.zone_nodes is not None:  # designed zones stored with the graph (routing2.design_od)
        if n_zones > len(g.zone_nodes):
            raise ValueError(f"graph has {len(g.zone_nodes)} designed zones, {n_zones} asked")
        return g.zone_nodes[:n_zones].to(g.src.device)
    gen = torch.Generator().manual_seed(seed)
    cand = g.scc_nodes.cpu()
    xy = g.node_xy.cpu()[cand].double()
    xy = xy - xy.mean(0)
    first = int(torch.randint(len(cand), (1,), generator=gen))
    chosen = [first]
    d = (xy - xy[first]).norm(dim=1)
    for _ in range(n_zones - 1):
        k = int(torch.argmax(d))
        chosen.append(k)
        d = torch.minimum(d, (xy - xy[k]).norm(dim=1))
    return cand[torch.tensor(chosen)].to(g.src.device)


def hot_zone_index(g: MesoGraph, zones: torch.Tensor, n_hot: int) -> torch.Tensor:
    """Indices into `zones` of the n_hot zones nearest the middle of the network."""
    xy = g.node_xy.cpu().double()
    d = (xy[zones.cpu()] - xy[g.scc_nodes.cpu()].mean(0)).norm(dim=1)
    return torch.argsort(d)[:n_hot]


def origin_weights(g: MesoGraph) -> torch.Tensor:
    """Per SCC node: half the length of incident alley edges (+1 m so roads can emit)."""
    w = torch.ones(g.n_nodes)
    al = (g.length * g.is_alley).cpu()
    w.index_add_(0, g.src.cpu(), 0.5 * al)
    w.index_add_(0, g.dst.cpu(), 0.5 * al)
    return w[g.scc_nodes.cpu()]


def make_demand(
    g: MesoGraph,
    zones: torch.Tensor,
    seeds: list[int],
    trips_per_hour: float,
    horizon_s: float,
    penetration: float,
    depart_window_s: float | None = None,
    hot_share: float = 0.0,
    n_hot: int = 4,
    inbound_share: float = 0.7,
    peak_sd: float = 0.0,
) -> Demand:
    """`depart_window_s` (default: the horizon) bounds the departure times. `peak_sd` is the spread
    of departures as a share of the window (0 = uniform). `inbound_share` of the hot trips go to a
    hot zone, the others leave one."""
    window = horizon_s if depart_window_s is None else depart_window_s
    n = max(1, int(round(trips_per_hour * window / 3600.0)))
    cand = g.scc_nodes.cpu()
    w = origin_weights(g)
    zc = zones.cpu()
    dep, org, dz, ctrl = [], [], [], []
    for s in seeds:
        gen = torch.Generator().manual_seed(int(s))
        if peak_sd > 0:
            u = (0.5 + peak_sd * torch.randn(n, generator=gen)).clamp(0.0, 1.0 - 1e-6)
        else:
            u = torch.rand(n, generator=gen)
        t = torch.sort(u * window).values
        o = cand[torch.multinomial(w, n, replacement=True, generator=gen)]
        z = torch.randint(len(zc), (n,), generator=gen)
        if hot_share > 0:
            hot = hot_zone_index(g, zones, n_hot)
            pick = hot[torch.randint(len(hot), (n,), generator=gen)]
            is_hot = torch.rand(n, generator=gen) < hot_share
            inbound = torch.rand(n, generator=gen) < inbound_share
            z = torch.where(is_hot & inbound, pick, z)
            o = torch.where(is_hot & ~inbound, zc[pick], o)
        same = zc[z] == o
        z = torch.where(same, (z + 1) % len(zc), z)
        c = torch.rand(n, generator=gen) < penetration
        dep.append(t)
        org.append(o)
        dz.append(z)
        ctrl.append(c)
    dev = g.src.device
    return Demand(
        torch.stack(dep).to(dev), torch.stack(org).to(dev), torch.stack(dz).to(dev),
        torch.stack(ctrl).to(dev), list(seeds),
    )
