"""Final scores of a trained run on held-out seeds, against the baselines on the same scenarios.

Seeds start at 60000 and are not used for training or for picking best.pt. Each seed runs every
combination of demand and fleet share under every controller, so gains are paired per seed. The
interval is a bootstrap over seeds: the seed is the independent unit, not the episode.

The actor plays in two modes, both reported: `sample` is what training evaluates, `argmax` always
takes its best exit. Choose the mode for the paper on seeds 50000+ (--start 50000), not here.
Teleports are reported, not priced (routing2.objectives). --teleport-s reruns a check of how much
a score depends on SUMO's teleport time. An existing result file is never overwritten.

    python -u -m routing2.eval_heldout --run <run_dir> --seeds 30 --workers 16
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

METRICS = ("T_all_s", "T_cust_s", "p95_all_s", "p95_cust_s", "arrived_share_all", "arrived_share_cust",
           "congestion_index", "teleports_per_1k_trips", "teleports_collision_per_1k_trips", "collisions_per_1k_trips")


def paired_gain(by_seed: dict[int, tuple[float, float]], draws: int = 10000, seed: int = 0) -> dict:
    """by_seed: seed -> (controller, reference), lower is better. Gain in percent of the reference mean."""
    keys = sorted(by_seed)
    x = np.array([by_seed[k][0] for k in keys], dtype=np.float64)
    r = np.array([by_seed[k][1] for k in keys], dtype=np.float64)
    gain = lambda i: 100.0 * (r[i].mean() - x[i].mean()) / r[i].mean()  # noqa: E731
    pick = np.random.default_rng(seed).integers(0, len(keys), (draws, len(keys)))
    boot = np.array([gain(i) for i in pick])
    return {"gain_pct": round(float(gain(np.arange(len(keys)))), 2),
            "ci95": [round(float(np.percentile(boot, 2.5)), 2), round(float(np.percentile(boot, 97.5)), 2)],
            "seeds_won": round(float((x < r).mean()), 3), "n_seeds": len(keys)}


def _init(conf: dict, teleport_s: float | None) -> None:
    from routing2 import sumo_marl as M

    M._worker_init(conf)
    if teleport_s is not None:
        M._W["env"].cfg.teleport_s = teleport_s


def _run(task: dict) -> dict:
    from routing2 import sumo_marl as M

    r = M._worker_run({**task, "best": task["name"] == "argmax"})
    return {"name": task["name"], "seed": task["seed"], "tph": task["tph"], "pen": task["pen"],
            "wall_s": r["wall_s"], "metrics": r["metrics"]}


def summarize(rows: list[dict], w_all: float) -> dict:
    from routing2.objectives import objective

    names = sorted({x["name"] for x in rows})
    J = lambda x: objective(x["metrics"], w_all)  # noqa: E731

    def seed_mean(name, value, keep=lambda x: True):
        out: dict[int, list[float]] = {}
        for x in rows:
            if x["name"] == name and keep(x):
                out.setdefault(x["seed"], []).append(value(x))
        return {k: float(np.mean(v)) for k, v in out.items()}

    def block(keep=lambda x: True):
        res = {}
        for n in names:
            vals = list(seed_mean(n, J, keep).values())
            res[n] = {"J": round(float(np.mean(vals)), 2),
                      "J_sd_seeds": round(float(np.std(vals, ddof=1)), 2) if len(vals) > 1 else None}
            for m in METRICS:
                res[n][m] = round(float(np.mean(list(seed_mean(n, lambda x: x["metrics"].get(m, float("nan")), keep).values()))), 3)
        return res

    base = [n for n in names if n not in ("sample", "argmax")]
    ctrl = [n for n in names if n in ("sample", "argmax")]
    gains = {}
    for c in ctrl:
        for b in base:
            a_, b_ = seed_mean(c, J), seed_mean(b, J)
            gains[f"{c}_vs_{b}"] = paired_gain({k: (a_[k], b_[k]) for k in a_ if k in b_})
            for m in ("T_all_s", "T_cust_s"):
                a_m, b_m = seed_mean(c, lambda x: x["metrics"][m]), seed_mean(b, lambda x: x["metrics"][m])
                gains[f"{c}_vs_{b}_{m}"] = paired_gain({k: (a_m[k], b_m[k]) for k in a_m if k in b_m})
    tphs, pens = sorted({x["tph"] for x in rows}), sorted({x["pen"] for x in rows})
    return {"overall": block(), "gains": gains,
            "by_tph": {str(t): block(lambda x, t=t: x["tph"] == t) for t in tphs},
            "by_pen": {str(p): block(lambda x, p=p: x["pen"] == p) for p in pens}}


def worker_conf(saved: dict, work_dir: Path) -> dict:
    """What a worker needs from the args.json of a run."""
    conf = {k: saved[k] for k in ("horizon", "zones", "hidden", "layers", "max_detour", "reward", "live_every",
                                  "incident_rate", "school_rate", "depart_window", "hot_share", "hot_zones",
                                  "peak_sd", "greedy_queue", "report_drop", "report_noise", "compliance")}
    conf.update(teleport_s=saved.get("teleport_s", 180.0), prior=saved.get("prior_w"),  # 180 s: runs before v7
                lateral=saved.get("lateral", 0.8))
    conf.update(bg_reroute=saved["bg_reroute"], net=str(Path(saved["net_dir"]) / "quan4_v4.net.xml"), work_dir=str(work_dir))
    return conf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--ckpt", type=Path, default=None, help="default: best.pt of the run")
    ap.add_argument("--start", type=int, default=60000)
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--tph", type=float, nargs="+", default=[8000.0, 10000.0])
    ap.add_argument("--pen", type=float, nargs="+", default=[0.25, 0.5, 0.75])
    ap.add_argument("--modes", nargs="+", default=["sample", "argmax"], choices=["sample", "argmax"])
    ap.add_argument("--baselines", nargs="*", default=["ff", "app", "greedy"], choices=["ff", "app", "greedy", "app_ext"])
    ap.add_argument("--queue", type=float, default=None, help="greedy: s per fleet vehicle; default: --tuned, else 0.5")
    ap.add_argument("--tuned", type=Path, default=None, help="tuned.json from routing2.tune_baselines")
    ap.add_argument("--drain", type=float, default=None, help="default: the run's --eval-drain")
    ap.add_argument("--teleport-s", type=float, default=None)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--work-dir", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None, help="default: the run directory")
    args = ap.parse_args()

    import torch

    from routing2 import sumo_marl as M

    saved = json.loads((args.run / "args.json").read_text(encoding="utf-8"))
    ck = torch.load(args.ckpt or args.run / "best.pt", map_location="cpu", weights_only=False)
    state = {k: v.numpy() for k, v in ck["net"].items()}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out_dir or args.run
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"heldout_eval_{stamp}.json"
    if out.exists():
        raise FileExistsError(out)
    conf = worker_conf(saved, args.work_dir or out_dir / f"work_heldout_{stamp}")
    drain = saved["eval_drain"] if args.drain is None else args.drain
    tuned = json.loads(args.tuned.read_text(encoding="utf-8")) if args.tuned else {}
    if "app_ext" in args.baselines and not tuned:
        ap.error("app_ext needs --tuned")
    queue = args.queue if args.queue is not None else tuned.get("greedy_queue", 0.5)
    extra = {"greedy": {"queue_s": queue}, "app_ext": tuned.get("app_ext", {})}
    tasks = []
    for s in range(args.seeds):
        for tph in args.tph:
            for pen in args.pen:
                # one SUMO seed per scenario seed, the same for every controller
                base = {"seed": args.start + s, "tph": tph, "pen": pen, "record": False, "drain": drain,
                        "sumo_seed": args.start + s}
                tasks += [{**base, "policy": "rl", "name": m, "state": state} for m in args.modes]
                tasks += [{**base, "policy": b, "name": b, **extra.get(b, {})} for b in args.baselines]
    t0 = time.time()
    rows = []
    with mp.get_context("spawn").Pool(args.workers, _init, (conf, args.teleport_s)) as pool:
        for i, r in enumerate(pool.imap_unordered(_run, tasks, chunksize=1), 1):
            rows.append(r)
            if i % 20 == 0 or i == len(tasks):
                print(f"[heldout] {i}/{len(tasks)} {(time.time() - t0) / 60:.1f} min", flush=True)
    summary = summarize(rows, saved["w_all"])
    out.write_text(json.dumps({"run": str(args.run), "update": ck.get("update"), "args": {k: str(v) for k, v in vars(args).items()},
                               "summary": summary, "rows": rows}, indent=1), encoding="utf-8")
    print(json.dumps({"overall": summary["overall"], "gains": summary["gains"]}, indent=1), flush=True)
    print(f"[heldout] wrote {out}\nHELDOUT_DONE", flush=True)


if __name__ == "__main__":
    main()
