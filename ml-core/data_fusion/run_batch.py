"""Batch fusion: Mapbox CSV + CV counts + alley graph → density per alley_id.

Node 2 only: read folders → write fused graph state. No while-True polling.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .alley_graph import load_or_build_graph, save_graph_artifacts, structures_from_graph
from .models import GreenshieldsParams, Kalman1D, density_from_speed, speed_from_density


@dataclass
class AlleyState:
    alley_id: str
    timestamp: str
    length_m: float
    road_class: str
    oneway: bool
    neighbors: list[str]
    density_k: float
    speed_mps: float
    uncertainty: float
    source: str


def _read_mapbox_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def _read_counts(counts_dir: Path) -> list[dict[str, Any]]:
    if not counts_dir.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(counts_dir.glob("*_counts.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def _observed_density_from_counts(
    counts: list[dict[str, Any]], length_m: float
) -> float | None:
    if not counts or length_m <= 0:
        return None
    # crude: vehicles / length as instantaneous occupancy proxy
    mean_veh = sum(float(c.get("vehicle_count", 0)) for c in counts) / len(counts)
    return min(0.17, mean_veh / max(length_m, 1.0))


def _observed_density_from_mapbox(
    rows: list[dict[str, str]], length_m: float, params: GreenshieldsParams
) -> float | None:
    if not rows or length_m <= 0:
        return None
    durations = [float(r["duration_sec"]) for r in rows if r.get("duration_sec")]
    if not durations:
        return None
    avg_t = sum(durations) / len(durations)
    v = length_m / max(avg_t, 0.1)
    return density_from_speed(v, params)


def fuse_alleys(
    graph_path: Path | None,
    mapbox_csv: Path,
    counts_dir: Path,
    output_dir: Path,
) -> list[AlleyState]:
    g = load_or_build_graph(graph_path)
    save_graph_artifacts(g, output_dir)
    structs = structures_from_graph(g)
    mapbox_rows = _read_mapbox_csv(mapbox_csv)
    counts = _read_counts(counts_dir)
    params = GreenshieldsParams()
    ts = datetime.now(timezone.utc).isoformat()

    states: list[AlleyState] = []
    filters: dict[str, Kalman1D] = {aid: Kalman1D() for aid in structs}

    # Spatial interpolation: seed observed alleys, propagate to neighbors
    seed_z: dict[str, float] = {}
    for aid, st in structs.items():
        z_cv = _observed_density_from_counts(counts, st.length_m) if st.road_class == "alley" else None
        z_mb = _observed_density_from_mapbox(mapbox_rows, st.length_m, params)
        if z_cv is not None and z_mb is not None:
            seed_z[aid] = 0.6 * z_cv + 0.4 * z_mb
        elif z_cv is not None:
            seed_z[aid] = z_cv
        elif z_mb is not None:
            seed_z[aid] = z_mb

    # If nothing observed, use mild prior on alleys
    if not seed_z:
        for aid, st in structs.items():
            seed_z[aid] = 0.04 if st.road_class == "alley" else 0.03

    # Graph Laplacian-style fill for missing alleys
    for _ in range(5):
        updated = dict(seed_z)
        for aid, st in structs.items():
            if aid in seed_z and aid in filters:
                continue
            neigh = [n for n in st.neighbors if n in seed_z]
            if not neigh:
                continue
            updated[aid] = sum(seed_z[n] for n in neigh) / len(neigh)
        seed_z = updated

    for aid, st in structs.items():
        z = seed_z.get(aid, 0.03)
        kf = filters[aid]
        k_hat = kf.update(z)
        v_hat = speed_from_density(k_hat, params)
        source = "interpolated" if aid not in seed_z else "fused"
        states.append(
            AlleyState(
                alley_id=aid,
                timestamp=ts,
                length_m=st.length_m,
                road_class=st.road_class,
                oneway=st.oneway,
                neighbors=st.neighbors,
                density_k=round(k_hat, 6),
                speed_mps=round(v_hat, 4),
                uncertainty=round(math.sqrt(kf.p), 6),
                source=source,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    payload = [asdict(s) for s in states]
    (output_dir / "alley_density.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # CSV for SUMO / MARL consumers
    csv_path = output_dir / "alley_density.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "alley_id",
                "timestamp",
                "length_m",
                "road_class",
                "oneway",
                "density_k",
                "speed_mps",
                "uncertainty",
                "source",
            ],
        )
        writer.writeheader()
        for row in payload:
            writer.writerow({k: row[k] for k in writer.fieldnames})

    return states


def run_batch(
    mapbox_csv: Path,
    counts_dir: Path,
    output_dir: Path,
    graph_path: Path | None = None,
) -> list[dict[str, Any]]:
    states = fuse_alleys(graph_path, mapbox_csv, counts_dir, output_dir)
    return [asdict(s) for s in states]


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch alley density fusion")
    parser.add_argument("--mapbox", type=Path, required=True, help="Mapbox travel_time CSV")
    parser.add_argument("--counts", type=Path, required=True, help="CV counts directory")
    parser.add_argument("--output", type=Path, required=True, help="Fusion output directory")
    parser.add_argument("--graph", type=Path, default=None, help="Optional alley_graph.json")
    args = parser.parse_args()
    rows = run_batch(args.mapbox, args.counts, args.output, args.graph)
    print(f"data_fusion: wrote {len(rows)} alley states -> {args.output}")


if __name__ == "__main__":
    main()
