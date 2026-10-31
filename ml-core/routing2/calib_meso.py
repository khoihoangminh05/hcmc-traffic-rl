"""Fit the meso P2.3 terms to SUMO (batch, GPU).

Input: `sumo_trips_<stamp>.json` from routing2.sumo_check. The demand, zones and
free-flow routes are rebuilt from its args and checked against its free-flow
times, so meso and SUMO drive the same trips on the same routes.

Every parameter candidate runs as an env (MesoSim env_params) for each fit seed,
one batch per demand level. Objective: mean over levels of 1 - R^2 of per-trip
delay (trip time minus route free-flow time) against SUMO, over the trips SUMO
delivers before the horizon; a meso trip that has not arrived ends at the horizon,
so jamming where SUMO flows is penalised. (Capping both sides instead lets the
late departures dominate the variance.) Search: uniform in the box (log-uniform for the scales), then
rounds that shrink the box around the best candidate.

The best candidate and the defaults are then scored on the test seeds, which the
fit never sees, with the sumo_check metrics, next to SUMO's own repeatability
(two SUMO driver seeds) as the ceiling. Writes calib_meso_<stamp>.json and does
not change the defaults in params.py.

    python -u -m routing2.calib_meso --trips artifacts/out/quan4/routing2/sumo_trips_<stamp>.json \\
        --device cuda --cands 128 --rounds 4
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import torch

from .demand import make_demand, pick_zones
from .graph import DEFAULT_GRAPH, load_graph
from .meso_gpu import ARRIVED, MesoSim
from .params import ENV_PARAMS, SimConfig
from .policies import FixedRoute, free_flow_routes

# name: (low, high, log scale)
BOX = {
    "speed_factor": (0.85, 1.05, False),
    "k_crit": (0.0, 0.8, False),
    "speed_floor": (0.05, 1.0, False),
    "storage_scale": (0.5, 6.0, True),
    "cap_scale": (0.5, 6.0, True),
    "gap_tc_s": (0.0, 6.0, False),
    "gap_tf_s": (0.5, 3.0, False),
}
assert set(BOX) == set(ENV_PARAMS)


def sample(n: int, gen: torch.Generator, center: dict | None = None, shrink: float = 1.0) -> dict:
    """n candidates, uniform in the box or in a box of relative width `shrink` around center."""
    out = {}
    for k, (lo, hi, log) in BOX.items():
        a, b = (math.log(lo), math.log(hi)) if log else (lo, hi)
        if center is not None:
            c = math.log(center[k]) if log else center[k]
            w = 0.5 * shrink * (b - a)
            a, b = max(a, c - w), min(b, c + w)
        x = a + (b - a) * torch.rand(n, generator=gen)
        out[k] = torch.exp(x) if log else x
    return out


class Level:
    """One demand level: SUMO targets and the routes for a set of seeds."""

    def __init__(self, g, zones, cfg, tph: float, recs: dict[int, dict], seeds: list[int], dev: str):
        self.tph, self.seeds = tph, seeds
        d0 = make_demand(g, zones, seeds, tph, cfg.horizon_s, 1.0)
        sim0 = MesoSim(g, d0, zones, cfg)
        self.N = sim0.N
        routes = free_flow_routes(g, sim0.free_tt(), zones, sim0.orig, sim0.dest_zone)
        ff_edge = g.length / g.v_free
        ff = torch.where(routes >= 0, ff_edge[routes.clamp(min=0)], 0.0).sum(1)
        self.routes = routes.view(len(seeds), self.N, -1)
        sumo_seeds = sorted({k for s in seeds for k in recs[s]["sumo_arrive"]}, key=int)
        H = cfg.horizon_s
        idx, dep, ffk, s_end, s_end2 = [], [], [], [], []
        for j, s in enumerate(seeds):
            r = recs[s]
            k = torch.tensor(r["kept"], dtype=torch.long)
            got = ff[j * self.N + k]
            want = torch.tensor(r["ff"])
            if not torch.allclose(got.cpu(), want, atol=0.05):
                raise SystemExit(f"tph={tph} seed={s}: routes differ from the SUMO run (graph or code changed)")
            idx.append(j * self.N + k)
            dep.append(torch.tensor(r["dep"]))
            ffk.append(want)
            arr = r["sumo_arrive"]
            s_end.append(torch.tensor([H if a is None else a for a in arr[sumo_seeds[0]]]))
            if len(sumo_seeds) > 1:
                s_end2.append(torch.tensor([H if a is None else a for a in arr[sumo_seeds[1]]]))
        self.idx = torch.cat(idx).to(dev)
        self.dep = torch.cat(dep).to(dev)
        self.ff = torch.cat(ffk).to(dev)
        self.s_end = torch.cat(s_end).to(dev)
        self.s_end2 = torch.cat(s_end2).to(dev) if s_end2 else None
        self.H = H

    def run(self, g, zones, cfg, cands: dict) -> torch.Tensor:
        """Meso end times [C, K] for C candidates on this level's trips."""
        C = next(iter(cands.values())).numel()
        S = len(self.seeds)
        d = make_demand(g, zones, self.seeds * C, self.tph, cfg.horizon_s, 1.0)
        ep = {k: v.repeat_interleave(S) for k, v in cands.items()}
        sim = MesoSim(g, d, zones, cfg, env_params=ep)
        routes = self.routes.repeat(C, 1, 1).view(C * S * self.N, -1)
        sim.run(FixedRoute(routes))
        end = torch.where(sim.status == ARRIVED, sim.arrive_t, torch.full_like(sim.arrive_t, self.H))
        end = torch.clamp(end, max=self.H).view(C, S * self.N)
        return end[:, self.idx]

    def loss(self, m_end: torch.Tensor) -> torch.Tensor:
        """1 - R^2 of delay on SUMO-delivered trips (meso capped at the horizon), per candidate."""
        a = self.s_end < self.H - 1e-6
        ref = (self.s_end - self.dep - self.ff)[a]
        est = (m_end - self.dep - self.ff)[:, a]
        ss_tot = ((ref - ref.mean()) ** 2).sum().clamp(min=1e-9)
        return ((est - ref) ** 2).sum(1) / ss_tot

    def metrics(self, m_end: torch.Tensor) -> dict:
        """sumo_check-style metrics for one candidate (m_end [K])."""
        H = self.H
        s_arr = self.s_end < H - 1e-6
        m_arr = m_end < H - 1e-6
        both = s_arr & m_arr
        ref = self.s_end - self.dep - self.ff
        est = m_end - self.dep - self.ff

        def r2(a, b):
            if a.numel() < 3:
                return math.nan
            return float(1 - ((a - b) ** 2).sum() / ((a - a.mean()) ** 2).sum().clamp(min=1e-9))

        row = {
            "tph": self.tph, "trips": int(ref.numel()), "both_arrived": int(both.sum()),
            "r2_delay_both_arrived": round(r2(ref[both], est[both]), 4),
            "r2_delay_sumo_arrived": round(r2(ref[s_arr], est[s_arr]), 4),
            "mean_delay_sumo_s": round(float(ref[both].mean()), 1),
            "mean_delay_meso_s": round(float(est[both].mean()), 1),
            "arrived_sumo": round(float(s_arr.float().mean()), 3),
            "arrived_meso": round(float(m_arr.float().mean()), 3),
        }
        if self.s_end2 is not None:
            ref2 = self.s_end2 - self.dep - self.ff
            b2 = s_arr & (self.s_end2 < H - 1e-6)
            row["r2_delay_sumo_vs_sumo"] = round(r2(ref[b2], ref2[b2]), 4)
            row["r2_delay_sumo_arrived_sumo_vs_sumo"] = round(r2(ref[s_arr], ref2[s_arr]), 4)
        return row


def evaluate(levels, g, zones, cfg, cands: dict, chunk: int) -> torch.Tensor:
    C = next(iter(cands.values())).numel()
    tot = torch.zeros(C)
    for lv in levels:
        for a in range(0, C, chunk):
            sub = {k: v[a:a + chunk] for k, v in cands.items()}
            tot[a:a + chunk] += lv.loss(lv.run(g, zones, cfg, sub)).cpu()
    return tot / len(levels)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trips", type=Path, required=True)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--fit-seeds", type=int, nargs="*", default=None, help="default: first half")
    ap.add_argument("--tph", type=float, nargs="*", default=None, help="default: every level")
    ap.add_argument("--cands", type=int, default=128)
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--chunk", type=int, default=128, help="candidates per batch")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/out/quan4/routing2"))
    args = ap.parse_args()

    data = json.loads(args.trips.read_text(encoding="utf-8"))
    targs = data["args"]
    cfg = replace(SimConfig(), horizon_s=float(targs["horizon"]), stuck_time_s=float(targs["teleport"]))
    dev = args.device
    g = load_graph(DEFAULT_GRAPH, cfg, device=dev)
    zones = pick_zones(g, int(targs["zones"]), seed=0)

    by_tph: dict[float, dict[int, dict]] = defaultdict(dict)
    for r in data["levels"]:
        by_tph[float(r["tph"])][int(r["seed"])] = r
    tphs = sorted(by_tph) if not args.tph else [float(t) for t in args.tph]
    all_seeds = sorted(next(iter(by_tph.values())))
    fit = args.fit_seeds or all_seeds[: max(1, len(all_seeds) // 2)]
    test = [s for s in all_seeds if s not in fit]
    print(f"[calib] device={dev} levels={tphs} fit={fit} test={test} cands={args.cands} "
          f"rounds={args.rounds}", flush=True)
    fit_lv = [Level(g, zones, cfg, t, by_tph[t], fit, dev) for t in tphs]

    gen = torch.Generator().manual_seed(args.seed)
    default = {k: float(getattr(cfg, k)) for k in ENV_PARAMS}
    best, best_loss = dict(default), math.inf
    history = []
    t0 = time.perf_counter()
    for rnd in range(args.rounds):
        cands = sample(args.cands, gen, None if rnd == 0 else best, 0.5 ** rnd)
        for k in ENV_PARAMS:  # keep the incumbent (round 0: the defaults) in the pool
            cands[k][0] = best[k]
        loss = evaluate(fit_lv, g, zones, cfg, cands, args.chunk)
        i = int(torch.argmin(loss))
        if float(loss[i]) < best_loss:
            best_loss = float(loss[i])
            best = {k: round(float(cands[k][i]), 4) for k in ENV_PARAMS}
        if rnd == 0:
            default_loss = float(loss[0])
        history.append({"round": rnd, "best_loss": round(best_loss, 4),
                        "median_loss": round(float(loss.median()), 4)})
        print(f"[calib] round={rnd} best_loss={best_loss:.4f} (mean 1 - R2 delay) "
              f"default_loss={default_loss:.4f} best={best} wall={time.perf_counter() - t0:.0f}s",
              flush=True)

    out = {"trips": str(args.trips), "args": {k: (str(v) if isinstance(v, Path) else v)
                                               for k, v in vars(args).items()},
           "fit_seeds": fit, "test_seeds": test, "box": BOX, "history": history,
           "default": default, "default_fit_loss": round(default_loss, 4),
           "best": best, "best_fit_loss": round(best_loss, 4), "test": {}}
    if test:
        pair = {k: torch.tensor([default[k], best[k]]) for k in ENV_PARAMS}
        for t in tphs:
            lv = Level(g, zones, cfg, t, by_tph[t], test, dev)
            m = lv.run(g, zones, cfg, pair)
            for j, name in enumerate(("default", "best")):
                row = lv.metrics(m[j])
                out["test"].setdefault(name, []).append(row)
                print(f"[test] {name} {row}", flush=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / f"calib_meso_{stamp}.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[calib] wrote {path}", flush=True)


if __name__ == "__main__":
    main()
