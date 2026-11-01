"""Fit the meso P2.3 terms to SUMO (batch, GPU).

Input: `sumo_trips_<stamp>.json` from routing2.sumo_check. The demand, zones and
free-flow routes are rebuilt from its args and checked against its free-flow
times, so meso and SUMO drive the same trips on the same routes.

Every parameter candidate runs as an env (MesoSim env_params) for each fit seed,
one batch per demand level. Objective (v2, 2026-11-01): mean over levels of
(1 - R^2 of link-delay cells) + |total delay error| / SUMO total delay, cells as in
routing2.edge_metrics (delay summed per link and 5-min entry bin). v1 fitted R^2 of
per-trip delay; per-trip delay is mostly driver noise (SUMO vs SUMO 0.64-0.86), and
the v1 optimum switched congestion off (R^2 near 0 beats congestion in the wrong
place), so v1 is not used. Search: uniform in the box (log-uniform for the scales),
then rounds that shrink the box around the best candidate.

P2 gate, per level on the test seeds: R^2 cell >= 0.8 x SUMO-vs-SUMO R^2 cell and
total delay within 15% of SUMO.

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
from .edge_metrics import cell_delay, cell_mask, cell_scores
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
    "alley_cap_scale": (0.5, 6.0, True),
    "gap_tc_s": (0.0, 10.0, False),
    # follow-up time: field values are 2-3 s (cars), motorbikes somewhat less
    "gap_tf_s": (1.5, 3.5, False),
}
BIN_S = 300.0
GATE_CEIL_FRAC = 0.8
GATE_TOTAL_ERR = 0.15
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

    def __init__(self, g, zones, cfg, tph: float, recs: dict[int, dict], seeds: list[int], dev: str,
                 name: str = ""):
        self.tph, self.seeds, self.name = tph, seeds, name or f"tph{tph:g}"
        d0 = make_demand(g, zones, seeds, tph, cfg.horizon_s, 1.0)
        sim0 = MesoSim(g, d0, zones, cfg)
        self.N = sim0.N
        if "routes" in recs[seeds[0]]:  # route sets other than free flow (2026-11-01+)
            L = max(len(r) for s in seeds for r in recs[s]["routes"])
            routes = torch.full((len(seeds) * self.N, max(1, L)), -1, dtype=torch.long)
            for j, s in enumerate(seeds):
                for i, r in zip(recs[s]["kept"], recs[s]["routes"]):
                    routes[j * self.N + i, : len(r)] = torch.tensor(r, dtype=torch.long)
                dep_now = sim0.dep_t[j * self.N + torch.tensor(recs[s]["kept"])].cpu()
                if not torch.allclose(dep_now, torch.tensor(recs[s]["dep"]), atol=0.01):
                    raise SystemExit(f"tph={tph} seed={s}: demand differs from the SUMO run")
            routes = routes.to(g.src.device)
        else:
            routes = free_flow_routes(g, sim0.free_tt(), zones, sim0.orig, sim0.dest_zone)
        ff_edge = g.length / g.v_free
        ff = torch.where(routes >= 0, ff_edge[routes.clamp(min=0)], 0.0).sum(1)
        self.routes = routes.view(len(seeds), self.N, -1)
        sumo_seeds = sorted({k for s in seeds for k in recs[s]["sumo_arrive"]}, key=int)
        H = cfg.horizon_s
        idx, dep, ffk, s_end, s_end2, s_ex, s_ex2 = [], [], [], [], [], [], []
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
            if "sumo_exits" not in r:
                raise SystemExit("trips file has no sumo_exits: rerun routing2.sumo_check (2026-11-01+)")
            s_ex += r["sumo_exits"][sumo_seeds[0]]
            if len(sumo_seeds) > 1:
                s_ex2 += r["sumo_exits"][sumo_seeds[1]]
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
        flat = self.routes.reshape(len(seeds) * self.N, -1)
        self.R = flat[self.idx]
        self.L = self.R.shape[1]
        self.E = g.n_edges
        self.ff_edge = g.length / g.v_free
        self.nb = max(1, math.ceil(H / BIN_S))
        self.mask = cell_mask(self.R, self.E, self.nb)
        self.c_ref = self._cells(self._ex(s_ex, dev))
        self.c_ref2 = self._cells(self._ex(s_ex2, dev)) if s_ex2 else None

    def _ex(self, rows: list[list[float]], dev: str) -> torch.Tensor:
        x = torch.full((len(rows), self.L), math.inf)
        for i, r in enumerate(rows):
            if r:
                x[i, : min(self.L, len(r))] = torch.tensor(r[: self.L])
        return x.to(dev)

    def _cells(self, exits: torch.Tensor) -> torch.Tensor:
        return cell_delay(self.R, self.dep, exits, self.ff_edge, self.H, BIN_S, self.E)

    def run(self, g, zones, cfg, cands: dict, edge_mult: torch.Tensor | None = None
            ) -> tuple[torch.Tensor, torch.Tensor]:
        """Meso end times [C, K] and link-delay cells [C, cells] for C candidates."""
        C = next(iter(cands.values())).numel()
        S = len(self.seeds)
        d = make_demand(g, zones, self.seeds * C, self.tph, cfg.horizon_s, 1.0)
        ep = {k: v.repeat_interleave(S) for k, v in cands.items()}
        sim = MesoSim(g, d, zones, cfg, env_params=ep, record_hops=self.L, edge_cap_mult=edge_mult)
        routes = self.routes.repeat(C, 1, 1).view(C * S * self.N, -1)
        sim.run(FixedRoute(routes))
        end = torch.where(sim.status == ARRIVED, sim.arrive_t, torch.full_like(sim.arrive_t, self.H))
        end = torch.clamp(end, max=self.H).view(C, S * self.N)
        ex = sim.hop_exit.view(C, S * self.N, self.L)[:, self.idx]
        return end[:, self.idx], self._cells(ex)

    def loss(self, cells: torch.Tensor) -> torch.Tensor:
        """(1 - R^2 of link-delay cells) + relative total-delay error, per candidate."""
        sc = cell_scores(self.c_ref, cells, self.mask)
        return (1.0 - sc["r2_cell"]) + sc["rel_err_total"]

    def metrics(self, m_end: torch.Tensor, cells: torch.Tensor) -> dict:
        """sumo_check-style metrics and the P2 gate for one candidate (m_end [K], cells [cells])."""
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
        sc = cell_scores(self.c_ref, cells, self.mask)
        row["r2_cell_delay"] = round(float(sc["r2_cell"]), 4)
        row["rel_err_total_delay"] = round(float(sc["rel_err_total"]), 4)
        row["total_delay_sumo_h"] = round(float(sc["total_delay_ref_s"]) / 3600, 2)
        row["total_delay_meso_h"] = round(float(sc["total_delay_est_s"]) / 3600, 2)
        if self.c_ref2 is not None:
            ss = cell_scores(self.c_ref, self.c_ref2, self.mask)
            row["r2_cell_delay_sumo_vs_sumo"] = round(float(ss["r2_cell"]), 4)
            row["rel_err_total_delay_sumo_vs_sumo"] = round(float(ss["rel_err_total"]), 4)
            row["gate_pass"] = bool(row["r2_cell_delay"] >= GATE_CEIL_FRAC * row["r2_cell_delay_sumo_vs_sumo"]
                                    and row["rel_err_total_delay"] <= GATE_TOTAL_ERR)
        return row


def evaluate(levels, g, zones, cfg, cands: dict, chunk: int, edge_mult=None) -> torch.Tensor:
    C = next(iter(cands.values())).numel()
    tot = torch.zeros(C)
    for lv in levels:
        for a in range(0, C, chunk):
            sub = {k: v[a:a + chunk] for k, v in cands.items()}
            tot[a:a + chunk] += lv.loss(lv.run(g, zones, cfg, sub, edge_mult)[1]).cpu()
    return tot / len(levels)


def edge_totals(lv, cells: torch.Tensor) -> torch.Tensor:
    """[E] delay summed over bins."""
    return cells.view(-1, lv.E, lv.nb).sum(-1).squeeze(0)


def fit_edge_mult(levels, g, zones, cfg, params: dict, iters: int, eta: float, smooth_s: float,
                  lo: float, hi: float) -> tuple[torch.Tensor, list]:
    """Stage 2: per-link capacity factors by damped multiplicative updates.

    A link where SUMO accumulates more delay than meso gets less outflow capacity (its
    queue forms in meso too), and the reverse: m_e <- m_e * ((D_meso + a) / (D_sumo + a))^eta,
    D summed over the fit levels, a = smooth_s keeps lightly used links near 1.
    The iterate with the lowest fit loss is kept.
    """
    dev = g.src.device
    one = {k: torch.tensor([float(v)]) for k, v in params.items()}
    ref = sum(edge_totals(lv, lv.c_ref) for lv in levels)
    m = torch.ones(g.n_edges, device=dev)
    best_m, best_loss, hist = m.clone(), math.inf, []
    for it in range(iters + 1):
        est = torch.zeros(g.n_edges, device=dev)
        loss = 0.0
        for lv in levels:
            _, cells = lv.run(g, zones, cfg, one, m)
            loss += float(lv.loss(cells)[0])
            est += edge_totals(lv, cells)
        loss /= len(levels)
        hist.append({"iter": it, "loss": round(loss, 4),
                     "m_p10_p50_p90": [round(float(x), 3) for x in torch.quantile(m, torch.tensor([0.1, 0.5, 0.9], device=dev))],
                     "m_below_0.9": int((m < 0.9).sum()), "m_above_1.1": int((m > 1.1).sum())})
        print(f"[edges] iter={it} loss={loss:.4f} {hist[-1]}", flush=True)
        if loss < best_loss:
            best_loss, best_m = loss, m.clone()
        if it == iters:
            break
        r = ((est + smooth_s) / (ref + smooth_s)).clamp(min=1e-3)
        m = torch.clamp(m * r**eta, lo, hi)
    return best_m, hist


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trips", type=Path, nargs="+", required=True, help="fit route sets (sumo_trips_*.json)")
    ap.add_argument("--test-trips", type=Path, nargs="*", default=[],
                    help="held-out route sets: every seed is a test seed")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--fit-seeds", type=int, nargs="*", default=None, help="default: first half")
    ap.add_argument("--tph", type=float, nargs="*", default=None, help="default: every level")
    ap.add_argument("--cands", type=int, default=128)
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--chunk", type=int, default=128, help="candidates per batch")
    ap.add_argument("--edge-iters", type=int, default=0,
                    help="stage 2 iterations (0 = off; diverged locally on 2026-11-01, see PLAN_V4)")
    ap.add_argument("--edge-eta", type=float, default=0.5)
    ap.add_argument("--edge-smooth-s", type=float, default=120.0)
    ap.add_argument("--edge-range", type=float, nargs=2, default=[0.1, 10.0])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", type=Path, default=Path("artifacts/out/quan4/routing2"))
    args = ap.parse_args()

    files = [json.loads(p.read_text(encoding="utf-8")) for p in args.trips]
    tfiles = [json.loads(p.read_text(encoding="utf-8")) for p in args.test_trips]
    targs = files[0]["args"]
    for f in files[1:] + tfiles:
        for k in ("horizon", "teleport", "zones"):
            if f["args"][k] != targs[k]:
                raise SystemExit(f"trips files disagree on {k}")
    cfg = replace(SimConfig(), horizon_s=float(targs["horizon"]), stuck_time_s=float(targs["teleport"]))
    dev = args.device
    g = load_graph(DEFAULT_GRAPH, cfg, device=dev)
    zones = pick_zones(g, int(targs["zones"]), seed=0)

    def by_level(data):
        out: dict[float, dict[int, dict]] = defaultdict(dict)
        for r in data["levels"]:
            out[float(r["tph"])][int(r["seed"])] = r
        return out

    def rs_name(data, p):
        a = data["args"]
        return f"rs{a.get('route_seed', 0)}_sig{a.get('route_sigma', 0.0):g}"

    fit_by = [(rs_name(f, p), by_level(f)) for f, p in zip(files, args.trips)]
    test_by = [(rs_name(f, p), by_level(f)) for f, p in zip(tfiles, args.test_trips)]
    tphs = sorted(fit_by[0][1]) if not args.tph else [float(t) for t in args.tph]
    all_seeds = sorted(next(iter(fit_by[0][1].values())))
    fit = args.fit_seeds or all_seeds[: max(1, len(all_seeds) // 2)]
    test = [s for s in all_seeds if s not in fit]
    print(f"[calib] device={dev} levels={tphs} route sets fit={[n for n, _ in fit_by]} "
          f"held-out={[n for n, _ in test_by]} fit seeds={fit} test seeds={test} cands={args.cands} "
          f"rounds={args.rounds} edge_iters={args.edge_iters}", flush=True)
    fit_lv = [Level(g, zones, cfg, t, b[t], fit, dev, f"{n}/tph{t:g}") for n, b in fit_by for t in tphs]

    gen = torch.Generator().manual_seed(args.seed)
    default = {k: float(getattr(cfg, k)) for k in ENV_PARAMS}
    best, best_loss = dict(default), math.inf
    history = []
    default_loss = math.nan
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
        print(f"[calib] round={rnd} best_loss={best_loss:.4f} (mean 1 - R2 cell + total err) "
              f"default_loss={default_loss:.4f} best={best} wall={time.perf_counter() - t0:.0f}s",
              flush=True)

    edge_mult, edge_hist = None, []
    if args.edge_iters > 0:
        edge_mult, edge_hist = fit_edge_mult(fit_lv, g, zones, cfg, best, args.edge_iters, args.edge_eta,
                                             args.edge_smooth_s, *args.edge_range)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = {"trips": [str(p) for p in args.trips], "test_trips": [str(p) for p in args.test_trips],
           "args": {k: (str(v) if isinstance(v, Path) else [str(x) for x in v] if isinstance(v, list)
                        and v and isinstance(v[0], Path) else v) for k, v in vars(args).items()},
           "fit_seeds": fit, "test_seeds": test, "box": BOX, "history": history,
           "default": default, "default_fit_loss": round(default_loss, 4),
           "best": best, "best_fit_loss": round(best_loss, 4), "edge_history": edge_hist, "test": {}}
    if edge_mult is not None:
        mpath = args.out_dir / f"edge_cap_mult_{stamp}.json"
        mpath.write_text(json.dumps({"graph": str(DEFAULT_GRAPH), "params": best,
                                     "mult": {g.edge_ids[e]: round(float(edge_mult[e]), 4)
                                              for e in range(g.n_edges)}}), encoding="utf-8")
        out["edge_cap_mult_file"] = str(mpath)
        print(f"[edges] wrote {mpath}", flush=True)

    # test: held-out demand seeds on the fit route sets, every seed on held-out route sets
    variants = [("default", default, None), ("best", best, None)]
    if edge_mult is not None:
        variants.append(("best_edges", best, edge_mult))
    test_lv = ([(n, t, b[t], test) for n, b in fit_by for t in tphs if test]
               + [(n, t, b[t], sorted(b[t])) for n, b in test_by for t in tphs if t in b])
    for n, t, recs, seeds in test_lv:
        lv = Level(g, zones, cfg, t, recs, seeds, dev, f"{n}/tph{t:g}")
        for name, prm, em in variants:
            pair = {k: torch.tensor([float(prm[k])]) for k in ENV_PARAMS}
            m, cells = lv.run(g, zones, cfg, pair, em)
            row = {"set": lv.name, "seeds": seeds, **lv.metrics(m[0], cells[0])}
            out["test"].setdefault(name, []).append(row)
            print(f"[test] {name} {row}", flush=True)

    final = "best_edges" if edge_mult is not None else "best"
    rows = out["test"].get(final, [])
    if rows:
        out["gate_variant"] = final
        out["gate_pass_all"] = all(r.get("gate_pass", False) for r in rows)
        for r in rows:
            print(f"[gate] {r['set']}: R2 cell {r['r2_cell_delay']} vs ceiling "
                  f"{r.get('r2_cell_delay_sumo_vs_sumo')} | total delay err {r['rel_err_total_delay']} "
                  f"| pass {r.get('gate_pass')}", flush=True)
        print(f"[gate] P2 ({final}) {'PASS' if out['gate_pass_all'] else 'FAIL'}", flush=True)
    path = args.out_dir / f"calib_meso_{stamp}.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[calib] wrote {path}", flush=True)


if __name__ == "__main__":
    main()
