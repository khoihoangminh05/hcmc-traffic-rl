"""L5: print a paper-facing metrics table from one or more run summary.json files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


KEYS = [
    "data_tag",
    "stop_reason",
    "best_update",
    "val_travel_time",
    "val_oracle_travel",
    "val_regret",
    "val_action_acc",
    "test_travel_time",
    "test_oracle_travel",
    "test_regret",
    "test_action_acc",
    "wall_seconds",
]


def load_summary(path: Path) -> dict:
    s = json.loads(path.read_text(encoding="utf-8"))
    # flatten common nesting
    flat = dict(s)
    for block in ("best_val", "test", "final_val", "metrics"):
        if isinstance(s.get(block), dict):
            for k, v in s[block].items():
                flat.setdefault(k, v)
                flat.setdefault(f"{block}_{k}", v)
    meta = {}
    meta_path = path.parent / "run_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    flat.setdefault("data_tag", meta.get("data_tag") or s.get("data_tag"))
    return flat


def row_from_summary(path: Path) -> dict:
    s = load_summary(path)
    # map aliases
    aliases = {
        "val_travel_time": ["val_travel_time", "best_val_travel_time", "travel_time"],
        "val_oracle_travel": ["val_oracle_travel", "oracle_travel", "best_val_oracle"],
        "val_regret": ["val_regret", "best_val_regret", "regret"],
        "val_action_acc": ["val_action_acc", "best_val_action_acc", "action_acc"],
        "test_travel_time": ["test_travel_time", "test_travel"],
        "test_oracle_travel": ["test_oracle_travel", "test_oracle"],
        "test_regret": ["test_regret"],
        "test_action_acc": ["test_action_acc"],
        "wall_seconds": ["wall_seconds", "elapsed_sec", "duration_sec"],
        "best_update": ["best_update", "best_at_update"],
        "stop_reason": ["stop_reason", "reason"],
    }
    out = {"run": str(path.parent.name), "summary": str(path)}
    out["data_tag"] = s.get("data_tag")
    for key, opts in aliases.items():
        for o in opts:
            if o in s and s[o] is not None:
                out[key] = s[o]
                break
        out.setdefault(key, None)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="L5 metrics table from summary.json")
    p.add_argument("summaries", nargs="+", type=Path, help="Paths to summary.json")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    rows = [row_from_summary(s) for s in args.summaries]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    cols = ["run", "data_tag", "val_regret", "val_action_acc", "test_regret", "test_action_acc", "stop_reason"]
    print(" | ".join(cols))
    print(" | ".join("---" for _ in cols))
    for r in rows:
        print(" | ".join(str(r.get(c, "")) for c in cols))


if __name__ == "__main__":
    main()
