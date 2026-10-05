"""Sample a subset of Quận 4 alley OD pairs for Mapbox observation seeds.

Full alley set (~5k) is too large to poll every cycle — sample seeds, then
data_fusion interpolates density to all alley_id via the graph.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def sample_ods(
    od_path: Path,
    out_path: Path,
    n: int,
    seed: int = 42,
) -> dict:
    import random

    pairs = json.loads(od_path.read_text(encoding="utf-8"))
    if not isinstance(pairs, list):
        raise SystemExit("od_pairs must be a JSON array")
    rng = random.Random(seed)
    if n >= len(pairs):
        chosen = list(pairs)
    else:
        # Spatial-ish: sort by odId hash buckets then stride for coverage
        indexed = list(enumerate(pairs))
        indexed.sort(key=lambda iv: hash(iv[1].get("odId", str(iv[0]))) % 10_000)
        step = max(1, len(indexed) // n)
        chosen = [indexed[i][1] for i in range(0, len(indexed), step)][:n]
        # fill randomly if short
        while len(chosen) < n:
            cand = rng.choice(pairs)
            if cand not in chosen:
                chosen.append(cand)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(chosen, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {
        "source": str(od_path),
        "total_alleys": len(pairs),
        "seed_count": len(chosen),
        "output": str(out_path),
        "note": "NestJS MAPBOX_OD_FILE should point here for density step",
    }
    print(json.dumps(meta, indent=2))
    return meta


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser()
    p.add_argument(
        "--input",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "od_pairs.json",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=root.parent
        / "ingestion-worker"
        / "config"
        / "od_pairs.quan4.seeds.json",
    )
    p.add_argument("--n", type=int, default=120, help="Number of Mapbox seed ODs")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    sample_ods(args.input, args.output, args.n, args.seed)


if __name__ == "__main__":
    main()
