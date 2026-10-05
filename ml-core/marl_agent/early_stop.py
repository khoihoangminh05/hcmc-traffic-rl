"""Early stopping + best-checkpoint tracking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EarlyStopState:
    best_metric: float
    best_update: int
    bad_evals: int
    stopped: bool
    reason: str


class EarlyStopping:
    def __init__(
        self,
        patience: int = 12,
        min_delta: float = 0.5,
        mode: str = "min",
    ) -> None:
        self.patience = max(1, int(patience))
        self.min_delta = float(min_delta)
        self.mode = mode if mode in ("min", "max") else "min"
        self.best_metric = float("inf") if self.mode == "min" else float("-inf")
        self.best_update = -1
        self.bad_evals = 0
        self.stopped = False
        self.reason = ""

    def _improved(self, value: float) -> bool:
        if self.mode == "min":
            return value < self.best_metric - self.min_delta
        return value > self.best_metric + self.min_delta

    def step(self, value: float, update: int) -> EarlyStopState:
        if self._improved(value):
            self.best_metric = float(value)
            self.best_update = int(update)
            self.bad_evals = 0
            self.reason = "improved"
        else:
            self.bad_evals += 1
            self.reason = f"no_improve ({self.bad_evals}/{self.patience})"
            if self.bad_evals >= self.patience:
                self.stopped = True
                self.reason = (
                    f"early_stop: no val improve for {self.patience} evals "
                    f"(best={self.best_metric:.4f} @ update {self.best_update})"
                )
        return EarlyStopState(
            best_metric=self.best_metric,
            best_update=self.best_update,
            bad_evals=self.bad_evals,
            stopped=self.stopped,
            reason=self.reason,
        )
