"""OSM turn restrictions mapped onto the graph's links (batch, Node 2).

Input: Overpass JSON of relation[type=restriction] with `out geom`, and the graph JSON. Output: one record per
restriction: from link, to link(s), via, whether it binds motorcycles and cars, and the time window. A link is
matched at the via node by its end segment lying on the member way (within --tol-m). Restrictions with a via
way are kept as link sequences. Unmatched relations are counted and listed, never dropped silently.

    python -m data_fusion.turn_restrictions --osm restr.json --graph alley_graph_full_z.json --out turn_bans.json
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path


def dist_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot((a[0] - b[0]) * 109300.0, (a[1] - b[1]) * 110574.0)


def on_way(p: tuple[float, float], way: list[tuple[float, float]], tol: float) -> bool:
    """Is p within tol metres of the polyline?"""
    px, py = p[0] * 109300.0, p[1] * 110574.0
    for (ax, ay), (bx, by) in zip(way, way[1:]):
        ax, ay, bx, by = ax * 109300.0, ay * 110574.0, bx * 109300.0, by * 110574.0
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / max(dx * dx + dy * dy, 1e-9)))
        if math.hypot(px - ax - t * dx, py - ay - t * dy) <= tol:
            return True
    return False


def binds(tags: dict[str, str]) -> dict[str, bool]:
    ex = set((tags.get("except") or "").replace(" ", "").split(";"))
    moto_only = "restriction:motorcycle" in tags
    car_only = "restriction:motorcar" in tags
    return {"motorcycle": ("motorcycle" not in ex and not car_only) or moto_only, "car": ("motorcar" not in ex and not moto_only) or car_only}


def rule(tags: dict[str, str]) -> tuple[str, str | None]:
    """(kind, time window or None)."""
    for k, v in tags.items():
        if k.startswith("restriction") and k not in ("restriction:conditional",):
            return v, None
    v = tags.get("restriction:conditional", "")
    if "@" in v:
        kind, when = v.split("@", 1)
        return kind.strip(), when.strip(" ()")
    return v.strip(), None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--osm", type=Path, required=True)
    ap.add_argument("--graph", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tol-m", type=float, default=4.0)
    args = ap.parse_args()
    G = json.loads(args.graph.read_text(encoding="utf-8"))
    alleys = G["alleys"]
    into: dict[str, list[str]] = {}
    outof: dict[str, list[str]] = {}
    for e in G["edge_list"]:
        into.setdefault(str(e["v"]), []).append(e["alley_id"])
        outof.setdefault(str(e["u"]), []).append(e["alley_id"])

    def seg_point(aid: str, at_end: bool) -> tuple[float, float]:
        c = alleys[aid]["coordinates"]
        return tuple(c[-2] if at_end else c[1]) if len(c) >= 2 else tuple(c[0])

    out, why = [], Counter()
    for r in json.loads(args.osm.read_text(encoding="utf-8"))["elements"]:
        m = {"from": [], "to": [], "via": []}
        for x in r["members"]:
            if x["role"] in m:
                m[x["role"]].append(x)
        kind, when = rule(r["tags"])
        rec = {"osm": r["id"], "kind": kind, "when": when, "binds": binds(r["tags"])}
        if not m["from"] or not m["to"] or not m["via"]:
            why["incomplete relation"] += 1
            continue
        geom = lambda x: [(g["lon"], g["lat"]) for g in x.get("geometry", []) if g]  # noqa: E731
        fw, tw = geom(m["from"][0]), geom(m["to"][0])
        if m["via"][0]["type"] == "node":
            v = str(m["via"][0]["ref"])
            if v not in into or v not in outof:
                why["via node not in graph (outside the net or simplified away)"] += 1
                continue
            f = [a for a in into[v] if on_way(seg_point(a, True), fw, args.tol_m)]
            t = [a for a in outof[v] if on_way(seg_point(a, False), tw, args.tol_m)]
            if not f or not t:
                why["no link matches the member way"] += 1
                continue
            out.append({**rec, "via": v, "from": f, "to": t})
        else:
            vw = geom(m["via"][0])
            f = [a for n in into for a in into[n] if on_way(seg_point(a, True), fw, args.tol_m) and on_way(tuple(alleys[a]["coordinates"][-1]), vw, args.tol_m)]
            t = [a for n in outof for a in outof[n] if on_way(seg_point(a, False), tw, args.tol_m) and on_way(tuple(alleys[a]["coordinates"][0]), vw, args.tol_m)]
            if not f or not t:
                why["via way: no link matches"] += 1
                continue
            out.append({**rec, "via_way": m["via"][0]["ref"], "from": f, "to": t})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"bans": out, "unmatched": dict(why)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"matched": len(out), "unmatched": dict(why),
                      "binds_motorcycle": sum(x["binds"]["motorcycle"] for x in out), "binds_car": sum(x["binds"]["car"] for x in out),
                      "timed": sum(x["when"] is not None for x in out), "kinds": Counter(x["kind"] for x in out).most_common()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
