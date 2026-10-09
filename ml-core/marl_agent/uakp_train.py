"""Train UncertaintyAwareKPath (UAKP) — main paper trainer.

North-star metrics: gap-to-oracle-K, risk-adjusted travel, win vs Dijkstra-mean.
Not binary action accuracy.
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
from .gnn import ActorCritic
from .od_split import ODPair, build_connected_od_pool, save_split, split_od_pairs
from .uakp_env import UAKPEnv


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
def evaluate_policy(
    env: UAKPEnv,
    model: ActorCritic,
    pairs: list[ODPair],
    t_list: list[float],
    device: torch.device,
) -> dict[str, float]:
    if not pairs:
        return {
            "travel_time": float("nan"),
            "risk_adjusted": float("nan"),
            "oracle_travel": float("nan"),
            "gap": float("nan"),
            "oracle_hit": float("nan"),
            "n": 0.0,
        }
    travels: list[float] = []
    risks: list[float] = []
    oracles: list[float] = []
    ora_risks: list[float] = []
    gaps: list[float] = []
    gaps_risk: list[float] = []
    hits = 0
    n = 0
    model.eval()
    for p in pairs:
        for t in t_list:
            obs, info = env.reset(
                options={"origin": p.origin, "destination": p.destination, "t": float(t)}
            )
            o = torch.tensor(obs, dtype=torch.float32, device=device).unsqueeze(0)
            logits, _ = model(o)
            action = int(torch.argmax(logits, dim=-1).item())
            _, _, _, _, step_info = env.step(action)
            ora_r = float(min(env.risk_adjusted_cost(c) for c in env._candidates))
            travels.append(float(step_info["travel_time"]))
            risks.append(float(step_info["risk_adjusted"]))
            oracles.append(float(step_info["oracle_travel"]))
            ora_risks.append(ora_r)
            gaps.append(float(step_info["gap"]))
            gaps_risk.append(float(step_info["risk_adjusted"]) - ora_r)
            if action == int(step_info["oracle_idx"]):
                hits += 1
            n += 1
    model.train()
    return {
        "travel_time": float(np.mean(travels)),
        "risk_adjusted": float(np.mean(risks)),
        "oracle_travel": float(np.mean(oracles)),
        "oracle_risk": float(np.mean(ora_risks)),
        "gap": float(np.mean(gaps)),
        "gap_risk": float(np.mean(gaps_risk)),
        "oracle_hit": hits / max(n, 1),
        "n": float(n),
    }


def evaluate_baselines(
    env: UAKPEnv,
    pairs: list[ODPair],
    t_list: list[float],
) -> dict[str, dict[str, float]]:
    """Non-RL baselines on the same OD×t grid.

    North-star for UAKP (λ>0): **risk_adjusted**, not mean travel.
    Dijkstra-mean often matches travel-oracle (shortest is in K) — that is expected;
    the scientific contrast is certainty-blind mean-T vs risk-aware selection.
    """
    names = [
        "dijkstra_mean",
        "dijkstra_ignore_u",
        "prefer_alley",
        "prefer_main",
        "random_k",
        "oracle_travel_k",
        "oracle_risk_k",
    ]
    travel_b: dict[str, list[float]] = {n: [] for n in names}
    risk_b: dict[str, list[float]] = {n: [] for n in names}
    gap_travel: dict[str, list[float]] = {n: [] for n in names}
    gap_risk: dict[str, list[float]] = {n: [] for n in names}
    rng = np.random.default_rng(0)

    for p in pairs:
        for t in t_list:
            env.reset(
                options={"origin": p.origin, "destination": p.destination, "t": float(t)}
            )
            o, d = p.origin, p.destination
            cands = env._candidates
            ora_tt = float(min(c.travel_time for c in cands))
            ora_rk = float(min(env.risk_adjusted_cost(c) for c in cands))

            dm = env.baseline_dijkstra_mean(o, d)
            di = env.baseline_dijkstra_ignore_u(o, d)
            pa = env.baseline_prefer(o, d, alley=True)
            pm = env.baseline_prefer(o, d, alley=False)
            rk = cands[int(rng.integers(0, len(cands)))]
            ok_t = cands[int(np.argmin([c.travel_time for c in cands]))]
            ok_r = cands[int(np.argmin([env.risk_adjusted_cost(c) for c in cands]))]

            mapping = {
                "dijkstra_mean": dm,
                "dijkstra_ignore_u": di,
                "prefer_alley": pa,
                "prefer_main": pm,
                "random_k": rk,
                "oracle_travel_k": ok_t,
                "oracle_risk_k": ok_r,
            }
            for name, cand in mapping.items():
                tt = float(cand.travel_time)
                ra = float(env.risk_adjusted_cost(cand))
                travel_b[name].append(tt)
                risk_b[name].append(ra)
                gap_travel[name].append(tt - ora_tt)
                gap_risk[name].append(ra - ora_rk)

    out: dict[str, dict[str, float]] = {}
    for name in names:
        out[name] = {
            "travel_time": float(np.mean(travel_b[name])),
            "risk_adjusted": float(np.mean(risk_b[name])),
            "gap_to_oracle_travel_k": float(np.mean(gap_travel[name])),
            "gap_to_oracle_risk_k": float(np.mean(gap_risk[name])),
            "n": float(len(travel_b[name])),
        }
    return out


def evaluate_stochastic(
    env: UAKPEnv,
    model: ActorCritic | None,
    pairs: list[ODPair],
    t_list: list[float],
    device: torch.device | None,
    n_samples: int = 24,
    mode: str = "policy",
) -> dict[str, float]:
    """Monte-Carlo travel under u-scaled noise — CVaR / mean for paper tables."""
    means: list[float] = []
    cvars: list[float] = []
    for i, p in enumerate(pairs):
        for j, t in enumerate(t_list):
            env.reset(
                options={"origin": p.origin, "destination": p.destination, "t": float(t)}
            )
            if mode == "policy":
                assert model is not None and device is not None
                o = torch.tensor(env._obs(), dtype=torch.float32, device=device).unsqueeze(0)
                with torch.no_grad():
                    logits, _ = model(o)
                    action = int(torch.argmax(logits, dim=-1).item())
                cand = env._candidates[action % env.k_paths]
            elif mode == "dijkstra_mean":
                cand = env.baseline_dijkstra_mean(p.origin, p.destination)
            elif mode == "random_k":
                cand = env._candidates[int(np.random.default_rng(i * 100 + j).integers(0, env.k_paths))]
            else:
                raise ValueError(mode)
            samples = env.realized_travel_samples(
                cand, n_samples=n_samples, seed=1000 + i * 17 + j
            )
            means.append(float(np.mean(samples)))
            cvars.append(env.cvar(samples, 0.9))
    return {
        "stoch_mean": float(np.mean(means)),
        "stoch_cvar90": float(np.mean(cvars)),
        "n": float(len(means)),
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

    last: dict[str, float] = {}
    for _ in range(ppo_epochs):
        logits, values = model(obs)
        dist = torch.distributions.Categorical(logits=logits)
        logp = dist.log_prob(actions)
        entropy = dist.entropy().mean()
        ratio = torch.exp(logp - old_logp)
        surr1 = ratio * advantages
        surr2 = torch.clamp(ratio, 1.0 - hparams.clip_eps, 1.0 + hparams.clip_eps) * advantages
        policy_loss = -torch.min(surr1, surr2).mean()
        value_loss = F.mse_loss(values, returns)
        loss = policy_loss + hparams.value_coef * value_loss - hparams.entropy_coef * entropy
        optim.zero_grad()
        loss.backward()
        if grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optim.step()
        last = {
            "loss": float(loss.item()),
            "policy_loss": float(policy_loss.item()),
            "value_loss": float(value_loss.item()),
            "entropy": float(entropy.item()),
        }
    return last


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
            "L1 requires density_by_peak (≥2 peaks). Check twin WCC files."
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    exp_name = cfg.get("experiment", {}).get("name", "quan4_uakp")
    data_tag = str(cfg.get("experiment", {}).get("data_tag", "uakp_v1"))
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
    if not split["train"] or not split["val"]:
        raise RuntimeError("OD split empty — check seeds/graph connectivity")

    env_cfg = cfg.get("env", {})
    k_paths = int(env_cfg.get("k_paths", 8))
    env = UAKPEnv(
        density_path=density,
        graph_path=graph,
        seed=seed,
        k_paths=k_paths,
        risk_lambda=float(env_cfg.get("risk_lambda", 0.05)),
        compact_dim=int(env_cfg.get("compact_dim", 128)),
        include_uncertainty=bool(env_cfg.get("include_uncertainty", True)),
        density_catalog=density_catalog or None,
    )
    obs_dim = env.obs_dim()
    n_actions = env.n_actions()
    max_obs = int(cfg.get("risk", {}).get("max_obs_dim", 512))
    if obs_dim > max_obs:
        raise RuntimeError(f"obs_dim={obs_dim} > max_obs_dim={max_obs}")

    model_cfg = cfg.get("model", {})
    model = ActorCritic(
        obs_dim,
        n_actions=n_actions,
        hidden=int(model_cfg.get("hidden", 128)),
    ).to(device)

    optim_cfg = cfg.get("optim", {})
    ppo_cfg = cfg.get("ppo", {})
    hparams = HyperParams(
        lr=float(optim_cfg.get("lr", 3e-4)),
        entropy_coef=float(ppo_cfg.get("entropy_coef", 0.05)),
        clip_eps=float(ppo_cfg.get("clip_eps", 0.2)),
        value_coef=float(ppo_cfg.get("value_coef", 0.5)),
    )
    optim = torch.optim.Adam(
        model.parameters(),
        lr=hparams.lr,
        weight_decay=float(optim_cfg.get("weight_decay", 1e-5)),
    )

    train_cfg = cfg.get("train", {})
    max_updates = int(train_cfg.get("max_updates", 500))
    eval_every = int(train_cfg.get("eval_every", 10))
    log_every = int(train_cfg.get("log_every", 1))
    save_every = int(train_cfg.get("save_every", 20))
    rollout_n = int(ppo_cfg.get("rollout_episodes", 64))
    ppo_epochs = int(ppo_cfg.get("ppo_epochs", 4))
    grad_clip = float(optim_cfg.get("grad_clip_norm", 1.0))
    normalize_adv = bool(ppo_cfg.get("normalize_advantage", True))

    t_train = [float(x) for x in data_cfg.get("t_train", [28800])]
    t_eval = [float(x) for x in data_cfg.get("t_eval", [28800])]

    es_cfg = cfg.get("early_stopping", {})
    early = EarlyStopping(
        patience=int(es_cfg.get("patience", 15)),
        min_delta=float(es_cfg.get("min_delta", 0.5)),
        mode=str(es_cfg.get("mode", "min")),
    )
    adapt_cfg = cfg.get("adapt", {})
    adapter = ValHyperAdapter(
        initial=hparams,
        lr_min=float(optim_cfg.get("lr_min", 1e-5)),
        entropy_min=float(ppo_cfg.get("entropy_coef_min", 0.005)),
        plateau_evals=int(adapt_cfg.get("plateau_evals", 3)),
        lr_decay=float(adapt_cfg.get("lr_decay", 0.5)),
        entropy_decay=float(adapt_cfg.get("entropy_decay", 0.7)),
        improve_entropy_boost=float(adapt_cfg.get("improve_entropy_boost", 1.15)),
        interpolate_with_best=bool(adapt_cfg.get("interpolate_with_best", True)),
        interpolate_alpha=float(adapt_cfg.get("interpolate_alpha", 0.35)),
        mode="min",
    )

    rng = np.random.default_rng(seed)
    jsonl_path = run_dir / "metrics.jsonl"
    csv_path = run_dir / "metrics.csv"
    best_path = run_dir / "best.pt"

    mode = "SMOKE" if str(data_tag).endswith("_smoke") else "FULL"
    print(
        f"[uakp_train] mode={mode} data_tag={data_tag} device={device} "
        f"K={k_paths} risk_lambda={env.risk_lambda} include_u={env.include_uncertainty} "
        f"obs_dim={obs_dim} n_actions={n_actions} max_updates={max_updates} "
        f"train_od={len(split['train'])} val_od={len(split['val'])}",
        flush=True,
    )
    print(f"[uakp_train] run_dir={run_dir}", flush=True)

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
                "mean_travel",
                "mean_risk_adj",
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
            last_update = update
            obs_list: list[torch.Tensor] = []
            act_list: list[torch.Tensor] = []
            logp_list: list[torch.Tensor] = []
            ret_list: list[torch.Tensor] = []
            adv_list: list[torch.Tensor] = []
            ep_returns: list[float] = []
            ep_travels: list[float] = []
            ep_risks: list[float] = []

            model.train()
            for ep in range(rollout_n):
                od = sample_od(split["train"], rng)
                t = float(rng.choice(t_train))
                obs_np, _ = env.reset(
                    seed=seed + update * 1000 + ep,
                    options={"origin": od.origin, "destination": od.destination, "t": t},
                )
                o = torch.tensor(obs_np, dtype=torch.float32, device=device)
                logits, value = model(o.unsqueeze(0))
                dist = torch.distributions.Categorical(logits=logits)
                action = dist.sample()
                logp = dist.log_prob(action)
                _, reward, _, _, info = env.step(int(action.item()))
                tt = float(info["travel_time"])
                if cfg.get("risk", {}).get("fail_on_infinite_travel", True) and tt >= 1e6:
                    raise RuntimeError(f"Infinite travel on OD {od.od_id}")
                if cfg.get("risk", {}).get("nan_guard", True) and (
                    not math.isfinite(reward) or not torch.isfinite(logp)
                ):
                    raise RuntimeError("NaN/Inf in rollout")
                r = float(reward) / 100.0
                ret = torch.tensor([r], dtype=torch.float32, device=device)
                adv = ret - value.detach()
                obs_list.append(o)
                act_list.append(action.squeeze(0))
                logp_list.append(logp.squeeze(0))
                ret_list.append(ret.squeeze(0))
                adv_list.append(adv.squeeze(0))
                ep_returns.append(float(reward))
                ep_travels.append(tt)
                ep_risks.append(float(info["risk_adjusted"]))

            batch = {
                "obs": torch.stack(obs_list),
                "actions": torch.stack(act_list),
                "logp": torch.stack(logp_list).detach(),
                "returns": torch.stack(ret_list),
                "advantages": torch.stack(adv_list),
            }
            stats = ppo_update(
                model, optim, batch, hparams, ppo_epochs, grad_clip, normalize_adv
            )

            row = {
                "update": update,
                "mean_return": float(np.mean(ep_returns)),
                "mean_travel": float(np.mean(ep_travels)),
                "mean_risk_adj": float(np.mean(ep_risks)),
                "loss": stats["loss"],
                "policy_loss": stats["policy_loss"],
                "value_loss": stats["value_loss"],
                "entropy": stats["entropy"],
                "lr": hparams.lr,
                "entropy_coef": hparams.entropy_coef,
            }
            csv_w.writerow(row)
            cf.flush()
            jf.write(json.dumps({"type": "train", **row}) + "\n")
            jf.flush()

            if update % log_every == 0:
                print(
                    f"[train] {update}/{max_updates} | "
                    f"return={row['mean_return']:.1f} travel={row['mean_travel']:.1f}s "
                    f"risk_adj={row['mean_risk_adj']:.1f} | loss={row['loss']:.3f} | "
                    f"lr={row['lr']:.2e} ent={row['entropy']:.4f}",
                    flush=True,
                )

            if update % eval_every == 0 or update == max_updates:
                val = evaluate_policy(env, model, split["val"], t_eval, device)
                erow = {"type": "eval", "update": update, **{f"val_{k}": v for k, v in val.items()}}
                jf.write(json.dumps(erow) + "\n")
                jf.flush()
                print(
                    f"[eval]  val_travel={val['travel_time']:.1f}s | "
                    f"risk_adj={val['risk_adjusted']:.1f} | oracle={val['oracle_travel']:.1f}s | "
                    f"gap={val['gap']:.1f}s | hit={val['oracle_hit']:.0%} | "
                    f"best={early.best_metric if early.best_update >= 0 else val['risk_adjusted']:.1f}",
                    flush=True,
                )

                if bool(es_cfg.get("enabled", True)):
                    st = early.step(val["risk_adjusted"], update)
                    if st.reason == "improved" or (
                        best_state is None and st.best_update == update
                    ):
                        best_state = {
                            "model": {k: v.detach().cpu().clone() for k, v in model.state_dict().items()},
                            "update": update,
                            "val": val,
                        }
                        torch.save(
                            {
                                "model": model.state_dict(),
                                "obs_dim": obs_dim,
                                "n_actions": n_actions,
                                "k_paths": k_paths,
                                "update": update,
                                "val": val,
                                "cfg_tag": data_tag,
                            },
                            best_path,
                        )
                        print(
                            f"  [ckpt] best.pt val_risk_adj={val['risk_adjusted']:.2f}s gap={val['gap']:.2f}s",
                            flush=True,
                        )
                    if st.stopped:
                        print(f"  [early_stop] {st.reason}", flush=True)
                        stop_reason = st.reason
                        break

                if bool(adapt_cfg.get("enabled", True)):
                    arec = adapter.step(val["risk_adjusted"], update)
                    hparams = adapter.current
                    for pg in optim.param_groups:
                        pg["lr"] = hparams.lr
                    if arec.get("event"):
                        print(f"  [adapt] {arec}", flush=True)

            if update % save_every == 0:
                torch.save(
                    {"model": model.state_dict(), "update": update},
                    run_dir / f"ckpt_{update}.pt",
                )

    if bool(es_cfg.get("restore_best", True)) and best_state is not None:
        model.load_state_dict(best_state["model"])
        print(
            f"[uakp_train] restored best.pt from update {best_state['update']}",
            flush=True,
        )

    test = evaluate_policy(env, model, split["test"], t_eval, device)
    baselines = {}
    stoch: dict[str, dict[str, float]] = {}
    if bool(cfg.get("baseline", {}).get("run_on_eval", True)):
        baselines = evaluate_baselines(env, split["test"], t_eval)
        print("[baselines] test set (travel | risk_adj | gap_risk):", flush=True)
        for name, m in baselines.items():
            print(
                f"  {name:20s} travel={m['travel_time']:.1f}s "
                f"risk_adj={m['risk_adjusted']:.1f}s "
                f"gap_risk={m['gap_to_oracle_risk_k']:.2f}s",
                flush=True,
            )
        # Stochastic realization eval (uncertainty-aware north-star)
        for mode in ("policy", "dijkstra_mean", "random_k"):
            stoch[mode] = evaluate_stochastic(
                env,
                model if mode == "policy" else None,
                split["test"],
                t_eval,
                device if mode == "policy" else None,
                n_samples=24,
                mode=mode,
            )
            print(
                f"  [stoch] {mode:16s} mean={stoch[mode]['stoch_mean']:.1f}s "
                f"CVaR90={stoch[mode]['stoch_cvar90']:.1f}s",
                flush=True,
            )

    djk = baselines.get("dijkstra_mean", {})
    djk_tt = float(djk.get("travel_time", float("nan")))
    djk_ra = float(djk.get("risk_adjusted", float("nan")))

    summary = {
        "data_tag": data_tag,
        "seed": seed,
        "device": str(device),
        "k_paths": k_paths,
        "risk_lambda": env.risk_lambda,
        "include_uncertainty": env.include_uncertainty,
        "obs_dim": obs_dim,
        "n_actions": n_actions,
        "updates_ran": int(last_update),
        "stop_reason": stop_reason,
        "best_val_risk_adjusted": early.best_metric if early.best_update >= 0 else test["risk_adjusted"],
        "best_update": early.best_update,
        "test_travel_time": test["travel_time"],
        "test_risk_adjusted": test["risk_adjusted"],
        "test_oracle_travel": test["oracle_travel"],
        "test_gap": test["gap"],
        "test_oracle_hit": test["oracle_hit"],
        "test_vs_dijkstra_mean_travel": djk_tt,
        "test_vs_dijkstra_mean_risk": djk_ra,
        "test_beats_dijkstra_on_risk": (
            bool(test["risk_adjusted"] < djk_ra) if math.isfinite(djk_ra) else None
        ),
        "test_beats_random_on_travel": (
            bool(test["travel_time"] < baselines["random_k"]["travel_time"])
            if "random_k" in baselines
            else None
        ),
        "baselines_test": baselines,
        "stochastic_test": stoch,
        "test_beats_dijkstra_on_cvar": (
            bool(stoch["policy"]["stoch_cvar90"] < stoch["dijkstra_mean"]["stoch_cvar90"])
            if stoch.get("policy") and stoch.get("dijkstra_mean")
            else None
        ),
        "elapsed_sec": time.time() - t0,
        "run_dir": str(run_dir),
        "best_checkpoint": str(best_path) if best_path.exists() else None,
        "note": (
            "Deterministic Dijkstra travel often equals travel-oracle (shortest in K). "
            "Primary uncertainty-aware metric: stochastic CVaR90 (realized travel ~ u)."
        ),
    }

    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    print("UAKP_TRAIN_OK", flush=True)
    return summary


def main() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="UAKP train (uncertainty-aware K-path)")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("marl_agent/configs/quan4_uakp.yaml"),
    )
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--smoke", action="store_true", help="Tiny run (~few updates)")
    parser.add_argument("--no-uncertainty", action="store_true", help="Ablation: drop u from obs/reward")
    parser.add_argument("--risk-lambda", type=float, default=None, help="Override env.risk_lambda")
    parser.add_argument("--max-updates", type=int, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.device:
        cfg.setdefault("experiment", {})["device"] = args.device
    if args.no_uncertainty:
        cfg.setdefault("env", {})["include_uncertainty"] = False
        cfg.setdefault("env", {})["risk_lambda"] = 0.0
        cfg.setdefault("experiment", {})["data_tag"] = (
            str(cfg.get("experiment", {}).get("data_tag", "uakp_v1")) + "_nou"
        )
    if args.risk_lambda is not None:
        cfg.setdefault("env", {})["risk_lambda"] = float(args.risk_lambda)
        if float(args.risk_lambda) == 0.0:
            tag = str(cfg.get("experiment", {}).get("data_tag", "uakp_v1"))
            if not tag.endswith("_l0"):
                cfg.setdefault("experiment", {})["data_tag"] = tag + "_l0"
    if args.max_updates is not None:
        cfg.setdefault("train", {})["max_updates"] = int(args.max_updates)
    if args.smoke:
        print("*** SMOKE MODE - not a paper run ***", flush=True)
        cfg.setdefault("train", {})["max_updates"] = 6
        cfg.setdefault("train", {})["eval_every"] = 2
        cfg.setdefault("ppo", {})["rollout_episodes"] = 8
        cfg.setdefault("early_stopping", {})["patience"] = 3
        cfg.setdefault("baseline", {})["run_on_eval"] = False
        cfg.setdefault("experiment", {})["data_tag"] = (
            str(cfg.get("experiment", {}).get("data_tag", "uakp_v1")) + "_smoke"
        )

    print(
        f"[uakp_train] boot config={args.config} smoke={args.smoke} "
        f"include_u={cfg.get('env', {}).get('include_uncertainty')} "
        f"risk_lambda={cfg.get('env', {}).get('risk_lambda')}",
        flush=True,
    )
    try:
        run_training(cfg, config_path=args.config)
    except Exception:
        import traceback

        print("FATAL uakp_train:", flush=True)
        traceback.print_exc()
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
