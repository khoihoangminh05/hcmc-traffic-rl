"""L4 demand for one hour on the whole network: SUMO trips (batch).

Traffic from other districts enters at the graph's gates, grouped by bridge or road (GROUPS); a `--through` share
of it leaves by a gate of another group, the rest ends at an internal zone. The same flow leaves each group from
inside the district (the peak is not assumed one-way). Internal trips start at core nodes weighted by incident alley
length (population proxy, assumed) and end at internal zones. Departures are Poisson over warm-up plus one hour. Cars
start and end only on edges that allow them. Every level is an assumption until L4 calibration (L4_DESIGN.md).

    python -m routing2.validate.l4_demand --graph graph.json --net net.xml --flows flows.json --out trips.xml
"""

from __future__ import annotations

import argparse
import json
import random
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from .l3_axis import MOTO
from .common import vtypes

# Gate group -> road names of the gate's edges. Alley-only gates take the group of their major road.
GROUPS = {
    "d1_center": {"Tôn Đức Thắng", "Hàm Nghi", "Nguyễn Huệ", "Pasteur", "Nam Kỳ Khởi Nghĩa"},
    "calmette_kycon": {"Ký Con", "Calmette", "Cầu Calmette", "Nguyễn Công Trứ"},
    "ong_lanh": {"Cầu Ông Lãnh", "Nguyễn Thái Học", "Cô Giang"},
    "nvc": {"Nguyễn Văn Cừ", "Cầu Nguyễn Văn Cừ"},
    "ho_hao_hon": {"Hồ Hảo Hớn"},
    "vvk_west": {"Võ Văn Kiệt"},
    "kenh_te": {"Cầu Kênh Tẻ"},
    "tan_thuan": {"Cầu Tân Thuận 1", "Cầu Tân Thuận 2", "Huỳnh Tấn Phát"},
}


def gate_groups(g: dict) -> dict[str, dict[str, list[str]]]:
    """Group -> {"in": gate nodes, "out": gate nodes}."""
    names: dict[str, set[str]] = defaultdict(set)  # every edge at the node, both directions
    for a in g["alleys"].values():
        names[a["u"]].add(a["name"])
        names[a["v"]].add(a["name"])
    res: dict[str, dict[str, list[str]]] = {k: {"in": [], "out": []} for k in GROUPS}
    for side, nodes in (("in", g["gates_in"]), ("out", g["gates_out"])):
        for n in nodes:
            hit = [k for k, v in GROUPS.items() if v & names[n]]
            if len(hit) != 1:
                raise ValueError(f"gate {n} ({side}) matches {hit} by names {names[n]}")
            res[hit[0]][side].append(n)
    return res


def edges_by_node(net: Path) -> tuple[dict, dict, set[str]]:
    """Node -> outgoing / incoming edge ids, and edges a passenger car may use."""
    out_of, into, car_ok = defaultdict(list), defaultdict(list), set()
    for e in ET.parse(net).getroot().iter("edge"):
        if e.get("function") == "internal":
            continue
        out_of[e.get("from")].append(e.get("id"))
        into[e.get("to")].append(e.get("id"))
        lane = e.find("lane")
        allow, disallow = lane.get("allow"), lane.get("disallow")
        if (allow is None or "passenger" in allow.split()) and (disallow is None or "passenger" not in disallow.split()):
            car_ok.add(e.get("id"))
    return out_of, into, car_ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--graph", type=Path, required=True)
    ap.add_argument("--net", type=Path, required=True)
    ap.add_argument("--flows", type=Path, required=True,
                    help='JSON: {"gates": {group: veh/h each way}, "internal": veh/h, "through": share, "car_share": share, "internal_car_share": share}')
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--warm-s", type=float, default=900.0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    g = json.loads(a.graph.read_text(encoding="utf-8"))
    f = json.loads(a.flows.read_text(encoding="utf-8"))
    groups = gate_groups(g)
    out_of, into, car_ok = edges_by_node(a.net)
    gates = set(g["gates_in"]) | set(g["gates_out"])
    zones = [z for z in g["zones"] if z not in gates and into[z]]
    weight = defaultdict(float)
    for al in g["alleys"].values():
        if al["road_class"] == "alley":
            weight[al["u"]] += al["length_m"]
            weight[al["v"]] += al["length_m"]
    origins = [n for n in weight if out_of[n] and n not in gates]
    ow = [weight[n] for n in origins]
    end = a.warm_s + 3600.0
    trips = []

    def depart_times(vph: float) -> list[float]:
        t, out = 0.0, []
        while vph > 0:
            t += rng.expovariate(vph / 3600.0)
            if t >= end:
                return out
            out.append(t)
        return out

    def edge(node: str, outgoing: bool, car: bool) -> str | None:
        c = [e for e in (out_of if outgoing else into)[node] if not car or e in car_ok]
        return rng.choice(c) if c else None

    def add(t: float, o: str, d: str, car: bool) -> None:
        fe, te = edge(o, True, car), edge(d, False, car)
        if fe and te and fe != te:
            trips.append((t, "car" if car else "moto", fe, te))

    other = {k: [n for k2, v in groups.items() if k2 != k for n in v["out"]] for k in groups}
    for k, v in groups.items():
        q = f["gates"].get(k, 0.0)
        if not v["in"] or not v["out"]:
            continue
        for t in depart_times(q):  # entering at this group's gates
            car = rng.random() < f["car_share"]
            o = rng.choice(v["in"])
            d = rng.choice(other[k]) if rng.random() < f["through"] else rng.choice(zones)
            add(t, o, d, car)
        for t in depart_times(q * (1 - f["through"])):  # leaving from inside through this group's gates
            car = rng.random() < f["car_share"]
            add(t, rng.choices(origins, ow)[0], rng.choice(v["out"]), car)
    for t in depart_times(f["internal"]):
        car = rng.random() < f["internal_car_share"]
        add(t, rng.choices(origins, ow)[0], rng.choice(zones), car)

    trips.sort()
    rows = [vtypes(MOTO)]
    for i, (t, kind, fe, te) in enumerate(trips):
        rows.append(f'<trip id="{kind[0]}{i}" type="{kind}" depart="{t:.1f}" from="{fe}" to="{te}" departLane="best" departPosLat="random_free" departSpeed="max"/>\n')
    a.out.write_text("<routes>\n" + "".join(rows) + "</routes>\n", encoding="utf-8")
    n_car = sum(1 for x in trips if x[1] == "car")
    print(json.dumps({"trips": len(trips), "cars": n_car, "per_hour": round(len(trips) / end * 3600), "zones": len(zones), "origins": len(origins),
                      "groups": {k: {"in": len(v["in"]), "out": len(v["out"])} for k, v in groups.items()}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
