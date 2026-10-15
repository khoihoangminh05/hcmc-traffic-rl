"""Export fused alley density to SUMO network/routes XML (offline twin)."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import networkx as nx

from data_fusion.alley_graph import load_or_build_graph


def _load_density_rows(density_json: Path) -> list[dict[str, Any]]:
    if not density_json.exists():
        return []
    return json.loads(density_json.read_text(encoding="utf-8"))


def _density_speed_map(rows: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in rows:
        aid = r.get("alley_id")
        if not aid:
            continue
        try:
            out[str(aid)] = float(r["speed_mps"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _clamp_speed(speed: float, lo: float = 0.5, hi: float = 13.0) -> float:
    return max(lo, min(hi, speed))


def _is_alley_edge(data: dict[str, Any]) -> bool:
    return data.get("road_class") == "alley" or data.get("layer") == "alley"


def write_net_xml(
    graph_path: Path | None,
    out_net: Path,
    density_by_id: dict[str, float] | None = None,
) -> None:
    g = load_or_build_graph(graph_path)
    density_by_id = density_by_id or {}
    # Minimal SUMO net — enough for smoke / MARL wrappers
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<net version="1.16" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/net_file.xsd">',
        '  <location netOffset="0.0,0.0" convBoundary="0.00,0.00,400.00,200.00" '
        'origBoundary="0.00,0.00,400.00,200.00" projParameter="!"/>',
    ]

    # Place nodes on a simple grid by index
    node_xy: dict[str, tuple[float, float]] = {}
    for i, n in enumerate(sorted(g.nodes())):
        node_xy[n] = (float((i % 5) * 80), float((i // 5) * 60))

    for n, (x, y) in node_xy.items():
        lines.append(
            f'  <junction id="{n}" type="priority" x="{x:.2f}" y="{y:.2f}" '
            f'incLanes="" intLanes="" '
            f'shape="{x-2:.2f},{y-2:.2f} {x+2:.2f},{y-2:.2f} '
            f'{x+2:.2f},{y+2:.2f} {x-2:.2f},{y+2:.2f}"/>'
        )

    edge_uv: list[tuple[str, str, str]] = []
    for u, v, data in g.edges(data=True):
        aid = str(data["alley_id"])
        length = float(data["length_m"])
        if aid in density_by_id:
            speed = _clamp_speed(float(density_by_id[aid]))
        else:
            speed = 8.0 if _is_alley_edge(data) else 13.0
        x1, y1 = node_xy[u]
        x2, y2 = node_xy[v]
        shape = f"{x1:.2f},{y1:.2f} {x2:.2f},{y2:.2f}"
        lines.append(
            f'  <edge id="{aid}" from="{u}" to="{v}" priority="1">'
            f'<lane id="{aid}_0" index="0" speed="{speed:.2f}" length="{length:.2f}" '
            f'shape="{shape}"/>'
            f"</edge>"
        )
        edge_uv.append((aid, str(u), str(v)))

    # Junction connections so multi-edge routes are valid in SUMO
    incoming: dict[str, list[str]] = {}
    outgoing: dict[str, list[str]] = {}
    for aid, u, v in edge_uv:
        outgoing.setdefault(u, []).append(aid)
        incoming.setdefault(v, []).append(aid)
    for node in node_xy:
        for frm in incoming.get(node, []):
            for to in outgoing.get(node, []):
                if frm == to:
                    continue
                lines.append(
                    f'  <connection from="{frm}" to="{to}" fromLane="0" toLane="0" '
                    f'dir="s" state="M"/>'
                )

    lines.append("</net>")
    out_net.parent.mkdir(parents=True, exist_ok=True)
    out_net.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _project_m(lon: float, lat: float, lon0: float, lat0: float) -> tuple[float, float]:
    import math

    x = (lon - lon0) * 111_320.0 * math.cos(math.radians(lat0))
    y = (lat - lat0) * 110_540.0
    return x, y


def write_geo_signal_net(
    graph_path: Path,
    signals_path: Path,
    out_net: Path,
    cycle_s: float = 60.0,
    red_s: float = 30.0,
) -> dict[str, Any]:
    """Quận 4 net in local metres, with a static program on snapped OSM signals.

    Signals are not actuated. The same cycle, red time, and offset are what
    the next-hop env uses, so Dijkstra, greedy_load, and MAPPO wait on the
    same red.
    """
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    g = _nx_from_payload(payload)
    sig = json.loads(signals_path.read_text(encoding="utf-8")) if signals_path.exists() else {}
    offsets: dict[str, float] = {}
    for row in sig.get("signals") or []:
        node = str(row.get("node") or "")
        if node:
            offsets[node] = float(row.get("offset_s") or 0.0)
    cycle_s = float(sig.get("cycle_s") or cycle_s)
    red_s = float(sig.get("red_s") or red_s)
    yellow_s = 3.0
    green_s = max(1.0, cycle_s - red_s - yellow_s)
    geo = payload.get("nodes_geo") or {}
    lons = [float(v["lon"]) for v in geo.values()]
    lats = [float(v["lat"]) for v in geo.values()]
    lon0 = min(lons) if lons else 106.70
    lat0 = min(lats) if lats else 10.75
    node_xy: dict[str, tuple[float, float]] = {}
    missing = 0
    for i, n in enumerate(sorted(g.nodes())):
        rec = geo.get(n) or geo.get(str(n))
        if rec is None:
            missing += 1
            node_xy[n] = (float((i % 40) * 25), float((i // 40) * 25))
        else:
            node_xy[n] = _project_m(float(rec["lon"]), float(rec["lat"]), lon0, lat0)
    xs = [p[0] for p in node_xy.values()]
    ys = [p[1] for p in node_xy.values()]
    boundary = f"{min(xs):.2f},{min(ys):.2f},{max(xs):.2f},{max(ys):.2f}"

    edge_uv: list[tuple[str, str, str]] = []
    incoming: dict[str, list[str]] = {}
    outgoing: dict[str, list[str]] = {}
    for u, v, data in g.edges(data=True):
        aid = str(data["alley_id"])
        edge_uv.append((aid, str(u), str(v)))
        outgoing.setdefault(str(u), []).append(aid)
        incoming.setdefault(str(v), []).append(aid)

    controlled: dict[str, list[tuple[str, str]]] = {}
    for node in node_xy:
        if node not in offsets:
            continue
        links = []
        for frm in incoming.get(node, []):
            for to in outgoing.get(node, []):
                if frm == to:
                    continue
                links.append((frm, to))
        if links:
            controlled[node] = links

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<net version="1.16" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/net_file.xsd">',
        f'  <location netOffset="0.0,0.0" convBoundary="{boundary}" '
        f'origBoundary="{boundary}" projParameter="!"/>',
    ]
    for node, links in sorted(controlled.items()):
        n_links = len(links)
        offset = offsets[node] % cycle_s
        lines.append(
            f'  <tlLogic id="{node}" type="static" programID="0" offset="{offset:.0f}">'
            f'<phase duration="{red_s:.0f}" state="{"r" * n_links}"/>'
            f'<phase duration="{green_s:.0f}" state="{"G" * n_links}"/>'
            f'<phase duration="{yellow_s:.0f}" state="{"y" * n_links}"/>'
            f"</tlLogic>"
        )
    for n, (x, y) in node_xy.items():
        kind = "traffic_light" if n in controlled else "priority"
        tl = f' tl="{n}"' if n in controlled else ""
        lines.append(
            f'  <junction id="{n}" type="{kind}" x="{x:.2f}" y="{y:.2f}"{tl} '
            f'incLanes="" intLanes="" '
            f'shape="{x-2:.2f},{y-2:.2f} {x+2:.2f},{y-2:.2f} '
            f'{x+2:.2f},{y+2:.2f} {x-2:.2f},{y+2:.2f}"/>'
        )
    for aid, u, v in edge_uv:
        length = float(g.edges[u, v]["length_m"])
        speed = 8.0 if _is_alley_edge(g.edges[u, v]) else 13.0
        x1, y1 = node_xy[u]
        x2, y2 = node_xy[v]
        lines.append(
            f'  <edge id="{aid}" from="{u}" to="{v}" priority="1">'
            f'<lane id="{aid}_0" index="0" speed="{speed:.2f}" length="{length:.2f}" '
            f'shape="{x1:.2f},{y1:.2f} {x2:.2f},{y2:.2f}"/>'
            f"</edge>"
        )
    for node in node_xy:
        links = controlled.get(node)
        if links is None:
            for frm in incoming.get(node, []):
                for to in outgoing.get(node, []):
                    if frm == to:
                        continue
                    lines.append(
                        f'  <connection from="{frm}" to="{to}" fromLane="0" toLane="0" '
                        f'dir="s" state="M"/>'
                    )
            continue
        for idx, (frm, to) in enumerate(links):
            lines.append(
                f'  <connection from="{frm}" to="{to}" fromLane="0" toLane="0" '
                f'tl="{node}" linkIndex="{idx}" dir="s" state="o"/>'
            )
    lines.append("</net>")
    out_net.parent.mkdir(parents=True, exist_ok=True)
    out_net.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "signals": len(controlled),
        "missing_xy": missing,
        "net": str(out_net),
    }


def write_routes_from_density(density_json: Path, out_routes: Path) -> None:
    """Demo routes (hcmc_alley_demo) — keep hardcoded main_* spine."""
    rows = _load_density_rows(density_json)

    alleys = [
        r
        for r in rows
        if r.get("road_class") == "alley" or r.get("layer") == "alley"
    ]
    alleys_sorted = sorted(alleys, key=lambda r: float(r.get("density_k", 1.0)))
    via = [a["alley_id"] for a in alleys_sorted[:3]]

    root = ET.Element("routes")
    ET.SubElement(
        root,
        "vType",
        id="moto",
        accel="1.5",
        decel="3.5",
        sigma="0.3",
        length="2.0",
        maxSpeed="12",
    )

    edges_main = "main_01 main_02 main_03"
    edges_alley = " ".join(via) if via else edges_main
    ET.SubElement(root, "route", id="r_main", edges=edges_main)
    ET.SubElement(root, "route", id="r_alley", edges=edges_alley)
    ET.SubElement(root, "vehicle", id="veh0", type="moto", route="r_main", depart="0")
    ET.SubElement(root, "vehicle", id="veh1", type="moto", route="r_alley", depart="2")

    tree = ET.ElementTree(root)
    out_routes.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out_routes, encoding="utf-8", xml_declaration=True)


def _load_graph_payload(graph_path: Path) -> dict[str, Any]:
    return json.loads(graph_path.read_text(encoding="utf-8"))


def _nx_from_payload(payload: dict[str, Any]) -> nx.DiGraph:
    g = nx.DiGraph()
    alleys = payload.get("alleys") or {}
    for e in payload.get("edge_list") or []:
        aid = e["alley_id"]
        a = alleys.get(aid, {})
        g.add_edge(
            str(e["u"]),
            str(e["v"]),
            alley_id=aid,
            length_m=float(a.get("length_m") or 10.0),
            road_class=str(a.get("road_class") or ""),
            layer=str(a.get("layer") or ""),
        )
    return g


def _seed_endpoints(
    seeds: list[dict[str, Any]], alleys: dict[str, Any]
) -> list[tuple[str, str, str]]:
    """Return (od_id, u, v) for seeds present in the graph."""
    out: list[tuple[str, str, str]] = []
    for s in seeds:
        od = str(s.get("odId") or s.get("od_id") or "")
        if not od or od not in alleys:
            continue
        a = alleys[od]
        u, v = str(a.get("u") or ""), str(a.get("v") or "")
        if u and v:
            out.append((od, u, v))
    return out


def _edge_path(
    g: nx.DiGraph,
    origin: str,
    dest: str,
    speed_map: dict[str, float],
    prefer_alley: bool,
) -> list[str] | None:
    def weight(u: str, v: str, data: dict[str, Any]) -> float:
        aid = data["alley_id"]
        length = float(data["length_m"])
        speed = _clamp_speed(speed_map.get(aid, 8.0 if _is_alley_edge(data) else 13.0))
        tt = length / speed
        if prefer_alley and not _is_alley_edge(data):
            tt += 5.0
        if not prefer_alley and _is_alley_edge(data):
            tt += 8.0
        return tt

    try:
        nodes = nx.shortest_path(g, origin, dest, weight=weight)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    edges: list[str] = []
    for a, b in zip(nodes[:-1], nodes[1:]):
        edges.append(str(g.edges[a, b]["alley_id"]))
    return edges if edges else None


def write_quan4_routes(
    graph_path: Path,
    density_json: Path,
    seeds_path: Path | None,
    out_routes: Path,
    max_routes: int = 3,
) -> list[dict[str, Any]]:
    """Topology-valid Quận 4 routes from seed OD endpoints + density speeds."""
    payload = _load_graph_payload(graph_path)
    alleys = payload.get("alleys") or {}
    g = _nx_from_payload(payload)
    speed_map = _density_speed_map(_load_density_rows(density_json))

    seeds: list[dict[str, Any]] = []
    if seeds_path and seeds_path.exists():
        seeds = json.loads(seeds_path.read_text(encoding="utf-8"))
    endpoints = _seed_endpoints(seeds, alleys)
    if not endpoints:
        # Fallback: first few alley edges
        for aid, a in list(alleys.items())[:20]:
            if a.get("road_class") == "alley" or a.get("layer") == "alley":
                endpoints.append((aid, str(a["u"]), str(a["v"])))

    root = ET.Element("routes")
    ET.SubElement(
        root,
        "vType",
        id="moto",
        accel="1.5",
        decel="3.5",
        sigma="0.3",
        length="2.0",
        maxSpeed="12",
    )

    built: list[dict[str, Any]] = []
    # Prefer multi-hop connected pairs, then single-edge seed trips
    candidates: list[tuple[str, str, str]] = []
    n = len(endpoints)
    for i in range(n):
        od_i, u, _ = endpoints[i]
        for j in range(i + 1, n):
            od_j, _, v = endpoints[j]
            if u != v and nx.has_path(g, u, v):
                candidates.append((f"{od_i}__{od_j}", u, v))
                break
        od, u, v = endpoints[i]
        candidates.append((od, u, v))

    seen_edges: set[str] = set()
    for od_label, origin, dest in candidates:
        if len(built) >= max_routes:
            break
        if origin == dest:
            continue
        edges_main = _edge_path(g, origin, dest, speed_map, prefer_alley=False)
        edges_alley = _edge_path(g, origin, dest, speed_map, prefer_alley=True)
        path = edges_alley or edges_main
        if not path:
            continue
        key = " ".join(path)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        rid = f"r_{len(built)}"
        ET.SubElement(root, "route", id=rid, edges=key)
        ET.SubElement(
            root,
            "vehicle",
            id=f"veh{len(built)}",
            type="moto",
            route=rid,
            depart=str(float(len(built) * 2)),
        )
        built.append(
            {
                "route_id": rid,
                "od_label": od_label,
                "origin": origin,
                "destination": dest,
                "n_edges": len(path),
                "edges": path,
            }
        )

    if not built:
        # Last resort: any single graph edge
        for u, v, data in g.edges(data=True):
            aid = data["alley_id"]
            ET.SubElement(root, "route", id="r_0", edges=aid)
            ET.SubElement(root, "vehicle", id="veh0", type="moto", route="r_0", depart="0")
            built.append(
                {
                    "route_id": "r_0",
                    "od_label": aid,
                    "origin": u,
                    "destination": v,
                    "n_edges": 1,
                    "edges": [aid],
                }
            )
            break

    out_routes.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(out_routes, encoding="utf-8", xml_declaration=True)
    return built


def write_sumocfg(net: Path, routes: Path, out_cfg: Path, sumo_env: Path | None = None) -> None:
    """Write sumocfg with paths relative to sumo-env/ when possible."""
    if sumo_env is None:
        sumo_env = out_cfg.parent
    try:
        net_rel = net.resolve().relative_to(sumo_env.resolve()).as_posix()
        routes_rel = routes.resolve().relative_to(sumo_env.resolve()).as_posix()
    except ValueError:
        net_rel = net.name
        routes_rel = routes.name
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <input>
    <net-file value="{net_rel}"/>
    <route-files value="{routes_rel}"/>
  </input>
  <time>
    <begin value="0"/>
    <end value="300"/>
  </time>
</configuration>
"""
    out_cfg.parent.mkdir(parents=True, exist_ok=True)
    out_cfg.write_text(content, encoding="utf-8")


def export_twin(
    density: Path,
    graph: Path | None,
    networks_dir: Path,
    routes_dir: Path,
    prefix: str = "hcmc_alley_demo",
    seeds: Path | None = None,
) -> dict[str, Any]:
    sumo_env = networks_dir.parent
    net = networks_dir / f"{prefix}.net.xml"
    routes = routes_dir / f"{prefix}.rou.xml"
    cfg = sumo_env / f"{prefix}.sumocfg"

    rows = _load_density_rows(density)
    speed_map = _density_speed_map(rows)

    write_net_xml(graph, net, density_by_id=speed_map)

    route_meta: list[dict[str, Any]] = []
    if prefix.startswith("quan4") and graph and graph.exists():
        route_meta = write_quan4_routes(graph, density, seeds, routes)
    else:
        write_routes_from_density(density, routes)

    write_sumocfg(net, routes, cfg, sumo_env=sumo_env)

    non_default = sum(1 for s in speed_map.values() if abs(s - 8.0) > 1e-3)
    return {
        "net": str(net),
        "routes": str(routes),
        "cfg": str(cfg),
        "prefix": prefix,
        "density_speeds": len(speed_map),
        "non_default_speeds": non_default,
        "routes_built": route_meta,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SUMO twin artifacts from fusion")
    parser.add_argument("--density", type=Path, required=True, help="alley_density.json")
    parser.add_argument("--graph", type=Path, default=None)
    parser.add_argument(
        "--prefix",
        type=str,
        default="hcmc_alley_demo",
        help="Output basename (e.g. hcmc_alley_demo or quan4_alleys)",
    )
    parser.add_argument(
        "--seeds",
        type=Path,
        default=None,
        help="OD seeds JSON (Quận 4 route builder)",
    )
    parser.add_argument(
        "--networks-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "sumo-env" / "networks",
    )
    parser.add_argument(
        "--routes-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "sumo-env" / "routes",
    )
    args = parser.parse_args()

    meta = export_twin(
        density=args.density,
        graph=args.graph,
        networks_dir=args.networks_dir,
        routes_dir=args.routes_dir,
        prefix=args.prefix,
        seeds=args.seeds,
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
