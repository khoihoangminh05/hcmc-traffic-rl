"""Professor-grade MARL trainer for Quận 4 alley routing.

Features:
- YAML hyperparams frozen per run
- Train/val/test OD split
- Compact obs (safe on large graphs)
- PPO clip + entropy + grad clip + adv normalize
- Eval block metrics every N updates
- Early stopping on val_travel_time
- Validation-driven LR/entropy adaptation + interpolate-to-best
- JSONL/CSV + summary.json logs (server-friendly, no HTML)
"""

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
import torch.nn.functional as F
import yaml

from .adapt import HyperParams, ValHyperAdapter
from .early_stop import EarlyStopping
from .env import AlleyRoutingEnv
from .gnn import ActorCritic
from .od_split import ODPair, build_connected_od_pool, save_split, split_od_pairs


def _repo_ml_core() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve(path: Path | str, base: Path, *, must_exist: bool = True) -> Path:
    """Resolve relative to ml-core first, then repo root."""
    p = Path(path)
    if p.is_absolute():
        return p
    cand = (base / p).resolve()
    if not must_exist or cand.exists():
        return cand
    alt = (base.parent / p).resolve()
    return alt


def _load_density_catalog(data_cfg: dict[str, Any], base: Path) -> dict[str, Path]:
    """L1: morning/evening density paths from yaml or density_l1_index.json."""
    catalog: dict[str, Path] = {}
    by_peak = data_cfg.get("density_by_peak") or {}
    for name, rel in by_peak.items():
        if not rel:
            continue
        p = _resolve(rel, base, must_exist=False)
        if p.exists():
            catalog[str(name)] = p
    index_rel = data_cfg.get("density_l1_index")
    if index_rel and len(catalog) < 2:
        index_path = _resolve(index_rel, base, must_exist=False)
        if index_path.exists():
            idx = json.loads(index_path.read_text(encoding="utf-8"))
            for name, meta in (idx.get("peaks") or {}).items():
                if name in catalog:
                    continue
                p = meta.get("path") if isinstance(meta, dict) else None
                if p and Path(p).exists():
                    catalog[str(name)] = Path(p)
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


def sample_od(pairs: list[ODPair], rng: np.random.Generator) -> ODPair:
    return pairs[int(rng.integers(0, len(pairs)))]


@torch.no_grad()
def evaluate(
    env: AlleyRoutingEnv,
    model: ActorCritic,
    pairs: list[ODPair],
    t_list: list[float],
    device: torch.device,
) -> dict[str, float]:
    if not pairs:
        return {
            "travel_time": float("nan"),
            "oracle": float("nan"),
            "regret": float("nan"),
            "action_acc": float("nan"),
            "n": 0.0,
        }
    travels: list[float] = []
    oracles: list[float] = []
    acc = 0
    n = 0
    model.eval()
    agent = env.agents[0]
    for p in pairs:
        for t in t_list:
            obs, _ = env.reset(
                options={"origin": p.origin, "destination": p.destination, "t": float(t)}
            )
            o = torch.tensor(obs[agent], dtype=torch.float32, device=device).unsqueeze(0)
            logits, _ = model(o)
            action = int(torch.argmax(logits, dim=-1).item())
            _, rewards, _, _, infos = env.step({agent: action})
            tt = float(infos[agent]["travel_time"])
            ora = env.oracle_travel_time(float(t), p.origin, p.destination)
            travels.append(tt)
            oracles.append(ora["travel_oracle"])
            if action == int(ora["oracle_action"]):
                acc += 1
            n += 1
    model.train()
    mean_tt = float(np.mean(travels))
    mean_ora = float(np.mean(oracles))
    return {
        "travel_time": mean_tt,
        "oracle": mean_ora,
        "regret": mean_tt - mean_ora,
        "action_acc": acc / max(n, 1),
        "n": float(n),
    }


def ppo_update(
    model: ActorCritic,
    optim: torch.optim.Optimizer,
    batch: dict[str, torch.Tensor],
    hparams: HyperParams,
    ppo_epochs: int,
    grad_clip: float,
    normalize_adv: bool,
) -> dict[str, float]:
    obs = batch["obs"]
    actions = batch["actions"]
    old_logp = batch["logp"]
    returns = batch["returns"]
    advantages = batch["advantages"]
    if normalize_adv and advantages.numel() > 1:
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

    metrics = {"loss": 0.0, "policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}
    n_steps = 0
    for _ in range(ppo_epochs):
        logits, values = model(obs)
        dist = torch.distributions.Categorical(logits=logits)
        logp = dist.log_prob(actions)
        entropy = dist.entropy().mean()
        ratio = torch.exp(logp - old_logp)
        unclipped = ratio * advantages
        clipped = torch.clamp(ratio, 1.0 - hparams.clip_eps, 1.0 + hparams.clip_eps) * advantages
        policy_loss = -torch.min(unclipped, clipped).mean()
        value_loss = F.mse_loss(values, returns)
        loss = policy_loss + hparams.value_coef * value_loss - hparams.entropy_coef * entropy
        if not torch.isfinite(loss):
            raise RuntimeError("Non-finite loss — abort to avoid training garbage weights")
        optim.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optim.step()
        metrics["loss"] += float(loss.item())
        metrics["policy_loss"] += float(policy_loss.item())
        metrics["value_loss"] += float(value_loss.item())
        metrics["entropy"] += float(entropy.item())
        n_steps += 1
    for k in metrics:
        metrics[k] /= max(n_steps, 1)
    return metrics


def run_training(cfg: dict[str, Any], config_path: Path | None = None) -> dict[str, Any]:
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
        raise FileNotFoundError(
            "L1 requires density_by_peak morning+evening (or density_l1_index). "
            "Run: python -m data_fusion.run_quan4_density --l1-peaks --mapbox <csv>"
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    exp_name = cfg.get("experiment", {}).get("name", "quan4_marl")
    data_tag = str(cfg.get("experiment", {}).get("data_tag", "v0"))
    out_root = _resolve(
        cfg.get("experiment", {}).get("output_root", "artifacts/out/quan4/marl_runs"),
        base,
        must_exist=False,
    )
    run_dir = out_root / f"{exp_name}_{data_tag}_{stamp}_seed{seed}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Freeze hyperparams
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
    if not split["train"] or not split["val"]:
        raise RuntimeError("OD split empty — check seeds/graph connectivity")

    env_cfg = cfg.get("env", {})
    obs_mode = str(env_cfg.get("obs_mode", "compact"))
    env = AlleyRoutingEnv(
        density_path=density,
        graph_path=graph,
        n_agents=int(env_cfg.get("n_agents", 1)),
        seed=seed,
        obs_mode=obs_mode,
        compact_dim=int(env_cfg.get("compact_dim", 64)),
        density_catalog=density_catalog or None,
    )
    obs_dim = env.obs_dim()
    max_obs = int(cfg.get("risk", {}).get("max_obs_dim", 512))
    if obs_dim > max_obs:
        raise RuntimeError(
            f"obs_dim={obs_dim} > max_obs_dim={max_obs}. "
            f"Use env.obs_mode=compact (not full) for Quận 4."
        )

    model_cfg = cfg.get("model", {})
    model = ActorCritic(
        obs_dim,
        n_actions=int(model_cfg.get("n_actions", 2)),
        hidden=int(model_cfg.get("hidden", 128)),
    ).to(device)

    optim_cfg = cfg.get("optim", {})
    ppo_cfg = cfg.get("ppo", {})
    hparams = HyperParams(
        lr=float(optim_cfg.get("lr", 3e-4)),
        entropy_coef=float(ppo_cfg.get("entropy_coef", 0.02)),
        clip_eps=float(ppo_cfg.get("clip_eps", 0.2)),
        value_coef=float(ppo_cfg.get("value_coef", 0.5)),
    )
    optim = torch.optim.Adam(
        model.parameters(),
        lr=hparams.lr,
        weight_decay=float(optim_cfg.get("weight_decay", 1e-5)),
    )

    train_cfg = cfg.get("train", {})
    max_updates = int(train_cfg.get("max_updates", 200))
    eval_every = int(train_cfg.get("eval_every", 5))
    log_every = int(train_cfg.get("log_every", 1))
    save_every = int(train_cfg.get("save_every", 10))
    rollout_n = int(ppo_cfg.get("rollout_episodes", 32))
    ppo_epochs = int(ppo_cfg.get("ppo_epochs", 4))
    grad_clip = float(optim_cfg.get("grad_clip_norm", 1.0))
    normalize_adv = bool(ppo_cfg.get("normalize_advantage", True))

    es_cfg = cfg.get("early_stopping", {})
    early = EarlyStopping(
        patience=int(es_cfg.get("patience", 12)),
        min_delta=float(es_cfg.get("min_delta", 0.5)),
        mode=str(es_cfg.get("mode", "min")),
    )
    adapt_cfg = cfg.get("adapt", {})
    adapter = None
    if adapt_cfg.get("enabled", True):
        adapter = ValHyperAdapter(
            initial=hparams,
            lr_min=float(optim_cfg.get("lr_min", 1e-5)),
            entropy_min=float(ppo_cfg.get("entropy_coef_min", 1e-3)),
            plateau_evals=int(adapt_cfg.get("plateau_evals", 3)),
            lr_decay=float(adapt_cfg.get("lr_decay", 0.5)),
            entropy_decay=float(adapt_cfg.get("entropy_decay", 0.7)),
            improve_entropy_boost=float(adapt_cfg.get("improve_entropy_boost", 1.15)),
            interpolate_with_best=bool(adapt_cfg.get("interpolate_with_best", True)),
            interpolate_alpha=float(adapt_cfg.get("interpolate_alpha", 0.35)),
            mode="min",
        )

    t_train = [float(x) for x in data_cfg.get("t_train", [28800])]
    t_eval = [float(x) for x in data_cfg.get("t_eval", [28800])]
    rng = np.random.default_rng(seed)

    train_history: list[dict[str, Any]] = []
    eval_history: list[dict[str, Any]] = []
    adapt_history: list[dict[str, Any]] = []
    jsonl_path = run_dir / "metrics.jsonl"
    csv_path = run_dir / "metrics_train.csv"
    best_ckpt = run_dir / "best.pt"
    last_ckpt = run_dir / "last.pt"

    meta = {
        "run_dir": str(run_dir),
        "data_tag": data_tag,
        "device": str(device),
        "obs_dim": obs_dim,
        "obs_mode": obs_mode,
        "n_train_od": len(split["train"]),
        "n_val_od": len(split["val"]),
        "n_test_od": len(split["test"]),
        "density": str(density),
        "density_catalog": {k: str(v) for k, v in density_catalog.items()},
        "graph": str(graph),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Camera not primary for alley k (cannot see into alleys); Mapbox seeds + graph interpolation.",
    }
    (run_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(
        f"[robust_train] data_tag={data_tag} device={device} obs_mode={obs_mode} "
        f"obs_dim={obs_dim} train_od={len(split['train'])} val_od={len(split['val'])} "
        f"test_od={len(split['test'])}",
        flush=True,
    )
    if density_catalog:
        print(
            f"[robust_train] L1 density_catalog={ {k: str(v) for k, v in density_catalog.items()} }",
            flush=True,
        )
    print(f"[robust_train] run_dir={run_dir}", flush=True)
    print("[robust_train] look at logs: [train] / [eval] / [adapt] → summary.json", flush=True)

    agent = env.agents[0]
    stop_reason = "max_updates"
    t0 = time.time()

    with jsonl_path.open("w", encoding="utf-8") as jsonl_f, csv_path.open(
        "w", encoding="utf-8", newline=""
    ) as csv_f:
        csv_w = csv.DictWriter(
            csv_f,
            fieldnames=[
                "update",
                "mean_return",
                "mean_travel",
                "loss",
                "policy_loss",
                "value_loss",
                "entropy",
                "lr",
                "entropy_coef",
            ],
        )
        csv_w.writeheader()

        for update in range(1, max_updates + 1):
            # --- collect rollout ---
            obs_list: list[torch.Tensor] = []
            act_list: list[torch.Tensor] = []
            logp_list: list[torch.Tensor] = []
            ret_list: list[torch.Tensor] = []
            adv_list: list[torch.Tensor] = []
            ep_returns: list[float] = []
            ep_travels: list[float] = []

            model.train()
            for ep in range(rollout_n):
                od = sample_od(split["train"], rng)
                t = float(rng.choice(t_train))
                obs_dict, _ = env.reset(
                    seed=seed + update * 1000 + ep,
                    options={"origin": od.origin, "destination": od.destination, "t": t},
                )
                o = torch.tensor(obs_dict[agent], dtype=torch.float32, device=device)
                logits, value = model(o.unsqueeze(0))
                dist = torch.distributions.Categorical(logits=logits)
                action = dist.sample()
                logp = dist.log_prob(action)
                _, rewards, _, _, infos = env.step({agent: int(action.item())})
                r_raw = float(rewards[agent])
                tt = float(infos[agent]["travel_time"])
                if cfg.get("risk", {}).get("fail_on_infinite_travel", True) and tt >= 1e6:
                    raise RuntimeError(f"Infinite travel on OD {od.od_id}")
                if cfg.get("risk", {}).get("nan_guard", True) and (
                    not math.isfinite(r_raw) or not torch.isfinite(logp)
                ):
                    raise RuntimeError("NaN/Inf in rollout")
                # Scale reward for stable value loss (log metrics use raw seconds)
                r = r_raw / 100.0
                ret = torch.tensor([r], dtype=torch.float32, device=device)
                adv = ret - value.detach()
                ep_returns.append(r_raw)
                ep_travels.append(tt)
                obs_list.append(o)
                act_list.append(action.detach().reshape(()))
                logp_list.append(logp.detach().reshape(()))
                ret_list.append(ret.reshape(()))
                adv_list.append(adv.reshape(()))

            batch = {
                "obs": torch.stack(obs_list, dim=0),
                "actions": torch.stack(act_list, dim=0),
                "logp": torch.stack(logp_list, dim=0),
                "returns": torch.stack(ret_list, dim=0),
                "advantages": torch.stack(adv_list, dim=0),
            }
            # sync optim lr with adapter
            for pg in optim.param_groups:
                pg["lr"] = hparams.lr

            umetrics = ppo_update(
                model,
                optim,
                batch,
                hparams,
                ppo_epochs=ppo_epochs,
                grad_clip=grad_clip,
                normalize_adv=normalize_adv,
            )

            row = {
                "block": "train",
                "update": update,
                "mean_return": float(np.mean(ep_returns)),
                "mean_travel": float(np.mean(ep_travels)),
                "lr": hparams.lr,
                "entropy_coef": hparams.entropy_coef,
                **umetrics,
            }
            train_history.append(row)
            if update % log_every == 0:
                jsonl_f.write(json.dumps(row) + "\n")
                jsonl_f.flush()
                csv_w.writerow({k: row.get(k, "") for k in csv_w.fieldnames})
                csv_f.flush()
                print(
                    f"[train] {update}/{max_updates} | "
                    f"return={row['mean_return']:.1f} travel={row['mean_travel']:.1f}s | "
                    f"loss={row['loss']:.3f} | lr={hparams.lr:.2e} ent={hparams.entropy_coef:.4f}"
                )

            if update % save_every == 0 or update == max_updates:
                torch.save(
                    {
                        "model": model.state_dict(),
                        "obs_dim": obs_dim,
                        "obs_mode": obs_mode,
                        "update": update,
                        "hparams": hparams.as_dict(),
                    },
                    last_ckpt,
                )

            # --- eval block ---
            if update % eval_every == 0 or update == max_updates:
                val = evaluate(env, model, split["val"], t_eval, device)
                erow = {
                    "block": "eval",
                    "update": update,
                    "val_travel_time": val["travel_time"],
                    "val_oracle": val["oracle"],
                    "val_regret": val["regret"],
                    "val_action_acc": val["action_acc"],
                    "val_n": val["n"],
                    "lr": hparams.lr,
                    "entropy_coef": hparams.entropy_coef,
                }
                eval_history.append(erow)
                jsonl_f.write(json.dumps(erow) + "\n")
                jsonl_f.flush()
                print(
                    f"[eval]  val_travel={val['travel_time']:.1f}s | "
                    f"oracle={val['oracle']:.1f}s | regret={val['regret']:.1f}s | "
                    f"acc={val['action_acc']:.0%} | best={early.best_metric:.1f}s"
                )

                # early stop
                if es_cfg.get("enabled", True):
                    st = early.step(val["travel_time"], update)
                    erow["early_stop"] = st.reason
                    if st.reason == "improved" or st.best_update == update:
                        torch.save(
                            {
                                "model": model.state_dict(),
                                "obs_dim": obs_dim,
                                "obs_mode": obs_mode,
                                "update": update,
                                "val_travel_time": val["travel_time"],
                                "hparams": hparams.as_dict(),
                            },
                            best_ckpt,
                        )
                        print(f"  [ckpt] best.pt val_travel={val['travel_time']:.2f}s")
                    if st.stopped:
                        stop_reason = st.reason
                        print(f"  [early_stop] {st.reason}")
                        break

                # adapt hparams from val
                if adapter is not None:
                    arec = adapter.step(val["travel_time"], update)
                    adapt_history.append(arec)
                    hparams = adapter.current
                    jsonl_f.write(json.dumps({"block": "adapt", **arec}) + "\n")
                    jsonl_f.flush()
                    if arec["event"] != "hold" and arec["event"] != "improve":
                        print(
                            f"  [adapt] {arec['event']} -> lr={hparams.lr:.2e} "
                            f"ent={hparams.entropy_coef:.4f}"
                        )

    # Restore best
    if es_cfg.get("restore_best", True) and best_ckpt.exists():
        try:
            state = torch.load(best_ckpt, map_location=device, weights_only=False)
        except TypeError:
            state = torch.load(best_ckpt, map_location=device)
        model.load_state_dict(state["model"])
        print(f"[robust_train] restored best.pt from update {state.get('update')}")

    test = evaluate(env, model, split["test"], t_eval, device)
    summary = {
        "data_tag": data_tag,
        "seed": seed,
        "device": str(device),
        "obs_mode": obs_mode,
        "obs_dim": obs_dim,
        "updates_ran": len(train_history),
        "stop_reason": stop_reason,
        "best_val_travel_time": early.best_metric if es_cfg.get("enabled", True) else test["travel_time"],
        "best_update": early.best_update,
        "test_travel_time": test["travel_time"],
        "test_oracle_travel_time": test["oracle"],
        "test_regret": test["regret"],
        "test_action_acc": test["action_acc"],
        "elapsed_sec": time.time() - t0,
        "run_dir": str(run_dir),
        "best_checkpoint": str(best_ckpt) if best_ckpt.exists() else str(last_ckpt),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_dir / "adapt_history.json").write_text(
        json.dumps(adapt_history, indent=2), encoding="utf-8"
    )

    # Convenience copies for twin pipeline
    twin_dir = base / "artifacts/out/quan4/marl"
    twin_dir.mkdir(parents=True, exist_ok=True)
    src_ckpt = best_ckpt if best_ckpt.exists() else last_ckpt
    if src_ckpt.exists():
        shutil.copy2(src_ckpt, twin_dir / "ppo_alley.pt")
        shutil.copy2(src_ckpt, twin_dir / "best_robust.pt")
    shutil.copy2(run_dir / "summary.json", twin_dir / "robust_summary.json")

    print(json.dumps(summary, indent=2))
    print("ROBUST_TRAIN_OK")
    return summary


def main() -> None:
    # Unbuffered-friendly for tmux/tee
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Robust Quận 4 MARL trainer")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parent / "configs" / "quan4_h100.yaml",
    )
    parser.add_argument("--max-updates", type=int, default=None, help="Override train.max_updates")
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--smoke", action="store_true", help="Tiny run for CI/local check")
    args = parser.parse_args()

    print(
        f"[robust_train] boot config={args.config} smoke={args.smoke} "
        f"device_arg={args.device} cwd={Path.cwd()}",
        flush=True,
    )

    cfg = load_config(args.config)
    if args.smoke:
        cfg.setdefault("train", {})
        cfg["train"]["max_updates"] = 6
        cfg["train"]["eval_every"] = 2
        cfg.setdefault("ppo", {})
        cfg["ppo"]["rollout_episodes"] = 8
        cfg["ppo"]["ppo_epochs"] = 2
        cfg.setdefault("early_stopping", {})
        cfg["early_stopping"]["patience"] = 3
        cfg.setdefault("experiment", {})
        cfg["experiment"]["name"] = "quan4_marl_smoke"
        print(
            "[robust_train] *** SMOKE MODE *** max_updates=6 — NOT a full Paper B train. "
            "Re-run WITHOUT --smoke for GPU job.",
            flush=True,
        )
    if args.max_updates is not None:
        cfg.setdefault("train", {})
        cfg["train"]["max_updates"] = args.max_updates
    if args.device:
        cfg.setdefault("experiment", {})
        cfg["experiment"]["device"] = args.device
    if args.seed is not None:
        cfg.setdefault("experiment", {})
        cfg["experiment"]["seed"] = args.seed

    max_u = int(cfg.get("train", {}).get("max_updates", 0))
    print(
        f"[robust_train] mode={'SMOKE' if args.smoke else 'FULL'} "
        f"data_tag={cfg.get('experiment', {}).get('data_tag')} max_updates={max_u}",
        flush=True,
    )

    try:
        run_training(cfg, config_path=args.config)
    except Exception:
        import traceback

        print("[robust_train] FATAL — traceback below", flush=True)
        traceback.print_exc()
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
