"""Quận 4 network for routing2 from the full OSM road graph (batch, Node 2).

Why: the old twin (`build_quan4_map` + `export_wcc_subgraph`) had no `primary` in its filter,
dropped `trunk`, and kept only alleys plus roads one hop from an alley. Alleys connect to each
other through those main roads, so the twin was a tree: 886 nodes, 67% of links were cut edges, and
only about 20% of trips had a second route within 1.3x free-flow time (2026-11-06, RESEARCH_V4 §14).

Here (v2, 2026-11-07, after the audit in .docs/AUDIT_SIM.md):
- Ways with motorcycle=no are dropped (N2): the network is the one motorcycles may use.
- The strongly connected core plus the one-way approaches into it and exits out of it (N3); nodes
  on tertiary-or-higher roads within 40 m of the area edge are the gates for traffic from other
  districts (`gates_in`, `gates_out`).
- Free speed per class from Mapbox at 05h (S1), written per edge as `v_free`.
- Area: the OSM boundary of Quận 4, buffered by `--buffer-m` so the bridges and their far ends are
  in (through traffic between Q1, Q7 and Q8 crosses Q4).
- Every drivable class from trunk down to service, plus footways that allow motorcycles. Excluded:
  motorway, construction, steps, parking aisles, driveways, private access.
- Classes for routing2.params: alley (same rule as build_quan4_map._classify), service, residential,
  tertiary, secondary, primary (primary and trunk with links).
- Lanes per direction: OSM `lanes` (halved on two-way ways), else 2 for primary and secondary, 1 below.
- Simplified to real junctions, plus nodes that carry a traffic signal; the largest strongly
  connected component only.
- Signals: OSM nodes with highway=traffic_signals in the same area, written as the sidecar
  `osm_signals_snapped.json` (offset from a hash of the node id, cycle 60 s, as the old file).

Output (same schema as alley_graph_wcc.json): <out>/alley_graph_full.json and the signal sidecar.

    python -m data_fusion.build_quan4_full --out artifacts/out/quan4/full
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import networkx as nx

from .build_quan4_map import PLACE_DEFAULT, _as_list, _classify, _name, _service

FILTER = (
    '["highway"~"^(trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|'
    'tertiary_link|unclassified|residential|living_street|service|road|footway|path|pedestrian)$"]'
    '["access"!~"private|no"]["motor_vehicle"!~"no"]'
)
SKIP_SERVICE = {"parking", "parking_aisle", "driveway", "emergency_access", "drive-through"}
FOOT = {"footway", "path", "pedestrian"}
CLASS_OF_HW = {
    "trunk": "primary", "trunk_link": "primary", "primary": "primary", "primary_link": "primary",
    "secondary": "secondary", "secondary_link": "secondary",
    "tertiary": "tertiary", "tertiary_link": "tertiary",
    "residential": "residential", "unclassified": "residential", "road": "residential",
    "living_street": "alley", "service": "service",
}
DEFAULT_LANES = {"primary": 2, "secondary": 2}
# Free speed per class, m/s (audit S1): median per-edge Mapbox driving-traffic speed at 05h VN time,
# 30/10-07/11 (diag_v6/probe_full, 783 matched edges). Alley and service: Mapbox drives cars there
# (3.05 and 3.25 m/s); motorcycles are faster, so the old assumed values stay, marked as assumptions.
V_FREE = {"primary": 8.86, "secondary": 7.17, "tertiary": 5.54, "residential": 5.27,
          "service": 5.0, "alley": 4.5}
MAJOR = {"primary", "secondary", "tertiary"}
OVERPASS = ["https://overpass-api.de/api", "https://overpass.private.coffee/api",
            "https://overpass.kumi.systems/api"]


def _first(v: Any) -> str:
    vals = _as_list(v)
    return vals[0] if vals else ""


def road_class(data: dict[str, Any]) -> str | None:
    """routing2 class of an OSM way, or None to drop it."""
    hw = _first(data.get("highway"))
    if _first(data.get("motorcycle")) == "no":  # e.g. Võ Văn Kiệt main lanes, Hầm Sông Sài Gòn (audit N2)
        return None
    if hw in FOOT:
        moto = _first(data.get("motorcycle"))
        return "alley" if moto in {"yes", "designated", "permissive"} else None
    if hw == "service" and _service(data) in SKIP_SERVICE:
        return None
    if hw not in CLASS_OF_HW:
        return None
    if _classify(data) == "alley":
        return "alley"
    return CLASS_OF_HW[hw]


def lanes_per_dir(data: dict[str, Any], cls: str) -> int:
    raw = _first(data.get("lanes"))
    oneway = str(_first(data.get("oneway"))).lower() in {"true", "yes", "1"}
    try:
        n = int(float(raw.split(";")[0]))
        return max(1, n if oneway else n // 2)
    except (ValueError, AttributeError):
        return DEFAULT_LANES.get(cls, 1)


def build(place: str, out: Path, buffer_m: float) -> dict[str, Any]:
    import osmnx as ox

    ox.settings.use_cache = True
    ox.settings.requests_timeout = 300
    ox.settings.useful_tags_way = sorted(set(ox.settings.useful_tags_way) | {
        "service", "lanes", "motorcycle", "motor_vehicle", "access", "name:vi", "alt_name", "width"})
    area = ox.geocode_to_gdf(place)
    crs = area.estimate_utm_crs()
    poly = area.to_crs(crs).buffer(buffer_m).to_crs(4326).iloc[0]
    raw = None
    for attempt in range(12):  # public Overpass servers are often full; rotate and back off
        ox.settings.overpass_url = OVERPASS[attempt % len(OVERPASS)]
        try:
            raw = ox.graph_from_polygon(poly, custom_filter=FILTER, simplify=False, retain_all=True,
                                        truncate_by_edge=True)
            break
        except Exception as ex:  # noqa: BLE001
            print(f"[build_quan4_full] {ox.settings.overpass_url}: {str(ex)[:80]}", flush=True)
            time.sleep(min(600, 30 * 2 ** (attempt // len(OVERPASS))))
    if raw is None:
        raise SystemExit("Overpass unavailable")
    drop = [(u, v, k) for u, v, k, d in raw.edges(keys=True, data=True) if road_class(d) is None]
    raw.remove_edges_from(drop)
    raw.remove_nodes_from([n for n in list(raw.nodes) if raw.degree(n) == 0])
    for _, d in raw.nodes(data=True):
        sig = d.get("highway") == "traffic_signals"
        d.pop("highway", None)
        if sig:
            d["sig"] = 1
    for _, _, d in raw.edges(data=True):
        d["cls"] = road_class(d)
    g = ox.simplify_graph(raw, node_attrs_include=["sig"], edge_attrs_differ=["cls"])
    core = max(nx.strongly_connected_components(g), key=len)
    # Keep the one-way approaches into the core and the exits out of it (audit N3): divided roads and
    # bridge ramps cut at the area boundary are dead ends that a strong component would drop, yet
    # they are where traffic from other districts enters and leaves.
    c0 = next(iter(core))
    keep = core | nx.ancestors(g, c0) | nx.descendants(g, c0)
    g = g.subgraph(keep).copy()
    ring = area.to_crs(crs).buffer(buffer_m).iloc[0].exterior
    from shapely.geometry import Point
    from pyproj import Transformer

    to_m = Transformer.from_crs(4326, crs, always_xy=True).transform
    near_edge = {n for n, d in g.nodes(data=True) if ring.distance(Point(*to_m(d["x"], d["y"]))) < 40.0}
    major_at = {n for u, v, d in g.edges(data=True) if _first(d["cls"]) in MAJOR for n in (u, v)}
    gates_in = sorted(str(n) for n in near_edge & major_at if g.out_degree(n) > 0 and (n not in core or g.in_degree(n) <= 1))
    gates_out = sorted(str(n) for n in near_edge & major_at if g.in_degree(n) > 0 and (n not in core or g.out_degree(n) <= 1))

    nodes_geo = {str(n): {"lon": float(d["x"]), "lat": float(d["y"])} for n, d in g.nodes(data=True)}
    alleys: dict[str, dict[str, Any]] = {}
    edge_list = []
    seen: set[tuple[str, str]] = set()
    stats: dict[str, int] = {}
    for u, v, k, d in sorted(g.edges(keys=True, data=True), key=lambda e: float(e[3]["length"])):
        su, sv = str(u), str(v)
        if su == sv or (su, sv) in seen:  # SUMO plain edges need a unique (from, to); keep the shortest
            continue
        seen.add((su, sv))
        cls = _first(d["cls"])
        aid = f"q4_{su}_{sv}_{k}"
        geom = d.get("geometry")
        coords = ([[float(x), float(y)] for x, y in geom.coords] if geom is not None
                  else [[nodes_geo[su]["lon"], nodes_geo[su]["lat"]], [nodes_geo[sv]["lon"], nodes_geo[sv]["lat"]]])
        alleys[aid] = {
            "alley_id": aid, "u": su, "v": sv, "length_m": float(d["length"]), "road_class": cls,
            "layer": "alley" if cls == "alley" else cls, "highway": _first(d.get("highway")),
            "name": _name(d), "lanes": lanes_per_dir(d, cls), "coordinates": coords,
            "v_free": V_FREE[cls],
        }
        edge_list.append({"u": su, "v": sv, "alley_id": aid})
        stats[cls] = stats.get(cls, 0) + 1
    # the dedup can only drop parallel edges, so the core stays strongly connected; check anyway
    h = nx.DiGraph([(e["u"], e["v"]) for e in edge_list])
    if len(max(nx.strongly_connected_components(h), key=len)) != len(core):
        raise SystemExit("core lost strong connectivity after dedup")

    signals = []
    for n, d in g.nodes(data=True):
        if d.get("sig"):
            off = int(hashlib.sha1(str(n).encode()).hexdigest(), 16) % 60
            signals.append({"osm_id": int(n), "node": str(n), "lat": float(d["y"]), "lon": float(d["x"]),
                            "dist_m": 0.0, "offset_s": float(off)})
    out.mkdir(parents=True, exist_ok=True)
    payload = {"place": place, "buffer_m": buffer_m, "build_profile": "full_osm_v2", "stats": stats,
               "nodes_geo": nodes_geo, "alleys": alleys, "edge_list": edge_list,
               "gates_in": gates_in, "gates_out": gates_out, "core_nodes": len(core)}
    (out / "alley_graph_full.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (out / "osm_signals_snapped.json").write_text(json.dumps(
        {"source": "overpass", "place": place, "cycle_s": 60.0, "red_s": 30.0, "signals": signals},
        indent=1), encoding="utf-8")
    meta = {"nodes": len(nodes_geo), "core_nodes": len(core), "edges": len(edge_list), "classes": stats,
            "signals": len(signals), "gates_in": len(gates_in), "gates_out": len(gates_out),
            "area_bounds": [round(float(b), 5) for b in poly.bounds]}
    (out / "build_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--place", default=PLACE_DEFAULT)
    ap.add_argument("--buffer-m", type=float, default=250.0)
    ap.add_argument("--out", type=Path, default=Path("artifacts/out/quan4/full"))
    args = ap.parse_args()
    print(json.dumps(build(args.place, args.out, args.buffer_m), indent=2), flush=True)


if __name__ == "__main__":
    main()
