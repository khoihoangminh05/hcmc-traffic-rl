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
        compact_dim: int = 160,
        bpr_alpha: float = 0.15,
        bpr_beta: float = 4.0,
        bpr_load_cap: float = 12.0,
        corridor_prob: float = 0.4,
        reward_weights: dict[str, float] | None = None,
        density_catalog: dict[str, Path] | None = None,
        reward_mode: str = "marginal",
        travel_scale: float = 1000.0,
    ) -> None:
        if reward_mode not in ("marginal", "travel", "legacy"):
            raise ValueError(f"reward_mode={reward_mode!r}")
        # marginal: -(own BPR tt + delay imposed on co-movers) — difference reward
        #           for the fleet objective (system optimum, exact per-step credit).
        # travel:   -(own BPR tt) — selfish, Wardrop-style.
        # legacy:   v1–v2h shaped reward (free-flow progress, cong, revisit, team).
        self.reward_mode = reward_mode
        self.travel_scale = max(1.0, float(travel_scale))
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
        cand = self._neighbors(curr)[: self.max_degree]
        if not cand:
            return None
        best = min(
            cand,
            key=lambda nxt: self._bpr_edge_t.get((curr, nxt), 1e18)
            + self._remain_bpr(nxt, dest),
        )
        return (curr, best)

    def _refresh_intents(self) -> None:
        """Rank-ordered contention (agent index = rank, like a vehicle id).

        Agent i sees, per exit, how many lower-index agents at its node commit to
        it under the sequential load-aware rule. Without this, co-located agents
        with one OD have identical obs, so a shared deterministic policy must
        send the whole platoon down one edge (BPR blows up quartically there).
        """
        committed: dict[tuple[str, str], int] = {}
        prior: list[dict[tuple[str, str], int]] = [{} for _ in range(self.n_agents)]
        intent_of: list[tuple[str, str] | None] = [None] * self.n_agents
        for i in range(self.n_agents):
            if self._done[i]:
                continue
            curr, dest = self._pos[i], self._ods[i][1]
            cand = self._neighbors(curr)[: self.max_degree]
            if not cand:
                continue
            prior[i] = {(curr, n): committed.get((curr, n), 0) for n in cand}
            best = min(
                cand,
                key=lambda n: self._bpr_time(
                    curr,
                    n,
                    float(self._bg_load.get((curr, n), 0.0))
                    + 1.0
                    + prior[i][(curr, n)],
                )
                + self._remain_bpr(n, dest),
            )
            e = (curr, best)
            intent_of[i] = e
            committed[e] = committed.get(e, 0) + 1
        self._intent_of = intent_of
        self._prior_load = prior
        self._intent_edge = committed

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

    def action_mask(self, agent_idx: int) -> np.ndarray:
        mask = np.zeros(self.max_degree, dtype=np.float32)
        if self._done[agent_idx]:
            mask[0] = 1.0
            return mask
        neigh = self._neighbors(self._pos[agent_idx])
        if not neigh:
            mask[0] = 1.0
            return mask
        for i in range(min(len(neigh), self.max_degree)):
            mask[i] = 1.0
        return mask

    # obs = [t(2), peak(3), emb O/D/curr(24), scalars(6), dens(4), unc(3)] + neighbors
    OBS_SCALAR_DIM = 42
    NEIGH_FEATS = 14
    REGRET_IDX = 13

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
        q_vals: list[float] = []
        for j, nxt in enumerate(neigh):
            e = (curr, nxt)
            data = self._g.edges[curr, nxt]
            ft = self._edge_free_time(curr, nxt)
            bg = float(self._bg_load.get(e, 0.0))
            # Load this step = bg + every agent that takes e now; only agents at
            # `curr` can. Lower-rank commitments are known, higher ranks follow.
            others = float(prior.get(e, 0))
            tt_pred = self._bpr_time(curr, nxt, bg + 1.0 + others)
            rem_bpr = self._remain_bpr(nxt, d)
            q = tt_pred + rem_bpr
            q_vals.append(q)
            rows[j, :13] = [
                1.0,
                1.0 if self._is_alley(data) else 0.0,
                ft / 100.0,
                self._edge_unc(curr, nxt),
                bg / 5.0,
                float(self._live_edge.get(e, 0.0)) / max(self.n_agents, 1),
                float(self._node_occ.get(nxt, 0.0)) / max(self.n_agents, 1),
                1.0 / max(self._cap[e], 0.5),
                self._remain_free(nxt, d) / 1000.0,
                others / max(self.n_agents, 1),
                tt_pred / 100.0,
                rem_bpr / 1000.0,
                q / 1000.0,
            ]
        if q_vals:
            q_min = min(q_vals)
            for j, q in enumerate(q_vals):
                # regret vs best hop under predicted load (0 = congested-optimal)
                rows[j, self.REGRET_IDX] = min((q - q_min) / 100.0, 50.0)
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
        obs = {a: self._local_obs(i) for i, a in enumerate(self.agents)}
        return self._global_state_from_obs(obs)

    def local_obs_dim(self) -> int:
        return self.compact_dim

    def global_state_dim(self) -> int:
        return int(self._global_state().shape[0])

    def _sample_ods(self) -> list[tuple[str, str]]:
        pool = self._od_pool
        if not pool:
            out = []
            for _ in range(self.n_agents):
                a, b = self.rng.choice(self._nodes, size=2, replace=False)
                out.append((str(a), str(b)))
            return out
        if self.rng.random() < self.corridor_prob and len(pool) >= 2:
            anchor = pool[int(self.rng.integers(0, len(pool)))]
            scored = sorted(
                pool,
                key=lambda od: abs(_stable_u32(od[0]) - _stable_u32(anchor[0])) % 997
                + abs(_stable_u32(od[1]) - _stable_u32(anchor[1])) % 997,
            )
            picks = scored[: self.n_agents]
            while len(picks) < self.n_agents:
                picks.append(pool[int(self.rng.integers(0, len(pool)))])
            self.rng.shuffle(picks)
            return picks[: self.n_agents]
        idx = self.rng.choice(len(pool), size=self.n_agents, replace=True)
        return [pool[int(i)] for i in idx]

    def reset(
        self, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[dict[str, np.ndarray], np.ndarray, dict[str, Any]]:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        options = options or {}
        self._t = float(options.get("t", 28800.0))
        self.ensure_density_for_t(self._t)
        self._step_i = 0
        if "ods" in options:
            self._ods = [(str(a), str(b)) for a, b in options["ods"]][: self.n_agents]
            while len(self._ods) < self.n_agents:
                self._ods.append(self._ods[-1])
        else:
            self._ods = self._sample_ods()
        self._pos = [o for o, _ in self._ods]
        self._done = [o == d for o, d in self._ods]
        self._travel = [0.0] * self.n_agents
        self._path_hist = [[self._pos[i]] for i in range(self.n_agents)]
        self._true_arrived = [bool(self._done[i]) for i in range(self.n_agents)]
        self._live_edge = {}
        self._rebuild_node_occ()
        self._refresh_intents()
        self._prev_remain = [
            self._remain_free(self._pos[i], self._ods[i][1]) for i in range(self.n_agents)
        ]
        obs = {a: self._local_obs(i) for i, a in enumerate(self.agents)}
        gstate = self._global_state_from_obs(obs)
        info = {
            "t": self._t,
            "peak": self._active_peak or self.peak_for_t(self._t),
            "masks": {a: self.action_mask(i) for i, a in enumerate(self.agents)},
        }
        return obs, gstate, info

    def _rebuild_node_occ(self) -> None:
        occ: dict[str, float] = {}
        for i, p in enumerate(self._pos):
            if self._done[i]:
                continue
            occ[p] = occ.get(p, 0.0) + 1.0
        self._node_occ = occ

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
        # resolve intended edges
        intended: list[tuple[str, str] | None] = [None] * self.n_agents
        edge_counts: dict[tuple[str, str], int] = {}
        for i, a in enumerate(self.agents):
            if self._done[i]:
                continue
            curr = self._pos[i]
            neigh = self._neighbors(curr)
            if not neigh:
                continue
            raw = int(actions.get(a, 0)) % self.max_degree
            mask = self.action_mask(i)
            if mask[raw] < 0.5:
                raw = int(np.argmax(mask))
            if raw < len(neigh):
                e = (curr, neigh[raw])
                intended[i] = e
                edge_counts[e] = edge_counts.get(e, 0) + 1

        w = self.reward_weights
        legacy = self.reward_mode == "legacy"
        scale = self.travel_scale
        rewards: dict[str, float] = {}
        cong_vals: list[float] = []
        progress_vals: list[float] = []
        for i, a in enumerate(self.agents):
            if self._done[i]:
                rewards[a] = 0.0
                progress_vals.append(0.0)
                continue
            e = intended[i]
            if e is None:
                # dead end: no travel happens; truncation charges the failure
                rewards[a] = -0.5 if legacy else 0.0
                progress_vals.append(0.0)
                continue
            u, v = e
            n_e = float(edge_counts.get(e, 0))
            load_e = float(self._bg_load.get(e, 0.0)) + n_e
            tt = self._bpr_time(u, v, load_e)
            cap = max(0.5, self._cap[e])
            cong = (min(load_e, self.bpr_load_cap) / cap) ** self.bpr_beta
            risk = self._edge_unc(u, v) * float(self._g.edges[u, v]["length_m"]) / 100.0
            rem_before = (
                self._prev_remain[i]
                if i < len(self._prev_remain)
                else self._remain_free(u, self._ods[i][1])
            )
            self._travel[i] += tt
            self._pos[i] = v
            revisit = 1.0 if v in self._path_hist[i] else 0.0
            self._path_hist[i].append(v)
            arrived = v == self._ods[i][1]
            if arrived:
                self._done[i] = True
                self._true_arrived[i] = True
                rem_after = 0.0
            else:
                rem_after = self._remain_free(v, self._ods[i][1])
            progress = (rem_before - rem_after) / 50.0
            progress_vals.append(float(progress))
            cong_vals.append(float(cong))
            if legacy:
                cost = (
                    w["w_T"] * (tt / 50.0)
                    + w["w_C"] * cong
                    + w["w_R"] * risk
                    + w["w_step"]
                    + w.get("w_revisit", 0.25) * revisit
                )
                bonus = w["arrive_bonus"] if arrived else 0.0
                shaped = w.get("w_progress", 0.4) * progress
                rewards[a] = float(-cost + bonus + shaped)
                continue
            # Sum of rewards over an episode = -(own travel [+ externality]) / scale,
            # so maximizing return is minimizing the reported fleet travel time.
            cost = tt
            if self.reward_mode == "marginal" and n_e > 1.0:
                # Delay this agent adds to each of the other n_e-1 agents on e.
                ext = self._bpr_time(u, v, load_e) - self._bpr_time(u, v, load_e - 1.0)
                cost += (n_e - 1.0) * ext
            rewards[a] = float(-cost / scale)

        team_cong = float(np.mean(cong_vals)) if cong_vals else 0.0
        w_team = float(w.get("w_team", 0.0)) if legacy else 0.0
        if w_team > 0 and cong_vals:
            for a in self.agents:
                if a in rewards:
                    rewards[a] -= w_team * team_cong

        self._live_edge = {
            e: float(c) for e, c in edge_counts.items() if e is not None
        }
        self._rebuild_node_occ()
        self._prev_remain = [
            0.0
            if self._done[i]
            else self._remain_free(self._pos[i], self._ods[i][1])
            for i in range(self.n_agents)
        ]

        self._step_i += 1
        truncated = self._step_i >= self.max_steps
        if truncated:
            # Free-flow remain under-penalizes failure vs congested Dijkstra success.
            # Use inflated fail cost so non-arrival cannot "win" on fleet_mean.
            fail_mult = float(w.get("truncate_fail_mult", 4.0))
            fail_floor = float(w.get("truncate_fail_floor", 8000.0))
            for i in range(self.n_agents):
                if not self._done[i]:
                    rem = self._remain_free(self._pos[i], self._ods[i][1])
                    pen = max(fail_floor, fail_mult * rem)
                    pen_scale = 40.0 if legacy else scale
                    rewards[self.agents[i]] = rewards.get(self.agents[i], 0.0) - pen / pen_scale
                    self._travel[i] += pen
                    self._done[i] = True

        self._refresh_intents()
        obs = {a: self._local_obs(i) for i, a in enumerate(self.agents)}
        terms = {a: bool(self._done[i]) for i, a in enumerate(self.agents)}
        truncs = {a: bool(truncated and terms[a]) for a in self.agents}
        gstate = self._global_state_from_obs(obs)
        travels = list(self._travel)
        t_arr = np.asarray(travels, dtype=np.float64)
        t_bar = float(np.mean(t_arr))
        cvar_thr = float(np.quantile(t_arr, 0.9))
        cvar = float(np.mean(t_arr[t_arr >= cvar_thr])) if np.any(t_arr >= cvar_thr) else t_bar
        n_true = int(sum(self._true_arrived))
        info = {
            "travels": travels,
            "fleet_mean": t_bar,
            "fleet_cvar90": cvar,
            "congestion": team_cong,
            # n_arrived includes truncate-forced done; n_true_arrived is destination hits
            "n_arrived": int(sum(self._done)),
            "n_true_arrived": n_true,
            "arrival_rate": float(n_true) / max(self.n_agents, 1),
            "truncated": bool(truncated),
            "step": self._step_i,
            "all_done": all(self._done),
            "agent_done": [bool(x) for x in self._done],
            "masks": {a: self.action_mask(i) for i, a in enumerate(self.agents)},
            "mean_progress": float(np.mean(progress_vals)) if progress_vals else 0.0,
        }
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
            best_j, best_d = 0, 1e18
            for j, nxt in enumerate(cand):
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

    def baseline_greedy_load_actions(self) -> dict[str, int]:
        """Sequential load-aware router: BPR(bg + already-assigned + 1) + congested cost-to-go.

        Agents are assigned in index order; each sees the loads committed by
        lower-index agents at its node this step — exactly the `others` the obs
        exposes, so argmin of the regret feature reproduces this rule. The old
        0.85·remain_free weighting made it loop (arr≈0.18).
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
