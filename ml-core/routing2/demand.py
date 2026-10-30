"""Open-system demand: trips spread over the horizon, to destination zones.

Placeholder until P1.4 (OSM POI + WorldPop gravity): origins are nodes of the
largest SCC weighted by incident alley length (a population proxy), destinations
are `n_zones` zone nodes picked by farthest-point sampling, departures are a
Poisson process (uniform order statistics for a fixed count).

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
    """Farthest-point sampling over SCC nodes (deterministic for a seed)."""
    gen = torch.Generator().manual_seed(seed)
    cand = g.scc_nodes.cpu()
    xy = g.node_xy.cpu()[cand]
    first = int(torch.randint(len(cand), (1,), generator=gen))
    chosen = [first]
    d = torch.cdist(xy, xy[first : first + 1]).squeeze(1)
    for _ in range(n_zones - 1):
        k = int(torch.argmax(d))
        chosen.append(k)
        d = torch.minimum(d, torch.cdist(xy, xy[k : k + 1]).squeeze(1))
    return cand[torch.tensor(chosen)].to(g.src.device)


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
) -> Demand:
    """`depart_window_s` (default: the horizon) bounds the departure times."""
    window = horizon_s if depart_window_s is None else depart_window_s
    n = max(1, int(round(trips_per_hour * window / 3600.0)))
    cand = g.scc_nodes.cpu()
    w = origin_weights(g)
    zc = zones.cpu()
    dep, org, dz, ctrl = [], [], [], []
    for s in seeds:
        gen = torch.Generator().manual_seed(int(s))
        t = torch.sort(torch.rand(n, generator=gen) * window).values
        o = cand[torch.multinomial(w, n, replacement=True, generator=gen)]
        z = torch.randint(len(zc), (n,), generator=gen)
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
