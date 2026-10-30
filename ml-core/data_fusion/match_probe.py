"""Match raw Mapbox driving-traffic probes to graph edges (batch, Node 2).

Input: data_raw/mapbox_probe/probe_*.jsonl (live traffic) or
data_raw/mapbox_typical/typical_*.jsonl (Mapbox typical traffic for a future
`depart_at`; pass `--glob "typical_*.jsonl"`), written by the NestJS probe service.
Each line has the full route geometry and per-segment annotations
(distance, duration, speed, congestion_numeric), one value per segment between
consecutive geometry vertices.

Each segment is assigned to the directed graph edge whose polyline is nearest
to the segment midpoint (within `--max-dist-m`) and points the same way
(bearing gap below `--max-bearing-deg`). Per (probe response, edge), the
observed speed is the harmonic distance-weighted mean: matched distance /
matched duration. An edge counts as observed only when the matched distance
covers at least `--min-cover` of its length.

Output:
- <out>/edge_obs.csv: one row per (timestamp, route, edge); `depart_at` is the
  VN local slot for typical samples, empty for live ones
- <out>/match_summary.json: match rate, and per route the share of the
  designed alley edges Mapbox actually drove (does it enter alleys at all?)

    python -m data_fusion.match_probe \
        --probes ../ingestion-worker/data_raw/mapbox_probe \
        --routes ../ingestion-worker/config/probe_routes.quan4.json \
        --out artifacts/out/quan4/probe
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

DEFAULT_GRAPH = Path("artifacts/out/quan4/wcc/alley_graph_wcc.json")
LAT0 = 10.76  # Quận 4; equirectangular projection is exact to ~0.1% here
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))


def project(lon: float, lat: float) -> tuple[float, float]:
    return lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT


@dataclass
class EdgeIndex:
    tree: cKDTree
    point_edge: np.ndarray  # edge row per densified point
    point_bearing: np.ndarray  # radians, direction u -> v at that point
    alley_ids: list[str]
    lengths: np.ndarray
    is_alley: np.ndarray


def _edge_polyline(a: dict[str, Any], u: str, v: str, geo: dict[str, Any]) -> list[tuple[float, float]]:
    coords = a.get("coordinates") or []
    if len(coords) < 2:
        coords = [[geo[u]["lon"], geo[u]["lat"]], [geo[v]["lon"], geo[v]["lat"]]]
    pts = [project(float(c[0]), float(c[1])) for c in coords]
    # Stored geometry may run v -> u; orient it from u.
    pu = project(geo[u]["lon"], geo[u]["lat"]) if u in geo else pts[0]
    if math.dist(pts[-1], pu) < math.dist(pts[0], pu):
        pts.reverse()
    return pts


def build_edge_index(graph: dict[str, Any], step_m: float = 3.0) -> EdgeIndex:
    geo = graph["nodes_geo"]
    alleys = graph["alleys"]
    xs: list[tuple[float, float]] = []
    owner: list[int] = []
    bearing: list[float] = []
    aids: list[str] = []
    lengths: list[float] = []
    is_alley: list[bool] = []
    for row, e in enumerate(graph["edge_list"]):
        a = alleys[e["alley_id"]]
        aids.append(e["alley_id"])
        lengths.append(float(a["length_m"]))
        is_alley.append(a.get("road_class") == "alley" or a.get("layer") == "alley")
        pts = _edge_polyline(a, str(e["u"]), str(e["v"]), geo)
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            seg = math.hypot(x1 - x0, y1 - y0)
            if seg < 1e-6:
                continue
            b = math.atan2(y1 - y0, x1 - x0)
            n = max(1, int(seg // step_m))
            for k in range(n + 1):
                f = k / n
                xs.append((x0 + f * (x1 - x0), y0 + f * (y1 - y0)))
                owner.append(row)
                bearing.append(b)
    return EdgeIndex(
        tree=cKDTree(np.asarray(xs)),
        point_edge=np.asarray(owner, dtype=np.int64),
        point_bearing=np.asarray(bearing),
        alley_ids=aids,
        lengths=np.asarray(lengths),
        is_alley=np.asarray(is_alley, dtype=bool),
    )


def _angle_gap(a: float, b: float) -> float:
    d = abs(a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def match_segment(
    idx: EdgeIndex, p0: tuple[float, float], p1: tuple[float, float], max_dist: float, max_bearing: float
) -> int | None:
    """Edge row for one Mapbox segment, or None."""
    mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    b = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    hits = idx.tree.query_ball_point(mid, r=max_dist)
    if not hits:
        return None
    best, best_d = None, float("inf")
    for h in hits:
        if _angle_gap(b, float(idx.point_bearing[h])) > max_bearing:
            continue
        d = math.dist(mid, idx.tree.data[h])
        if d < best_d:
            best, best_d = int(idx.point_edge[h]), d
    return best


def _flatten_legs(legs: list[dict[str, list[Any]]], key: str) -> list[Any]:
    out: list[Any] = []
    for leg in legs:
        out.extend(leg.get(key) or [])
    return out


def match_sample(
    idx: EdgeIndex, sample: dict[str, Any], *, max_dist: float, max_bearing: float, min_cover: float
) -> tuple[list[dict[str, Any]], float, float]:
    """Edge observations of one probe response, plus (matched m, total m)."""
    geom = [project(float(c[0]), float(c[1])) for c in sample.get("geometry") or []]
    legs = sample.get("legs") or []
    dist = _flatten_legs(legs, "distance")
    dur = _flatten_legs(legs, "duration")
    cong = _flatten_legs(legs, "congestion_numeric")
    n = min(len(geom) - 1, len(dist), len(dur))
    acc: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])  # m, s, cong·m, cong m
    matched_m = 0.0
    total_m = 0.0
    for k in range(max(0, n)):
        dk = float(dist[k] or 0.0)
        tk = float(dur[k] or 0.0)
        total_m += dk
        if dk <= 0.0 or tk <= 0.0:
            continue
        row = match_segment(idx, geom[k], geom[k + 1], max_dist, max_bearing)
        if row is None:
            continue
        matched_m += dk
        a = acc[row]
        a[0] += dk
        a[1] += tk
        c = cong[k] if k < len(cong) else None
        if isinstance(c, (int, float)):
            a[2] += float(c) * dk
            a[3] += dk
    obs: list[dict[str, Any]] = []
    for row, (m, s, cm, cmm) in acc.items():
        cover = m / max(float(idx.lengths[row]), 1e-6)
        if cover < min_cover:
            continue
        obs.append(
            {
                "timestamp": sample["timestamp"],
                "depart_at": sample.get("departAt") or "",
                "route_id": sample["routeId"],
                "alley_id": idx.alley_ids[row],
                "is_alley": bool(idx.is_alley[row]),
                "speed_mps": m / s,
                "congestion_numeric": (cm / cmm) if cmm > 0 else "",
                "matched_m": m,
                "cover": min(cover, 1.0),
            }
        )
    return obs, matched_m, total_m


def iter_samples(probe_dir: Path, pattern: str = "probe_*.jsonl") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(probe_dir.glob(pattern)):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def run(
    probe_dir: Path,
    graph_path: Path,
    routes_path: Path | None,
    out_dir: Path,
    *,
    max_dist: float = 10.0,
    max_bearing_deg: float = 45.0,
    min_cover: float = 0.5,
    pattern: str = "probe_*.jsonl",
) -> dict[str, Any]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    idx = build_edge_index(graph)
    samples = iter_samples(probe_dir, pattern)
    designed: dict[str, set[str]] = {}
    if routes_path and routes_path.exists():
        for r in json.loads(routes_path.read_text(encoding="utf-8")):
            designed[r["routeId"]] = {
                a for a in r.get("expected_alley_ids") or [] if a in set(idx.alley_ids)
            }
    out_dir.mkdir(parents=True, exist_ok=True)
    all_obs: list[dict[str, Any]] = []
    m_hit = 0.0
    m_all = 0.0
    driven: dict[str, set[str]] = defaultdict(set)
    for s in samples:
        obs, mh, ma = match_sample(
            idx, s, max_dist=max_dist, max_bearing=math.radians(max_bearing_deg), min_cover=min_cover
        )
        all_obs.extend(obs)
        m_hit += mh
        m_all += ma
        driven[s["routeId"]].update(o["alley_id"] for o in obs)
    fields = [
        "timestamp", "depart_at", "route_id", "alley_id", "is_alley", "speed_mps",
        "congestion_numeric", "matched_m", "cover",
    ]
    with (out_dir / "edge_obs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_obs)
    alley_set = {a for a, al in zip(idx.alley_ids, idx.is_alley) if al}
    per_route = {}
    for rid, exp in designed.items():
        exp_alley = exp & alley_set
        if exp_alley:
            per_route[rid] = len(driven.get(rid, set()) & exp_alley) / len(exp_alley)
    observed_edges = {o["alley_id"] for o in all_obs}
    summary = {
        "n_samples": len(samples),
        "n_obs": len(all_obs),
        "matched_distance_share": (m_hit / m_all) if m_all > 0 else 0.0,
        "edges_observed": len(observed_edges),
        "alley_edges_observed": len(observed_edges & alley_set),
        "n_edges": len(idx.alley_ids),
        "n_alley_edges": len(alley_set),
        "designed_alley_share_driven_median": float(np.median(list(per_route.values())))
        if per_route
        else None,
        "designed_alley_share_driven_by_route": per_route,
        "params": {"max_dist_m": max_dist, "max_bearing_deg": max_bearing_deg, "min_cover": min_cover},
    }
    (out_dir / "match_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probes", type=Path, required=True)
    ap.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    ap.add_argument("--routes", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-dist-m", type=float, default=10.0)
    ap.add_argument("--max-bearing-deg", type=float, default=45.0)
    ap.add_argument("--min-cover", type=float, default=0.5)
    ap.add_argument("--glob", default="probe_*.jsonl", help='"typical_*.jsonl" for depart_at samples')
    args = ap.parse_args()
    s = run(
        args.probes, args.graph, args.routes, args.out,
        max_dist=args.max_dist_m, max_bearing_deg=args.max_bearing_deg, min_cover=args.min_cover,
        pattern=args.glob,
    )
    print(
        f"[match] samples={s['n_samples']} obs={s['n_obs']} "
        f"matched={100 * s['matched_distance_share']:.1f}% of driven distance | "
        f"edges observed {s['edges_observed']}/{s['n_edges']} "
        f"(alley {s['alley_edges_observed']}/{s['n_alley_edges']}) | "
        f"designed alleys actually driven (median route) = {s['designed_alley_share_driven_median']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
