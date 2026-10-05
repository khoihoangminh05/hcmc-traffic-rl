"""Data fusion: Greenshields + Kalman → density k(t) per alley_id."""

from __future__ import annotations

__all__ = ["run_batch"]


def __getattr__(name: str):
    if name == "run_batch":
        from .run_batch import run_batch

        return run_batch
    raise AttributeError(name)
