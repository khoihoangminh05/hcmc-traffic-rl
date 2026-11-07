"""Design Mapbox probe routes that cover the Quận 4 alley graph.

The v1 seeds were single edges (median 18 m, 7 s): Mapbox returns its speed
model for such a hop, not traffic. A probe here is a 0.3–1.5 km trip whose
`driving-traffic` response carries per-segment speed and congestion along the
whole route, so one request observes tens of edges.

Candidates are origin → alley edge → destination, shortest by length, picked
greedily for weighted edge coverage (alley edges 1.0, other edges 0.5). To keep
Mapbox on the designed path, each probe also carries up to `--n-via` via points
at the midpoints of alley edges along it, with the travel bearing at each one
(driving-traffic accepts 25 coordinates; the service sends the vias as
non-leg `waypoints` with `bearings`). `expected_alley_ids` is the designed
path, used later to measure how often Mapbox actually enters the alleys.

    python -m data_fusion.design_probe_routes --n-routes 100 \
        --out ../ingestion-worker/config/probe_routes.quan4.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np

from .match_probe import M_PER_DEG_LAT, M_PER_DEG_LON, _edge_polyline

MAJOR = {"primary", "secondary", "tertiary"}
DEFAULT_GRAPH = Path("artifacts/out/quan4/wcc/alley_graph_wcc.json")
DEFAULT_OUT = Path("../ingestion-worker/config/probe_routes.quan4.json")


def load_graph(path: Path) -> tuple[nx.DiGraph, dict[str, tuple[float, float]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    alleys = data["alleys"]
    gates = {str(n) for n in data.get("gates_in", []) + data.get("gates_out", [])}
    g = nx.DiGraph()
    for e in data["edge_list"]:
        a = alleys[e["alley_id"]]
        cls = a.get("road_class")
        g.add_edge(
            str(e["u"]),
            str(e["v"]),
            alley_id=e["alley_id"],
            length_m=float(a["length_m"]),
            is_alley=(cls == "alley" or a.get("layer") == "alley"),
            # focus "major" (network v2): main roads, bridges and boundary gate links
            is_target=(cls == "alley" or a.get("layer") == "alley"),
            is_major=cls in MAJOR,
            is_gate=str(e["u"]) in gates or str(e["v"]) in gates,
        )
    geo = {str(n): (float(p["lon"]), float(p["lat"])) for n, p in data["nodes_geo"].items()}
    return g, geo


def _path_edges(path: list[str]) -> list[tuple[str, str]]:
    return list(zip(path[:-1], path[1:]))


def candidate_routes(
    g: nx.DiGraph,
    rng: np.random.Generator,
    n_candidates: int,
    min_m: float,
    max_m: float,
) -> list[dict[str, Any]]:
    """Origin → via → destination, via on an alley edge, both legs shortest by length."""
    alley_edges = [(u, v) for u, v, d in g.edges(data=True) if d["is_target"]]
    nodes = list(g.nodes())
    out: list[dict[str, Any]] = []
    tries = 0
    while len(out) < n_candidates and tries < n_candidates * 20:
        tries += 1
        via_u, via_v = alley_edges[int(rng.integers(len(alley_edges)))]
        o = nodes[int(rng.integers(len(nodes)))]
        d = nodes[int(rng.integers(len(nodes)))]
        if len({o, d, via_u, via_v}) < 4:
            continue
        try:
            leg1 = nx.shortest_path(g, o, via_u, weight="length_m")
            leg2 = nx.shortest_path(g, via_v, d, weight="length_m")
        except nx.NetworkXNoPath:
            continue
        path = leg1 + leg2
        edges = _path_edges(path)
        if len(set(edges)) != len(edges):
            continue
        length = sum(g.edges[e]["length_m"] for e in edges)
        if not (min_m <= length <= max_m):
            continue
        out.append({"origin": o, "via": via_u, "destination": d, "edges": edges, "length_m": length})
    return out


def greedy_cover(
    g: nx.DiGraph, cands: list[dict[str, Any]], n_routes: int
) -> tuple[list[dict[str, Any]], set[tuple[str, str]]]:
    covered: set[tuple[str, str]] = set()
    chosen: list[dict[str, Any]] = []
    weight = {e: g.edges[e]["w"] for e in g.edges()}
    remaining = list(cands)
    for _ in range(n_routes):
        best, best_gain = None, 0.0
        for c in remaining:
            gain = sum(weight[e] for e in set(c["edges"]) - covered)
            if gain > best_gain:
                best, best_gain = c, gain
        if best is None:
            break
        chosen.append(best)
        covered |= set(best["edges"])
        remaining.remove(best)
    return chosen, covered


def edge_midpoint(graph: dict[str, Any], aid: str, u: str, v: str) -> tuple[float, float, float]:
    """(lon, lat, bearing deg clockwise from north) halfway along edge u -> v."""
    pts = _edge_polyline(graph["alleys"][aid], u, v, graph["nodes_geo"])
    seg = [float(np.hypot(x1 - x0, y1 - y0)) for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:])]
    half = sum(seg) / 2.0
    for (x0, y0), (x1, y1), d in zip(pts[:-1], pts[1:], seg):
        if d > 0 and half <= d:
            f = half / d
            x, y = x0 + f * (x1 - x0), y0 + f * (y1 - y0)
            bearing = float(np.degrees(np.arctan2(x1 - x0, y1 - y0)) % 360.0)
            return x / M_PER_DEG_LON, y / M_PER_DEG_LAT, bearing
        half -= d
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    return x1 / M_PER_DEG_LON, y1 / M_PER_DEG_LAT, float(np.degrees(np.arctan2(x1 - x0, y1 - y0)) % 360.0)


def pick_vias(g: nx.DiGraph, edges: list[tuple[str, str]], n_via: int, min_m: float) -> list[tuple[str, str]]:
    """Up to n_via alley edges spread evenly along the path."""
    alley = [e for e in edges if g.edges[e]["is_target"] and g.edges[e]["length_m"] >= min_m]
    if len(alley) <= n_via:
        return alley
    idx = np.linspace(0, len(alley) - 1, n_via).round().astype(int)
    return [alley[i] for i in sorted(set(idx.tolist()))]


def to_probe(
    g: nx.DiGraph,
    graph: dict[str, Any],
    geo: dict[str, tuple[float, float]],
    k: int,
    c: dict[str, Any],
    prefix: str,
    n_via: int,
    via_min_m: float,
) -> dict[str, Any]:
    def fmt(lon: float, lat: float) -> str:
        return f"{lon:.7f},{lat:.7f}"

    end = c["edges"][-1][1]
    coords = [fmt(*geo[c["origin"]])]
    bearings = [""]
    vias = pick_vias(g, c["edges"], n_via, via_min_m)
    for u, v in vias:
        lon, lat, b = edge_midpoint(graph, g.edges[u, v]["alley_id"], u, v)
        coords.append(fmt(lon, lat))
        bearings.append(f"{round(b) % 360},45")
    coords.append(fmt(*geo[end]))
    bearings.append("")
    return {
        "routeId": f"{prefix}_{k:03d}",
        "coordinates": coords,
        "bearings": bearings,
        "nodes": [c["origin"], *[u for u, _ in vias], end],
        "length_m": round(float(c["length_m"]), 1),
        "expected_alley_ids": [g.edges[e]["alley_id"] for e in c["edges"]],
        "n_alley_edges": int(sum(1 for e in c["edges"] if g.edges[e]["is_alley"])),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--n-routes", type=int, default=100)
    ap.add_argument("--n-candidates", type=int, default=6000)
    ap.add_argument("--min-m", type=float, default=300.0)
    ap.add_argument("--max-m", type=float, default=1500.0)
    ap.add_argument("--n-via", type=int, default=8, help="via points per probe (25 coords max)")
    ap.add_argument("--via-min-m", type=float, default=10.0, help="skip shorter alley edges as vias")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--focus", choices=["alley", "major"], default="alley",
                    help="major: vias and coverage weight on main roads and boundary gates (network v2)")
    ap.add_argument("--prefix", default="q4p", help="routeId prefix")
    ap.add_argument("--cycles-per-day", type=int, default=28, help="for the request budget printout")
    args = ap.parse_args()

    g, geo = load_graph(args.graph)
    for u, v, d in g.edges(data=True):
        if args.focus == "major":
            d["is_target"] = d["is_major"] or d["is_gate"]
            d["w"] = 2.0 if d["is_gate"] else (1.0 if d["is_major"] else 0.0)
        else:
            d["w"] = 1.0 if d["is_alley"] else 0.5
    rng = np.random.default_rng(args.seed)
    cands = candidate_routes(g, rng, args.n_candidates, args.min_m, args.max_m)
    chosen, covered = greedy_cover(g, cands, args.n_routes)
    assert 0 <= args.n_via <= 23
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    probes = [to_probe(g, graph, geo, k, c, args.prefix, args.n_via, args.via_min_m) for k, c in enumerate(chosen)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(probes, indent=2, ensure_ascii=False), encoding="utf-8")

    n_alley = sum(1 for e in g.edges() if g.edges[e]["is_target"])
    cov_alley = sum(1 for e in covered if g.edges[e]["is_target"])
    per_month = len(probes) * args.cycles_per_day * 31
    print(
        f"[probe] {len(cands)} candidates -> {len(probes)} routes | "
        f"edges covered {len(covered)}/{g.number_of_edges()} "
        f"(target {cov_alley}/{n_alley}) | "
        f"median length {np.median([p['length_m'] for p in probes]):.0f} m | "
        f"budget {per_month} requests / 31 days at {args.cycles_per_day} cycles/day",
        flush=True,
    )
    print(f"[probe] wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
