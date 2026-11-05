"""Tune baseline parameters on seeds 40000+, which no learned policy is ever selected on.

Parameters are chosen once here and then fixed for seeds 50000+ and 60000+. greedy: q, seconds per
fleet vehicle. app_ext: link set from an `app` history on the same seeds, then K, f, charge, cap
(.docs/paper/experiment_protocol.md, section 3b). All values are our own grid. Uses the scenario of
a run (args.json) and never touches the run. An existing output directory is refused.

    python -u -m routing2.tune_baselines --run <run_dir> --out-dir <dir> --workers 16
"""

from __future__ import annotations

import argparse
import itertools
import json
import multiprocessing as mp
import time
from pathlib import Path

import numpy as np

GREEDY_Q = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
EXT_K = (20, 50, 100)
EXT_F = (0.5, 0.7)
EXT_CHARGE_S = (15.0, 30.0, 60.0)
EXT_CAP = (0.03, 0.05, 0.10)


def _init(conf: dict) -> None:
    from routing2 import sumo_marl as M

    M._worker_init(conf)


def _run(task: dict) -> dict:
    from routing2 import sumo_marl as M

    r = M._worker_run(task)
    return {"name": task["name"], "seed": task["seed"], "tph": task["tph"], "pen": task["pen"],
            "metrics": r["metrics"], "hist": r.get("hist")}


def top_links(hist: np.ndarray, k: int) -> list[int]:
    """The k links with the largest summed excess; links without excess never qualify."""
    order = np.argsort(-hist, kind="stable")[:k]
    return [int(e) for e in order if hist[e] > 0.0]


def mean_J(rows: list[dict], w_all: float) -> dict[str, float]:
    """Controller -> J, seeds weighted equally."""
    from routing2.objectives import objective

    by: dict[str, dict[int, list[float]]] = {}
    for r in rows:
        by.setdefault(r["name"], {}).setdefault(r["seed"], []).append(objective(r["metrics"], w_all))
    return {n: float(np.mean([np.mean(v) for v in s.values()])) for n, s in by.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--start", type=int, default=40000)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--tph", type=float, nargs="+", default=[8000.0, 10000.0])
    ap.add_argument("--pen", type=float, nargs="+", default=[0.25, 0.75])
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--drain", type=float, default=None, help="default: the run's --eval-drain")
    ap.add_argument("--quick", action="store_true", help="one value of each app_ext parameter, to test the tool")
    args = ap.parse_args()
    if args.start + args.seeds > 50000:
        ap.error("tuning seeds must stay below 50000")
    args.out_dir.mkdir(parents=True, exist_ok=False)

    from routing2.eval_heldout import worker_conf

    saved = json.loads((args.run / "args.json").read_text(encoding="utf-8"))
    conf = worker_conf(saved, args.out_dir / "work")
    drain = saved["eval_drain"] if args.drain is None else args.drain
    scen = [{"seed": args.start + s, "tph": t, "pen": p, "record": False, "drain": drain,
             "sumo_seed": args.start + s} for s, t, p in itertools.product(range(args.seeds), args.tph, args.pen)]
    t0 = time.time()
    with mp.get_context("spawn").Pool(args.workers, _init, (conf,)) as pool:
        hist_rows = pool.map(_run, [{**b, "policy": "app_history", "name": "app"} for b in scen], chunksize=1)
        hist = np.sum([r.pop("hist") for r in hist_rows], axis=0)
        print(f"[tune] history {(time.time() - t0) / 60:.1f} min", flush=True)
        grid = {"K": EXT_K[:1], "f": EXT_F[:1], "charge_s": EXT_CHARGE_S[:1], "cap": EXT_CAP[:1]} if args.quick else \
            {"K": EXT_K, "f": EXT_F, "charge_s": EXT_CHARGE_S, "cap": EXT_CAP}
        ext = [dict(zip(grid, x)) for x in itertools.product(*grid.values())]
        qs = GREEDY_Q[:1] if args.quick else GREEDY_Q
        tasks = [{**b, "policy": "greedy", "name": f"greedy_q{q}", "queue_s": q} for q in qs for b in scen]
        for i, x in enumerate(ext):
            tasks += [{**b, "policy": "app_ext", "name": f"ext{i}", "links": top_links(hist, x["K"]), "f": x["f"],
                       "charge_s": x["charge_s"], "cap": x["cap"]} for b in scen]
        rows = []
        for i, r in enumerate(pool.imap_unordered(_run, tasks, chunksize=1), 1):
            r.pop("hist")
            rows.append(r)
            if i % 50 == 0 or i == len(tasks):
                print(f"[tune] {i}/{len(tasks)} {(time.time() - t0) / 60:.1f} min", flush=True)
    all_rows = hist_rows + rows
    J = mean_J(all_rows, saved["w_all"])
    best_q = min(qs, key=lambda q: J[f"greedy_q{q}"])
    i_best = min(range(len(ext)), key=lambda i: J[f"ext{i}"])
    x = ext[i_best]
    tuned = {"greedy_queue": best_q,
             "app_ext": {"links": top_links(hist, x["K"]), "f": x["f"], "charge_s": x["charge_s"], "cap": x["cap"]},
             "app_ext_grid_point": x, "J": {"app": J["app"], "greedy": J[f"greedy_q{best_q}"], "app_ext": J[f"ext{i_best}"]},
             "seeds": [args.start, args.seeds]}
    (args.out_dir / "tuned.json").write_text(json.dumps(tuned, indent=1), encoding="utf-8")
    (args.out_dir / "all.json").write_text(json.dumps({"J": J, "ext": ext, "hist": hist.tolist(), "rows": all_rows,
                                                       "args": {k: str(v) for k, v in vars(args).items()}}),
                                           encoding="utf-8")
    print(json.dumps({k: tuned[k] for k in ("greedy_queue", "app_ext_grid_point", "J")}), flush=True)
    print("TUNE_DONE", flush=True)


if __name__ == "__main__":
    main()
