"""CLI: (t, O, D) → shortest travel time allowing alleys."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .env import AlleyRoutingEnv


def main() -> None:
    parser = argparse.ArgumentParser(description="Infer min travel time via alleys")
    parser.add_argument("--density", type=Path, required=True)
    parser.add_argument("--graph", type=Path, default=None)
    parser.add_argument("--t", type=float, default=0.0, help="Departure time (sec of day)")
    parser.add_argument("--origin", type=str, required=True)
    parser.add_argument("--destination", type=str, required=True)
    args = parser.parse_args()

    env = AlleyRoutingEnv(args.density, args.graph)
    travel = env.shortest_travel_time(args.t, args.origin, args.destination)
    out = {
        "t": args.t,
        "origin": args.origin,
        "destination": args.destination,
        "min_travel_time_sec": travel,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
