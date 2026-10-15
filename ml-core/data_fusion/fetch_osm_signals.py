"""Snap OSM traffic signals in the Quận 4 alley bbox onto graph nodes.

Writes sumo-env/quan4_osm_signals.json (tracked) and a sibling copy next to
the graph. Then rebuilds sumo-env/networks/quan4_alleys.net.xml with a static
program. Lights are not learned.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

from data_fusion.export_sumo import write_geo_signal_net

# Graph extent plus a small pad. Place: Quận 4, Thành phố Hồ Chí Minh.
SOUTH, WEST, NORTH, EAST = 10.752, 106.700, 10.762, 106.719
SNAP_M = 40.0
CYCLE_S = 60.0
RED_S = 30.0
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)


def _meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    x = (lon2 - lon1) * 111_320.0 * math.cos(math.radians(lat1))
    y = (lat2 - lat1) * 110_540.0
    return math.hypot(x, y)


def _stable_offset(node: str) -> float:
    import hashlib

    digest = int(hashlib.md5(node.encode("utf-8")).hexdigest()[:8], 16)
    return float(digest % int(CYCLE_S))


def fetch_overpass() -> list[dict]:
    query = f"""
[out:json][timeout:90];
(
  node["highway"="traffic_signals"]({SOUTH},{WEST},{NORTH},{EAST});
  node["crossing"="traffic_signals"]({SOUTH},{WEST},{NORTH},{EAST});
  node["highway"="stop"]({SOUTH},{WEST},{NORTH},{EAST});
);
out body;
"""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last: Exception | None = None
    for url in OVERPASS_URLS:
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"User-Agent": "hcmc-traffic-rl/quan4-signals"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return list(payload.get("elements") or [])
        except Exception as exc:  # noqa: BLE001 — try the next mirror
            last = exc
    raise RuntimeError(f"overpass failed: {last}")


def snap(graph_path: Path, elements: list[dict]) -> dict:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    geo = graph.get("nodes_geo") or {}
    nodes = [(str(k), float(v["lon"]), float(v["lat"])) for k, v in geo.items()]
    signals = []
    stops = []
    rejected = []
    seen: set[str] = set()
    for el in elements:
        lon = el.get("lon")
        lat = el.get("lat")
        if lon is None or lat is None:
            continue
        tags = el.get("tags") or {}
        kind = "stop" if tags.get("highway") == "stop" else "signal"
        best = None
        best_d = 1e9
        for node, nlon, nlat in nodes:
            dist = _meters(float(lon), float(lat), nlon, nlat)
            if dist < best_d:
                best, best_d = node, dist
        row = {
            "osm_id": el.get("id"),
            "lat": lat,
            "lon": lon,
            "node": best if best_d <= SNAP_M else None,
            "nearest_m": None if best is None else round(best_d, 2),
            "dist_m": None if best is None or best_d > SNAP_M else round(best_d, 2),
        }
        if kind == "stop":
            if row["node"] is not None:
                stops.append(row)
            continue
        if row["node"] is None or best in seen:
            rejected.append(row)
            continue
        seen.add(best)
        row["offset_s"] = _stable_offset(best)
        signals.append(row)
    return {
        "source": "overpass",
        "place": "Quận 4, Thành phố Hồ Chí Minh",
        "bbox": [SOUTH, WEST, NORTH, EAST],
        "cycle_s": CYCLE_S,
        "red_s": RED_S,
        "snap_m": SNAP_M,
        "signals": signals,
        "stops": stops,
        "rejected": rejected,
        "unmatched_signals": len(rejected),
        "nodes": [row["node"] for row in signals],
    }


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    graph = repo / "ml-core" / "artifacts" / "out" / "quan4" / "wcc" / "alley_graph_wcc.json"
    if not graph.exists():
        raise SystemExit(f"missing graph {graph}")
    elements = fetch_overpass()
    payload = snap(graph, elements)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    tracked = repo / "sumo-env" / "quan4_osm_signals.json"
    tracked.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text(text, encoding="utf-8")
    graph.with_name("osm_signals_snapped.json").write_text(text, encoding="utf-8")
    net = repo / "sumo-env" / "networks" / "quan4_alleys.net.xml"
    stats = write_geo_signal_net(graph, tracked, net)
    print(
        json.dumps(
            {
                "osm_elements": len(elements),
                "snapped_signals": len(payload["signals"]),
                "snapped_stops": len(payload["stops"]),
                "unmatched_signals": payload["unmatched_signals"],
                **stats,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
