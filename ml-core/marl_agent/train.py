"""Batch PPO trainer for alley routing MARL (Node 2, finite episodes).

For professor-grade training (val split, early-stop, adapt, dashboard):
  python -m marl_agent.robust_train --config marl_agent/configs/quan4_h100.yaml
See `.docs/TRAIN_SERVER.md`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from .env import AlleyRoutingEnv
from .gnn import ActorCritic


def train(
    density_path: Path,
    graph_path: Path | None,
    output_dir: Path,
    episodes: int = 50,
    seed: int = 0,
    origin: str | None = None,
    destination: str | None = None,
) -> dict[str, float]:
    env = AlleyRoutingEnv(density_path, graph_path, n_agents=2, seed=seed)
    obs0, _ = env.reset(seed=seed)
    obs_dim = int(obs0["agent_0"].shape[0])
    model = ActorCritic(obs_dim)
    optim = torch.optim.Adam(model.parameters(), lr=3e-4)

    ep_returns: list[float] = []
    for ep in range(episodes):
        options: dict = {}
        if origin is not None and destination is not None:
            options = {"origin": origin, "destination": destination, "t": 8 * 3600}
        obs, infos = env.reset(seed=seed + ep, options=options or None)
        # Single-step episode (route choice)
        actions: dict[str, int] = {}
        logps: list[torch.Tensor] = []
        values: list[torch.Tensor] = []
        for agent, o in obs.items():
            t = torch.tensor(o, dtype=torch.float32).unsqueeze(0)
            logits, value = model(t)
            dist = torch.distributions.Categorical(logits=logits)
            a = dist.sample()
            actions[agent] = int(a.item())
            logps.append(dist.log_prob(a))
            values.append(value)

        _, rewards, _, _, step_infos = env.step(actions)
        ret = float(np.mean(list(rewards.values())))
        ep_returns.append(ret)

        # PPO-ish single-step policy gradient + value loss
        adv = []
        for agent, val in zip(rewards.keys(), values):
            r = torch.tensor(rewards[agent], dtype=torch.float32)
            adv.append(r - val.detach())
        policy_loss = torch.stack([-lp * a for lp, a in zip(logps, adv)]).mean()
        value_loss = torch.stack(
            [
                F.mse_loss(
                    v.reshape(()),
                    torch.tensor(rewards[agent], dtype=torch.float32),
                )
                for agent, v in zip(rewards.keys(), values)
            ]
        ).mean()
        loss = policy_loss + 0.5 * value_loss
        optim.zero_grad()
        loss.backward()
        optim.step()

        if (ep + 1) % 10 == 0:
            print(f"episode {ep+1}/{episodes} mean_return={ret:.3f}")

    output_dir.mkdir(parents=True, exist_ok=True)
    ckpt = output_dir / "ppo_alley.pt"
    torch.save({"model": model.state_dict(), "obs_dim": obs_dim}, ckpt)

    # North-star smoke: (t, O, D) → min travel time
    nodes = list(env._g.nodes())
    od_origin = origin or (nodes[0] if nodes else "n0")
    od_dest = destination or (nodes[-1] if nodes else "n3")
    travel = env.shortest_travel_time(t=8 * 3600, origin=od_origin, destination=od_dest)
    metrics = {
        "episodes": float(episodes),
        "mean_return": float(np.mean(ep_returns)) if ep_returns else 0.0,
        "origin": od_origin,
        "destination": od_dest,
        "min_travel_time_od": float(travel),
        "checkpoint": str(ckpt),
    }
    (output_dir / "train_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(
        f"marl_agent: checkpoint -> {ckpt}; "
        f"min_travel_time({od_origin}->{od_dest})={travel:.2f}s"
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train alley MARL (batch PPO)")
    parser.add_argument("--density", type=Path, required=True)
    parser.add_argument("--graph", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--origin", type=str, default=None)
    parser.add_argument("--destination", type=str, default=None)
    args = parser.parse_args()
    train(
        args.density,
        args.graph,
        args.output,
        args.episodes,
        args.seed,
        args.origin,
        args.destination,
    )


if __name__ == "__main__":
    main()
