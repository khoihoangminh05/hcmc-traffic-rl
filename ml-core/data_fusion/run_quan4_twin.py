"""Quận 4 Twin pipeline: density → SUMO scenario + MARL infer/train smoke.

Usage (from ml-core):
  python -m data_fusion.run_quan4_twin
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from data_fusion.export_sumo import export_twin
from marl_agent.env import AlleyRoutingEnv
from marl_agent.train import train as marl_train


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ml_core() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_seed_ods(
    seeds_path: Path, graph_path: Path, n: int = 3
) -> list[tuple[str, str, str]]:
    """Return up to n (od_id, origin_node, dest_node) with a real directed path."""
    import networkx as nx

    seeds = json.loads(seeds_path.read_text(encoding="utf-8"))
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    alleys = payload.get("alleys") or {}
    g = nx.DiGraph()
    for e in payload.get("edge_list") or []:
        g.add_edge(str(e["u"]), str(e["v"]))

    endpoints: list[tuple[str, str, str]] = []
    for s in seeds:
        od = str(s.get("odId") or "")
        if od not in alleys:
            continue
        a = alleys[od]
        endpoints.append((od, str(a["u"]), str(a["v"])))

    pairs: list[tuple[str, str, str]] = []
    # Prefer multi-hop connected seed pairs
    for i, (od_i, u, _) in enumerate(endpoints):
        for j in range(i + 1, len(endpoints)):
            od_j, _, v = endpoints[j]
            if u == v:
                continue
            if nx.has_path(g, u, v):
                pairs.append((f"{od_i}__{od_j}", u, v))
                break
        if len(pairs) >= n:
            break
    if len(pairs) < n:
        for od, u, v in endpoints:
            if nx.has_path(g, u, v):
                pairs.append((od, u, v))
            if len(pairs) >= n:
                break
    return pairs[:n]


def _try_sumo(cfg: Path) -> str:
    sumo_bin = shutil.which("sumo")
    if not sumo_bin:
        return "skipped"
    try:
        proc = subprocess.run(
            [sumo_bin, "-c", str(cfg), "--no-step-log", "true", "--duration-log.disable", "true"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return "ok" if proc.returncode == 0 else f"failed:{proc.returncode}"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"failed:{exc}"


def run_quan4_twin(
    graph: Path,
    density: Path,
    seeds: Path,
    networks_dir: Path,
    routes_dir: Path,
    marl_out: Path,
    episodes: int = 20,
) -> dict[str, Any]:
    meta: dict[str, Any] = {}

    export_meta = export_twin(
        density=density,
        graph=graph,
        networks_dir=networks_dir,
        routes_dir=routes_dir,
        prefix="quan4_alleys",
        seeds=seeds,
    )
    meta["export"] = export_meta

    cfg = Path(export_meta["cfg"])
    meta["sumo_smoke"] = _try_sumo(cfg)

    od_pairs = _load_seed_ods(seeds, graph, n=3)
    if not od_pairs:
        raise RuntimeError("No seed OD endpoints found in graph")

    env = AlleyRoutingEnv(density, graph)
    infer_results: list[dict[str, Any]] = []
    for od_id, origin, dest in od_pairs:
        tt = env.shortest_travel_time(t=8 * 3600, origin=origin, destination=dest)
        if tt >= 1e6:
            raise RuntimeError(f"Infer failed for {od_id}: {origin} -> {dest}")
        infer_results.append(
            {
                "od_id": od_id,
                "origin": origin,
                "destination": dest,
                "min_travel_time_sec": tt,
            }
        )
    meta["infer"] = infer_results

    train_origin = od_pairs[0][1]
    train_dest = od_pairs[0][2]
    train_metrics = marl_train(
        density_path=density,
        graph_path=graph,
        output_dir=marl_out,
        episodes=episodes,
        seed=0,
        origin=train_origin,
        destination=train_dest,
    )
    meta["train"] = train_metrics
    meta["status"] = "QUAN4_TWIN_OK"
    return meta


def main() -> None:
    root = _repo_root()
    ml = _ml_core()
    parser = argparse.ArgumentParser(description="Quận 4 density → SUMO + MARL twin smoke")
    parser.add_argument(
        "--graph",
        type=Path,
        default=ml / "artifacts/out/quan4/alley_graph.json",
    )
    parser.add_argument(
        "--density",
        type=Path,
        default=ml / "artifacts/out/quan4/density/alley_density_latest.json",
    )
    parser.add_argument(
        "--seeds",
        type=Path,
        default=root / "ingestion-worker/config/od_pairs.quan4.seeds.json",
    )
    parser.add_argument(
        "--networks-dir",
        type=Path,
        default=root / "sumo-env/networks",
    )
    parser.add_argument(
        "--routes-dir",
        type=Path,
        default=root / "sumo-env/routes",
    )
    parser.add_argument(
        "--marl-out",
        type=Path,
        default=ml / "artifacts/out/quan4/marl",
    )
    parser.add_argument("--episodes", type=int, default=20)
    args = parser.parse_args()

    for p, name in (
        (args.graph, "graph"),
        (args.density, "density"),
        (args.seeds, "seeds"),
    ):
        if not p.exists():
            print(f"MISSING {name}: {p}", file=sys.stderr)
            sys.exit(1)

    meta = run_quan4_twin(
        graph=args.graph,
        density=args.density,
        seeds=args.seeds,
        networks_dir=args.networks_dir,
        routes_dir=args.routes_dir,
        marl_out=args.marl_out,
        episodes=args.episodes,
    )
    out_meta = args.marl_out / "quan4_twin_meta.json"
    args.marl_out.mkdir(parents=True, exist_ok=True)
    # routes_built may be large; keep summary
    slim = dict(meta)
    if "export" in slim and "routes_built" in slim["export"]:
        slim["export"] = {
            **{k: v for k, v in slim["export"].items() if k != "routes_built"},
            "routes_built_n": len(meta["export"].get("routes_built") or []),
            "routes_built": [
                {k: r[k] for k in ("route_id", "od_label", "origin", "destination", "n_edges") if k in r}
                for r in (meta["export"].get("routes_built") or [])
            ],
        }
    out_meta.write_text(json.dumps(slim, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(slim, indent=2, ensure_ascii=False))
    print("QUAN4_TWIN_OK")


if __name__ == "__main__":
    main()
