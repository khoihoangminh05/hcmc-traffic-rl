"""L4: camera as secondary prior at alley entries / spine — never interior alley k.

Rules:
- Map cam → nearest graph NODE (entry/spine), not mid-alley geometry.
- Only adjust edges that touch that node (boundary) + optional 1–2 hop decay into alleys.
- Tag source additions as camera_secondary (never camera_direct on interior).
- Mapbox density remains primary; camera blends with low weight / high uncertainty.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def load_camera_catalog(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def node_positions(graph: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Prefer nodes_geo; else midpoint of touching alleys' entry/exit."""
    out: dict[str, tuple[float, float]] = {}
    geo = graph.get("nodes_geo") or {}
    for n, g in geo.items():
        try:
            out[str(n)] = (float(g["lon"]), float(g["lat"]))
        except (KeyError, TypeError, ValueError):
            continue
    if out:
        return out
    # fallback from alley endpoints
    for e in graph.get("edge_list") or []:
        aid = e.get("alley_id")
        a = (graph.get("alleys") or {}).get(aid) or {}
        for key, node in (("entry", e.get("u")), ("exit", e.get("v"))):
            pt = a.get(key)
            if not pt or node is None:
                continue
            try:
                out.setdefault(str(node), (float(pt["lon"]), float(pt["lat"])))
            except (KeyError, TypeError, ValueError):
                pass
    return out


def map_cameras_to_nodes(
    cameras: list[dict[str, Any]],
    node_xy: dict[str, tuple[float, float]],
    *,
    max_dist_m: float = 250.0,
) -> list[dict[str, Any]]:
    """Attach each cam with lon/lat to nearest node within max_dist_m."""
    mapped: list[dict[str, Any]] = []
    for cam in cameras:
        try:
            lon = float(cam["lon"])
            lat = float(cam["lat"])
        except (KeyError, TypeError, ValueError):
            mapped.append(
                {
                    "cameraId": cam.get("cameraId"),
                    "mapped": False,
                    "reason": "missing_lon_lat",
                }
            )
            continue
        best_n, best_d = None, float("inf")
        for n, (x, y) in node_xy.items():
            d = haversine_m(lon, lat, x, y)
            if d < best_d:
                best_d, best_n = d, n
        if best_n is None or best_d > max_dist_m:
            mapped.append(
                {
                    "cameraId": cam.get("cameraId"),
                    "mapped": False,
                    "reason": "outside_radius",
                    "nearest_m": None if best_n is None else round(best_d, 1),
                }
            )
            continue
        mapped.append(
            {
                "cameraId": cam.get("cameraId"),
                "mapped": True,
                "node": best_n,
                "dist_m": round(best_d, 1),
                "lon": lon,
                "lat": lat,
            }
        )
    return mapped


def edges_touching_node(graph: dict[str, Any], node: str) -> list[str]:
    aids: list[str] = []
    for e in graph.get("edge_list") or []:
        if str(e.get("u")) == node or str(e.get("v")) == node:
            aids.append(str(e["alley_id"]))
    return aids


def neighbor_aids(graph: dict[str, Any], aid: str) -> list[str]:
    a = (graph.get("alleys") or {}).get(aid) or {}
    return [str(x) for x in (a.get("neighbors") or [])]


def occupancy_to_delta_k(vehicle_count: float, *, scale: float = 0.002) -> float:
    """Soft positive density nudge from count — capped, never replaces Mapbox."""
    return max(0.0, min(0.04, float(vehicle_count) * scale))


def apply_camera_secondary(
    density_rows: list[dict[str, Any]],
    graph: dict[str, Any],
    cam_maps: list[dict[str, Any]],
    counts_by_cam: dict[str, float],
    *,
    hop_decay: float = 0.45,
    max_hops: int = 2,
    blend: float = 0.25,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Blend camera prior into boundary alleys; mark camera_secondary metadata."""
    by_id = {str(r["alley_id"]): dict(r) for r in density_rows}
    touched: dict[str, dict[str, Any]] = {}

    for m in cam_maps:
        if not m.get("mapped"):
            continue
        cid = str(m["cameraId"])
        node = str(m["node"])
        count = float(counts_by_cam.get(cid, 10.0))  # mild default if no CV yet
        delta0 = occupancy_to_delta_k(count)
        frontier = {aid: 0 for aid in edges_touching_node(graph, node)}
        seen = set(frontier)
        queue = list(frontier.items())
        while queue:
            aid, hop = queue.pop(0)
            if hop > max_hops:
                continue
            weight = (hop_decay**hop) * blend
            if aid not in by_id:
                continue
            row = by_id[aid]
            # Never claim camera_direct / never overwrite source=observed label
            old_k = float(row.get("density_k") or 0.04)
            new_k = old_k + delta0 * weight
            row["density_k"] = round(new_k, 6)
            # bump uncertainty (secondary is less trusted)
            unc = float(row.get("uncertainty") or 0.03)
            row["uncertainty"] = round(min(0.08, unc + 0.01 * (hop + 1)), 6)
            meta = {
                "cameraId": cid,
                "hop": hop,
                "delta_k": round(delta0 * weight, 6),
                "node": node,
            }
            row.setdefault("camera_secondary", [])
            if isinstance(row["camera_secondary"], list):
                row["camera_secondary"].append(meta)
            # source stays observed/interpolated/prior — add flag only
            if row.get("source") not in ("observed", "interpolated", "prior"):
                row["source"] = "prior"
            touched[aid] = meta
            if hop < max_hops:
                for nb in neighbor_aids(graph, aid):
                    if nb not in seen:
                        seen.add(nb)
                        queue.append((nb, hop + 1))

    # Safety: no interior-only alley may be tagged camera_direct
    illegal = [aid for aid, r in by_id.items() if r.get("source") == "camera_direct"]
    out_rows = list(by_id.values())
    summary = {
        "l4": True,
        "cams_mapped": sum(1 for m in cam_maps if m.get("mapped")),
        "cams_unmapped": sum(1 for m in cam_maps if not m.get("mapped")),
        "alleys_touched": len(touched),
        "illegal_camera_direct": illegal,
        "pass_no_camera_direct": len(illegal) == 0,
        "note": "Camera is secondary at entries/spine; Mapbox remains primary in alleys.",
    }
    return out_rows, summary


def load_counts(counts_dir: Path | None) -> dict[str, float]:
    out: dict[str, float] = {}
    if counts_dir is None or not counts_dir.exists():
        return out
    index = counts_dir / "counts_index.json"
    files = list(counts_dir.glob("*.json"))
    if index.exists():
        try:
            idx = json.loads(index.read_text(encoding="utf-8"))
            if isinstance(idx, list):
                for row in idx:
                    cid = row.get("camera_id") or row.get("cameraId")
                    if cid is not None:
                        out[str(cid)] = float(row.get("vehicle_count") or 0)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    for f in files:
        if f.name == "counts_index.json":
            continue
        try:
            row = json.loads(f.read_text(encoding="utf-8"))
            cid = row.get("camera_id") or row.get("cameraId") or f.stem
            out[str(cid)] = float(row.get("vehicle_count") or out.get(str(cid), 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return out


def run_l4(
    graph_path: Path,
    density_path: Path,
    cameras_path: Path,
    output_path: Path,
    *,
    counts_dir: Path | None = None,
    max_dist_m: float = 250.0,
    map_out: Path | None = None,
) -> dict[str, Any]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    dens = json.loads(density_path.read_text(encoding="utf-8"))
    cams = load_camera_catalog(cameras_path)
    node_xy = node_positions(graph)
    cam_maps = map_cameras_to_nodes(cams, node_xy, max_dist_m=max_dist_m)
    counts = load_counts(counts_dir)
    rows, summary = apply_camera_secondary(dens, graph, cam_maps, counts)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    if map_out:
        map_out.parent.mkdir(parents=True, exist_ok=True)
        map_out.write_text(
            json.dumps({"cameras": cam_maps, "summary": summary}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    meta = {
        **summary,
        "graph": str(graph_path),
        "density_in": str(density_path),
        "density_out": str(output_path),
        "cameras": str(cameras_path),
        "nodes_with_geo": len(node_xy),
    }
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="L4 camera secondary prior")
    p.add_argument(
        "--graph",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "wcc" / "alley_graph_wcc.json",
    )
    p.add_argument(
        "--density",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "density" / "alley_density_latest.json",
    )
    p.add_argument(
        "--cameras",
        type=Path,
        default=root.parent / "ingestion-worker" / "config" / "cameras.quan4_entries.json",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "density" / "alley_density_l4_cam.json",
    )
    p.add_argument(
        "--map-out",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "density" / "cam_node_map.json",
    )
    p.add_argument("--counts", type=Path, default=None)
    p.add_argument("--max-dist-m", type=float, default=250.0)
    args = p.parse_args()
    # fallback to city-wide catalog if Q4 entries file missing
    cams = args.cameras
    if not cams.exists():
        alt = root.parent / "ingestion-worker" / "config" / "cameras.hcmc_seed.json"
        if alt.exists():
            cams = alt
    run_l4(
        args.graph,
        args.density,
        cams,
        args.output,
        counts_dir=args.counts,
        max_dist_m=args.max_dist_m,
        map_out=args.map_out,
    )


if __name__ == "__main__":
    main()
