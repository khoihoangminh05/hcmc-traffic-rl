"""Batch CV: read a video folder → write per-file vehicle counts JSON.

Designed for Node 2 (GPU server). No real-time wait loops.
When ultralytics is unavailable, falls back to a deterministic stub counter
so the pipeline remains runnable offline.
"""

from __future__ import annotations

import argparse
import json
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class CountResult:
    video: str
    camera_id: str | None
    frame_count: int
    vehicle_count: int
    avg_confidence: float
    method: str
    processed_at: str


def _stub_count(video_path: Path) -> CountResult:
    """Deterministic placeholder when YOLO weights are not installed."""
    digest = hashlib.sha256(video_path.read_bytes() if video_path.is_file() else video_path.name.encode()).hexdigest()
    n = int(digest[:6], 16) % 80 + 5
    camera_id = video_path.parent.name if video_path.parent.name != "video" else None
    return CountResult(
        video=str(video_path),
        camera_id=camera_id,
        frame_count=max(1, n * 3),
        vehicle_count=n,
        avg_confidence=0.5,
        method="stub_hash",
        processed_at=datetime.now(timezone.utc).isoformat(),
    )


def _yolo_count(video_path: Path, model_name: str = "yolov10n.pt") -> CountResult:
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError:
        return _stub_count(video_path)

    model = YOLO(model_name)
    results = model.track(source=str(video_path), persist=True, verbose=False)
    vehicle_ids: set[int] = set()
    confs: list[float] = []
    frames = 0
    for r in results:
        frames += 1
        if r.boxes is None:
            continue
        for box in r.boxes:
            cls_id = int(box.cls[0]) if box.cls is not None else -1
            # COCO: car=2, motorcycle=3, bus=5, truck=7
            if cls_id not in {2, 3, 5, 7}:
                continue
            if box.id is not None:
                vehicle_ids.add(int(box.id[0]))
            if box.conf is not None:
                confs.append(float(box.conf[0]))

    camera_id = video_path.parent.name if video_path.parent.name != "video" else None
    return CountResult(
        video=str(video_path),
        camera_id=camera_id,
        frame_count=frames,
        vehicle_count=len(vehicle_ids) if vehicle_ids else len(confs),
        avg_confidence=sum(confs) / len(confs) if confs else 0.0,
        method="yolov10_bytetrack",
        processed_at=datetime.now(timezone.utc).isoformat(),
    )


def process_video(video_path: Path, use_yolo: bool = True) -> CountResult:
    if use_yolo:
        return _yolo_count(video_path)
    return _stub_count(video_path)


def run_batch(input_dir: Path, output_dir: Path, use_yolo: bool = True) -> list[dict[str, Any]]:
    """Read videos under input_dir, write one JSON count file each."""
    output_dir.mkdir(parents=True, exist_ok=True)
    patterns = ("*.mp4", "*.ts", "*.mkv", "*.avi")
    videos: list[Path] = []
    for pat in patterns:
        videos.extend(sorted(input_dir.rglob(pat)))

    results: list[dict[str, Any]] = []
    if not videos:
        # Allow empty folder: write empty index so downstream fusion can run.
        index_path = output_dir / "counts_index.json"
        index_path.write_text(json.dumps({"videos": [], "count": 0}, indent=2), encoding="utf-8")
        return results

    for path in videos:
        result = process_video(path, use_yolo=use_yolo)
        payload = asdict(result)
        out_file = output_dir / f"{path.stem}_counts.json"
        out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        results.append(payload)

    index = {"videos": [r["video"] for r in results], "count": len(results)}
    (output_dir / "counts_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch CV vehicle counting")
    parser.add_argument("--input", type=Path, required=True, help="Folder of raw videos")
    parser.add_argument("--output", type=Path, required=True, help="Output counts folder")
    parser.add_argument("--no-yolo", action="store_true", help="Force stub counter")
    args = parser.parse_args()
    rows = run_batch(args.input, args.output, use_yolo=not args.no_yolo)
    print(f"cv_tracker: wrote {len(rows)} count files -> {args.output}")


if __name__ == "__main__":
    main()
