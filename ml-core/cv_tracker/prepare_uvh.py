"""UVH-26 (fixed CCTV, Bengaluru, CC-BY-4.0) -> YOLO dataset matching the HCMC portal snapshots (batch, Node 2).

Images are shrunk to 512x288 and re-encoded as low-quality JPEG, because the Q4 cameras give exactly that.
Classes: 0 motorcycle (Two-wheeler), 1 car (Hatchback, Sedan, SUV, MUV, Van), 2 bus (Bus, Mini-bus, Tempo-traveller),
3 truck (Truck, LCV), 4 three_wheeler, 5 bicycle. "Others" boxes are dropped.

    python cv_tracker/prepare_uvh.py --root UVH-26 --out uvh_yolo --jpeg 45 [--limit 50]
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

MAP = {8: 0, 1: 1, 2: 1, 3: 1, 4: 1, 13: 1, 5: 2, 10: 2, 11: 2, 6: 3, 9: 3, 7: 4, 12: 5}
NAMES = ["motorcycle", "car", "bus", "truck", "three_wheeler", "bicycle"]
SIZE = (512, 288)


def one(job: tuple[str, str, str, int]) -> bool:
    src, img_out, lab_txt, q = job
    try:
        Image.open(src).convert("RGB").resize(SIZE, Image.BILINEAR).save(img_out, quality=q)
    except Exception:
        return False
    Path(img_out.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt").write_text(lab_txt)
    return True


def split(root: Path, out: Path, tag: str, name: str, q: int, limit: int, workers: int) -> None:
    d = json.loads((root / f"UVH-26-{tag}" / f"UVH-26-ST-{tag}.json").read_text())
    files = {p.name: p for p in (root / f"UVH-26-{tag}").rglob("*.png")}
    lab: dict[int, list[str]] = {}
    for a in d["annotations"]:
        if a["category_id"] not in MAP:
            continue
        lab.setdefault(a["image_id"], [])
    W, H = 1920.0, 1080.0
    for a in d["annotations"]:
        c = MAP.get(a["category_id"])
        if c is None:
            continue
        x, y, w, h = a["bbox"]
        if w * 512 / W < 3 or h * 288 / H < 3:  # invisible at the target resolution
            continue
        lab[a["image_id"]].append(f"{c} {(x + w / 2) / W:.5f} {(y + h / 2) / H:.5f} {w / W:.5f} {h / H:.5f}")
    (out / "images" / name).mkdir(parents=True, exist_ok=True)
    (out / "labels" / name).mkdir(parents=True, exist_ok=True)
    jobs = []
    for im in d["images"]:
        p = files.get(im["file_name"])
        if p is not None:
            jobs.append((str(p), str(out / "images" / name / (p.stem + ".jpg")), "\n".join(lab.get(im["id"], [])) + "\n", q))
    jobs = jobs[:limit] if limit else jobs
    with ProcessPoolExecutor(workers) as ex:
        ok = sum(ex.map(one, jobs, chunksize=32))
    print(f"[uvh] {name}: images in json {len(d['images'])}, files found {len(files)}, written {ok}/{len(jobs)}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jpeg", type=int, default=45)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    split(args.root, args.out, "Train", "train", args.jpeg, args.limit, args.workers)
    split(args.root, args.out, "Val", "val", args.jpeg, args.limit, args.workers)
    (args.out / "data.yaml").write_text(
        f"path: {args.out.resolve()}\ntrain: images/train\nval: images/val\nnames:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(NAMES)))


if __name__ == "__main__":
    main()
