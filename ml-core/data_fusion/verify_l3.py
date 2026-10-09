"""L3 QA: Mapbox CSV + density meta vs observed/uncertainty targets."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def audit_mapbox(csv_path: Path) -> dict:
    pairs: dict[str, list[float]] = defaultdict(list)
    if not csv_path.exists():
        return {"error": f"missing {csv_path}"}
    with csv_path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            od = r.get("od_id") or ""
            if not od:
                continue
            try:
                d = float(r["duration_sec"])
            except (KeyError, TypeError, ValueError):
                continue
            pairs[od].append(d)
    pos = {od: sum(1 for x in v if x > 0) for od, v in pairs.items()}
    only_zero = sum(1 for c in pos.values() if c == 0)
    ge3 = sum(1 for c in pos.values() if c >= 3)
    return {
        "csv": str(csv_path),
        "od": len(pairs),
        "only_zero": only_zero,
        "only_zero_pct": round(100 * only_zero / max(len(pairs), 1), 2),
        "pos_ge3": ge3,
        "pos_ge3_pct": round(100 * ge3 / max(len(pairs), 1), 2),
    }


def audit_density(dens_path: Path) -> dict:
    rows = json.loads(dens_path.read_text(encoding="utf-8"))
    src: dict[str, int] = defaultdict(int)
    unc = sorted({round(float(r["uncertainty"]), 6) for r in rows})
    for r in rows:
        src[str(r.get("source") or "?")] += 1
    observed = src.get("observed", 0)
    return {
        "density": str(dens_path),
        "alleys": len(rows),
        "sources": dict(src),
        "observed": observed,
        "observed_pct": round(100 * observed / max(len(rows), 1), 2),
        "uncertainty_levels": unc,
        "uncertainty_n_levels": len(unc),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="L3 pass checker")
    p.add_argument("--mapbox", type=Path, required=True)
    p.add_argument(
        "--density",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "density" / "alley_density_latest.json",
    )
    p.add_argument("--min-observed", type=int, default=300)
    p.add_argument("--max-only-zero-pct", type=float, default=5.0)
    p.add_argument("--min-unc-levels", type=int, default=3)
    args = p.parse_args()

    mb = audit_mapbox(args.mapbox)
    dens = audit_density(args.density) if args.density.exists() else {"error": "no density"}
    ok = {
        "observed_ge_min": dens.get("observed", 0) >= args.min_observed
        or dens.get("observed_pct", 0) >= 5.0,
        "only_zero_ok": mb.get("only_zero_pct", 100) <= args.max_only_zero_pct,
        "unc_levels_ok": dens.get("uncertainty_n_levels", 0) >= args.min_unc_levels,
    }
    out = {"mapbox": mb, "density": dens, "pass": ok, "all_pass": all(ok.values())}
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
