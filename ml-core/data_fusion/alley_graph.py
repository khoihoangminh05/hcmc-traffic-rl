"""Alley graph identity + structure (canonical IDs for twin / MARL)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx


@dataclass
class AlleyStructure:
    alley_id: str
    length_m: float
    road_class: str
    oneway: bool
    neighbors: list[str] = field(default_factory=list)
    u: str = ""
    v: str = ""


def build_demo_alley_graph() -> nx.DiGraph:
    """Small HCMC-style alley subgraph for offline smoke tests."""
    g = nx.DiGraph()
    # Main road spine
    edges = [
        ("n0", "n1", {"alley_id": "main_01", "length_m": 120.0, "road_class": "primary", "oneway": False}),
        ("n1", "n2", {"alley_id": "main_02", "length_m": 100.0, "road_class": "primary", "oneway": False}),
        ("n2", "n3", {"alley_id": "main_03", "length_m": 140.0, "road_class": "secondary", "oneway": False}),
        # Alleys branching off
        ("n1", "n1a", {"alley_id": "alley_01", "length_m": 60.0, "road_class": "alley", "oneway": False}),
        ("n1a", "n2a", {"alley_id": "alley_02", "length_m": 80.0, "road_class": "alley", "oneway": True}),
        ("n2a", "n2", {"alley_id": "alley_03", "length_m": 55.0, "road_class": "alley", "oneway": False}),
        ("n2", "n2b", {"alley_id": "alley_04", "length_m": 70.0, "road_class": "alley", "oneway": False}),
        ("n2b", "n3", {"alley_id": "alley_05", "length_m": 90.0, "road_class": "alley", "oneway": False}),
    ]
    for u, v, attrs in edges:
        g.add_edge(u, v, **attrs)
        if not attrs["oneway"]:
            g.add_edge(v, u, **{**attrs, "alley_id": f"{attrs['alley_id']}_rev"})
    return g


def structures_from_graph(g: nx.DiGraph) -> dict[str, AlleyStructure]:
    out: dict[str, AlleyStructure] = {}
    for u, v, data in g.edges(data=True):
        aid = str(data["alley_id"])
        neighbors = sorted(
            {
                str(g.edges[a, b]["alley_id"])
                for a, b in list(g.out_edges(v)) + list(g.in_edges(u))
                if str(g.edges[a, b]["alley_id"]) != aid
            }
        )
        out[aid] = AlleyStructure(
            alley_id=aid,
            length_m=float(data["length_m"]),
            road_class=str(data["road_class"]),
            oneway=bool(data["oneway"]),
            neighbors=neighbors,
            u=str(u),
            v=str(v),
        )
    return out


def save_graph_artifacts(g: nx.DiGraph, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    structs = {k: asdict(v) for k, v in structures_from_graph(g).items()}
    path = output_dir / "alley_graph.json"
    payload: dict[str, Any] = {
        "nodes": list(g.nodes()),
        "alleys": structs,
        "edge_list": [
            {"u": u, "v": v, "alley_id": d["alley_id"]} for u, v, d in g.edges(data=True)
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_or_build_graph(graph_path: Path | None) -> nx.DiGraph:
    if graph_path and graph_path.exists():
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        g = nx.DiGraph()
        for e in data["edge_list"]:
            aid = e["alley_id"]
            alley = data["alleys"][aid]
            g.add_edge(
                e["u"],
                e["v"],
                alley_id=aid,
                length_m=alley["length_m"],
                road_class=alley["road_class"],
                oneway=alley["oneway"],
                layer=alley.get("layer") or "",
            )
        return g
    return build_demo_alley_graph()
