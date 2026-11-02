"""MARL next-hop routing trained directly in SUMO (PPO, shared policy, batch job).

Every controlled motorbike is an agent that picks its next link at each node
(routing2.sumo_env). One shared policy scores each candidate exit from its
measurable features (pointer-style: permutation invariant, any node degree, no
node or zone ids, so it can transfer to other districts). The critic sees the
pooled candidate embeddings and the time of day.

Reward of a decision = -(time to the vehicle's next decision) / 60, so a vehicle's
return is minus its own remaining travel time ("selfish", v1). System-optimal
rewards (marginal external cost) come next; every controller is scored on the same
system metric: mean travel time of all trips (controlled and background).

Episodes run in worker processes (one libsumo per process), each with a CPU copy of
the policy; PPO updates run on the GPU. Every `--eval-every` updates the greedy
policy and the baselines (free-flow next hop, app = live link time + free-flow to go)
play the fixed eval seeds 50000+; `best.pt` keeps the best eval mean travel time.
Final numbers come from held-out seeds 60000+ (not in this script).

    python -u -m routing2.sumo_marl --smoke            # CPU, minutes
    CUDA_VISIBLE_DEVICES=1 python -u -m routing2.sumo_marl --workers 32 --updates 400
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import subprocess
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

N_IN = 8  # prepared per-candidate features
REWARD_SCALE = 60.0


def prep(feat: torch.Tensor, mask: torch.Tensor, t_frac: torch.Tensor) -> torch.Tensor:
    """Raw candidate features [M, D, 5] -> network input [M, D, N_IN].

    raw: free-flow s, current link time s, vehicles on link, free-flow to go s, length m.
    Relative terms compare a candidate with the best one at the same node.
    """
    ff, tt, n, togo, length = feat.unbind(-1)
    big = torch.full_like(ff, 1e6)
    a = torch.where(mask, ff + togo, big)
    b = torch.where(mask, tt + togo, big)
    rel_ff = (a - a.min(1, keepdim=True).values) / 60.0
    rel_tt = (b - b.min(1, keepdim=True).values) / 60.0
    x = torch.stack([ff / 60.0, tt / 60.0, (tt - ff) / 60.0, n / 10.0, togo / 600.0,
                     rel_ff.clamp(max=10.0), rel_tt.clamp(max=10.0),
                     t_frac.view(-1, 1).expand_as(ff)], -1)
    return torch.where(mask.unsqueeze(-1), x, torch.zeros_like(x))


class PointerPolicy(nn.Module):
    def __init__(self, hidden: int = 128):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(N_IN, hidden), nn.Tanh(), nn.Linear(hidden, hidden), nn.Tanh())
        self.ctx = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.Tanh())
        self.score = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.Tanh(), nn.Linear(hidden, 1))
        self.value = nn.Sequential(nn.Linear(2 * hidden + 1, hidden), nn.Tanh(), nn.Linear(hidden, 1))

    def forward(self, x: torch.Tensor, mask: torch.Tensor, t_frac: torch.Tensor):
        h = self.enc(x)  # [M, D, H]
        m = mask.unsqueeze(-1).float()
        mean = (h * m).sum(1) / m.sum(1).clamp(min=1.0)
        mx = torch.where(mask.unsqueeze(-1), h, torch.full_like(h, -1e4)).max(1).values
        pooled = torch.cat([mean, mx], -1)
        c = self.ctx(pooled)
        logits = self.score(torch.cat([h, c.unsqueeze(1).expand_as(h)], -1)).squeeze(-1)
        logits = torch.where(mask, logits, torch.full_like(logits, -1e9))
        v = self.value(torch.cat([pooled, t_frac.view(-1, 1)], -1)).squeeze(-1)
        return logits, v


# ---------------------------------------------------------------- worker side

_W: dict = {}


def _worker_init(conf: dict) -> None:
    torch.set_num_threads(1)
    from .demand import pick_zones
    from .graph import DEFAULT_GRAPH, load_graph
    from .params import SimConfig
    from .sumo_env import SumoEnvConfig, SumoRoutingEnv

    cfg = replace(SimConfig(), horizon_s=conf["horizon"])
    g = load_graph(DEFAULT_GRAPH, cfg)
    zones = pick_zones(g, conf["zones"], seed=0)
    work = Path(conf["work_dir"]) / f"w{os.getpid()}"
    env = SumoRoutingEnv(g, zones, SumoEnvConfig(net=Path(conf["net"]), horizon_s=conf["horizon"],
                                                 work_dir=work))
    _W.update(g=g, zones=zones, env=env, conf=conf, net=PointerPolicy(conf["hidden"]))
    _W["net"].eval()


class _RLActor:
    def __init__(self, net: PointerPolicy, H: float, greedy: bool, gen: torch.Generator):
        self.net, self.H, self.greedy, self.gen = net, H, greedy, gen
        self.logp: list[torch.Tensor] = []
        self.v: list[torch.Tensor] = []

    @torch.no_grad()
    def act(self, req):
        mask = req.cand >= 0
        tf = torch.full((len(req.vid),), req.t / self.H)
        logits, v = self.net(prep(req.feat, mask, tf), mask, tf)
        if self.greedy:
            a = logits.argmax(1)
        else:
            p = torch.softmax(logits, 1)
            a = torch.multinomial(p, 1, generator=self.gen).squeeze(1)
        self.logp.append(torch.log_softmax(logits, 1).gather(1, a.unsqueeze(1)).squeeze(1))
        self.v.append(v)
        return a


class _Score:
    def __init__(self, live: bool):
        self.live = live

    def act(self, req):
        f = req.feat
        s = (f[..., 1] if self.live else f[..., 0]) + f[..., 3]
        return torch.where(req.cand >= 0, s, torch.full_like(s, math.inf)).argmin(1)


def _worker_run(task: dict) -> dict:
    from .demand import make_demand

    conf, env = _W["conf"], _W["env"]
    H = conf["horizon"]
    d = make_demand(_W["g"], _W["zones"], [task["seed"]], task["tph"], H, task["pen"])
    kind = task["policy"]
    actor = None
    if kind == "rl":
        _W["net"].load_state_dict(task["state"])
        actor = _RLActor(_W["net"], H, task["greedy"], torch.Generator().manual_seed(task["seed"]))
        pol = actor
    else:
        pol = _Score(live=(kind == "app"))
    env.cfg.sumo_seed = task.get("sumo_seed", 1)
    ep = env.run(d, 0, pol, record=task["record"])
    out = {"seed": task["seed"], "tph": task["tph"], "policy": kind, "wall_s": ep.wall_s,
           "mean_tt_s": ep.ttt_s / max(1, ep.n_trips),
           "mean_tt_ctrl_s": ep.ttt_ctrl_s / max(1, ep.n_ctrl),
           "arrived_share": ep.arrived / max(1, ep.n_trips), "decisions": ep.n_decisions,
           "teleports": ep.teleports}
    if task["record"] and ep.decisions:
        D = env.Dmax
        M = len(ep.decisions)
        feat = np.zeros((M, D, 5), dtype=np.float32)
        mask = np.zeros((M, D), dtype=bool)
        for j, dd in enumerate(ep.decisions):
            k = len(dd["cand"])
            feat[j, :k] = dd["feat"].numpy()
            mask[j, :k] = True
        vids = {}
        out.update(
            feat=feat, mask=mask,
            a=np.array([dd["a"] for dd in ep.decisions], dtype=np.int64),
            t=np.array([dd["t"] for dd in ep.decisions], dtype=np.float32),
            dt=np.array([dd["dt"] for dd in ep.decisions], dtype=np.float32),
            veh=np.array([vids.setdefault(dd["vid"], len(vids)) for dd in ep.decisions], dtype=np.int64),
            done=np.array([dd["t"] + dd["dt"] < H - 1e-6 for dd in ep.decisions], dtype=bool),
        )
        if actor is not None:
            out["logp"] = torch.cat(actor.logp).numpy()
            out["v"] = torch.cat(actor.v).numpy()
    return out


# ---------------------------------------------------------------- learner side

def gae(r: np.ndarray, v: np.ndarray, veh: np.ndarray, t: np.ndarray, done: np.ndarray,
        gamma: float, lam: float) -> tuple[np.ndarray, np.ndarray]:
    """Per-vehicle GAE. A vehicle's last decision bootstraps with 0 if it arrived, else
    with its own value (truncated at the horizon)."""
    adv = np.zeros_like(r)
    order = np.lexsort((t, veh))
    vs, ts = veh[order], t[order]
    nxt_same = np.zeros(len(order), dtype=bool)
    nxt_same[:-1] = vs[1:] == vs[:-1]
    last = 0.0
    for k in range(len(order) - 1, -1, -1):
        i = order[k]
        if nxt_same[k]:
            j = order[k + 1]
            delta = r[i] + gamma * v[j] - v[i]
            last = delta + gamma * lam * last
        else:
            boot = 0.0 if done[i] else v[i]
            last = r[i] + gamma * boot - v[i]
        adv[i] = last
    _ = ts
    return adv, adv + v


def git_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--episodes", type=int, default=0, help="episodes per update (default = workers)")
    ap.add_argument("--updates", type=int, default=400)
    ap.add_argument("--horizon", type=float, default=1800.0)
    ap.add_argument("--tph", type=float, nargs=2, default=[4000.0, 7000.0], help="demand range per episode")
    ap.add_argument("--pen", type=float, default=1.0, help="share of trips controlled")
    ap.add_argument("--zones", type=int, default=32)
    ap.add_argument("--hidden", type=int, default=128)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--minibatch", type=int, default=65536)
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--ent", type=float, default=0.01)
    ap.add_argument("--vf", type=float, default=0.5)
    ap.add_argument("--gamma", type=float, default=0.995)
    ap.add_argument("--lam", type=float, default=0.95)
    ap.add_argument("--eval-every", type=int, default=25)
    ap.add_argument("--eval-seeds", type=int, default=4)
    ap.add_argument("--eval-tph", type=float, nargs="+", default=[4000.0, 6000.0])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--net-dir", type=Path, default=Path("../sumo-env/networks/v4"))
    ap.add_argument("--runs-dir", type=Path, default=Path("artifacts/out/quan4/routing2_runs"))
    ap.add_argument("--tag", default="selfish")
    ap.add_argument("--smoke", action="store_true", help="2 workers, 5-min episodes, 2 updates, CPU")
    args = ap.parse_args()
    if args.smoke:
        args.workers, args.updates, args.horizon = 2, 2, 300.0
        args.tph, args.eval_tph, args.eval_seeds, args.eval_every = [2000.0, 3000.0], [2000.0], 1, 2
        args.device, args.minibatch = "cpu", 4096
    E = args.episodes or args.workers

    from .graph import DEFAULT_GRAPH
    from .sumo_net import build_net

    net_path = build_net(DEFAULT_GRAPH, args.net_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = args.runs_dir / f"sumo_marl_{args.tag}{'_smoke' if args.smoke else ''}_{stamp}_seed{args.seed}"
    run.mkdir(parents=True, exist_ok=True)
    (run / "args.json").write_text(json.dumps({**{k: (str(v) if isinstance(v, Path) else v)
                                                  for k, v in vars(args).items()},
                                               "git": git_hash()}, indent=2), encoding="utf-8")
    print(f"[marl] run={run} device={args.device} workers={args.workers} episodes/update={E}", flush=True)

    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    dev = torch.device(args.device)
    net = PointerPolicy(args.hidden).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=args.lr)
    conf = {"horizon": args.horizon, "zones": args.zones, "net": str(net_path), "hidden": args.hidden,
            "work_dir": str(run / "work")}
    ctx = mp.get_context("spawn")
    pool = ctx.Pool(args.workers, initializer=_worker_init, initargs=(conf,))
    metrics = (run / "metrics.jsonl").open("a", encoding="utf-8")

    def cpu_state():
        return {k: v.detach().cpu() for k, v in net.state_dict().items()}

    def evaluate(u: int) -> dict:
        tasks = []
        for tph in args.eval_tph:
            for s in range(args.eval_seeds):
                for pol in ("rl", "ff", "app"):
                    tasks.append({"seed": 50000 + s, "tph": tph, "pen": args.pen, "policy": pol,
                                  "greedy": True, "record": False, "state": cpu_state()})
        res = pool.map(_worker_run, tasks)
        out = {"update": u, "eval": {}}
        for pol in ("rl", "ff", "app"):
            rows = [r for r in res if r["policy"] == pol]
            out["eval"][pol] = {
                "mean_tt_s": round(float(np.mean([r["mean_tt_s"] for r in rows])), 2),
                "by_tph": {str(t): round(float(np.mean([r["mean_tt_s"] for r in rows if r["tph"] == t])), 2)
                           for t in args.eval_tph},
                "arrived_share": round(float(np.mean([r["arrived_share"] for r in rows])), 3),
            }
        return out

    best = math.inf
    ep_seed = 1000
    t_start = time.perf_counter()
    for u in range(1, args.updates + 1):
        t0 = time.perf_counter()
        st = cpu_state()
        tasks = []
        for _ in range(E):
            ep_seed += 1
            tasks.append({"seed": ep_seed, "tph": float(rng.uniform(*args.tph)), "pen": args.pen,
                          "policy": "rl", "greedy": False, "record": True, "state": st,
                          "sumo_seed": int(rng.integers(1, 1_000_000))})
        res = [r for r in pool.map(_worker_run, tasks) if "feat" in r]
        t_col = time.perf_counter() - t0
        # flatten; vehicle ids made unique per episode
        feat = torch.from_numpy(np.concatenate([r["feat"] for r in res]))
        mask = torch.from_numpy(np.concatenate([r["mask"] for r in res]))
        a = torch.from_numpy(np.concatenate([r["a"] for r in res]))
        t = np.concatenate([r["t"] for r in res])
        old_logp = torch.from_numpy(np.concatenate([r["logp"] for r in res]))
        v = np.concatenate([r["v"] for r in res])
        rew = -np.concatenate([r["dt"] for r in res]) / REWARD_SCALE
        done = np.concatenate([r["done"] for r in res])
        off, veh = 0, []
        for r in res:
            veh.append(r["veh"] + off)
            off += int(r["veh"].max()) + 1
        veh = np.concatenate(veh)
        adv, ret = gae(rew, v, veh, t, done, args.gamma, args.lam)
        adv_t = torch.from_numpy(adv)
        adv_t = (adv_t - adv_t.mean()) / (adv_t.std() + 1e-8)
        ret_t = torch.from_numpy(ret)
        tf = torch.from_numpy(t / args.horizon)
        n = len(a)
        stats = {"pi": 0.0, "vf": 0.0, "ent": 0.0, "kl": 0.0, "clipfrac": 0.0, "k": 0}
        net.train()
        for _ in range(args.epochs):
            perm = torch.randperm(n)
            for s0 in range(0, n, args.minibatch):
                idx = perm[s0:s0 + args.minibatch]
                m = mask[idx].to(dev)
                tfi = tf[idx].to(dev).float()
                logits, val = net(prep(feat[idx].to(dev), m, tfi), m, tfi)
                logp_all = torch.log_softmax(logits, 1)
                lp = logp_all.gather(1, a[idx].to(dev).unsqueeze(1)).squeeze(1)
                ratio = torch.exp(lp - old_logp[idx].to(dev))
                ad = adv_t[idx].to(dev).float()
                pi_loss = -torch.min(ratio * ad, ratio.clamp(1 - args.clip, 1 + args.clip) * ad).mean()
                vf_loss = ((val - ret_t[idx].to(dev).float()) ** 2).mean()
                p = logp_all.exp()
                ent = -(torch.where(m, p * logp_all, torch.zeros_like(p))).sum(1).mean()
                loss = pi_loss + args.vf * vf_loss - args.ent * ent
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(net.parameters(), 0.5)
                opt.step()
                with torch.no_grad():
                    stats["pi"] += float(pi_loss)
                    stats["vf"] += float(vf_loss)
                    stats["ent"] += float(ent)
                    stats["kl"] += float((old_logp[idx].to(dev) - lp).mean())
                    stats["clipfrac"] += float(((ratio - 1).abs() > args.clip).float().mean())
                    stats["k"] += 1
        net.eval()
        k = max(1, stats.pop("k"))
        row = {"update": u, "samples": n, "episodes": len(res),
               "train_mean_tt_s": round(float(np.mean([r["mean_tt_s"] for r in res])), 2),
               "train_tph_mean": round(float(np.mean([r["tph"] for r in res])), 0),
               "collect_s": round(t_col, 1), "update_s": round(time.perf_counter() - t0 - t_col, 1),
               **{k2: round(v2 / k, 5) for k2, v2 in stats.items()},
               "elapsed_h": round((time.perf_counter() - t_start) / 3600, 3)}
        if u % args.eval_every == 0 or u == args.updates:
            ev = evaluate(u)
            row["eval"] = ev["eval"]
            score = ev["eval"]["rl"]["mean_tt_s"]
            if score < best:
                best = score
                torch.save({"net": net.state_dict(), "args": vars(args), "update": u, "eval": ev},
                           run / "best.pt")
            torch.save({"net": net.state_dict(), "opt": opt.state_dict(), "update": u}, run / "last.pt")
        metrics.write(json.dumps(row, default=str) + "\n")
        metrics.flush()
        print(f"[marl] {json.dumps(row, default=str)}", flush=True)

    pool.close()
    pool.join()
    (run / "summary.json").write_text(json.dumps({"best_eval_mean_tt_s": best, "run": str(run)}, indent=2),
                                      encoding="utf-8")
    print(f"[marl] done best_eval_mean_tt_s={best:.2f} run={run}", flush=True)


if __name__ == "__main__":
    main()
