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


def run_episode_baseline(
    env: MicroAlleyEnv,
    mode: str,
    ods_pool: list[tuple[str, str]],
    t: float,
    seed: int,
) -> dict[str, float]:
    env.set_od_pool(ods_pool)
    env.reset(seed=seed, options={"t": t})
    last = {"congestion": 0.0}
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
    travels = np.asarray(env._travel, dtype=np.float64)
    thr = float(np.quantile(travels, 0.9))
    cvar = float(np.mean(travels[travels >= thr])) if np.any(travels >= thr) else float(np.mean(travels))
    return {
        "fleet_mean": float(np.mean(travels)),
        "fleet_cvar90": cvar,
        "congestion": float(last.get("congestion", 0.0)),
    }


@torch.no_grad()
def evaluate_policy(
    env: MicroAlleyEnv,
    actor: SharedActor,
    ods_pool: list[tuple[str, str]],
    t_list: list[float],
    device: torch.device,
    n_episodes: int = 16,
) -> dict[str, float]:
    actor.eval()
    means, cvars, congs = [], [], []
    for ep in range(n_episodes):
        t = float(t_list[ep % len(t_list)])
        env.set_od_pool(ods_pool)
        obs, _, info = env.reset(seed=50_000 + ep, options={"t": t})
        last = {"congestion": 0.0}
        for _ in range(env.max_steps):
            actions = {}
            for i, a in enumerate(env.agents):
                o = torch.tensor(obs[a], dtype=torch.float32, device=device).unsqueeze(0)
                m = torch.tensor(info["masks"][a], dtype=torch.float32, device=device).unsqueeze(0)
                dist = masked_categorical(actor(o), m)
                actions[a] = int(torch.argmax(dist.logits, dim=-1).item())
            obs, _, _, _, _, step_info = env.step(actions)
            info = step_info
            last = step_info
            if step_info["all_done"]:
                break
        travels = np.asarray(env._travel, dtype=np.float64)
        thr = float(np.quantile(travels, 0.9))
        cvar = (
            float(np.mean(travels[travels >= thr]))
            if np.any(travels >= thr)
            else float(np.mean(travels))
        )
        means.append(float(np.mean(travels)))
        cvars.append(cvar)
        congs.append(float(last.get("congestion", 0.0)))
    actor.train()
    return {
        "fleet_mean": float(np.mean(means)),
        "fleet_cvar90": float(np.mean(cvars)),
        "congestion": float(np.mean(congs)),
        "n": float(n_episodes),
    }


def compute_gae(
    rewards: list[float],
    values: list[float],
    dones: list[bool],
    gamma: float,
    lam: float,
) -> tuple[list[float], list[float]]:
    """rewards/values/dones are per env-step (team)."""
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
        max_degree=int(env_cfg.get("max_degree", 6)),
        max_steps=int(env_cfg.get("max_steps", 64)),
        compact_dim=int(env_cfg.get("compact_dim", 128)),
        bpr_alpha=float(env_cfg.get("bpr_alpha", 0.15)),
        bpr_beta=float(env_cfg.get("bpr_beta", 4.0)),
        bpr_load_cap=float(env_cfg.get("bpr_load_cap", 12.0)),
        corridor_prob=float(env_cfg.get("corridor_prob", 0.4)),
        reward_weights=env_cfg.get("reward_weights"),
        density_catalog=density_catalog or None,
    )
    env.set_od_pool(train_ods)
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
    rollout_n = int(ppo_cfg.get("rollout_episodes", 64))
    ppo_epochs = int(ppo_cfg.get("ppo_epochs", 4))
    clip_eps = float(ppo_cfg.get("clip_eps", 0.2))
    value_coef = float(ppo_cfg.get("value_coef", 0.5))
    entropy_coef = float(ppo_cfg.get("entropy_coef", 0.03))
    gamma = float(ppo_cfg.get("gamma", 0.99))
    gae_lam = float(ppo_cfg.get("gae_lambda", 0.95))
    grad_clip = float(optim_cfg.get("grad_clip_norm", 1.0))
    normalize_adv = bool(ppo_cfg.get("normalize_advantage", True))

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
        f"max_updates={max_updates}",
        flush=True,
    )
    print(f"[mappo_micro] run_dir={run_dir}", flush=True)

    t0 = time.time()
    stop_reason = "max_updates"
    best_state: dict[str, Any] | None = None
    last_update = 0

    with jsonl_path.open("w", encoding="utf-8") as jf, csv_path.open(
        "w", encoding="utf-8", newline=""
    ) as cf:
        csv_w = csv.DictWriter(
            cf,
            fieldnames=["update", "mean_return", "fleet_mean", "loss", "entropy", "ep_len"],
        )
        csv_w.writeheader()

        for update in range(1, max_updates + 1):
            last_update = update
            obs_buf: list[torch.Tensor] = []
            act_buf: list[torch.Tensor] = []
            logp_buf: list[torch.Tensor] = []
            ret_buf: list[torch.Tensor] = []
            adv_buf: list[torch.Tensor] = []
            mask_buf: list[torch.Tensor] = []
            g_buf: list[torch.Tensor] = []
            ep_returns: list[float] = []
            ep_fleet: list[float] = []
            ep_lens: list[float] = []

            for ep in range(rollout_n):
                t = float(rng.choice(t_train))
                env.set_od_pool(train_ods)
                obs, gstate, info = env.reset(
                    seed=seed + update * 10000 + ep, options={"t": t}
                )
                step_obs: list[list[torch.Tensor]] = []
                step_act: list[list[torch.Tensor]] = []
                step_logp: list[list[torch.Tensor]] = []
                step_mask: list[list[torch.Tensor]] = []
                step_g: list[torch.Tensor] = []
                step_r: list[float] = []
                step_v: list[float] = []
                step_done: list[bool] = []

                for _ in range(env.max_steps):
                    g_t = torch.tensor(gstate, dtype=torch.float32, device=device)
                    if ippo:
                        # mean local value
                        vs = []
                        for a in env.agents:
                            o = torch.tensor(obs[a], dtype=torch.float32, device=device)
                            vs.append(float(critic(o.unsqueeze(0)).item()))
                        v = float(np.mean(vs))
                    else:
                        v = float(critic(g_t.unsqueeze(0)).item())

                    actions: dict[str, int] = {}
                    o_list, a_list, lp_list, m_list = [], [], [], []
                    for i, a in enumerate(env.agents):
                        o = torch.tensor(obs[a], dtype=torch.float32, device=device)
                        m = torch.tensor(info["masks"][a], dtype=torch.float32, device=device)
                        dist = masked_categorical(actor(o.unsqueeze(0)), m.unsqueeze(0))
                        action = dist.sample()
                        logp = dist.log_prob(action)
                        actions[a] = int(action.item())
                        o_list.append(o)
                        a_list.append(action.squeeze(0))
                        lp_list.append(logp.squeeze(0))
                        m_list.append(m)

                    obs, rewards, terms, _, gstate, step_info = env.step(actions)
                    info = step_info
                    r_team = float(np.mean([rewards[a] for a in env.agents]))
                    if not math.isfinite(r_team):
                        raise RuntimeError("NaN reward")
                    done_team = bool(step_info["all_done"])

                    step_obs.append(o_list)
                    step_act.append(a_list)
                    step_logp.append(lp_list)
                    step_mask.append(m_list)
                    step_g.append(g_t)
                    step_r.append(r_team)
                    step_v.append(v)
                    step_done.append(done_team)
                    if done_team:
                        break

                adv_t, ret_t = compute_gae(step_r, step_v, step_done, gamma, gae_lam)
                for ti in range(len(step_r)):
                    for i in range(n_agents):
                        obs_buf.append(step_obs[ti][i])
                        act_buf.append(step_act[ti][i])
                        logp_buf.append(step_logp[ti][i].detach())
                        mask_buf.append(step_mask[ti][i])
                        g_buf.append(step_g[ti] if not ippo else step_obs[ti][i])
                        adv_buf.append(
                            torch.tensor(adv_t[ti], dtype=torch.float32, device=device)
                        )
                        ret_buf.append(
                            torch.tensor(ret_t[ti], dtype=torch.float32, device=device)
                        )
                ep_returns.append(float(np.sum(step_r)))
                ep_fleet.append(float(np.mean(env._travel)))
                ep_lens.append(float(len(step_r)))

            advantages = torch.stack(adv_buf)
            if normalize_adv and advantages.numel() > 1:
                advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
            batch_obs = torch.stack(obs_buf)
            batch_act = torch.stack(act_buf)
            batch_logp = torch.stack(logp_buf)
            batch_ret = torch.stack(ret_buf)
            batch_mask = torch.stack(mask_buf)
            batch_g = torch.stack(g_buf)

            last_loss = 0.0
            last_ent = 0.0
            for _ in range(ppo_epochs):
                logits = actor(batch_obs)
                dist = masked_categorical(logits, batch_mask)
                logp = dist.log_prob(batch_act)
                entropy = dist.entropy().mean()
                ratio = torch.exp(logp - batch_logp)
                surr1 = ratio * advantages
                surr2 = torch.clamp(ratio, 1.0 - clip_eps, 1.0 + clip_eps) * advantages
                policy_loss = -torch.min(surr1, surr2).mean()
                values = critic(batch_g if not ippo else batch_obs)
                value_loss = F.mse_loss(values, batch_ret)
                loss = policy_loss + value_coef * value_loss - entropy_coef * entropy
                opt_actor.zero_grad()
                opt_critic.zero_grad()
                loss.backward()
                if grad_clip > 0:
                    torch.nn.utils.clip_grad_norm_(actor.parameters(), grad_clip)
                    torch.nn.utils.clip_grad_norm_(critic.parameters(), grad_clip)
                opt_actor.step()
                opt_critic.step()
                last_loss = float(loss.item())
                last_ent = float(entropy.item())

            row = {
                "update": update,
                "mean_return": float(np.mean(ep_returns)),
                "fleet_mean": float(np.mean(ep_fleet)),
                "loss": last_loss,
                "entropy": last_ent,
                "ep_len": float(np.mean(ep_lens)),
            }
            csv_w.writerow(row)
            cf.flush()
            jf.write(json.dumps({"type": "train", **row}) + "\n")
            jf.flush()
            if update % log_every == 0:
                print(
                    f"[train] {update}/{max_updates} | ret={row['mean_return']:.3f} "
                    f"fleet={row['fleet_mean']:.1f}s len={row['ep_len']:.1f} | "
                    f"loss={row['loss']:.3f} ent={row['entropy']:.4f}",
                    flush=True,
                )

            if update % eval_every == 0 or update == max_updates:
                val = evaluate_policy(env, actor, val_ods, t_eval, device, n_episodes=20)
                print(
                    f"[eval]  fleet_mean={val['fleet_mean']:.1f}s "
                    f"cvar90={val['fleet_cvar90']:.1f}s cong={val['congestion']:.3f} | "
                    f"best={early.best_metric if early.best_update >= 0 else val['fleet_mean']:.1f}",
                    flush=True,
                )
                jf.write(json.dumps({"type": "eval", "update": update, **val}) + "\n")
                jf.flush()
                if bool(es_cfg.get("enabled", True)):
                    st = early.step(val["fleet_mean"], update)
                    if st.reason == "improved" or best_state is None:
                        best_state = {
                            "actor": {k: v.detach().cpu().clone() for k, v in actor.state_dict().items()},
                            "critic": {
                                k: v.detach().cpu().clone() for k, v in critic.state_dict().items()
                            },
                            "update": update,
                            "val": val,
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
                                "val": val,
                                "cfg_tag": data_tag,
                            },
                            best_path,
                        )
                        print(f"  [ckpt] best.pt fleet_mean={val['fleet_mean']:.2f}s", flush=True)
                    if st.stopped:
                        print(f"  [early_stop] {st.reason}", flush=True)
                        stop_reason = st.reason
                        break
            if update % save_every == 0:
                torch.save(
                    {"actor": actor.state_dict(), "critic": critic.state_dict(), "update": update},
                    run_dir / f"ckpt_{update}.pt",
                )

    if bool(es_cfg.get("restore_best", True)) and best_state is not None:
        actor.load_state_dict(best_state["actor"])
        critic.load_state_dict(best_state["critic"])
        print(f"[mappo_micro] restored best @{best_state['update']}", flush=True)

    test = evaluate_policy(env, actor, test_ods, t_eval, device, n_episodes=30)
    baselines: dict[str, dict[str, float]] = {}
    if bool(cfg.get("baseline", {}).get("run_on_eval", True)):
        for mode in ("dijkstra", "random", "greedy_load"):
            ms = []
            for ep in range(30):
                ms.append(
                    run_episode_baseline(
                        env, mode, test_ods, float(t_eval[ep % len(t_eval)]), 70_000 + ep
                    )
                )
            baselines[mode] = {
                "fleet_mean": float(np.mean([m["fleet_mean"] for m in ms])),
                "fleet_cvar90": float(np.mean([m["fleet_cvar90"] for m in ms])),
                "congestion": float(np.mean([m["congestion"] for m in ms])),
            }
            print(
                f"  [base] {mode:14s} fleet={baselines[mode]['fleet_mean']:.1f}s "
                f"cvar={baselines[mode]['fleet_cvar90']:.1f}s",
                flush=True,
            )

    djk = baselines.get("dijkstra", {})
    rnd = baselines.get("random", {})
    grd = baselines.get("greedy_load", {})
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
        "best_val_fleet_mean": early.best_metric if early.best_update >= 0 else test["fleet_mean"],
        "best_update": early.best_update,
        "test_fleet_mean": test["fleet_mean"],
        "test_fleet_cvar90": test["fleet_cvar90"],
        "test_congestion": test["congestion"],
        "baselines_test": baselines,
        "beats_dijkstra_mean": bool(test["fleet_mean"] < djk["fleet_mean"]) if djk else None,
        "beats_random_mean": bool(test["fleet_mean"] < rnd["fleet_mean"]) if rnd else None,
        "beats_greedy_mean": bool(test["fleet_mean"] < grd["fleet_mean"]) if grd else None,
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
        cfg.setdefault("train", {})["max_updates"] = 3
        cfg.setdefault("train", {})["eval_every"] = 1
        cfg.setdefault("ppo", {})["rollout_episodes"] = 2
        cfg.setdefault("env", {})["n_agents"] = 4
        cfg.setdefault("env", {})["max_steps"] = 20
        cfg.setdefault("data", {}).setdefault("split", {})["min_path_edges"] = 3
        cfg.setdefault("data", {}).setdefault("split", {})["min_length_m"] = 100
        cfg.setdefault("early_stopping", {})["patience"] = 5
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
