"""Per-link delay cells: where and when a model puts its congestion.

A trip's j-th link time is exit_j - exit_{j-1}, with exit_{-1} the planned
departure (so a wait to enter the network counts on the first link, and junction
time counts on the link after it, the same way in meso and SUMO). Its delay is that
time minus the link's free-flow time length / v_free. A link the trip is still on at
the horizon counts max(0, H - entry - free-flow). Delays are summed per
(link, entry-time bin): the cell total is the time loss that link adds in that
window, the quantity a router trades off.

Per-trip delay is mostly driver noise at low demand (SUMO against itself reaches
R^2 0.64-0.86), so the P2 gate uses these cells and the total delay instead.
"""

from __future__ import annotations

import math

import torch


def cell_delay(
    routes: torch.Tensor,
    dep: torch.Tensor,
    exits: torch.Tensor,
    ff_edge: torch.Tensor,
    horizon: float,
    bin_s: float,
    n_edges: int,
) -> torch.Tensor:
    """Delay per (link, bin) cell.

    routes [K, L] link index per hop (-1 = padding); dep [K] planned departures;
    exits [..., K, L] time the trip left hop j (inf = not left). Returns
    [..., n_edges * n_bins], cell = link * n_bins + bin.
    """
    n_bins = max(1, math.ceil(horizon / bin_s))
    lead = exits.shape[:-2]
    K, L = routes.shape
    dep_b = dep.expand(*lead, K).unsqueeze(-1)
    entry = torch.cat([dep_b, exits[..., :-1]], dim=-1)
    valid = (routes >= 0) & (entry < horizon) & torch.isfinite(entry)
    r = routes.clamp(min=0)
    done = torch.isfinite(exits)
    end = torch.where(done, torch.clamp(exits, max=horizon), torch.full_like(exits, horizon))
    delay = end - torch.where(valid, entry, torch.zeros_like(entry)) - ff_edge[r]
    delay = torch.where(done, delay, delay.clamp(min=0.0))
    delay = torch.where(valid, delay, torch.zeros_like(delay))
    b = torch.clamp(torch.floor(torch.where(valid, entry, torch.zeros_like(entry)) / bin_s), 0, n_bins - 1)
    cell = (r * n_bins + b.long()).expand(*lead, K, L)
    out = torch.zeros(*lead, n_edges * n_bins, device=exits.device)
    flat_cell = cell.reshape(-1, K * L)
    flat_out = out.reshape(-1, n_edges * n_bins)
    flat_out.scatter_add_(1, flat_cell, delay.reshape(-1, K * L))
    return flat_out.view(*lead, n_edges * n_bins)


def cell_mask(routes: torch.Tensor, n_edges: int, n_bins: int) -> torch.Tensor:
    """[n_edges * n_bins] cells on links any route uses."""
    used = torch.zeros(n_edges, dtype=torch.bool, device=routes.device)
    used[routes[routes >= 0]] = True
    return used.repeat_interleave(n_bins)


def r2(ref: torch.Tensor, est: torch.Tensor) -> torch.Tensor:
    """1 - SSres/SStot over the last dim; est may carry leading candidate dims."""
    ss_tot = ((ref - ref.mean()) ** 2).sum().clamp(min=1e-9)
    return 1.0 - ((est - ref) ** 2).sum(-1) / ss_tot


def cell_scores(ref: torch.Tensor, est: torch.Tensor, mask: torch.Tensor) -> dict[str, torch.Tensor]:
    """R^2 of cell delays and relative error of total delay, est [..., cells]."""
    rm, em = ref[mask], est[..., mask]
    tot_ref = rm.sum().clamp(min=1e-9)
    return {
        "r2_cell": r2(rm, em),
        "rel_err_total": (em.sum(-1) - rm.sum()).abs() / tot_ref,
        "total_delay_ref_s": rm.sum(),
        "total_delay_est_s": em.sum(-1),
    }
