"""The two objectives every routing controller is scored on, from per-trip records.

- T_all: mean travel time of every trip, customers and other traffic. This is the congestion
  objective. The congestion index is T_all / T_ff_all, where T_ff_all is the mean free-flow time
  of the same trips; for a fixed demand T_ff_all is a constant, so the index is proportional to
  T_all and can be compared across demand levels.
- T_cust: mean travel time of the customers, the motorbikes the provider dispatches.

Rules that keep a jammed network from looking good:
- The denominator is every trip in the demand, not only the trips that finished.
- A trip's clock starts at its planned departure, so waiting to enter the network counts.
- An unfinished trip counts its time so far plus the free-flow time it still has to drive, which
  is a lower bound on its true time.
- Teleports cannot be priced without inventing a number, so they are reported, not added.

Both objectives are in seconds, so J = w T_all + (1 - w) T_cust needs no rescaling. At
penetration 1 the two objectives are the same number.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def _mean(x: np.ndarray) -> float | None:
    return float(x.mean()) if x.size else None


def _p95(x: np.ndarray) -> float | None:
    return float(np.percentile(x, 95)) if x.size else None


def trip_metrics(
    depart_s: Any,
    end_s: Any,
    arrived: Any,
    remaining_ff_s: Any,
    free_flow_s: Any,
    is_customer: Any,
    teleports: int = 0,
) -> dict[str, float | int | None]:
    """One episode's metrics. All arrays have one row per trip in the demand.

    end_s is the arrival time, or the end of the simulation for an unfinished trip.
    remaining_ff_s is the free-flow time still to drive (ignored for arrived trips).
    """
    dep = np.asarray(depart_s, dtype=np.float64)
    end = np.asarray(end_s, dtype=np.float64)
    done = np.asarray(arrived, dtype=bool)
    rem = np.asarray(remaining_ff_s, dtype=np.float64)
    ff = np.asarray(free_flow_s, dtype=np.float64)
    cust = np.asarray(is_customer, dtype=bool)
    if not dep.shape == end.shape == done.shape == rem.shape == ff.shape == cust.shape:
        raise ValueError("every per-trip array must have the same shape")
    tt = end - dep + np.where(done, 0.0, np.maximum(rem, 0.0))
    n = int(tt.size)
    t_all = _mean(tt)
    t_ff = _mean(ff)
    return {
        "T_all_s": t_all,
        "T_cust_s": _mean(tt[cust]),
        "T_other_s": _mean(tt[~cust]),
        "congestion_index": t_all / t_ff if t_all is not None and t_ff else None,
        "p95_all_s": _p95(tt),
        "p95_cust_s": _p95(tt[cust]),
        "T_ff_all_s": t_ff,
        "n_all": n,
        "n_cust": int(cust.sum()),
        "unfinished_all": int((~done).sum()),
        "unfinished_cust": int((~done & cust).sum()),
        "arrived_share_all": float(done.mean()) if n else None,
        "arrived_share_cust": float(done[cust].mean()) if cust.any() else None,
        "teleports": int(teleports),
        "teleports_per_1k_trips": 1000.0 * teleports / n if n else None,
    }


def objective(m: dict, w_all: float = 0.5) -> float:
    """J = w T_all + (1 - w) T_cust, lower is better. With no customers, J = T_all."""
    if not 0.0 <= w_all <= 1.0:
        raise ValueError(f"w_all must be in [0, 1], got {w_all}")
    t_all, t_cust = m["T_all_s"], m["T_cust_s"]
    if t_all is None:
        raise ValueError("episode has no trips")
    return float(t_all) if t_cust is None else w_all * t_all + (1.0 - w_all) * t_cust


def gain_pct(m: dict, ref: dict) -> dict[str, float | None]:
    """Reduction versus a reference on the same demand, in percent. Positive means better than ref."""
    out: dict[str, float | None] = {}
    for key in ("T_all_s", "T_cust_s", "T_other_s", "p95_all_s", "p95_cust_s"):
        a, b = m.get(key), ref.get(key)
        out[key] = 100.0 * (b - a) / b if a is not None and b else None
    return out
