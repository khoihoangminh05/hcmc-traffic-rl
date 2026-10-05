"""Offline PettingZoo-style env over fused alley density (SUMO-ready state).

Batch episodes only — no real-time waiting for new data.
I/O contract: observe graph at t; agents choose routes O→D; reward = -travel_time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np


class AlleyRoutingEnv:
    """Minimal multi-agent routing env (PettingZoo ParallelAPI-compatible subset)."""

    metadata = {"name": "alley_routing_v0", "render_modes": []}

    def __init__(
        self,
        density_path: Path,
        graph_path: Path | None = None,
        n_agents: int = 2,
        seed: int = 0,
        obs_mode: str = "compact",
        compact_dim: int = 64,
    ) -> None:
        self.density_path = density_path
        self.graph_path = graph_path
        self.n_agents = n_agents
        self.obs_mode = obs_mode if obs_mode in ("compact", "full") else "compact"
        self.compact_dim = max(32, int(compact_dim))
        self.rng = np.random.default_rng(seed)
        self.agents = [f"agent_{i}" for i in range(n_agents)]
        self.possible_agents = list(self.agents)
        self._g = self._load_graph()
        self._density, self._speed = self._load_density()
        self._aids = sorted({d["alley_id"] for _, _, d in self._g.edges(data=True)})
        self._nodes = sorted(self._g.nodes())
        self._node_index = {n: i for i, n in enumerate(self._nodes)}
        self._od: dict[str, tuple[str, str]] = {}
        self._t: float = 0.0
        self._dens_cache = self._density_summaries()
        # Dummy OD so obs_dim() works before first reset
        if self._nodes:
            for a in self.agents:
                self._od[a] = (self._nodes[0], self._nodes[min(1, len(self._nodes) - 1)])

    @staticmethod
    def _is_alley(data: dict[str, Any]) -> bool:
        return data.get("road_class") == "alley" or data.get("layer") == "alley"

    def _load_graph(self) -> nx.DiGraph:
        if self.graph_path and self.graph_path.exists():
            data = json.loads(self.graph_path.read_text(encoding="utf-8"))
            g = nx.DiGraph()
            alleys = data["alleys"]
            for e in data["edge_list"]:
                a = alleys[e["alley_id"]]
                g.add_edge(
                    e["u"],
                    e["v"],
                    alley_id=e["alley_id"],
                    length_m=a["length_m"],
                    road_class=a.get("road_class") or "",
                    layer=a.get("layer") or "",
                )
            return g
        # Fallback: import demo builder
        from data_fusion.alley_graph import build_demo_alley_graph

        return build_demo_alley_graph()

    def _load_density(self) -> tuple[dict[str, float], dict[str, float]]:
        if not self.density_path.exists():
            return {}, {}
        rows = json.loads(self.density_path.read_text(encoding="utf-8"))
        dens: dict[str, float] = {}
        speeds: dict[str, float] = {}
        for r in rows:
            aid = r.get("alley_id")
            if not aid:
                continue
            try:
                dens[str(aid)] = float(r["density_k"])
            except (KeyError, TypeError, ValueError):
                pass
            try:
                speeds[str(aid)] = float(r["speed_mps"])
            except (KeyError, TypeError, ValueError):
                pass
        return dens, speeds

    def observation_space(self, agent: str) -> dict[str, Any]:
        return {"graph_nodes": len(self._g.nodes), "edges": len(self._g.edges)}

    def action_space(self, agent: str) -> dict[str, Any]:
        # Discrete: 0 = prefer main, 1 = prefer alley when density lower
        return {"n": 2}

    def reset(
        self, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        options = options or {}
        self._t = float(options.get("t", 0.0))
        nodes = list(self._g.nodes())
        self._od = {}
        for agent in self.agents:
            o = options.get("origin", nodes[0])
            d = options.get("destination", nodes[-1])
            if "origin" not in options:
                o, d = self.rng.choice(nodes, size=2, replace=False)
            self._od[agent] = (str(o), str(d))
        obs = {a: self._obs(a) for a in self.agents}
        infos = {a: {"t": self._t, "od": self._od[a]} for a in self.agents}
        return obs, infos

    def _edge_travel_time(self, u: str, v: str, prefer_alley: bool) -> float:
        data = self._g.edges[u, v]
        aid = data["alley_id"]
        length = float(data["length_m"])
        is_alley = self._is_alley(data)
        if aid in self._speed:
            speed = max(0.5, min(13.0, float(self._speed[aid])))
        else:
            k = self._density.get(aid, 0.03)
            v_free = 8.0 if is_alley else 13.0
            k_jam = 0.18
            speed = max(0.5, v_free * (1.0 - min(k, k_jam * 0.99) / k_jam))
        penalty = 0.0
        if prefer_alley and not is_alley:
            penalty = 5.0
        if not prefer_alley and is_alley:
            penalty = 8.0
        return length / speed + penalty

    def _shortest_time(self, origin: str, dest: str, prefer_alley: bool) -> float:
        def weight(u: str, v: str, _d: dict[str, Any]) -> float:
            return self._edge_travel_time(u, v, prefer_alley)

        try:
            path = nx.shortest_path(self._g, origin, dest, weight=weight)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return 1e6
        total = 0.0
        for a, b in zip(path[:-1], path[1:]):
            total += self._edge_travel_time(a, b, prefer_alley)
        return total

    def _density_summaries(self) -> np.ndarray:
        dens = np.array(
            [self._density.get(a, 0.03) for a in self._aids], dtype=np.float32
        )
        if dens.size == 0:
            return np.zeros(8, dtype=np.float32)
        alley_flags = []
        for _, _, data in self._g.edges(data=True):
            alley_flags.append(1.0 if self._is_alley(data) else 0.0)
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

    @staticmethod
    def _hash_embed(token: str, dim: int) -> np.ndarray:
        """Deterministic Fourier-like embedding of a node id (no learnable table)."""
        h = abs(hash(token)) % (2**31)
        idx = np.arange(dim, dtype=np.float32)
        return np.sin((h % 997) * 0.1 + idx * 0.37).astype(np.float32)

    def _obs(self, agent: str) -> np.ndarray:
        o, d = self._od[agent]
        t_feat = np.array([self._t / 86400.0], dtype=np.float32)
        if self.obs_mode == "full":
            dens = np.array(
                [self._density.get(a, 0.03) for a in self._aids], dtype=np.float32
            )
            o_oh = np.zeros(len(self._nodes), dtype=np.float32)
            d_oh = np.zeros(len(self._nodes), dtype=np.float32)
            if o in self._node_index:
                o_oh[self._node_index[o]] = 1.0
            if d in self._node_index:
                d_oh[self._node_index[d]] = 1.0
            return np.concatenate([t_feat, o_oh, d_oh, dens])

        # compact: fixed-size, train-friendly for Quận 4
        emb_dim = max(8, (self.compact_dim - 1 - 8) // 2)
        o_emb = self._hash_embed(o, emb_dim)
        d_emb = self._hash_embed(d, emb_dim)
        feat = np.concatenate([t_feat, o_emb, d_emb, self._dens_cache])
        if feat.size < self.compact_dim:
            feat = np.pad(feat, (0, self.compact_dim - feat.size))
        return feat[: self.compact_dim].astype(np.float32)

    def obs_dim(self) -> int:
        return int(self._obs(self.agents[0]).shape[0]) if self.agents else self.compact_dim

    def oracle_travel_time(self, t: float, origin: str, destination: str) -> dict[str, float]:
        """Baseline times for both preferences + min (oracle)."""
        self._t = t
        t_main = self._shortest_time(origin, destination, prefer_alley=False)
        t_alley = self._shortest_time(origin, destination, prefer_alley=True)
        return {
            "travel_main": float(t_main),
            "travel_alley": float(t_alley),
            "travel_oracle": float(min(t_main, t_alley)),
            "oracle_action": 1.0 if t_alley <= t_main else 0.0,
        }

    def step(
        self, actions: dict[str, int]
    ) -> tuple[
        dict[str, np.ndarray],
        dict[str, float],
        dict[str, bool],
        dict[str, bool],
        dict[str, Any],
    ]:
        obs: dict[str, np.ndarray] = {}
        rewards: dict[str, float] = {}
        terms = {a: True for a in self.agents}
        truncs = {a: False for a in self.agents}
        infos: dict[str, Any] = {}

        for agent in self.agents:
            o, d = self._od[agent]
            prefer_alley = int(actions.get(agent, 0)) == 1
            travel = self._shortest_time(o, d, prefer_alley)
            rewards[agent] = -float(travel)
            obs[agent] = self._obs(agent)
            infos[agent] = {
                "travel_time": travel,
                "prefer_alley": prefer_alley,
                "od": (o, d),
                "t": self._t,
            }
        return obs, rewards, terms, truncs, infos

    def shortest_travel_time(self, t: float, origin: str, destination: str) -> float:
        """North-star inference helper: (t, O, D) → min travel time (alleys allowed)."""
        self._t = t
        return min(
            self._shortest_time(origin, destination, prefer_alley=True),
            self._shortest_time(origin, destination, prefer_alley=False),
        )
