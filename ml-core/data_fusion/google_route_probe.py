"""Do Google two-wheeler routes use alleys, and does Google report live traffic inside them? (batch)

Calls the Routes API (computeRoutes, TWO_WHEELER, TRAFFIC_AWARE, TRAFFIC_ON_POLYLINE) for a few
origin-destination pairs inside Quan 4 and matches each returned polyline to the alley graph.
Reports per route: share of matched distance on alleys, and the share of alley / other distance
that Google marks SLOW or TRAFFIC_JAM, with duration against staticDuration.

Keeps derived numbers only (no polylines, no raw responses): Google's terms limit storing content,
so check them before publishing anything. The key comes from GOOGLE_MAPS_API_KEY, never from the
command line or a file in the repo. The API is billed: `--max-requests` caps the calls.

    python -m data_fusion.google_route_probe --self-test        # no key, no network
    GOOGLE_MAPS_API_KEY=... python -m data_fusion.google_route_probe --label peak --pairs 10
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .match_probe import build_edge_index, match_segment, project

URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELDS = ("routes.duration,routes.staticDuration,routes.distanceMeters,routes.polyline.encodedPolyline,"
          "routes.travelAdvisory.speedReadingIntervals")
GRAPH = Path("artifacts/out/quan4/wcc/alley_graph_wcc.json")
STEP_M = 10.0


def decode_polyline(s: str) -> list[tuple[float, float]]:
    """Encoded polyline -> [(lon, lat)]."""
    pts, i, lat, lon = [], 0, 0, 0
    while i < len(s):
        for which in (0, 1):
            shift = res = 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                res |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            d = ~(res >> 1) if res & 1 else res >> 1
            if which == 0:
                lat += d
            else:
                lon += d
        pts.append((lon / 1e5, lat / 1e5))
    return pts


def encode_polyline(pts: list[tuple[float, float]]) -> str:
    """[(lon, lat)] -> encoded polyline (self-test only)."""
    out, plat, plon = [], 0, 0
    for lon, lat in pts:
        for v in (round(lat * 1e5) - plat, round(lon * 1e5) - plon):
            v = ~(v << 1) if v < 0 else v << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plon = round(lat * 1e5), round(lon * 1e5)
    return "".join(out)


def seconds(x: Any) -> float | None:
    return float(str(x).rstrip("s")) if x is not None else None


def analyse(route: dict[str, Any], idx) -> dict[str, Any]:
    """Derived numbers for one route; the polyline itself is not kept."""
    pts = [project(a, b) for a, b in decode_polyline(route["polyline"]["encodedPolyline"])]
    speed = ["NORMAL"] * max(0, len(pts) - 1)
    ivs = (route.get("travelAdvisory") or {}).get("speedReadingIntervals") or []
    for iv in ivs:
        for k in range(int(iv.get("startPolylinePointIndex", 0)), int(iv.get("endPolylinePointIndex", 0))):
            if k < len(speed):
                speed[k] = iv.get("speed", "NORMAL")
    tot = matched = alley = alley_slow = other_slow = 0.0
    for k, (p0, p1) in enumerate(zip(pts[:-1], pts[1:])):
        L = math.dist(p0, p1)
        n = max(1, int(L // STEP_M))
        slow = speed[k] in ("SLOW", "TRAFFIC_JAM")
        for j in range(n):
            a = (p0[0] + (p1[0] - p0[0]) * j / n, p0[1] + (p1[1] - p0[1]) * j / n)
            b = (p0[0] + (p1[0] - p0[0]) * (j + 1) / n, p0[1] + (p1[1] - p0[1]) * (j + 1) / n)
            seg = L / n
            tot += seg
            row = match_segment(idx, a, b, 12.0, math.radians(50))
            if row is None:
                continue
            matched += seg
            if bool(idx.is_alley[row]):
                alley += seg
                alley_slow += seg * slow
            else:
                other_slow += seg * slow
    other = matched - alley
    dur, sta = seconds(route.get("duration")), seconds(route.get("staticDuration"))
    return {"km": round(tot / 1000, 3), "matched_share": round(matched / max(tot, 1e-9), 3),
            "alley_share": round(alley / max(matched, 1e-9), 3), "alley_km": round(alley / 1000, 3),
            "other_km": round(other / 1000, 3), "alley_slow_share": round(alley_slow / max(alley, 1e-9), 3),
            "other_slow_share": round(other_slow / max(other, 1e-9), 3), "duration_s": dur, "static_s": sta,
            "duration_over_static": round(dur / sta, 3) if dur and sta else None, "traffic_intervals": len(ivs)}


def call(key: str, o: dict[str, float], d: dict[str, float]) -> dict[str, Any]:
    body = {"origin": {"location": {"latLng": {"latitude": o["lat"], "longitude": o["lon"]}}},
            "destination": {"location": {"latLng": {"latitude": d["lat"], "longitude": d["lon"]}}},
            "travelMode": "TWO_WHEELER", "routingPreference": "TRAFFIC_AWARE",
            "extraComputations": ["TRAFFIC_ON_POLYLINE"], "polylineQuality": "HIGH_QUALITY", "regionCode": "VN"}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Goog-Api-Key": key,
                                          "X-Goog-FieldMask": FIELDS})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def pick_pairs(graph: dict[str, Any], n: int, seed: int, lo_m: float, hi_m: float) -> list[tuple[str, str]]:
    geo = graph["nodes_geo"]
    nodes = sorted({str(e["u"]) for e in graph["edge_list"]} & {str(e["v"]) for e in graph["edge_list"]} & set(geo))
    rng = random.Random(seed)
    out: list[tuple[str, str]] = []
    while len(out) < n:
        a, b = rng.sample(nodes, 2)
        d = math.dist(project(geo[a]["lon"], geo[a]["lat"]), project(geo[b]["lon"], geo[b]["lat"]))
        if lo_m <= d <= hi_m:
            out.append((a, b))
    return out


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if "alley_share" in r]
    km_a, km_o = sum(r["alley_km"] for r in ok), sum(r["other_km"] for r in ok)
    return {"routes": len(ok), "failed": len(rows) - len(ok),
            "alley_share_of_matched_km": round(km_a / max(km_a + km_o, 1e-9), 3),
            "alley_slow_share_km_weighted": round(sum(r["alley_slow_share"] * r["alley_km"] for r in ok) / max(km_a, 1e-9), 3),
            "other_slow_share_km_weighted": round(sum(r["other_slow_share"] * r["other_km"] for r in ok) / max(km_o, 1e-9), 3),
            "mean_matched_share": round(sum(r["matched_share"] for r in ok) / max(len(ok), 1), 3),
            "mean_duration_over_static": round(sum(r["duration_over_static"] or 1.0 for r in ok) / max(len(ok), 1), 3)}


def self_test(graph: dict[str, Any], idx) -> None:
    """A fake response along known alley and road links must match them with the right traffic."""
    pts = [(106.0, 10.0), (106.001, 10.001), (106.5, 10.5)]
    back = decode_polyline(encode_polyline(pts))
    assert all(abs(a - c) < 1e-5 and abs(b - d) < 1e-5 for (a, b), (c, d) in zip(pts, back)), back
    geo = graph["nodes_geo"]
    alley = next(e for i, e in enumerate(graph["edge_list"]) if idx.is_alley[i]
                 and graph["alleys"][e["alley_id"]]["length_m"] > 60 and len(graph["alleys"][e["alley_id"]].get("coordinates") or []) == 2)
    road = next(e for i, e in enumerate(graph["edge_list"]) if not idx.is_alley[i]
                and graph["alleys"][e["alley_id"]]["length_m"] > 60 and len(graph["alleys"][e["alley_id"]].get("coordinates") or []) == 2)
    ll = lambda n: (geo[str(n)]["lon"], geo[str(n)]["lat"])  # noqa: E731
    r = {"polyline": {"encodedPolyline": encode_polyline([ll(alley["u"]), ll(alley["v"])])},
         "duration": "100s", "staticDuration": "80s",
         "travelAdvisory": {"speedReadingIntervals": [{"startPolylinePointIndex": 0, "endPolylinePointIndex": 1,
                                                       "speed": "TRAFFIC_JAM"}]}}
    a = analyse(r, idx)
    assert a["alley_share"] > 0.9 and a["alley_slow_share"] > 0.9 and a["duration_over_static"] == 1.25, a
    r2 = {"polyline": {"encodedPolyline": encode_polyline([ll(road["u"]), ll(road["v"])])}, "duration": "50s"}
    b = analyse(r2, idx)
    assert b["alley_share"] < 0.1 and b["other_slow_share"] == 0.0 and b["duration_over_static"] is None, b
    print("GOOGLE_ROUTE_PROBE_TESTS_OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run", help="e.g. peak, offpeak")
    ap.add_argument("--pairs", type=int, default=10)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--min-m", type=float, default=800.0)
    ap.add_argument("--max-m", type=float, default=3000.0)
    ap.add_argument("--max-requests", type=int, default=30)
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/out/quan4/google_probe"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    idx = build_edge_index(graph)
    if args.self_test:
        self_test(graph, idx)
        return
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        raise SystemExit("GOOGLE_MAPS_API_KEY is not set")
    if args.pairs > args.max_requests:
        raise SystemExit(f"--pairs {args.pairs} exceeds --max-requests {args.max_requests}")
    geo = graph["nodes_geo"]
    rows: list[dict[str, Any]] = []
    for a, b in pick_pairs(graph, args.pairs, args.seed, args.min_m, args.max_m):
        row: dict[str, Any] = {"from": a, "to": b}
        try:
            res = call(key, geo[a], geo[b])
            routes = res.get("routes") or []
            if routes:
                row.update(analyse(routes[0], idx))
            else:
                row["error"] = "no route"
        except Exception as ex:  # keep going, report it; the message never contains the key
            row["error"] = f"{type(ex).__name__}: {getattr(ex, 'code', '')}"
        rows.append(row)
        print(json.dumps(row), flush=True)
        time.sleep(0.2)
    summ = summarise(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"google_{args.label}_{stamp}.json"
    out.write_text(json.dumps({"label": args.label, "time_utc": stamp, "summary": summ, "routes": rows}, indent=2), encoding="utf-8")
    print(f"[google] summary {json.dumps(summ)}\n[google] wrote {out}", flush=True)


if __name__ == "__main__":
    main()
