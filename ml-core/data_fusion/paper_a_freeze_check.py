"""Paper A freeze gate: check twin artifacts before declaring paper_a_q4_wcc_peaks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="Paper A twin freeze checklist")
    p.add_argument(
        "--index",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "density" / "density_l1_index.json",
    )
    p.add_argument(
        "--wcc-meta",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "wcc" / "l2_wcc_meta.json",
    )
    p.add_argument("--min-observed-peak", type=int, default=100)
    p.add_argument("--require-morning", action="store_true", default=True)
    p.add_argument("--no-require-morning", action="store_true")
    p.add_argument(
        "--out",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "paper_a_freeze_meta.json",
    )
    args = p.parse_args()
    require_morning = args.require_morning and not args.no_require_morning

    idx = json.loads(args.index.read_text(encoding="utf-8"))
    wcc = json.loads(args.wcc_meta.read_text(encoding="utf-8"))
    peaks = idx.get("peaks") or {}
    obs = {k: int((v or {}).get("observed") or 0) for k, v in peaks.items()}
    peaks_ok = sum(1 for v in obs.values() if v >= args.min_observed_peak)
    morning_ok = (not require_morning) or obs.get("morning", 0) >= args.min_observed_peak
    checks = {
        "pass_single_wcc": bool(wcc.get("pass_single_wcc")),
        "peaks_with_observed_ge_min": peaks_ok >= 2,
        "morning_ok": morning_ok,
        "observed_by_peak": obs,
        "latest_peak": idx.get("latest_peak"),
        "min_observed_peak": args.min_observed_peak,
    }
    checks["ready_to_freeze"] = all(
        [
            checks["pass_single_wcc"],
            checks["peaks_with_observed_ge_min"],
            checks["morning_ok"],
        ]
    )
    meta = {
        "paper": "A",
        "data_tag_proposed": "paper_a_q4_wcc_peaks",
        "checks": checks,
        "index": str(args.index),
        "wcc_meta": str(args.wcc_meta),
        "note": "Freeze only when ready_to_freeze=true; then sync for Paper B train.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    raise SystemExit(0 if checks["ready_to_freeze"] else 2)


if __name__ == "__main__":
    main()
