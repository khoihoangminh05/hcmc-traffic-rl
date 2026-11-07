"""SUMO routing environment for MARL (libsumo; one SUMO instance per process).

Vehicles are motorbikes on the v4 net (routing2.sumo_net), demand from
routing2.demand (same zones and trips as the meso). A share `penetration` of the
trips is the controlled fleet; the rest is background traffic on free-flow routes.

With `micro` on, the episode is a sequence of single decisions. SUMO runs until the first time
a vehicle must choose: it is about to reach the end of its link (decide_ahead_*) or it departs.
Vehicles due at the same time are served one at a time, in random order, at zero elapsed time, so
each one sees what the previous one chose. The vehicle count feature then covers fleet vehicles
only. A vehicle with a single exit is not asked: it is routed and nothing is recorded, so a
decision's dt runs to the vehicle's next real choice. Without `micro` (the setting of the gate
scripts):

A controlled vehicle decides its next link at every node (next-hop routing):
- at its origin, when it departs (it is inserted on the chosen first link);
- each time it enters a new link e, for the exit at e's downstream node, unless that
  node is its destination.
After a decision the vehicle's SUMO route is [current link, chosen exit] + the
free-flow shortest completion, so SUMO always holds a valid route; the next
decision replaces the completion.

Policies see, per candidate exit (feature order in FEAT_*): free-flow time, current link time,
vehicle count on the link, free-flow time to the destination, length, intent, live time to the
destination. Intent is the number of other fleet vehicles that already chose this link and have
not entered it yet; only the provider knows this, a speed map does not. With live_source="probe"
the link time comes from completed traversals of fleet vehicles; otherwise it is SUMO's
edge.getTraveltime, which jumps when one vehicle stops. The vehicle count is still SUMO's count of
all vehicles, which a provider could not measure at p < 1.

`run(policy)` plays one episode and returns, per decision, the request, the chosen
index and the time to the vehicle's next decision (or arrival / horizon). The reward
of a decision is minus that time, so a vehicle's return is minus its own travel time;
system objectives (total travel time) are summed by the trainer.

    python -u -m routing2.bench_sumo   # speed and sanity check
"""

from __future__ import annotations

import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import torch

from .demand import Demand
from .graph import MesoGraph
from .objectives import trip_metrics
from .sumo_check import MOTO_VTYPE
from .sumo_net import sumo_binary

N_FEAT = 8  # per candidate exit
FEAT_FF, FEAT_TT, FEAT_N, FEAT_TOGO, FEAT_LEN, FEAT_INTENT, FEAT_LIVE_TOGO, FEAT_AHEAD = range(N_FEAT)


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
    # "edge": SUMO's instantaneous edge estimate (length / last-step mean speed, jumps when one
    # vehicle stops). "probe": completed traversals of controlled vehicles in the last
    # `probe_window_s`, plus the elapsed time of vehicles still on the link when above that mean,
    # which is what a navigation provider can measure from its own users.
    live_source: str = "edge"
    probe_window_s: float = 120.0
    # Which links reports may come from: all, roads (no alley reports), a blind app on alleys.
    live_mask: str = "all"
    # Hidden alley incidents (parked vehicle, market, funeral): their rate is unknown, so it is
    # swept. A link used by free-flow routes slows to incident_speed for incident_s; no policy
    # is told, it can only see the effect through reports. Same schedule for every policy.
    incident_rate_per_h: float = 0.0
    incident_s: float = 600.0
    incident_speed: float = 0.5
    incident_seed: int = 0
    # School letting out: every link at one alley node slows down for school_s. Rate unknown, swept.
    school_rate_per_h: float = 0.0
    school_s: float = 900.0
    school_speed: float = 1.5
    # One decision at a time, at the end of the link. See the module docstring.
    micro: bool = False
    decide_ahead_m: float = 10.0
    decide_ahead_s: float = 3.0
    # Exits are hidden when the trip's free-flow length would pass (1 + max_detour) x its shortest
    # one + detour_abs_s. Stops untrained policies from wandering; the shortest exit stays. None = off.
    max_detour: float | None = None
    detour_abs_s: float = 60.0
    # > 0: every this many seconds, while recording, charge each slowed vehicle's delay to the
    # vehicles that hold it up (see _attribute). Training only; uses the true state of all vehicles.
    attribute_every_s: float = 0.0
    attribute_ahead_m: float = 50.0
    attribute_merge_m: float = 30.0
    # What the real world adds, the same for every controller. No value here is measured: sweep them.
    # A report of a fleet vehicle is lost with report_drop; a traversal time carries a lognormal
    # error of report_noise (GPS, map matching).
    report_drop: float = 0.0
    report_noise: float = 0.0
    # True: features count the fleet vehicles seen at the last report, not where they are right now.
    fleet_snapshot: bool = False
    # A driver follows the instruction with this probability, otherwise takes the shortest exit, and
    # less often the further the instruction is from the shortest way: x exp(-extra free-flow s /
    # compliance_detour_s). Drivers avoid long or unfamiliar ways. Invented values: swept in the results.
    # The provider only learns it from later reports, so intent keeps what it told the driver.
    compliance: float = 1.0
    compliance_detour_s: float = 60.0
    # This share of background trips uses another navigation app (SUMO rerouting device).
    bg_reroute_share: float = 0.0
    bg_reroute_period_s: float = 120.0
    # extra SUMO command-line arguments, e.g. ("-a", "edgedata.add.xml") for per-link speeds (audits only)
    extra_args: tuple[str, ...] = ()
    # Measure vehicle-seconds standing per link, for routing2.scenarios. Not for controllers.
    record_link_wait: bool = False


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
    tick: int = -1  # index of the current report period


class SumoPolicy(Protocol):
    def act(self, req: Request) -> torch.Tensor:
        """Chosen candidate index per row [M]."""
        ...


@dataclass
class Episode:
    decisions: list[dict] = field(default_factory=list)
    ticks: list[dict] = field(default_factory=list)  # micro + record: edge state per report period
    ttt_s: float = 0.0
    ttt_ctrl_s: float = 0.0
    n_trips: int = 0
    n_ctrl: int = 0
    arrived: int = 0
    arrived_ctrl: int = 0
    teleports: int = 0
    teleports_collision: int = 0  # of those, the vehicle had just collided; the others waited too long
    collisions: int = 0
    wall_s: float = 0.0
    km: float = 0.0  # distance driven by controlled vehicles (completed links)
    incidents: int = 0
    n_decisions: int = 0
    forced: int = 0  # micro: nodes passed with a single exit, no decision asked
    missed_decisions: int = 0  # micro: entered the next link before its decision came due
    # Integrals over the episode of (trips in the system / trips) and the same for customers. With
    # every trip finished they equal T_all and T_cust, so these are J written as a rate over time.
    system_all_s: float = 0.0
    system_cust_s: float = 0.0
    delay_attributed_s: float = 0.0
    delay_seen_s: float = 0.0
    trip_tt: dict = field(default_factory=dict)  # trip index -> travel time, unfinished ones included
    caused_s: dict = field(default_factory=dict)  # fleet vid -> delay charged to it, all vehicles
    metrics: dict = field(default_factory=dict)  # routing2.objectives.trip_metrics
    link_wait_s: list[float] = field(default_factory=list)
    teleport_links: dict = field(default_factory=dict)  # link index -> teleports of fleet vehicles


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
        self._lane_len: dict[int, float] = {}

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

    def _fleet_ahead_table(self, load: torch.Tensor) -> torch.Tensor:
        """[Z, E + 1] sum of `load` over the links after each link on the live shortest path to each
        zone. Pointer doubling; a path of up to 256 links counts in full."""
        Z, E = len(self.zones), self.g.n_edges
        idx = self.frm.unsqueeze(0).expand(Z, -1)
        cost = self.live_tt[self.to].unsqueeze(0) + self.live_D[:, self.to]
        best = torch.full((Z, E), math.inf, dtype=cost.dtype).scatter_reduce(1, idx, cost, reduce="amin", include_self=True)
        zi, k = torch.nonzero((cost == best.gather(1, idx)) & torch.isfinite(cost), as_tuple=True)
        nxt = torch.full((Z, E + 1), E, dtype=torch.long)
        nxt[zi, self.frm[k]] = self.to[k]
        nxt[:, :E][self._at] = E  # arrived: the path ends
        out = torch.cat([load.float(), torch.zeros(1)])[nxt]
        for _ in range(8):
            out = out + out.gather(1, nxt)
            nxt = nxt.gather(1, nxt)
        return out

    def _refresh_probe(self, t: float) -> None:
        win = self.cfg.probe_window_s
        while self._probes and self._probes[0][0] < t - win:
            self._probes.popleft()
        tot: dict[int, float] = {}
        cnt: dict[int, int] = {}
        for _, e, x in self._probes:
            tot[e] = tot.get(e, 0.0) + x
            cnt[e] = cnt.get(e, 0) + 1
        for vid, e in self._on_edge.items():
            t0 = self._t_enter.get(vid)
            if t0 is None or self._rng.random() < self.cfg.report_drop:
                continue
            x = (t - t0) * self._rng.lognormvariate(0.0, self.cfg.report_noise)
            m = tot[e] / cnt[e] if e in cnt else float(self.ff_edge[e])
            if x > m:
                tot[e] = tot.get(e, 0.0) + x
                cnt[e] = cnt.get(e, 0) + 1
        # live_alpha and the drift are per 30 s of simulated time, whatever the refresh period
        rate = self.cfg.live_every_s / 30.0
        a = 1.0 - (1.0 - self.cfg.live_alpha) ** rate
        now = self.live_tt + (1.0 - 0.9**rate) * (self.ff_edge - self.live_tt)  # no report: drift to free flow
        for e, n in cnt.items():
            if self.cfg.live_mask == "roads" and bool(self.g.is_alley[e]):
                continue
            now[e] = (1 - a) * self.live_tt[e] + a * max(tot[e] / n, 0.5 * float(self.ff_edge[e]))
        self.live_tt = now
        self.live_D = self._time_to_zones(self.live_tt)

    def _refresh_live(self, t: float = 0.0) -> None:
        if self.cfg.live_source == "probe":
            self._refresh_probe(t)
            return
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

    def _incident_schedule(self, rt: list[list[int]], dep: torch.Tensor) -> list[tuple[float, list[int], float, float]]:
        """(start, links, speed, duration), places drawn in proportion to free-flow use among alleys."""
        cfg = self.cfg
        if cfg.incident_rate_per_h <= 0 and cfg.school_rate_per_h <= 0:
            return []
        use = torch.zeros(self.g.n_edges)
        for r in rt:
            if r:
                use[torch.tensor(r)] += 1.0
        use = use * self.g.is_alley.cpu().float()
        gen = torch.Generator().manual_seed(cfg.incident_seed)
        last = float(dep.max())
        out: list[tuple[float, list[int], float, float]] = []
        if cfg.incident_rate_per_h > 0:
            n = max(1, round(cfg.incident_rate_per_h * last / 3600.0))
            links = torch.multinomial(use, n, replacement=False, generator=gen).tolist()
            starts = (torch.rand(n, generator=gen) * last).tolist()
            out += [(s, [e], cfg.incident_speed, cfg.incident_s) for s, e in zip(starts, links)]
        if cfg.school_rate_per_h > 0:
            gen2 = torch.Generator().manual_seed(cfg.incident_seed + 1)
            n = max(1, round(cfg.school_rate_per_h * last / 3600.0))
            for e in torch.multinomial(use, n, replacement=False, generator=gen2).tolist():
                node = self.dst[e]
                near = torch.nonzero((self.src == node) | (self.dst == node)).squeeze(1).tolist()
                out.append((float(torch.rand(1, generator=gen2)) * last, near, cfg.school_speed, cfg.school_s))
        return sorted(out, key=lambda x: x[0])

    def _start(self, rou: Path) -> None:
        cfg = self.cfg
        self.sumo.start([
            sumo_binary("sumo"), "-n", str(cfg.net), "-r", str(rou),
            "--step-length", str(cfg.step_s), "--lateral-resolution", str(cfg.lateral_m),
            "--time-to-teleport", str(cfg.teleport_s), "--no-step-log", "true",
            "--no-warnings", "true", "--end", str(cfg.horizon_s), "--seed", str(cfg.sumo_seed),
            "--device.rerouting.period", str(cfg.bg_reroute_period_s),
            *cfg.extra_args,
        ])

    def _features(self, node: int, cand: list[int], z: int) -> list[list[float]]:
        ed = self.sumo.edge
        rows = []
        probe = self.cfg.live_source == "probe" and self.cfg.live_every_s > 0
        if self._ahead_tick != self._tick or self._ahead is None:  # the same table for one report period
            self._ahead_tick = self._tick
            self._ahead = self._fleet_ahead_table(torch.tensor(self._fleet_seen, dtype=torch.float32)
                                                  + torch.tensor(self._intent_n, dtype=torch.float32))
        for e in cand:
            eid = self.eid[e]
            ff = float(self.ff_edge[e])
            if probe:
                tt = float(self.live_tt[e])
            else:
                tt = ed.getTraveltime(eid)
                if not math.isfinite(tt) or tt <= 0 or tt > 1e5:
                    tt = ff
            count = self._fleet_seen[e] if self.cfg.micro else ed.getLastStepVehicleNumber(eid)
            rows.append([ff, tt, float(count),
                         float(self.Dz[z, e]), float(self.length[e]),
                         float(self._intent_n[e]), float(self.live_D[z, e]), float(self._ahead[z, e])])
        return rows

    def _attribute(self, dt: float, ep: Episode) -> None:
        """Split each slowed vehicle's delay of the last dt seconds among the vehicles holding it up.

        Holding it up means ahead of it on its link within attribute_ahead_m, or, when it is near the
        end of the link, near the end of another link into the same junction. Shares add up to the
        delay, so nothing is counted twice. A delay with nobody to blame (a red light on an empty
        road) goes uncharged. Only fleet vehicles keep their charge. c* ids are the fleet.
        """
        cfg, sv = self.cfg, self.sumo.vehicle
        on: dict[int, list[tuple[float, str, float]]] = {}
        for vid in sv.getIDList():
            e = self.e_of.get(sv.getRoadID(vid))
            if e is not None:
                on.setdefault(e, []).append((sv.getLanePosition(vid), vid, sv.getSpeed(vid)))
        lane_len = self._lane_len
        near_node: dict[int, list[tuple[int, str, float]]] = {}
        for e, rows in on.items():
            if e not in lane_len:
                lane_len[e] = self.sumo.lane.getLength(f"{self.eid[e]}_0")
            rows.sort(reverse=True)  # front of the link first
            for pos, vid, v in rows:
                if lane_len[e] - pos <= cfg.attribute_merge_m:
                    near_node.setdefault(int(self.dst[e]), []).append((e, vid, v))
        for e, rows in on.items():
            # an event's own slowdown is nobody's fault: measure against the limit in force
            vf = self._limit.get(e, float(self.length[e]) / float(self.ff_edge[e]))
            node = int(self.dst[e])
            for k, (pos, vid, v) in enumerate(rows):
                if v >= 0.9 * vf:  # drivers run a little under the limit: not a delay
                    continue
                d = dt * (1.0 - v / vf)
                ep.delay_seen_s += d
                causes = [x[1] for x in rows[:k] if x[0] - pos <= cfg.attribute_ahead_m]
                if lane_len[e] - pos <= cfg.attribute_merge_m:
                    # a vehicle standing on another branch is waiting too, it holds nobody up
                    causes += [u for f, u, w in near_node.get(node, []) if f != e and w > 0.5]
                if not causes:
                    continue
                ep.delay_attributed_s += d
                book = self._caused_cust if vid[0] == "c" else self._caused_other
                for u in causes:
                    if u[0] == "c":
                        book[u] = book.get(u, 0.0) + d / len(causes)

    def _edge_state(self, truth: bool) -> dict[str, torch.Tensor]:
        """actor: [E, 2] congestion from reports, fleet load. true (training only): [E, 2] all
        vehicles per 10 m, speed / free-flow speed."""
        per10m = 10.0 / self.length.float().clamp(min=5.0)
        fleet = torch.tensor(self._fleet_seen, dtype=torch.float32) + torch.tensor(self._intent_n, dtype=torch.float32)
        out = {"actor": torch.stack([torch.log(self.live_tt.float() / self.ff_edge.float()).clamp(-1.0, 4.0),
                                     (fleet * per10m).clamp(max=5.0)], -1)}
        if truth:
            ed = self.sumo.edge
            n = torch.tensor([ed.getLastStepVehicleNumber(e) for e in self.eid], dtype=torch.float32)
            v = torch.tensor([ed.getLastStepMeanSpeed(e) for e in self.eid], dtype=torch.float32)
            vf = (self.length.float() / self.ff_edge.float()).clamp(min=0.1)
            out["true"] = torch.stack([(n * per10m).clamp(max=5.0), (v / vf).clamp(0.0, 1.5)], -1)
        return out

    def _within_detour(self, vid: str, cur: int, z: int, c: list[int]) -> list[int]:
        cost = [float(self.ff_edge[e]) + float(self.Dz[z, e]) for e in c]
        if cur < 0:
            self._ff_orig[vid], self._ff_done[vid] = min(cost), 0.0
        limit = (1.0 + self.cfg.max_detour) * self._ff_orig[vid] + self.cfg.detour_abs_s
        done = self._ff_done[vid]
        keep = [e for e, x in zip(c, cost) if done + x <= limit]
        return keep or [c[cost.index(min(cost))]]

    def _move_fleet(self, vid: str, e: int | None) -> None:
        old = self._fleet_at.pop(vid, None)
        if old is not None:
            self._fleet_n[old] -= 1
        if e is not None:
            self._fleet_at[vid] = e
            self._fleet_n[e] += 1
        if not self.cfg.fleet_snapshot:
            self._fleet_seen = self._fleet_n

    def _take_snapshot(self) -> None:
        self._fleet_seen = [0] * self.g.n_edges
        for e in self._fleet_at.values():
            if self._rng.random() >= self.cfg.report_drop:
                self._fleet_seen[e] += 1

    def _clear_intent(self, vid: str) -> None:
        e = self._intent.pop(vid, None)
        if e is not None:
            self._intent_n[e] -= 1

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
        # same draws for every controller on a seed
        bg_u = torch.rand(N, generator=torch.Generator().manual_seed(cfg.incident_seed + 2))
        self._rng = random.Random(cfg.incident_seed + 3)
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
                app = '<param key="has.rerouting.device" value="true"/>' if float(bg_u[i]) < cfg.bg_reroute_share else ""
                f.write(f'  <vehicle id="v{i}" type="moto" depart="{float(dep[i]):.2f}" departLane="best" '
                        f'departSpeed="max">{app}<route edges="{" ".join(r)}"/></vehicle>\n')
            f.write("</routes>\n")
        n_trips = sum(1 for i in order if rt[i])
        self._start(rou)
        sv, ss = self.sumo.vehicle, self.sumo.simulation
        ep = Episode(n_trips=n_trips, n_ctrl=len(pending))
        self._zone_of: dict[str, int] = {}
        on_edge: dict[str, int] = {}   # controlled vid -> link index it is on
        last_dec: dict[str, int] = {}  # vid -> index of its last decision in ep.decisions
        arrive: dict[str, float] = {}
        rem_ff: dict[str, float] = {}
        pi = 0
        self.live_tt = self.ff_edge.clone()
        self.live_D = self.Dz.clone()
        next_live = 0.0
        schedule = self._incident_schedule(rt, dep)
        ending: list[tuple[float, int]] = []
        slow: dict[int, int] = {}
        self._limit: dict[int, float] = {}  # link -> speed limit of an event in force
        self._ahead, self._ahead_tick = None, None
        ep.incidents = len(schedule)
        self._probes: deque = deque()
        self._report_n = [0] * self.g.n_edges  # traversal reports received per link, this episode
        self._on_edge = on_edge
        self._t_enter: dict[str, float] = {}
        self._intent: dict[str, int] = {}  # fleet vid -> link it chose and has not entered
        self._intent_n = [0] * self.g.n_edges
        self._due: dict[str, tuple[int, int, int]] = {}  # micro: vid -> (node, link, zone) to decide
        self._fleet_at: dict[str, int] = {}  # micro: vid -> link it is counted on
        self._fleet_n = [0] * self.g.n_edges
        self._fleet_seen = self._fleet_n
        order_gen = torch.Generator().manual_seed(cfg.sumo_seed)
        self._tick = -1
        self._sys = (0.0, 0.0)
        self._caused_cust: dict[str, float] = {}
        self._caused_other: dict[str, float] = {}
        next_attr = cfg.attribute_every_s
        next_wait = 5.0
        if cfg.record_link_wait:
            ep.link_wait_s = [0.0] * self.g.n_edges
        kept = [i for i in order if rt[i]]
        n_kept, n_cust = max(1, len(kept)), max(1, ep.n_ctrl)
        dep_idx, in_all, in_cust = 0, 0, 0
        sys_all, sys_cust = 0.0, 0.0
        at_end: dict[str, tuple[float, float]] = {}  # vid -> integrals when it arrived
        self._ff_orig: dict[str, float] = {}
        self._ff_done: dict[str, float] = {}
        try:
            while ss.getTime() < cfg.horizon_s - 1e-9:
                t = ss.getTime()
                while schedule and schedule[0][0] <= t:
                    _, links, speed, dur = schedule.pop(0)
                    for e in links:
                        self.sumo.edge.setMaxSpeed(self.eid[e], speed)
                        slow[e] = slow.get(e, 0) + 1
                        self._limit[e] = speed
                        ending.append((t + dur, e))
                for item in [x for x in ending if x[0] <= t]:
                    ending.remove(item)
                    slow[item[1]] -= 1
                    if slow[item[1]] == 0:  # overlapping events: free flow only after the last one
                        self._limit.pop(item[1], None)
                        self.sumo.edge.setMaxSpeed(self.eid[item[1]], float(self.g.v_free[item[1]]))
                if cfg.live_every_s > 0 and t >= next_live:
                    self._refresh_live(t)
                    next_live = t + cfg.live_every_s
                    self._tick += 1
                    if cfg.micro and cfg.fleet_snapshot:
                        self._take_snapshot()
                    if cfg.micro:
                        state = self._edge_state(record)
                        if record:
                            ep.ticks.append(state)
                        if hasattr(policy, "observe"):
                            policy.observe(state)
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
                    if e is not None and self._intent.get(vid) == e:
                        self._clear_intent(vid)
                    if e is not None and cfg.micro and self._fleet_at.get(vid) != e:
                        self._move_fleet(vid, e)
                    if e is None:
                        continue
                    if e != on_edge[vid]:
                        old = on_edge[vid]
                        ep.km += float(self.length[old]) / 1000.0
                        if vid in self._t_enter:
                            self._add_probe(t, old, t - self._t_enter[vid])
                        self._t_enter[vid] = t
                        on_edge[vid] = e
                        z = self._zone_of[vid]
                        n = int(self.dst[e])
                        if cfg.micro:
                            ep.missed_decisions += self._due.pop(vid, None) is not None
                        if n != int(self.zones[z]):
                            if cfg.micro:
                                self._due[vid] = (n, e, z)
                            else:
                                reqs.append((vid, n, e, z))
                    if vid in self._due and e == self._due[vid][1]:
                        # a link shorter than one step is due in the step it is entered
                        # the lane length, not the graph's: netconvert shortens lanes at junctions
                        rem = self.sumo.lane.getLength(sv.getLaneID(vid)) - sv.getLanePosition(vid)
                        if rem <= max(cfg.decide_ahead_m, sv.getSpeed(vid) * cfg.decide_ahead_s):
                            n, _, z = self._due.pop(vid)
                            reqs.append((vid, n, e, z))
                if reqs and cfg.micro:
                    for k in torch.randperm(len(reqs), generator=order_gen).tolist():
                        self._decide([reqs[k]], t, policy, ep, on_edge, last_dec, record)
                elif reqs:
                    self._decide(reqs, t, policy, ep, on_edge, last_dec, record)
                self.sumo.simulationStep()
                tn = ss.getTime()
                # each trip counts from its planned departure, part of a step included
                sys_all += in_all * cfg.step_s / n_kept
                sys_cust += in_cust * cfg.step_s / n_cust
                while dep_idx < len(kept) and float(dep[kept[dep_idx]]) < tn:
                    i = kept[dep_idx]
                    part = tn - float(dep[i])
                    is_cust = bool(ctrl[i])
                    sys_all += part / n_kept
                    sys_cust += part * is_cust / n_cust
                    in_all += 1
                    in_cust += is_cust
                    dep_idx += 1
                self._sys = (sys_all, sys_cust)
                if cfg.record_link_wait and tn >= next_wait:
                    next_wait += 5.0
                    for k, eid in enumerate(self.eid):
                        ep.link_wait_s[k] += 5.0 * self.sumo.edge.getLastStepHaltingNumber(eid)
                if record and cfg.attribute_every_s > 0 and tn >= next_attr:
                    self._attribute(cfg.attribute_every_s, ep)
                    next_attr += cfg.attribute_every_s
                for vid in ss.getArrivedIDList():
                    arrive[vid] = tn
                    in_all -= 1
                    in_cust -= vid[0] == "c"
                    at_end[vid] = (sys_all, sys_cust)
                    self._clear_intent(vid)
                    self._due.pop(vid, None)
                    self._move_fleet(vid, None)
                    if vid in on_edge:
                        last = on_edge.pop(vid)
                        ep.km += float(self.length[last]) / 1000.0
                        if vid in self._t_enter:
                            self._add_probe(tn, last, tn - self._t_enter.pop(vid))
                crashed = {c.collider for c in ss.getCollisions()}
                ep.collisions += len(crashed)
                for vid in ss.getStartingTeleportIDList():
                    ep.teleports += 1
                    ep.teleports_collision += vid in crashed
                    if vid in on_edge:  # where: known for the fleet only
                        ep.teleport_links[on_edge[vid]] = ep.teleport_links.get(on_edge[vid], 0) + 1
            for vid in sv.getIDList():  # still driving at the end
                rem_ff[vid] = self._remaining_ff(vid, int(dz[int(vid[1:])]))
        finally:
            self.sumo.close()
        H = cfg.horizon_s
        rows: list[tuple[float, float, bool, float, float, bool]] = []
        for i in order:
            if not rt[i]:
                continue
            vid = f"c{i}" if bool(ctrl[i]) else f"v{i}"
            d0 = float(dep[i])
            if d0 >= H:
                continue
            end = arrive.get(vid, H)
            tt = end - d0
            ff = float(self.ff_edge[torch.tensor(rt[i])].sum())
            # a trip that never entered the network still has its whole route to drive
            rows.append((d0, end, vid in arrive, rem_ff.get(vid, ff), ff, bool(ctrl[i])))
            ep.trip_tt[i] = end - d0 + (0.0 if vid in arrive else rem_ff.get(vid, ff))
            ep.ttt_s += tt
            ep.arrived += vid in arrive
            if bool(ctrl[i]):
                ep.ttt_ctrl_s += tt
                ep.arrived_ctrl += vid in arrive
        ep.metrics = trip_metrics(*zip(*rows), teleports=ep.teleports) if rows else {}
        if rows:
            ep.metrics["collisions_per_1k_trips"] = 1000.0 * ep.collisions / len(rows)
            ep.metrics["teleports_collision_per_1k_trips"] = 1000.0 * ep.teleports_collision / len(rows)
        # time from each decision to the vehicle's next one (or arrival / horizon)
        nxt: dict[str, float] = {}
        nxt_cust, nxt_other = dict(self._caused_cust), dict(self._caused_other)
        ep.system_all_s, ep.system_cust_s = sys_all, sys_cust
        nxt_sys: dict[str, tuple[float, float]] = {}
        for d in reversed(ep.decisions):
            vid = d["vid"]
            end = nxt.get(vid, arrive.get(vid, H))
            d["dt"] = end - d["t"]
            nxt[vid] = d["t"]
            # delay this vehicle caused between this decision and its next one
            d["e_cust"] = nxt_cust.get(vid, 0.0) - d["cust0"]
            d["e_other"] = nxt_other.get(vid, 0.0) - d["other0"]
            nxt_cust[vid], nxt_other[vid] = d["cust0"], d["other0"]
            end_sys = nxt_sys.get(vid, at_end.get(vid, (sys_all, sys_cust)))
            d["sys_all"], d["sys_cust"] = end_sys[0] - d["sys0"][0], end_sys[1] - d["sys0"][1]
            nxt_sys[vid] = d["sys0"]
        for vid in set(self._caused_cust) | set(self._caused_other):
            ep.caused_s[vid] = self._caused_cust.get(vid, 0.0) + self._caused_other.get(vid, 0.0)
        ep.wall_s = time.perf_counter() - t0
        return ep

    def _add_probe(self, t: float, e: int, x: float) -> None:
        if self._rng.random() >= self.cfg.report_drop:
            self._probes.append((t, e, x * self._rng.lognormvariate(0.0, self.cfg.report_noise)))
            self._report_n[e] += 1

    def _remaining_ff(self, vid: str, z: int) -> float:
        """Free-flow time from the vehicle's position to zone z along connected links."""
        sv = self.sumo.vehicle
        k = sv.getRouteIndex(vid)
        route = sv.getRoute(vid)
        e = self.e_of.get(route[k]) if 0 <= k < len(route) else None
        if e is None:
            return 0.0
        togo = float(self.Dz[z, e])
        togo = togo if math.isfinite(togo) else 0.0
        if sv.getRoadID(vid) == route[k]:
            v = float(self.length[e]) / float(self.ff_edge[e])
            togo += max(0.0, float(self.length[e]) - sv.getLanePosition(vid)) / v
        return togo

    def _decide(self, reqs, t, policy, ep, on_edge, last_dec, record) -> None:
        kept, cands = [], []
        for r in reqs:
            vid, n, cur, z = r
            c = [e for e in self.candidates(n, cur) if math.isfinite(float(self.Dz[z, e]))]
            if c and self.cfg.max_detour is not None:
                c = self._within_detour(vid, cur, z, c)
            if c:
                kept.append(r)
                cands.append(c)
        reqs = kept
        M = len(reqs)
        if M == 0:
            return
        forced = self.cfg.micro and M == 1 and len(cands[0]) == 1
        if forced:
            self._route(reqs[0], cands[0][0], cands[0][0], on_edge)
            ep.forced += 1
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
                      torch.tensor([r[3] for r in reqs]), live, self._tick)
        a = policy.act(req) if policy is not None else torch.zeros(M, dtype=torch.long)
        for j, (vid, n, cur, z) in enumerate(reqs):
            k = int(a[j])
            if not 0 <= k < len(cands[j]):
                k = 0
            told = cands[j][k]
            best = self._best(z, cands[j])
            extra = float(self.ff_edge[told] + self.Dz[z, told] - self.ff_edge[best] - self.Dz[z, best])
            follow = self.cfg.compliance * math.exp(-max(extra, 0.0) / self.cfg.compliance_detour_s)
            ignores = follow < 1.0 and self._rng.random() >= follow
            self._route(reqs[j], best if ignores else told, told, on_edge)
            ep.n_decisions += 1
            if record:
                ep.decisions.append({"vid": vid, "t": t, "node": n, "cand": cands[j], "feat": feat[j, : len(cands[j])],
                                     "dest_zone": z, "a": k, "tick": self._tick,
                                     "togo": float(live[j].min()) if live is not None else 0.0,
                                     "cust0": self._caused_cust.get(vid, 0.0),
                                     "other0": self._caused_other.get(vid, 0.0), "sys0": self._sys})

    def _route(self, req, e: int, told: int, on_edge: dict[str, int]) -> None:
        """Send the vehicle of a request onto exit e; `told` is what the provider asked of it."""
        vid, _, cur, z = req
        sv = self.sumo.vehicle
        if self.cfg.max_detour is not None:
            self._ff_done[vid] += float(self.ff_edge[e])
        route = ([] if cur < 0 else [cur]) + [e] + self.completion(z, e)
        ids = [self.eid[x] for x in route]
        if cur < 0:
            self._zone_of[vid] = z
            rid = f"r_{vid}"
            self.sumo.route.add(rid, ids)
            sv.add(vid, rid, typeID="moto", depart="now", departLane="best", departSpeed="max")
            on_edge[vid] = e
            if self.cfg.micro and int(self.dst[e]) != int(self.zones[z]):
                self._due[vid] = (int(self.dst[e]), e, z)
        else:
            sv.setRoute(vid, ids)
        self._clear_intent(vid)  # it left its previous target without entering it (teleport)
        self._intent[vid] = told
        self._intent_n[told] += 1
