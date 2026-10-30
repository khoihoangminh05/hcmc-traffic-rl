"""Is the Mapbox probe signal live traffic or a fixed profile? (batch, Node 2)

Reads two edge_obs.csv files written by data_fusion.match_probe: one for live
sweeps, one for typical (`depart_at`) samples. A live observation is paired with
the typical one of the same route, edge, weekday and 15-min slot (VN local).

If live / typical stays at 1 with no day-to-day spread, the "live" speeds are
Mapbox's historic profile and must enter fusion as a prior, not a measurement.

Everything is split by alley vs non-alley edges.

    python -m data_fusion.probe_diagnostics \
        --live artifacts/out/quan4/probe/edge_obs.csv \
        --typical artifacts/out/quan4/probe_typical/edge_obs.csv \
        --out artifacts/out/quan4/probe/diagnostics.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics as st
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

VN = timedelta(hours=7)
SLOT_MIN = 15


def _slot_key(local: datetime) -> tuple[int, int]:
    """(weekday, minute of day floored to the slot)."""
    m = local.hour * 60 + local.minute
    return local.weekday(), m - m % SLOT_MIN


def live_local(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None) + VN


def read_obs(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _q(xs: list[float], p: float) -> float:
    s = sorted(xs)
    return round(s[int(p * (len(s) - 1))], 3)


def describe(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"rows": 0}
    sp = [float(r["speed_mps"]) for r in rows]
    cong = [r["congestion_numeric"] for r in rows if r.get("congestion_numeric") not in ("", None, "None")]
    return {
        "rows": len(rows),
        "edges": len({r["alley_id"] for r in rows}),
        "congestion_present": len(cong) / len(rows),
        "speed_p10_p50_p90": [_q(sp, 0.1), _q(sp, 0.5), _q(sp, 0.9)],
    }


def typical_profile(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Median over edges of speed(hour) / edge median speed."""
    per_edge: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for r in rows:
        if r.get("depart_at"):
            per_edge[r["alley_id"]].append((int(r["depart_at"][11:13]), float(r["speed_mps"])))
    by_hour: dict[int, list[float]] = defaultdict(list)
    for v in per_edge.values():
        med = st.median(s for _, s in v)
        for h, s in v:
            by_hour[h].append(s / med)
    return {f"{h:02d}": round(st.median(x), 3) for h, x in sorted(by_hour.items())}


def live_vs_typical(live: list[dict[str, Any]], typ: list[dict[str, Any]]) -> dict[str, Any]:
    t_index: dict[tuple[str, str, int, int], float] = {}
    for r in typ:
        if not r.get("depart_at"):
            continue
        k = _slot_key(datetime.fromisoformat(r["depart_at"]))
        t_index[(r["route_id"], r["alley_id"], *k)] = float(r["speed_mps"])
    logr: list[float] = []
    by_day: dict[str, list[float]] = defaultdict(list)
    for r in live:
        loc = live_local(r["timestamp"])
        ts = t_index.get((r["route_id"], r["alley_id"], *_slot_key(loc)))
        if ts is None or ts <= 0:
            continue
        x = math.log(float(r["speed_mps"]) / ts)
        logr.append(x)
        by_day[loc.date().isoformat()].append(x)
    if not logr:
        return {"pairs": 0}
    return {
        "pairs": len(logr),
        "ratio_p10_p50_p90": [round(math.exp(_q(logr, p)), 3) for p in (0.1, 0.5, 0.9)],
        "share_off_by_more_than_5pct": round(
            sum(1 for x in logr if abs(x) > math.log(1.05)) / len(logr), 3
        ),
        "median_ratio_by_day": {d: round(math.exp(st.median(v)), 3) for d, v in sorted(by_day.items())},
    }


def run(live_csv: Path, typical_csv: Path, out: Path) -> dict[str, Any]:
    live = read_obs(live_csv)
    typ = read_obs(typical_csv)
    report: dict[str, Any] = {"live_csv": str(live_csv), "typical_csv": str(typical_csv)}
    for flag, name in (("True", "alley"), ("False", "other")):
        lv = [r for r in live if r["is_alley"] == flag]
        tp = [r for r in typ if r["is_alley"] == flag]
        report[name] = {
            "live": describe(lv),
            "typical": describe(tp),
            "typical_profile_by_hour": typical_profile(tp),
            "live_vs_typical": live_vs_typical(lv, tp),
        }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", type=Path, required=True)
    ap.add_argument("--typical", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    rep = run(args.live, args.typical, args.out)
    for name in ("alley", "other"):
        r = rep[name]
        lv, tp, lt = r["live"], r["typical"], r["live_vs_typical"]
        print(f"[{name}] live rows={lv.get('rows')} edges={lv.get('edges')} "
              f"congestion={lv.get('congestion_present', 0):.1%} speed p10/50/90={lv.get('speed_p10_p50_p90')}")
        print(f"[{name}] typical rows={tp.get('rows')} edges={tp.get('edges')}")
        print(f"[{name}] typical speed by hour / edge median: {r['typical_profile_by_hour']}")
        print(f"[{name}] live/typical pairs={lt.get('pairs')} ratio p10/50/90={lt.get('ratio_p10_p50_p90')} "
              f"off>5%={lt.get('share_off_by_more_than_5pct')}")
        print(f"[{name}] live/typical median by day: {lt.get('median_ratio_by_day')}")
    print(f"[diag] wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
