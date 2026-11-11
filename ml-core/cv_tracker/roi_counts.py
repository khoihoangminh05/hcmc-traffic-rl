"""Counts inside the hand-drawn road ROI of each camera (batch). A box counts when its bottom-centre (where it
touches the road) lies in a listed grid cell. Input: count_snapshots --boxes JSONL, cv_tracker/roi_q4.json.

    python -m cv_tracker.roi_counts --boxes boxes.jsonl --roi cv_tracker/roi_q4.json --out roi_counts.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from .count_snapshots import LABELS


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--boxes", type=Path, required=True)
    ap.add_argument("--roi", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--conf", type=float, default=0.1)
    ap.add_argument("--labels", choices=list(LABELS), default="coco", help="class ids used in --boxes")
    args = ap.parse_args()
    NAMES = LABELS[args.labels]
    spec = json.loads(args.roi.read_text())
    gw, gh = spec["grid"]["w"] / spec["grid"]["cols"], spec["grid"]["h"] / spec["grid"]["rows"]
    roi = {k: set(v) for k, v in spec["roi"].items()}
    with args.out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "camera", "utc", "vn_hour", "vn_dow", *NAMES.values()])
        for line in args.boxes.open():
            r = json.loads(line)
            if r["camera"] not in roi or not r["utc"]:
                continue
            n = {k: 0 for k in NAMES}
            for c, p, (x0, y0, x1, y1) in zip(r["cls"], r["conf"], r["xyxy"]):
                if c not in NAMES or p < args.conf:
                    continue
                cx, cy = (x0 + x1) / 2, min(y1, spec["grid"]["h"] - 1)
                cell = f"{'ABCDEFGH'[min(7, int(cx // gw))]}{min(6, int(cy // gh) + 1)}"
                n[c] += cell in roi[r["camera"]]
            vn = datetime.fromisoformat(r["utc"]) + timedelta(hours=7)
            w.writerow([r["file"], r["camera"], r["utc"], vn.hour, vn.weekday(), *n.values()])
    print(f"[roi] wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
