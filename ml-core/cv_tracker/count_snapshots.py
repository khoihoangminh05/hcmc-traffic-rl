"""Count vehicles in camera snapshots (batch, Node 2).

Input: the crawler's snapshot tree <root>/<cameraId>/<YYYY-MM-DD>/snap_<UTC>.jpg (HCMC portal, 512x288).
Output: one CSV row per image: camera, UTC time, VN hour, counts per COCO class (motorcycle, car, bus,
truck, bicycle, person on a two-wheeler is not counted). A snapshot count is a density (vehicles in view),
not a flow; flow = density x speed (Mapbox) is done downstream. Images already in --out are skipped.

    python -m cv_tracker.count_snapshots --root <camera dir> --glob 'q4_*' --out counts.csv --model yolo11m.pt
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

LABELS = {
    "coco": {1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"},
    # UVH-26 fine-tune selected at G0 (cv runs/uvh512_y11m_g): class ids differ from COCO
    "uvh": {0: "motorcycle", 1: "car", 2: "bus", 3: "truck", 4: "three_wheeler", 5: "bicycle"},
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--glob", default="q4_*")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="yolo11m.pt")
    ap.add_argument("--conf", type=float, default=0.2)
    ap.add_argument("--imgsz", type=int, default=960, help="upscale the 512x288 snapshots for small motorcycles")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--device", default="0")
    ap.add_argument("--save-vis", type=Path, default=None, help="write annotated images for the first N files")
    ap.add_argument("--n-vis", type=int, default=0)
    ap.add_argument("--labels", choices=list(LABELS), default="coco", help="class ids of --model")
    ap.add_argument("--days", nargs="+", default=None, help="only these YYYY-MM-DD folders")
    ap.add_argument("--boxes", type=Path, default=None, help="also write every box (JSONL) for the parked-vehicle filter")
    args = ap.parse_args()

    done: set[str] = set()
    if args.out.exists():
        with args.out.open() as f:
            done = {r["file"] for r in csv.DictReader(f)}
    CLASSES = LABELS[args.labels]
    files = sorted(
        str(p) for d in sorted(args.root.glob(args.glob)) for p in d.rglob("*.jpg")
        if str(p) not in done and (args.days is None or p.parent.name in args.days)
    )
    print(f"[count] {len(files)} new images, {len(done)} already counted", flush=True)
    if not files:
        return
    from ultralytics import YOLO

    model = YOLO(args.model)
    new = not args.out.exists()
    with args.out.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["file", "camera", "utc", "vn_hour", "vn_dow", *CLASSES.values(), "ok"])
        for i in range(0, len(files), args.batch):
            chunk = files[i : i + args.batch]
            res = model.predict(chunk, imgsz=args.imgsz, conf=args.conf, classes=list(CLASSES), device=args.device, verbose=False)
            for fn, r in zip(chunk, res):
                m = re.search(r"snap_(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})", fn)
                utc = datetime.fromisoformat(f"{m[1]}T{m[2]}:{m[3]}:{m[4]}") if m else None
                vn = utc + timedelta(hours=7) if utc else None
                cls = r.boxes.cls.int().tolist() if r.boxes is not None else []
                n = {c: cls.count(k) for k, c in CLASSES.items()}
                ok = int(r.orig_img is not None and r.orig_img.std() > 3)  # grey "no image" placeholders
                if args.boxes is not None:
                    with args.boxes.open("a") as fb:
                        b = r.boxes
                        fb.write(json.dumps({"file": fn, "camera": Path(fn).parts[-3], "utc": utc.isoformat() if utc else "",
                                             "cls": b.cls.int().tolist(), "conf": [round(x, 3) for x in b.conf.tolist()],
                                             "xyxy": [[round(v, 1) for v in bb] for bb in b.xyxy.tolist()]}) + "\n")
                w.writerow([fn, Path(fn).parts[-3], utc.isoformat() if utc else "", vn.hour if vn else "",
                            vn.weekday() if vn else "", *n.values(), ok])
                if args.save_vis and args.n_vis > 0:
                    args.save_vis.mkdir(parents=True, exist_ok=True)
                    r.save(filename=str(args.save_vis / (Path(fn).parts[-3] + ".jpg")))
                    args.n_vis -= 1
            print(f"[count] {min(i + args.batch, len(files))}/{len(files)}", flush=True)


if __name__ == "__main__":
    main()
