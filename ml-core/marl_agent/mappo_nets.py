"""MAPPO networks: shared actor + centralized critic (CTDE)."""

from __future__ import annotations

import torch
import torch.nn as nn


class SharedActor(nn.Module):
    def __init__(self, obs_dim: int, n_actions: int, hidden: int = 128) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
        )
        self.policy = nn.Linear(hidden, n_actions)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.policy(self.net(obs))


class CentralCritic(nn.Module):
    def __init__(self, global_dim: int, hidden: int = 128) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(global_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, gstate: torch.Tensor) -> torch.Tensor:
        return self.net(gstate).squeeze(-1)


class IndependentCritic(nn.Module):
    """IPPO ablation: value from local obs only."""

    def __init__(self, obs_dim: int, hidden: int = 128) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.net(obs).squeeze(-1)
