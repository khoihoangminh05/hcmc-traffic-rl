"""Quận 4 density: Mapbox seeds → k(t) per time peak (L1) + graph interpolation.

L1 rules:
- Drop rows with duration_sec <= 0
- Do NOT mix morning+evening into one k
- Write one density file per peak; latest points at a single peak (not a mix)
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import GreenshieldsParams, Kalman1D, density_from_speed, speed_from_density

# UTC hours → peak name (aligned with Nest crawl; afternoon = off-peak bridge)
DEFAULT_PEAKS: dict[str, set[int]] = {
    "morning": {0, 1, 2, 3, 4, 5},  # ~07–12 VN
    "afternoon": {6, 7, 8, 9},  # ~13–16 VN (catch-up / off-peak)
    "evening": {10, 11, 12, 13, 14},  # ~17–21 VN
}


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


def _row_duration(row: dict[str, str]) -> float | None:
    try:
        return float(row["duration_sec"])
    except (KeyError, TypeError, ValueError):
        return None


def _row_utc_hour(row: dict[str, str]) -> int | None:
    ts = row.get("timestamp") or ""
    if len(ts) < 13:
        return None
    try:
        return int(ts[11:13])
    except ValueError:
        return None


def read_mapbox_rows(
    csv_path: Path,
    *,
    min_duration: float = 0.0,
    utc_hours: set[int] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Read Mapbox CSV; keep duration > min_duration; optional UTC hour filter."""
    by_od: dict[str, list[dict[str, str]]] = defaultdict(list)
    if not csv_path.exists():
        return by_od
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            od = row.get("od_id") or row.get("odId") or ""
            if not od:
                continue
            dur = _row_duration(row)
            if dur is None or dur <= min_duration:
                continue
            if utc_hours is not None:
                hour = _row_utc_hour(row)
                if hour is None or hour not in utc_hours:
                    continue
            by_od[od].append(row)
    return by_od


def _density_from_mapbox_rows(
    rows: list[dict[str, str]],
    length_m: float,
    params: GreenshieldsParams,
    *,
    min_positive: int = 1,
) -> tuple[float | None, int]:
    """Return (density_k or None, n_positive_duration_samples)."""
    if not rows or length_m <= 0:
        return None, 0
    durs = []
    for r in rows:
        d = _row_duration(r)
        if d is not None and d > 0:
            durs.append(d)
    n_pos = len(durs)
    if n_pos < max(1, int(min_positive)):
        return None, n_pos
    avg_t = sum(durs) / n_pos
    v = length_m / max(avg_t, 0.1)
    v = max(0.5, min(v, params.v_free))
    return density_from_speed(v, params), n_pos


def _hop_distances(
    neighbor_map: dict[str, list[str]], observed: set[str]
) -> dict[str, int]:
    """BFS hop distance from nearest observed alley (inf → omitted)."""
    from collections import deque

    dist: dict[str, int] = {aid: 0 for aid in observed}
    q: deque[str] = deque(observed)
    while q:
        u = q.popleft()
        for v in neighbor_map.get(u, []):
            if v in dist:
                continue
            dist[v] = dist[u] + 1
            q.append(v)
    return dist


def _uncertainty_l3(source: str, n_pos: int, hop: int | None) -> float:
    """Discrete uncertainty levels (≥3) for paper-facing fusion."""
    if source == "observed":
        if n_pos >= 6:
            return 0.008
        if n_pos >= 3:
            return 0.015
        return 0.022
    if source == "interpolated":
        h = 99 if hop is None else hop
        if h <= 1:
            return 0.030
        if h <= 2:
            return 0.040
        return 0.050
    return 0.060  # prior


def fuse_quan4_density(
    graph_path: Path,
    mapbox_csv: Path,
    output_dir: Path,
    time_bucket: str | None = None,
    alley_layer_only: bool = True,
    *,
    by_od: dict[str, list[dict[str, str]]] | None = None,
    write_latest: bool = True,
    file_stem: str | None = None,
    min_positive: int = 3,
) -> tuple[list[AlleyDensity], dict[str, Any]]:
    payload = _load_graph_payload(graph_path)
    alleys: dict[str, Any] = payload.get("alleys") or {}
    if by_od is None:
        by_od = read_mapbox_rows(mapbox_csv, min_duration=0.0)
    params = GreenshieldsParams(v_free=8.0, k_jam=0.18)
    ts = datetime.now(timezone.utc).isoformat()
    bucket = time_bucket or ts[:13]
    min_pos = max(1, int(min_positive))

    targets = {
        aid: a
        for aid, a in alleys.items()
        if (not alley_layer_only) or a.get("layer") == "alley" or a.get("road_class") == "alley"
    }
    if not targets:
        targets = alleys

    neighbor_map = {aid: list(a.get("neighbors") or []) for aid, a in targets.items()}
    filters = {aid: Kalman1D(x=0.04, p=1.0, q=1e-4, r=8e-3) for aid in targets}

    observed: dict[str, float] = {}
    n_pos_by_aid: dict[str, int] = {}
    weak_pos = 0  # had some positive rows but < min_pos
    for aid, a in targets.items():
        length = float(a.get("length_m") or 0.0)
        z, n_pos = _density_from_mapbox_rows(
            by_od.get(aid, []), length, params, min_positive=min_pos
        )
        n_pos_by_aid[aid] = n_pos
        if z is not None:
            observed[aid] = z
        elif n_pos > 0:
            weak_pos += 1

    hop = _hop_distances(neighbor_map, set(observed))

    filled = dict(observed)
    if not filled:
        for aid, a in targets.items():
            filled[aid] = 0.05 if float(a.get("length_m") or 0) < 80 else 0.035

    for _ in range(8):
        nxt = dict(filled)
        for aid in targets:
            if aid in observed:
                continue
            neigh = [n for n in neighbor_map.get(aid, []) if n in filled]
            if not neigh:
                continue
            nxt[aid] = sum(filled[n] for n in neigh) / len(neigh)
        filled = nxt

    for aid in targets:
        filled.setdefault(aid, 0.04)

    states: list[AlleyDensity] = []
    for aid, a in targets.items():
        z = filled[aid]
        n_pos = n_pos_by_aid.get(aid, 0)
        # Measurement noise: fewer samples → trust less
        if aid in observed:
            filters[aid].r = 4e-3 if n_pos >= 6 else 1.2e-2
        k_hat = filters[aid].update(z)
        v_hat = speed_from_density(k_hat, params)
        if aid in observed:
            source = "observed"
        elif any(n in observed for n in neighbor_map.get(aid, [])):
            source = "interpolated"
        else:
            source = "interpolated" if observed else "prior"
        h = hop.get(aid)
        unc = _uncertainty_l3(source, n_pos, h)
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
                uncertainty=round(float(unc), 6),
                source=source,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = file_stem or f"alley_density_{bucket.replace(':', '')}"
    json_path = output_dir / f"{stem}.json"
    payload_out = [asdict(s) for s in states]
    json_path.write_text(json.dumps(payload_out, indent=2, ensure_ascii=False), encoding="utf-8")

    latest = output_dir / "alley_density_latest.json"
    if write_latest:
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
    else:
        gj = output_dir / "quan4_density_latest.geojson"

    unc_levels = sorted({round(float(s.uncertainty), 6) for s in states})
    meta = {
        "time_bucket": bucket,
        "alleys": len(states),
        "observed": sum(1 for s in states if s.source == "observed"),
        "interpolated": sum(1 for s in states if s.source == "interpolated"),
        "prior": sum(1 for s in states if s.source == "prior"),
        "mapbox_rows_used": sum(len(v) for v in by_od.values()),
        "mapbox_od_used": len(by_od),
        "mapbox_csv": str(mapbox_csv),
        "graph": str(graph_path),
        "density_json": str(json_path),
        "wrote_latest": write_latest,
        "density_geojson": str(gj) if write_latest else None,
        "l3": {
            "min_positive": min_pos,
            "weak_positive_below_min": weak_pos,
            "uncertainty_unique_levels": len(unc_levels),
            "uncertainty_levels": unc_levels[:12],
        },
    }
    return states, meta


def fuse_l1_peaks(
    graph_path: Path,
    mapbox_csv: Path,
    output_dir: Path,
    peaks: dict[str, set[int]] | None = None,
    latest_peak: str = "evening",
    *,
    min_positive: int = 3,
) -> dict[str, Any]:
    """L1: one density file per peak; latest = single peak (never mixed day)."""
    peaks = peaks or {k: set(v) for k, v in DEFAULT_PEAKS.items()}
    date_hint = mapbox_csv.stem.replace("travel_time_", "")
    index: dict[str, Any] = {
        "l1": True,
        "mapbox_csv": str(mapbox_csv),
        "peaks": {},
        "latest_peak": latest_peak,
        "rule": "duration_sec > 0; peaks do not mix morning+evening",
        "min_positive": min_positive,
    }
    all_meta: list[dict[str, Any]] = []

    for peak_name, hours in peaks.items():
        by_od = read_mapbox_rows(mapbox_csv, min_duration=0.0, utc_hours=hours)
        bucket = f"{date_hint}/peak_{peak_name}"
        stem = f"alley_density_peak_{peak_name}_{date_hint}"
        write_latest = peak_name == latest_peak
        _states, meta = fuse_quan4_density(
            graph_path,
            mapbox_csv,
            output_dir,
            time_bucket=bucket,
            by_od=by_od,
            write_latest=write_latest,
            file_stem=stem,
            min_positive=min_positive,
        )
        meta["peak"] = peak_name
        meta["utc_hours"] = sorted(hours)
        all_meta.append(meta)
        index["peaks"][peak_name] = {
            "utc_hours": sorted(hours),
            "path": meta["density_json"],
            "observed": meta["observed"],
            "mapbox_rows_used": meta["mapbox_rows_used"],
            "mapbox_od_used": meta["mapbox_od_used"],
            "is_latest": write_latest,
            "l3": meta.get("l3"),
        }
        print(json.dumps(meta, indent=2, ensure_ascii=False))

    if latest_peak not in index["peaks"] and index["peaks"]:
        # fallback: last peak written becomes latest
        last = list(index["peaks"].keys())[-1]
        index["latest_peak"] = last

    index["alley_density_latest"] = str(output_dir / "alley_density_latest.json")
    index_path = output_dir / "density_l1_index.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "density_meta.json").write_text(
        json.dumps(
            {
                "mode": "l1_peaks",
                "index": str(index_path),
                "latest_peak": index["latest_peak"],
                "peaks": index["peaks"],
                "min_positive": min_positive,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps(index, indent=2, ensure_ascii=False))
    return index


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
    p.add_argument(
        "--l1-peaks",
        action="store_true",
        help="L1: fuse morning/evening peaks separately (no day mix)",
    )
    p.add_argument(
        "--latest-peak",
        type=str,
        default="evening",
        choices=["morning", "afternoon", "evening"],
        help="Which peak alley_density_latest.json mirrors",
    )
    p.add_argument(
        "--min-positive",
        type=int,
        default=3,
        help="L3: min positive duration samples / OD to count as observed",
    )
    args = p.parse_args()

    if args.l1_peaks:
        fuse_l1_peaks(
            args.graph,
            args.mapbox,
            args.output,
            latest_peak=args.latest_peak,
            min_positive=args.min_positive,
        )
    else:
        by_od = read_mapbox_rows(args.mapbox, min_duration=0.0)
        _states, meta = fuse_quan4_density(
            args.graph,
            args.mapbox,
            args.output,
            args.time_bucket,
            by_od=by_od,
            write_latest=True,
            min_positive=args.min_positive,
        )
        (args.output / "density_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
