"""L2-B: export largest weakly-connected component as train graph.

Cuts Quận 4 fragmentation (hundreds of WCCs) down to one connected twin domain.
Optionally keep alley-layer edges only (+ 1-hop local/spine for connectivity).
Also subsets density JSON and Mapbox seed lists to alley_ids in the subgraph.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import networkx as nx


def _is_alley(a: dict[str, Any]) -> bool:
    return a.get("layer") == "alley" or a.get("road_class") == "alley"


def build_nx(payload: dict[str, Any]) -> nx.DiGraph:
    g = nx.DiGraph()
    alleys = payload.get("alleys") or {}
    for e in payload.get("edge_list") or []:
        aid = e.get("alley_id")
        if not aid:
            continue
        a = alleys.get(aid) or {}
        g.add_edge(
            str(e["u"]),
            str(e["v"]),
            alley_id=str(aid),
            length_m=float(a.get("length_m") or 0.0),
            layer=str(a.get("layer") or ""),
            road_class=str(a.get("road_class") or ""),
        )
    return g


def largest_wcc_nodes(g: nx.DiGraph) -> set[str]:
    if g.number_of_nodes() == 0:
        return set()
    comps = list(nx.weakly_connected_components(g))
    best = max(comps, key=len)
    return {str(n) for n in best}


def select_edges(
    payload: dict[str, Any],
    nodes: set[str],
    *,
    alley_core: bool,
    hop1: bool,
) -> tuple[list[dict[str, str]], set[str]]:
    """Return edge_list subset + alley_id set."""
    alleys = payload.get("alleys") or {}
    edges_in = [
        e
        for e in (payload.get("edge_list") or [])
        if str(e["u"]) in nodes and str(e["v"]) in nodes
    ]
    if not alley_core:
        aids = {str(e["alley_id"]) for e in edges_in}
        return edges_in, aids

    # Alley edges inside WCC
    alley_edges = [
        e
        for e in edges_in
        if _is_alley(alleys.get(str(e["alley_id"])) or {})
    ]
    if not hop1:
        aids = {str(e["alley_id"]) for e in alley_edges}
        return alley_edges, aids

    # 1-hop: any non-alley edge that touches an alley endpoint already kept
    alley_nodes: set[str] = set()
    for e in alley_edges:
        alley_nodes.add(str(e["u"]))
        alley_nodes.add(str(e["v"]))
    extra = [
        e
        for e in edges_in
        if (str(e["u"]) in alley_nodes or str(e["v"]) in alley_nodes)
        and e not in alley_edges
    ]
    chosen = alley_edges + extra
    aids = {str(e["alley_id"]) for e in chosen}
    return chosen, aids


def rebuild_neighbors(alleys: dict[str, Any], edge_list: list[dict[str, str]]) -> None:
    """Rewrite neighbors to only ids present in the subgraph."""
    # adjacency via shared nodes
    node_to_aids: dict[str, set[str]] = {}
    for e in edge_list:
        aid = str(e["alley_id"])
        for n in (str(e["u"]), str(e["v"])):
            node_to_aids.setdefault(n, set()).add(aid)
    aid_set = set(alleys)
    for aid, a in alleys.items():
        touch: set[str] = set()
        # find nodes of this alley
        for e in edge_list:
            if str(e["alley_id"]) != aid:
                continue
            for n in (str(e["u"]), str(e["v"])):
                touch |= node_to_aids.get(n, set())
        touch.discard(aid)
        a["neighbors"] = sorted(x for x in touch if x in aid_set)


def export_wcc_subgraph(
    graph_path: Path,
    output_dir: Path,
    *,
    alley_core: bool = True,
    hop1: bool = True,
    density_paths: list[Path] | None = None,
    seeds_path: Path | None = None,
    od_pairs_path: Path | None = None,
) -> dict[str, Any]:
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    g_full = build_nx(payload)
    wcc_nodes = largest_wcc_nodes(g_full)
    n_wcc = len(list(nx.weakly_connected_components(g_full)))

    edge_list, aid_set = select_edges(
        payload, wcc_nodes, alley_core=alley_core, hop1=hop1
    )
    # Final cut: alley_core+hop1 can fragment — keep largest WCC of selection
    g_sel = nx.DiGraph()
    for e in edge_list:
        g_sel.add_edge(str(e["u"]), str(e["v"]), alley_id=str(e["alley_id"]))
    if g_sel.number_of_nodes() > 0:
        keep_nodes = largest_wcc_nodes(g_sel)
        edge_list = [
            e
            for e in edge_list
            if str(e["u"]) in keep_nodes and str(e["v"]) in keep_nodes
        ]
        aid_set = {str(e["alley_id"]) for e in edge_list}

    # nodes actually used by selected edges
    used_nodes: set[str] = set()
    for e in edge_list:
        used_nodes.add(str(e["u"]))
        used_nodes.add(str(e["v"]))

    alleys_src = payload.get("alleys") or {}
    alleys = {aid: dict(alleys_src[aid]) for aid in aid_set if aid in alleys_src}
    rebuild_neighbors(alleys, edge_list)

    out_payload: dict[str, Any] = {
        k: v
        for k, v in payload.items()
        if k not in ("nodes", "alleys", "edge_list", "nodes_geo")
    }
    out_payload["nodes"] = sorted(used_nodes)
    out_payload["alleys"] = alleys
    out_payload["edge_list"] = edge_list
    out_payload["l2"] = {
        "mode": "wcc_subgraph",
        "alley_core": alley_core,
        "hop1": hop1,
        "source_graph": str(graph_path),
        "full_wcc_count": n_wcc,
        "full_nodes": g_full.number_of_nodes(),
        "full_edges": g_full.number_of_edges(),
        "wcc_nodes_raw": len(wcc_nodes),
        "subgraph_nodes": len(used_nodes),
        "subgraph_edges": len(edge_list),
        "subgraph_alleys": len(alleys),
    }
    if "nodes_geo" in payload and isinstance(payload["nodes_geo"], dict):
        out_payload["nodes_geo"] = {
            n: payload["nodes_geo"][n]
            for n in used_nodes
            if n in payload["nodes_geo"]
        }

    # verify single WCC
    g_sub = build_nx(out_payload)
    sub_wcc = list(nx.weakly_connected_components(g_sub)) if g_sub.number_of_nodes() else []
    out_payload["l2"]["subgraph_wcc_count"] = len(sub_wcc)
    out_payload["l2"]["subgraph_largest_wcc"] = max((len(c) for c in sub_wcc), default=0)

    output_dir.mkdir(parents=True, exist_ok=True)
    graph_out = output_dir / "alley_graph_wcc.json"
    graph_out.write_text(json.dumps(out_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # OD pairs (alley endpoints) inside subgraph
    nest_od: list[dict[str, str]] = []
    for aid, alley in alleys.items():
        if alley_core and not _is_alley(alley):
            continue
        entry, ex = alley.get("entry"), alley.get("exit")
        if not entry or not ex:
            continue
        nest_od.append(
            {
                "odId": aid,
                "origin": f"{float(entry['lon']):.6f},{float(entry['lat']):.6f}",
                "destination": f"{float(ex['lon']):.6f},{float(ex['lat']):.6f}",
            }
        )
    od_out = output_dir / "od_pairs_wcc.json"
    od_out.write_text(json.dumps(nest_od, indent=2, ensure_ascii=False), encoding="utf-8")

    # Filter existing full od_pairs if provided
    if od_pairs_path and od_pairs_path.exists():
        full_od = json.loads(od_pairs_path.read_text(encoding="utf-8"))
        filtered = [r for r in full_od if (r.get("odId") or r.get("od_id")) in aid_set]
        (output_dir / "od_pairs_wcc_from_full.json").write_text(
            json.dumps(filtered, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    seeds_out = None
    if seeds_path and seeds_path.exists():
        seeds = json.loads(seeds_path.read_text(encoding="utf-8"))
        kept = [r for r in seeds if (r.get("odId") or r.get("od_id")) in aid_set]
        seeds_out = output_dir / "od_pairs.quan4.seeds_wcc.json"
        seeds_out.write_text(json.dumps(kept, indent=2, ensure_ascii=False), encoding="utf-8")

    dens_outs: list[str] = []
    for dp in density_paths or []:
        if not dp.exists():
            continue
        rows = json.loads(dp.read_text(encoding="utf-8"))
        kept_rows = [r for r in rows if r.get("alley_id") in aid_set]
        # L2-A lite: prior fill for alleys missing from density
        have = {r["alley_id"] for r in kept_rows}
        for aid, a in alleys.items():
            if aid in have:
                continue
            length = float(a.get("length_m") or 0)
            k = 0.05 if length < 80 else 0.035
            kept_rows.append(
                {
                    "alley_id": aid,
                    "timestamp": "",
                    "time_bucket": "l2_prior",
                    "length_m": length,
                    "layer": str(a.get("layer") or ""),
                    "highway": str(a.get("highway") or ""),
                    "name": str(a.get("name") or ""),
                    "density_k": k,
                    "speed_mps": round(8.0 * (1.0 - k / 0.18), 4),
                    "uncertainty": 0.05,
                    "source": "prior",
                }
            )
        out_p = output_dir / f"{dp.stem}_wcc{dp.suffix}"
        out_p.write_text(json.dumps(kept_rows, indent=2, ensure_ascii=False), encoding="utf-8")
        dens_outs.append(str(out_p))

    meta = {
        "l2": out_payload["l2"],
        "graph_out": str(graph_out),
        "od_pairs_out": str(od_out),
        "od_pairs_count": len(nest_od),
        "seeds_out": str(seeds_out) if seeds_out else None,
        "seeds_kept": (
            len(json.loads(seeds_out.read_text(encoding="utf-8"))) if seeds_out else None
        ),
        "density_outs": dens_outs,
        "pass_single_wcc": out_payload["l2"]["subgraph_wcc_count"] == 1,
    }
    meta_path = output_dir / "l2_wcc_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="L2-B export largest WCC train subgraph")
    p.add_argument(
        "--graph",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "alley_graph.json",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "wcc",
    )
    p.add_argument(
        "--full-wcc",
        action="store_true",
        help="Keep all layers in largest WCC (not alley-core)",
    )
    p.add_argument(
        "--no-hop1",
        action="store_true",
        help="Alley-core only, no 1-hop local/spine edges",
    )
    p.add_argument(
        "--density",
        type=Path,
        nargs="*",
        default=[],
        help="Density JSON file(s) to subset (+ prior-fill missing)",
    )
    p.add_argument(
        "--seeds",
        type=Path,
        default=root.parent / "ingestion-worker" / "config" / "od_pairs.quan4.seeds.json",
    )
    p.add_argument(
        "--od-pairs",
        type=Path,
        default=root / "artifacts" / "out" / "quan4" / "od_pairs.json",
    )
    args = p.parse_args()
    export_wcc_subgraph(
        args.graph,
        args.output,
        alley_core=not args.full_wcc,
        hop1=not args.no_hop1,
        density_paths=list(args.density or []),
        seeds_path=args.seeds if args.seeds.exists() else None,
        od_pairs_path=args.od_pairs if args.od_pairs.exists() else None,
    )


if __name__ == "__main__":
    main()
