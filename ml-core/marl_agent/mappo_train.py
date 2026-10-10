"""MAPPO trainer for multi-agent alley path choice under BPR congestion."""

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
from .mappo_env import MultiAgentPathEnv
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


def masked_categorical(logits: torch.Tensor, mask: torch.Tensor) -> torch.distributions.Categorical:
    neg = torch.finfo(logits.dtype).min
    masked = logits.masked_fill(mask < 0.5, neg)
    return torch.distributions.Categorical(logits=masked)


@torch.no_grad()
def evaluate_policy(
    env: MultiAgentPathEnv,
    actor: SharedActor,
    pairs_pool: list[tuple[str, str]],
    t_list: list[float],
    device: torch.device,
    n_episodes: int = 20,
) -> dict[str, float]:
    actor.eval()
    means, cvars, congs, ginis = [], [], [], []
    for ep in range(n_episodes):
        t = float(t_list[ep % len(t_list)])
        env.set_od_pool(pairs_pool)
        obs, _, info = env.reset(seed=10_000 + ep, options={"t": t})
        actions = {}
        for i, a in enumerate(env.agents):
            o = torch.tensor(obs[a], dtype=torch.float32, device=device).unsqueeze(0)
            mask = torch.tensor(info["masks"][a], dtype=torch.float32, device=device).unsqueeze(0)
            logits = actor(o)
            dist = masked_categorical(logits, mask)
            actions[a] = int(torch.argmax(dist.logits, dim=-1).item())
        _, _, _, _, _, step_info = env.step(actions)
        means.append(step_info["fleet_mean"])
        cvars.append(step_info["fleet_cvar90"])
        congs.append(step_info["congestion"])
        ginis.append(step_info["fairness_gini"])
    actor.train()
    return {
        "fleet_mean": float(np.mean(means)),
        "fleet_cvar90": float(np.mean(cvars)),
        "congestion": float(np.mean(congs)),
        "fairness_gini": float(np.mean(ginis)),
        "n": float(n_episodes),
    }


def evaluate_baseline(
    env: MultiAgentPathEnv,
    pairs_pool: list[tuple[str, str]],
    t_list: list[float],
    mode: str,
    n_episodes: int = 20,
) -> dict[str, float]:
    means, cvars, congs = [], [], []
    for ep in range(n_episodes):
        t = float(t_list[ep % len(t_list)])
        env.set_od_pool(pairs_pool)
        env.reset(seed=20_000 + ep, options={"t": t})
        if mode == "all_dijkstra":
            acts = env.baseline_all_dijkstra()
        elif mode == "random":
            acts = env.baseline_random()
        elif mode == "greedy_load":
            acts = env.baseline_greedy_load()
        else:
            raise ValueError(mode)
        _, _, _, _, _, info = env.step(acts)
        means.append(info["fleet_mean"])
        cvars.append(info["fleet_cvar90"])
        congs.append(info["congestion"])
    return {
        "fleet_mean": float(np.mean(means)),
        "fleet_cvar90": float(np.mean(cvars)),
        "congestion": float(np.mean(congs)),
        "n": float(n_episodes),
    }


def run_training(cfg: dict[str, Any], config_path: Path | None = None, ippo: bool = False) -> dict[str, Any]:
    base = _repo_ml_core()
    seed = int(cfg.get("experiment", {}).get("seed", 42))
    set_seeds(seed)
    device = pick_device(str(cfg.get("experiment", {}).get("device", "auto")))

    data_cfg = cfg["data"]
    graph = _resolve(data_cfg["graph"], base, must_exist=True)
    density = _resolve(data_cfg["density"], base, must_exist=True)
    seeds = _resolve(data_cfg["seeds"], base, must_exist=True)
    density_catalog = _load_density_catalog(data_cfg, base)
    for p, name in ((graph, "graph"), (density, "density"), (seeds, "seeds")):
        if not p.exists():
            raise FileNotFoundError(f"Missing {name}: {p}")
    if data_cfg.get("require_l1_catalog") and len(density_catalog) < 2:
        raise FileNotFoundError("Need density_by_peak (>=2)")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    exp_name = cfg.get("experiment", {}).get("name", "quan4_mappo")
    data_tag = str(cfg.get("experiment", {}).get("data_tag", "mappo_v1"))
    if ippo and not data_tag.endswith("_ippo"):
        data_tag = data_tag + "_ippo"
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
        seeds,
        require_path=bool(split_cfg.get("require_path", True)),
        min_path_edges=int(split_cfg.get("min_path_edges", 2)),
        max_pairs=400,
    )
    split = split_od_pairs(
        pool,
        train_ratio=float(split_cfg.get("train_ratio", 0.7)),
        val_ratio=float(split_cfg.get("val_ratio", 0.15)),
        test_ratio=float(split_cfg.get("test_ratio", 0.15)),
        seed=seed,
    )
    save_split(split, run_dir / "od_split.json")
    train_ods = [(p.origin, p.destination) for p in split["train"]]
    val_ods = [(p.origin, p.destination) for p in split["val"]]
    test_ods = [(p.origin, p.destination) for p in split["test"]]

    env_cfg = cfg.get("env", {})
    n_agents = int(env_cfg.get("n_agents", 16))
    k_paths = int(env_cfg.get("k_paths", 8))
    env = MultiAgentPathEnv(
        density_path=density,
        graph_path=graph,
        seed=seed,
        n_agents=n_agents,
        k_paths=k_paths,
        compact_dim=int(env_cfg.get("compact_dim", 96)),
        bpr_alpha=float(env_cfg.get("bpr_alpha", 0.15)),
        bpr_beta=float(env_cfg.get("bpr_beta", 4.0)),
        corridor_prob=float(env_cfg.get("corridor_prob", 0.5)),
        reward_weights=env_cfg.get("reward_weights"),
        density_catalog=density_catalog or None,
    )
    env.set_od_pool(train_ods)
    # probe dims
    obs0, g0, _ = env.reset(options={"t": 28800.0})
    obs_dim = int(obs0[env.agents[0]].shape[0])
    global_dim = int(g0.shape[0])

    model_cfg = cfg.get("model", {})
    hidden = int(model_cfg.get("hidden", 128))
    actor = SharedActor(obs_dim, k_paths, hidden=hidden).to(device)
    if ippo:
        critic: nn.Module = IndependentCritic(obs_dim, hidden=hidden).to(device)
    else:
        critic = CentralCritic(global_dim, hidden=hidden).to(device)

    optim_cfg = cfg.get("optim", {})
    ppo_cfg = cfg.get("ppo", {})
    lr_actor = float(optim_cfg.get("lr_actor", 3e-4))
    lr_critic = float(optim_cfg.get("lr_critic", 1e-3))
    entropy_coef = float(ppo_cfg.get("entropy_coef", 0.05))
    clip_eps = float(ppo_cfg.get("clip_eps", 0.2))
    value_coef = float(ppo_cfg.get("value_coef", 0.5))
    opt_actor = torch.optim.Adam(
        actor.parameters(), lr=lr_actor, weight_decay=float(optim_cfg.get("weight_decay", 1e-5))
    )
    opt_critic = torch.optim.Adam(
        critic.parameters(), lr=lr_critic, weight_decay=float(optim_cfg.get("weight_decay", 1e-5))
    )

    train_cfg = cfg.get("train", {})
    max_updates = int(train_cfg.get("max_updates", 2000))
    eval_every = int(train_cfg.get("eval_every", 20))
    log_every = int(train_cfg.get("log_every", 1))
    save_every = int(train_cfg.get("save_every", 50))
    rollout_n = int(ppo_cfg.get("rollout_episodes", 128))
    ppo_epochs = int(ppo_cfg.get("ppo_epochs", 4))
    grad_clip = float(optim_cfg.get("grad_clip_norm", 1.0))
    normalize_adv = bool(ppo_cfg.get("normalize_advantage", True))

    t_train = [float(x) for x in data_cfg.get("t_train", [28800])]
    t_eval = [float(x) for x in data_cfg.get("t_eval", [28800])]

    es_cfg = cfg.get("early_stopping", {})
    early = EarlyStopping(
        patience=int(es_cfg.get("patience", 25)),
        min_delta=float(es_cfg.get("min_delta", 0.5)),
        mode="min",
    )

    rng = np.random.default_rng(seed)
    jsonl_path = run_dir / "metrics.jsonl"
    csv_path = run_dir / "metrics.csv"
    best_path = run_dir / "best.pt"

    algo = "IPPO" if ippo else "MAPPO"
    print(
        f"[mappo_train] mode=FULL algo={algo} data_tag={data_tag} device={device} "
        f"N={n_agents} K={k_paths} obs={obs_dim} global={global_dim} "
        f"max_updates={max_updates} rollouts={rollout_n}",
        flush=True,
    )
    print(f"[mappo_train] run_dir={run_dir}", flush=True)

    t0 = time.time()
    stop_reason = "max_updates"
    best_state: dict[str, Any] | None = None
    last_update = 0

    with jsonl_path.open("w", encoding="utf-8") as jf, csv_path.open(
        "w", encoding="utf-8", newline=""
    ) as cf:
        csv_w = csv.DictWriter(
            cf,
            fieldnames=[
                "update",
                "mean_return",
                "fleet_mean",
                "congestion",
                "loss",
                "entropy",
                "lr_actor",
            ],
        )
        csv_w.writeheader()

        for update in range(1, max_updates + 1):
            last_update = update
            obs_buf: list[torch.Tensor] = []
            act_buf: list[torch.Tensor] = []
            logp_buf: list[torch.Tensor] = []
            ret_buf: list[torch.Tensor] = []
            adv_buf: list[torch.Tensor] = []
            g_buf: list[torch.Tensor] = []
            mask_buf: list[torch.Tensor] = []
            ep_returns: list[float] = []
            ep_fleet: list[float] = []
            ep_cong: list[float] = []

            actor.train()
            critic.train()
            for ep in range(rollout_n):
                t = float(rng.choice(t_train))
                env.set_od_pool(train_ods)
                obs, gstate, info = env.reset(
                    seed=seed + update * 10_000 + ep, options={"t": t}
                )
                g_t = torch.tensor(gstate, dtype=torch.float32, device=device)
                if ippo:
                    # value from mean local later; store placeholder
                    value = torch.zeros((), device=device)
                else:
                    value = critic(g_t.unsqueeze(0)).squeeze(0)

                actions: dict[str, int] = {}
                ep_logps = []
                ep_obs = []
                ep_masks = []
                ep_acts = []
                local_values = []
                for a in env.agents:
                    o = torch.tensor(obs[a], dtype=torch.float32, device=device)
                    m = torch.tensor(info["masks"][a], dtype=torch.float32, device=device)
                    logits = actor(o.unsqueeze(0)).squeeze(0)
                    dist = masked_categorical(logits.unsqueeze(0), m.unsqueeze(0))
                    action = dist.sample()
                    logp = dist.log_prob(action)
                    actions[a] = int(action.item())
                    ep_logps.append(logp.squeeze(0))
                    ep_obs.append(o)
                    ep_masks.append(m)
                    ep_acts.append(action.squeeze(0))
                    if ippo:
                        local_values.append(critic(o.unsqueeze(0)).squeeze(0))

                _, rewards, _, _, _, step_info = env.step(actions)
                # team reward for CTDE: mean agent return (cooperative MAPPO)
                r_team = float(np.mean([rewards[a] for a in env.agents]))
                if cfg.get("risk", {}).get("nan_guard", True) and not math.isfinite(r_team):
                    raise RuntimeError("NaN reward")

                if ippo:
                    # each agent uses own reward + local value
                    for i, a in enumerate(env.agents):
                        r_i = float(rewards[a])
                        v_i = local_values[i]
                        adv_i = torch.tensor(r_i, device=device) - v_i.detach()
                        obs_buf.append(ep_obs[i])
                        act_buf.append(ep_acts[i])
                        logp_buf.append(ep_logps[i].detach())
                        ret_buf.append(torch.tensor(r_i, dtype=torch.float32, device=device))
                        adv_buf.append(adv_i)
                        mask_buf.append(ep_masks[i])
                        g_buf.append(ep_obs[i])  # unused for central
                else:
                    adv = torch.tensor(r_team, device=device) - value.detach()
                    for i in range(n_agents):
                        obs_buf.append(ep_obs[i])
                        act_buf.append(ep_acts[i])
                        logp_buf.append(ep_logps[i].detach())
                        ret_buf.append(torch.tensor(r_team, dtype=torch.float32, device=device))
                        adv_buf.append(adv)
                        mask_buf.append(ep_masks[i])
                        g_buf.append(g_t)

                ep_returns.append(r_team)
                ep_fleet.append(float(step_info["fleet_mean"]))
                ep_cong.append(float(step_info["congestion"]))

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

                if ippo:
                    values = critic(batch_obs)
                else:
                    # critic sees repeated global states
                    values = critic(batch_g)
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
                "congestion": float(np.mean(ep_cong)),
                "loss": last_loss,
                "entropy": last_ent,
                "lr_actor": lr_actor,
            }
            csv_w.writerow(row)
            cf.flush()
            jf.write(json.dumps({"type": "train", **row}) + "\n")
            jf.flush()

            if update % log_every == 0:
                print(
                    f"[train] {update}/{max_updates} | ret={row['mean_return']:.3f} "
                    f"fleet={row['fleet_mean']:.1f}s cong={row['congestion']:.3f} | "
                    f"loss={row['loss']:.3f} ent={row['entropy']:.4f}",
                    flush=True,
                )

            if update % eval_every == 0 or update == max_updates:
                val = evaluate_policy(env, actor, val_ods, t_eval, device, n_episodes=24)
                erow = {"type": "eval", "update": update, **{f"val_{k}": v for k, v in val.items()}}
                jf.write(json.dumps(erow) + "\n")
                jf.flush()
                print(
                    f"[eval]  fleet_mean={val['fleet_mean']:.1f}s cvar90={val['fleet_cvar90']:.1f}s "
                    f"cong={val['congestion']:.3f} gini={val['fairness_gini']:.3f} | "
                    f"best={early.best_metric if early.best_update >= 0 else val['fleet_mean']:.1f}",
                    flush=True,
                )
                if bool(es_cfg.get("enabled", True)):
                    st = early.step(val["fleet_mean"], update)
                    if st.reason == "improved" or best_state is None:
                        best_state = {
                            "actor": {k: v.detach().cpu().clone() for k, v in actor.state_dict().items()},
                            "critic": {k: v.detach().cpu().clone() for k, v in critic.state_dict().items()},
                            "update": update,
                            "val": val,
                        }
                        torch.save(
                            {
                                "actor": actor.state_dict(),
                                "critic": critic.state_dict(),
                                "obs_dim": obs_dim,
                                "global_dim": global_dim,
                                "n_actions": k_paths,
                                "n_agents": n_agents,
                                "ippo": ippo,
                                "update": update,
                                "val": val,
                                "cfg_tag": data_tag,
                            },
                            best_path,
                        )
                        print(
                            f"  [ckpt] best.pt fleet_mean={val['fleet_mean']:.2f}s",
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

    if bool(es_cfg.get("restore_best", True)) and best_state is not None:
        actor.load_state_dict(best_state["actor"])
        critic.load_state_dict(best_state["critic"])
        print(f"[mappo_train] restored best from update {best_state['update']}", flush=True)

    test = evaluate_policy(env, actor, test_ods, t_eval, device, n_episodes=40)
    baselines: dict[str, dict[str, float]] = {}
    if bool(cfg.get("baseline", {}).get("run_on_eval", True)):
        for mode in ("all_dijkstra", "random", "greedy_load"):
            baselines[mode] = evaluate_baseline(env, test_ods, t_eval, mode, n_episodes=40)
            print(
                f"  [base] {mode:16s} fleet={baselines[mode]['fleet_mean']:.1f}s "
                f"cvar={baselines[mode]['fleet_cvar90']:.1f}s cong={baselines[mode]['congestion']:.3f}",
                flush=True,
            )

    djk = baselines.get("all_dijkstra", {})
    summary = {
        "algo": algo,
        "data_tag": data_tag,
        "seed": seed,
        "device": str(device),
        "n_agents": n_agents,
        "k_paths": k_paths,
        "ippo": ippo,
        "updates_ran": int(last_update),
        "stop_reason": stop_reason,
        "best_val_fleet_mean": early.best_metric if early.best_update >= 0 else test["fleet_mean"],
        "best_update": early.best_update,
        "test_fleet_mean": test["fleet_mean"],
        "test_fleet_cvar90": test["fleet_cvar90"],
        "test_congestion": test["congestion"],
        "test_fairness_gini": test["fairness_gini"],
        "baselines_test": baselines,
        "beats_dijkstra_mean": (
            bool(test["fleet_mean"] < djk["fleet_mean"]) if djk else None
        ),
        "beats_dijkstra_cvar": (
            bool(test["fleet_cvar90"] < djk["fleet_cvar90"]) if djk else None
        ),
        "beats_dijkstra_cong": (
            bool(test["congestion"] < djk["congestion"]) if djk else None
        ),
        "elapsed_sec": time.time() - t0,
        "run_dir": str(run_dir),
        "best_checkpoint": str(best_path) if best_path.exists() else None,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    print("MAPPO_TRAIN_OK", flush=True)
    return summary


def main() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="MAPPO multi-agent alley train")
    parser.add_argument("--config", type=Path, default=Path("marl_agent/configs/quan4_mappo.yaml"))
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--ippo", action="store_true", help="Ablation: independent critic")
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
        cfg.setdefault("train", {})["max_updates"] = 4
        cfg.setdefault("train", {})["eval_every"] = 2
        cfg.setdefault("ppo", {})["rollout_episodes"] = 4
        cfg.setdefault("env", {})["n_agents"] = min(4, int(cfg.get("env", {}).get("n_agents", 16)))
        cfg.setdefault("early_stopping", {})["patience"] = 3
        cfg.setdefault("baseline", {})["run_on_eval"] = True
        cfg.setdefault("experiment", {})["data_tag"] = (
            str(cfg.get("experiment", {}).get("data_tag", "mappo_v1")) + "_smoke"
        )

    print(
        f"[mappo_train] boot config={args.config} smoke={args.smoke} ippo={args.ippo}",
        flush=True,
    )
    try:
        run_training(cfg, config_path=args.config, ippo=bool(args.ippo))
    except Exception:
        import traceback

        print("FATAL mappo_train:", flush=True)
        traceback.print_exc()
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
