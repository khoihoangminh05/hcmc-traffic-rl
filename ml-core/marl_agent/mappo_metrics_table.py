"""Compare MAPPO summary.json files.

  python -m marl_agent.mappo_metrics_table path/a/summary.json path/b/summary.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

COLS = [
    "run",
    "algo",
    "fleet_mean",
    "cvar90",
    "cong",
    "djk_mean",
    "beats_djk",
    "beats_cvar",
    "stop",
]


def load_row(path: Path) -> dict[str, object]:
    s = json.loads(path.read_text(encoding="utf-8"))
    djk = (s.get("baselines_test") or {}).get("all_dijkstra") or {}
    return {
        "run": path.parent.name,
        "algo": s.get("algo"),
        "fleet_mean": round(float(s.get("test_fleet_mean") or float("nan")), 2),
        "cvar90": round(float(s.get("test_fleet_cvar90") or float("nan")), 2),
        "cong": round(float(s.get("test_congestion") or float("nan")), 3),
        "djk_mean": round(float(djk.get("fleet_mean") or float("nan")), 2),
        "beats_djk": s.get("beats_dijkstra_mean"),
        "beats_cvar": s.get("beats_dijkstra_cvar"),
        "stop": str(s.get("stop_reason") or "")[:50],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summaries", nargs="+", type=Path)
    args = parser.parse_args()
    rows = [load_row(p) for p in args.summaries]
    print("| " + " | ".join(COLS) + " |")
    print("| " + " | ".join(["---"] * len(COLS)) + " |")
    for r in rows:
        print("| " + " | ".join(str(r[c]) for c in COLS) + " |")


if __name__ == "__main__":
    main()
