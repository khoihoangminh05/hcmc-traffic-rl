"""Multi-agent K-path env with BPR congestion (MAPPO / RESEARCH_ONE_PAPER).

N agents choose paths simultaneously; edge loads determine travel times.
Partial local obs; global state available for centralized critic (CTDE).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np


@dataclass
class PathCand:
    nodes: list[str]
    edge_keys: list[tuple[str, str]]
    free_time: float  # t0 sum without agent congestion
    risk: float
    n_edges: int
    alley_frac: float
    mean_u: float
    label: str
    valid: bool = True


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


class MultiAgentPathEnv:
    """N-agent joint path choice under BPR congestion + multi-objective reward."""

    metadata = {"name": "mappo_alley_v1"}

    def __init__(
        self,
        density_path: Path,
        graph_path: Path | None = None,
        seed: int = 0,
        n_agents: int = 16,
        k_paths: int = 8,
        compact_dim: int = 96,
        bpr_alpha: float = 0.15,
        bpr_beta: float = 4.0,
        corridor_prob: float = 0.5,
        reward_weights: dict[str, float] | None = None,
        density_catalog: dict[str, Path] | None = None,
    ) -> None:
        self.density_path = Path(density_path)
        self.graph_path = graph_path
        self.n_agents = max(2, int(n_agents))
        self.k_paths = max(2, int(k_paths))
        self.compact_dim = max(64, int(compact_dim))
        self.bpr_alpha = float(bpr_alpha)
        self.bpr_beta = float(bpr_beta)
        self.corridor_prob = float(corridor_prob)
        self.reward_weights = {
            "w_T": 1.0,
            "w_S": 0.35,
            "w_R": 0.15,
            "w_F": 0.1,
            "w_C": 0.25,
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
        self._eid = {e: i for i, e in enumerate(self._edge_index)}
        self._cap = {
            e: _capacity_for(self._g.edges[e[0], e[1]]) for e in self._edge_index
        }
        self._aids = sorted({d["alley_id"] for _, _, d in self._g.edges(data=True)})
        self._nodes = sorted(self._g.nodes())
        self._od_pool: list[tuple[str, str]] = []
        self._t = 0.0
        self._ods: list[tuple[str, str]] = []
        self._cands: list[list[PathCand]] = []
        self._action_mask: list[np.ndarray] = []
        self._dens_cache = self._density_summaries()
        self._unc_cache = self._uncertainty_summaries()
        self._cand_cache: dict[tuple[str, str, str], list[PathCand]] = {}
        self._bg_load = self._background_load()

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
            return None
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
        self._density, self._speed, self._unc = self._load_density_file(path)
        self._dens_cache = self._density_summaries()
        self._unc_cache = self._uncertainty_summaries()
        self._bg_load = self._background_load()
        self._active_peak = peak
        self.density_path = path
        self._cand_cache.clear()
        return peak

    def set_od_pool(self, pairs: list[tuple[str, str]]) -> None:
        self._od_pool = [(str(o), str(d)) for o, d in pairs if o != d]

    def _background_load(self) -> dict[tuple[str, str], float]:
        """Map twin density_k into soft background occupancy."""
        out: dict[tuple[str, str], float] = {}
        for u, v in self._edge_index:
            aid = self._g.edges[u, v]["alley_id"]
            k = float(self._density.get(aid, 0.03))
            # scale k~0.03-0.15 → ~0.3-2.0 background agents-equivalent
            out[(u, v)] = float(np.clip(k / 0.06, 0.2, 3.0))
        return out

    def _edge_free_time(self, u: str, v: str) -> float:
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

    def _edge_unc(self, u: str, v: str) -> float:
        aid = self._g.edges[u, v]["alley_id"]
        return float(self._unc.get(aid, 0.05))

    def _weight_factory(self, mode: str):
        def weight(u: str, v: str, _d: dict[str, Any]) -> float:
            base = self._edge_free_time(u, v)
            data = self._g.edges[u, v]
            is_alley = self._is_alley(data)
            u_val = self._edge_unc(u, v)
            if mode == "mean":
                return base
            if mode == "prefer_alley":
                return base + (0.0 if is_alley else 8.0)
            if mode == "prefer_main":
                return base + (8.0 if is_alley else 0.0)
            if mode == "risk":
                return base + 0.15 * u_val * float(data["length_m"])
            if mode == "heavy_alley":
                return base + (0.0 if is_alley else 20.0)
            if mode == "heavy_main":
                return base + (20.0 if is_alley else 0.0)
            if mode == "bg_load":
                return base * (1.0 + 0.3 * self._bg_load.get((u, v), 0.5))
            return base

        return weight

    def _shortest_nodes(self, origin: str, dest: str, mode: str) -> list[str] | None:
        try:
            return list(
                nx.shortest_path(self._g, origin, dest, weight=self._weight_factory(mode))
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def _path_from_nodes(self, nodes: list[str], label: str) -> PathCand | None:
        if len(nodes) < 2:
            return None
        edges: list[tuple[str, str]] = []
        free = 0.0
        risk = 0.0
        alley_n = 0
        u_sum = 0.0
        for a, b in zip(nodes[:-1], nodes[1:]):
            if not self._g.has_edge(a, b):
                return None
            edges.append((a, b))
            data = self._g.edges[a, b]
            free += self._edge_free_time(a, b)
            u = self._edge_unc(a, b)
            risk += u * float(data["length_m"])
            u_sum += u
            if self._is_alley(data):
                alley_n += 1
        n_e = len(edges)
        return PathCand(
            nodes=list(nodes),
            edge_keys=edges,
            free_time=float(free),
            risk=float(risk),
            n_edges=n_e,
            alley_frac=float(alley_n / max(n_e, 1)),
            mean_u=float(u_sum / max(n_e, 1)),
            label=label,
            valid=True,
        )

    def generate_candidates(self, origin: str, dest: str) -> list[PathCand]:
        peak = self._active_peak or self.peak_for_t(self._t)
        key = (origin, dest, peak)
        if key in self._cand_cache and len(self._cand_cache[key]) >= self.k_paths:
            return list(self._cand_cache[key][: self.k_paths])

        found: list[PathCand] = []
        seen: set[tuple[str, ...]] = set()

        def add(nodes: list[str] | None, label: str) -> None:
            if not nodes:
                return
            tup = tuple(nodes)
            if tup in seen:
                return
            meta = self._path_from_nodes(nodes, label)
            if meta is None:
                return
            seen.add(tup)
            found.append(meta)

        for mode in (
            "mean",
            "prefer_alley",
            "prefer_main",
            "risk",
            "heavy_alley",
            "heavy_main",
            "bg_load",
        ):
            add(self._shortest_nodes(origin, dest, mode), mode)

        base = self._shortest_nodes(origin, dest, "mean")
        if base and len(base) >= 3:
            for i, (u, v) in enumerate(zip(base[:-1], base[1:])):
                if len(found) >= self.k_paths * 2 or i > 10:
                    break
                data = dict(self._g.edges[u, v])
                self._g.remove_edge(u, v)
                try:
                    add(self._shortest_nodes(origin, dest, "mean"), f"yen_{i}")
                finally:
                    self._g.add_edge(u, v, **data)

        if not found:
            dummy = PathCand(
                nodes=[origin, dest],
                edge_keys=[],
                free_time=1e6,
                risk=1e6,
                n_edges=0,
                alley_frac=0.0,
                mean_u=0.05,
                label="invalid",
                valid=False,
            )
            found = [dummy]

        found.sort(key=lambda p: p.free_time)
        selected = found[: self.k_paths]
        while len(selected) < self.k_paths:
            pad = PathCand(
                nodes=list(selected[0].nodes),
                edge_keys=list(selected[0].edge_keys),
                free_time=selected[0].free_time,
                risk=selected[0].risk,
                n_edges=selected[0].n_edges,
                alley_frac=selected[0].alley_frac,
                mean_u=selected[0].mean_u,
                label="pad",
                valid=False,
            )
            selected.append(pad)
        self._cand_cache[key] = selected
        return selected

    def _density_summaries(self) -> np.ndarray:
        dens = np.array(
            [self._density.get(a, 0.03) for a in self._aids], dtype=np.float32
        )
        if dens.size == 0:
            return np.zeros(6, dtype=np.float32)
        return np.array(
            [
                float(np.mean(dens)),
                float(np.std(dens)),
                float(np.percentile(dens, 50)),
                float(np.percentile(dens, 90)),
                float(np.max(dens)),
                float(len(self._aids)) / 10000.0,
            ],
            dtype=np.float32,
        )

    def _uncertainty_summaries(self) -> np.ndarray:
        us = np.array([self._unc.get(a, 0.05) for a in self._aids], dtype=np.float32)
        if us.size == 0:
            return np.zeros(4, dtype=np.float32)
        return np.array(
            [
                float(np.mean(us)),
                float(np.std(us)),
                float(np.percentile(us, 90)),
                float(np.max(us)),
            ],
            dtype=np.float32,
        )

    @staticmethod
    def _hash_embed(token: str, dim: int) -> np.ndarray:
        h = abs(hash(token)) % (2**31)
        idx = np.arange(dim, dtype=np.float32)
        return np.sin((h % 997) * 0.1 + idx * 0.37).astype(np.float32)

    def _local_obs(self, agent_idx: int) -> np.ndarray:
        o, d = self._ods[agent_idx]
        cands = self._cands[agent_idx]
        t_feat = np.array([self._t / 86400.0], dtype=np.float32)
        emb_dim = 12
        o_emb = self._hash_embed(o, emb_dim)
        d_emb = self._hash_embed(d, emb_dim)
        # noisy load hint: mean bg load on candidate edges
        hints = []
        rows = []
        for c in cands:
            if c.edge_keys:
                bg = float(np.mean([self._bg_load.get(e, 0.5) for e in c.edge_keys]))
            else:
                bg = 0.0
            # observation noise
            bg_obs = bg + float(self.rng.normal(0.0, 0.15))
            hints.append(bg_obs)
            rows.append(
                [
                    c.free_time / 1000.0,
                    c.risk / 1000.0,
                    c.n_edges / 50.0,
                    c.alley_frac,
                    c.mean_u,
                    bg_obs / 5.0,
                    1.0 if c.valid else 0.0,
                ]
            )
        while len(rows) < self.k_paths:
            rows.append([0.0] * 7)
        feat = np.concatenate(
            [
                t_feat,
                o_emb,
                d_emb,
                self._dens_cache,
                self._unc_cache,
                np.asarray(rows[: self.k_paths], dtype=np.float32).reshape(-1),
            ]
        )
        if feat.size < self.compact_dim:
            feat = np.pad(feat, (0, self.compact_dim - feat.size))
        return feat[: self.compact_dim].astype(np.float32)

    def _global_state(self) -> np.ndarray:
        """Critic input: mean local obs + coarse load histogram (background)."""
        locs = np.stack([self._local_obs(i) for i in range(self.n_agents)], axis=0)
        mean_loc = locs.mean(axis=0)
        bg_vals = np.array(list(self._bg_load.values()), dtype=np.float32)
        if bg_vals.size == 0:
            hist = np.zeros(8, dtype=np.float32)
        else:
            hist = np.histogram(bg_vals, bins=8, range=(0.0, 4.0))[0].astype(np.float32)
            hist = hist / max(float(hist.sum()), 1.0)
        g = np.concatenate([mean_loc, hist, np.array([self.n_agents / 32.0], dtype=np.float32)])
        return g.astype(np.float32)

    def local_obs_dim(self) -> int:
        return self.compact_dim

    def global_state_dim(self) -> int:
        return int(self._global_state().shape[0])

    def _sample_ods(self) -> list[tuple[str, str]]:
        pool = self._od_pool
        if not pool:
            # random node pairs
            nodes = self._nodes
            out = []
            for _ in range(self.n_agents):
                o, d = self.rng.choice(nodes, size=2, replace=False)
                out.append((str(o), str(d)))
            return out

        if self.rng.random() < self.corridor_prob and len(pool) >= 2:
            # correlated: pick a seed OD then nearest-ish partners by shared origin prefix hash
            anchor = pool[int(self.rng.integers(0, len(pool)))]
            scored = sorted(
                pool,
                key=lambda od: abs(hash(od[0]) - hash(anchor[0])) % 997
                + abs(hash(od[1]) - hash(anchor[1])) % 997,
            )
            picks = scored[: max(self.n_agents, 1)]
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
        if "ods" in options:
            self._ods = [(str(o), str(d)) for o, d in options["ods"]]
            while len(self._ods) < self.n_agents:
                self._ods.append(self._ods[-1])
            self._ods = self._ods[: self.n_agents]
        else:
            self._ods = self._sample_ods()

        self._cands = []
        self._action_mask = []
        for od in self._ods:
            cands = self.generate_candidates(od[0], od[1])
            self._cands.append(cands)
            mask = np.array([1.0 if c.valid else 0.0 for c in cands], dtype=np.float32)
            if mask.sum() < 1:
                mask[0] = 1.0
            self._action_mask.append(mask)

        obs = {a: self._local_obs(i) for i, a in enumerate(self.agents)}
        gstate = self._global_state()
        info = {
            "t": self._t,
            "peak": self._active_peak,
            "n_agents": self.n_agents,
            "masks": {a: self._action_mask[i] for i, a in enumerate(self.agents)},
        }
        return obs, gstate, info

    def _bpr_edge_time(self, u: str, v: str, load: float) -> float:
        t0 = self._edge_free_time(u, v)
        cap = max(0.5, self._cap[(u, v)])
        return float(t0 * (1.0 + self.bpr_alpha * (load / cap) ** self.bpr_beta))

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
        chosen: list[PathCand] = []
        for i, a in enumerate(self.agents):
            mask = self._action_mask[i]
            raw = int(actions.get(a, 0)) % self.k_paths
            if mask[raw] < 0.5:
                # fallback to first valid
                raw = int(np.argmax(mask))
            chosen.append(self._cands[i][raw])

        # aggregate loads
        load: dict[tuple[str, str], float] = {e: float(self._bg_load.get(e, 0.0)) for e in self._edge_index}
        for c in chosen:
            for e in c.edge_keys:
                load[e] = load.get(e, 0.0) + 1.0

        travels: list[float] = []
        risks: list[float] = []
        congests: list[float] = []
        for c in chosen:
            if not c.edge_keys:
                travels.append(1e6)
                risks.append(1e6)
                congests.append(10.0)
                continue
            tt = 0.0
            cong = 0.0
            for e in c.edge_keys:
                tt += self._bpr_edge_time(e[0], e[1], load[e])
                cap = max(0.5, self._cap[e])
                cong += (load[e] / cap) ** self.bpr_beta
            travels.append(float(tt))
            risks.append(float(c.risk))
            congests.append(float(cong / max(len(c.edge_keys), 1)))

        t_arr = np.asarray(travels, dtype=np.float64)
        t_bar = float(np.mean(t_arr))
        w = self.reward_weights
        rewards: dict[str, float] = {}
        for i, a in enumerate(self.agents):
            fair = abs(travels[i] - t_bar)
            # scale rewards to stable magnitude
            cost = (
                w["w_T"] * (travels[i] / 100.0)
                + w["w_S"] * (t_bar / 100.0)
                + w["w_R"] * (risks[i] / 500.0)
                + w["w_F"] * (fair / 100.0)
                + w["w_C"] * congests[i]
            )
            rewards[a] = -float(cost)

        obs = {a: self._local_obs(i) for i, a in enumerate(self.agents)}
        terms = {a: True for a in self.agents}
        truncs = {a: False for a in self.agents}
        gstate = self._global_state()

        # fleet metrics
        sorted_t = np.sort(t_arr)
        p90 = float(sorted_t[int(0.9 * (len(sorted_t) - 1))])
        cvar_thr = float(np.quantile(t_arr, 0.9))
        cvar = float(np.mean(t_arr[t_arr >= cvar_thr])) if np.any(t_arr >= cvar_thr) else t_bar
        # Gini
        if t_bar > 0:
            diff = np.abs(t_arr.reshape(-1, 1) - t_arr.reshape(1, -1)).mean()
            gini = float(diff / (2.0 * t_bar))
        else:
            gini = 0.0
        cong_index = float(np.mean(congests))

        info = {
            "travels": travels,
            "fleet_mean": t_bar,
            "fleet_p90": p90,
            "fleet_cvar90": cvar,
            "fairness_gini": gini,
            "congestion": cong_index,
            "actions": {a: int(actions.get(a, 0)) % self.k_paths for a in self.agents},
            "loads_max": float(max(load.values()) if load else 0.0),
        }
        return obs, rewards, terms, truncs, gstate, info

    # ----- baselines (joint assignment) -----

    def baseline_all_dijkstra(self) -> dict[str, int]:
        """Each agent picks free-flow mean shortest (index of 'mean' / lowest free_time)."""
        acts = {}
        for i, a in enumerate(self.agents):
            idx = int(np.argmin([c.free_time if c.valid else 1e9 for c in self._cands[i]]))
            acts[a] = idx
        return acts

    def baseline_random(self) -> dict[str, int]:
        acts = {}
        for i, a in enumerate(self.agents):
            valid = np.where(self._action_mask[i] > 0.5)[0]
            acts[a] = int(self.rng.choice(valid)) if len(valid) else 0
        return acts

    def baseline_greedy_load(self) -> dict[str, int]:
        """Sequential: assign agents one-by-one minimizing BPR given current loads."""
        load: dict[tuple[str, str], float] = {
            e: float(self._bg_load.get(e, 0.0)) for e in self._edge_index
        }
        acts: dict[str, int] = {}
        order = list(range(self.n_agents))
        self.rng.shuffle(order)
        for i in order:
            best_j, best_tt = 0, 1e18
            for j, c in enumerate(self._cands[i]):
                if not c.valid or self._action_mask[i][j] < 0.5:
                    continue
                tt = 0.0
                for e in c.edge_keys:
                    tt += self._bpr_edge_time(e[0], e[1], load[e] + 1.0)
                if tt < best_tt:
                    best_tt, best_j = tt, j
            acts[self.agents[i]] = best_j
            for e in self._cands[i][best_j].edge_keys:
                load[e] = load.get(e, 0.0) + 1.0
        return acts
