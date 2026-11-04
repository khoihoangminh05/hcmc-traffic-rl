"""MARL next-hop routing trained directly in SUMO (PPO, shared policy, batch job).

Every controlled motorbike is an agent that picks its next link when it is about to reach the end
of its current one, one vehicle at a time (routing2.sumo_env, micro). The shared actor reads a GNN
compression of the network built from fleet reports and scores each exit
(routing2.gnn_policy). The critic is centralised: in training it also sees all vehicles.

Reward of a decision over the time to the vehicle's next decision (--reward attrib, the default):
    r = -[a (dt + D_cust) + b D_other] / 60 + (R - gamma^dt R') / 60
D_cust and D_other are the seconds of measured delay of customers and of other trips that the simulator
charges to this vehicle (sumo_env._attribute). A delay is split among the vehicles holding that vehicle
up, so charges add up to measured delay. a, b follow from J and the fleet share (fleet_weights), so no
weight is set by hand. R is the live time to the destination: potential-based, so it guides learning
without changing the best policy (--shaping). Neither term enters a score. Training only: the actor
never sees charges or the true state.

Other rewards, for comparison:
--reward team was r = -[(1 - rho) dt + rho I / mean rate] / 60, correlated 0.996 with the selfish reward:
I is the integral of the system rate w (trips in the system / trips) + (1 - w) (customers in the
system / customers), whose integral over an episode is exactly J. So the shared term is J itself,
with no estimate of who delayed whom; the central critic has to separate the credit. Dividing by the
episode's mean rate puts I on the scale of dt. rho = 0 is a selfish vehicle.
A rerun check of the charges was inconclusive: its noise floor was not measured.
--reward selfish is the vehicle's own time. Discounting is per second. Scores never use any of
these: every controller is scored on T_all, T_cust and J (routing2.objectives), w = --w-all.

Episodes run in worker processes (one libsumo per process), each with a CPU copy of
the policy; PPO updates run on the GPU. Every `--eval-every` updates the
policy and the baselines (free-flow next hop, app = live link time + live time to go, greedy = app +
a queue cost per fleet vehicle on or committed to the link)
play the fixed eval seeds 50000+, with `--eval-drain` extra seconds so that late trips can finish. In eval
the actor takes its best exit, the mode that is reported, and `best.pt` keeps the best J of that mode.
Baselines run once: their scores on the same seeds do not change.
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
from .sumo_env import FEAT_INTENT, FEAT_N

REWARD_SCALE = 60.0
POLICIES = ("rl", "ff", "app", "greedy")


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
                                                 teleport_s=conf.get("teleport_s", 180.0),
                                                 max_detour=conf["max_detour"],
                                                 attribute_every_s=5.0 if conf["reward"] == "attrib" else 0.0,
                                                 report_drop=conf["report_drop"], report_noise=conf["report_noise"],
                                                 fleet_snapshot=True, compliance=conf["compliance"],
                                                 bg_reroute_share=conf["bg_reroute"],
                                                 incident_rate_per_h=conf["incident_rate"],
                                                 school_rate_per_h=conf["school_rate"]))
    _W.update(g=g, zones=zones, env=env, conf=conf, net=RoutingNet.from_env(env, conf["hidden"], conf["layers"]))
    _W["net"].eval()


class _RLActor:
    """Samples from the policy while recording; `best` takes the top exit."""

    def __init__(self, net: RoutingNet, H: float, p: float, gen: torch.Generator, best: bool = False):
        self.net, self.H, self.p, self.gen, self.best = net, H, p, gen, best
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
        if self.best:
            return logits.argmax(1)
        a = torch.multinomial(torch.softmax(logits, 1), 1, generator=self.gen).squeeze(1)
        self.logp.append(torch.log_softmax(logits, 1).gather(1, a.unsqueeze(1)).squeeze(1))
        return a


class _Score:
    def __init__(self, live: bool, queue_s: float = 0.0):
        self.live, self.queue_s = live, queue_s

    def act(self, req):
        if self.live:
            load = req.feat[..., FEAT_N] + req.feat[..., FEAT_INTENT]
            return (req.live_cost + self.queue_s * load).argmin(1)
        s = req.feat[..., 0] + req.feat[..., 3]
        return torch.where(req.cand >= 0, s, torch.full_like(s, math.inf)).argmin(1)


def _worker_run(task: dict) -> dict:
    from .demand import make_demand
    from .sumo_env import N_FEAT

    conf, env = _W["conf"], _W["env"]
    H = conf["horizon"]
    d = make_demand(_W["g"], _W["zones"], [task["seed"]], task["tph"], H, task["pen"],
                    depart_window_s=conf["depart_window"], hot_share=conf["hot_share"], n_hot=conf["hot_zones"],
                    peak_sd=conf["peak_sd"])
    kind = task["policy"]
    actor = None
    if kind == "rl":
        _W["net"].load_state_dict({k: torch.from_numpy(v) for k, v in task["state"].items()})
        # 0: a provider does not know its share of the traffic. The critic does, in training.
        actor = _RLActor(_W["net"], H, 0.0, torch.Generator().manual_seed(task["seed"]), task.get("best", False))
        pol = actor
    else:
        pol = _Score(live=kind in ("app", "greedy"), queue_s=task.get("queue_s", conf["greedy_queue"]) if kind == "greedy" else 0.0)
    env.cfg.sumo_seed = task.get("sumo_seed", 1)
    env.cfg.horizon_s = H + task.get("drain", 0.0)
    env.cfg.incident_seed = task["seed"]  # same events for every policy on a seed
    ep = env.run(d, 0, pol, record=task["record"])
    out = {"seed": task["seed"], "tph": task["tph"], "policy": kind, "wall_s": ep.wall_s,
           "mean_tt_s": ep.ttt_s / max(1, ep.n_trips),
           "mean_tt_ctrl_s": ep.ttt_ctrl_s / max(1, ep.n_ctrl),
           "arrived_share": ep.arrived / max(1, ep.n_trips), "decisions": ep.n_decisions,
           "forced": ep.forced, "teleports": ep.teleports, "metrics": ep.metrics}
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
            togo=np.array([dd["togo"] for dd in ep.decisions], dtype=np.float32),
            e_cust=np.array([dd["e_cust"] for dd in ep.decisions], dtype=np.float32),
            e_other=np.array([dd["e_other"] for dd in ep.decisions], dtype=np.float32),
            sys_all=np.array([dd["sys_all"] for dd in ep.decisions], dtype=np.float32),
            sys_cust=np.array([dd["sys_cust"] for dd in ep.decisions], dtype=np.float32),
            sys_mean=(ep.system_all_s / env.cfg.horizon_s, ep.system_cust_s / env.cfg.horizon_s),
            veh=np.array([vids.setdefault(dd["vid"], len(vids)) for dd in ep.decisions], dtype=np.int64),
            done=np.array([dd["t"] + dd["dt"] < H - 1e-6 for dd in ep.decisions], dtype=bool),
        )
        if actor is not None:
            out["logp"] = torch.cat(actor.logp).numpy()
    return out


# ---------------------------------------------------------------- learner side

def _episode_reward(r: dict, args) -> np.ndarray:
    if args.reward == "selfish":
        base = -r["dt"] / REWARD_SCALE
    elif args.reward == "attrib":
        a, b = fleet_weights(args.w_all, r["pen"])
        base = -(a * (r["dt"] + r["e_cust"]) + b * r["e_other"]) / REWARD_SCALE
    else:
        base = team_reward(r["dt"], r["sys_all"], r["sys_cust"], r["sys_mean"], args.w_all, args.rho)
    return base + args.shaping * potential_shaping(r["togo"], r["veh"], r["t"], r["done"], r["dt"], args.gamma)


def potential_shaping(togo: np.ndarray, veh: np.ndarray, t: np.ndarray, done: np.ndarray, dt: np.ndarray,
                      gamma: float) -> np.ndarray:
    """(R - gamma^dt R') / REWARD_SCALE, R = time to go at each decision. R' = 0 for a vehicle that
    arrived; a vehicle cut at the horizon keeps its own R, as its value is bootstrapped there."""
    order = np.lexsort((t, veh))
    nxt = togo.copy()
    nxt[done] = 0.0
    same = veh[order][1:] == veh[order][:-1]
    nxt[order[:-1][same]] = togo[order[1:][same]]
    return (togo - gamma ** dt * nxt) / REWARD_SCALE


def team_reward(dt, sys_all, sys_cust, sys_mean, w: float, rho: float) -> np.ndarray:
    """sys_mean: (mean of the all-trips rate, mean of the customers rate) over the episode."""
    rate = max(w * sys_mean[0] + (1.0 - w) * sys_mean[1], 1e-6)
    return -((1.0 - rho) * dt + rho * (w * sys_all + (1.0 - w) * sys_cust) / rate) / REWARD_SCALE


def fleet_weights(w: float, p: float) -> tuple[float, float]:
    """(a, b): weights in the reward that make a vehicle's sum follow J. See the module docstring."""
    return w * p + 1.0 - w, w * p


def gae(r: np.ndarray, v: np.ndarray, veh: np.ndarray, t: np.ndarray, done: np.ndarray, dt: np.ndarray,
        gamma: float, lam: float) -> tuple[np.ndarray, np.ndarray]:
    """Per-vehicle GAE; gamma is per second, so a long wait is discounted more than a short one. A
    vehicle's last decision bootstraps with 0 if it arrived, else with its own value (cut at the horizon)."""
    adv = np.zeros_like(r)
    order = np.lexsort((t, veh))
    vs = veh[order]
    nxt_same = np.zeros(len(order), dtype=bool)
    nxt_same[:-1] = vs[1:] == vs[:-1]
    g = gamma ** dt
    last = 0.0
    for k in range(len(order) - 1, -1, -1):
        i = order[k]
        if nxt_same[k]:
            j = order[k + 1]
            last = r[i] + g[i] * v[j] - v[i] + g[i] * lam * last
        else:
            boot = 0.0 if done[i] else v[i]
            last = r[i] + g[i] * boot - v[i]
        adv[i] = last
    return adv, adv + v


def numpy_state(net: nn.Module) -> dict[str, np.ndarray]:
    """Weights for the workers. Tensors would cross the pool as one open file each, per task, which
    runs out of file descriptors at 24 workers."""
    return {k: v.detach().cpu().numpy() for k, v in net.state_dict().items()}


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
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--episodes", type=int, default=0, help="episodes per update (default = workers)")
    ap.add_argument("--updates", type=int, default=300)
    ap.add_argument("--horizon", type=float, default=900.0)
    ap.add_argument("--depart-window", type=float, default=600.0, help="trips depart in the first seconds")
    ap.add_argument("--tph", type=float, nargs=2, default=[4000.0, 7000.0], help="demand range per episode")
    ap.add_argument("--hot-share", type=float, default=0.0, help="share of trips to or from the hot zones")
    ap.add_argument("--hot-zones", type=int, default=4)
    ap.add_argument("--peak-sd", type=float, default=0.0, help="spread of departures / window, 0 = uniform")
    ap.add_argument("--greedy-queue", type=float, default=2.0, help="greedy baseline: s per fleet vehicle")
    ap.add_argument("--pen", type=float, nargs=2, default=[0.1, 1.0], help="range of the fleet share p per episode")
    ap.add_argument("--eval-pen", type=float, nargs="+", default=[0.25, 0.75])
    ap.add_argument("--max-detour", type=float, default=0.5, help="see SumoEnvConfig.max_detour")
    ap.add_argument("--teleport-s", type=float, default=300.0, help="SUMO --time-to-teleport, its default")
    ap.add_argument("--layers", type=int, default=3, help="GNN layers")
    ap.add_argument("--ticks-per-batch", type=int, default=64, help="report periods per PPO minibatch")
    ap.add_argument("--zones", type=int, default=32)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--live-every", type=float, default=10.0, help="seconds between fleet reports")
    ap.add_argument("--incident-rate", type=float, default=2.0, help="hidden accidents per hour")
    ap.add_argument("--school-rate", type=float, default=1.0, help="school releases per hour")
    # Learning rates, entropy schedule and size of a PPO step as in v3v, about 12 Adam steps per update.
    ap.add_argument("--lr-actor", type=float, default=1e-4)
    ap.add_argument("--lr-critic", type=float, default=5e-4)
    ap.add_argument("--steps", type=int, default=12, help="Adam steps per update")
    ap.add_argument("--critic-steps", type=int, default=24, help="extra critic-only Adam steps per update")
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--ent-start", type=float, default=0.03)
    ap.add_argument("--ent-end", type=float, default=0.005)
    ap.add_argument("--ent-anneal", type=int, default=400, help="updates from ent-start to ent-end")
    ap.add_argument("--vf", type=float, default=0.5)
    ap.add_argument("--gamma", type=float, default=0.9995, help="per simulated second")
    ap.add_argument("--reward", default="attrib", choices=["attrib", "team", "selfish"])
    # Real-world limits, the same for every controller. Invented values: swept in the results.
    ap.add_argument("--report-drop", type=float, default=0.2, help="share of fleet reports lost")
    ap.add_argument("--report-noise", type=float, default=0.1, help="lognormal error of a reported time")
    ap.add_argument("--compliance", type=float, default=0.9, help="share of instructions drivers follow")
    ap.add_argument("--bg-reroute", type=float, default=0.3, help="share of background trips using another app")
    ap.add_argument("--shaping", type=float, default=1.0, help="weight of the potential term, 0 = off")
    ap.add_argument("--rho", type=float, default=0.5, help="weight of the shared term in the team reward")
    ap.add_argument("--lam", type=float, default=0.95)
    ap.add_argument("--eval-every", type=int, default=25)
    ap.add_argument("--eval-seeds", type=int, default=8)
    ap.add_argument("--eval-tph", type=float, nargs="+", default=[4000.0, 6000.0])
    ap.add_argument("--eval-drain", type=float, default=900.0, help="extra simulated seconds in eval")
    ap.add_argument("--w-all", type=float, default=0.5, help="J = w T_all + (1 - w) T_cust")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--net-dir", type=Path, default=Path("../sumo-env/networks/v4"))
    ap.add_argument("--runs-dir", type=Path, default=Path("artifacts/out/quan4/routing2_runs"))
    ap.add_argument("--tag", default="")
    ap.add_argument("--smoke", action="store_true", help="2 workers, 5-min episodes, 2 updates, CPU")
    args = ap.parse_args()
    if args.smoke:
        args.workers, args.updates, args.horizon, args.depart_window = 2, 2, 300.0, 240.0
        args.tph, args.eval_tph, args.eval_seeds, args.eval_every = [2000.0, 3000.0], [2000.0], 1, 2
        args.eval_drain = 60.0
        args.device, args.ticks_per_batch = "cpu", 16
    E = args.episodes or args.workers

    from .graph import DEFAULT_GRAPH
    from .objectives import objective
    from .sumo_net import build_net

    net_path = build_net(DEFAULT_GRAPH, args.net_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = args.runs_dir / f"sumo_marl_{args.tag or args.reward}{'_smoke' if args.smoke else ''}_{stamp}_seed{args.seed}"
    run.mkdir(parents=True, exist_ok=True)
    (run / "args.json").write_text(json.dumps({**{k: (str(v) if isinstance(v, Path) else v)
                                                  for k, v in vars(args).items()},
                                               "git": git_hash()}, indent=2), encoding="utf-8")
    print(f"[marl] run={run} device={args.device} workers={args.workers} episodes/update={E}", flush=True)

    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    dev = torch.device(args.device)
    conf = {"horizon": args.horizon, "zones": args.zones, "net": str(net_path), "hidden": args.hidden,
            "layers": args.layers, "max_detour": args.max_detour, "reward": args.reward,
            "live_every": args.live_every, "incident_rate": args.incident_rate, "school_rate": args.school_rate,
            "depart_window": args.depart_window, "hot_share": args.hot_share, "hot_zones": args.hot_zones,
            "peak_sd": args.peak_sd, "greedy_queue": args.greedy_queue, "report_drop": args.report_drop,
            "report_noise": args.report_noise, "compliance": args.compliance, "bg_reroute": args.bg_reroute,
            "teleport_s": args.teleport_s, "work_dir": str(run / "work")}
    net = _learner_net(conf, run).to(dev)
    opt = torch.optim.Adam(net.param_groups(args.lr_actor, args.lr_critic), weight_decay=1e-5)
    ctx = mp.get_context("spawn")
    pool = ctx.Pool(args.workers, initializer=_worker_init, initargs=(conf,))
    metrics = (run / "metrics.jsonl").open("a", encoding="utf-8")

    base_rows: list[dict] = []

    def evaluate(u: int) -> dict:
        tasks = []
        st = numpy_state(net)
        for tph in args.eval_tph:
            for s in range(args.eval_seeds):
                for pen in args.eval_pen:
                    for pol in POLICIES:
                        if pol == "rl" or not base_rows:
                            tasks.append({"seed": 50000 + s, "tph": tph, "pen": pen, "policy": pol, "best": True,
                                          "record": False, "state": st, "drain": args.eval_drain})
        res = pool.map(_worker_run, tasks)
        if not base_rows:
            base_rows.extend(r for r in res if r["policy"] != "rl")
        res = [r for r in res if r["policy"] == "rl"] + base_rows
        out = {"update": u, "eval": {}}
        for pol in POLICIES:
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
        st = numpy_state(net)
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
        dts = np.concatenate([r["dt"] for r in res])
        rew = np.concatenate([_episode_reward(r, args) for r in res])
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
        actor_glob = torch.tensor([1.0, 0.0], device=dev)  # the actor is not told the fleet share

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
            return net.policy(h, z, cd, local, g_ * actor_glob, b), net.critic(hc, zc, cd, local, g_, b)

        n = len(a)
        keys = sorted(groups)
        v = np.zeros(n, dtype=np.float32)
        with torch.no_grad():
            for s0 in range(0, len(keys), args.ticks_per_batch):
                chunk = np.array(keys[s0:s0 + args.ticks_per_batch])
                idx = np.concatenate([groups[int(k)] for k in chunk])
                v[idx] = forward(chunk, idx)[1].cpu().numpy()
        adv, ret = gae(rew, v, veh, t, done, dts, args.gamma, args.lam)
        adv_t = torch.from_numpy(adv)
        adv_t = (adv_t - adv_t.mean()) / (adv_t.std() + 1e-8)
        ret_t = torch.from_numpy(ret)
        stats = {"pi": 0.0, "vf": 0.0, "ent": 0.0, "kl": 0.0, "clipfrac": 0.0, "k": 0}
        ent_coef = args.ent_start + (args.ent_end - args.ent_start) * min(1.0, (u - 1) / max(1, args.ent_anneal))
        net.train()
        shuffle = np.random.default_rng(int(rng.integers(1 << 31)))
        order = shuffle.permutation(keys)
        for step in range(args.steps):
            s0 = step * args.ticks_per_batch % len(order)
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
            loss = pi_loss + args.vf * vf_loss - ent_coef * ent
            opt.zero_grad()
            loss.backward()
            for group in opt.param_groups:
                nn.utils.clip_grad_norm_(group["params"], 1.0)
            opt.step()
            with torch.no_grad():
                stats["pi"] += float(pi_loss)
                stats["vf"] += float(vf_loss)
                stats["ent"] += float(ent)
                stats["kl"] += float((old_logp[ii].to(dev) - lp).mean())
                stats["clipfrac"] += float(((ratio - 1).abs() > args.clip).float().mean())
                stats["k"] += 1
        for step in range(args.critic_steps):
            s0 = (args.steps + step) * args.ticks_per_batch % len(order)
            chunk = np.array(order[s0:s0 + args.ticks_per_batch])
            idx = np.concatenate([groups[int(k)] for k in chunk])
            val = forward(chunk, idx)[1]
            vf_loss = args.vf * ((val - ret_t[torch.from_numpy(idx)].to(dev).float()) ** 2).mean()
            opt.zero_grad()
            vf_loss.backward()
            for group in opt.param_groups:
                nn.utils.clip_grad_norm_(group["params"], 1.0)
            opt.step()
        net.eval()
        k = max(1, stats.pop("k"))
        row = {"update": u, "samples": n, "episodes": len(res),
               "train_mean_tt_s": round(float(np.mean([r["mean_tt_s"] for r in res])), 2),
               "train_tph_mean": round(float(np.mean([r["tph"] for r in res])), 0),
               "reward_mean": round(float(rew.mean()), 4), "ent_coef": round(ent_coef, 5),
               "cut_share": round(float(1.0 - np.mean([r["arrived_share"] for r in res])), 4),
               "ev": round(float(1.0 - adv.var() / max(float(ret.var()), 1e-8)), 4),
               "dt_mean_s": round(float(dts.mean()), 2),
               "charged_mean_s": round(float(np.mean([(r["e_cust"] + r["e_other"]).mean() for r in res])), 2),
               "forced_share": round(float(np.mean([r["forced"] / max(1, r["forced"] + r["decisions"])
                                                     for r in res])), 3),
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
            torch.save({"net": net.state_dict(), "update": u}, run / f"ckpt_u{u}.pt")
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
