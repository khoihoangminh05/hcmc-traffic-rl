"""MARL next-hop routing trained directly in SUMO (PPO, shared policy, batch job).

Every controlled motorbike is an agent that picks its next link when it is about to reach the end
of its current one, one vehicle at a time (routing2.sumo_env, micro). The shared actor reads a GNN
compression of the network built from fleet reports and scores each exit
(routing2.gnn_policy). The critic is centralised: in training it also sees all vehicles.

Reward of a decision = -(time to the vehicle's next decision) / 60, so a vehicle's
return is minus its own remaining travel time ("selfish", v1). System-optimal
rewards (marginal external cost) come next. Every controller is scored on the same
two objectives (routing2.objectives): T_all, the mean time of all trips, and T_cust,
the mean time of the customers. J = w T_all + (1 - w) T_cust, w = --w-all.

Episodes run in worker processes (one libsumo per process), each with a CPU copy of
the policy; PPO updates run on the GPU. Every `--eval-every` updates the greedy
policy and the baselines (free-flow next hop, app = live link time + live time to go)
play the fixed eval seeds 50000+, with `--eval-drain` extra seconds so that late trips can
finish; `best.pt` keeps the best eval J.
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

from .gnn_policy import RoutingNet, prep_local

REWARD_SCALE = 60.0


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
                                                 work_dir=work, live_every_s=conf["live_every"],
                                                 live_source="probe", micro=True,
                                                 max_detour=conf["max_detour"],
                                                 incident_rate_per_h=conf["incident_rate"],
                                                 school_rate_per_h=conf["school_rate"]))
    _W.update(g=g, zones=zones, env=env, conf=conf, net=RoutingNet.from_env(env, conf["hidden"], conf["layers"]))
    _W["net"].eval()


class _RLActor:
    """Samples from the policy, also in evaluation: greedy would send identical vehicles the same way."""

    def __init__(self, net: RoutingNet, H: float, p: float, gen: torch.Generator):
        self.net, self.H, self.p, self.gen = net, H, p, gen
        self.logp: list[torch.Tensor] = []

    @torch.no_grad()
    def observe(self, state: dict) -> None:
        self.h, self.z = self.net.encode_actor(state["actor"].unsqueeze(0))

    @torch.no_grad()
    def act(self, req):
        M = len(req.vid)
        glob = torch.tensor([min(req.t / self.H, 1.0), self.p]).expand(M, -1)
        local = prep_local(req.feat, req.cand >= 0)
        logits = self.net.policy(self.h, self.z, req.cand, local, glob, torch.zeros(M, dtype=torch.long))
        a = torch.multinomial(torch.softmax(logits, 1), 1, generator=self.gen).squeeze(1)
        self.logp.append(torch.log_softmax(logits, 1).gather(1, a.unsqueeze(1)).squeeze(1))
        return a


class _Score:
    def __init__(self, live: bool):
        self.live = live

    def act(self, req):
        if self.live:
            return req.live_cost.argmin(1)
        s = req.feat[..., 0] + req.feat[..., 3]
        return torch.where(req.cand >= 0, s, torch.full_like(s, math.inf)).argmin(1)


def _worker_run(task: dict) -> dict:
    from .demand import make_demand
    from .sumo_env import N_FEAT

    conf, env = _W["conf"], _W["env"]
    H = conf["horizon"]
    d = make_demand(_W["g"], _W["zones"], [task["seed"]], task["tph"], H, task["pen"])
    kind = task["policy"]
    actor = None
    if kind == "rl":
        _W["net"].load_state_dict(task["state"])
        actor = _RLActor(_W["net"], H, task["pen"], torch.Generator().manual_seed(task["seed"]))
        pol = actor
    else:
        pol = _Score(live=(kind == "app"))
    env.cfg.sumo_seed = task.get("sumo_seed", 1)
    env.cfg.horizon_s = H + task.get("drain", 0.0)
    env.cfg.incident_seed = task["seed"]  # same events for every policy on a seed
    ep = env.run(d, 0, pol, record=task["record"])
    out = {"seed": task["seed"], "tph": task["tph"], "policy": kind, "wall_s": ep.wall_s,
           "mean_tt_s": ep.ttt_s / max(1, ep.n_trips),
           "mean_tt_ctrl_s": ep.ttt_ctrl_s / max(1, ep.n_ctrl),
           "arrived_share": ep.arrived / max(1, ep.n_trips), "decisions": ep.n_decisions,
           "teleports": ep.teleports, "metrics": ep.metrics}
    if task["record"] and ep.decisions:
        D = env.Dmax
        M = len(ep.decisions)
        feat = np.zeros((M, D, N_FEAT), dtype=np.float32)
        cand = np.full((M, D), -1, dtype=np.int64)
        for j, dd in enumerate(ep.decisions):
            k = len(dd["cand"])
            feat[j, :k] = dd["feat"].numpy()
            cand[j, :k] = dd["cand"]
        vids = {}
        out.update(
            feat=feat, cand=cand, pen=task["pen"],
            tick=np.array([dd["tick"] for dd in ep.decisions], dtype=np.int64),
            dyn=torch.stack([x["actor"] for x in ep.ticks]).numpy(),
            true=torch.stack([x["true"] for x in ep.ticks]).numpy(),
            a=np.array([dd["a"] for dd in ep.decisions], dtype=np.int64),
            t=np.array([dd["t"] for dd in ep.decisions], dtype=np.float32),
            dt=np.array([dd["dt"] for dd in ep.decisions], dtype=np.float32),
            veh=np.array([vids.setdefault(dd["vid"], len(vids)) for dd in ep.decisions], dtype=np.int64),
            done=np.array([dd["t"] + dd["dt"] < H - 1e-6 for dd in ep.decisions], dtype=bool),
        )
        if actor is not None:
            out["logp"] = torch.cat(actor.logp).numpy()
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


def _tick_groups(tick: np.ndarray) -> dict[int, np.ndarray]:
    """Report period -> indices of its decisions."""
    order = np.argsort(tick, kind="stable")
    keys, starts = np.unique(tick[order], return_index=True)
    return {int(k): g for k, g in zip(keys, np.split(order, starts[1:]))}


def _learner_net(conf: dict, run: Path) -> RoutingNet:
    from .demand import pick_zones
    from .graph import DEFAULT_GRAPH, load_graph
    from .params import SimConfig
    from .sumo_env import SumoEnvConfig, SumoRoutingEnv

    g = load_graph(DEFAULT_GRAPH, replace(SimConfig(), horizon_s=conf["horizon"]))
    env = SumoRoutingEnv(g, pick_zones(g, conf["zones"], seed=0), SumoEnvConfig(net=Path(conf["net"]), work_dir=run / "work"))
    return RoutingNet.from_env(env, conf["hidden"], conf["layers"])


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
    ap.add_argument("--pen", type=float, nargs=2, default=[0.1, 1.0], help="range of the fleet share p per episode")
    ap.add_argument("--eval-pen", type=float, nargs="+", default=[0.25, 0.75])
    ap.add_argument("--max-detour", type=float, default=0.5, help="see SumoEnvConfig.max_detour")
    ap.add_argument("--layers", type=int, default=3, help="GNN layers")
    ap.add_argument("--ticks-per-batch", type=int, default=64, help="report periods per PPO minibatch")
    ap.add_argument("--zones", type=int, default=32)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--live-every", type=float, default=10.0, help="seconds between fleet reports")
    ap.add_argument("--incident-rate", type=float, default=2.0, help="hidden accidents per hour")
    ap.add_argument("--school-rate", type=float, default=1.0, help="school releases per hour")
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--ent", type=float, default=0.01)
    ap.add_argument("--vf", type=float, default=0.5)
    ap.add_argument("--gamma", type=float, default=0.995)
    ap.add_argument("--lam", type=float, default=0.95)
    ap.add_argument("--eval-every", type=int, default=25)
    ap.add_argument("--eval-seeds", type=int, default=4)
    ap.add_argument("--eval-tph", type=float, nargs="+", default=[4000.0, 6000.0])
    ap.add_argument("--eval-drain", type=float, default=900.0, help="extra simulated seconds in eval")
    ap.add_argument("--w-all", type=float, default=0.5, help="J = w T_all + (1 - w) T_cust")
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
        args.eval_drain = 60.0
        args.device, args.ticks_per_batch = "cpu", 16
    E = args.episodes or args.workers

    from .graph import DEFAULT_GRAPH
    from .objectives import objective
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
    conf = {"horizon": args.horizon, "zones": args.zones, "net": str(net_path), "hidden": args.hidden,
            "layers": args.layers, "max_detour": args.max_detour,
            "live_every": args.live_every, "incident_rate": args.incident_rate, "school_rate": args.school_rate,
            "work_dir": str(run / "work")}
    net = _learner_net(conf, run).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=args.lr)
    ctx = mp.get_context("spawn")
    pool = ctx.Pool(args.workers, initializer=_worker_init, initargs=(conf,))
    metrics = (run / "metrics.jsonl").open("a", encoding="utf-8")

    def cpu_state():
        return {k: v.detach().cpu() for k, v in net.state_dict().items()}

    def evaluate(u: int) -> dict:
        tasks = []
        for tph in args.eval_tph:
            for s in range(args.eval_seeds):
                for pen in args.eval_pen:
                    for pol in ("rl", "ff", "app"):
                        tasks.append({"seed": 50000 + s, "tph": tph, "pen": pen, "policy": pol,
                                      "record": False, "state": cpu_state(), "drain": args.eval_drain})
        res = pool.map(_worker_run, tasks)
        out = {"update": u, "eval": {}}
        for pol in ("rl", "ff", "app"):
            rows = [r for r in res if r["policy"] == pol]
            J = lambda r: objective(r["metrics"], args.w_all)  # noqa: E731
            avg = lambda key, rs=rows: round(float(np.mean([r["metrics"][key] for r in rs])), 3)  # noqa: E731
            out["eval"][pol] = {
                "J": round(float(np.mean([J(r) for r in rows])), 2),
                **{k: avg(k) for k in ("T_all_s", "T_cust_s", "congestion_index", "p95_all_s", "p95_cust_s",
                                       "arrived_share_all", "arrived_share_cust", "teleports_per_1k_trips")},
                "by_tph": {str(t): {"J": round(float(np.mean([J(r) for r in rows if r["tph"] == t])), 2),
                                    "T_all_s": avg("T_all_s", [r for r in rows if r["tph"] == t]),
                                    "T_cust_s": avg("T_cust_s", [r for r in rows if r["tph"] == t])}
                           for t in args.eval_tph},
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
            tasks.append({"seed": ep_seed, "tph": float(rng.uniform(*args.tph)), "pen": float(rng.uniform(*args.pen)),
                          "policy": "rl", "record": True, "state": st,
                          "sumo_seed": int(rng.integers(1, 1_000_000))})
        res = [r for r in pool.map(_worker_run, tasks) if "feat" in r]
        t_col = time.perf_counter() - t0
        # flatten; vehicle and report-period ids made unique per episode
        feat = torch.from_numpy(np.concatenate([r["feat"] for r in res]))
        cand = torch.from_numpy(np.concatenate([r["cand"] for r in res]))
        a = torch.from_numpy(np.concatenate([r["a"] for r in res]))
        t = np.concatenate([r["t"] for r in res])
        old_logp = torch.from_numpy(np.concatenate([r["logp"] for r in res]))
        rew = -np.concatenate([r["dt"] for r in res]) / REWARD_SCALE
        done = np.concatenate([r["done"] for r in res])
        off, veh, tk_off, tick, pens = 0, [], 0, [], []
        for r in res:
            veh.append(r["veh"] + off)
            off += int(r["veh"].max()) + 1
            tick.append(r["tick"] + tk_off)
            tk_off += len(r["dyn"])
            pens.append(np.full(len(r["a"]), r["pen"], dtype=np.float32))
        veh, tick = np.concatenate(veh), np.concatenate(tick)
        dyn = torch.from_numpy(np.concatenate([r["dyn"] for r in res]))
        true = torch.from_numpy(np.concatenate([r["true"] for r in res]))
        glob = torch.stack([torch.from_numpy(t / args.horizon).clamp(max=1.0).float(),
                            torch.from_numpy(np.concatenate(pens))], -1)
        groups = _tick_groups(tick)
        tick_t = torch.from_numpy(tick)

        def forward(chunk: np.ndarray, idx: np.ndarray):
            """A minibatch is a set of report periods: each one needs one GNN pass, however many decide."""
            ids = torch.from_numpy(chunk)
            remap = torch.full((tk_off,), -1, dtype=torch.long)
            remap[ids] = torch.arange(len(ids))
            ii = torch.from_numpy(idx)
            b = remap[tick_t[ii]].to(dev)
            d, tr = dyn[ids].to(dev), true[ids].to(dev)
            cd, g_ = cand[ii].to(dev), glob[ii].to(dev)
            local = prep_local(feat[ii].to(dev), cd >= 0)
            h, z = net.encode_actor(d)
            hc, zc = net.encode_critic(d, tr)
            return net.policy(h, z, cd, local, g_, b), net.critic(hc, zc, cd, local, g_, b)

        n = len(a)
        keys = sorted(groups)
        v = np.zeros(n, dtype=np.float32)
        with torch.no_grad():
            for s0 in range(0, len(keys), args.ticks_per_batch):
                chunk = np.array(keys[s0:s0 + args.ticks_per_batch])
                idx = np.concatenate([groups[int(k)] for k in chunk])
                v[idx] = forward(chunk, idx)[1].cpu().numpy()
        adv, ret = gae(rew, v, veh, t, done, args.gamma, args.lam)
        adv_t = torch.from_numpy(adv)
        adv_t = (adv_t - adv_t.mean()) / (adv_t.std() + 1e-8)
        ret_t = torch.from_numpy(ret)
        stats = {"pi": 0.0, "vf": 0.0, "ent": 0.0, "kl": 0.0, "clipfrac": 0.0, "k": 0}
        net.train()
        for _ in range(args.epochs):
            order = np.random.default_rng(int(rng.integers(1 << 31))).permutation(keys)
            for s0 in range(0, len(order), args.ticks_per_batch):
                chunk = np.array(order[s0:s0 + args.ticks_per_batch])
                idx = np.concatenate([groups[int(k)] for k in chunk])
                ii = torch.from_numpy(idx)
                logits, val = forward(chunk, idx)
                logp_all = torch.log_softmax(logits, 1)
                lp = logp_all.gather(1, a[ii].to(dev).unsqueeze(1)).squeeze(1)
                ratio = torch.exp(lp - old_logp[ii].to(dev))
                ad = adv_t[ii].to(dev).float()
                pi_loss = -torch.min(ratio * ad, ratio.clamp(1 - args.clip, 1 + args.clip) * ad).mean()
                vf_loss = ((val - ret_t[ii].to(dev).float()) ** 2).mean()
                p = logp_all.exp()
                ent = -(torch.where(cand[ii].to(dev) >= 0, p * logp_all, torch.zeros_like(p))).sum(1).mean()
                loss = pi_loss + args.vf * vf_loss - args.ent * ent
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(net.parameters(), 0.5)
                opt.step()
                with torch.no_grad():
                    stats["pi"] += float(pi_loss)
                    stats["vf"] += float(vf_loss)
                    stats["ent"] += float(ent)
                    stats["kl"] += float((old_logp[ii].to(dev) - lp).mean())
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
            score = ev["eval"]["rl"]["J"]
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
    (run / "summary.json").write_text(json.dumps({"best_eval_J": best, "w_all": args.w_all, "run": str(run)}, indent=2),
                                      encoding="utf-8")
    print(f"[marl] done best_eval_J={best:.2f} run={run}", flush=True)


if __name__ == "__main__":
    main()
