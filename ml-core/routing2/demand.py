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
    # per env: car trips (depart s, entry node, exit node), routed by SUMO on roads cars may use; never
    # controlled and not counted in the objective (the objective is over motorcycle trips)
    cars: list[list[tuple[float, int, int]]] | None = None

    def to(self, device: torch.device | str) -> Demand:
        return Demand(
            self.dep_t.to(device), self.orig.to(device), self.dest_zone.to(device),
            self.ctrl.to(device), self.seeds, self.cars,
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


SIDES = ("E", "N", "W", "S")


def make_demand_v2(
    g: MesoGraph,
    zones: torch.Tensor,
    seeds: list[int],
    horizon_s: float,
    penetration: float,
    internal_tph: float,
    gate_tph: tuple[float, float, float, float],
    through_share: float,
    car_share: float,
    hot_share: float = 0.0,
    n_hot: int = 4,
) -> Demand:
    """Demand with traffic from other districts (audit D1, D3, V1), departures uniform over the horizon.

    Per hour: `internal_tph` motorcycle trips from alley-weighted core nodes to internal zones; for each
    side (E, N, W, S) `gate_tph[k]` vehicles enter through that side's gates, a `through_share` of them
    leave through an exit of another side and the rest end at an internal zone; the same number leave
    from the core through that side's exits (the peak is not assumed one-way). A `car_share` of the
    side flows are cars (entry and exit gates only, routed by SUMO), the rest motorcycles. Fleet
    vehicles (`penetration`) are drawn among motorcycle trips. All numbers are to be calibrated.
    """
    if g.gate_in is None or g.zone_exit is None:
        raise ValueError("graph has no gates or exit zones: build it with data_fusion.build_quan4_full v2")
    cand = g.scc_nodes.cpu()
    w = origin_weights(g)
    zx = g.zone_exit.cpu()[: len(zones)]
    internal = torch.nonzero(zx < 0).squeeze(1)
    exits_by = [torch.nonzero(zx == k).squeeze(1) for k in range(4)]
    gin, gside = g.gate_in.cpu(), g.gate_in_side.cpu()
    gin_by = [gin[gside == k] for k in range(4)]
    zc = zones.cpu()
    hot = hot_zone_index(g, zones[internal.to(zones.device)], n_hot) if hot_share > 0 else None
    dep, org, dz, ctrl, cars = [], [], [], [], []
    for s in seeds:
        gen = torch.Generator().manual_seed(int(s))

        def count(tph: float) -> int:
            return int(torch.poisson(torch.tensor(tph * horizon_s / 3600.0), generator=gen))

        def pick(t: torch.Tensor, n: int) -> torch.Tensor:
            return t[torch.randint(len(t), (n,), generator=gen)]

        o_l, z_l, c_l = [], [], []
        n = count(internal_tph)
        o_l.append(cand[torch.multinomial(w, n, replacement=True, generator=gen)])
        zi = pick(internal, n)
        if hot is not None:
            is_hot = torch.rand(n, generator=gen) < hot_share
            zi = torch.where(is_hot, internal[pick(hot, n)], zi)
        z_l.append(zi)
        car_list: list[tuple[float, int, int]] = []
        for k in range(4):
            if gate_tph[k] <= 0 or len(gin_by[k]) == 0:
                continue
            other = torch.cat([exits_by[j] for j in range(4) if j != k])
            for inbound in (True, False):
                m = count(gate_tph[k])
                # cars only enter through gates and leave through a gate of another side (they cannot
                # reach alley zones); outbound trips from the core are motorcycles. An assumption.
                is_car = (torch.rand(m, generator=gen) < car_share) & torch.tensor(inbound).expand(m)
                thr = torch.rand(m, generator=gen) < through_share if inbound else torch.zeros(m, dtype=torch.bool)
                if inbound:
                    o = pick(gin_by[k], m)
                    z = torch.where(thr, pick(other, m) if len(other) else pick(internal, m), pick(internal, m))
                else:
                    if len(exits_by[k]) == 0:
                        continue
                    o = cand[torch.multinomial(w, m, replacement=True, generator=gen)]
                    z = pick(exits_by[k], m)
                t_car = torch.rand(int(is_car.sum()), generator=gen) * horizon_s
                for ti, oi, zi_ in zip(t_car.tolist(), o[is_car].tolist(), z[is_car].tolist()):
                    exit_node = int(zc[zi_]) if int(zx[zi_]) >= 0 else int(zc[pick(other, 1)]) if len(other) else -1
                    if exit_node >= 0:
                        car_list.append((ti, int(oi), exit_node))
                o_l.append(o[~is_car])
                z_l.append(z[~is_car])
        o = torch.cat(o_l)
        z = torch.cat(z_l)
        same = zc[z] == o
        z = torch.where(same, internal[(torch.searchsorted(internal, z) + 1) % len(internal)], z)
        t = torch.rand(len(o), generator=gen) * horizon_s
        order = torch.argsort(t)
        dep.append(t[order])
        org.append(o[order])
        dz.append(z[order])
        ctrl.append(torch.rand(len(o), generator=gen) < penetration)
        cars.append(sorted(car_list))
    L = max(len(x) for x in dep)
    pad = lambda xs, v: torch.stack([torch.cat([x, torch.full((L - len(x),), v, dtype=x.dtype)]) for x in xs])  # noqa: E731
    if any(len(x) != L for x in dep):
        raise ValueError("make_demand_v2 builds one env per call when counts differ; pass one seed")
    dev = g.src.device
    return Demand(pad(dep, 0.0).to(dev), pad(org, 0).to(dev), pad(dz, 0).to(dev), pad(ctrl, False).to(dev),
                  list(seeds), cars)
