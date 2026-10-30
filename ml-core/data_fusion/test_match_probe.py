"""Tests for data_fusion.match_probe on synthetic Mapbox responses.

    python -m data_fusion.test_match_probe   # prints MATCH_PROBE_TESTS_OK
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import networkx as nx

from .design_probe_routes import DEFAULT_GRAPH, edge_midpoint, load_graph, pick_vias
from .match_probe import _edge_polyline, build_edge_index, match_sample, match_segment, project, run

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / DEFAULT_GRAPH


def _fake_response(graph: dict, path: list[str], speed: float, route_id: str = "r0") -> dict:
    """What driving-traffic would return if it drove `path` at a constant speed."""
    by_uv = {(str(e["u"]), str(e["v"])): e["alley_id"] for e in graph["edge_list"]}
    lonlat: list[list[float]] = []
    for u, v in zip(path[:-1], path[1:]):
        a = graph["alleys"][by_uv[(u, v)]]
        pts = _edge_polyline(a, u, v, graph["nodes_geo"])
        ll = [[x / project(1.0, 0.0)[0], y / project(0.0, 1.0)[1]] for x, y in pts]
        lonlat.extend(ll if not lonlat else ll[1:])
    dist = []
    for (lo0, la0), (lo1, la1) in zip(lonlat[:-1], lonlat[1:]):
        x0, y0 = project(lo0, la0)
        x1, y1 = project(lo1, la1)
        dist.append(math.hypot(x1 - x0, y1 - y0))
    leg = {
        "distance": dist,
        "duration": [d / speed for d in dist],
        "speed": [speed] * len(dist),
        "congestion_numeric": [30] * len(dist),
    }
    return {
        "timestamp": "2026-11-01T01:00:00.000Z",
        "routeId": route_id,
        "profile": "driving-traffic",
        "durationSec": sum(leg["duration"]),
        "distanceM": sum(dist),
        "geometry": lonlat,
        "legs": [leg],
    }


def _long_path(g: nx.DiGraph) -> list[str]:
    nodes = sorted(g.nodes())
    for o in nodes:
        lengths = nx.single_source_dijkstra_path_length(g, o, weight="length_m")
        far = [n for n, d in lengths.items() if 500.0 <= d <= 900.0]
        if far:
            return nx.shortest_path(g, o, sorted(far)[0], weight="length_m")
    raise RuntimeError("no 500–900 m path")


def test_recovers_driven_edges_and_speed() -> None:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    g, _geo = load_graph(GRAPH)
    path = _long_path(g)
    want = {g.edges[u, v]["alley_id"] for u, v in zip(path[:-1], path[1:])}
    idx = build_edge_index(graph)
    obs, hit, total = match_sample(
        idx, _fake_response(graph, path, 4.0),
        max_dist=10.0, max_bearing=math.radians(45.0), min_cover=0.5,
    )
    got = {o["alley_id"] for o in obs}
    recall = len(got & want) / len(want)
    precision = len(got & want) / max(len(got), 1)
    assert recall >= 0.9, f"recall {recall:.2f}"
    assert precision >= 0.9, f"precision {precision:.2f}"
    assert hit / total >= 0.95, f"matched share {hit / total:.2f}"
    for o in obs:
        if o["alley_id"] in want:
            assert abs(o["speed_mps"] - 4.0) < 1e-6, o
            assert abs(float(o["congestion_numeric"]) - 30.0) < 1e-6, o


def test_direction_picks_reverse_edge() -> None:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    g, _geo = load_graph(GRAPH)
    path = _long_path(g)
    rev = list(reversed(path))
    if not all(g.has_edge(u, v) for u, v in zip(rev[:-1], rev[1:])):
        return  # one-way somewhere; the forward test covers matching
    fwd = {g.edges[u, v]["alley_id"] for u, v in zip(path[:-1], path[1:])}
    idx = build_edge_index(graph)
    obs, _, _ = match_sample(
        idx, _fake_response(graph, rev, 4.0),
        max_dist=10.0, max_bearing=math.radians(45.0), min_cover=0.5,
    )
    got = {o["alley_id"] for o in obs}
    assert not (got & fwd), "matched the opposite direction"


def test_run_writes_outputs() -> None:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    g, _geo = load_graph(GRAPH)
    path = _long_path(g)
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        probes = tdp / "probes"
        probes.mkdir()
        line = json.dumps(_fake_response(graph, path, 3.0, "q4p_000"))
        (probes / "probe_2026-11-01.jsonl").write_text(line + "\n", encoding="utf-8")
        routes = tdp / "routes.json"
        exp = [g.edges[u, v]["alley_id"] for u, v in zip(path[:-1], path[1:])]
        routes.write_text(json.dumps([{"routeId": "q4p_000", "expected_alley_ids": exp}]), encoding="utf-8")
        s = run(probes, GRAPH, routes, tdp / "out")
        assert s["n_samples"] == 1 and s["n_obs"] > 0
        assert (tdp / "out" / "edge_obs.csv").exists()
        share = s["designed_alley_share_driven_median"]
        assert share is None or share >= 0.9, share


def test_vias_sit_on_their_alley_edge() -> None:
    """Each via point lies on its alley edge and its bearing points u -> v."""
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    g, _geo = load_graph(GRAPH)
    idx = build_edge_index(graph)
    row_of = {aid: r for r, aid in enumerate(idx.alley_ids)}
    path = _long_path(g)
    edges = list(zip(path[:-1], path[1:]))
    vias = pick_vias(g, edges, 8, 10.0)
    assert len(vias) <= 8
    for u, v in vias:
        aid = g.edges[u, v]["alley_id"]
        lon, lat, b = edge_midpoint(graph, aid, u, v)
        x, y = project(lon, lat)
        step = (math.sin(math.radians(b)), math.cos(math.radians(b)))
        got = match_segment(idx, (x - step[0], y - step[1]), (x + step[0], y + step[1]), 3.0, math.radians(30))
        assert got is not None and idx.alley_ids[got] == aid, (aid, got)
        assert got == row_of[aid]


def main() -> None:
    test_recovers_driven_edges_and_speed()
    print("PASS test_recovers_driven_edges_and_speed")
    test_direction_picks_reverse_edge()
    print("PASS test_direction_picks_reverse_edge")
    test_run_writes_outputs()
    print("PASS test_run_writes_outputs")
    test_vias_sit_on_their_alley_edge()
    print("PASS test_vias_sit_on_their_alley_edge")
    print("MATCH_PROBE_TESTS_OK")


if __name__ == "__main__":
    main()
