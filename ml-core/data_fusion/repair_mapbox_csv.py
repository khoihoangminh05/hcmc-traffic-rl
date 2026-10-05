"""Repair Mapbox CSV corrupted by unquoted lon,lat commas.

Broken layout (8 fields):
  ts, od_id, o_lon, o_lat, d_lon, d_lat, duration, distance
Correct:
  ts, od_id, "o_lon,o_lat", "d_lon,d_lat", duration, distance
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def repair_file(src: Path, dst: Path) -> int:
    fixed: list[dict[str, str]] = []
    with src.open(encoding="utf-8", newline="") as f:
        # read raw lines — DictReader already mis-parsed; use raw split carefully
        lines = f.read().splitlines()
    if not lines:
        return 0
    header = lines[0]
    for line in lines[1:]:
        if not line.strip():
            continue
        # Prefer csv reader on a reconstructed guess: if 8 comma-parts without quotes
        parts = line.split(",")
        if len(parts) >= 8 and not line.startswith('"'):
            # timestamp may contain no comma; od_id no comma
            ts, od = parts[0], parts[1]
            o_lon, o_lat = parts[2], parts[3]
            d_lon, d_lat = parts[4], parts[5]
            dur, dist = parts[6], parts[7]
            # ignore trailing junk
            fixed.append(
                {
                    "timestamp": ts,
                    "od_id": od,
                    "origin": f"{o_lon},{o_lat}",
                    "destination": f"{d_lon},{d_lat}",
                    "duration_sec": dur,
                    "distance_m": dist,
                }
            )
        else:
            # already ok? try DictReader single row
            row = next(csv.DictReader([header, line]))
            if row.get("origin") and "," in (row.get("origin") or ""):
                fixed.append(
                    {
                        "timestamp": row["timestamp"],
                        "od_id": row["od_id"],
                        "origin": row["origin"],
                        "destination": row["destination"],
                        "duration_sec": row["duration_sec"],
                        "distance_m": row["distance_m"],
                    }
                )

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "od_id",
                "origin",
                "destination",
                "duration_sec",
                "distance_m",
            ],
            quoting=csv.QUOTE_MINIMAL,
        )
        w.writeheader()
        w.writerows(fixed)
    return len(fixed)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Default: <input>.repaired.csv",
    )
    args = p.parse_args()
    out = args.output or args.input.with_suffix(".repaired.csv")
    n = repair_file(args.input, out)
    print(f"repaired {n} rows -> {out}")


if __name__ == "__main__":
    main()
