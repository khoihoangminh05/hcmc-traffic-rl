"""Measured rules on the Quận 4 SUMO network: turn bans and signal cycles (batch, Node 2).

Input: the plain node and edge files of a network, OSM turn bans (`data_fusion.turn_restrictions`), measured cycles,
camera positions and the graph with node positions. Output in --out:

  quan4_v5.net.xml     network without internal links (G1), with the bans that bind every vehicle removed
  tls_seed<N>.add.xml  signal programs; load after the network, one file per sampled configuration
  tls_sources.csv      per signal: cycle, where it came from, offset
  route_bans.json      bans SUMO cannot enforce on this network, for whoever generates the routes
  report.json          counts of everything applied and everything not applied

Bans active at --at only: SUMO connections cannot change during a run. Car-only bans cannot be physically enforced:
without internal links SUMO ignores per-class connection permissions (tested on SUMO 1.28), so they go to
route_bans.json. A ban over two consecutive links (via way) also goes there, as a forbidden link sequence.

OSM splits one crossing into several signal nodes, often with a single approach each, and netconvert sees no conflict
between them: its programs have almost no red (76 of 80 nodes at or below 15%) or are all green once joined. Signal
nodes closer than CLUSTER_M therefore share one controller with our own two-phase program, approaches grouped by road
axis. The equal green split is an assumption.

Signals without a measurement take a cycle drawn from the measured cycles. Offsets and green splits are unmeasured:
offsets are drawn per seed, greens are split equally between the two axes.

With --free-obs, an edge with a Mapbox speed at --free-hour gets that speed as its free speed instead of the class value,
except where it is far below its neighbours on the same road: that is junction delay placed on a short edge, and as a
speed limit it would cap the discharge (found on Khánh Hội, VALIDATE_L3.md).

    python -m routing2.net_rules --plain DIR --bans turn_bans.json --graph graph.json --out DIR --at 08:00 --seeds 0 1 2
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from xml.sax.saxutils import quoteattr

from .sumo_net import sumo_binary

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CYCLES = Path(__file__).with_name("signal_cycles_2026-11-09.json")
DEFAULT_CAMERAS = REPO / "ingestion-worker" / "config" / "cameras.quan4_real.json"
CLUSTER_M = 40.0  # signal nodes this close belong to one intersection
CAMERA_M = 60.0  # a camera measures the intersection with a signal node this close
YELLOW_S = 3


def active(when: str | None, at: str) -> bool:
    """Is a rule with windows like "06:00-09:00,16:00-19:00" (None = always) in force at HH:MM?"""
    if when is None:
        return True

    def minutes(s: str) -> int:
        h, m = s.strip().split(":")
        return int(h) * 60 + int(m)

    t = minutes(at)
    return any(minutes(w.split("-")[0]) <= t < minutes(w.split("-")[1]) for w in when.split(","))


def split_bans(bans: list[dict], at: str, succ: dict[str, set[str]]) -> dict:
    """Sorts the bans active at `at` by how they can be applied. `succ` is edge -> edges it connects to."""
    out: dict = {"delete": set(), "car_pairs": set(), "moto_pairs": set(), "chains": [], "inactive": [], "no_link": [], "unhandled": []}
    for b in bans:
        if not active(b["when"], at):
            out["inactive"].append(b["osm"])
            continue
        pairs = [(f, t) for f in b["from"] for t in b["to"] if t in succ.get(f, ())]
        moto, car = b["binds"]["motorcycle"], b["binds"]["car"]
        if not pairs:
            out["no_link"].append(b["osm"])
        elif len(pairs) == 1:
            out["delete" if moto and car else "car_pairs" if car else "moto_pairs"].add(pairs[0])
        elif len(pairs) == 2 and (pairs[0][1] == pairs[1][0] or pairs[1][1] == pairs[0][0]):
            first, second = pairs if pairs[0][1] == pairs[1][0] else pairs[::-1]
            out["chains"].append({"osm": b["osm"], "links": [first[0], first[1], second[1]], "motorcycle": moto, "car": car})
        else:
            out["unhandled"].append(b["osm"])
    return out


def axis_groups(headings: dict[str, float]) -> dict[str, int]:
    """Approach edge -> 0 or 1, splitting compass headings (degrees) into two road axes. Opposite directions share one."""
    def spread(ref: float) -> float:
        return sum(math.cos(2 * math.radians(h - ref)) ** 2 for h in headings.values())

    ref = max(sorted(headings.values()), key=spread)
    return {e: 0 if abs((h - ref + 90) % 180 - 90) < 45 else 1 for e, h in headings.items()}


def two_axis_phases(links: list[dict], group: dict[str, int], cycle: float, yellow: int = YELLOW_S, share0: float = 0.5) -> list[tuple[int, str]]:
    """(duration, state) of a two-phase program, axis 0 getting `share0` of the green. `links` is ordered by linkIndex, each with
    "from" and "dir". Links missing from `group` join two signal nodes inside the crossing and stay green. Left turns
    and U-turns are permissive. With one axis only, the second phase is red for that axis (unmodelled side street or
    pedestrians)."""
    total = round(cycle)
    if total - 2 * yellow < 2:
        raise ValueError(f"cycle {cycle} too short")
    green = min(max(1, round((total - 2 * yellow) * share0)), total - 2 * yellow - 1) if share0 != 0.5 else (total - 2 * yellow) // 2

    def state(axis: int, ch: str) -> str:
        out = ""
        for k in links:
            g = group.get(k["from"])
            if g is None:
                out += "G"
            elif g != axis:
                out += "r"
            elif ch == "G" and k["dir"] in ("l", "L", "t"):
                out += "g"
            else:
                out += ch
        return out

    return [(green, state(0, "G")), (yellow, state(0, "y")), (total - green - 2 * yellow, state(1, "G")), (yellow, state(1, "y"))]


def clusters(points: dict[str, tuple[float, float]], radius_m: float) -> dict[str, int]:
    """Node -> cluster number, joining nodes closer than radius_m (lon, lat points)."""
    parent = {n: n for n in points}

    def find(n: str) -> str:
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    names = sorted(points)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if dist_m(points[a], points[b]) <= radius_m:
                parent[find(a)] = find(b)
    roots = {r: i for i, r in enumerate(sorted({find(n) for n in names}))}
    return {n: roots[find(n)] for n in names}


def dist_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot((a[0] - b[0]) * 109300.0, (a[1] - b[1]) * 110574.0)


def net_links(net: Path) -> tuple[dict[str, set[str]], list[ET.Element]]:
    root = ET.parse(net).getroot()
    edges = {e.get("id") for e in root.iter("edge") if e.get("function") != "internal"}
    succ: dict[str, set[str]] = defaultdict(set)
    for c in root.iter("connection"):
        if c.get("from") in edges and c.get("to") in edges:
            succ[c.get("from")].add(c.get("to"))
    return succ, root.findall("tlLogic")


def largest_scc(succ: dict[str, set[str]]) -> int:
    """Size of the largest strongly connected set of edges (iterative Kosaraju)."""
    nodes = set(succ) | {v for s in succ.values() for v in s}
    pred: dict[str, list[str]] = defaultdict(list)
    for u, s in succ.items():
        for v in s:
            pred[v].append(u)
    seen, order = set(), []
    for start in sorted(nodes):
        if start in seen:
            continue
        seen.add(start)
        stack = [(start, iter(sorted(succ.get(start, ()))))]
        while stack:
            u, it = stack[-1]
            v = next((x for x in it if x not in seen), None)
            if v is None:
                order.append(u)
                stack.pop()
            else:
                seen.add(v)
                stack.append((v, iter(sorted(succ.get(v, ())))))
    done, best = set(), 0
    for start in reversed(order):
        if start in done:
            continue
        size, stack = 0, [start]
        done.add(start)
        while stack:
            u = stack.pop()
            size += 1
            for v in pred[u]:
                if v not in done:
                    done.add(v)
                    stack.append(v)
        best = max(best, size)
    return best


def signal_nodes(plain: Path) -> list[str]:
    return sorted(n.get("id") for n in ET.parse(plain / "quan4.nod.xml").getroot() if n.get("type") == "traffic_light")


def write_joined_nodes(plain: Path, out: Path, tl_of: dict[str, str]) -> Path:
    """Copy of the node file in which each signal node names its shared controller."""
    root = ET.parse(plain / "quan4.nod.xml").getroot()
    for n in root:
        if n.get("id") in tl_of:
            n.set("tl", tl_of[n.get("id")])
    path = out / "quan4_v5.nod.xml"
    ET.ElementTree(root).write(path, encoding="utf-8")
    return path


def hour_speeds(obs: Path, hour: int) -> dict[str, float]:
    """Edge -> median Mapbox speed (m/s) for trips departing in that local hour."""
    by: dict[str, list[float]] = defaultdict(list)
    with obs.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("depart_at") and int(r["depart_at"][11:13]) == hour:
                by[r["alley_id"]].append(float(r["speed_mps"]))
    return {e: sorted(v)[len(v) // 2] if len(v) % 2 else sum(sorted(v)[len(v) // 2 - 1: len(v) // 2 + 1]) / 2 for e, v in by.items()}


def road_neighbours(edges: dict[str, tuple[str, str, str]], hops: int = 2) -> dict[str, list[str]]:
    """Edge -> edges up to `hops` steps before and after it on the same road: same priority, no U-turn."""
    out_of, into = defaultdict(list), defaultdict(list)
    for e, (u, v, _) in edges.items():
        out_of[u].append(e)
        into[v].append(e)
    res = {}
    for e, (u, v, p) in edges.items():
        found = []
        for step, back in ((lambda x: out_of[edges[x][1]], lambda x, y: edges[y][1] != edges[x][0]),
                           (lambda x: into[edges[x][0]], lambda x, y: edges[y][0] != edges[x][1])):
            front = [e]
            for _ in range(hops):
                front = [y for x in front for y in step(x) if edges[y][2] == p and back(x, y) and y != e]
                found += front
        res[e] = list(dict.fromkeys(found))
    return res


def free_speeds(v: dict[str, float], neighbours: dict[str, list[str]], ratio: float = 0.6) -> tuple[dict[str, float], list[str]]:
    """Measured speeds with junction delay removed: an edge below `ratio` x the median of its measured neighbours takes
    that median."""
    out, fixed = dict(v), []
    for e, x in v.items():
        near = sorted(v[n] for n in neighbours.get(e, []) if n in v)
        if near:
            m = near[len(near) // 2] if len(near) % 2 else (near[len(near) // 2 - 1] + near[len(near) // 2]) / 2
            if x < ratio * m:
                out[e] = m
                fixed.append(e)
    return out, fixed


def write_edges(plain: Path, out: Path, one_lane: bool, speeds: dict[str, float]) -> Path:
    """The plain edges with each direction as one lane as wide as the carriageway (one_lane) and measured free speeds.

    One lane: OSM lane counts change along a road where the pavement does not, and netconvert then joins only one lane
    across the change, which makes a lane drop that does not exist. Motorcycles do not keep to lanes, and L1 and L2
    validated one wide lane."""
    root = ET.parse(plain / "quan4.edg.xml").getroot()
    for e in root.iter("edge"):
        if one_lane:
            n = int(e.get("numLanes", "1"))
            e.set("width", f'{float(e.get("width", "3.2")) * n:.2f}')
            e.set("numLanes", "1")
        if e.get("id") in speeds:
            e.set("speed", f'{speeds[e.get("id")]:.2f}')
    path = out / "edges.edg.xml"
    ET.ElementTree(root).write(path, encoding="unicode")
    return path


def build(plain: Path, out: Path, delete: set[tuple[str, str]], tl_of: dict[str, str], name: str = "quan4_v5.net.xml", one_lane: bool = False,
          speeds: dict[str, float] | None = None) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    edges = write_edges(plain, out, one_lane, speeds) if one_lane or speeds else plain / "quan4.edg.xml"
    nod = write_joined_nodes(plain, out, tl_of)
    con = out / "quan4_v5.con.xml"
    con.write_text(
        "<connections>\n"
        + "".join(f"  <delete from={quoteattr(f)} to={quoteattr(t)}/>\n" for f, t in sorted(delete))
        + "</connections>\n",
        encoding="utf-8",
    )
    net = out / name
    cmd = [
        sumo_binary("netconvert"), "--node-files", str(nod), "--edge-files", str(edges),
        "--connection-files", str(con), "--output-file", str(net), "--junctions.join", "false", "--geometry.remove", "false",
        "--offset.disable-normalization", "true", "--default.junctions.radius", "1.5", "--junctions.corner-detail", "0",
        "--tls.default-type", "static", "--tls.cycle.time", "60", "--no-internal-links", "true", "--no-warnings", "true",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return net


def assign_cycles(tls: list[str], geo: dict, cameras: list[dict], measured: list[dict]) -> tuple[dict[str, dict], list[dict]]:
    """Signal id -> measured cycle and camera; also one row per camera saying what it matched."""
    pts = {t: (float(geo[t]["lon"]), float(geo[t]["lat"])) for t in tls}
    cl = clusters(pts, CLUSTER_M)
    by_cam = {c["cameraId"]: (float(c["lon"]), float(c["lat"])) for c in cameras if "lon" in c}
    got: dict[str, dict] = {}
    rows = []
    for m in measured:
        p = by_cam[m["camera"]]
        near = [t for t in tls if dist_m(p, pts[t]) <= CAMERA_M]
        hit = {cl[t] for t in near}
        nodes = sorted(t for t in tls if cl[t] in hit)
        rows.append({"camera": m["camera"], "cycle_s": m["cycle_s"], "nearest_m": round(min(dist_m(p, q) for q in pts.values())), "signals": len(nodes)})
        for t in nodes:
            if t in got and got[t]["cycle_s"] != m["cycle_s"]:
                raise ValueError(f"signal {t}: cameras {got[t]['camera']} and {m['camera']} disagree")
            got.setdefault(t, {**m})
    return got, rows


def inner_nodes(members: set[str], succ: dict[str, set[str]], signal: set[str], xy: dict[str, tuple[float, float]], radius_m: float) -> set[str]:
    """Signal nodes of one controller plus the unsignalled nodes reached from them without leaving radius_m of a member.

    OSM often places an unsignalled node between two signal nodes of one crossing. An edge starting there is inside the
    crossing, not an approach, otherwise traffic meets a second stop line a few metres after the first.
    """
    seen, todo = set(members), list(members)
    while todo:
        for v in succ.get(todo.pop(), ()):
            if v not in seen and v not in signal and min(math.dist(xy[v], xy[m]) for m in members) <= radius_m:
                seen.add(v)
                todo.append(v)
    return seen


def tl_links(root: ET.Element, tl_of: dict[str, str]) -> tuple[dict[str, list[dict]], dict[str, dict[str, int]]]:
    """Controller -> links by linkIndex, and controller -> approach edge -> axis. Edges that start inside the crossing
    are not approaches."""
    edge = {e.get("id"): e for e in root.iter("edge") if e.get("function") != "internal"}
    node_xy = {j.get("id"): (float(j.get("x")), float(j.get("y"))) for j in root.iter("junction") if j.get("type") != "internal"}
    succ: dict[str, set[str]] = defaultdict(set)
    for e in edge.values():
        succ[e.get("from")].add(e.get("to"))
    raw: dict[str, list[ET.Element]] = defaultdict(list)
    for c in root.iter("connection"):
        if c.get("tl"):
            raw[c.get("tl")].append(c)
    links, groups = {}, {}
    for tl, cs in raw.items():
        cs.sort(key=lambda c: int(c.get("linkIndex")))
        links[tl] = [{"from": c.get("from"), "dir": c.get("dir")} for c in cs]
        heading = {}
        inner = inner_nodes({n for n, t in tl_of.items() if t == tl}, succ, set(tl_of), node_xy, CLUSTER_M)
        for e in {c.get("from") for c in cs}:
            if edge[e].get("from") in inner:
                continue
            xy = [tuple(map(float, q.split(","))) for q in edge[e].find("lane").get("shape").split()]
            (x0, y0), (x1, y1) = xy[-2], xy[-1]
            heading[e] = math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360
        groups[tl] = axis_groups(heading) if heading else {}
    return links, groups


def axis_share(group: dict[str, int], priority: dict[str, int], major_share: float) -> float:
    """Green share of axis 0: `major_share` if its highest approach class is above axis 1's, its complement if below,
    0.5 if equal or one axis only. The split is unmeasured (VALIDATE_L3.md); major_share = 0.5 is the equal split."""
    top = {}
    for e, ax in group.items():
        top[ax] = max(top.get(ax, 0), priority.get(e, 0))
    if len(top) < 2 or top[0] == top[1]:
        return 0.5
    return major_share if top[0] > top[1] else 1 - major_share


def write_programs(path: Path, links: dict[str, list[dict]], groups: dict[str, dict[str, int]], cycles: dict[str, tuple[float, str, str]], seed: int,
                   priority: dict[str, int] | None = None, major_share: float = 0.5) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    with path.open("w", encoding="utf-8") as f:
        f.write("<additional>\n")
        for tl in sorted(links):
            cycle, src, cam = cycles[tl]
            share0 = axis_share(groups[tl], priority or {}, major_share)
            phases = two_axis_phases(links[tl], groups[tl], cycle, share0=share0)
            total = sum(d for d, _ in phases)
            offset = int(rng.random() * total)
            f.write(f'  <tlLogic id={quoteattr(tl)} type="static" programID="measured" offset="{offset}">\n')
            f.writelines(f'    <phase duration="{d}" state="{s}"/>\n' for d, s in phases)
            f.write("  </tlLogic>\n")
            rows.append({"tl": tl, "cycle_s": total, "source": src, "camera": cam, "offset_s": offset, "approaches": len(groups[tl]), "axes": len(set(groups[tl].values()))})
        f.write("</additional>\n")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plain", type=Path, required=True, help="directory with quan4.nod.xml and quan4.edg.xml")
    ap.add_argument("--bans", type=Path, required=True)
    ap.add_argument("--graph", type=Path, required=True, help="graph JSON with nodes_geo")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--at", default="08:00", help="HH:MM; time-windowed bans in force at this time are applied")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0])
    ap.add_argument("--one-lane", action="store_true", help="each direction is one lane as wide as the carriageway")
    ap.add_argument("--free-obs", type=Path, help="Mapbox edge_obs.csv; edges in it get a measured free speed")
    ap.add_argument("--free-hour", type=int, default=5)
    ap.add_argument("--major-share", type=float, default=0.5, help="green share of the higher-class axis at a crossing of unequal classes")
    ap.add_argument("--cycles", type=Path, default=DEFAULT_CYCLES)
    ap.add_argument("--cameras", type=Path, default=DEFAULT_CAMERAS)
    a = ap.parse_args()

    bans = json.loads(a.bans.read_text(encoding="utf-8"))
    geo = json.loads(a.graph.read_text(encoding="utf-8"))["nodes_geo"]
    nodes = signal_nodes(a.plain)
    cl = clusters({t: (float(geo[t]["lon"]), float(geo[t]["lat"])) for t in nodes}, CLUSTER_M)
    tl_of = {t: f"i{c}" for t, c in cl.items()}
    speeds, fixed, n_obs = None, [], 0
    if a.free_obs:
        plain_edges = {e.get("id"): (e.get("from"), e.get("to"), e.get("priority")) for e in ET.parse(a.plain / "quan4.edg.xml").getroot().iter("edge")}
        measured = {e: s for e, s in hour_speeds(a.free_obs, a.free_hour).items() if e in plain_edges}
        n_obs = len(measured)
        speeds, fixed = free_speeds(measured, road_neighbours(plain_edges))
    base = build(a.plain, a.out, set(), tl_of, name="base.net.xml", one_lane=a.one_lane, speeds=speeds)
    succ0, _ = net_links(base)
    sp = split_bans(bans["bans"], a.at, succ0)
    net = build(a.plain, a.out, sp["delete"], tl_of, one_lane=a.one_lane, speeds=speeds)
    base.unlink()
    succ1, logics = net_links(net)
    links, groups = tl_links(ET.parse(net).getroot(), tl_of)
    priority = {e.get("id"): int(e.get("priority", "0")) for e in ET.parse(net).getroot().iter("edge") if e.get("function") != "internal"}

    measured = json.loads(a.cycles.read_text(encoding="utf-8"))["cameras"]
    got, cam_rows = assign_cycles(nodes, geo, json.loads(a.cameras.read_text(encoding="utf-8")), measured)
    got_tl = {tl_of[n]: v for n, v in got.items()}
    tls = sorted(links)
    pool = sorted({m["cycle_s"] for m in measured})
    for seed in a.seeds:
        rng = random.Random(seed)
        cycles = {
            t: (got_tl[t]["cycle_s"], f"measured_{got_tl[t]['level']}", got_tl[t]["camera"]) if t in got_tl else (rng.choice(pool), "drawn_from_measured", "")
            for t in tls
        }
        rows = write_programs(a.out / f"tls_seed{seed}.add.xml", links, groups, cycles, seed, priority, a.major_share)
        if seed == a.seeds[0]:
            with (a.out / "tls_sources.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)

    (a.out / "route_bans.json").write_text(
        json.dumps(
            {"at": a.at, "car_pairs": sorted(sp["car_pairs"]), "moto_pairs": sorted(sp["moto_pairs"]), "chains": sp["chains"]},
            ensure_ascii=False, indent=1,
        ),
        encoding="utf-8",
    )
    report = {
        "at": a.at,
        "bans_total": len(bans["bans"]),
        "bans_unmatched_on_graph": bans["unmatched"],
        "deleted_connections": len(sp["delete"]),
        "route_level_car_pairs": len(sp["car_pairs"]),
        "route_level_moto_pairs": len(sp["moto_pairs"]),
        "route_level_chains": len(sp["chains"]),
        "inactive_at_this_time": len(sp["inactive"]),
        "no_link_in_net": sp["no_link"],
        "unhandled": sp["unhandled"],
        "connections_before": sum(map(len, succ0.values())),
        "connections_after": sum(map(len, succ1.values())),
        "edges_largest_scc_before": largest_scc(succ0),
        "edges_largest_scc_after": largest_scc(succ1),
        "signal_nodes": len(nodes),
        "controllers": len(tls),
        "controllers_measured": len(got_tl),
        "controllers_by_axes": Counter(len(set(g.values())) for g in groups.values()),
        "controllers_measured_levels": Counter(v["level"] for v in got_tl.values()),
        "cameras": cam_rows,
        "cycle_pool_s": pool,
        "one_lane": a.one_lane,
        "major_share": a.major_share,
        "free_speed_edges_measured": n_obs,
        "free_speed_edges_junction_delay_replaced": fixed,
    }
    (a.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "cameras"}, ensure_ascii=False, indent=1), flush=True)
    print("NET_RULES_DONE", flush=True)


if __name__ == "__main__":
    main()
