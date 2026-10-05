"""One-shot audit: Mapbox + camera + density + graph readiness for train/paper."""

from __future__ import annotations

import csv
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    print("========== 1. MAPBOX RAW ==========")
    mb = ROOT / "ingestion-worker/data_raw/mapbox"
    for p in sorted(mb.glob("*.csv")):
        rows = list(csv.DictReader(p.open(encoding="utf-8")))
        if not rows:
            continue
        ok = sum(
            1
            for r in rows
            if "," in (r.get("origin") or "")
            and len((r.get("origin") or "").split(",")) == 2
        )
        zeros = sum(1 for r in rows if float(r.get("duration_sec") or 0) <= 0)
        pairs: dict[str, list[float]] = defaultdict(list)
        hours: Counter[str] = Counter()
        speeds: list[float] = []
        for r in rows:
            try:
                d = float(r["duration_sec"])
                dist = float(r["distance_m"])
            except (KeyError, TypeError, ValueError):
                continue
            pairs[r["od_id"]].append(d)
            hours[r["timestamp"][:13]] += 1
            if d > 0 and dist > 0:
                speeds.append(dist / d)
        pos = [sum(1 for x in v if x > 0) for v in pairs.values()]
        print(
            f"{p.name}: rows={len(rows)} od={len(pairs)} "
            f"quote_ok={ok}/{len(rows)} zero={zeros} ({100*zeros/len(rows):.1f}%)"
        )
        if pos:
            print(
                f"  pos/od: min={min(pos)} max={max(pos)} mean={st.mean(pos):.1f} "
                f"med={st.median(pos):.0f} | >=3:{sum(1 for c in pos if c>=3)} "
                f">=6:{sum(1 for c in pos if c>=6)} only0:{sum(1 for c in pos if c==0)}"
            )
        if speeds:
            print(
                f"  speed km/h: mean={st.mean(speeds)*3.6:.1f} "
                f"med={st.median(speeds)*3.6:.1f}"
            )
        print(f"  hours UTC: {dict(sorted(hours.items()))}")

    print("\n========== 2. COMBINED USABLE ==========")
    files = [
        "travel_time_2026-09-24.repaired.csv",
        "travel_time_2026-09-25.csv",
        "travel_time_2026-10-02.csv",
    ]
    allr: list[dict[str, str]] = []
    for f in files:
        p = mb / f
        if p.exists():
            allr += list(csv.DictReader(p.open(encoding="utf-8")))
    pairs2: dict[str, list[float]] = defaultdict(list)
    vn: Counter[int] = Counter()
    for r in allr:
        d = float(r["duration_sec"])
        pairs2[r["od_id"]].append(d)
        vn[(int(r["timestamp"][11:13]) + 7) % 24] += 1
    pos2 = [sum(1 for x in v if x > 0) for v in pairs2.values()]
    zpct = 100 * sum(1 for r in allr if float(r["duration_sec"]) <= 0) / max(len(allr), 1)
    print(f"rows={len(allr)} od={len(pairs2)} zero_pct={zpct:.1f}%")
    print(
        f"pos/od mean={st.mean(pos2):.1f} med={st.median(pos2):.0f} "
        f">=6:{sum(1 for c in pos2 if c>=6)}/{len(pos2)} "
        f"only0:{sum(1 for c in pos2 if c==0)}"
    )
    print(f"VN hour hist: {dict(sorted(vn.items()))}")

    print("\n========== 3. DENSITY FUSION ==========")
    dens_path = ROOT / "ml-core/artifacts/out/quan4/density/alley_density_latest.json"
    meta_path = ROOT / "ml-core/artifacts/out/quan4/density/density_meta.json"
    dens = json.loads(dens_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    print("meta:", json.dumps(meta, ensure_ascii=False))
    src = Counter(r["source"] for r in dens)
    ks = [float(r["density_k"]) for r in dens]
    vs = [float(r["speed_mps"]) for r in dens]
    obs = [r for r in dens if r["source"] == "observed"]
    oks = [float(r["density_k"]) for r in obs]
    ovs = [float(r["speed_mps"]) for r in obs]
    print(f"alleys={len(dens)} sources={dict(src)}")
    print(
        f"k all: mean={st.mean(ks):.4f} med={st.median(ks):.4f} "
        f"[{min(ks):.4f},{max(ks):.4f}]"
    )
    print(f"v km/h all: mean={st.mean(vs)*3.6:.1f} med={st.median(vs)*3.6:.1f}")
    print(
        f"obs n={len(obs)} k mean={st.mean(oks):.4f} "
        f"v mean={st.mean(ovs)*3.6:.1f} km/h"
    )
    us = sorted({round(float(r["uncertainty"]), 6) for r in dens})
    print(f"uncertainty n_unique={len(us)} values={us[:5]}")
    print(
        f"k free<=0.01: {sum(1 for k in ks if k<=0.01)}; "
        f"jam>=0.15: {sum(1 for k in ks if k>=0.15)}"
    )
    snaps = sorted((ROOT / "ml-core/artifacts/out/quan4/density").glob("alley_density_20*.json"))
    print("snapshots:", [s.name for s in snaps])

    print("\n========== 4. GRAPH vs DENSITY ==========")
    g = json.loads((ROOT / "ml-core/artifacts/out/quan4/alley_graph.json").read_text(encoding="utf-8"))
    dens_ids = {r["alley_id"] for r in dens}
    graph_ids = set(g["alleys"])
    print(
        f"nodes={len(g['nodes'])} edges={len(g['edge_list'])} "
        f"alleys_dict={len(g['alleys'])}"
    )
    print(
        f"density cover: {len(dens_ids & graph_ids)}/{len(graph_ids)} "
        f"({100*len(dens_ids)/len(graph_ids):.1f}%)"
    )
    print(f"missing density (MARL default k): {len(graph_ids - dens_ids)}")
    G = nx.DiGraph()
    for e in g["edge_list"]:
        G.add_edge(e["u"], e["v"])
    wcc = list(nx.weakly_connected_components(G))
    largest = max(len(c) for c in wcc)
    print(
        f"WCC={len(wcc)} largest={largest} "
        f"({100*largest/G.number_of_nodes():.1f}% nodes)"
    )

    print("\n========== 5. CAMERA ==========")
    cam = ROOT / "ingestion-worker/data_raw/camera"
    if cam.exists():
        total = 0
        for d in sorted(cam.iterdir()):
            if not d.is_dir():
                continue
            files = [f for f in d.rglob("*") if f.is_file()]
            total += len(files)
            sizes = [f.stat().st_size for f in files]
            print(
                f"{d.name}: n={len(files)} mean_kb={st.mean(sizes)/1024:.0f} "
                f"empty={sum(1 for s in sizes if s < 1000)}"
            )
        print(f"TOTAL frames={total} — NOT used in density fusion")
    else:
        print("no camera dir")

    print("\n========== 6. TIME MIXING ==========")
    p = mb / "travel_time_2026-10-02.csv"
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    morning = sum(1 for r in rows if int(r["timestamp"][11:13]) < 6)
    evening = sum(1 for r in rows if int(r["timestamp"][11:13]) >= 10)
    print(
        f"2026-10-02 morningUTC<06:{morning} eveningUTC>=10:{evening} "
        f"— fusion averages ALL into one k (bucket={meta.get('time_bucket')})"
    )

    print("\n========== VERDICT KEYS ==========")
    print(
        json.dumps(
            {
                "observed_pct": round(100 * len(obs) / len(dens), 2),
                "pos_samples_mean": round(st.mean(pos2), 2),
                "pos_ge6_pct": round(100 * sum(1 for c in pos2 if c >= 6) / len(pos2), 1),
                "density_graph_cover_pct": round(100 * len(dens_ids) / len(graph_ids), 1),
                "camera_in_fusion": False,
                "time_bucketed_latest": False,
                "uncertainty_informative": len(us) > 3,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
