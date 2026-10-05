"""Validation-driven hyperparameter adaptation.

Idea (professor-safe, no random hyper-search burn):
- Keep a snapshot of hyperparameters at the best validation score.
- On plateau: decay LR & entropy (less noise, finer steps).
- On sharp improvement: mild entropy boost (escape greedy collapse).
- Optionally interpolate current ↔ best using inverse-distance on val metric.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class HyperParams:
    lr: float
    entropy_coef: float
    clip_eps: float
    value_coef: float

    def as_dict(self) -> dict[str, float]:
        return {k: float(v) for k, v in asdict(self).items()}


class ValHyperAdapter:
    def __init__(
        self,
        initial: HyperParams,
        lr_min: float = 1e-5,
        entropy_min: float = 1e-3,
        plateau_evals: int = 3,
        lr_decay: float = 0.5,
        entropy_decay: float = 0.7,
        improve_entropy_boost: float = 1.15,
        interpolate_with_best: bool = True,
        interpolate_alpha: float = 0.35,
        mode: str = "min",
    ) -> None:
        self.current = HyperParams(**initial.as_dict())
        self.best = HyperParams(**initial.as_dict())
        self.best_metric = float("inf") if mode == "min" else float("-inf")
        self.lr_min = lr_min
        self.entropy_min = entropy_min
        self.plateau_evals = max(1, plateau_evals)
        self.lr_decay = lr_decay
        self.entropy_decay = entropy_decay
        self.improve_entropy_boost = improve_entropy_boost
        self.interpolate_with_best = interpolate_with_best
        self.interpolate_alpha = float(interpolate_alpha)
        self.mode = mode
        self._since_improve = 0
        self.history: list[dict[str, Any]] = []

    def _is_better(self, metric: float) -> bool:
        if self.mode == "min":
            return metric < self.best_metric
        return metric > self.best_metric

    def _gap(self, metric: float) -> float:
        """Non-negative distance from best (0 = at best)."""
        if self.mode == "min":
            return max(0.0, metric - self.best_metric)
        return max(0.0, self.best_metric - metric)

    def step(self, val_metric: float, update: int) -> dict[str, Any]:
        event = "hold"
        prev = self.current.as_dict()

        if self._is_better(val_metric):
            # Sharp vs mild improvement
            gap_before = self._gap(val_metric) if self.best_metric < float("inf") else 0.0
            self.best_metric = float(val_metric)
            self.best = HyperParams(**self.current.as_dict())
            self._since_improve = 0
            if gap_before > 1.0:  # meaningful jump (seconds for travel time)
                self.current.entropy_coef = min(
                    0.1, self.current.entropy_coef * self.improve_entropy_boost
                )
                event = "improve_boost_entropy"
            else:
                event = "improve"
        else:
            self._since_improve += 1
            if self._since_improve >= self.plateau_evals:
                self.current.lr = max(self.lr_min, self.current.lr * self.lr_decay)
                self.current.entropy_coef = max(
                    self.entropy_min, self.current.entropy_coef * self.entropy_decay
                )
                self._since_improve = 0
                event = "plateau_decay"

            if self.interpolate_with_best and self.best_metric < float("inf"):
                # Pull toward best hyperparams proportional to how bad val is vs best
                gap = self._gap(val_metric)
                # Map gap → blend weight in [0, alpha]
                w = self.interpolate_alpha * (1.0 - 1.0 / (1.0 + gap / 10.0))
                self.current.lr = (1 - w) * self.current.lr + w * self.best.lr
                self.current.entropy_coef = (
                    (1 - w) * self.current.entropy_coef + w * self.best.entropy_coef
                )
                self.current.clip_eps = (1 - w) * self.current.clip_eps + w * self.best.clip_eps
                self.current.value_coef = (
                    (1 - w) * self.current.value_coef + w * self.best.value_coef
                )
                if event == "hold":
                    event = "interpolate_toward_best"

        rec = {
            "update": update,
            "val_metric": float(val_metric),
            "event": event,
            "before": prev,
            "after": self.current.as_dict(),
            "best_metric": float(self.best_metric),
            "best_hparams": self.best.as_dict(),
        }
        self.history.append(rec)
        return rec
