"""Sample Mapbox OD seeds — L3: denser seeds inside WCC / allowlist only.

Full alley set (~5k) is too large to poll every cycle. Prefer:
  od_pairs from WCC (`od_pairs_wcc.json`) → sample 300–500 seeds.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


def _od_id(row: dict[str, Any]) -> str:
    return str(row.get("odId") or row.get("od_id") or "")


def _parse_lonlat(s: str) -> tuple[float, float] | None:
    try:
        a, b = s.split(",")
        return float(a.strip()), float(b.strip())
    except (ValueError, AttributeError):
        return None


def _origin_xy(row: dict[str, Any]) -> tuple[float, float] | None:
    return _parse_lonlat(str(row.get("origin") or ""))


def load_allowlist(path: Path | None) -> set[str] | None:
    if path is None or not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {_od_id(r) for r in data if _od_id(r)}
    if isinstance(data, dict) and "alleys" in data:
        return set(map(str, data["alleys"].keys()))
    if isinstance(data, dict) and "alley_ids" in data:
        return {str(x) for x in data["alley_ids"]}
    raise SystemExit(f"Unsupported allowlist format: {path}")


def sample_ods(
    od_path: Path,
    out_path: Path,
    n: int,
    seed: int = 42,
    *,
    allowlist: set[str] | None = None,
    spatial_bins: int = 8,
) -> dict:
    pairs = json.loads(od_path.read_text(encoding="utf-8"))
    if not isinstance(pairs, list):
        raise SystemExit("od_pairs must be a JSON array")

    if allowlist is not None:
        pairs = [p for p in pairs if _od_id(p) in allowlist]

    if not pairs:
        raise SystemExit("No OD pairs left after allowlist filter")

    rng = random.Random(seed)
    target_n = min(n, len(pairs))

    # Spatial coverage: bin by origin lon/lat when available
    bins: dict[tuple[int, int], list[dict[str, Any]]] = {}
    no_xy: list[dict[str, Any]] = []
    for p in pairs:
        xy = _origin_xy(p)
        if xy is None:
            no_xy.append(p)
            continue
        # coarse grid (relative ranks would need global min/max)
        lon, lat = xy
        bi = (int(lon * spatial_bins * 100) % spatial_bins, int(lat * spatial_bins * 100) % spatial_bins)
        bins.setdefault(bi, []).append(p)

    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _take(cand: dict[str, Any]) -> None:
        oid = _od_id(cand)
        if not oid or oid in seen:
            return
        seen.add(oid)
        chosen.append(cand)

    # Round-robin across spatial bins
    bucket_lists = [list(v) for v in bins.values()]
    for bl in bucket_lists:
        rng.shuffle(bl)
    if no_xy:
        rng.shuffle(no_xy)
        bucket_lists.append(no_xy)

    if not bucket_lists:
        bucket_lists = [list(pairs)]
        rng.shuffle(bucket_lists[0])

    i = 0
    while len(chosen) < target_n and any(bucket_lists):
        bl = bucket_lists[i % len(bucket_lists)]
        i += 1
        if not bl:
            continue
        _take(bl.pop())
        # drop empty buckets
        bucket_lists = [b for b in bucket_lists if b] or bucket_lists

    # Fill remainder randomly
    remain = [p for p in pairs if _od_id(p) not in seen]
    rng.shuffle(remain)
    for p in remain:
        if len(chosen) >= target_n:
            break
        _take(p)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(chosen, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {
        "source": str(od_path),
        "pool_after_allowlist": len(pairs),
        "allowlist_size": len(allowlist) if allowlist is not None else None,
        "seed_count": len(chosen),
        "requested_n": n,
        "output": str(out_path),
        "l3": True,
        "note": "Point Nest MAPBOX_OD_FILE here; poll peaks only (gentle batch).",
    }
    print(json.dumps(meta, indent=2))
    return meta


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="Sample Mapbox OD seeds (L3 WCC-aware)")
    p.add_argument(
        "--input",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "od_pairs.json",
        help="Prefer od_pairs_wcc.json after L2",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=root.parent
        / "ingestion-worker"
        / "config"
        / "od_pairs.quan4.seeds_l3.json",
    )
    p.add_argument("--n", type=int, default=400, help="Target seed count (L3: 300–500)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="JSON list of ODs, or alley_graph_wcc.json, or {alley_ids:[...]}",
    )
    p.add_argument("--spatial-bins", type=int, default=8)
    args = p.parse_args()
    allow = load_allowlist(args.allowlist)
    sample_ods(
        args.input,
        args.output,
        args.n,
        args.seed,
        allowlist=allow,
        spatial_bins=args.spatial_bins,
    )


if __name__ == "__main__":
    main()
