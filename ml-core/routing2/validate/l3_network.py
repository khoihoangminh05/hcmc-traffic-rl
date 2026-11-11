"""L3 on a corridor with its crossing streets: each stream's hourly flow inverted from its own Mapbox speed, then checks
that the inversion did not use.

Why: on Khánh Hội the peak delay sits where side streets join (VALIDATE_L3.md), so a corridor without cross traffic
cannot be tested. A stream is either a whole chain driven end to end, or a routed flow between an edge of one chain and
an edge of another (turning traffic), whose speed target is a chain it drives on. Each hour, all stream flows are bisected
together on a log scale until every target chain's simulated car speed equals its Mapbox speed.

Checks not used by the fit, per hour:
  * where the delay sits: Spearman, over the corridor's edges, between simulated and Mapbox extra time against 05h;
  * flows: the corridor's noon flow against its peak flow, to be read against camera counts by hand.

    python -m routing2.validate.l3_network --net DIR --obs edge_obs.csv --axes axes.json --counts counts.csv \\
        --streams streams.json --corridor "Khánh Hội|324" "Khánh Hội|142" --out DIR --hours 8 12 17
"""

from __future__ import annotations

import argparse
import json
import math
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from .l3_axis import MOTO, camera_profile, chain_speed, free_speeds, lane_counts, lane_lengths, mapbox_speeds, one

LO, HI = 20.0, 6000.0  # veh/h


def spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 4:
        return None
    ra, rb = pd.Series(a).rank().to_numpy(), pd.Series(b).rank().to_numpy()
    if ra.std() == 0 or rb.std() == 0:
        return None
    return round(float(np.corrcoef(ra, rb)[0, 1]), 2)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for k in ("net", "obs", "axes", "counts", "streams", "out"):
        ap.add_argument(f"--{k}", type=Path, required=True)
    ap.add_argument("--corridor", nargs="+", required=True, help="chains whose per-edge delay pattern is checked")
    ap.add_argument("--hours", type=int, nargs="+", default=[8, 12, 17])
    ap.add_argument("--iters", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--width", type=float, default=7.0, help="carriageway per direction on every chain (assumed)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--moto", default=MOTO)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    axes = json.loads(a.axes.read_text(encoding="utf-8"))
    streams = json.loads(a.streams.read_text(encoding="utf-8"))
    targets = sorted({s.get("target", s.get("chain")) for s in streams} | set(a.corridor))
    chains = {k: axes[k] for k in targets}
    net = a.net / "quan4_v5.net.xml"
    lengths, lanes = lane_lengths(net), lane_counts(net)
    table = mapbox_speeds(a.obs, {e for c in chains.values() for e in c})

    def mb(e: str, h: int) -> float | None:
        return float(table.loc[e, h]) if e in table.index and h in table.columns and pd.notna(table.loc[e, h]) else None

    free = {e: mb(e, 5) or 8.0 for c in chains.values() for e in c}
    free, fixed = free_speeds(free, chains)
    target = {n: {h: chain_speed(c, lengths, {e: mb(e, h) for e in c if mb(e, h)}, free) for h in a.hours} for n, c in chains.items()}
    share = camera_profile(a.counts).car_share

    def extra_flows(h: int, q: dict[str, float]) -> list[tuple]:
        out = []
        for s in streams:
            if "chain" not in s:
                fe = axes[s["from"][0]][s["from"][1]]
                te = axes[s["to"][0]][s["to"][1]]
                out.append((s["name"], fe, te, q[s["name"]]))
        return out

    def chain_scale(q: dict[str, float]) -> dict[str, float]:
        sc = {n: 0.0 for n in chains}
        for s in streams:
            if "chain" in s:
                sc[s["chain"]] = q[s["name"]]
        return sc

    base = dict(moto=a.moto, shape="net", alpha=1.0, width=a.width, seed=a.seed, green=0.5, arrivals="poisson", net=str(net),
                tls=str(a.net / f"tls_seed{a.seed}.add.xml"), chains=chains, lengths=lengths, lanes=lanes, free=free)
    lo = {(h, s["name"]): math.log(LO) for h in a.hours for s in streams}
    hi = {(h, s["name"]): math.log(HI) for h in a.hours for s in streams}
    last: dict[int, dict] = {}
    log = (a.out / "iters.jsonl").open("a", encoding="utf-8")
    print(f"[l3net] {len(streams)} streams, targets {targets}, free speed replaced on {fixed}", flush=True)
    with Pool(a.workers) as pool:
        for it in range(a.iters + 1):
            jobs = []
            for h in a.hours:
                q = {s["name"]: math.exp((lo[h, s["name"]] + hi[h, s["name"]]) / 2) for s in streams}
                jobs.append(base | dict(hour=h, profile={str(h): {"q": 1.0, "car_share": float(share[h])}}, scale=chain_scale(q),
                                        extra_flows=extra_flows(h, q), q=q))
            for job, r in zip(jobs, pool.map(one, jobs)):
                h = job["hour"]
                last[h] = r | {"q": job["q"]}
                row = {"iter": it, "hour": h, "teleports": r["teleports"], "depart_delay_s": r["depart_delay_s"], "streams": {}}
                for s in streams:
                    t = s.get("target", s.get("chain"))
                    v = r["sim"][f"car:{t}"]
                    row["streams"][s["name"]] = {"q": round(job["q"][s["name"]]), "sim": v, "map": round(target[t][h], 2)}
                    if it < a.iters and v is not None:
                        if v > target[t][h]:
                            lo[h, s["name"]] = math.log(job["q"][s["name"]])
                        else:
                            hi[h, s["name"]] = math.log(job["q"][s["name"]])
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                log.flush()
                print(row, flush=True)

    result: dict = {"streams": {}, "delay_pattern": {}}
    for h in a.hours:
        r = last[h]
        result["streams"][h] = {s["name"]: {"q": round(r["q"][s["name"]]), "sim": r["sim"][f"car:{s.get('target', s.get('chain'))}"],
                                            "map": round(target[s.get("target", s.get("chain"))][h], 2),
                                            "at_bound": min(abs(math.log(r["q"][s["name"]]) - math.log(x)) for x in (LO, HI)) < 0.3}
                                for s in streams}
        result["teleports_" + str(h)] = r["teleports"]
        for c in a.corridor:
            sim_x, map_x, top = [], [], []
            for e in chains[c]:
                L = lengths[e]
                v_sim = (r["per_edge"].get(e) or {}).get("v_car")
                m5, mh = mb(e, 5), mb(e, h)
                if L < 8 or not v_sim or not m5 or not mh:
                    continue
                sim_x.append(L / v_sim - L / free[e])
                map_x.append(L / mh - L / m5)
                top.append((round(map_x[-1], 1), round(sim_x[-1], 1), e))
            result["delay_pattern"][f"{c}|{h}"] = {
                "spearman": spearman(sim_x, map_x), "edges": len(sim_x),
                "sim_total_s": round(sum(sim_x), 1), "map_total_s": round(sum(map_x), 1),
                "top_map_edges": sorted(top, reverse=True)[:4],
            }
    (a.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1), flush=True)
    print("L3NET_DONE", flush=True)


if __name__ == "__main__":
    main()
