"""UncertaintyAwareKPath (UAKP) env — K-path selection under density + uncertainty.

Scientific core for RESEARCH_ONE_PAPER.md (not binary prefer-main/alley).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np


@dataclass
class PathCandidate:
    nodes: list[str]
    travel_time: float
    risk: float  # sum(u_e * length_m)
    n_edges: int
    alley_frac: float
    mean_u: float
    label: str

    @property
    def risk_adjusted(self) -> float:
        return float(self.travel_time)


class UAKPEnv:
    """Single-agent env: reset(O,D,t) → K candidates; step(a) → risk-adjusted reward."""

    metadata = {"name": "uakp_v1", "render_modes": []}

    def __init__(
        self,
        density_path: Path,
        graph_path: Path | None = None,
        seed: int = 0,
        k_paths: int = 8,
        risk_lambda: float = 0.05,
        compact_dim: int = 128,
        include_uncertainty: bool = True,
        density_catalog: dict[str, Path] | None = None,
    ) -> None:
        self.density_path = Path(density_path)
        self.graph_path = graph_path
        self.k_paths = max(2, int(k_paths))
        self.risk_lambda = float(risk_lambda)
        self.compact_dim = max(64, int(compact_dim))
        self.include_uncertainty = bool(include_uncertainty)
        self.density_catalog = {
            str(k): Path(v) for k, v in (density_catalog or {}).items() if v
        }
        self._active_peak: str | None = None
        self.rng = np.random.default_rng(seed)
        self.agents = ["agent_0"]
        self._g = self._load_graph()
        self._density, self._speed, self._unc = self._load_density_file(self.density_path)
        self._aids = sorted({d["alley_id"] for _, _, d in self._g.edges(data=True)})
        self._nodes = sorted(self._g.nodes())
        self._od: tuple[str, str] = (
            self._nodes[0],
            self._nodes[min(1, len(self._nodes) - 1)],
        ) if self._nodes else ("", "")
        self._t: float = 0.0
        self._candidates: list[PathCandidate] = []
        self._dens_cache = self._density_summaries()
        self._unc_cache = self._uncertainty_summaries()
        self._cand_cache: dict[tuple[str, str, str], list[PathCandidate]] = {}

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
                    e["u"],
                    e["v"],
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
        self._active_peak = peak
        self.density_path = path
        self._cand_cache.clear()
        return peak

    def _edge_speed(self, u: str, v: str) -> float:
        data = self._g.edges[u, v]
        aid = data["alley_id"]
        is_alley = self._is_alley(data)
        if aid in self._speed:
            return max(0.5, min(13.0, float(self._speed[aid])))
        k = self._density.get(aid, 0.03)
        v_free = 8.0 if is_alley else 13.0
        k_jam = 0.18
        return max(0.5, v_free * (1.0 - min(k, k_jam * 0.99) / k_jam))

    def _edge_unc(self, u: str, v: str) -> float:
        aid = self._g.edges[u, v]["alley_id"]
        return float(self._unc.get(aid, 0.05))

    def _path_metrics(self, nodes: list[str], label: str) -> PathCandidate | None:
        if len(nodes) < 2:
            return None
        travel = 0.0
        risk = 0.0
        alley_n = 0
        u_sum = 0.0
        n_e = 0
        for a, b in zip(nodes[:-1], nodes[1:]):
            if not self._g.has_edge(a, b):
                return None
            data = self._g.edges[a, b]
            length = float(data["length_m"])
            speed = self._edge_speed(a, b)
            u = self._edge_unc(a, b)
            travel += length / speed
            risk += u * length
            u_sum += u
            n_e += 1
            if self._is_alley(data):
                alley_n += 1
        return PathCandidate(
            nodes=list(nodes),
            travel_time=float(travel),
            risk=float(risk),
            n_edges=n_e,
            alley_frac=float(alley_n / max(n_e, 1)),
            mean_u=float(u_sum / max(n_e, 1)),
            label=label,
        )

    def _weight_factory(self, mode: str):
        def weight(u: str, v: str, _d: dict[str, Any]) -> float:
            data = self._g.edges[u, v]
            length = float(data["length_m"])
            speed = self._edge_speed(u, v)
            base = length / speed
            is_alley = self._is_alley(data)
            u_val = self._edge_unc(u, v)
            if mode == "mean":
                return base
            if mode == "prefer_alley":
                return base + (0.0 if is_alley else 8.0)
            if mode == "prefer_main":
                return base + (8.0 if is_alley else 0.0)
            if mode == "risk":
                return base + self.risk_lambda * u_val * length
            if mode == "optimistic":
                return max(0.01, base - 0.5 * u_val * length)
            if mode == "heavy_alley":
                return base + (0.0 if is_alley else 20.0)
            if mode == "heavy_main":
                return base + (20.0 if is_alley else 0.0)
            return base

        return weight

    def _shortest_nodes(self, origin: str, dest: str, mode: str) -> list[str] | None:
        try:
            return list(
                nx.shortest_path(self._g, origin, dest, weight=self._weight_factory(mode))
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def generate_candidates(self, origin: str, dest: str) -> list[PathCandidate]:
        """Build up to K diverse paths; pad by repeating best if fewer."""
        peak = self._active_peak or self.peak_for_t(self._t)
        key = (origin, dest, peak)
        if key in self._cand_cache:
            cached = self._cand_cache[key]
            if len(cached) >= self.k_paths:
                return [cached[i] for i in range(self.k_paths)]

        found: list[PathCandidate] = []
        seen: set[tuple[str, ...]] = set()

        def add(nodes: list[str] | None, label: str) -> None:
            if not nodes:
                return
            tup = tuple(nodes)
            if tup in seen:
                return
            meta = self._path_metrics(nodes, label)
            if meta is None or meta.travel_time >= 1e6:
                return
            seen.add(tup)
            found.append(meta)

        for mode in (
            "mean",
            "prefer_alley",
            "prefer_main",
            "risk",
            "optimistic",
            "heavy_alley",
            "heavy_main",
        ):
            add(self._shortest_nodes(origin, dest, mode), mode)

        # Yen-lite diversity: remove one edge from best mean path and re-route
        base = self._shortest_nodes(origin, dest, "mean")
        if base and len(base) >= 3:
            for i, (u, v) in enumerate(zip(base[:-1], base[1:])):
                if len(found) >= self.k_paths * 2:
                    break
                if i > 12:
                    break
                data = dict(self._g.edges[u, v])
                self._g.remove_edge(u, v)
                try:
                    alt = self._shortest_nodes(origin, dest, "mean")
                    add(alt, f"yen_{i}")
                finally:
                    self._g.add_edge(u, v, **data)

        if not found:
            # unreachable — placeholder infinite cost
            dummy = PathCandidate(
                nodes=[origin, dest],
                travel_time=1e6,
                risk=1e6,
                n_edges=1,
                alley_frac=0.0,
                mean_u=0.05,
                label="unreachable",
            )
            found = [dummy]

        # Prefer diverse travel times: sort by travel then take unique, fill to K
        found.sort(key=lambda p: (p.travel_time, p.risk))
        selected: list[PathCandidate] = []
        for p in found:
            if len(selected) >= self.k_paths:
                break
            selected.append(p)
        while len(selected) < self.k_paths:
            selected.append(selected[len(selected) % len(found)])

        self._cand_cache[key] = selected
        return selected

    def risk_adjusted_cost(self, cand: PathCandidate) -> float:
        if self.include_uncertainty:
            return float(cand.travel_time + self.risk_lambda * cand.risk)
        return float(cand.travel_time)

    def _density_summaries(self) -> np.ndarray:
        dens = np.array(
            [self._density.get(a, 0.03) for a in self._aids], dtype=np.float32
        )
        if dens.size == 0:
            return np.zeros(8, dtype=np.float32)
        alley_flags = [
            1.0 if self._is_alley(d) else 0.0 for _, _, d in self._g.edges(data=True)
        ]
        alley_frac = float(np.mean(alley_flags)) if alley_flags else 0.0
        return np.array(
            [
                float(np.mean(dens)),
                float(np.std(dens)),
                float(np.percentile(dens, 10)),
                float(np.percentile(dens, 50)),
                float(np.percentile(dens, 90)),
                float(np.max(dens)),
                alley_frac,
                float(len(self._aids)) / 10000.0,
            ],
            dtype=np.float32,
        )

    def _uncertainty_summaries(self) -> np.ndarray:
        us = np.array(
            [self._unc.get(a, 0.05) for a in self._aids], dtype=np.float32
        )
        if us.size == 0:
            return np.zeros(8, dtype=np.float32)
        return np.array(
            [
                float(np.mean(us)),
                float(np.std(us)),
                float(np.percentile(us, 10)),
                float(np.percentile(us, 50)),
                float(np.percentile(us, 90)),
                float(np.max(us)),
                float(np.min(us)),
                float(len(set(np.round(us, 4).tolist()))) / 20.0,
            ],
            dtype=np.float32,
        )

    @staticmethod
    def _hash_embed(token: str, dim: int) -> np.ndarray:
        h = abs(hash(token)) % (2**31)
        idx = np.arange(dim, dtype=np.float32)
        return np.sin((h % 997) * 0.1 + idx * 0.37).astype(np.float32)

    def _candidate_feat_matrix(self) -> np.ndarray:
        """Per-candidate features: [travel/1000, risk/1000, n_edges/50, alley_frac, mean_u]."""
        rows = []
        for c in self._candidates:
            rows.append(
                [
                    c.travel_time / 1000.0,
                    c.risk / 1000.0,
                    c.n_edges / 50.0,
                    c.alley_frac,
                    c.mean_u if self.include_uncertainty else 0.0,
                ]
            )
        while len(rows) < self.k_paths:
            rows.append([0.0, 0.0, 0.0, 0.0, 0.0])
        return np.asarray(rows[: self.k_paths], dtype=np.float32).reshape(-1)

    def _obs(self) -> np.ndarray:
        o, d = self._od
        t_feat = np.array([self._t / 86400.0], dtype=np.float32)
        # Reserve: 1 + 2*emb + 8 dens + 8 unc + 5*K
        per_k = 5 * self.k_paths
        fixed = 1 + 8 + (8 if self.include_uncertainty else 0) + per_k
        emb_dim = max(8, (self.compact_dim - fixed) // 2)
        o_emb = self._hash_embed(o, emb_dim)
        d_emb = self._hash_embed(d, emb_dim)
        parts = [t_feat, o_emb, d_emb, self._dens_cache]
        if self.include_uncertainty:
            parts.append(self._unc_cache)
        else:
            parts.append(np.zeros(8, dtype=np.float32))
        parts.append(self._candidate_feat_matrix())
        feat = np.concatenate(parts)
        if feat.size < self.compact_dim:
            feat = np.pad(feat, (0, self.compact_dim - feat.size))
        return feat[: self.compact_dim].astype(np.float32)

    def obs_dim(self) -> int:
        if not self._candidates:
            # build dummy candidates for dim
            if self._nodes:
                self._candidates = self.generate_candidates(self._od[0], self._od[1])
        return int(self._obs().shape[0])

    def n_actions(self) -> int:
        return self.k_paths

    def reset(
        self, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        options = options or {}
        self._t = float(options.get("t", 0.0))
        self.ensure_density_for_t(self._t)
        nodes = list(self._g.nodes())
        o = str(options.get("origin", nodes[0] if nodes else ""))
        d = str(options.get("destination", nodes[-1] if nodes else ""))
        if "origin" not in options and len(nodes) >= 2:
            o, d = self.rng.choice(nodes, size=2, replace=False)
            o, d = str(o), str(d)
        self._od = (o, d)
        self._candidates = self.generate_candidates(o, d)
        obs = self._obs()
        info = {
            "t": self._t,
            "od": self._od,
            "n_candidates": len(self._candidates),
            "unique_paths": len({tuple(c.nodes) for c in self._candidates}),
            "oracle_idx": int(np.argmin([self.risk_adjusted_cost(c) for c in self._candidates])),
            "oracle_travel": float(min(c.travel_time for c in self._candidates)),
            "peak": self._active_peak,
        }
        return obs, info

    def step(
        self, action: int
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        a = int(action) % self.k_paths
        cand = self._candidates[a]
        cost = self.risk_adjusted_cost(cand)
        reward = -float(cost)
        oracle_idx = int(np.argmin([self.risk_adjusted_cost(c) for c in self._candidates]))
        oracle_tt = float(self._candidates[oracle_idx].travel_time)
        info = {
            "travel_time": float(cand.travel_time),
            "risk": float(cand.risk),
            "risk_adjusted": float(cost),
            "action": a,
            "label": cand.label,
            "oracle_idx": oracle_idx,
            "oracle_travel": oracle_tt,
            "gap": float(cand.travel_time - oracle_tt),
            "od": self._od,
            "t": self._t,
        }
        return self._obs(), reward, True, False, info

    # --- baselines (same candidate set / graph) ---

    def baseline_dijkstra_mean(self, origin: str, dest: str) -> PathCandidate:
        nodes = self._shortest_nodes(origin, dest, "mean")
        meta = self._path_metrics(nodes or [origin, dest], "dijkstra_mean")
        assert meta is not None
        return meta

    def baseline_dijkstra_ignore_u(self, origin: str, dest: str) -> PathCandidate:
        """Same as mean travel path (uncertainty not in weight) — explicit name for tables."""
        return self.baseline_dijkstra_mean(origin, dest)

    def baseline_prefer(self, origin: str, dest: str, alley: bool) -> PathCandidate:
        mode = "prefer_alley" if alley else "prefer_main"
        nodes = self._shortest_nodes(origin, dest, mode)
        meta = self._path_metrics(nodes or [origin, dest], mode)
        assert meta is not None
        return meta

    def oracle_among_candidates(self) -> tuple[int, PathCandidate]:
        costs = [self.risk_adjusted_cost(c) for c in self._candidates]
        idx = int(np.argmin(costs))
        return idx, self._candidates[idx]

    def realized_travel_samples(
        self, cand: PathCandidate, n_samples: int = 32, seed: int = 0
    ) -> np.ndarray:
        """Stochastic travel: each edge time *= (1 + |N(0, sigma)|) with sigma ∝ uncertainty.

        Used for paper eval when deterministic risk ranking ≈ mean-T ranking.
        """
        rng = np.random.default_rng(seed)
        samples = np.zeros(n_samples, dtype=np.float64)
        edges = list(zip(cand.nodes[:-1], cand.nodes[1:]))
        if not edges:
            return samples
        base: list[float] = []
        sig: list[float] = []
        for u, v in edges:
            length = float(self._g.edges[u, v]["length_m"])
            speed = self._edge_speed(u, v)
            base.append(length / speed)
            sig.append(max(0.01, self._edge_unc(u, v) * 4.0))
        base_a = np.asarray(base, dtype=np.float64)
        sig_a = np.asarray(sig, dtype=np.float64)
        for i in range(n_samples):
            noise = np.abs(rng.normal(0.0, sig_a))
            samples[i] = float(np.sum(base_a * (1.0 + noise)))
        return samples

    @staticmethod
    def cvar(samples: np.ndarray, alpha: float = 0.9) -> float:
        if samples.size == 0:
            return float("nan")
        thr = float(np.quantile(samples, alpha))
        tail = samples[samples >= thr]
        if tail.size == 0:
            return float(np.mean(samples))
        return float(np.mean(tail))
