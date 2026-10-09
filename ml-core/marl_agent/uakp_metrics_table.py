"""Build comparison table from UAKP summary.json files (main + ablations).

Usage:
  python -m marl_agent.uakp_metrics_table run_a/summary.json run_b/summary.json ...
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


COLS = [
    "run",
    "data_tag",
    "include_u",
    "lambda",
    "test_travel",
    "test_risk",
    "test_gap",
    "djk_travel",
    "djk_risk",
    "beats_djk_risk",
    "beats_random",
    "stop_reason",
]


def load_row(path: Path) -> dict[str, object]:
    s = json.loads(path.read_text(encoding="utf-8"))
    djk = (s.get("baselines_test") or {}).get("dijkstra_mean") or {}
    return {
        "run": path.parent.name,
        "data_tag": s.get("data_tag"),
        "include_u": s.get("include_uncertainty"),
        "lambda": s.get("risk_lambda"),
        "test_travel": round(float(s.get("test_travel_time") or float("nan")), 2),
        "test_risk": round(float(s.get("test_risk_adjusted") or float("nan")), 2),
        "test_gap": round(float(s.get("test_gap") or float("nan")), 2),
        "djk_travel": round(float(djk.get("travel_time") or float("nan")), 2),
        "djk_risk": round(float(djk.get("risk_adjusted") or s.get("test_vs_dijkstra_mean_risk") or float("nan")), 2),
        "beats_djk_risk": s.get("test_beats_dijkstra_on_risk"),
        "beats_random": s.get("test_beats_random_on_travel"),
        "stop_reason": str(s.get("stop_reason") or "")[:60],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summaries", nargs="+", type=Path)
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args()
    rows = [load_row(p) for p in args.summaries]
    # markdown
    print("| " + " | ".join(COLS) + " |")
    print("| " + " | ".join(["---"] * len(COLS)) + " |")
    for r in rows:
        print("| " + " | ".join(str(r[c]) for c in COLS) + " |")
    if args.csv:
        import csv

        with args.csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {args.csv}")


if __name__ == "__main__":
    main()
