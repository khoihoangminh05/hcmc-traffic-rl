"""Hard scenarios found by a heuristic: a burst of trips onto a link that really jams, with a real way around.

Fleets are small over a district but can gather at one place at one time. Mining, on tuning seeds only:
1. Run free flow and measure where vehicles really stand (link_wait), not where routes overlap.
2. A hotspot is a jammed link with origin-destination pairs whose free-flow route uses it and whose
   way around it is short and carries little waiting (mine_hotspots).
3. Keep a hotspot only if an oracle that sends a share of the fleet around it gains on the best simple
   controller (scripts in the run directory). Without that, no controller could win there.
These scenarios are chosen to be hard for simple controllers, so results must be reported as a stress
set, beside ordinary demand. Every controller gets the same trips on a seed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import torch

from .demand import Demand


@dataclass
class Hotspot:
    link: int  # the link that jams
    pairs: list[list[int]]  # [origin node, zone index] with a route through it and a short way around
    detour: float  # mean free-flow time around / through
    wait_s: float  # vehicle-seconds standing on it under free flow, per episode
    spare: float  # waiting along the ways around, per link, relative to the network's top links


def mine_hotspots(env, link_wait: torch.Tensor, k: int = 6, top: int = 60, max_detour: float = 1.4, min_pairs: int = 30,
                  reach_m: float = 500.0, min_apart_m: float = 200.0) -> list[Hotspot]:
    """link_wait [E]: mean vehicle-seconds standing per link. Best first: much waiting, a short way
    around that is itself free. Pure graph search on measured waits; no controller is scored here."""
    g = env.g
    xy = g.node_xy.cpu().double()
    nodes = g.scc_nodes.cpu()
    ref = float(link_wait.topk(min(top, len(link_wait))).values.mean()) + 1e-6
    scored: list[tuple[float, Hotspot]] = []
    for b in link_wait.topk(min(top, len(link_wait))).indices.tolist():
        near = nodes[(xy[nodes] - xy[int(env.src[b])]).norm(dim=1) <= reach_m].tolist()
        cost = env.ff_edge.clone()
        cost[b] = 1e6
        around = env._time_to_zones(cost)
        pairs, ratios, spare = [], [], []
        for n in near:
            first = env.candidates(n, -1)
            if not first:
                continue
            for z in range(len(env.zones)):
                if int(env.zones[z]) == n:
                    continue
                route = env.free_flow_route(z, n)
                if b not in route:
                    continue
                direct = float(env.ff_edge[torch.tensor(route)].sum())
                f = min(first, key=lambda e: float(cost[e] + around[z, e]))
                alt = float(cost[f] + around[z, f])
                if alt > max_detour * max(direct, 1.0):
                    continue
                pairs.append([n, z])
                ratios.append(alt / max(direct, 1.0))
                spare.append(_path_wait(env, around, cost, f, z, link_wait, set(route)))
        if len(pairs) < min_pairs:
            continue
        free = 1.0 / (1.0 + sum(spare) / len(spare) / ref)
        h = Hotspot(b, pairs, sum(ratios) / len(ratios), float(link_wait[b]), free)
        scored.append((float(link_wait[b]) * free / h.detour, h))
    scored.sort(key=lambda x: -x[0])
    out: list[Hotspot] = []
    for _, h in scored:
        if all(float((xy[int(env.src[h.link])] - xy[int(env.src[o.link])]).norm()) >= min_apart_m for o in out):
            out.append(h)
        if len(out) == k:
            break
    return out


def _path_wait(env, around, cost, first: int, z: int, link_wait: torch.Tensor, skip: set[int]) -> float:
    """Largest waiting on a link of the way around that the direct route does not share."""
    target, cur, worst = int(env.zones[z]), first, float(link_wait[first]) if first not in skip else 0.0
    for _ in range(env.g.n_edges):
        if int(env.dst[cur]) == target or not env.succ[cur]:
            break
        cur = min(env.succ[cur], key=lambda f: float(cost[f] + around[z, f]))
        if cur not in skip:
            worst = max(worst, float(link_wait[cur]))
    return worst


def save_hotspots(path: Path, spots: list[Hotspot]) -> None:
    path.write_text(json.dumps([asdict(h) for h in spots]), encoding="utf-8")


def load_hotspots(path: str | Path) -> list[Hotspot]:
    return [Hotspot(**x) for x in json.loads(Path(path).read_text(encoding="utf-8"))]


def hotspot_of(spots: list[Hotspot], seed: int) -> Hotspot:
    return spots[int(torch.randint(len(spots), (1,), generator=torch.Generator().manual_seed(int(seed) + 7919)))]


def add_burst(d: Demand, spot: Hotspot, seed: int, n: int, fleet_share: float, sd_s: float = 45.0,
              window: tuple[float, float] = (200.0, 500.0)) -> Demand:
    """Demand d (one env) plus n trips bunched in time onto this hotspot's pairs, from the seed."""
    gen = torch.Generator().manual_seed(int(seed) + 104729)
    t0 = window[0] + float(torch.rand(1, generator=gen)) * (window[1] - window[0])
    dep = (t0 + sd_s * torch.randn(n, generator=gen)).clamp(min=0.0)
    p = torch.tensor(spot.pairs)[torch.randint(len(spot.pairs), (n,), generator=gen)]
    ctrl = torch.rand(n, generator=gen) < fleet_share
    t = torch.cat([d.dep_t[0].cpu(), dep])
    order = torch.argsort(t)
    pick = lambda old, new: torch.cat([old[0].cpu(), new])[order].unsqueeze(0)  # noqa: E731
    return Demand(t[order].unsqueeze(0), pick(d.orig, p[:, 0]), pick(d.dest_zone, p[:, 1]), pick(d.ctrl, ctrl), d.seeds)
