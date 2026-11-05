"""Alley widths for the Quan 4 graph, two free sources (batch; explicit outputs, finite work).

OSM has no width on any alley link, so the SUMO net assumes a value. This gives evidence for it:

- `sample`: a stratified sample of alleys for a person to label on street imagery. Writes a CSV with
  a street-view link per alley and empty columns to fill. Strata: length x whether the alley yields
  into a larger road at its end.
- `osm`: estimates width as the free space between building footprints on each side of the alley,
  at points along it. Reports coverage honestly: a side with no building within --search-m gives no
  estimate. The value is an upper bound on the drivable width (walls, not parked bikes or stalls)
  and needs the labelled sample to check it. Tried 2026-11-04: OSM has too few footprints here (2 of
  730 alleys), so this is not usable for Quan 4. Overpass responses are cached under --out.

    python -m data_fusion.alley_width sample --n 50 --csv ../.docs/results_alley/alley_width_sample.csv
    python -m data_fusion.alley_width osm --out artifacts/out/quan4/alley_width
    python -m data_fusion.alley_width test     # no network
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics as st
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

from .match_probe import _edge_polyline, project

GRAPH = Path("artifacts/out/quan4/wcc/alley_graph_wcc.json")
MIRRORS = ("https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter")
PRIO = {"alley": 1, "service": 2, "residential": 3, "tertiary": 4, "secondary": 5}


def _alley_ways(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """One record per undirected alley link: the two directions share one physical alley."""
    al, geo = graph["alleys"], graph["nodes_geo"]
    top: dict[str, int] = {}
    for e in graph["edge_list"]:
        p = PRIO.get(al[e["alley_id"]].get("road_class") or "residential", 3)
        for n in (str(e["u"]), str(e["v"])):
            top[n] = max(top.get(n, 0), p)
    seen, out = set(), []
    for e in graph["edge_list"]:
        a = al[e["alley_id"]]
        u, v = str(e["u"]), str(e["v"])
        if a.get("road_class") != "alley" or (v, u) in seen:
            continue
        seen.add((u, v))
        pts = _edge_polyline(a, u, v, geo)
        mid_ll = ((geo[u]["lat"] + geo[v]["lat"]) / 2, (geo[u]["lon"] + geo[v]["lon"]) / 2)
        out.append({"id": e["alley_id"], "name": a.get("name") or "", "length_m": float(a["length_m"]), "pts": pts,
                    "lat": mid_ll[0], "lon": mid_ll[1], "merge": max(top[u], top[v]) > 1})
    return out


def sample(graph: dict[str, Any], n: int, seed: int) -> list[dict[str, Any]]:
    ways = _alley_ways(graph)
    cut = st.median(w["length_m"] for w in ways)
    strata: dict[tuple[bool, bool], list[dict[str, Any]]] = {}
    for w in ways:
        strata.setdefault((w["merge"], w["length_m"] >= cut), []).append(w)
    rng = random.Random(seed)
    per, picked = n // len(strata), []
    for key in sorted(strata):
        rng.shuffle(strata[key])
        picked += [dict(w, stratum=f"{'merge' if key[0] else 'inner'}_{'long' if key[1] else 'short'}")
                   for w in strata[key][:per]]
    rest = [w for k in sorted(strata) for w in strata[k][per:]]
    rng.shuffle(rest)
    picked += [dict(w, stratum="extra") for w in rest[: n - len(picked)]]
    return picked


def write_sample(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "stratum", "length_m", "lat", "lon", "street_view", "imagery_found(y/n)",
                    "width_class(<2,2-3,3-4,>4)", "two_way(y/n)", "parked_or_stalls(none/some/many)", "note"])
        for r in rows:
            url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={r['lat']:.6f},{r['lon']:.6f}"
            w.writerow([r["id"], r["name"], r["stratum"], round(r["length_m"], 1), round(r["lat"], 6), round(r["lon"], 6),
                        url, "", "", "", "", ""])


def side_gaps(pts: list[tuple[float, float]], tree: cKDTree, xy: np.ndarray, step_m: float, search_m: float,
              band_m: float = 1.5) -> list[tuple[float | None, float | None]]:
    """(left, right) distance to the nearest building boundary, at points along a polyline."""
    out: list[tuple[float | None, float | None]] = []
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 1e-6:
            continue
        tx, ty = (x1 - x0) / L, (y1 - y0) / L
        nx, ny = -ty, tx
        for k in range(max(1, int(L // step_m))):
            s = (k + 0.5) * L / max(1, int(L // step_m))
            px, py = x0 + tx * s, y0 + ty * s
            left, right = None, None
            for h in tree.query_ball_point((px, py), r=search_m):
                dx, dy = xy[h, 0] - px, xy[h, 1] - py
                if abs(dx * tx + dy * ty) > band_m:
                    continue
                d = dx * nx + dy * ny
                if d > 0 and (left is None or d < left):
                    left = d
                elif d < 0 and (right is None or -d < right):
                    right = -d
            out.append((left, right))
    return out


def boundary_points(polys: list[list[tuple[float, float]]], step_m: float = 0.5) -> np.ndarray:
    pts: list[tuple[float, float]] = []
    for ring in polys:
        for (x0, y0), (x1, y1) in zip(ring[:-1], ring[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) // step_m))
            pts += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n)]
    return np.asarray(pts) if pts else np.zeros((0, 2))


def fetch_buildings(bbox: tuple[float, float, float, float], cache: Path, tries: int = 6) -> list[list[tuple[float, float]]]:
    if not cache.exists():
        q = f'[out:json][timeout:120];way["building"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});out geom;'
        body = urllib.parse.urlencode({"data": q}).encode()
        last: Exception | None = None
        for i in range(tries):
            req = urllib.request.Request(MIRRORS[i % len(MIRRORS)], data=body, headers={"User-Agent": "hcmc-traffic-research"})
            try:
                with urllib.request.urlopen(req, timeout=150) as r:
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    cache.write_bytes(r.read())
                last = None
                break
            except Exception as ex:  # public servers are often busy
                last = ex
                print(f"[width] {MIRRORS[i % len(MIRRORS)]}: {type(ex).__name__} {ex}", flush=True)
                time.sleep(20)
        if last is not None:
            raise SystemExit("Overpass unavailable, try again later")
    data = json.loads(cache.read_text(encoding="utf-8"))
    return [[project(p["lon"], p["lat"]) for p in el["geometry"]] for el in data["elements"] if el.get("geometry")]


def estimate(graph: dict[str, Any], polys: list[list[tuple[float, float]]], step_m: float, search_m: float) -> dict[str, Any]:
    xy = boundary_points(polys)
    tree = cKDTree(xy)
    rows = []
    for w in _alley_ways(graph):
        g = side_gaps(w["pts"], tree, xy, step_m, search_m)
        both = [a + b for a, b in g if a is not None and b is not None]
        rows.append({"id": w["id"], "points": len(g), "both_sides": len(both),
                     "width_m": round(float(st.median(both)), 2) if both else None})
    good = [r for r in rows if r["width_m"] is not None]
    v = np.array([r["width_m"] for r in good]) if good else np.zeros(0)
    return {"buildings": len(polys), "alleys": len(rows), "with_estimate": len(good),
            "coverage": round(len(good) / max(1, len(rows)), 3),
            "width_p10_p50_p90": [round(float(x), 2) for x in np.percentile(v, [10, 50, 90])] if len(v) else None,
            "share_under_2p5": round(float((v < 2.5).mean()), 3) if len(v) else None,
            "share_under_5": round(float((v < 5.0).mean()), 3) if len(v) else None, "rows": rows}


def self_test() -> None:
    # A 3 m wide east-west alley between two long buildings, plus one point with a wall on one side only.
    polys = [[(0.0, 1.5), (40.0, 1.5), (40.0, 9.0), (0.0, 9.0), (0.0, 1.5)],
             [(0.0, -1.5), (20.0, -1.5), (20.0, -9.0), (0.0, -9.0), (0.0, -1.5)]]
    xy = boundary_points(polys)
    g = side_gaps([(0.0, 0.0), (40.0, 0.0)], cKDTree(xy), xy, 5.0, 12.0)
    assert len(g) == 8, g
    assert abs(g[1][0] - 1.5) < 0.01 and abs(g[1][1] - 1.5) < 0.01, g[1]
    assert g[-1][1] is None and abs(g[-1][0] - 1.5) < 0.01, g[-1]
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    rows = sample(graph, 50, 1)
    assert len(rows) == 50 and len({r["id"] for r in rows}) == 50
    print("ALLEY_WIDTH_TESTS_OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "osm", "test"])
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--csv", type=Path, default=Path("../.docs/results_alley/alley_width_sample.csv"))
    ap.add_argument("--out", type=Path, default=Path("artifacts/out/quan4/alley_width"))
    ap.add_argument("--step-m", type=float, default=5.0)
    ap.add_argument("--search-m", type=float, default=12.0)
    args = ap.parse_args()
    if args.cmd == "test":
        self_test()
        return
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    if args.cmd == "sample":
        if args.csv.exists():
            raise SystemExit(f"{args.csv} exists; it may hold labels, not overwriting")
        rows = sample(graph, args.n, args.seed)
        write_sample(rows, args.csv)
        print(f"[width] wrote {args.csv}: {len(rows)} alleys")
        return
    geo = graph["nodes_geo"].values()
    lats, lons = [g["lat"] for g in geo], [g["lon"] for g in geo]
    bbox = (min(lats) - 0.001, min(lons) - 0.001, max(lats) + 0.001, max(lons) + 0.001)
    args.out.mkdir(parents=True, exist_ok=True)
    res = estimate(graph, fetch_buildings(bbox, args.out / "buildings_overpass.json"), args.step_m, args.search_m)
    (args.out / "alley_width_osm.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}))


if __name__ == "__main__":
    main()
