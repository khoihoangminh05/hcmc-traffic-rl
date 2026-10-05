"""Build Quận 4 (HCMC) detailed alley + local-road map from OSM.

Improvements vs v1:
- Do NOT use network_type=drive (it EXCLUDES service=alley — the VN hẻm tag).
- Custom Overpass filter: residential / living_street / service(+alley) / footway+moto.
- simplify=False → keep intermediate vertices (hình học chi tiết hơn).
- Export full LineString geometry + layer (alley vs local vs arterial).
- Honest note: OSM VN hẻm còn thiếu/sai chỗ; map chỉ tốt bằng dữ liệu OSM.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import networkx as nx

from .alley_graph import save_graph_artifacts

PLACE_DEFAULT = "Quận 4, Thành phố Hồ Chí Minh, Việt Nam"

# Vietnam Mapping Guide: hẻm ≈ highway=service + service=alley
# Also many narrow streets tagged residential / living_street.
CUSTOM_FILTERS = [
    '["highway"~"residential|living_street|unclassified|tertiary|secondary"]',
    '["highway"="service"]',
    '["highway"~"footway|path|pedestrian"]["motorcycle"~"yes|designated|permissive"]',
]

EXCLUDE_HIGHWAY = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "construction",
    "proposed",
    "abandoned",
    "elevator",
    "escalator",
    "steps",
    "platform",
}


def _as_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v) for v in val]
    return [str(val)]


def _highway(data: dict[str, Any]) -> str:
    vals = _as_list(data.get("highway"))
    return vals[0] if vals else ""


def _service(data: dict[str, Any]) -> str:
    vals = _as_list(data.get("service"))
    return vals[0] if vals else ""


def _name(data: dict[str, Any]) -> str:
    for key in ("name", "name:vi", "alt_name"):
        vals = _as_list(data.get(key))
        if vals:
            return vals[0]
    return ""


def _is_named_hem(name: str) -> bool:
    """True if OSM name clearly denotes an alley (hẻm / ngõ / ngách)."""
    n = name.strip().lower()
    if not n:
        return False
    if n.startswith(("hẻm", "hem ", "hem", "ngõ", "ngo ", "ngách", "ngach")):
        return True
    padded = f" {n} "
    return any(t in padded for t in (" hẻm ", " hem ", " ngõ ", " ngách ", " ngach "))


def _classify(data: dict[str, Any]) -> str:
    """Return layer: alley | local | secondary | arterial | other.

    Hard rule: primary/secondary/tertiary/trunk NEVER become alley.
    """
    hw = _highway(data)
    svc = _service(data)
    name = _name(data)

    if hw in {
        "primary",
        "primary_link",
        "secondary",
        "secondary_link",
        "tertiary",
        "tertiary_link",
        "trunk",
        "trunk_link",
        "motorway",
        "motorway_link",
    }:
        if hw.startswith(("tertiary", "secondary")):
            return "secondary"
        return "arterial"

    if hw == "service":
        # Vietnam guide: true hẻm = service=alley (or named Hẻm/Ngõ)
        if svc == "alley" or _is_named_hem(name):
            return "alley"
        if svc in {"parking", "parking_aisle", "driveway", "emergency_access"}:
            return "other"
        return "local"

    if hw in {"living_street", "footway", "path", "pedestrian"}:
        return "alley"

    if hw in {"residential", "unclassified", "road"}:
        if _is_named_hem(name):
            return "alley"
        return "local"

    return "other"


def _edge_coords(
    u: Any, v: Any, data: dict[str, Any], node_xy: dict[Any, tuple[float, float]]
) -> list[list[float]]:
    geom = data.get("geometry")
    if geom is not None:
        try:
            return [[float(x), float(y)] for x, y in geom.coords]
        except Exception:
            pass
    if u in node_xy and v in node_xy:
        return [[node_xy[u][0], node_xy[u][1]], [node_xy[v][0], node_xy[v][1]]]
    return []


def build_quan4(
    place: str,
    output_dir: Path,
    export_od: Path | None,
    networks_dir: Path | None,
    max_edges: int | None,
    min_length_m: float,
    max_length_m: float,
    include_secondary: bool,
) -> dict[str, Any]:
    try:
        import osmnx as ox
    except ImportError as e:
        raise SystemExit("pip install osmnx") from e

    # Keep VN-relevant tags
    useful = list(ox.settings.useful_tags_way)
    for t in (
        "service",
        "width",
        "lanes",
        "access",
        "motorcycle",
        "motor_vehicle",
        "name:vi",
        "alt_name",
        "tunnel",
        "bridge",
    ):
        if t not in useful:
            useful.append(t)
    ox.settings.useful_tags_way = useful

    print(f"Downloading detailed OSM graph for: {place}")
    print("Filter: residential|living_street|service(+alley)|footway+moto|… ; simplify=False")
    g_wgs = ox.graph_from_place(
        place,
        custom_filter=CUSTOM_FILTERS,
        simplify=False,
        retain_all=True,
        truncate_by_edge=True,
    )

    node_xy: dict[Any, tuple[float, float]] = {}
    for n, nd in g_wgs.nodes(data=True):
        if "x" in nd and "y" in nd:
            node_xy[n] = (float(nd["x"]), float(nd["y"]))

    out = nx.DiGraph()
    stats = {"alley": 0, "local": 0, "secondary": 0, "arterial": 0, "other": 0, "skipped": 0}
    count = 0
    edge_meta: dict[str, dict[str, Any]] = {}

    for u, v, k, data in g_wgs.edges(keys=True, data=True):
        hw = _highway(data)
        if hw in EXCLUDE_HIGHWAY:
            stats["skipped"] += 1
            continue
        layer = _classify(data)
        if layer == "secondary" and not include_secondary:
            stats["skipped"] += 1
            continue
        if layer == "other":
            stats["skipped"] += 1
            continue

        length = float(data.get("length") or 0.0)
        if length < min_length_m or length > max_length_m:
            stats["skipped"] += 1
            continue
        if max_edges is not None and count >= max_edges:
            break

        alley_id = f"q4_{u}_{v}_{k}"
        name = _name(data)
        coords = _edge_coords(u, v, data, node_xy)
        width = data.get("width")
        lanes = data.get("lanes")

        out.add_edge(
            str(u),
            str(v),
            alley_id=alley_id,
            length_m=length,
            road_class=layer if layer == "alley" else hw or layer,
            layer=layer,
            oneway=bool(data.get("oneway", False)),
            name=name,
            service=_service(data),
            highway=hw,
            width=str(width) if width is not None else "",
            lanes=str(lanes) if lanes is not None else "",
        )
        edge_meta[alley_id] = {
            "coordinates": coords,
            "entry": {"lon": coords[0][0], "lat": coords[0][1]} if coords else None,
            "exit": {"lon": coords[-1][0], "lat": coords[-1][1]} if coords else None,
        }
        stats[layer] = stats.get(layer, 0) + 1
        count += 1

    if out.number_of_edges() == 0:
        raise SystemExit("No edges kept — relax filters or check place name")

    output_dir.mkdir(parents=True, exist_ok=True)
    graph_path = save_graph_artifacts(out, output_dir)

    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["place"] = place
    payload["district"] = "Quan_4_HCMC"
    payload["build_profile"] = "detailed_v2_alley_inclusive"
    payload["stats"] = stats
    payload["nodes_geo"] = {
        str(n): {"lon": xy[0], "lat": xy[1]} for n, xy in node_xy.items() if str(n) in out.nodes
    }

    for aid, alley in payload["alleys"].items():
        meta = edge_meta.get(aid, {})
        for _, _, d in out.edges(data=True):
            if d["alley_id"] == aid:
                alley["name"] = d.get("name", "")
                alley["layer"] = d.get("layer", "")
                alley["highway"] = d.get("highway", "")
                alley["service"] = d.get("service", "")
                alley["width"] = d.get("width", "")
                alley["lanes"] = d.get("lanes", "")
                break
        alley["coordinates"] = meta.get("coordinates") or []
        alley["entry"] = meta.get("entry")
        alley["exit"] = meta.get("exit")

    graph_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # OD for later density: ALLEY layer only (never secondary/arterial)
    nest_od: list[dict[str, str]] = []
    for aid, alley in payload["alleys"].items():
        if alley.get("layer") != "alley":
            continue
        entry, ex = alley.get("entry"), alley.get("exit")
        if not entry or not ex:
            continue
        nest_od.append(
            {
                "odId": aid,
                "origin": f"{entry['lon']:.6f},{entry['lat']:.6f}",
                "destination": f"{ex['lon']:.6f},{ex['lat']:.6f}",
            }
        )
    od_path = output_dir / "od_pairs.json"
    od_path.write_text(json.dumps(nest_od, indent=2), encoding="utf-8")
    if export_od:
        export_od.parent.mkdir(parents=True, exist_ok=True)
        export_od.write_text(json.dumps(nest_od, ensure_ascii=False), encoding="utf-8")

    # GeoJSON: default file = HẺM ONLY (không lẫn đường to)
    features: list[dict[str, Any]] = []
    for aid, alley in payload["alleys"].items():
        coords = alley.get("coordinates") or []
        if len(coords) < 2:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "alley_id": aid,
                    "layer": alley.get("layer"),
                    "highway": alley.get("highway"),
                    "service": alley.get("service"),
                    "road_class": alley.get("road_class"),
                    "length_m": alley.get("length_m"),
                    "name": alley.get("name", ""),
                    "oneway": alley.get("oneway"),
                    "width": alley.get("width", ""),
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )

    alley_only = [f for f in features if f["properties"].get("layer") == "alley"]
    local_only = [f for f in features if f["properties"].get("layer") == "local"]
    spine = [f for f in features if f["properties"].get("layer") in {"secondary", "arterial"}]

    # Hard QA: no arterial highway tags inside alley layer
    arterial_hw = {
        "primary",
        "primary_link",
        "secondary",
        "secondary_link",
        "tertiary",
        "tertiary_link",
        "trunk",
        "trunk_link",
        "motorway",
        "motorway_link",
    }
    bad = [
        f
        for f in alley_only
        if f["properties"].get("highway") in arterial_hw
    ]
    if bad:
        raise SystemExit(
            f"QA FAIL: {len(bad)} arterial edges mislabeled as alley — fix _classify"
        )

    gj_path = output_dir / "quan4_alleys.geojson"
    gj_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": alley_only}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    gj_all = output_dir / "quan4_network_all.geojson"
    gj_all.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    gj_spine = output_dir / "quan4_roads_spine.geojson"
    gj_spine.write_text(
        json.dumps({"type": "FeatureCollection", "features": spine}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    gj_local = output_dir / "quan4_local_streets.geojson"
    gj_local.write_text(
        json.dumps({"type": "FeatureCollection", "features": local_only}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if networks_dir:
        from .export_sumo import write_net_xml

        networks_dir.mkdir(parents=True, exist_ok=True)
        net_path = networks_dir / "quan4_alleys.net.xml"
        write_net_xml(graph_path, net_path)
    else:
        net_path = None

    index_rows = []
    for aid, alley in sorted(payload["alleys"].items()):
        index_rows.append(
            {
                "alley_id": aid,
                "name": alley.get("name", ""),
                "layer": alley.get("layer"),
                "highway": alley.get("highway"),
                "service": alley.get("service"),
                "length_m": alley.get("length_m"),
                "oneway": alley.get("oneway"),
                "width": alley.get("width", ""),
                "vertex_count": len(alley.get("coordinates") or []),
                "entry": alley.get("entry"),
                "exit": alley.get("exit"),
                "neighbors_count": len(alley.get("neighbors") or []),
            }
        )
    index_path = output_dir / "alley_index.json"
    index_path.write_text(json.dumps(index_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    meta = {
        "place": place,
        "district": "Quan_4_HCMC",
        "build_profile": "detailed_v2_alley_inclusive",
        "nodes": out.number_of_nodes(),
        "edges": out.number_of_edges(),
        "stats": stats,
        "alleys_only_features": len(alley_only),
        "local_features": len(local_only),
        "spine_features": len(spine),
        "od_pairs_alley_only": len(nest_od),
        "graph": str(graph_path),
        "geojson_alleys": str(gj_path),
        "geojson_all": str(gj_all),
        "geojson_spine": str(gj_spine),
        "qa": "PASS — zero primary/secondary/tertiary in alley layer",
        "alley_index": str(index_path),
        "export_od": str(export_od) if export_od else None,
        "sumo_net": str(net_path) if net_path else None,
        "limitations": (
            "OSM Vietnam often misses or misplaces hẻm (tube houses obscure imagery). "
            "This build includes service=alley + residential + moto-accessible footways; "
            "ground survey / JOSM edits still needed for true completeness."
        ),
    }
    (output_dir / "build_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


def main() -> None:
    p = argparse.ArgumentParser(description="Rebuild detailed Quận 4 alley map from OSM")
    p.add_argument("--place", default=PLACE_DEFAULT)
    p.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "artifacts" / "out" / "quan4",
    )
    p.add_argument(
        "--export-od",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "ingestion-worker"
        / "config"
        / "od_pairs.quan4.json",
    )
    p.add_argument(
        "--networks-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "sumo-env" / "networks",
    )
    p.add_argument("--max-edges", type=int, default=None)
    p.add_argument("--min-length-m", type=float, default=5.0)
    p.add_argument("--max-length-m", type=float, default=800.0)
    p.add_argument(
        "--no-secondary",
        action="store_true",
        help="Drop tertiary/secondary spine (alleys+local only)",
    )
    args = p.parse_args()
    build_quan4(
        args.place,
        args.output,
        args.export_od,
        args.networks_dir,
        args.max_edges,
        args.min_length_m,
        args.max_length_m,
        include_secondary=not args.no_secondary,
    )


if __name__ == "__main__":
    main()
