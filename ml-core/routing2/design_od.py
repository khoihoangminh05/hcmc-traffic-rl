"""Design destination zones so that trips have real route choice (batch, Node 2).

Measure used for every network (RESEARCH_V4 §14): a trip o -> z "has choice" when a second route
exists whose free-flow time is at most `--ratio` times the fastest and which shares at most
`--overlap` of the fastest route's length. The second route is the fastest route after the first
route's links are made 3 times slower (it may share the access legs out of a dead-end alley).
Trips shorter than `--min-tt` seconds are not counted. Times are free-flow (length / class speed).

Zones:
1. Gateways: nodes of tertiary-or-higher roads outside the Quận 4 boundary, i.e. the far ends of the
   bridges and border roads (through traffic between Q1, Q7, Q8), thinned to one per `--spacing-m`.
2. The rest: junctions (3 or more neighbours) on any class, ranked by the share of sampled origins
   that have choice to them, taken greedily with at least `--spacing-m` between zones.
The zone list is written into a copy of the graph JSON ("zones"), which routing2.demand.pick_zones
uses in place of farthest-point sampling. The report compares that rule with the designed zones on
the same origins.

    ROUTING2_GRAPH=<graph.json> python -m routing2.design_od --out <graph_with_zones.json> --jobs 16
"""

from __future__ import annotations

import argparse
import json
import math
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import networkx as nx

from .params import DEFAULT_CLASS, ROAD_CLASS

MAJOR = {"tertiary", "secondary", "primary"}
_G: nx.DiGraph | None = None


def node_graph(data: dict) -> nx.DiGraph:
    g = nx.DiGraph()
    for e in data["edge_list"]:
        a = data["alleys"][e["alley_id"]]
        cls = a.get("road_class") or DEFAULT_CLASS
        p = ROAD_CLASS.get(cls, ROAD_CLASS[DEFAULT_CLASS])
        L = max(float(a["length_m"]), 1.0)
        g.add_edge(str(e["u"]), str(e["v"]), t=L / p.v_free, L=L, cls=cls)
    return g


def _init(g: nx.DiGraph) -> None:
    global _G
    _G = g


def choice(pair: tuple[str, str]) -> tuple[float, float, float] | None:
    """(fastest free-flow s, second / fastest, overlap share by length), or None if unreachable."""
    g = _G
    o, z = pair
    try:
        p = nx.shortest_path(g, o, z, weight="t")
    except nx.NetworkXNoPath:
        return None
    e1 = list(zip(p, p[1:]))
    t1 = sum(g[a][b]["t"] for a, b in e1)
    s1 = set(e1)
    q = nx.shortest_path(g, o, z, weight=lambda a, b, d: d["t"] * (3.0 if (a, b) in s1 else 1.0))
    e2 = list(zip(q, q[1:]))
    t2 = sum(g[a][b]["t"] for a, b in e2)
    L1 = sum(g[a][b]["L"] for a, b in e1)
    ov = sum(g[a][b]["L"] for a, b in set(e2) & s1) / L1
    return t1, t2 / t1, ov


def has_choice(r: tuple[float, float, float] | None, args: argparse.Namespace) -> bool | None:
    if r is None or r[0] < args.min_tt:
        return None
    return r[1] <= args.ratio and r[2] <= args.overlap


def xy_of(data: dict) -> dict[str, tuple[float, float]]:
    lat0 = 10.76
    return {n: (float(v["lon"]) * 111_320.0 * math.cos(math.radians(lat0)), float(v["lat"]) * 110_574.0)
            for n, v in data["nodes_geo"].items()}


def farthest_point(cands: list[str], xy: dict, k: int, seed: int = 0) -> list[str]:
    rnd = random.Random(seed)
    chosen = [rnd.choice(cands)]
    d = {n: math.dist(xy[n], xy[chosen[0]]) for n in cands}
    while len(chosen) < k:
        n = max(d, key=d.get)
        chosen.append(n)
        for m in cands:
            d[m] = min(d[m], math.dist(xy[m], xy[n]))
    return chosen


def outside_q4(data: dict, nodes: list[str]) -> set[str]:
    import osmnx as ox
    from shapely.geometry import Point

    poly = ox.geocode_to_gdf(data.get("place") or "Quận 4, Thành phố Hồ Chí Minh, Việt Nam").geometry.iloc[0]
    geo = data["nodes_geo"]
    return {n for n in nodes if not poly.contains(Point(float(geo[n]["lon"]), float(geo[n]["lat"])))}


def main() -> None:
    from .graph import DEFAULT_GRAPH

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--zones", type=int, default=32)
    ap.add_argument("--max-gateways", type=int, default=8)
    ap.add_argument("--internal", type=int, default=24, help="network v2: internal zones beside the exit gates")
    ap.add_argument("--origins", type=int, default=150)
    ap.add_argument("--cands", type=int, default=240)
    ap.add_argument("--spacing-m", type=float, default=250.0)
    ap.add_argument("--ratio", type=float, default=1.3)
    ap.add_argument("--overlap", type=float, default=0.5)
    ap.add_argument("--min-tt", type=float, default=90.0)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    data = json.loads(args.graph.read_text(encoding="utf-8"))
    g = node_graph(data)
    scc = max(nx.strongly_connected_components(g), key=len)
    if not data.get("gates_out"):
        g = g.subgraph(scc).copy()
    xy = xy_of(data)
    und = g.to_undirected()
    junc = [n for n in g if und.degree(n) >= 3 and n in scc]
    major_nodes = {n for a, b, d in g.edges(data=True) if d["cls"] in MAJOR for n in (a, b)}

    # origins weighted like routing2.demand.origin_weights: half the incident alley length + 1 m
    w = {n: 1.0 for n in g}
    for a, b, d in g.edges(data=True):
        if d["cls"] == "alley":
            w[a] += 0.5 * d["L"]
            w[b] += 0.5 * d["L"]
    rnd = random.Random(args.seed)
    nodes = [n for n in g if n in scc]  # origins in the core, as routing2.demand does
    origins = rnd.choices(nodes, weights=[w[n] for n in nodes], k=args.origins)

    out_nodes = outside_q4(data, list(g))
    if data.get("gates_out"):  # network v2: every exit gate is a zone (through traffic ends there)
        gw_all = sorted(str(n) for n in data["gates_out"] if str(n) in g)
        args.max_gateways = len(gw_all)
        args.zones = len(gw_all) + args.internal
        junc = [n for n in junc if n not in out_nodes]  # internal zones inside Quận 4
    else:
        gw_all = sorted(n for n in major_nodes & out_nodes if und.degree(n) >= 2)
    cands = sorted(set(farthest_point(junc, xy, min(args.cands, len(junc)), args.seed)) | set(gw_all))
    old = farthest_point(sorted(scc), xy, min(args.zones, 32), args.seed)  # the old rule, for comparison

    pairs = sorted({(o, z) for z in set(cands) | set(old) for o in origins if o != z})
    with ProcessPoolExecutor(args.jobs, initializer=_init, initargs=(g,)) as ex:
        res = dict(zip(pairs, ex.map(choice, pairs, chunksize=64)))

    def share(zs: list[str], per_origin_cycle: bool = True) -> dict:
        flags = [has_choice(res.get((o, z)), args) for z in zs for o in origins if o != z]
        flags = [f for f in flags if f is not None]
        return {"trips": len(flags), "choice_share": round(sum(flags) / max(1, len(flags)), 3)}

    score = {z: share([z])["choice_share"] for z in cands}
    zones: list[str] = []
    gws = sorted(gw_all, key=lambda n: -score[n])
    for n in gws:
        if len(zones) >= args.max_gateways:
            break
        if data.get("gates_out") or all(math.dist(xy[n], xy[m]) >= args.spacing_m for m in zones):
            zones.append(n)
    n_gw = len(zones)
    for n in sorted(set(cands) - set(gw_all), key=lambda n: -score[n]):
        if len(zones) >= args.zones:
            break
        if all(math.dist(xy[n], xy[m]) >= args.spacing_m for m in zones):
            zones.append(n)

    report = {
        "graph": str(args.graph), "nodes": g.number_of_nodes(), "edges": g.number_of_edges(),
        "criterion": {"ratio": args.ratio, "overlap": args.overlap, "min_tt_s": args.min_tt},
        "old_farthest_point": share(old), "designed": share(zones), "n_gateways": n_gw,
        "gateway_candidates": len(gw_all), "zones": zones,
        "zone_choice_share": {z: score[z] for z in zones},
    }
    out = dict(data)
    out["zones"] = zones
    out["zones_design"] = {k: v for k, v in report.items() if k != "zone_choice_share"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    args.out.with_suffix(".design.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("zones", "zone_choice_share")}, indent=1))


if __name__ == "__main__":
    main()
