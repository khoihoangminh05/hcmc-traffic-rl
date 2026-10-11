"""Preflight audit before sol1 micro train. python -m marl_agent._audit_micro_preflight"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from marl_agent.mappo_micro_env import MicroAlleyEnv
from marl_agent.mappo_micro_train import run_episode_baseline
from marl_agent.od_split import build_connected_od_pool, split_od_pairs


def main() -> None:
    base = Path(__file__).resolve().parents[1]
    graph = base / "artifacts/out/quan4/wcc/alley_graph_wcc.json"
    dens = base / "artifacts/out/quan4/wcc/alley_density_l4_cam_wcc.json"
    seeds = base.parent / "ingestion-worker/config/od_pairs.quan4.seeds_l3.json"
    peaks = {
        "morning": base
        / "artifacts/out/quan4/wcc/alley_density_peak_morning_paper_a_merged_wcc.json",
        "afternoon": base
        / "artifacts/out/quan4/wcc/alley_density_peak_afternoon_paper_a_merged_wcc.json",
        "evening": base
        / "artifacts/out/quan4/wcc/alley_density_peak_evening_paper_a_merged_wcc.json",
    }
    print("=== FILES ===")
    ok = True
    for name, p in [("graph", graph), ("dens", dens), ("seeds", seeds), *peaks.items()]:
        ex = p.exists()
        print(f"  {name}: {ex} {p}")
        ok = ok and ex
    if not ok:
        raise SystemExit("MISSING_FILES")

    pool = build_connected_od_pool(
        graph, seeds, min_path_edges=6, min_length_m=400, max_pairs=500
    )
    split = split_od_pairs(pool, seed=42)
    hops = np.array([p.n_edges for p in pool], dtype=float)
    lens = np.array([p.length_m for p in pool], dtype=float)
    print("=== OD FILTER (>=6 hops, >=400m) ===")
    print(
        f"  n={len(pool)} train/val/test="
        f"{len(split['train'])}/{len(split['val'])}/{len(split['test'])}"
    )
    print(
        f"  hops mean={hops.mean():.1f} p50={np.percentile(hops,50):.0f} "
        f"p90={np.percentile(hops,90):.0f} max={hops.max():.0f}"
    )
    print(
        f"  len_m mean={lens.mean():.0f} p50={np.percentile(lens,50):.0f} "
        f"p90={np.percentile(lens,90):.0f} max={lens.max():.0f}"
    )
    print(f"  share hops>64: {100 * np.mean(hops > 64):.1f}%  (max_steps risk)")

    g = json.loads(graph.read_text(encoding="utf-8"))
    outd: Counter[str] = Counter()
    for e in g["edge_list"]:
        outd[str(e["u"])] += 1
    degs = np.array(list(outd.values()), dtype=float)
    print("=== GRAPH DEGREE ===")
    print(
        f"  outdeg mean={degs.mean():.2f} max={degs.max():.0f} "
        f"pct>6={100 * np.mean(degs > 6):.1f}% pct>8={100 * np.mean(degs > 8):.1f}%"
    )

    catalog = {k: v for k, v in peaks.items() if v.exists()}
    env = MicroAlleyEnv(
        dens,
        graph,
        n_agents=16,
        max_degree=8,
        max_steps=96,
        seed=0,
        density_catalog=catalog,
    )
    train_ods = [(p.origin, p.destination) for p in split["train"]]
    test_ods = [(p.origin, p.destination) for p in split["test"]]
    env.set_od_pool(train_ods)

    print("=== TIME / PEAK ===")
    for t, expect in [(28800, "morning"), (50400, "afternoon"), (64800, "evening")]:
        obs, gstate, info = env.reset(options={"t": float(t)})
        oh = obs["agent_0"][2:5]
        print(
            f"  t={t} peak={info['peak']} expect~{expect} oh={oh.tolist()} "
            f"dens={env.density_path.name}"
        )
        assert info["peak"] == expect, (info["peak"], expect)

    print("=== BASELINES (12 eps, max_degree=8, max_steps=96) ===")
    for mode in ("dijkstra", "random", "greedy_load"):
        ms = [
            run_episode_baseline(env, mode, test_ods, 28800.0, 9000 + ep)
            for ep in range(12)
        ]
        print(
            f"  {mode:12s} mean={np.mean([m['fleet_mean'] for m in ms]):.1f} "
            f"cvar={np.mean([m['fleet_cvar90'] for m in ms]):.1f} "
            f"cong={np.mean([m['congestion'] for m in ms]):.3f}"
        )

    # Dijkstra timeout / hop feasibility
    timeouts = 0
    arrived_all = 0
    travels = []
    for ep in range(24):
        env.set_od_pool(test_ods)
        env.reset(seed=200 + ep, options={"t": 28800.0})
        for _ in range(env.max_steps):
            env.step(env.baseline_dijkstra_actions())
            if all(env._done):
                break
        if env._step_i >= env.max_steps:
            timeouts += 1
        if all(env._pos[i] == env._ods[i][1] for i in range(env.n_agents)):
            arrived_all += 1
        travels.append(float(np.mean(env._travel)))
    print("=== DIJKSTRA FEASIBILITY ===")
    print(f"  hit_max_steps={timeouts}/24  all_at_dest={arrived_all}/24  meanT={np.mean(travels):.1f}")

    # Can Dijkstra next-hop always be in action set?
    miss = 0
    total = 0
    env2 = MicroAlleyEnv(dens, graph, n_agents=1, max_degree=6, max_steps=80, seed=0)
    for p in split["train"][:80]:
        env2.set_od_pool([(p.origin, p.destination)])
        env2.reset(options={"t": 28800.0, "ods": [(p.origin, p.destination)]})
        for _ in range(80):
            if env2._done[0]:
                break
            curr, dest = env2._pos[0], env2._ods[0][1]
            neigh = env2._neighbors(curr)
            import networkx as nx

            try:
                path = nx.shortest_path(
                    env2._g,
                    curr,
                    dest,
                    weight=lambda a, b, d: env2._edge_free_time(a, b),
                )
                nxt = path[1]
            except Exception:
                break
            total += 1
            if nxt not in neigh[:6]:
                miss += 1
            env2.step({env2.agents[0]: neigh.index(nxt) if nxt in neigh else 0})
    print("=== ACTION TRUNCATION (max_degree=6) ===")
    print(f"  dijkstra_next_not_in_top6: {miss}/{total} ({100 * miss / max(total, 1):.1f}%)")

    print("PREFLIGHT_DONE")


if __name__ == "__main__":
    main()
