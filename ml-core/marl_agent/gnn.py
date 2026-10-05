"""Lightweight GNN-style encoder over alley graph features (PyTorch)."""

from __future__ import annotations

import torch
import torch.nn as nn


class AlleyGNNEncoder(nn.Module):
    """Two-layer message-passing-ish MLP over concatenated node/edge features."""

    def __init__(self, in_dim: int, hidden: int = 64, out_dim: int = 32) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, out_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class ActorCritic(nn.Module):
    def __init__(self, obs_dim: int, n_actions: int = 2, hidden: int = 64) -> None:
        super().__init__()
        self.encoder = AlleyGNNEncoder(obs_dim, hidden=hidden, out_dim=hidden)
        self.policy = nn.Linear(hidden, n_actions)
        self.value = nn.Linear(hidden, 1)

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.encoder(obs)
        return self.policy(h), self.value(h).squeeze(-1)
