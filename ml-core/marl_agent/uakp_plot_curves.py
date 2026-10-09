"""Plot UAKP learning curves from metrics.jsonl (optional matplotlib).

  python -m marl_agent.uakp_plot_curves path/to/run_dir [--out curve.png]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    path = args.run_dir / "metrics.jsonl"
    trains: list[dict] = []
    evals: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("type") == "train":
            trains.append(row)
        elif row.get("type") == "eval":
            evals.append(row)

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; printing numeric summary only")
        print(f"train updates={len(trains)} evals={len(evals)}")
        if evals:
            print("last eval:", {k: evals[-1].get(k) for k in evals[-1] if k.startswith("val_")})
        return

    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    if trains:
        ax[0].plot([r["update"] for r in trains], [r["mean_travel"] for r in trains], label="train travel")
        ax[0].set_xlabel("update")
        ax[0].set_ylabel("travel (s)")
        ax[0].set_title("Train mean travel")
        ax[0].legend()
    if evals:
        ax[1].plot([r["update"] for r in evals], [r.get("val_gap", 0) for r in evals], label="val gap")
        ax[1].plot(
            [r["update"] for r in evals],
            [r.get("val_risk_adjusted", 0) for r in evals],
            label="val risk_adj",
        )
        ax[1].set_xlabel("update")
        ax[1].set_title("Val gap / risk-adjusted")
        ax[1].legend()
    fig.tight_layout()
    out = args.out or (args.run_dir / "learning_curve.png")
    fig.savefig(out, dpi=140)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
