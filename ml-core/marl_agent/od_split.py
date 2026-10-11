"""Build train/val/test OD pairs from Quận 4 seeds with connectivity checks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import networkx as nx


@dataclass(frozen=True)
class ODPair:
    od_id: str
    origin: str
    destination: str
    n_edges: int = 0
    length_m: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_graph(graph_path: Path) -> tuple[nx.DiGraph, dict[str, Any]]:
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    g = nx.DiGraph()
    alleys = payload.get("alleys") or {}
    for e in payload.get("edge_list") or []:
        aid = e["alley_id"]
        length = float((alleys.get(aid) or {}).get("length_m") or 0.0)
        g.add_edge(str(e["u"]), str(e["v"]), alley_id=aid, length_m=length)
    return g, alleys


def _seed_endpoints(seeds_path: Path, alleys: dict[str, Any]) -> list[tuple[str, str, str]]:
    seeds = json.loads(seeds_path.read_text(encoding="utf-8"))
    out: list[tuple[str, str, str]] = []
    for s in seeds:
        od = str(s.get("odId") or s.get("od_id") or "")
        if od not in alleys:
            continue
        a = alleys[od]
        out.append((od, str(a["u"]), str(a["v"])))
    return out


def _path_len(g: nx.DiGraph, u: str, v: str) -> int | None:
    try:
        return len(nx.shortest_path(g, u, v)) - 1
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def _path_length_m(g: nx.DiGraph, u: str, v: str) -> float | None:
    try:
        path = nx.shortest_path(g, u, v)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    total = 0.0
    for a, b in zip(path[:-1], path[1:]):
        total += float(g.edges[a, b].get("length_m") or 0.0)
    return float(total)


def build_connected_od_pool(
    graph_path: Path,
    seeds_path: Path,
    require_path: bool = True,
    min_path_edges: int = 1,
    max_pairs: int = 400,
    min_length_m: float = 0.0,
) -> list[ODPair]:
    """Expand seeds into connected (u_i → v_j) pairs for training diversity."""
    g, alleys = _load_graph(graph_path)
    endpoints = _seed_endpoints(seeds_path, alleys)
    pairs: list[ODPair] = []
    seen: set[tuple[str, str]] = set()
    min_len = float(min_length_m)

    def maybe_add(od_id: str, u: str, v: str, min_edges: int) -> None:
        if u == v:
            return
        n = _path_len(g, u, v)
        if n is None and require_path:
            return
        n = int(n or 0)
        if n < min_edges:
            return
        length = _path_length_m(g, u, v) or 0.0
        if length < min_len:
            return
        key = (u, v)
        if key in seen:
            return
        seen.add(key)
        pairs.append(
            ODPair(od_id=od_id, origin=u, destination=v, n_edges=n, length_m=length)
        )

    for od, u, v in endpoints:
        maybe_add(od, u, v, min_path_edges)

    for i, (od_i, u, _) in enumerate(endpoints):
        for j in range(i + 1, len(endpoints)):
            if len(pairs) >= max_pairs:
                break
            od_j, _, v = endpoints[j]
            maybe_add(f"{od_i}__{od_j}", u, v, max(min_path_edges, 2))
        if len(pairs) >= max_pairs:
            break

    return pairs


def split_od_pairs(
    pairs: list[ODPair],
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> dict[str, list[ODPair]]:
    total = train_ratio + val_ratio + test_ratio
    tr, vr, te = train_ratio / total, val_ratio / total, test_ratio / total
    # Stable shuffle by hash(seed + od_id)
    def sort_key(p: ODPair) -> str:
        h = hashlib.sha256(f"{seed}:{p.od_id}:{p.origin}:{p.destination}".encode()).hexdigest()
        return h

    ordered = sorted(pairs, key=sort_key)
    n = len(ordered)
    if n == 0:
        return {"train": [], "val": [], "test": []}
    n_train = max(1, int(round(n * tr)))
    n_val = max(1, int(round(n * vr))) if n >= 3 else max(0, n - n_train)
    if n_train + n_val >= n:
        n_val = max(0, n - n_train - (1 if n > n_train else 0))
    n_test = n - n_train - n_val
    train = ordered[:n_train]
    val = ordered[n_train : n_train + n_val]
    test = ordered[n_train + n_val : n_train + n_val + n_test]
    # Ensure val/test non-empty when possible
    if not val and train:
        val = [train[-1]]
    if not test and train:
        test = [train[0]]
    return {"train": train, "val": val, "test": test}


def save_split(split: dict[str, list[ODPair]], path: Path) -> None:
    payload = {k: [p.as_dict() for p in v] for k, v in split.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_split(path: Path) -> dict[str, list[ODPair]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        k: [ODPair(**row) for row in rows]
        for k, rows in raw.items()
    }
