"""Quận 4 density step: Mapbox seeds (per alley_id) + graph → k(t) for ALL alleys.

Matching rule: travel_time CSV `od_id` == `alley_id` (seed observations).
Unobserved alleys get neighbor interpolation + Kalman.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import GreenshieldsParams, Kalman1D, density_from_speed, speed_from_density


@dataclass
class AlleyDensity:
    alley_id: str
    timestamp: str
    time_bucket: str
    length_m: float
    layer: str
    highway: str
    name: str
    density_k: float
    speed_mps: float
    uncertainty: float
    source: str  # observed | interpolated | prior


def _load_graph_payload(graph_path: Path) -> dict[str, Any]:
    return json.loads(graph_path.read_text(encoding="utf-8"))


def _read_mapbox_by_od(csv_path: Path) -> dict[str, list[dict[str, str]]]:
    by_od: dict[str, list[dict[str, str]]] = defaultdict(list)
    if not csv_path.exists():
        return by_od
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            od = row.get("od_id") or row.get("odId") or ""
            if od:
                by_od[od].append(row)
    return by_od


def _density_from_mapbox_rows(
    rows: list[dict[str, str]], length_m: float, params: GreenshieldsParams
) -> float | None:
    if not rows or length_m <= 0:
        return None
    durs = []
    for r in rows:
        try:
            durs.append(float(r["duration_sec"]))
        except (KeyError, ValueError, TypeError):
            continue
    if not durs:
        return None
    avg_t = sum(durs) / len(durs)
    v = length_m / max(avg_t, 0.1)
    # Clamp to plausible alley speeds
    v = max(0.5, min(v, params.v_free))
    return density_from_speed(v, params)


def fuse_quan4_density(
    graph_path: Path,
    mapbox_csv: Path,
    output_dir: Path,
    time_bucket: str | None = None,
    alley_layer_only: bool = True,
) -> list[AlleyDensity]:
    payload = _load_graph_payload(graph_path)
    alleys: dict[str, Any] = payload.get("alleys") or {}
    by_od = _read_mapbox_by_od(mapbox_csv)
    params = GreenshieldsParams(v_free=8.0, k_jam=0.18)  # alley-ish free speed
    ts = datetime.now(timezone.utc).isoformat()
    bucket = time_bucket or ts[:13]  # YYYY-MM-DDTHH

    # Restrict to alley layer for density product
    targets = {
        aid: a
        for aid, a in alleys.items()
        if (not alley_layer_only) or a.get("layer") == "alley" or a.get("road_class") == "alley"
    }
    if not targets:
        # fallback: all edges if layer missing (older graphs)
        targets = alleys

    neighbor_map = {aid: list(a.get("neighbors") or []) for aid, a in targets.items()}
    filters = {aid: Kalman1D(x=0.04, p=1.0, q=1e-4, r=8e-3) for aid in targets}

    observed: dict[str, float] = {}
    for aid, a in targets.items():
        length = float(a.get("length_m") or 0.0)
        z = _density_from_mapbox_rows(by_od.get(aid, []), length, params)
        if z is not None:
            observed[aid] = z

    # Graph diffusion fill
    filled = dict(observed)
    if not filled:
        # mild prior by length class
        for aid, a in targets.items():
            filled[aid] = 0.05 if float(a.get("length_m") or 0) < 80 else 0.035

    for _ in range(8):
        nxt = dict(filled)
        for aid, a in targets.items():
            if aid in observed:
                continue
            neigh = [n for n in neighbor_map.get(aid, []) if n in filled]
            if not neigh:
                continue
            nxt[aid] = sum(filled[n] for n in neigh) / len(neigh)
        filled = nxt

    # ensure every target has a value
    for aid in targets:
        filled.setdefault(aid, 0.04)

    states: list[AlleyDensity] = []
    for aid, a in targets.items():
        z = filled[aid]
        k_hat = filters[aid].update(z)
        v_hat = speed_from_density(k_hat, params)
        if aid in observed:
            source = "observed"
        elif aid in filled and any(n in observed for n in neighbor_map.get(aid, [])):
            source = "interpolated"
        else:
            source = "interpolated" if observed else "prior"
        states.append(
            AlleyDensity(
                alley_id=aid,
                timestamp=ts,
                time_bucket=bucket,
                length_m=float(a.get("length_m") or 0.0),
                layer=str(a.get("layer") or a.get("road_class") or ""),
                highway=str(a.get("highway") or ""),
                name=str(a.get("name") or ""),
                density_k=round(float(k_hat), 6),
                speed_mps=round(float(v_hat), 4),
                uncertainty=round(math.sqrt(filters[aid].p), 6),
                source=source,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"alley_density_{bucket.replace(':', '')}.json"
    latest = output_dir / "alley_density_latest.json"
    payload_out = [asdict(s) for s in states]
    json_path.write_text(json.dumps(payload_out, indent=2, ensure_ascii=False), encoding="utf-8")
    latest.write_text(json.dumps(payload_out, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = output_dir / "alley_density_latest.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "alley_id",
                "timestamp",
                "time_bucket",
                "length_m",
                "layer",
                "highway",
                "name",
                "density_k",
                "speed_mps",
                "uncertainty",
                "source",
            ],
        )
        w.writeheader()
        for row in payload_out:
            w.writerow(row)

    # Density GeoJSON (reuse coordinates from graph)
    features = []
    for s in states:
        a = alleys.get(s.alley_id) or {}
        coords = a.get("coordinates") or []
        if len(coords) < 2:
            entry, ex = a.get("entry"), a.get("exit")
            if entry and ex:
                coords = [[entry["lon"], entry["lat"]], [ex["lon"], ex["lat"]]]
        if len(coords) < 2:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "alley_id": s.alley_id,
                    "density_k": s.density_k,
                    "speed_mps": s.speed_mps,
                    "uncertainty": s.uncertainty,
                    "source": s.source,
                    "time_bucket": s.time_bucket,
                    "name": s.name,
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )
    gj = output_dir / "quan4_density_latest.geojson"
    gj.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    meta = {
        "time_bucket": bucket,
        "alleys": len(states),
        "observed": sum(1 for s in states if s.source == "observed"),
        "interpolated": sum(1 for s in states if s.source == "interpolated"),
        "prior": sum(1 for s in states if s.source == "prior"),
        "mapbox_csv": str(mapbox_csv),
        "graph": str(graph_path),
        "density_json": str(latest),
        "density_geojson": str(gj),
    }
    (output_dir / "density_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    return states


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="Fuse Quận 4 alley densities k(t)")
    p.add_argument(
        "--graph",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "alley_graph.json",
    )
    p.add_argument(
        "--mapbox",
        type=Path,
        required=True,
        help="CSV from NestJS data_raw/mapbox/travel_time_YYYY-MM-DD.csv",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "density",
    )
    p.add_argument("--time-bucket", type=str, default=None)
    args = p.parse_args()
    fuse_quan4_density(args.graph, args.mapbox, args.output, args.time_bucket)


if __name__ == "__main__":
    main()
