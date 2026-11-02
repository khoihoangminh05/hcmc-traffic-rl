"""SUMO routing environment for MARL (libsumo; one SUMO instance per process).

Vehicles are motorbikes on the v4 net (routing2.sumo_net), demand from
routing2.demand (same zones and trips as the meso). A share `penetration` of the
trips is the controlled fleet; the rest is background traffic on free-flow routes.

A controlled vehicle decides its next link at every node (next-hop routing):
- at its origin, when it departs (it is inserted on the chosen first link);
- each time it enters a new link e, for the exit at e's downstream node, unless that
  node is its destination.
After a decision the vehicle's SUMO route is [current link, chosen exit] + the
free-flow shortest completion, so SUMO always holds a valid route; the next
decision replaces the completion.

Policies see only what a real system measures: per candidate exit its free-flow
time, SUMO's current link travel time estimate (edge.getTraveltime, from the last
step's mean speed, i.e. what a probe fleet reports), the vehicle count on the link,
and the free-flow time from the exit's end to the destination. No SUMO internals.

`run(policy)` plays one episode and returns, per decision, the request, the chosen
index and the time to the vehicle's next decision (or arrival / horizon). The reward
of a decision is minus that time, so a vehicle's return is minus its own travel time;
system objectives (total travel time) are summed by the trainer.

    python -u -m routing2.bench_sumo   # speed and sanity check
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import torch

from .demand import Demand
from .graph import MesoGraph
from .sumo_check import MOTO_VTYPE
from .sumo_net import sumo_binary

N_FEAT = 5  # per candidate exit


def read_connections(net: Path, e_of: dict[str, int]) -> tuple[torch.Tensor, torch.Tensor]:
    """(from, to) link indices of every non-internal connection in a SUMO net."""
    import xml.etree.ElementTree as ET

    pairs = set()
    for _, el in ET.iterparse(net, events=("end",)):
        if el.tag == "connection":
            a, b = el.get("from", ""), el.get("to", "")
            if a in e_of and b in e_of:
                pairs.add((e_of[a], e_of[b]))
        el.clear()
    p = sorted(pairs)
    return torch.tensor([x for x, _ in p], dtype=torch.long), torch.tensor([y for _, y in p], dtype=torch.long)


def _sumo():
    try:
        import libsumo  # type: ignore[import-not-found]

        return libsumo, True
    except ImportError:  # no libsumo wheel for this Python (Windows 3.13): slower TraCI
        import traci  # type: ignore[import-not-found]

        return traci, False


@dataclass
class SumoEnvConfig:
    net: Path
    horizon_s: float = 1800.0
    step_s: float = 0.5
    lateral_m: float = 0.8
    teleport_s: float = 180.0
    sumo_seed: int = 1
    work_dir: Path = Path("artifacts/out/quan4/routing2/sumo_env_work")
    # > 0: every this many seconds read all link times (EMA) and recompute time-to-zone, as a
    # navigation app does from probe speeds. Fills Request.live_cost. 0 = off.
    live_every_s: float = 0.0
    live_alpha: float = 0.5


@dataclass
class Request:
    """Decisions due now: one row per controlled vehicle."""

    vid: list[str]
    t: float
    node: torch.Tensor  # [M]
    cand: torch.Tensor  # [M, D] candidate exit links, -1 padded
    feat: torch.Tensor  # [M, D, N_FEAT]
    dest_zone: torch.Tensor  # [M]
    live_cost: torch.Tensor | None = None  # [M, D] live link time + live time to the zone (inf = padding)


class SumoPolicy(Protocol):
    def act(self, req: Request) -> torch.Tensor:
        """Chosen candidate index per row [M]."""
        ...


@dataclass
class Episode:
    decisions: list[dict] = field(default_factory=list)
    ttt_s: float = 0.0
    ttt_ctrl_s: float = 0.0
    n_trips: int = 0
    n_ctrl: int = 0
    arrived: int = 0
    arrived_ctrl: int = 0
    teleports: int = 0
    wall_s: float = 0.0
    n_decisions: int = 0


class SumoRoutingEnv:
    def __init__(self, g: MesoGraph, zones: torch.Tensor, cfg: SumoEnvConfig):
        """cfg.net must exist (routing2.sumo_net.build_net)."""
        self.g, self.zones, self.cfg = g, zones.cpu(), cfg
        self.eid = list(g.edge_ids)
        self.e_of = {e: i for i, e in enumerate(self.eid)}
        self.src, self.dst = g.src.cpu(), g.dst.cpu()
        self.length = g.length.cpu()
        self.ff_edge = (g.length / g.v_free).cpu()
        self.out_edges = g.out_edges.cpu()
        self.rev = g.rev.cpu()
        # SUMO connections (turns netconvert allows; e.g. many U-turns are not)
        frm, to = read_connections(cfg.net, self.e_of)
        self.succ: list[list[int]] = [[] for _ in range(g.n_edges)]
        for a, c in zip(frm.tolist(), to.tolist()):
            self.succ[a].append(c)
        # Dz[z, e]: free-flow time from the end of link e to zone z over connected links
        Z = len(self.zones)
        E = g.n_edges
        self.frm, self.to = frm, to
        self._at = self.dst.unsqueeze(0) == self.zones.unsqueeze(1)
        self.Dz = self._time_to_zones(self.ff_edge)
        self.live_tt = self.ff_edge.clone()
        self.live_D = self.Dz.clone()
        self.Dmax = max(max((len(x) for x in self.succ), default=1), self.out_edges.shape[1])
        self._path_cache: dict[tuple[int, int], list[int]] = {}

    def _time_to_zones(self, cost: torch.Tensor) -> torch.Tensor:
        """[Z, E] time from the end of each link to each zone over connected links."""
        Z, E = len(self.zones), self.g.n_edges
        D = torch.full((Z, E), math.inf, dtype=torch.float64)
        D[self._at] = 0.0
        c = cost.double()
        idx = self.frm.unsqueeze(0).expand(Z, -1)
        for _ in range(E):
            nd = D.scatter_reduce(1, idx, c[self.to].unsqueeze(0) + D[:, self.to], reduce="amin", include_self=True)
            nd[self._at] = 0.0
            if torch.equal(nd, D):
                break
            D = nd
        return D.float()

    def _refresh_live(self) -> None:
        ed = self.sumo.edge
        now = self.live_tt.clone()
        for i, eid in enumerate(self.eid):
            tt = ed.getTraveltime(eid)
            ff = float(self.ff_edge[i])
            now[i] = ff if not math.isfinite(tt) or tt <= 0 or tt > 1e5 else max(tt, 0.5 * ff)
        a = self.cfg.live_alpha
        self.live_tt = (1 - a) * self.live_tt + a * now
        self.live_D = self._time_to_zones(self.live_tt)

    def live_path(self, z: int, e: int) -> list[int]:
        """Connected links after e towards zone z on the current live times."""
        target = int(self.zones[z])
        path, cur = [], e
        for _ in range(self.g.n_edges):
            if int(self.dst[cur]) == target:
                break
            cs = self.succ[cur]
            if not cs:
                break
            nx = min(cs, key=lambda f: float(self.live_tt[f]) + float(self.live_D[z, f]))
            if not math.isfinite(float(self.live_D[z, nx])):
                break
            path.append(nx)
            cur = nx
        return path

    # ----------------------------------------------------------- routes

    def _best(self, z: int, cands: list[int]) -> int:
        """Candidate with the least free-flow time to zone z (-1 if none reaches it)."""
        best, bv = -1, math.inf
        for e in cands:
            v = float(self.ff_edge[e]) + float(self.Dz[z, e])
            if v < bv:
                best, bv = e, v
        return best

    def completion(self, z: int, e: int) -> list[int]:
        """Free-flow shortest connected links after link e to zone z ([] if e ends there)."""
        key = (z, e)
        if key in self._path_cache:
            return self._path_cache[key]
        target = int(self.zones[z])
        path, cur = [], e
        for _ in range(self.g.n_edges):
            if int(self.dst[cur]) == target:
                break
            nx = self._best(z, self.succ[cur])
            if nx < 0:
                break
            path.append(nx)
            cur = nx
        self._path_cache[key] = path
        return path

    def free_flow_route(self, z: int, node: int) -> list[int]:
        first = self._best(z, self.candidates(node, -1))
        return [] if first < 0 else [first] + self.completion(z, first)

    def candidates(self, node: int, cur: int) -> list[int]:
        """Exits a vehicle may take: SUMO-connected successors of cur that can reach a zone."""
        if cur < 0:
            out = [int(e) for e in self.out_edges[node].tolist() if e >= 0]
        else:
            out = list(self.succ[cur])
        return out

    # ----------------------------------------------------------- episode

    def _start(self, rou: Path) -> None:
        cfg = self.cfg
        self.sumo.start([
            sumo_binary("sumo"), "-n", str(cfg.net), "-r", str(rou),
            "--step-length", str(cfg.step_s), "--lateral-resolution", str(cfg.lateral_m),
            "--time-to-teleport", str(cfg.teleport_s), "--no-step-log", "true",
            "--no-warnings", "true", "--end", str(cfg.horizon_s), "--seed", str(cfg.sumo_seed),
        ])

    def _features(self, node: int, cand: list[int], z: int) -> list[list[float]]:
        ed = self.sumo.edge
        rows = []
        for e in cand:
            eid = self.eid[e]
            tt = ed.getTraveltime(eid)
            ff = float(self.ff_edge[e])
            if not math.isfinite(tt) or tt <= 0 or tt > 1e5:
                tt = ff
            rows.append([ff, tt, float(ed.getLastStepVehicleNumber(eid)),
                         float(self.Dz[z, e]), float(self.length[e])])
        return rows

    def run(self, demand: Demand, b: int, policy: SumoPolicy | None, record: bool = True) -> Episode:
        """One episode for env b of `demand` (its controlled flags pick the fleet)."""
        cfg = self.cfg
        self.sumo, self.is_lib = _sumo()
        t0 = time.perf_counter()
        dep = demand.dep_t[b].cpu()
        orig = demand.orig[b].cpu()
        dz = demand.dest_zone[b].cpu()
        ctrl = demand.ctrl[b].cpu() if policy is not None else torch.zeros_like(demand.ctrl[b].cpu())
        N = dep.numel()
        cfg.work_dir.mkdir(parents=True, exist_ok=True)
        rou = cfg.work_dir / f"bg_{id(self)}_{b}.rou.xml"
        rt = [self.free_flow_route(int(dz[i]), int(orig[i])) for i in range(N)]
        order = torch.argsort(dep).tolist()
        pending = []  # controlled trips, by departure time
        with rou.open("w", encoding="utf-8") as f:
            f.write("<routes>\n  " + MOTO_VTYPE + "\n")
            for i in order:
                r = [self.eid[e] for e in rt[i]]
                if not r:
                    continue
                if bool(ctrl[i]):
                    pending.append(i)
                    continue
                f.write(f'  <vehicle id="v{i}" type="moto" depart="{float(dep[i]):.2f}" departLane="best" '
                        f'departSpeed="max"><route edges="{" ".join(r)}"/></vehicle>\n')
            f.write("</routes>\n")
        n_trips = sum(1 for i in order if rt[i])
        self._start(rou)
        sv, ss = self.sumo.vehicle, self.sumo.simulation
        ep = Episode(n_trips=n_trips, n_ctrl=len(pending))
        self._zone_of: dict[str, int] = {}
        on_edge: dict[str, int] = {}   # controlled vid -> link index it is on
        last_dec: dict[str, int] = {}  # vid -> index of its last decision in ep.decisions
        arrive: dict[str, float] = {}
        pi = 0
        self.live_tt = self.ff_edge.clone()
        self.live_D = self.Dz.clone()
        next_live = 0.0
        try:
            while ss.getTime() < cfg.horizon_s - 1e-9:
                t = ss.getTime()
                if cfg.live_every_s > 0 and t >= next_live:
                    self._refresh_live()
                    next_live = t + cfg.live_every_s
                # departures of controlled trips due by the end of this step: decide at the origin
                reqs: list[tuple[str, int, int, int]] = []  # vid, node, cur, zone
                while pi < len(pending) and float(dep[pending[pi]]) < t + cfg.step_s:
                    i = pending[pi]
                    reqs.append((f"c{i}", int(orig[i]), -1, int(dz[i])))
                    pi += 1
                # controlled vehicles that entered a new link
                for vid in list(on_edge):
                    road = sv.getRoadID(vid)
                    if not road or road.startswith(":"):
                        continue
                    e = self.e_of.get(road)
                    if e is None or e == on_edge[vid]:
                        continue
                    on_edge[vid] = e
                    z = self._zone_of[vid]
                    n = int(self.dst[e])
                    if n != int(self.zones[z]):
                        reqs.append((vid, n, e, z))
                if reqs:
                    self._decide(reqs, t, policy, ep, on_edge, last_dec, record)
                self.sumo.simulationStep()
                tn = ss.getTime()
                for vid in ss.getArrivedIDList():
                    arrive[vid] = tn
                    on_edge.pop(vid, None)
                for vid in ss.getStartingTeleportIDList() if hasattr(ss, "getStartingTeleportIDList") else []:
                    ep.teleports += 1
        finally:
            self.sumo.close()
        H = cfg.horizon_s
        for i in order:
            if not rt[i]:
                continue
            vid = f"c{i}" if bool(ctrl[i]) else f"v{i}"
            d0 = float(dep[i])
            if d0 >= H:
                continue
            end = arrive.get(vid, H)
            tt = end - d0
            ep.ttt_s += tt
            ep.arrived += vid in arrive
            if bool(ctrl[i]):
                ep.ttt_ctrl_s += tt
                ep.arrived_ctrl += vid in arrive
        # time from each decision to the vehicle's next one (or arrival / horizon)
        nxt: dict[str, float] = {}
        for d in reversed(ep.decisions):
            end = nxt.get(d["vid"], arrive.get(d["vid"], H))
            d["dt"] = end - d["t"]
            nxt[d["vid"]] = d["t"]
        ep.wall_s = time.perf_counter() - t0
        return ep

    def _decide(self, reqs, t, policy, ep, on_edge, last_dec, record) -> None:
        kept, cands = [], []
        for r in reqs:
            vid, n, cur, z = r
            c = [e for e in self.candidates(n, cur) if math.isfinite(float(self.Dz[z, e]))]
            if c:
                kept.append(r)
                cands.append(c)
        reqs = kept
        M = len(reqs)
        if M == 0:
            return
        cand = torch.full((M, self.Dmax), -1, dtype=torch.long)
        feat = torch.zeros(M, self.Dmax, N_FEAT)
        for j, (vid, n, cur, z) in enumerate(reqs):
            c = cands[j]
            cand[j, : len(c)] = torch.tensor(c)
            feat[j, : len(c)] = torch.tensor(self._features(n, c, z))
        live = None
        if self.cfg.live_every_s > 0:
            zs = torch.tensor([r[3] for r in reqs])
            c0 = cand.clamp(min=0)
            live = self.live_tt[c0] + self.live_D[zs.unsqueeze(1), c0]
            live = torch.where(cand >= 0, live, torch.full_like(live, math.inf))
        req = Request([r[0] for r in reqs], t, torch.tensor([r[1] for r in reqs]), cand, feat,
                      torch.tensor([r[3] for r in reqs]), live)
        a = policy.act(req) if policy is not None else torch.zeros(M, dtype=torch.long)
        sv = self.sumo.vehicle
        for j, (vid, n, cur, z) in enumerate(reqs):
            k = int(a[j])
            if not 0 <= k < len(cands[j]):
                k = 0
            e = cands[j][k]
            route = ([] if cur < 0 else [cur]) + [e] + self.completion(z, e)
            ids = [self.eid[x] for x in route]
            if cur < 0:
                self._zone_of[vid] = z
                rid = f"r_{vid}"
                self.sumo.route.add(rid, ids)
                sv.add(vid, rid, typeID="moto", depart="now", departLane="best", departSpeed="max")
                on_edge[vid] = e
            else:
                sv.setRoute(vid, ids)
            ep.n_decisions += 1
            if record:
                ep.decisions.append({"vid": vid, "t": t, "node": n, "cand": cands[j], "feat": feat[j, : len(cands[j])],
                                     "dest_zone": z, "a": k})
