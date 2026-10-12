"""MAPPO trainer for micro next-hop alley routing."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import yaml

from .early_stop import EarlyStopping
from .mappo_micro_env import MicroAlleyEnv
from .mappo_micro_vec import SubprocMicroEnvs
from .mappo_nets import CentralCritic, IndependentCritic, SharedActor
from .od_split import build_connected_od_pool, save_split, split_od_pairs


def _repo_ml_core() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve(path: Path | str, base: Path, *, must_exist: bool = True) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    cand = (base / p).resolve()
    if not must_exist or cand.exists():
        return cand
    return (base.parent / p).resolve()


def _load_density_catalog(data_cfg: dict[str, Any], base: Path) -> dict[str, Path]:
    catalog: dict[str, Path] = {}
    for name, rel in (data_cfg.get("density_by_peak") or {}).items():
        if not rel:
            continue
        p = _resolve(rel, base, must_exist=False)
        if p.exists():
            catalog[str(name)] = p
    return catalog


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def pick_device(name: str) -> torch.device:
    if name == "cpu":
        return torch.device("cpu")
    if name == "cuda":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def masked_categorical(
    logits: torch.Tensor, mask: torch.Tensor
) -> torch.distributions.Categorical:
    neg = torch.finfo(logits.dtype).min
    return torch.distributions.Categorical(logits=logits.masked_fill(mask < 0.5, neg))


# Shared eval seed base: policy and baselines MUST use the same (seed, t, OD).
EVAL_SEED_BASE = 50_000


def _fleet_metrics_from_env(env: MicroAlleyEnv, last: dict[str, Any]) -> dict[str, float]:
    travels = np.asarray(env._travel, dtype=np.float64)
    thr = float(np.quantile(travels, 0.9))
    cvar = (
        float(np.mean(travels[travels >= thr]))
        if np.any(travels >= thr)
        else float(np.mean(travels))
    )
    return {
        "fleet_mean": float(np.mean(travels)),
        "fleet_cvar90": cvar,
        "congestion": float(last.get("congestion", 0.0)),
        "arrival_rate": float(last.get("arrival_rate", 0.0)),
    }


def _mean_metric_dicts(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {
            "fleet_mean": 0.0,
            "fleet_cvar90": 0.0,
            "congestion": 0.0,
            "arrival_rate": 0.0,
            "n": 0.0,
        }
    keys = ("fleet_mean", "fleet_cvar90", "congestion", "arrival_rate")
    out = {k: float(np.mean([r[k] for r in rows])) for k in keys}
    out["n"] = float(len(rows))
    return out


def run_episode_baseline(
    env: MicroAlleyEnv,
    mode: str,
    ods_pool: list[tuple[str, str]],
    t: float,
    seed: int,
    *,
    ods: list[tuple[str, str]] | None = None,
) -> dict[str, float]:
    """One baseline episode. Prefer evaluate_fair_suite for paired comparisons."""
    env.set_od_pool(ods_pool)
    opts: dict[str, Any] = {"t": t}
    if ods is not None:
        opts["ods"] = ods
    env.reset(seed=seed, options=opts)
    last: dict[str, Any] = {"congestion": 0.0, "arrival_rate": 0.0}
    for _ in range(env.max_steps):
        if mode == "dijkstra":
            acts = env.baseline_dijkstra_actions()
        elif mode == "random":
            acts = env.baseline_random_actions()
        elif mode == "greedy_load":
            acts = env.baseline_greedy_load_actions()
        else:
            raise ValueError(mode)
        _, _, _, _, _, info = env.step(acts)
        last = info
        if info["all_done"]:
            break
    return _fleet_metrics_from_env(env, last)


@torch.no_grad()
def _batched_actions(
    actor: SharedActor,
    env: MicroAlleyEnv,
    obs: dict[str, np.ndarray],
    info: dict[str, Any],
    device: torch.device,
    *,
    greedy: bool = False,
) -> tuple[dict[str, int], list[torch.Tensor], list[torch.Tensor], list[torch.Tensor], list[torch.Tensor]]:
    """One GPU forward for all agents."""
    o_mat = np.stack([obs[a] for a in env.agents], axis=0)
    m_mat = np.stack([info["masks"][a] for a in env.agents], axis=0)
    o_t = torch.tensor(o_mat, dtype=torch.float32, device=device)
    m_t = torch.tensor(m_mat, dtype=torch.float32, device=device)
    dist = masked_categorical(actor(o_t), m_t)
    if greedy:
        act_t = torch.argmax(dist.logits, dim=-1)
    else:
        act_t = dist.sample()
    logp_t = dist.log_prob(act_t)
    actions = {a: int(act_t[i].item()) for i, a in enumerate(env.agents)}
    o_list = [o_t[i] for i in range(len(env.agents))]
    a_list = [act_t[i] for i in range(len(env.agents))]
    lp_list = [logp_t[i] for i in range(len(env.agents))]
    m_list = [m_t[i] for i in range(len(env.agents))]
    return actions, o_list, a_list, lp_list, m_list


@torch.no_grad()
def _run_policy_episode(
    env: MicroAlleyEnv,
    actor: SharedActor,
    device: torch.device,
    *,
    seed: int,
    t: float,
    ods: list[tuple[str, str]] | None,
    greedy: bool,
) -> dict[str, float]:
    opts: dict[str, Any] = {"t": t}
    if ods is not None:
        opts["ods"] = ods
    obs, _, info = env.reset(seed=seed, options=opts)
    last: dict[str, Any] = {"congestion": 0.0, "arrival_rate": 0.0}
    for _ in range(env.max_steps):
        actions, _, _, _, _ = _batched_actions(
            actor, env, obs, info, device, greedy=greedy
        )
        obs, _, _, _, _, step_info = env.step(actions)
        info = step_info
        last = step_info
        if step_info["all_done"]:
            break
    return _fleet_metrics_from_env(env, last)


@torch.no_grad()
def evaluate_policy(
    env: MicroAlleyEnv,
    actor: SharedActor,
    ods_pool: list[tuple[str, str]],
    t_list: list[float],
    device: torch.device,
    n_episodes: int = 16,
    *,
    greedy: bool = False,
    seed_base: int = EVAL_SEED_BASE,
) -> dict[str, float]:
    """Eval policy alone (val loop). Final test must use evaluate_fair_suite."""
    actor.eval()
    rows: list[dict[str, float]] = []
    env.set_od_pool(ods_pool)
    for ep in range(n_episodes):
        t = float(t_list[ep % len(t_list)])
        rows.append(
            _run_policy_episode(
                env,
                actor,
                device,
                seed=seed_base + ep,
                t=t,
                ods=None,
                greedy=greedy,
            )
        )
    actor.train()
    out = _mean_metric_dicts(rows)
    out["greedy"] = float(1.0 if greedy else 0.0)
    return out


@torch.no_grad()
def evaluate_fair_suite(
    env: MicroAlleyEnv,
    actor: SharedActor,
    ods_pool: list[tuple[str, str]],
    t_list: list[float],
    device: torch.device,
    n_episodes: int = 30,
    *,
    seed_base: int = EVAL_SEED_BASE,
    baseline_modes: tuple[str, ...] = ("dijkstra", "random", "greedy_load"),
) -> dict[str, Any]:
    """Paired comparison: identical env / OD / t / seed / step+reward for every controller.

    Only the action-selection rule differs. Locks ODs from the first reset of each
    episode so policy and baselines cannot drift.
    """
    actor.eval()
    env.set_od_pool(ods_pool)
    buckets: dict[str, list[dict[str, float]]] = {
        "policy_stoch": [],
        "policy_greedy": [],
        **{m: [] for m in baseline_modes},
    }
    for ep in range(n_episodes):
        t = float(t_list[ep % len(t_list)])
        seed = int(seed_base + ep)
        # Probe reset → freeze exact OD assignment for this episode.
        env.reset(seed=seed, options={"t": t})
        ods_ep = [(str(o), str(d)) for o, d in env._ods]
        buckets["policy_stoch"].append(
            _run_policy_episode(
                env, actor, device, seed=seed, t=t, ods=ods_ep, greedy=False
            )
        )
        buckets["policy_greedy"].append(
            _run_policy_episode(
                env, actor, device, seed=seed, t=t, ods=ods_ep, greedy=True
            )
        )
        for mode in baseline_modes:
            buckets[mode].append(
                run_episode_baseline(
                    env, mode, ods_pool, t, seed, ods=ods_ep
                )
            )
    actor.train()
    agg = {name: _mean_metric_dicts(rows) for name, rows in buckets.items()}
    djk = agg.get("dijkstra", {})
    pol_g = agg["policy_greedy"]
    pol_s = agg["policy_stoch"]
    # Primary fair flag: deterministic policy vs Dijkstra on the same episodes.
    beats_dijkstra_fair = bool(
        djk
        and pol_g["fleet_mean"] < djk["fleet_mean"]
        and float(pol_g.get("arrival_rate", 0.0))
        >= float(djk.get("arrival_rate", 0.0)) - 0.05
    )
    # Stoch reported too, but not used as primary fairness claim.
    beats_dijkstra_stoch = bool(
        djk
        and pol_s["fleet_mean"] < djk["fleet_mean"]
        and float(pol_s.get("arrival_rate", 0.0))
        >= float(djk.get("arrival_rate", 0.0)) - 0.05
    )
    return {
        **agg,
        "eval_protocol": "paired_identical_od_t_seed_step",
        "seed_base": int(seed_base),
        "n_episodes": int(n_episodes),
        "beats_dijkstra_fair": beats_dijkstra_fair,
        "beats_dijkstra_stoch": beats_dijkstra_stoch,
        "delta_fleet_greedy_minus_dijkstra": float(
            pol_g["fleet_mean"] - float(djk.get("fleet_mean", 0.0))
        )
        if djk
        else None,
    }


def early_stop_score(fleet_mean: float, arrival_rate: float, *, arr_penalty: float = 12_000.0) -> float:
    """Minimize. Penalize low arrival so checkpoints like v2b@125 (arr~0.16) are not preferred."""
    return float(fleet_mean) + float(arr_penalty) * (1.0 - float(arrival_rate))


def compute_gae(
    rewards: list[float],
    values: list[float],
    dones: list[bool],
    gamma: float,
    lam: float,
) -> tuple[list[float], list[float]]:
    """GAE for one agent trajectory (or team if rewards are team-level)."""
    adv: list[float] = [0.0] * len(rewards)
    last_gae = 0.0
    next_v = 0.0
    for t in reversed(range(len(rewards))):
        if dones[t]:
            next_v = 0.0
            last_gae = 0.0
        delta = rewards[t] + gamma * next_v - values[t]
        last_gae = delta + gamma * lam * last_gae
        adv[t] = last_gae
        next_v = values[t]
    rets = [adv[t] + values[t] for t in range(len(rewards))]
    return adv, rets


def _collect_teacher_batch(
    env: MicroAlleyEnv,
    t_train: list[float],
    *,
    episodes: int,
    seed: int,
    teacher: str,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    obs_rows: list[np.ndarray] = []
    mask_rows: list[np.ndarray] = []
    act_rows: list[int] = []
    for ep in range(episodes):
        t = float(rng.choice(t_train))
        obs, _, info = env.reset(seed=seed + ep, options={"t": t})
        for _ in range(env.max_steps):
            if teacher == "dijkstra":
                teach = env.baseline_dijkstra_actions()
            else:
                teach = env.baseline_greedy_load_actions()
            for i, a in enumerate(env.agents):
                if env._done[i]:
                    continue
                obs_rows.append(obs[a])
                mask_rows.append(info["masks"][a])
                act_rows.append(int(teach[a]))
            obs, _, _, _, _, info = env.step(teach)
            if info["all_done"]:
                break
    if not act_rows:
        return (
            np.zeros((0, 1), np.float32),
            np.zeros((0, 1), np.float32),
            np.zeros((0,), np.int64),
        )
    return (
        np.stack(obs_rows).astype(np.float32),
        np.stack(mask_rows).astype(np.float32),
        np.asarray(act_rows, dtype=np.int64),
    )


@torch.no_grad()
def measure_closed_loop_teacher_agree(
    env: MicroAlleyEnv,
    actor: SharedActor,
    ods_pool: list[tuple[str, str]],
    t_list: list[float],
    device: torch.device,
    *,
    n_episodes: int,
    seed_base: int,
    teacher: str = "dijkstra",
) -> float:
    """Fraction of greedy actions matching teacher under *policy* closed-loop states.

    Train-batch CE can look great while argmax drifts off the teacher trajectory;
    v2f greedy arr=0.85 was exactly this failure mode.
    """
    actor.eval()
    env.set_od_pool(ods_pool)
    agree = 0
    total = 0
    for ep in range(n_episodes):
        t = float(t_list[ep % len(t_list)])
        obs, _, info = env.reset(seed=seed_base + ep, options={"t": t})
        for _ in range(env.max_steps):
            if teacher == "dijkstra":
                teach = env.baseline_dijkstra_actions()
            else:
                teach = env.baseline_greedy_load_actions()
            acts, _, _, _, _ = _batched_actions(
                actor, env, obs, info, device, greedy=True
            )
            for i, a in enumerate(env.agents):
                if env._done[i]:
                    continue
                agree += int(int(acts[a]) == int(teach[a]))
                total += 1
            obs, _, _, _, _, info = env.step(acts)
            if info["all_done"]:
                break
    actor.train()
    return float(agree / max(total, 1))


_EMBED_PARITY_TOKEN = "__parity_node_xyz__"


def _embed_parity_worker(q: Any) -> None:
    """Top-level for spawn pickling (Windows)."""
    q.put(MicroAlleyEnv._hash_embed(_EMBED_PARITY_TOKEN, 8).tolist())


def assert_embed_parity_across_spawn() -> None:
    """Fail fast if node embeds differ under spawn (the v2f GPU-waster)."""
    import multiprocessing as mp

    parent = MicroAlleyEnv._hash_embed(_EMBED_PARITY_TOKEN, 8).tolist()
    ctx = mp.get_context("spawn")
    q: Any = ctx.Queue()
    p = ctx.Process(target=_embed_parity_worker, args=(q,))
    p.start()
    child = q.get(timeout=120)
    p.join(timeout=120)
    if parent != child:
        raise RuntimeError(
            "Node embeds differ across spawn workers — refusing to train. "
            "Use md5-stable _hash_embed (v2g+)."
        )
    print("[preflight] spawn embed parity OK", flush=True)


def behavioral_clone_baseline(
    env: MicroAlleyEnv,
    actor: SharedActor,
    train_ods: list[tuple[str, str]],
    t_train: list[float],
    device: torch.device,
    *,
    updates: int,
    episodes_per_update: int,
    seed: int,
    teacher: str = "dijkstra",
    lr: float = 1e-3,
    target_acc: float = 0.995,
    epochs_per_update: int = 6,
    holdout_episodes: int = 8,
) -> dict[str, float]:
    """Clone teacher; gate on *holdout* next-hop accuracy (not train-batch CE)."""
    if updates <= 0:
        return {"bc_updates": 0.0, "bc_acc": 0.0, "bc_ce": 0.0, "bc_train_acc": 0.0}
    if teacher not in ("dijkstra", "greedy_load"):
        raise ValueError(teacher)
    opt = torch.optim.Adam(actor.parameters(), lr=float(lr))
    print(
        f"[bc] teacher={teacher} max_updates={updates} eps/upd={episodes_per_update} "
        f"lr={lr} target_holdout_acc={target_acc} epochs={epochs_per_update} "
        f"holdout_eps={holdout_episodes}",
        flush=True,
    )
    rng = np.random.default_rng(seed + 7)
    env.set_od_pool(train_ods)
    last_acc, last_ce, last_train_acc = 0.0, 9.0, 0.0
    used = 0
    for u in range(1, updates + 1):
        used = u
        O, M, A = _collect_teacher_batch(
            env,
            t_train,
            episodes=episodes_per_update,
            seed=seed + 9_000_000 + u * 10_000,
            teacher=teacher,
            rng=rng,
        )
        if A.size < 16:
            continue
        o_t = torch.tensor(O, dtype=torch.float32, device=device)
        m_t = torch.tensor(M, dtype=torch.float32, device=device)
        a_t = torch.tensor(A, dtype=torch.long, device=device)
        n = int(o_t.shape[0])
        idx = np.arange(n)
        for _ep in range(max(1, int(epochs_per_update))):
            rng.shuffle(idx)
            for start in range(0, n, 2048):
                mb = idx[start : start + 2048]
                if len(mb) < 8:
                    continue
                mb_t = torch.tensor(mb, dtype=torch.long, device=device)
                dist = masked_categorical(
                    actor(o_t.index_select(0, mb_t)), m_t.index_select(0, mb_t)
                )
                loss = -dist.log_prob(a_t.index_select(0, mb_t)).mean()
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(actor.parameters(), 1.0)
                opt.step()
        with torch.no_grad():
            dist = masked_categorical(actor(o_t), m_t)
            pred = torch.argmax(dist.logits, dim=-1)
            last_train_acc = float((pred == a_t).float().mean().item())
        # Holdout batch — never used for the SGD steps above.
        Oh, Mh, Ah = _collect_teacher_batch(
            env,
            t_train,
            episodes=max(2, int(holdout_episodes)),
            seed=seed + 7_000_000 + u * 10_000,
            teacher=teacher,
            rng=rng,
        )
        if Ah.size >= 8:
            with torch.no_grad():
                oh = torch.tensor(Oh, dtype=torch.float32, device=device)
                mh = torch.tensor(Mh, dtype=torch.float32, device=device)
                ah = torch.tensor(Ah, dtype=torch.long, device=device)
                dist_h = masked_categorical(actor(oh), mh)
                pred_h = torch.argmax(dist_h.logits, dim=-1)
                last_acc = float((pred_h == ah).float().mean().item())
                last_ce = float((-dist_h.log_prob(ah)).mean().item())
        if (
            u == 1
            or u % max(1, updates // 10) == 0
            or u == updates
            or last_acc >= target_acc
        ):
            print(
                f"[bc] {u}/{updates} holdout_acc={last_acc:.4f} "
                f"train_acc={last_train_acc:.4f} ce={last_ce:.4f} n={n}",
                flush=True,
            )
        if last_acc >= target_acc:
            print(
                f"[bc] reached target_holdout_acc={target_acc} at update {u}",
                flush=True,
            )
            break
    if last_acc < target_acc:
        print(
            f"[bc] WARNING holdout_acc={last_acc:.4f} below target={target_acc}",
            flush=True,
        )
    return {
        "bc_updates": float(used),
        "bc_acc": float(last_acc),
        "bc_ce": float(last_ce),
        "bc_train_acc": float(last_train_acc),
    }


def fit_critic_on_teacher(
    env: MicroAlleyEnv,
    actor: SharedActor,
    critic: nn.Module,
    opt_critic: torch.optim.Optimizer,
    train_ods: list[tuple[str, str]],
    t_train: list[float],
    device: torch.device,
    *,
    episodes: int,
    seed: int,
    gamma: float,
    ippo: bool,
) -> float:
    """Fit critic on greedy-actor rollouts before PPO (cold critic wrecks BC)."""
    env.set_od_pool(train_ods)
    rng = np.random.default_rng(seed + 99)
    returns_buf: list[np.ndarray] = []
    state_buf: list[np.ndarray] = []
    for ep in range(episodes):
        t = float(rng.choice(t_train))
        obs, gstate, info = env.reset(
            seed=seed + 8_000_000 + ep, options={"t": t}
        )
        rewards_ep: list[np.ndarray] = []
        states_ep: list[np.ndarray] = []
        for _ in range(env.max_steps):
            if ippo:
                states_ep.append(np.stack([obs[a] for a in env.agents], axis=0))
            else:
                states_ep.append(np.asarray(gstate, dtype=np.float32))
            with torch.no_grad():
                actions, _, _, _, _ = _batched_actions(
                    actor, env, obs, info, device, greedy=True
                )
            obs, rew, _, _, gstate, info = env.step(actions)
            rewards_ep.append(
                np.asarray([float(rew[a]) for a in env.agents], dtype=np.float32)
            )
            if info["all_done"]:
                break
        T = len(rewards_ep)
        if T == 0:
            continue
        R = np.zeros((T, len(env.agents)), dtype=np.float32)
        running = np.zeros(len(env.agents), dtype=np.float32)
        for ti in reversed(range(T)):
            running = rewards_ep[ti] + float(gamma) * running
            R[ti] = running
        if ippo:
            for ti in range(T):
                # states_ep[ti]: [A, obs] — flatten like PPO collect
                state_buf.append(states_ep[ti])
                returns_buf.append(R[ti])
        else:
            for ti in range(T):
                # Match PPO: repeat global state per agent, target = per-agent return.
                g = states_ep[ti]
                state_buf.append(np.repeat(g[None, :], R.shape[1], axis=0))
                returns_buf.append(R[ti])
    if not returns_buf:
        return 0.0
    x = torch.tensor(
        np.concatenate(state_buf, axis=0), dtype=torch.float32, device=device
    )
    y = torch.tensor(
        np.concatenate(returns_buf, axis=0), dtype=torch.float32, device=device
    )
    last = 0.0
    idx = np.arange(x.shape[0])
    for _ in range(8):
        rng.shuffle(idx)
        for start in range(0, len(idx), 2048):
            mb = idx[start : start + 2048]
            if len(mb) < 8:
                continue
            mb_t = torch.tensor(mb, dtype=torch.long, device=device)
            pred = critic(x.index_select(0, mb_t)).view(-1)
            loss = F.mse_loss(pred, y.index_select(0, mb_t).view(-1))
            opt_critic.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(critic.parameters(), 1.0)
            opt_critic.step()
            last = float(loss.item())
    print(f"[bc] critic_fit mse={last:.3f} n={x.shape[0]}", flush=True)
    return last


def run_training(
    cfg: dict[str, Any], config_path: Path | None = None, ippo: bool = False
) -> dict[str, Any]:
    base = _repo_ml_core()
    seed = int(cfg.get("experiment", {}).get("seed", 42))
    set_seeds(seed)
    device = pick_device(str(cfg.get("experiment", {}).get("device", "auto")))

    data_cfg = cfg["data"]
    graph = _resolve(data_cfg["graph"], base, must_exist=True)
    density = _resolve(data_cfg["density"], base, must_exist=True)
    seeds_p = _resolve(data_cfg["seeds"], base, must_exist=True)
    density_catalog = _load_density_catalog(data_cfg, base)
    for p, name in ((graph, "graph"), (density, "density"), (seeds_p, "seeds")):
        if not p.exists():
            raise FileNotFoundError(f"Missing {name}: {p}")
    if data_cfg.get("require_l1_catalog") and len(density_catalog) < 2:
        raise FileNotFoundError("Need density_by_peak")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    exp_name = cfg.get("experiment", {}).get("name", "quan4_mappo_micro")
    data_tag = str(cfg.get("experiment", {}).get("data_tag", "mappo_micro_v1"))
    if ippo and not data_tag.endswith("_ippo"):
        data_tag += "_ippo"
    out_root = _resolve(
        cfg.get("experiment", {}).get("output_root", "artifacts/out/quan4/marl_runs"),
        base,
        must_exist=False,
    )
    run_dir = out_root / f"{exp_name}_{data_tag}_{stamp}_seed{seed}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "hyperparameters.snapshot.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    if config_path and config_path.exists():
        shutil.copy2(config_path, run_dir / "config.source.yaml")

    split_cfg = data_cfg.get("split", {})
    pool = build_connected_od_pool(
        graph,
        seeds_p,
        require_path=bool(split_cfg.get("require_path", True)),
        min_path_edges=int(split_cfg.get("min_path_edges", 6)),
        max_pairs=int(split_cfg.get("max_pairs", 500)),
        min_length_m=float(split_cfg.get("min_length_m", 400)),
    )
    split = split_od_pairs(
        pool,
        train_ratio=float(split_cfg.get("train_ratio", 0.7)),
        val_ratio=float(split_cfg.get("val_ratio", 0.15)),
        test_ratio=float(split_cfg.get("test_ratio", 0.15)),
        seed=seed,
    )
    save_split(split, run_dir / "od_split.json")
    if len(split["train"]) < 8:
        raise RuntimeError(
            f"OD pool too small after length filter ({len(pool)}). "
            "Lower min_length_m / min_path_edges."
        )
    train_ods = [(p.origin, p.destination) for p in split["train"]]
    val_ods = [(p.origin, p.destination) for p in split["val"]] or train_ods
    test_ods = [(p.origin, p.destination) for p in split["test"]] or val_ods

    env_cfg = cfg.get("env", {})
    n_agents = int(env_cfg.get("n_agents", 16))
    env = MicroAlleyEnv(
        density_path=density,
        graph_path=graph,
        seed=seed,
        n_agents=n_agents,
        max_degree=int(env_cfg.get("max_degree", 8)),
        max_steps=int(env_cfg.get("max_steps", 200)),
        compact_dim=int(env_cfg.get("compact_dim", 160)),
        bpr_alpha=float(env_cfg.get("bpr_alpha", 0.15)),
        bpr_beta=float(env_cfg.get("bpr_beta", 4.0)),
        bpr_load_cap=float(env_cfg.get("bpr_load_cap", 12.0)),
        corridor_prob=float(env_cfg.get("corridor_prob", 0.4)),
        reward_weights=env_cfg.get("reward_weights"),
        density_catalog=density_catalog or None,
    )
    env.set_od_pool(train_ods)
    env.warmup_peak_caches()
    obs0, g0, _ = env.reset(options={"t": 28800.0})
    obs_dim = int(obs0[env.agents[0]].shape[0])
    global_dim = int(g0.shape[0])
    n_actions = env.n_actions()

    hidden = int(cfg.get("model", {}).get("hidden", 256))
    actor = SharedActor(obs_dim, n_actions, hidden=hidden).to(device)
    critic: nn.Module
    if ippo:
        critic = IndependentCritic(obs_dim, hidden=hidden).to(device)
    else:
        critic = CentralCritic(global_dim, hidden=hidden).to(device)

    optim_cfg = cfg.get("optim", {})
    ppo_cfg = cfg.get("ppo", {})
    lr_actor = float(optim_cfg.get("lr_actor", 3e-4))
    lr_critic = float(optim_cfg.get("lr_critic", 1e-3))
    opt_actor = torch.optim.Adam(
        actor.parameters(), lr=lr_actor, weight_decay=float(optim_cfg.get("weight_decay", 1e-5))
    )
    opt_critic = torch.optim.Adam(
        critic.parameters(), lr=lr_critic, weight_decay=float(optim_cfg.get("weight_decay", 1e-5))
    )

    train_cfg = cfg.get("train", {})
    max_updates = int(train_cfg.get("max_updates", 3000))
    eval_every = int(train_cfg.get("eval_every", 25))
    log_every = int(train_cfg.get("log_every", 1))
    save_every = int(train_cfg.get("save_every", 50))
    n_envs = max(1, int(ppo_cfg.get("n_envs", 32)))
    rollout_n = int(ppo_cfg.get("rollout_episodes", 128))
    if rollout_n % n_envs != 0:
        rollout_n = max(n_envs, (rollout_n // n_envs) * n_envs)
    use_subproc = bool(ppo_cfg.get("use_subproc", True)) and n_envs > 1
    minibatch_size = int(ppo_cfg.get("minibatch_size", 8192))
    ppo_epochs = int(ppo_cfg.get("ppo_epochs", 4))
    clip_eps = float(ppo_cfg.get("clip_eps", 0.2))
    value_coef = float(ppo_cfg.get("value_coef", 0.5))
    entropy_coef = float(ppo_cfg.get("entropy_coef", 0.03))
    gamma = float(ppo_cfg.get("gamma", 0.99))
    gae_lam = float(ppo_cfg.get("gae_lambda", 0.95))
    grad_clip = float(optim_cfg.get("grad_clip_norm", 1.0))
    normalize_adv = bool(ppo_cfg.get("normalize_advantage", True))

    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
        torch.set_float32_matmul_precision("high")

    def _env_kwargs(i: int) -> dict[str, Any]:
        return {
            "density_path": density,
            "graph_path": graph,
            "seed": seed + 17 * (i + 1),
            "n_agents": n_agents,
            "max_degree": int(env_cfg.get("max_degree", 8)),
            "max_steps": int(env_cfg.get("max_steps", 200)),
            "compact_dim": int(env_cfg.get("compact_dim", 160)),
            "bpr_alpha": float(env_cfg.get("bpr_alpha", 0.15)),
            "bpr_beta": float(env_cfg.get("bpr_beta", 4.0)),
            "bpr_load_cap": float(env_cfg.get("bpr_load_cap", 12.0)),
            "corridor_prob": float(env_cfg.get("corridor_prob", 0.4)),
            "reward_weights": env_cfg.get("reward_weights"),
            "density_catalog": density_catalog or None,
        }

    vec: SubprocMicroEnvs | None = None
    local_envs: list[MicroAlleyEnv] = []
    if use_subproc:
        print(
            f"[mappo_micro] spawning {n_envs} subproc envs (CPU parallel)…",
            flush=True,
        )
        t_spawn = time.time()
        vec = SubprocMicroEnvs([_env_kwargs(i) for i in range(n_envs)])
        vec.set_od_pool(train_ods)
        print(
            f"[mappo_micro] subproc ready in {time.time() - t_spawn:.1f}s",
            flush=True,
        )
    else:
        print(f"[mappo_micro] in-process envs={n_envs} (no subproc)", flush=True)
        local_envs = [env] + [MicroAlleyEnv(**_env_kwargs(i)) for i in range(1, n_envs)]
        for e in local_envs:
            e.set_od_pool(train_ods)
            if e is not env:
                e.warmup_peak_caches()

    t_train = [float(x) for x in data_cfg.get("t_train", [28800])]
    t_eval = [float(x) for x in data_cfg.get("t_eval", [28800])]

    es_cfg = cfg.get("early_stopping", {})
    early = EarlyStopping(
        patience=int(es_cfg.get("patience", 30)),
        min_delta=float(es_cfg.get("min_delta", 1.0)),
        mode="min",
    )

    rng = np.random.default_rng(seed)
    jsonl_path = run_dir / "metrics.jsonl"
    csv_path = run_dir / "metrics.csv"
    best_path = run_dir / "best.pt"
    algo = "IPPO_micro" if ippo else "MAPPO_micro"

    lens = [p.n_edges for p in split["train"]]
    print(
        f"[mappo_micro] mode=FULL algo={algo} device={device} N={n_agents} "
        f"max_degree={n_actions} max_steps={env.max_steps} obs={obs_dim} "
        f"train_od={len(train_ods)} mean_hops={float(np.mean(lens)):.1f} "
        f"max_updates={max_updates} n_envs={n_envs} subproc={use_subproc} "
        f"minibatch={minibatch_size}",
        flush=True,
    )
    print(f"[mappo_micro] run_dir={run_dir}", flush=True)
    if device.type == "cuda":
        print(
            f"[mappo_micro] GPU={torch.cuda.get_device_name(0)} "
            f"mem={torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB",
            flush=True,
        )

    t0 = time.time()
    stop_reason = "max_updates"
    best_state: dict[str, Any] | None = None
    last_update = 0

    # Refuse to train if spawn workers would see different node embeds than main.
    if use_subproc:
        assert_embed_parity_across_spawn()

    bc_cfg = cfg.get("bc", {})
    freeze_actor_updates = int(bc_cfg.get("freeze_actor_updates", 0))
    if bool(bc_cfg.get("enabled", True)):
        bc_stats = behavioral_clone_baseline(
            env,
            actor,
            train_ods,
            t_train,
            device,
            updates=int(bc_cfg.get("updates", 200)),
            episodes_per_update=int(bc_cfg.get("episodes_per_update", 32)),
            seed=seed,
            teacher=str(bc_cfg.get("teacher", "dijkstra")),
            lr=float(bc_cfg.get("lr", 1e-3)),
            target_acc=float(bc_cfg.get("target_acc", 0.995)),
            epochs_per_update=int(bc_cfg.get("epochs_per_update", 6)),
            holdout_episodes=int(bc_cfg.get("holdout_episodes", 8)),
        )
        fit_critic_on_teacher(
            env,
            actor,
            critic,
            opt_critic,
            train_ods,
            t_train,
            device,
            episodes=int(bc_cfg.get("critic_fit_episodes", 64)),
            seed=seed,
            gamma=gamma,
            ippo=ippo,
        )
        n_bc_fair = int(bc_cfg.get("fair_check_episodes", 20))
        bc_fair = evaluate_fair_suite(
            env,
            actor,
            val_ods,
            t_eval,
            device,
            n_episodes=n_bc_fair,
            seed_base=EVAL_SEED_BASE,
            baseline_modes=("dijkstra",),
        )
        bc_val_g = bc_fair["policy_greedy"]
        bc_val = bc_fair["policy_stoch"]
        djk_f = float(bc_fair["dijkstra"]["fleet_mean"])
        pol_f = float(bc_val_g["fleet_mean"])
        pol_arr = float(bc_val_g.get("arrival_rate", 0.0))
        djk_arr = float(bc_fair["dijkstra"].get("arrival_rate", 0.0))
        ratio = float(pol_f / max(djk_f, 1.0))
        agree = measure_closed_loop_teacher_agree(
            env,
            actor,
            val_ods,
            t_eval,
            device,
            n_episodes=n_bc_fair,
            seed_base=EVAL_SEED_BASE + 100_000,
            teacher=str(bc_cfg.get("teacher", "dijkstra")),
        )
        print(
            f"[bc] done holdout_acc={bc_stats['bc_acc']:.4f} "
            f"train_acc={bc_stats.get('bc_train_acc', 0):.4f} "
            f"updates={bc_stats['bc_updates']:.0f} | "
            f"paired greedy fleet={pol_f:.1f}s arr={pol_arr:.3f} | "
            f"djk fleet={djk_f:.1f}s arr={djk_arr:.3f} | "
            f"ratio={ratio:.3f} closed_loop_agree={agree:.4f}",
            flush=True,
        )
        min_arr = float(bc_cfg.get("min_arrival_rate", 0.98))
        max_ratio = float(bc_cfg.get("max_fleet_ratio_vs_dijkstra", 1.10))
        min_agree = float(bc_cfg.get("min_closed_loop_agree", 0.95))
        min_holdout = float(bc_cfg.get("target_acc", 0.995))
        if float(bc_stats["bc_acc"]) < min_holdout:
            raise RuntimeError(
                f"BC holdout_acc={bc_stats['bc_acc']:.4f} < {min_holdout}. "
                "Aborting PPO."
            )
        if pol_arr < min_arr:
            raise RuntimeError(
                f"BC paired greedy arrival={pol_arr:.3f} < {min_arr}. Aborting PPO."
            )
        if pol_arr + 1e-6 < djk_arr - 0.02:
            raise RuntimeError(
                f"BC paired greedy arr={pol_arr:.3f} << Dijkstra arr={djk_arr:.3f}. "
                "Aborting PPO."
            )
        if ratio > max_ratio:
            raise RuntimeError(
                f"BC paired greedy fleet {pol_f:.1f} > {max_ratio}× Dijkstra "
                f"{djk_f:.1f} (ratio={ratio:.3f}). Aborting PPO."
            )
        if agree < min_agree:
            raise RuntimeError(
                f"BC closed-loop teacher agree={agree:.4f} < {min_agree}. "
                "Aborting PPO — argmax drifts off Dijkstra trajectory."
            )
        # Seed early-stop from the *same* paired greedy metrics used for the gate.
        arr_pen = float(es_cfg.get("arrival_penalty", 12_000.0))
        bc_score = early_stop_score(pol_f, pol_arr, arr_penalty=arr_pen)
        early.step(bc_score, 0)
        best_state = {
            "actor": {k: v.detach().cpu().clone() for k, v in actor.state_dict().items()},
            "critic": {
                k: v.detach().cpu().clone() for k, v in critic.state_dict().items()
            },
            "update": 0,
            "val": bc_val_g,
            "score": bc_score,
        }
        torch.save(
            {
                "actor": actor.state_dict(),
                "critic": critic.state_dict(),
                "obs_dim": obs_dim,
                "global_dim": global_dim,
                "n_actions": n_actions,
                "ippo": ippo,
                "update": 0,
                "val": bc_val_g,
                "score": bc_score,
                "bc": bc_stats,
                "bc_fair": {
                    "policy_greedy": bc_fair["policy_greedy"],
                    "policy_stoch": bc_fair["policy_stoch"],
                    "dijkstra": bc_fair["dijkstra"],
                    "ratio": ratio,
                    "closed_loop_agree": agree,
                },
            },
            best_path,
        )
        print(
            f"[bc] seeded best.pt score={bc_score:.1f} "
            f"(paired greedy) freeze_actor_updates={freeze_actor_updates}",
            flush=True,
        )

    try:
      with jsonl_path.open("w", encoding="utf-8") as jf, csv_path.open(
        "w", encoding="utf-8", newline=""
      ) as cf:
        csv_w = csv.DictWriter(
            cf,
            fieldnames=[
                "update",
                "mean_return",
                "fleet_mean",
                "loss",
                "entropy",
                "ep_len",
                "collect_sec",
                "ppo_sec",
                "n_samples",
            ],
        )
        csv_w.writeheader()

        for update in range(1, max_updates + 1):
            last_update = update
            ep_returns: list[float] = []
            ep_fleet: list[float] = []
            ep_lens: list[float] = []

            # --- rollouts: subproc CPU envs + batched GPU act ---
            # Keep trajectories in preallocated numpy; ONE GPU upload after collect.
            t_collect0 = time.time()
            ep_i = 0
            # flat sample lists (numpy) — concat once
            all_obs: list[np.ndarray] = []
            all_act: list[np.ndarray] = []
            all_logp: list[np.ndarray] = []
            all_mask: list[np.ndarray] = []
            all_g: list[np.ndarray] = []
            all_adv: list[np.ndarray] = []
            all_ret: list[np.ndarray] = []
            max_t = int(env.max_steps)

            while ep_i < rollout_n:
                chunk = min(n_envs, rollout_n - ep_i)
                seeds = [
                    seed + update * 100_000 + ep_i + j for j in range(chunk)
                ]
                ts = [float(rng.choice(t_train)) for _ in range(chunk)]

                if vec is not None:
                    obs_b, g_b, m_b = vec.reset_batch(seeds, ts)  # [E,A,D]
                else:
                    o_list, g_list, m_list = [], [], []
                    for j in range(chunk):
                        e = local_envs[j]
                        obs, gstate, info = e.reset(
                            seed=seeds[j], options={"t": ts[j]}
                        )
                        o_list.append(
                            np.stack([obs[a] for a in e.agents], axis=0)
                        )
                        g_list.append(gstate)
                        m_list.append(
                            np.stack(
                                [info["masks"][a] for a in e.agents], axis=0
                            )
                        )
                    obs_b = np.stack(o_list, axis=0).astype(np.float32)
                    g_b = np.stack(g_list, axis=0).astype(np.float32)
                    m_b = np.stack(m_list, axis=0).astype(np.float32)

                # [T, E, A, ...] — per-agent rewards (experiment; MAPPO paper often uses shared r)
                buf_o = np.zeros((max_t, chunk, n_agents, obs_dim), np.float32)
                buf_a = np.zeros((max_t, chunk, n_agents), np.int64)
                buf_lp = np.zeros((max_t, chunk, n_agents), np.float32)
                buf_m = np.zeros((max_t, chunk, n_agents, n_actions), np.float32)
                buf_g = np.zeros((max_t, chunk, global_dim), np.float32)
                buf_r = np.zeros((max_t, chunk, n_agents), np.float32)
                buf_v = np.zeros((max_t, chunk, n_agents), np.float32)
                buf_d = np.zeros((max_t, chunk), np.bool_)
                ep_len = np.zeros(chunk, dtype=np.int32)
                alive = np.ones(chunk, dtype=np.bool_)
                last_travel = np.zeros((chunk, n_agents), dtype=np.float64)

                for t in range(max_t):
                    if not alive.any():
                        break
                    alive_idx = np.flatnonzero(alive)
                    n_alive = int(alive_idx.size)
                    o_flat = np.ascontiguousarray(obs_b[alive_idx].reshape(-1, obs_dim))
                    m_flat = np.ascontiguousarray(m_b[alive_idx].reshape(-1, n_actions))
                    o_t = torch.from_numpy(o_flat).to(device, non_blocking=True)
                    m_t = torch.from_numpy(m_flat).to(device, non_blocking=True)
                    with torch.no_grad():
                        dist = masked_categorical(actor(o_t), m_t)
                        act_t = dist.sample()
                        logp_t = dist.log_prob(act_t)
                        if ippo:
                            v_np = (
                                critic(o_t)
                                .view(n_alive, n_agents)
                                .detach()
                                .cpu()
                                .numpy()
                                .astype(np.float32)
                            )
                        else:
                            g_t = torch.from_numpy(
                                np.ascontiguousarray(g_b[alive_idx])
                            ).to(device, non_blocking=True)
                            v_env = critic(g_t).view(-1).detach().cpu().numpy()
                            v_np = np.repeat(
                                v_env.astype(np.float32)[:, None], n_agents, axis=1
                            )
                        act_np = (
                            act_t.view(n_alive, n_agents).cpu().numpy().astype(np.int64)
                        )
                        logp_np = (
                            logp_t.view(n_alive, n_agents).cpu().numpy().astype(np.float32)
                        )

                    acts_full = np.zeros((chunk, n_agents), dtype=np.int64)
                    acts_full[alive_idx] = act_np
                    buf_o[t, alive_idx] = obs_b[alive_idx]
                    buf_a[t, alive_idx] = act_np
                    buf_lp[t, alive_idx] = logp_np
                    buf_m[t, alive_idx] = m_b[alive_idx]
                    buf_g[t, alive_idx] = g_b[alive_idx]
                    buf_v[t, alive_idx] = v_np

                    if vec is not None:
                        obs_b, g_b, m_b, rewards, dones, travels = vec.step_batch(
                            acts_full
                        )
                    else:
                        rewards = np.zeros((chunk, n_agents), dtype=np.float32)
                        dones = np.zeros(chunk, dtype=np.bool_)
                        travels = last_travel.copy()
                        for j in alive_idx:
                            e = local_envs[j]
                            actions = {
                                e.agents[i]: int(acts_full[j, i])
                                for i in range(n_agents)
                            }
                            obs, rew, _, _, gstate, info = e.step(actions)
                            obs_b[j] = np.stack(
                                [obs[a] for a in e.agents], axis=0
                            )
                            g_b[j] = gstate
                            m_b[j] = np.stack(
                                [info["masks"][a] for a in e.agents], axis=0
                            )
                            rewards[j] = np.asarray(
                                [float(rew[a]) for a in e.agents], dtype=np.float32
                            )
                            dones[j] = bool(info["all_done"])
                            travels[j] = np.asarray(e._travel, dtype=np.float64)

                    buf_r[t, alive_idx] = rewards[alive_idx]
                    if not np.isfinite(buf_r[t, alive_idx]).all():
                        raise RuntimeError("NaN reward")
                    buf_d[t, alive_idx] = dones[alive_idx]
                    ep_len[alive_idx] = t + 1
                    newly_done = alive_idx[dones[alive_idx]]
                    if newly_done.size:
                        last_travel[newly_done] = travels[newly_done]
                    alive[alive_idx] = ~dones[alive_idx]

                for j in range(chunk):
                    L = int(ep_len[j])
                    if L <= 0:
                        continue
                    d_j = buf_d[:L, j].tolist()
                    adv_parts: list[np.ndarray] = []
                    ret_parts: list[np.ndarray] = []
                    for ai in range(n_agents):
                        adv_i, ret_i = compute_gae(
                            buf_r[:L, j, ai].tolist(),
                            buf_v[:L, j, ai].tolist(),
                            d_j,
                            gamma,
                            gae_lam,
                        )
                        adv_parts.append(np.asarray(adv_i, dtype=np.float32))
                        ret_parts.append(np.asarray(ret_i, dtype=np.float32))
                    # interleave as [t0_a0, t0_a1, ..., t1_a0, ...] matching reshape
                    adv_mat = np.stack(adv_parts, axis=1)  # [L, A]
                    ret_mat = np.stack(ret_parts, axis=1)
                    o_flat = buf_o[:L, j].reshape(L * n_agents, obs_dim)
                    a_flat = buf_a[:L, j].reshape(L * n_agents)
                    lp_flat = buf_lp[:L, j].reshape(L * n_agents)
                    m_flat = buf_m[:L, j].reshape(L * n_agents, n_actions)
                    if ippo:
                        g_flat = o_flat
                    else:
                        g_flat = np.repeat(buf_g[:L, j], n_agents, axis=0)
                    all_obs.append(o_flat)
                    all_act.append(a_flat)
                    all_logp.append(lp_flat)
                    all_mask.append(m_flat)
                    all_g.append(g_flat)
                    all_adv.append(adv_mat.reshape(L * n_agents))
                    all_ret.append(ret_mat.reshape(L * n_agents))
                    ep_returns.append(float(np.sum(buf_r[:L, j])))
                    ep_fleet.append(float(np.mean(last_travel[j])))
                    ep_lens.append(float(L))
                ep_i += chunk
            collect_sec = time.time() - t_collect0

            batch_obs = torch.from_numpy(np.concatenate(all_obs, axis=0)).to(device)
            batch_act = torch.from_numpy(np.concatenate(all_act, axis=0)).long().to(device)
            batch_logp = torch.from_numpy(np.concatenate(all_logp, axis=0)).to(device)
            batch_mask = torch.from_numpy(np.concatenate(all_mask, axis=0)).to(device)
            batch_g = torch.from_numpy(np.concatenate(all_g, axis=0)).to(device)
            advantages = torch.from_numpy(np.concatenate(all_adv, axis=0)).to(device)
            batch_ret = torch.from_numpy(np.concatenate(all_ret, axis=0)).to(device)
            if normalize_adv and advantages.numel() > 1:
                advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
            n_samples = int(batch_obs.shape[0])

            t_ppo0 = time.time()
            last_loss = 0.0
            last_ent = 0.0
            idx_all = np.arange(n_samples)
            for _ in range(ppo_epochs):
                rng.shuffle(idx_all)
                for start in range(0, n_samples, minibatch_size):
                    mb = idx_all[start : start + minibatch_size]
                    if len(mb) < 8:
                        continue
                    mb_t = torch.tensor(mb, dtype=torch.long, device=device)
                    b_obs = batch_obs.index_select(0, mb_t)
                    b_act = batch_act.index_select(0, mb_t)
                    b_logp = batch_logp.index_select(0, mb_t)
                    b_ret = batch_ret.index_select(0, mb_t)
                    b_mask = batch_mask.index_select(0, mb_t)
                    b_g = batch_g.index_select(0, mb_t)
                    b_adv = advantages.index_select(0, mb_t)
                    logits = actor(b_obs)
                    dist = masked_categorical(logits, b_mask)
                    logp = dist.log_prob(b_act)
                    entropy = dist.entropy().mean()
                    ratio = torch.exp(logp - b_logp)
                    surr1 = ratio * b_adv
                    surr2 = torch.clamp(ratio, 1.0 - clip_eps, 1.0 + clip_eps) * b_adv
                    policy_loss = -torch.min(surr1, surr2).mean()
                    values = critic(b_g if not ippo else b_obs).view(-1)
                    value_loss = F.mse_loss(values, b_ret.view(-1))
                    # Freeze actor for first N updates so critic catches up on BC rollouts
                    # without wiping the Dijkstra clone (v2f: best stayed @0 after PPO noise).
                    freeze_actor = update <= freeze_actor_updates
                    if freeze_actor:
                        loss = value_coef * value_loss
                    else:
                        loss = (
                            policy_loss
                            + value_coef * value_loss
                            - entropy_coef * entropy
                        )
                    opt_actor.zero_grad()
                    opt_critic.zero_grad()
                    loss.backward()
                    if grad_clip > 0:
                        if not freeze_actor:
                            torch.nn.utils.clip_grad_norm_(actor.parameters(), grad_clip)
                        torch.nn.utils.clip_grad_norm_(critic.parameters(), grad_clip)
                    if not freeze_actor:
                        opt_actor.step()
                    opt_critic.step()
                    last_loss = float(loss.item())
                    last_ent = float(entropy.item())
            ppo_sec = time.time() - t_ppo0

            row = {
                "update": update,
                "mean_return": float(np.mean(ep_returns)),
                "fleet_mean": float(np.mean(ep_fleet)),
                "loss": last_loss,
                "entropy": last_ent,
                "ep_len": float(np.mean(ep_lens)),
                "collect_sec": collect_sec,
                "ppo_sec": ppo_sec,
                "n_samples": int(n_samples),
            }
            csv_w.writerow(row)
            cf.flush()
            jf.write(json.dumps({"type": "train", **row}) + "\n")
            jf.flush()
            if update % log_every == 0:
                print(
                    f"[train] {update}/{max_updates} | ret={row['mean_return']:.3f} "
                    f"fleet={row['fleet_mean']:.1f}s len={row['ep_len']:.1f} | "
                    f"loss={row['loss']:.3f} ent={row['entropy']:.4f} | "
                    f"collect={collect_sec:.1f}s ppo={ppo_sec:.1f}s n={n_samples}",
                    flush=True,
                )

            if update % eval_every == 0 or update == max_updates:
                # Score on GREEDY — same decision mode as beats_dijkstra_fair / BC seed.
                # Stoch logged for train-distribution monitoring only.
                n_val = 20
                val = evaluate_policy(
                    env, actor, val_ods, t_eval, device, n_episodes=n_val, greedy=False
                )
                val_g = evaluate_policy(
                    env, actor, val_ods, t_eval, device, n_episodes=n_val, greedy=True
                )
                arr_pen = float(es_cfg.get("arrival_penalty", 12_000.0))
                score = early_stop_score(
                    val_g["fleet_mean"],
                    val_g.get("arrival_rate", 0.0),
                    arr_penalty=arr_pen,
                )
                print(
                    f"[eval]  greedy fleet={val_g['fleet_mean']:.1f}s arr={val_g.get('arrival_rate', 0.0):.2f} "
                    f"cong={val_g['congestion']:.3f} | stoch fleet={val['fleet_mean']:.1f}s "
                    f"arr={val.get('arrival_rate', 0.0):.2f} | score={score:.1f} "
                    f"best={early.best_metric if early.best_update >= 0 else score:.1f}",
                    flush=True,
                )
                jf.write(
                    json.dumps(
                        {
                            "type": "eval",
                            "update": update,
                            **val_g,
                            "score": score,
                            "stoch_fleet_mean": val["fleet_mean"],
                            "stoch_arrival_rate": val.get("arrival_rate", 0.0),
                            "stoch_congestion": val["congestion"],
                            "greedy_fleet_mean": val_g["fleet_mean"],
                            "greedy_arrival_rate": val_g.get("arrival_rate", 0.0),
                            "greedy_congestion": val_g["congestion"],
                        }
                    )
                    + "\n"
                )
                jf.flush()
                if bool(es_cfg.get("enabled", True)):
                    st = early.step(score, update)
                    if st.reason == "improved" or best_state is None:
                        best_state = {
                            "actor": {k: v.detach().cpu().clone() for k, v in actor.state_dict().items()},
                            "critic": {
                                k: v.detach().cpu().clone() for k, v in critic.state_dict().items()
                            },
                            "update": update,
                            "val": val_g,
                            "score": score,
                        }
                        torch.save(
                            {
                                "actor": actor.state_dict(),
                                "critic": critic.state_dict(),
                                "obs_dim": obs_dim,
                                "global_dim": global_dim,
                                "n_actions": n_actions,
                                "ippo": ippo,
                                "update": update,
                                "val": val_g,
                                "score": score,
                                "cfg_tag": data_tag,
                            },
                            best_path,
                        )
                        print(
                            f"  [ckpt] best.pt score={score:.1f} "
                            f"greedy_fleet={val_g['fleet_mean']:.1f}s "
                            f"arr={val_g.get('arrival_rate', 0.0):.2f}",
                            flush=True,
                        )
                    if st.stopped:
                        print(f"  [early_stop] {st.reason}", flush=True)
                        stop_reason = st.reason
                        break
            if update % save_every == 0:
                torch.save(
                    {"actor": actor.state_dict(), "critic": critic.state_dict(), "update": update},
                    run_dir / f"ckpt_{update}.pt",
                )
    finally:
        if vec is not None:
            vec.close()
            vec = None

    if bool(es_cfg.get("restore_best", True)) and best_state is not None:
        actor.load_state_dict(best_state["actor"])
        critic.load_state_dict(best_state["critic"])
        print(f"[mappo_micro] restored best @{best_state['update']}", flush=True)

    n_test_ep = int(cfg.get("baseline", {}).get("n_episodes", 30))
    fair: dict[str, Any] = {}
    if bool(cfg.get("baseline", {}).get("run_on_eval", True)):
        print(
            f"[fair] paired eval n={n_test_ep} seed_base={EVAL_SEED_BASE} "
            "(same OD/t/seed/step/reward; only action rule differs)",
            flush=True,
        )
        fair = evaluate_fair_suite(
            env,
            actor,
            test_ods,
            t_eval,
            device,
            n_episodes=n_test_ep,
            seed_base=EVAL_SEED_BASE,
        )
        for name in ("policy_greedy", "policy_stoch", "dijkstra", "random", "greedy_load"):
            m = fair.get(name)
            if not m:
                continue
            print(
                f"  [fair] {name:14s} fleet={m['fleet_mean']:.1f}s "
                f"cvar={m['fleet_cvar90']:.1f}s arr={m['arrival_rate']:.2f}",
                flush=True,
            )
        print(
            f"  [fair] delta_greedy-djk={fair.get('delta_fleet_greedy_minus_dijkstra')} "
            f"beats_dijkstra_fair={fair.get('beats_dijkstra_fair')}",
            flush=True,
        )
    else:
        # Fallback: policy-only (no baseline compare).
        fair = {
            "policy_stoch": evaluate_policy(
                env, actor, test_ods, t_eval, device, n_episodes=n_test_ep, greedy=False
            ),
            "policy_greedy": evaluate_policy(
                env, actor, test_ods, t_eval, device, n_episodes=n_test_ep, greedy=True
            ),
            "eval_protocol": "policy_only",
        }

    test = fair.get("policy_stoch", {})
    test_g = fair.get("policy_greedy", {})
    djk = fair.get("dijkstra", {})
    rnd = fair.get("random", {})
    grd = fair.get("greedy_load", {})
    baselines = {
        k: fair[k]
        for k in ("dijkstra", "random", "greedy_load")
        if k in fair and isinstance(fair[k], dict) and "fleet_mean" in fair[k]
    }
    summary = {
        "algo": algo,
        "data_tag": data_tag,
        "seed": seed,
        "device": str(device),
        "n_agents": n_agents,
        "max_degree": n_actions,
        "max_steps": env.max_steps,
        "ippo": ippo,
        "updates_ran": int(last_update),
        "stop_reason": stop_reason,
        "best_val_score": early.best_metric if early.best_update >= 0 else None,
        "best_val_fleet_mean": (
            best_state["val"]["fleet_mean"] if best_state is not None else test_g.get("fleet_mean")
        ),
        "best_update": early.best_update,
        "eval_protocol": fair.get("eval_protocol"),
        "test_fleet_mean": test.get("fleet_mean"),
        "test_fleet_cvar90": test.get("fleet_cvar90"),
        "test_congestion": test.get("congestion"),
        "test_arrival_rate": test.get("arrival_rate"),
        "test_greedy_fleet_mean": test_g.get("fleet_mean"),
        "test_greedy_arrival_rate": test_g.get("arrival_rate"),
        "baselines_test": baselines,
        "fair_suite": {
            k: fair[k]
            for k in (
                "policy_greedy",
                "policy_stoch",
                "dijkstra",
                "random",
                "greedy_load",
                "delta_fleet_greedy_minus_dijkstra",
                "beats_dijkstra_fair",
                "beats_dijkstra_stoch",
                "seed_base",
                "n_episodes",
                "eval_protocol",
            )
            if k in fair
        },
        # Primary: greedy policy vs Dijkstra on identical paired episodes.
        "beats_dijkstra_mean": bool(
            djk and test_g.get("fleet_mean", 1e18) < djk["fleet_mean"]
        )
        if djk
        else None,
        "beats_random_mean": bool(
            rnd and test_g.get("fleet_mean", 1e18) < rnd["fleet_mean"]
        )
        if rnd
        else None,
        "beats_greedy_mean": bool(
            grd and test_g.get("fleet_mean", 1e18) < grd["fleet_mean"]
        )
        if grd
        else None,
        "beats_dijkstra_fair": fair.get("beats_dijkstra_fair"),
        "beats_dijkstra_stoch": fair.get("beats_dijkstra_stoch"),
        "beats_random_fair": bool(
            rnd
            and test_g.get("fleet_mean", 1e18) < rnd["fleet_mean"]
            and float(test_g.get("arrival_rate", 0.0))
            >= max(0.5, float(rnd.get("arrival_rate", 0.0)))
        )
        if rnd
        else None,
        "train_od_mean_hops": float(np.mean(lens)),
        "elapsed_sec": time.time() - t0,
        "run_dir": str(run_dir),
        "best_checkpoint": str(best_path) if best_path.exists() else None,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    print("MAPPO_MICRO_TRAIN_OK", flush=True)
    return summary


def main() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=Path("marl_agent/configs/quan4_mappo_micro.yaml")
    )
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--ippo", action="store_true")
    parser.add_argument("--max-updates", type=int, default=None)
    parser.add_argument("--n-agents", type=int, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.device:
        cfg.setdefault("experiment", {})["device"] = args.device
    if args.max_updates is not None:
        cfg.setdefault("train", {})["max_updates"] = int(args.max_updates)
    if args.n_agents is not None:
        cfg.setdefault("env", {})["n_agents"] = int(args.n_agents)
    if args.smoke:
        print("*** SMOKE MODE - not a paper run ***", flush=True)
        cfg.setdefault("train", {})["max_updates"] = 2
        cfg.setdefault("train", {})["eval_every"] = 1
        cfg.setdefault("ppo", {})["rollout_episodes"] = 4
        cfg.setdefault("ppo", {})["n_envs"] = 2
        cfg.setdefault("ppo", {})["use_subproc"] = False  # faster local smoke
        cfg.setdefault("ppo", {})["minibatch_size"] = 256
        cfg.setdefault("ppo", {})["ppo_epochs"] = 2
        cfg.setdefault("env", {})["n_agents"] = 4
        cfg.setdefault("env", {})["max_steps"] = 20
        cfg.setdefault("data", {}).setdefault("split", {})["min_path_edges"] = 3
        cfg.setdefault("data", {}).setdefault("split", {})["min_length_m"] = 100
        cfg.setdefault("early_stopping", {})["patience"] = 5
        cfg.setdefault("baseline", {})["n_episodes"] = 2
        cfg.setdefault("train", {})["eval_every"] = 1
        cfg.setdefault("bc", {})["enabled"] = True
        cfg.setdefault("bc", {})["updates"] = 2
        cfg.setdefault("bc", {})["episodes_per_update"] = 2
        cfg.setdefault("bc", {})["holdout_episodes"] = 1
        cfg.setdefault("bc", {})["epochs_per_update"] = 1
        # Short BC cannot hit production gates — smoke only checks plumbing.
        cfg.setdefault("bc", {})["target_acc"] = 0.0
        cfg.setdefault("bc", {})["min_arrival_rate"] = 0.0
        cfg.setdefault("bc", {})["max_fleet_ratio_vs_dijkstra"] = 99.0
        cfg.setdefault("bc", {})["min_closed_loop_agree"] = 0.0
        cfg.setdefault("bc", {})["fair_check_episodes"] = 2
        cfg.setdefault("bc", {})["critic_fit_episodes"] = 2
        cfg.setdefault("bc", {})["freeze_actor_updates"] = 0
        cfg.setdefault("env", {})["compact_dim"] = 160
        cfg.setdefault("experiment", {})["data_tag"] = (
            str(cfg.get("experiment", {}).get("data_tag", "mappo_micro_v1")) + "_smoke"
        )
    print(f"[mappo_micro] boot smoke={args.smoke} ippo={args.ippo}", flush=True)
    try:
        run_training(cfg, config_path=args.config, ippo=bool(args.ippo))
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
