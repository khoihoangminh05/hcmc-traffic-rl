"""Micro next-hop multi-agent alley env (MAPPO).

Fixes vs macro K-path:
- Action = choose outgoing edge at current node (horizon long)
- OD filtered for longer trips (caller / pool)
- Rich time: t_norm + peak one-hot; density switches by peak
- Reward aligned to travel (dominant) + mild congestion
- Local obs includes per-neighbor free-time, unc, bg load, remaining heuristic
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np


def _stable_u32(token: str) -> int:
    """Process-stable hash (Python hash() is salted per process → breaks subproc obs)."""
    return int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)


def _capacity_for(data: dict[str, Any]) -> float:
    rc = (data.get("road_class") or "").lower()
    layer = (data.get("layer") or "").lower()
    if rc == "alley" or layer == "alley":
        return 2.5
    if rc in ("residential", "service") or layer in ("local",):
        return 6.0
    if rc in ("tertiary", "secondary"):
        return 10.0
    return 8.0


class MicroAlleyEnv:
    metadata = {"name": "mappo_micro_v1"}

    def __init__(
        self,
        density_path: Path,
        graph_path: Path | None = None,
        seed: int = 0,
        n_agents: int = 16,
        max_degree: int = 8,
        max_steps: int = 200,
        compact_dim: int = 208,
        bpr_alpha: float = 0.15,
        bpr_beta: float = 4.0,
        bpr_load_cap: float = 12.0,
        corridor_prob: float = 0.4,
        reward_weights: dict[str, float] | None = None,
        density_catalog: dict[str, Path] | None = None,
        reward_mode: str = "travel",
        travel_scale: float = 1000.0,
        depart_span_s: float = 90.0,
        jam_spacing_m: float = 6.0,
        shock_rate: float = 0.0,
        share_coef: float = 0.0,
        include_alley_info: bool = True,
        no_uturn: bool = False,
        trip_cap_mult: float = 0.0,
        trip_cap_min_s: float = 1800.0,
        progress_shaping: float = 0.0,
        shaping_gamma: float = 0.999,
        uturn_delay_s: float = 0.0,
    ) -> None:
        if reward_mode not in ("marginal", "travel", "legacy"):
            raise ValueError(f"reward_mode={reward_mode!r}")
        # travel:   realized traversal time, plus the pile penalty in _corr.
        #           This is the compared score for every controller.
        # marginal: that same time, plus the imposed delay a second time.
        # legacy:   v1–v2h shaped reward (free-flow progress, cong, revisit, team).
        self.reward_mode = reward_mode
        self.travel_scale = max(1.0, float(travel_scale))
        # Release offsets. 0 = everyone departs together (tests). Training uses
        # a spread so vehicles do not enter the corridor on the same instant.
        self.depart_span_s = max(0.0, float(depart_span_s))
        # Metres of alley per vehicle stored in it. Distinct from BPR flow
        # capacity: a full alley refuses entry and the vehicle waits at the node.
        self.jam_spacing_m = max(1.0, float(jam_spacing_m))
        # Probability an episode draws one controlled exogenous event. 0 keeps
        # the nominal MDP (unit tests). Training sets 1. The event is seeded and
        # locked across controllers; the basic heuristic does not read it.
        self.shock_rate = min(1.0, max(0.0, float(shock_rate)))
        # Extra seconds charged when a vehicle joins others already on a link.
        # Same charge for every controller. It is part of the reward and of the
        # compared objective (travel + this penalty). It is not a second copy
        # of the BPR slowdown, which is already inside travel time.
        self.share_coef = max(0.0, float(share_coef))
        self.include_alley_info = bool(include_alley_info)
        # Same rule for every controller: do not go straight back to the node
        # just left, unless it is the only exit.
        self.no_uturn = bool(no_uturn)
        # A trip still out after max(min_s, mult · congested trip time) has
        # failed and is truncated on its own. 0 = only the fleet step cap.
        self.trip_cap_mult = max(0.0, float(trip_cap_mult))
        self.trip_cap_min_s = max(0.0, float(trip_cap_min_s))
        # Training signal only, potential-based (Ng et al. 1999): each hop adds
        # coef · (R(curr) − γ·R(next)) / scale, R = congested time to go.
        # It does not change the optimal policy, and it is not in _travel or
        # _city, so the compared score is untouched. γ must equal ppo.gamma.
        self.progress_shaping = max(0.0, float(progress_shaping))
        self.shaping_gamma = float(shaping_gamma)
        # Turning a motorbike around in an alley takes time. Charged as extra
        # free-flow seconds on the link back, so it grows with congestion.
        # Every controller pays it, and greedy_load's forecast includes it.
        self.uturn_delay_s = max(0.0, float(uturn_delay_s))
        self.density_path = Path(density_path)
        self.graph_path = graph_path
        self.n_agents = max(2, int(n_agents))
        self.max_degree = max(2, int(max_degree))
        self.max_steps = max(8, int(max_steps))
        self.compact_dim = max(64, int(compact_dim))
        self.bpr_alpha = float(bpr_alpha)
        self.bpr_beta = float(bpr_beta)
        self.bpr_load_cap = float(bpr_load_cap)
        self.corridor_prob = float(corridor_prob)
        self.reward_weights = {
            "w_T": 1.0,
            "w_C": 0.35,
            "w_R": 0.05,
            "w_step": 0.02,
            "arrive_bonus": 2.0,
            "w_progress": 0.4,
            "w_revisit": 0.25,
            "w_team": 0.15,
        }
        if reward_weights:
            self.reward_weights.update({k: float(v) for k, v in reward_weights.items()})
        self.density_catalog = {
            str(k): Path(v) for k, v in (density_catalog or {}).items() if v
        }
        self._active_peak: str | None = None
        self.rng = np.random.default_rng(seed)
        self.agents = [f"agent_{i}" for i in range(self.n_agents)]
        self._g = self._load_graph()
        self._density, self._speed, self._unc = self._load_density_file(self.density_path)
        self._edge_index = list(self._g.edges())
        self._cap = {
            e: _capacity_for(self._g.edges[e[0], e[1]]) for e in self._edge_index
        }
        self._nodes = sorted(self._g.nodes())
        self._aids = sorted({d["alley_id"] for _, _, d in self._g.edges(data=True)})
        self._out: dict[str, list[str]] = {n: list(self._g.successors(n)) for n in self._nodes}
        self._od_pool: list[tuple[str, str]] = []
        self._remain_cache: dict[tuple[str, str], float] = {}
        self._free_t: dict[tuple[str, str], float] = {}
        self._sp_from: dict[str, dict[str, float]] = {}
        # Static congested edge time BPR(bg + 1) and its APSP — cost-to-go the
        # transition actually charges, unlike free-flow remain.
        self._bpr_edge_t: dict[tuple[str, str], float] = {}
        self._sp_bpr_from: dict[str, dict[str, float]] = {}
        self._n_truncated_nodes = 0
        # peak -> (free_t, out, sp_from, bg_load, dens_cache, unc_cache, density, speed, unc)
        self._peak_bundle: dict[str, dict[str, Any]] = {}
        self._node_emb = {
            n: self._hash_embed(n, 8) for n in self._nodes
        }
        self._bg_hist = np.zeros(6, dtype=np.float32)
        self._bg_load = self._background_load()
        self._dens_cache = self._density_summaries()
        self._unc_cache = self._uncertainty_summaries()
        # free_t + out-order + all-pairs SP (cached per density peak)
        self._refresh_travel_caches(peak=self.peak_for_t(28800.0))

        # episode state
        self._t = 0.0
        self._step_i = 0
        self._ods: list[tuple[str, str]] = []
        self._pos: list[str] = []
        self._done: list[bool] = []
        self._travel: list[float] = []
        self._path_hist: list[list[str]] = []
        self._true_arrived: list[bool] = []
        # live multi-agent state (coordination features; usefulness = empirical)
        self._node_occ: dict[str, float] = {}
        self._live_edge: dict[tuple[str, str], float] = {}
        self._prev_remain: list[float] = []
        # Predicted same-step contention: edge -> #active agents whose
        # congested-greedy next hop is that edge (only co-located agents can
        # take an edge this step, so this is the load the transition will see).
        self._intent_edge: dict[tuple[str, str], int] = {}
        self._intent_of: list[tuple[str, str] | None] = []
        self._prior_load: list[dict[tuple[str, str], int]] = []
        self._social_of: list[tuple[str, str] | None] = []
        self._social_prior: list[dict[tuple[str, str], int]] = []
        self._pred_ext: list[dict[tuple[str, str], float]] = []
        self._shocks: list[dict[str, Any]] = []
        # OSM signals snapped onto this graph. Empty when the sidecar is absent.
        # Observation only marks presence. Phase and cycle stay in the transition.
        self._signals: set[str] = set()
        self._signal_offset: dict[str, float] = {}
        self._shock_edge: tuple[str, str] | None = None
        self._load_signals()
        # Reused between steps for vehicles that are not about to act.
        self._obs_cache: list[np.ndarray | None] = [None] * self.n_agents
        self._trip_cap: list[float] = [float("inf")] * self.n_agents
        self._merge_cache: dict[tuple[str, str], float] = {}
        self._approach_cache: dict[str, float] = {}

    @staticmethod
    def _is_alley(data: dict[str, Any]) -> bool:
        return data.get("road_class") == "alley" or data.get("layer") == "alley"

    def _load_graph(self) -> nx.DiGraph:
        if self.graph_path and Path(self.graph_path).exists():
            data = json.loads(Path(self.graph_path).read_text(encoding="utf-8"))
            g = nx.DiGraph()
            alleys = data["alleys"]
            for e in data["edge_list"]:
                a = alleys[e["alley_id"]]
                g.add_edge(
                    str(e["u"]),
                    str(e["v"]),
                    alley_id=e["alley_id"],
                    length_m=float(a["length_m"]),
                    road_class=a.get("road_class") or "",
                    layer=a.get("layer") or "",
                )
            return g
        from data_fusion.alley_graph import build_demo_alley_graph

        return build_demo_alley_graph()

    def _load_signals(self) -> None:
        """Static OSM program. Same file the SUMO net was built from."""
        candidates: list[Path] = []
        if self.graph_path:
            candidates.append(Path(self.graph_path).with_name("osm_signals_snapped.json"))
        candidates.append(Path(__file__).resolve().parents[2] / "sumo-env" / "quan4_osm_signals.json")
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        known = set(self._nodes)
        for row in data.get("signals") or []:
            node = str(row.get("node") or "")
            if node not in known:
                continue
            if self._g.in_degree(node) < 1 or self._g.out_degree(node) < 1:
                continue
            self._signals.add(node)
            self._signal_offset[node] = float(row.get("offset_s") or 0.0)

    # SUMO static program: red for the first red_s of each cycle, then green.
    # phase = (t - offset) mod cycle, matching SUMO's program shift.
    SIGNAL_CYCLE_S = 60.0
    SIGNAL_RED_S = 30.0

    def _red_wait(self, node: str, arrive: float) -> float:
        if node not in self._signals:
            return 0.0
        offset = float(self._signal_offset.get(node, 0.0))
        phase = (float(arrive) - offset) % self.SIGNAL_CYCLE_S
        if phase >= self.SIGNAL_RED_S:
            return 0.0
        return self.SIGNAL_RED_S - phase

    def _load_density_file(
        self, path: Path
    ) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
        if not path.exists():
            return {}, {}, {}
        rows = json.loads(path.read_text(encoding="utf-8"))
        dens: dict[str, float] = {}
        speeds: dict[str, float] = {}
        unc: dict[str, float] = {}
        for r in rows:
            aid = r.get("alley_id")
            if not aid:
                continue
            aid = str(aid)
            try:
                dens[aid] = float(r["density_k"])
            except (KeyError, TypeError, ValueError):
                pass
            try:
                speeds[aid] = float(r["speed_mps"])
            except (KeyError, TypeError, ValueError):
                pass
            try:
                unc[aid] = float(r["uncertainty"])
            except (KeyError, TypeError, ValueError):
                unc[aid] = 0.05
        return dens, speeds, unc

    @staticmethod
    def peak_for_t(t: float) -> str:
        sec = float(t)
        if sec < 12 * 3600:
            return "morning"
        if sec < 17 * 3600:
            return "afternoon"
        return "evening"

    def ensure_density_for_t(self, t: float) -> str | None:
        if not self.density_catalog:
            return self.peak_for_t(t)
        peak = self.peak_for_t(t)
        if peak == self._active_peak:
            return peak
        path = self.density_catalog.get(peak)
        if path is None or not path.exists():
            for name, p in self.density_catalog.items():
                if p.exists():
                    peak, path = name, p
                    break
            else:
                return None
        self._active_peak = peak
        self.density_path = path
        if peak in self._peak_bundle:
            self._restore_peak_bundle(peak)
            return peak
        self._density, self._speed, self._unc = self._load_density_file(path)
        self._dens_cache = self._density_summaries()
        self._unc_cache = self._uncertainty_summaries()
        self._bg_load = self._background_load()
        self._refresh_travel_caches(peak=peak)
        return peak

    def set_od_pool(self, pairs: list[tuple[str, str]]) -> None:
        self._od_pool = [(str(o), str(d)) for o, d in pairs if o != d]

    def warmup_peak_caches(self) -> None:
        """Build free-time/SP bundles for every catalog peak (pay once at spawn)."""
        if not self.density_catalog:
            return
        # representative seconds for morning / afternoon / evening
        for t in (8 * 3600, 14 * 3600, 19 * 3600):
            self.ensure_density_for_t(float(t))

    def _rebuild_out_order(self) -> None:
        """Order successors by congested edge time BPR(bg+1).

        Free-flow ordering made truncation keep exactly the hops Dijkstra wants
        and drop load-relieving exits. Node degree above max_degree is reported,
        never silently assumed away.
        """
        out: dict[str, list[str]] = {}
        n_trunc = 0
        for n in self._nodes:
            succ = list(self._g.successors(n))
            succ.sort(key=lambda v: (self._bpr_edge_t.get((n, v), 1e18), v))
            if len(succ) > self.max_degree:
                n_trunc += 1
            out[n] = succ
        self._out = out
        if n_trunc and n_trunc != self._n_truncated_nodes:
            print(
                f"[env] WARNING {n_trunc} nodes have out-degree > max_degree="
                f"{self.max_degree}; extra (slowest congested) exits are unreachable",
                flush=True,
            )
        self._n_truncated_nodes = n_trunc

    def _restore_peak_bundle(self, peak: str) -> None:
        b = self._peak_bundle[peak]
        self._density = b["density"]
        self._speed = b["speed"]
        self._unc = b["unc"]
        self._dens_cache = b["dens_cache"]
        self._unc_cache = b["unc_cache"]
        self._bg_load = b["bg_load"]
        self._bg_hist = b["bg_hist"]
        self._free_t = b["free_t"]
        self._out = b["out"]
        self._sp_from = b["sp_from"]
        self._bpr_edge_t = b["bpr_edge_t"]
        self._sp_bpr_from = b["sp_bpr_from"]
        for (u, v), ft in self._free_t.items():
            self._g.edges[u, v]["free_t"] = ft
        self._remain_cache.clear()

    def _refresh_travel_caches(self, peak: str | None = None) -> None:
        """Cache edge free-times + all-pairs SP (O(1) remain). Stored per peak."""
        free_t: dict[tuple[str, str], float] = {}
        for u, v in self._edge_index:
            ft = self._compute_edge_free_time(u, v)
            free_t[(u, v)] = ft
            self._g.edges[u, v]["free_t"] = ft
        self._free_t = free_t
        bpr_t: dict[tuple[str, str], float] = {}
        for u, v in self._edge_index:
            bt = self._bpr_time(u, v, float(self._bg_load.get((u, v), 0.0)) + 1.0)
            bpr_t[(u, v)] = bt
            self._g.edges[u, v]["bpr_t"] = bt
        self._bpr_edge_t = bpr_t
        self._rebuild_out_order()
        sp_from: dict[str, dict[str, float]] = {}
        sp_bpr: dict[str, dict[str, float]] = {}
        for src in self._nodes:
            sp_from[src] = nx.single_source_dijkstra_path_length(
                self._g, src, weight="free_t"
            )
            sp_bpr[src] = nx.single_source_dijkstra_path_length(
                self._g, src, weight="bpr_t"
            )
        self._sp_from = sp_from
        self._sp_bpr_from = sp_bpr
        self._remain_cache.clear()
        bg = np.array(list(self._bg_load.values()), dtype=np.float32)
        if bg.size:
            hist = np.histogram(bg, bins=6, range=(0.0, 4.0))[0].astype(np.float32)
            self._bg_hist = hist / max(float(hist.sum()), 1.0)
        else:
            self._bg_hist = np.zeros(6, dtype=np.float32)
        key = peak or self._active_peak or "default"
        self._peak_bundle[key] = {
            "density": self._density,
            "speed": self._speed,
            "unc": self._unc,
            "dens_cache": self._dens_cache,
            "unc_cache": self._unc_cache,
            "bg_load": self._bg_load,
            "bg_hist": self._bg_hist,
            "free_t": self._free_t,
            "out": self._out,
            "sp_from": self._sp_from,
            "bpr_edge_t": self._bpr_edge_t,
            "sp_bpr_from": self._sp_bpr_from,
        }

    def _background_load(self) -> dict[tuple[str, str], float]:
        out: dict[tuple[str, str], float] = {}
        for u, v in self._edge_index:
            aid = self._g.edges[u, v]["alley_id"]
            k = float(self._density.get(aid, 0.03))
            out[(u, v)] = float(np.clip(k / 0.06, 0.2, 3.0))
        return out

    def _compute_edge_free_time(self, u: str, v: str) -> float:
        data = self._g.edges[u, v]
        length = float(data["length_m"])
        aid = data["alley_id"]
        is_alley = self._is_alley(data)
        if aid in self._speed:
            speed = max(0.5, min(13.0, float(self._speed[aid])))
        else:
            k = self._density.get(aid, 0.03)
            v_free = 8.0 if is_alley else 13.0
            k_jam = 0.18
            speed = max(0.5, v_free * (1.0 - min(k, k_jam * 0.99) / k_jam))
        return length / speed

    def _edge_free_time(self, u: str, v: str) -> float:
        cached = getattr(self, "_free_t", {}).get((u, v))
        if cached is not None:
            return float(cached)
        return self._compute_edge_free_time(u, v)

    def _edge_unc(self, u: str, v: str) -> float:
        return float(self._unc.get(self._g.edges[u, v]["alley_id"], 0.05))

    def _bpr_time(self, u: str, v: str, load: float) -> float:
        t0 = self._edge_free_time(u, v)
        cap = max(0.5, self._cap[(u, v)])
        load_c = min(float(load), self.bpr_load_cap)
        return float(t0 * (1.0 + self.bpr_alpha * (load_c / cap) ** self.bpr_beta))

    def _pace(self, edge: tuple[str, str], n_veh: int, at: float | None = None) -> float:
        """Wall-seconds per free-flow-second at this occupancy. Piecewise constant.

        `at` evaluates scheduled load at a future time (informed forecast only).
        The obstacle factor is always the current one: it cannot be foreseen.
        """
        t0 = self._edge_free_time(edge[0], edge[1])
        if t0 <= 1e-8:
            return 1.0
        load = (
            float(self._bg_load.get(edge, 0.0))
            + float(max(0, n_veh))
            + self._exogenous_load(edge, at)
        )
        pace = max(1e-3, self._bpr_time(edge[0], edge[1], load) / t0)
        return pace * self._obstacle_factor(edge)

    def _storage(self, edge: tuple[str, str]) -> int:
        """How many vehicles fit in the alley at once. Full → entry is refused."""
        length = float(self._g.edges[edge[0], edge[1]]["length_m"])
        base = max(1, int(length / self.jam_spacing_m))
        if self._obstacle_factor(edge) > 1.0:
            return max(1, base // 2)
        return base

    def _exogenous_load(self, edge: tuple[str, str], at: float | None = None) -> float:
        """Residents or a school release in progress at `at` (default: now)."""
        now = float(getattr(self, "_sim", 0.0)) if at is None else float(at)
        total = 0.0
        for sh in getattr(self, "_shocks", []):
            if sh["edge"] != edge or sh["kind"] == "obstacle":
                continue
            if sh["t0"] <= now < sh["t1"]:
                total += float(sh["extra"])
        return total

    def _obstacle_factor(self, edge: tuple[str, str]) -> float:
        now = float(getattr(self, "_sim", 0.0))
        factor = 1.0
        for sh in getattr(self, "_shocks", []):
            if sh["edge"] == edge and sh["kind"] == "obstacle" and sh["t0"] <= now < sh["t1"]:
                factor = max(factor, 4.0)
        return factor

    # A school dismissal or residents leaving at peak hour follows a timetable.
    # An accident or a sudden blockage does not: nobody sees it before it starts.
    SCHEDULED_KINDS = ("egress", "school")

    def _shock_view(self, edge: tuple[str, str]) -> tuple[float, float]:
        """Countdown and magnitude of an event on this edge.

        Scheduled kinds show their countdown. An obstacle shows only once active.
        greedy_load's forecast uses only load already happening; greedy_informed
        also uses the timetable, so both see what MAPPO sees.
        """
        now = float(getattr(self, "_sim", 0.0))
        eta = 0.0
        mag = 0.0
        seen = False
        for sh in getattr(self, "_shocks", []):
            if sh["edge"] != edge or now >= sh["t1"]:
                continue
            if now < sh["t0"] and sh["kind"] not in self.SCHEDULED_KINDS:
                continue
            mass = 1.0 if sh["kind"] == "obstacle" else float(sh["extra"]) / 10.0
            if now < sh["t0"]:
                dt = float(sh["t0"] - now)
                if not seen or dt < eta:
                    eta = dt
                mag = max(mag, mass)
                seen = True
            else:
                eta = 0.0
                mag = max(mag, mass)
                seen = True
        return min(eta / 100.0, 50.0), mag

    def _merge_pressure(self, u: str, v: str) -> float:
        """Vehicles on other approaches whose free-flow path still uses (u, v).

        Someone standing at u does not count: the heuristic already sees them.
        Streams that have not reached the junction yet do not.
        """
        edge = (u, v)
        hit = self._merge_cache.get(edge)
        if hit is not None:
            return hit
        n = 0
        for i in range(self.n_agents):
            if self._done[i] or self._edge_of[i] == edge or self._pos[i] == u:
                continue
            if self._through_edge(self._pos[i], self._ods[i][1], u, v):
                n += 1
        out = float(n) / max(self.n_agents, 1)
        self._merge_cache[edge] = out
        return out

    def _copy_shocks(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for sh in raw:
            if "edge" in sh:
                u, v = sh["edge"]
            else:
                u, v = sh["u"], sh["v"]
            edge = (str(u), str(v))
            if edge not in self._cap:
                continue
            out.append(
                {
                    "kind": str(sh.get("kind", "egress")),
                    "edge": edge,
                    "t0": float(sh["t0"]),
                    "t1": float(sh["t1"]),
                    "extra": float(sh.get("extra", 0.0)),
                }
            )
        return out

    def _sample_shocks(self) -> None:
        """One seeded event on the shared alley: residents, school, or a blockage."""
        self._shocks = []
        if self.shock_rate <= 0.0 or float(self.rng.random()) > self.shock_rate:
            return
        edge = self._shock_edge if self._shock_edge in self._cap else None
        if edge is None:
            edge = self._overlap_edge if self._overlap_edge in self._cap else None
        if edge is None:
            for o, d in self._ods:
                for cand in self._edge_index:
                    if self._cap.get(cand, 8.0) <= 2.5 and self._through_edge(o, d, cand[0], cand[1]):
                        edge = cand
                        break
                if edge is not None:
                    break
        if edge is None:
            return
        kind = ("egress", "school", "obstacle")[int(self.rng.integers(0, 3))]
        t0 = float(self.rng.uniform(10.0, 80.0))
        if kind == "egress":
            extra, dur = 4.0, 30.0
        elif kind == "school":
            extra, dur = 8.0, 45.0
        else:
            extra, dur = 0.0, 60.0
        self._shocks = [
            {
                "kind": kind,
                "edge": (str(edge[0]), str(edge[1])),
                "t0": t0,
                "t1": t0 + dur,
                "extra": extra,
            }
        ]

    def _entry_wait(self, edge: tuple[str, str], n_ahead: int) -> float:
        """Seconds until a storage slot opens. n_ahead excludes the vehicle being scored."""
        storage = self._storage(edge)
        if n_ahead < storage:
            return 0.0
        n_wait = n_ahead - storage + 1
        t0 = max(1e-6, self._edge_free_time(edge[0], edge[1]))
        slot = t0 * self._pace(edge, storage) / storage
        return float(n_wait * slot)

    def _downstream_fill(self, node: str) -> float:
        """Max storage-fill of edges leaving `node`. The one-step heuristic ignores this."""
        nxts = self._neighbors(node)[: self.max_degree]
        if not nxts:
            return 0.0
        fills = [
            len(self._on_edge.get((node, v), [])) / self._storage((node, v)) for v in nxts
        ]
        return float(min(1.5, max(fills)))

    def _approaching(self, node: str) -> float:
        """Vehicles already on an edge that ends at `node`, not yet there."""
        hit = self._approach_cache.get(node)
        if hit is not None:
            return hit
        n = sum(1 for e in self._edge_of if e is not None and e[1] == node)
        out = float(n) / max(self.n_agents, 1)
        self._approach_cache[node] = out
        return out

    def _build_obs(self, refresh: set[int] | None = None) -> dict[str, np.ndarray]:
        """Local observations. Recompute only agents in `refresh` (None = all).

        Vehicles still inside an edge do not act this step, so their previous
        obs is kept for the critic mean. Ready agents always get a fresh vector.
        Reward and transition are unchanged.
        """
        self._merge_cache.clear()
        self._approach_cache.clear()
        if refresh is None:
            refresh = set(range(self.n_agents))
        obs: dict[str, np.ndarray] = {}
        for i, a in enumerate(self.agents):
            if i in refresh or self._obs_cache[i] is None:
                self._obs_cache[i] = self._local_obs(i)
            obs[a] = self._obs_cache[i]
        return obs

    def _schedule_breaks(self, edge: tuple[str, str], now: float) -> list[float]:
        """Future start/end times of timetabled events on this edge."""
        out: list[float] = []
        for sh in getattr(self, "_shocks", []):
            if sh["edge"] != edge or sh["kind"] not in self.SCHEDULED_KINDS:
                continue
            for b in (float(sh["t0"]), float(sh["t1"])):
                if b > now + 1e-9:
                    out.append(b)
        return sorted(out)

    def _forecast_entry(
        self, u: str, v: str, n_extra: int, informed: bool = False, me_extra: float = 0.0
    ) -> tuple[float, float]:
        """Own crossing time and the extra time imposed on vehicles already in.

        `n_extra` vehicles (lower-index decisions at this same instant) plus the
        vehicle being scored enter now at progress 0. Occupants keep their
        remaining free-flow distance. Pace is recomputed every time someone
        exits. A full alley is not entered: own cost is the wait plus a crossing
        at jam pace, and externality is 0 because the vehicle stays at the node.

        Private cost is `tt`. Social cost is `tt + ext`. With BPR exponent 4 the
        externality is several times the private congestion term, so a vehicle
        can still prefer the alley for itself while making the fleet slower.
        """
        edge = (u, v)
        t0 = max(1e-6, self._edge_free_time(u, v))
        now = float(self._sim)
        ids = list(self._on_edge.get(edge, []))
        n = len(ids)
        if n + int(n_extra) >= self._storage(edge):
            tt = self._entry_wait(edge, n + int(n_extra)) + (t0 + me_extra) * self._pace(
                edge, self._storage(edge)
            )
            return float(tt), 0.0
        last = float(self._edge_clock.get(edge, now))
        dprog = 0.0
        if n and now > last + 1e-9:
            dprog = (now - last) / self._pace(edge, n)
        exist = [
            max(0.0, t0 - (float(self._prog[j]) + dprog))
            for j in ids
            if t0 - (float(self._prog[j]) + dprog) > 1e-5
        ]

        breaks = self._schedule_breaks(edge, now) if informed else []

        def walls(n_new: int, last_extra: float = 0.0) -> list[float]:
            rem = list(exist) + [t0] * n_new
            if n_new and last_extra > 0.0:
                rem[-1] += last_extra
            out_w = [0.0] * len(rem)
            alive = [k for k, r in enumerate(rem) if r > 1e-5]
            wall = 0.0
            guard = 0
            while alive and guard < 128:
                guard += 1
                if informed:
                    f = self._pace(edge, len(alive), at=now + wall)
                else:
                    f = self._pace(edge, len(alive))
                step = min(rem[k] for k in alive)
                if informed:
                    nxt_b = next((b for b in breaks if b > now + wall + 1e-9), None)
                    if nxt_b is not None and now + wall + step * f > nxt_b + 1e-9:
                        step = (nxt_b - (now + wall)) / f
                wall += step * f
                done: list[int] = []
                for k in alive:
                    rem[k] -= step
                    if rem[k] <= 1e-5:
                        out_w[k] = wall
                        done.append(k)
                for k in done:
                    alive.remove(k)
            return out_w

        prior = max(0, int(n_extra))
        without = walls(prior)
        with_me = walls(prior + 1, me_extra)
        ext = 0.0
        for k in range(len(without)):
            ext += max(0.0, with_me[k] - without[k])
        tt = with_me[-1] if with_me else 0.0
        return float(tt), float(ext)

    def _forecast_tt(self, u: str, v: str, n_extra: int) -> float:
        """Wall time for one more vehicle to cross (u, v). See `_forecast_entry`."""
        tt, _ext = self._forecast_entry(u, v, n_extra)
        return tt

    def _remain_free(self, curr: str, dest: str) -> float:
        if curr == dest:
            return 0.0
        dist = self._sp_from.get(curr, {}).get(dest)
        if dist is not None:
            return float(dist)
        key = (curr, dest)
        if key in self._remain_cache:
            return self._remain_cache[key]
        # Fallback (should be rare if APSP built)
        try:
            total = float(
                nx.shortest_path_length(self._g, curr, dest, weight="free_t")
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            total = 1e5
        self._remain_cache[key] = total
        return total

    def _remain_bpr(self, curr: str, dest: str) -> float:
        """Cost-to-go under static congestion BPR(bg+1) — what the env charges a lone agent."""
        if curr == dest:
            return 0.0
        dist = self._sp_bpr_from.get(curr, {}).get(dest)
        return float(dist) if dist is not None else 1e5

    def _bpr_greedy_hop(self, i: int) -> tuple[str, str] | None:
        """Congested shortest-path next hop of agent i (within the action set)."""
        if self._done[i]:
            return None
        curr, dest = self._pos[i], self._ods[i][1]
        cand = self._allowed_next(i)
        if not cand:
            return None
        best = min(
            cand,
            key=lambda nxt: self._bpr_edge_t.get((curr, nxt), 1e18)
            + self._remain_bpr(nxt, dest),
        )
        return (curr, best)

    def _score_waiting(self, social: bool, informed: bool = False) -> tuple[
        list[tuple[str, str] | None],
        list[dict[tuple[str, str], int]],
        list[dict[tuple[str, str], float]],
        list[dict[tuple[str, str], float]],
        dict[tuple[str, str], int],
    ]:
        """Index-order next hop. Social adds the delay imposed on vehicles already in."""
        committed: dict[tuple[str, str], int] = {}
        prior: list[dict[tuple[str, str], int]] = [{} for _ in range(self.n_agents)]
        intent_of: list[tuple[str, str] | None] = [None] * self.n_agents
        pred_tt: list[dict[tuple[str, str], float]] = [{} for _ in range(self.n_agents)]
        pred_ext: list[dict[tuple[str, str], float]] = [{} for _ in range(self.n_agents)]
        ready = set(self._awaiting)
        for i in range(self.n_agents):
            if i not in ready or self._done[i]:
                continue
            curr, dest = self._pos[i], self._ods[i][1]
            cand = self._allowed_next(i)
            if not cand:
                continue
            prior[i] = {(curr, n): committed.get((curr, n), 0) for n in cand}
            scored: list[tuple[float, str]] = []
            for n in cand:
                tt, ext = self._forecast_entry(
                    curr, n, prior[i][(curr, n)], informed, self._uturn_extra(i, n)
                )
                pred_tt[i][(curr, n)] = tt
                pred_ext[i][(curr, n)] = ext
                has_light, q = self._hop_rank(n, dest, tt, ext, social)
                scored.append((has_light, q, n))
            _lit, _q, best = min(scored, key=lambda row: (row[0], row[1], row[2]))
            e = (curr, best)
            intent_of[i] = e
            committed[e] = committed.get(e, 0) + 1
        return intent_of, prior, pred_tt, pred_ext, committed

    def _refresh_intents(self) -> None:
        """Selfish next hop for agents who are at a node right now.

        Own forecast plus static remaining time. A known light is avoided when
        another exit exists. Phase and cycle are not inputs. argmin of the
        regret feature reproduces this rule. It does not reserve capacity for
        a stream still on another approach, and it does not look at a shock
        that has not started. Only the ready set acts.
        """
        intent, prior, pred_tt, _ext, committed = self._score_waiting(False)
        self._intent_of = intent
        self._prior_load = prior
        self._intent_edge = committed
        self._pred_tt = pred_tt

    def _density_summaries(self) -> np.ndarray:
        dens = np.array(
            [self._density.get(a, 0.03) for a in self._aids], dtype=np.float32
        )
        if dens.size == 0:
            return np.zeros(4, dtype=np.float32)
        return np.array(
            [
                float(np.mean(dens)),
                float(np.std(dens)),
                float(np.percentile(dens, 90)),
                float(np.max(dens)),
            ],
            dtype=np.float32,
        )

    def _uncertainty_summaries(self) -> np.ndarray:
        us = np.array([self._unc.get(a, 0.05) for a in self._aids], dtype=np.float32)
        if us.size == 0:
            return np.zeros(3, dtype=np.float32)
        return np.array(
            [float(np.mean(us)), float(np.percentile(us, 90)), float(np.max(us))],
            dtype=np.float32,
        )

    @staticmethod
    def _hash_embed(token: str, dim: int) -> np.ndarray:
        h = _stable_u32(str(token)) % (2**31)
        idx = np.arange(dim, dtype=np.float32)
        return np.sin((h % 997) * 0.1 + idx * 0.37).astype(np.float32)

    def _peak_onehot(self) -> np.ndarray:
        peak = self._active_peak or self.peak_for_t(self._t)
        oh = np.zeros(3, dtype=np.float32)
        oh[{"morning": 0, "afternoon": 1, "evening": 2}.get(peak, 0)] = 1.0
        return oh

    def n_actions(self) -> int:
        return self.max_degree

    def _neighbors(self, node: str) -> list[str]:
        return self._out.get(node, [])

    def _came_from(self, i: int) -> str | None:
        hist = self._path_hist[i]
        return hist[-2] if len(hist) >= 2 else None

    def _uturn_extra(self, i: int, nxt: str) -> float:
        return self.uturn_delay_s if nxt == self._came_from(i) else 0.0

    def _blocked_next(self, i: int) -> str | None:
        """The node agent i just came from, when going back is not allowed."""
        if not self.no_uturn or len(self._path_hist[i]) < 2:
            return None
        prev = self._path_hist[i][-2]
        neigh = self._neighbors(self._pos[i])[: self.max_degree]
        if prev not in neigh or len(neigh) < 2:
            return None
        return prev

    def _allowed_next(self, i: int) -> list[str]:
        """Exits agent i may take. Same set for every controller.

        A node from which the destination cannot be reached is not offered:
        Quận 4 has one edge into a dead end with no way out. Baselines never
        chose it (cost-to-go 1e5); a learner that did froze the episode.
        """
        neigh = self._neighbors(self._pos[i])[: self.max_degree]
        blocked = self._blocked_next(i)
        dest = self._ods[i][1]
        open_ = [n for n in neigh if n != blocked]
        reach = [n for n in open_ if n == dest or self._remain_free(n, dest) < 1e4]
        return reach or open_ or list(neigh)

    def action_mask(self, agent_idx: int) -> np.ndarray:
        mask = np.zeros(self.max_degree, dtype=np.float32)
        ready = set(getattr(self, "_awaiting", []))
        if self._done[agent_idx] or agent_idx not in ready:
            mask[0] = 1.0
            return mask
        neigh = self._neighbors(self._pos[agent_idx])
        if not neigh:
            mask[0] = 1.0
            return mask
        allowed = set(self._allowed_next(agent_idx))
        for i in range(min(len(neigh), self.max_degree)):
            if neigh[i] in allowed:
                mask[i] = 1.0
        return mask

    # obs = [t(2), peak(3), emb O/D/curr(24), scalars(7), dens(4), unc(3)] + neighbors
    # neighbor 14–15 = scheduled shock the heuristic does not read.
    # neighbor 16 = vehicles on other approaches that will still use this edge.
    # neighbor 17 = 1 if the next node has a light, else 0. Not the phase or cycle.
    # neighbor 18 = 1 if this exit goes back to the node just left.
    # neighbor 19 = times this car has already been at that node, /5, capped.
    # A memoryless policy ping-ponged A->B->A on short links (v3q diag: 88% of
    # failing cars in a <=3-node loop). A driver knows where they came from.
    OBS_SCALAR_DIM = 43
    NEIGH_FEATS = 20
    REGRET_IDX = 13
    SHOCK_ETA_IDX = 14
    SHOCK_MAG_IDX = 15
    MERGE_IDX = 16
    HAS_SIGNAL_IDX = 17
    BACK_IDX = 18
    VISITED_IDX = 19

    def _hop_rank(
        self, nxt: str, dest: str, tt: float, ext: float, social: bool
    ) -> tuple[float, float]:
        """(avoid, seconds). Avoid a light the vehicle would pass through.

        Stopping at that node is not a wait. Phase and cycle are not inputs.
        """
        avoid = 1.0 if nxt in self._signals and nxt != dest else 0.0
        seconds = tt + (ext if social else 0.0) + self._remain_bpr(nxt, dest)
        return avoid, seconds

    def neighbor_block(self, obs_vec: np.ndarray) -> np.ndarray:
        """[max_degree, NEIGH_FEATS] view of the neighbor features of one local obs."""
        s = self.OBS_SCALAR_DIM
        return obs_vec[s : s + self.max_degree * self.NEIGH_FEATS].reshape(
            self.max_degree, self.NEIGH_FEATS
        )

    def _local_obs(self, i: int) -> np.ndarray:
        o, d = self._ods[i]
        curr = self._pos[i]
        rem_here = self._remain_free(curr, d)
        rem_here_bpr = self._remain_bpr(curr, d)
        n_here = float(self._node_occ.get(curr, 0.0))
        revisits = 0.0
        if len(self._path_hist[i]) > 1:
            revisits = float(self._path_hist[i].count(curr) - 1)
        t_feat = np.array([self._t / 86400.0, self._step_i / max(self.max_steps, 1)], dtype=np.float32)
        feat_parts = [
            t_feat,
            self._peak_onehot(),
            self._node_emb.get(o, self._hash_embed(o, 8)),
            self._node_emb.get(d, self._hash_embed(d, 8)),
            self._node_emb.get(curr, self._hash_embed(curr, 8)),
            np.array(
                [
                    1.0 if self._done[i] else 0.0,
                    rem_here / 1000.0,
                    rem_here_bpr / 1000.0,
                    self._travel[i] / 1000.0,
                    n_here / max(self.n_agents, 1),
                    min(revisits, 5.0) / 5.0,
                    self._approaching(curr),
                ],
                dtype=np.float32,
            ),
            self._dens_cache,
            self._unc_cache,
        ]
        neigh = self._neighbors(curr)[: self.max_degree]
        nf = self.NEIGH_FEATS
        rows = np.zeros((self.max_degree, nf), dtype=np.float32)
        prior = self._prior_load[i] if i < len(self._prior_load) else {}
        pred = self._pred_tt[i] if i < len(getattr(self, "_pred_tt", [])) else {}
        allowed = set(self._allowed_next(i)) if not self._done[i] else set(neigh)
        came_from = self._came_from(i)
        q_vals: list[float] = []
        for j, nxt in enumerate(neigh):
            e = (curr, nxt)
            data = self._g.edges[curr, nxt]
            ft = self._edge_free_time(curr, nxt)
            bg = float(self._bg_load.get(e, 0.0))
            # others = same-instant lower ranks already committed to e.
            # live = vehicles physically still inside the alley.
            others = float(prior.get(e, 0))
            live = float(len(self._on_edge.get(e, [])))
            tt_pred = (
                float(pred[e])
                if e in pred
                else self._forecast_entry(
                    curr, nxt, int(others), False, self._uturn_extra(i, nxt)
                )[0]
            )
            avoid, q = self._hop_rank(nxt, d, tt_pred, 0.0, False)
            q_vals.append((avoid, q))
            eta, mag = self._shock_view(e)
            alley = self._is_alley(data)
            show_alley = alley and self.include_alley_info
            cap_feat = self._cap[e] if show_alley or not alley else 8.0
            rows[j, :13] = [
                1.0,
                1.0 if show_alley else 0.0,
                ft / 100.0,
                self._edge_unc(curr, nxt) if show_alley or not alley else 0.05,
                (bg / 5.0) if show_alley or not alley else 0.0,
                live / max(self.n_agents, 1),
                self._downstream_fill(nxt),
                1.0 / max(cap_feat, 0.5),
                self._remain_free(nxt, d) / 1000.0,
                (live + others) / max(self.n_agents, 1),
                tt_pred / 100.0,
                self._remain_bpr(nxt, d) / 1000.0,
                q / 1000.0,
            ]
            rows[j, self.SHOCK_ETA_IDX] = eta
            rows[j, self.SHOCK_MAG_IDX] = mag
            rows[j, self.MERGE_IDX] = self._merge_pressure(curr, nxt)
            rows[j, self.HAS_SIGNAL_IDX] = 1.0 if nxt in self._signals else 0.0
            rows[j, self.BACK_IDX] = 1.0 if nxt == came_from else 0.0
            rows[j, self.VISITED_IDX] = min(self._path_hist[i].count(nxt), 5) / 5.0
        open_q = [qv for j, qv in enumerate(q_vals) if neigh[j] in allowed]
        if open_q:
            best_light, best_q = min(open_q)
            for j, (lit, q) in enumerate(q_vals):
                # 0 on the hop the heuristic takes. A light is refused while
                # any exit without a light exists. The gap is not the red time.
                if neigh[j] not in allowed or lit > best_light:
                    rows[j, self.REGRET_IDX] = 50.0
                else:
                    rows[j, self.REGRET_IDX] = min((q - best_q) / 100.0, 50.0)
        feat_parts.append(rows.reshape(-1))
        feat = np.concatenate(feat_parts)
        if feat.size > self.compact_dim:
            raise ValueError(
                f"obs needs {feat.size} dims > compact_dim={self.compact_dim}; "
                "raise compact_dim instead of truncating neighbor features"
            )
        if feat.size < self.compact_dim:
            feat = np.pad(feat, (0, self.compact_dim - feat.size))
        return feat.astype(np.float32)

    def _global_state_from_obs(self, obs: dict[str, np.ndarray]) -> np.ndarray:
        """Build critic state from already-computed local obs (no recompute)."""
        locs = np.stack([obs[a] for a in self.agents], axis=0)
        mean_loc = locs.mean(axis=0)
        active = float(sum(1 for d in self._done if not d)) / self.n_agents
        # live crowding signal for central critic
        occ_vals = np.array(list(self._node_occ.values()), dtype=np.float32)
        if occ_vals.size:
            live_stats = np.array(
                [
                    float(np.mean(occ_vals)) / max(self.n_agents, 1),
                    float(np.max(occ_vals)) / max(self.n_agents, 1),
                    float(len(occ_vals)) / max(len(self._nodes), 1),
                ],
                dtype=np.float32,
            )
        else:
            live_stats = np.zeros(3, dtype=np.float32)
        return np.concatenate(
            [
                mean_loc,
                self._bg_hist,
                live_stats,
                np.array([active, self._step_i / self.max_steps], dtype=np.float32),
            ]
        ).astype(np.float32)

    def _global_state(self) -> np.ndarray:
        return self._global_state_from_obs(self._build_obs())

    def local_obs_dim(self) -> int:
        return self.compact_dim

    def global_state_dim(self) -> int:
        return int(self._global_state().shape[0])

    def _through_edge(self, o: str, d: str, u: str, v: str) -> bool:
        if o == d or o == v or d == u:
            return False
        ft = self._edge_free_time(u, v)
        ru = self._remain_free(o, u)
        rv = self._remain_free(v, d)
        rd = self._remain_free(o, d)
        if min(ru, rv, rd) >= 1e4 or rd < 40.0:
            return False
        return abs((ru + ft + rv) - rd) <= 1.0

    def _through_path(self, o: str, d: str, edges: list[tuple[str, str]]) -> bool:
        """True when every edge of the corridor lies on the free-flow shortest path."""
        if not edges or o == d:
            return False
        rd = self._remain_free(o, d)
        if rd >= 1e4 or rd < 40.0:
            return False
        acc = self._remain_free(o, edges[0][0])
        if acc >= 1e4:
            return False
        for u, v in edges:
            acc += self._edge_free_time(u, v)
            if abs(acc + self._remain_free(v, d) - rd) > 1.0:
                return False
        return True

    def _free_path(self, o: str, d: str) -> list[tuple[str, str]]:
        """Edges of one free-flow shortest path. Empty when o cannot reach d."""
        if o == d:
            return []
        edges: list[tuple[str, str]] = []
        cur = o
        for _ in range(64):
            if cur == d:
                return edges
            rd = self._remain_free(cur, d)
            if rd >= 1e4:
                return []
            nxt = None
            for cand in self._g.successors(cur):
                if abs(self._edge_free_time(cur, cand) + self._remain_free(cand, d) - rd) <= 1.0:
                    nxt = cand
                    break
            if nxt is None:
                return []
            edges.append((cur, nxt))
            cur = nxt
        return []

    def _fleet_overlap(
        self, ods: list[tuple[str, str]]
    ) -> tuple[dict[tuple[str, str], int], int, int]:
        """Edge counts, number of edges several vehicles share, and the busiest count."""
        counts: dict[tuple[str, str], int] = {}
        for o, d in ods:
            seen: set[tuple[str, str]] = set()
            for edge in self._free_path(o, d):
                if edge in seen:
                    continue
                seen.add(edge)
                counts[edge] = counts.get(edge, 0) + 1
        if not counts:
            return counts, 0, 0
        min_cross = 2 if len(ods) < 12 else 3
        crossed = sum(1 for c in counts.values() if c >= min_cross)
        busiest = max(counts.values())
        return counts, crossed, busiest

    def _balance_score(self, ods: list[tuple[str, str]]) -> float:
        """Reward paths that meet on several streets, and a pile-up on one alley."""
        n = max(len(ods), 1)
        counts, crossed, busiest = self._fleet_overlap(ods)
        if not counts:
            return -1e6
        meet = sum(c - 1 for c in counts.values() if c >= 2)
        share_cap = max(3, n // 4)
        pile = max(0, busiest - share_cap)
        score = float(meet + 4 * crossed - pile * n)
        if meet < max(1, n // 10):
            score -= float(n)
        return score

    def _draw_unique_ods(self, n: int) -> list[tuple[str, str]]:
        nodes = self._nodes
        used_o: set[str] = set()
        used_d: set[str] = set()
        ods: list[tuple[str, str]] = []
        for _ in range(max(200, n * 80)):
            if len(ods) >= n:
                break
            o, d = (str(x) for x in self.rng.choice(nodes, size=2, replace=False))
            if o in used_o or d in used_d:
                continue
            dist = self._remain_free(o, d)
            if dist < 40.0 or dist > 900.0 or dist >= 1e4:
                continue
            ods.append((o, d))
            used_o.add(o)
            used_d.add(d)
        if len(ods) < n:
            for o, d in self._fallback_unique_ods(n):
                if o in used_o or d in used_d:
                    continue
                ods.append((o, d))
                used_o.add(o)
                used_d.add(d)
                if len(ods) >= n:
                    break
        while len(ods) < n and ods:
            ods.append(ods[-1])
        return ods[:n]

    def _fallback_unique_ods(self, n: int) -> list[tuple[str, str]]:
        nodes = self._nodes
        used_o: set[str] = set()
        used_d: set[str] = set()
        ods: list[tuple[str, str]] = []
        for _ in range(n * 40):
            if len(ods) >= n:
                break
            o, d = (str(x) for x in self.rng.choice(nodes, size=2, replace=False))
            if o in used_o or d in used_d:
                continue
            dist = self._remain_free(o, d)
            if dist >= 1e4 or dist < 40.0:
                continue
            ods.append((o, d))
            used_o.add(o)
            used_d.add(d)
        while len(ods) < n and ods:
            ods.append(ods[-1])
        while len(ods) < n:
            a, b = (str(x) for x in self.rng.choice(nodes, size=2, replace=False))
            ods.append((a, b))
        return ods[:n]

    def _sample_ods(self) -> list[tuple[str, str]]:
        """Distinct origins and destinations whose paths meet, without one funnel.

        Draw several fleets and keep the one that shares several streets.
        A single alley carrying the whole fleet scores worse than the same
        number of meetings spread across a few streets. Nothing is required
        to pass a signal; a light only delays a vehicle that happens to arrive.
        """
        n = self.n_agents
        best: list[tuple[str, str]] | None = None
        best_score = -1e18
        best_counts: dict[tuple[str, str], int] = {}
        draws = 8 if n >= 40 else 16
        for _ in range(draws):
            ods = self._draw_unique_ods(n)
            score = self._balance_score(ods)
            if score > best_score:
                best_score = score
                best = ods
                best_counts, _crossed, _busiest = self._fleet_overlap(ods)
        ods = list(best or self._fallback_unique_ods(n))
        self.rng.shuffle(ods)
        min_share = 2 if n < 12 else 4
        ranked = sorted(best_counts.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))
        alleys = [e for e, c in ranked if c >= min_share and self._cap.get(e, 8.0) <= 2.5]
        shared = [e for e, c in ranked if c >= min_share]
        chosen = alleys[0] if alleys else (shared[0] if shared else None)
        self._overlap_edge = chosen
        self._overlap_corridor = [chosen] if chosen is not None else None
        self._shock_edge = chosen
        return ods[:n]

    def _assign_departures(self) -> None:
        n = self.n_agents
        span = self.depart_span_s
        if span <= 1e-6 or n == 1:
            self._depart = [0.0] * n
            return
        # Distinct release times spread over `span`. Permute so agent index is
        # not departure order and nobody waits at the curb for the others.
        slots = np.linspace(0.0, span, n)
        order = self.rng.permutation(n)
        self._depart = [0.0] * n
        for k, i in enumerate(order):
            self._depart[int(i)] = float(slots[k])

    def reset(
        self, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[dict[str, np.ndarray], np.ndarray, dict[str, Any]]:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        options = options or {}
        self._t = float(options.get("t", 28800.0))
        self.ensure_density_for_t(self._t)
        self._step_i = 0
        self._overlap_edge = None
        self._overlap_corridor = None
        self._shock_edge = None
        if "ods" in options:
            self._ods = [(str(a), str(b)) for a, b in options["ods"]][: self.n_agents]
            while len(self._ods) < self.n_agents:
                self._ods.append(self._ods[-1])
        else:
            self._ods = self._sample_ods()
        self._pos = [o for o, _ in self._ods]
        self._done = [o == d for o, d in self._ods]
        self._travel = [0.0] * self.n_agents
        self._city = [0.0] * self.n_agents
        self._path_hist = [[self._pos[i]] for i in range(self.n_agents)]
        self._true_arrived = [bool(self._done[i]) for i in range(self.n_agents)]
        self._live_edge = {}
        self._on_edge = {e: [] for e in self._edge_index}
        self._edge_clock = {}
        self._edge_of = [None] * self.n_agents
        self._prog = [0.0] * self.n_agents
        self._enter_t = [0.0] * self.n_agents
        self._exit_t = [0.0] * self.n_agents
        self._booked = [0.0] * self.n_agents
        self._released = [False] * self.n_agents
        self._queue_edge = [None] * self.n_agents
        self._queue_since = [0.0] * self.n_agents
        self._wake_at = [None] * self.n_agents
        self._awaiting = []
        self._sim = 0.0
        self._corr = [0.0] * self.n_agents
        self._pred_tt = [{} for _ in range(self.n_agents)]
        if "shocks" in options:
            self._shocks = self._copy_shocks(options["shocks"])
        else:
            self._sample_shocks()
        self._assign_departures()
        self._trip_cap = [
            max(self.trip_cap_min_s, self.trip_cap_mult * self._remain_bpr(o, d))
            if self.trip_cap_mult > 0.0
            else float("inf")
            for o, d in self._ods
        ]
        self._advance_to_ready()
        self._rebuild_node_occ()
        self._refresh_intents()
        self._prev_remain = [
            self._remain_free(self._pos[i], self._ods[i][1]) for i in range(self.n_agents)
        ]
        self._obs_cache = [None] * self.n_agents
        obs = self._build_obs()
        gstate = self._global_state_from_obs(obs)
        return obs, gstate, self._info_now()

    def _info_now(self) -> dict[str, Any]:
        ready = set(self._awaiting)
        return {
            "t": self._t,
            "sim_time": float(self._sim),
            "peak": self._active_peak or self.peak_for_t(self._t),
            "masks": {a: self.action_mask(i) for i, a in enumerate(self.agents)},
            "agent_acting": [i in ready and not self._done[i] for i in range(self.n_agents)],
            "overlap_edge": self._overlap_edge,
        }

    def _rebuild_node_occ(self) -> None:
        """Only vehicles waiting at a node. In-transit vehicles occupy the edge."""
        occ: dict[str, float] = {}
        ready = set(self._awaiting)
        for i in ready:
            if self._done[i]:
                continue
            p = self._pos[i]
            occ[p] = occ.get(p, 0.0) + 1.0
        for i, edge in enumerate(self._queue_edge):
            if edge is None or self._done[i]:
                continue
            p = self._pos[i]
            occ[p] = occ.get(p, 0.0) + 1.0
        self._node_occ = occ
        self._live_edge = {
            e: float(len(ids)) for e, ids in self._on_edge.items() if ids
        }

    def _emit(self, i: int, delta_s: float) -> None:
        """Charge (or refund) a change in a hop's wall time to agent i.

        Booked time moves with the scheduled exit, so the final residue at
        exit is ~0 when no unexpected vehicle enters.
        """
        if abs(delta_s) < 1e-4:
            return
        self._corr[i] -= float(delta_s) / self.travel_scale
        self._booked[i] += float(delta_s)

    def _sync_edge(self, edge: tuple[str, str], now: float) -> None:
        ids = self._on_edge.get(edge, [])
        last = float(self._edge_clock.get(edge, now))
        if ids and now > last + 1e-9:
            dprog = (now - last) / self._pace(edge, len(ids))
            for j in ids:
                self._prog[j] += dprog
        self._edge_clock[edge] = now

    def _forecast_exits(self, edge: tuple[str, str], now: float) -> None:
        ids = list(self._on_edge.get(edge, []))
        if not ids:
            return
        t0 = max(1e-6, self._edge_free_time(edge[0], edge[1]))
        rem = {j: max(0.0, t0 - self._prog[j]) for j in ids}
        alive = [j for j in ids if rem[j] > 1e-5]
        for j in ids:
            if rem[j] <= 1e-5:
                self._exit_t[j] = now
        wall = float(now)
        guard = 0
        while alive and guard < 64:
            guard += 1
            f = self._pace(edge, len(alive))
            step = min(rem[j] for j in alive)
            wall += step * f
            done: list[int] = []
            for j in alive:
                rem[j] -= step
                if rem[j] <= 1e-5:
                    self._exit_t[j] = wall
                    done.append(j)
            for j in done:
                alive.remove(j)

    def _commit_entry(
        self, i: int, u: str, v: str, now: float, extra_free: float = 0.0
    ) -> tuple[float, float]:
        """Put i on (u, v) at `now`. Return (own forecast tt, delay imposed on vehicles already inside).

        `extra_free` free-flow seconds are added before the link (a U-turn).
        """
        edge = (u, v)
        self._sync_edge(edge, now)
        before = {j: self._exit_t[j] for j in self._on_edge[edge]}
        self._on_edge[edge].append(i)
        self._edge_of[i] = edge
        self._prog[i] = -float(extra_free)
        self._enter_t[i] = now
        self._booked[i] = 0.0
        self._forecast_exits(edge, now)
        tt = float(self._exit_t[i] - now)
        self._booked[i] = tt
        ext = 0.0
        for j, old in before.items():
            delta = float(self._exit_t[j] - old)
            ext += max(0.0, delta)
            self._emit(j, delta)
        n_share = len(self._on_edge[edge])
        if self.share_coef > 0.0 and n_share >= 2 and self.reward_mode != "legacy":
            # Per extra vehicle already on the link, scaled by how narrow it is.
            # A long bypass shared by two cars is cheaper for the city than
            # five motorbikes in one alley. Own BPR time is unchanged.
            narrow = 8.0 / max(self._cap[edge], 0.5)
            pen = self.share_coef * (n_share - 1) * narrow
            self._city[i] += pen
            self._corr[i] -= pen / self.travel_scale
        return tt, ext

    def _settle_events(self, now: float) -> list[int]:
        """Apply exits and departures at `now`. Do not jump past the next decision."""
        self._reforecast_shocked(now)
        leaving = [
            i
            for i in range(self.n_agents)
            if self._edge_of[i] is not None and self._exit_t[i] <= now + 1e-4
        ]
        ready: list[int] = []
        touched: set[tuple[str, str]] = set()
        for i in leaving:
            edge = self._edge_of[i]
            assert edge is not None
            self._sync_edge(edge, now)
            actual = float(now - self._enter_t[i])
            self._emit(i, actual - self._booked[i])
            self._travel[i] += actual
            self._on_edge[edge].remove(i)
            self._edge_of[i] = None
            v = edge[1]
            self._pos[i] = v
            self._path_hist[i].append(v)
            touched.add(edge)
            if v == self._ods[i][1]:
                self._done[i] = True
                self._true_arrived[i] = True
            else:
                hold = self._red_wait(v, now)
                if hold > 1e-3:
                    self._wake_at[i] = now + hold
                    self._queue_since[i] = now
                    self._queue_edge[i] = None
                else:
                    ready.append(i)
        for edge in touched:
            before = {j: self._exit_t[j] for j in self._on_edge[edge]}
            self._forecast_exits(edge, now)
            for j, old in before.items():
                self._emit(j, float(self._exit_t[j] - old))
        for i in range(self.n_agents):
            if self._released[i] or self._done[i]:
                continue
            if self._depart[i] <= now + 1e-4:
                self._released[i] = True
                origin = self._ods[i][0]
                self._pos[i] = origin
                if origin == self._ods[i][1]:
                    self._done[i] = True
                    self._true_arrived[i] = True
                else:
                    hold = self._red_wait(origin, now)
                    if hold > 1e-3:
                        self._wake_at[i] = now + hold
                        self._queue_since[i] = now
                        self._queue_edge[i] = None
                    else:
                        ready.append(i)
        for i in range(self.n_agents):
            wake = self._wake_at[i]
            if wake is None or wake > now + 1e-4 or self._done[i]:
                continue
            waited = max(0.0, float(now - self._queue_since[i]))
            self._travel[i] += waited
            self._corr[i] -= waited / self.travel_scale
            self._queue_edge[i] = None
            self._wake_at[i] = None
            ready.append(i)
        return ready

    def _next_event_time(self) -> float | None:
        cands: list[float] = []
        for i in range(self.n_agents):
            if self._edge_of[i] is not None:
                cands.append(float(self._exit_t[i]))
            elif not self._released[i] and not self._done[i]:
                cands.append(float(self._depart[i]))
            elif self._wake_at[i] is not None:
                cands.append(float(self._wake_at[i]))
        now = float(self._sim)
        for sh in self._shocks:
            if sh["t0"] > now + 1e-6:
                cands.append(float(sh["t0"]))
            if sh["t1"] > now + 1e-6:
                cands.append(float(sh["t1"]))
        return min(cands) if cands else None

    def _reforecast_shocked(self, now: float) -> None:
        """A scheduled event just started or ended. Revise exits already in the alley."""
        edges = [
            sh["edge"]
            for sh in self._shocks
            if abs(now - float(sh["t0"])) <= 1e-3 or abs(now - float(sh["t1"])) <= 1e-3
        ]
        for edge in edges:
            ids = list(self._on_edge.get(edge) or [])
            if not ids:
                continue
            self._sync_edge(edge, now)
            before = {j: self._exit_t[j] for j in ids}
            self._forecast_exits(edge, now)
            for j, old in before.items():
                self._emit(j, float(self._exit_t[j] - old))

    def _advance_to_ready(self) -> None:
        """Move the clock to the next instant someone is at a node and must choose.

        The jump is the minimum pending exit or departure, never the max. A fast
        vehicle is decided while a slow one is still inside an alley.
        """
        self._awaiting = []
        limit = max(8, self.n_agents * self.max_steps + 2)
        for _ in range(limit):
            if all(self._done):
                return
            t = self._next_event_time()
            if t is None:
                return
            if t < self._sim - 1e-6:
                t = self._sim
            self._sim = float(t)
            ready = self._settle_events(self._sim)
            if ready:
                # A car only stops at a node, so the budget is checked there.
                # A node with no exit would never wake the car again.
                keep: list[int] = []
                for i in ready:
                    over = (
                        self.trip_cap_mult > 0.0
                        and self._sim - float(self._depart[i]) >= self._trip_cap[i]
                    )
                    if over or not self._neighbors(self._pos[i]):
                        self._truncate_agent(i, self._sim)
                    else:
                        keep.append(i)
                ready = keep
            if ready:
                self._awaiting = ready
                return

    def _shaping(self, curr: str, nxt: str, dest: str) -> float:
        rem_cap = float(self.reward_weights.get("truncate_remain_cap_s", 3600.0))
        r0 = min(rem_cap, self._remain_bpr(curr, dest))
        r1 = 0.0 if nxt == dest else min(rem_cap, self._remain_bpr(nxt, dest))
        return float(self.progress_shaping * (r0 - self.shaping_gamma * r1) / self.travel_scale)

    def _truncate_agent(self, i: int, now: float) -> None:
        """End agent i's trip as a failure. Same charge for every controller."""
        w = self.reward_weights
        scale = self.travel_scale if self.reward_mode != "legacy" else 40.0
        fail_mult = float(w.get("truncate_fail_mult", 4.0))
        fail_base = float(w.get("truncate_fail_base", 2000.0))
        rem_cap = float(w.get("truncate_remain_cap_s", 3600.0))
        if self._edge_of[i] is not None:
            edge = self._edge_of[i]
            self._sync_edge(edge, now)
            actual = max(0.0, now - self._enter_t[i])
            self._emit(i, actual - self._booked[i])
            self._travel[i] += actual
            self._on_edge[edge].remove(i)
            self._edge_of[i] = None
            self._pos[i] = edge[1]
        if self._wake_at[i] is not None:
            waited = max(0.0, now - self._queue_since[i])
            self._corr[i] -= waited / scale
            self._travel[i] += waited
            self._queue_edge[i] = None
            self._wake_at[i] = None
        # Additive, not max(floor, ...): a flat floor made every unfinished
        # trip cost the same, so a policy could bounce on short links and
        # never approach the destination. Each second still to go costs more.
        rem = min(rem_cap, self._remain_free(self._pos[i], self._ods[i][1]))
        pen = fail_base + fail_mult * rem
        self._corr[i] -= pen / scale
        self._travel[i] += pen
        self._done[i] = True

    def _force_truncate(self) -> None:
        now = float(self._sim)
        for i in range(self.n_agents):
            if not self._done[i]:
                self._truncate_agent(i, now)
        self._awaiting = []

    def step(
        self, actions: dict[str, int]
    ) -> tuple[
        dict[str, np.ndarray],
        dict[str, float],
        dict[str, bool],
        dict[str, bool],
        np.ndarray,
        dict[str, Any],
    ]:
        # One decision epoch. Only vehicles at a node right now move. The clock
        # then advances to the next arrival or departure — other vehicles keep
        # traversing and are not asked to wait.
        self._corr = [0.0] * self.n_agents
        imm = [0.0] * self.n_agents
        w = self.reward_weights
        legacy = self.reward_mode == "legacy"
        scale = self.travel_scale
        now = float(self._sim)
        for i in sorted(self._awaiting):
            if self._done[i]:
                continue
            a = self.agents[i]
            curr = self._pos[i]
            neigh = self._neighbors(curr)[: self.max_degree]
            if not neigh:
                continue
            raw = int(actions.get(a, 0)) % self.max_degree
            mask = self.action_mask(i)
            if raw >= len(neigh) or mask[raw] < 0.5:
                raw = int(np.argmax(mask))
            if raw >= len(neigh):
                continue
            v = neigh[raw]
            edge = (curr, v)
            if len(self._on_edge[edge]) >= self._storage(edge):
                exits = [self._exit_t[j] for j in self._on_edge[edge]]
                self._queue_edge[i] = edge
                self._queue_since[i] = now
                self._wake_at[i] = min(exits) if exits else now + 0.5
                continue
            tt, ext = self._commit_entry(i, curr, v, now, self._uturn_extra(i, v))
            if legacy:
                cap = max(0.5, self._cap[(curr, v)])
                load = float(self._bg_load.get((curr, v), 0.0)) + float(
                    len(self._on_edge[(curr, v)])
                )
                cong = (min(load, self.bpr_load_cap) / cap) ** self.bpr_beta
                imm[i] = float(
                    -(
                        w["w_T"] * (tt / 50.0)
                        + w["w_C"] * cong
                        + w["w_step"]
                    )
                )
            else:
                # travel: own traversal only. The pile penalty is already in
                # _corr, for every controller. marginal adds the delay imposed
                # on other vehicles a second time and is not the compared score.
                cost = tt + (ext if self.reward_mode == "marginal" else 0.0)
                imm[i] = float(-cost / scale)
                if self.progress_shaping > 0.0:
                    imm[i] += self._shaping(curr, v, self._ods[i][1])
        self._awaiting = []
        self._advance_to_ready()

        self._step_i += 1
        truncated = self._step_i >= self.max_steps
        if truncated:
            self._force_truncate()

        self._rebuild_node_occ()
        self._refresh_intents()
        self._prev_remain = [
            0.0
            if self._done[i]
            else self._remain_free(self._pos[i], self._ods[i][1])
            for i in range(self.n_agents)
        ]
        # Only vehicles at a node need a fresh decision vector this step.
        obs = self._build_obs(refresh=set(self._awaiting))
        terms = {a: bool(self._done[i]) for i, a in enumerate(self.agents)}
        truncs = {a: bool(truncated and terms[a]) for a in self.agents}
        gstate = self._global_state_from_obs(obs)
        rewards = {
            a: float(imm[i] + self._corr[i]) for i, a in enumerate(self.agents)
        }
        travels = list(self._travel)
        t_arr = np.asarray(travels, dtype=np.float64)
        t_bar = float(np.mean(t_arr))
        cvar_thr = float(np.quantile(t_arr, 0.9))
        cvar = (
            float(np.mean(t_arr[t_arr >= cvar_thr])) if np.any(t_arr >= cvar_thr) else t_bar
        )
        n_true = int(sum(self._true_arrived))
        occ_loads = list(self._live_edge.values())
        team_cong = float(np.mean(occ_loads)) if occ_loads else 0.0
        info = self._info_now()
        info.update(
            {
                "travels": travels,
                "fleet_mean": t_bar,
                "fleet_cvar90": cvar,
                "congestion": team_cong,
                "n_arrived": int(sum(self._done)),
                "n_true_arrived": n_true,
                "arrival_rate": float(n_true) / max(self.n_agents, 1),
                "truncated": bool(truncated),
                "step": self._step_i,
                "all_done": all(self._done),
                "agent_done": [bool(x) for x in self._done],
                "immediate": list(imm),
                "correction": list(self._corr),
                "mean_progress": 0.0,
            }
        )
        return obs, rewards, terms, truncs, gstate, info

    # ----- baselines (micro) -----

    def baseline_dijkstra_actions(self) -> dict[str, int]:
        """Free-flow shortest-path next hop: argmin free_t(curr,nxt) + remain_free(nxt)."""
        acts = {}
        for i, a in enumerate(self.agents):
            if self._done[i]:
                acts[a] = 0
                continue
            curr, dest = self._pos[i], self._ods[i][1]
            # Only actionable neighbors (same truncation as mask / greedy_load).
            cand = self._neighbors(curr)[: self.max_degree]
            if not cand:
                acts[a] = 0
                continue
            allowed = set(self._allowed_next(i))
            best_j, best_d = 0, 1e18
            for j, nxt in enumerate(cand):
                if nxt not in allowed:
                    continue
                d = self._edge_free_time(curr, nxt) + self._remain_free(nxt, dest)
                if d < best_d:
                    best_d, best_j = d, j
            acts[a] = best_j
        return acts

    def baseline_dijkstra_bpr_actions(self) -> dict[str, int]:
        """Congestion-aware static Dijkstra: shortest path under BPR(bg+1) edge times."""
        acts = {}
        for i, a in enumerate(self.agents):
            e = self._bpr_greedy_hop(i)
            if e is None:
                acts[a] = 0
                continue
            acts[a] = self._neighbors(e[0]).index(e[1])
        return acts

    def baseline_random_actions(self) -> dict[str, int]:
        acts = {}
        for i, a in enumerate(self.agents):
            mask = self.action_mask(i)
            valid = np.where(mask > 0.5)[0]
            acts[a] = int(self.rng.choice(valid)) if len(valid) else 0
        return acts

    def baseline_social_actions(self) -> dict[str, int]:
        """Diagnostic only: greedy_load plus delay imposed on vehicles already inside.

        Not the training teacher. On the nominal alley the gap versus greedy_load
        is a few percent, because the mouth still has another exit.
        """
        intent, _prior, _tt, _ext, _committed = self._score_waiting(True)
        acts: dict[str, int] = {}
        for i, a in enumerate(self.agents):
            e = intent[i]
            acts[a] = 0 if e is None else self._neighbors(e[0]).index(e[1])
        return acts

    def baseline_greedy_informed_actions(self) -> dict[str, int]:
        """greedy_load with the timetable MAPPO sees: scheduled school or resident
        load enters the forecast before it starts. Accidents stay unforeseen.

        Fairness control. If MAPPO beats this, the gain is not extra information.
        """
        intent, _prior, _tt, _ext, _committed = self._score_waiting(False, informed=True)
        acts: dict[str, int] = {}
        for i, a in enumerate(self.agents):
            e = intent[i]
            acts[a] = 0 if e is None else self._neighbors(e[0]).index(e[1])
        return acts

    def baseline_greedy_load_actions(self) -> dict[str, int]:
        """Sequential load-aware router: own forecast + congested cost-to-go.

        A next node with a light is skipped when another exit exists. The phase
        and the cycle are not known here. Agents are assigned in index order;
        each sees the loads committed by lower-index agents at its node this
        step, so argmin of the regret feature reproduces this rule.
        """
        acts: dict[str, int] = {}
        for i, a in enumerate(self.agents):
            e = self._intent_of[i] if i < len(self._intent_of) else None
            acts[a] = 0 if e is None else self._neighbors(e[0]).index(e[1])
        return acts

    def roll_baseline(self, mode: str, seed: int | None = None) -> dict[str, float]:
        """Run full episode with a baseline policy; return fleet metrics."""
        obs, g, info = self.reset(seed=seed) if seed is not None else (None, None, None)
        if seed is None:
            # assume already reset
            pass
        else:
            pass
        # Always use current episode state after reset by caller
        for _ in range(self.max_steps):
            if mode == "dijkstra":
                acts = self.baseline_dijkstra_actions()
            elif mode == "dijkstra_bpr":
                acts = self.baseline_dijkstra_bpr_actions()
            elif mode == "random":
                acts = self.baseline_random_actions()
            elif mode == "greedy_load":
                acts = self.baseline_greedy_load_actions()
            elif mode == "greedy_informed":
                acts = self.baseline_greedy_informed_actions()
            else:
                raise ValueError(mode)
            _, _, _, _, _, step_info = self.step(acts)
            if step_info["all_done"]:
                break
        return {
            "fleet_mean": float(np.mean(self._travel)),
            "fleet_cvar90": float(
                np.mean(
                    np.sort(self._travel)[int(0.9 * (len(self._travel) - 1)) :]
                )
            ),
            "congestion": float(step_info.get("congestion", 0.0)),
            "n_arrived": int(sum(1 for d in self._done if d)),
        }
