"""End-to-end offline smoke: CV → fusion → SUMO export → MARL train/infer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "artifacts" / "samples"
OUT = ROOT / "artifacts" / "out"
SUMO = ROOT.parent / "sumo-env"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> None:
    counts_out = OUT / "counts"
    fusion_out = OUT / "fusion"
    marl_out = OUT / "marl"
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) CV batch (stub if no YOLO)
    run(
        [
            sys.executable,
            "-m",
            "cv_tracker.run_batch",
            "--input",
            str(SAMPLES),
            "--output",
            str(counts_out),
            "--no-yolo",
        ]
    )

    # Prefer sample counts if no videos
    counts_dir = SAMPLES / "counts"
    if not list(counts_out.glob("*_counts.json")):
        counts_dir = SAMPLES / "counts"
    else:
        counts_dir = counts_out

    # 2) Fusion → density per alley_id
    run(
        [
            sys.executable,
            "-m",
            "data_fusion.run_batch",
            "--mapbox",
            str(SAMPLES / "travel_time_demo.csv"),
            "--counts",
            str(counts_dir),
            "--output",
            str(fusion_out),
        ]
    )

    # 3) SUMO twin artifacts
    run(
        [
            sys.executable,
            "-m",
            "data_fusion.export_sumo",
            "--density",
            str(fusion_out / "alley_density.json"),
            "--graph",
            str(fusion_out / "alley_graph.json"),
            "--networks-dir",
            str(SUMO / "networks"),
            "--routes-dir",
            str(SUMO / "routes"),
        ]
    )

    # 4) MARL train + infer
    run(
        [
            sys.executable,
            "-m",
            "marl_agent.train",
            "--density",
            str(fusion_out / "alley_density.json"),
            "--graph",
            str(fusion_out / "alley_graph.json"),
            "--output",
            str(marl_out),
            "--episodes",
            "30",
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "marl_agent.infer",
            "--density",
            str(fusion_out / "alley_density.json"),
            "--graph",
            str(fusion_out / "alley_graph.json"),
            "--t",
            "28800",
            "--origin",
            "n0",
            "--destination",
            "n3",
        ]
    )
    print("SMOKE_OK")


if __name__ == "__main__":
    main()
