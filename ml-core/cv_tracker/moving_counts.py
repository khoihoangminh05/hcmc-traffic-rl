"""Remove parked vehicles from snapshot counts (batch, Node 2).

A box is parked when a box of the same class overlaps it (IoU >= --iou) in at least --share of the camera's
other snapshots within +-(--window-min) minutes. Snapshots are 5 min apart, so a moving vehicle is never in the
same place twice. Input: the JSONL from count_snapshots --boxes. Output: CSV of moving counts per image.

    python -m cv_tracker.moving_counts --boxes boxes.jsonl --out moving.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

NAMES = {1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


def iou(a: list[float], b: list[float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--boxes", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--share", type=float, default=0.3)
    ap.add_argument("--window-min", type=float, default=60.0)
    args = ap.parse_args()
    by_cam: dict[str, list[dict]] = defaultdict(list)
    for line in args.boxes.open():
        r = json.loads(line)
        if r["utc"]:
            r["t"] = datetime.fromisoformat(r["utc"])
            by_cam[r["camera"]].append(r)
    with args.out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "camera", "utc", "vn_hour", "vn_dow", *[f"{n}_all" for n in NAMES.values()],
                    *[f"{n}_moving" for n in NAMES.values()]])
        for cam, rows in by_cam.items():
            rows.sort(key=lambda r: r["t"])
            win = timedelta(minutes=args.window_min)
            for i, r in enumerate(rows):
                others = [o for o in rows if o is not r and abs(o["t"] - r["t"]) <= win]
                allc = {k: 0 for k in NAMES}
                mov = {k: 0 for k in NAMES}
                for c, bb in zip(r["cls"], r["xyxy"]):
                    if c not in NAMES:
                        continue
                    allc[c] += 1
                    hits = sum(any(oc == c and iou(bb, ob) >= args.iou for oc, ob in zip(o["cls"], o["xyxy"])) for o in others)
                    if not others or hits / len(others) < args.share:
                        mov[c] += 1
                vn = r["t"] + timedelta(hours=7)
                w.writerow([r["file"], cam, r["utc"], vn.hour, vn.weekday(), *allc.values(), *mov.values()])
    print(f"[moving] wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
