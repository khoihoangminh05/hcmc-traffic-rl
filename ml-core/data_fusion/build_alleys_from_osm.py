"""Build alley graph from OSM bbox → Mapbox OD pairs (entry/exit of each alley).

Run on local PC or GPU (batch, finite). Requires: osmnx, networkx.

Example:
  python -m data_fusion.build_alleys_from_osm \\
    --north 10.79 --south 10.76 --east 106.72 --west 106.69 \\
    --output artifacts/out/alleys \\
    --export-od ../ingestion-worker/config/od_pairs.generated.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .alley_graph import AlleyStructure, save_graph_artifacts


def _is_alley_like(highway: Any) -> bool:
    if highway is None:
        return False
    vals = highway if isinstance(highway, list) else [highway]
    alley_tags = {
        "residential",
        "living_street",
        "service",
        "unclassified",
        "tertiary",
        "footway",
        "path",
        "alley",
    }
    # Prefer true alleys / narrow local roads; exclude motorway etc.
    return any(str(v) in alley_tags for v in vals)


def build_from_bbox(
    north: float,
    south: float,
    east: float,
    west: float,
    output_dir: Path,
    export_od: Path | None,
    max_alleys: int = 80,
) -> dict[str, Any]:
    try:
        import osmnx as ox
        import networkx as nx
    except ImportError as e:
        raise SystemExit(
            "Need osmnx (+ networkx). pip install osmnx"
        ) from e

    # Drive network in bbox; filter to alley-like edges
    # osmnx >= 1.6: bbox = (left, bottom, right, top) = (west, south, east, north)
    g = ox.graph_from_bbox((west, south, east, north), network_type="drive")
    g = ox.add_edge_speeds(g)
    g = ox.add_edge_travel_times(g)

    # Keep only alley-like edges as DiGraph with stable alley_id
    out = nx.DiGraph()
    count = 0
    for u, v, k, data in g.edges(keys=True, data=True):
        if not _is_alley_like(data.get("highway")):
            continue
        if count >= max_alleys:
            break
        length = float(data.get("length") or 0.0)
        if length < 20 or length > 400:
            continue
        alley_id = f"osm_{u}_{v}_{k}"
        oneway = bool(data.get("oneway", False))
        road_class = "alley"
        hw = data.get("highway")
        if isinstance(hw, list):
            hw = hw[0]
        if hw in {"tertiary", "unclassified", "residential"}:
            road_class = str(hw)
        out.add_edge(
            str(u),
            str(v),
            alley_id=alley_id,
            length_m=length,
            road_class=road_class,
            oneway=oneway,
        )
        count += 1

    if out.number_of_edges() == 0:
        raise SystemExit("No alley-like edges in bbox — widen bbox or raise max_alleys")

    output_dir.mkdir(parents=True, exist_ok=True)
    graph_path = save_graph_artifacts(out, output_dir)

    # Node coords from OSMnx
    node_xy: dict[str, tuple[float, float]] = {}
    for n, nd in g.nodes(data=True):
        if "x" in nd and "y" in nd:
            node_xy[str(n)] = (float(nd["x"]), float(nd["y"]))  # lon, lat

    od_pairs: list[dict[str, str]] = []
    for u, v, data in out.edges(data=True):
        if str(u) not in node_xy or str(v) not in node_xy:
            continue
        lon_o, lat_o = node_xy[str(u)]
        lon_d, lat_d = node_xy[str(v)]
        od_pairs.append(
            {
                "odId": data["alley_id"],
                "origin": f"{lon_o:.6f},{lat_o:.6f}",
                "destination": f"{lon_d:.6f},{lat_d:.6f}",
                "alley_id": data["alley_id"],
            }
        )

    od_path = output_dir / "od_pairs.json"
    # NestJS env expects [{odId, origin, destination}] only
    nest_od = [
        {"odId": p["odId"], "origin": p["origin"], "destination": p["destination"]}
        for p in od_pairs
    ]
    od_path.write_text(json.dumps(nest_od, indent=2), encoding="utf-8")
    if export_od:
        export_od.parent.mkdir(parents=True, exist_ok=True)
        export_od.write_text(json.dumps(nest_od, ensure_ascii=False), encoding="utf-8")

    meta = {
        "bbox": {"north": north, "south": south, "east": east, "west": west},
        "alley_count": len(od_pairs),
        "graph": str(graph_path),
        "od_pairs": str(od_path),
        "export_od": str(export_od) if export_od else None,
    }
    (output_dir / "build_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return meta


def main() -> None:
    p = argparse.ArgumentParser(description="OSM alleys → Mapbox OD pairs")
    p.add_argument("--north", type=float, required=True)
    p.add_argument("--south", type=float, required=True)
    p.add_argument("--east", type=float, required=True)
    p.add_argument("--west", type=float, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--export-od", type=Path, default=None, help="Write NestJS OD JSON")
    p.add_argument("--max-alleys", type=int, default=80)
    args = p.parse_args()
    build_from_bbox(
        args.north,
        args.south,
        args.east,
        args.west,
        args.output,
        args.export_od,
        args.max_alleys,
    )


if __name__ == "__main__":
    main()
