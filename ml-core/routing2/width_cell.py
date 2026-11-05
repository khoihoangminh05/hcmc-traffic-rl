"""What one alley does at a given width and lateral resolution, away from the full network.

Toy nets with lanes of width W, the project's motorbike type and SUMO settings, over-saturated:
- straight: in -> out, no conflict. Plain saturation flow.
- merge: two equal-priority arms -> out, as at alley junctions.
- narrow, widen: a 3.2 m road into the alley and the alley into the road.
- side: a minor arm yields to a 3.2 m through road carrying 900 veh/h.
Reports exits/h from the tested arms, teleports by cause, and how often bikes on the tested arm
ride abreast (a pair overlapping lengthwise). A vType variant changes minGapLat, to test the
rule "two bikes fit when W >= 2 * 0.8 + minGapLat". No demand or policy from the project.

    python -u -m routing2.width_cell --out artifacts/out/quan4/routing2_review/width_cell
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .sumo_net import sumo_binary

LEN = 100.0
SIM_S = 900.0
SETTLE_S = 120.0


def vtype(min_gap_lat: float) -> str:
    return ('<vType id="moto" vClass="motorcycle" length="1.9" width="0.8" minGap="0.5" maxSpeed="15" '
            'accel="2.5" decel="4.5" sigma="0.5" speedDev="0" latAlignment="arbitrary" '
            f'minGapLat="{min_gap_lat}" lcSublane="1.0" lcPushy="0.5"/>')


def build(wd: Path, case: str, w: float) -> Path:
    nodes = {"c": (0, 0), "o": (LEN, 0), "a": (-LEN, 0)}
    edges = [("in_a", "a", "c", w, 1), ("out", "c", "o", w, 1)]
    if case == "merge":
        nodes["b"] = (0, LEN)
        edges.append(("in_b", "b", "c", w, 1))
    if case == "side":
        nodes = {"c": (0, 0), "a": (0, LEN), "e": (-LEN, 0), "o": (LEN, 0)}
        edges = [("in_a", "a", "c", w, 1), ("thru_in", "e", "c", 3.2, 5), ("out", "c", "o", 3.2, 5)]
    if case == "narrow":  # road into alley
        edges = [("in_a", "a", "c", 3.2, 1), ("out", "c", "o", w, 1)]
    if case == "widen":  # alley into road
        edges = [("in_a", "a", "c", w, 1), ("out", "c", "o", 3.2, 1)]
    nod = wd / "n.nod.xml"
    edg = wd / "n.edg.xml"
    nod.write_text("<nodes>" + "".join(f'<node id="{k}" x="{x}" y="{y}" type="priority"/>' for k, (x, y) in nodes.items())
                   + "</nodes>")
    edg.write_text("<edges>" + "".join(f'<edge id="{e}" from="{a}" to="{b}" numLanes="1" speed="8.33" width="{wd_:.2f}" priority="{p}"/>'
                                       for e, a, b, wd_, p in edges) + "</edges>")
    net = wd / "n.net.xml"
    subprocess.run([sumo_binary("netconvert"), "--node-files", str(nod), "--edge-files", str(edg), "--output-file", str(net),
                    "--default.junctions.radius", "1.5", "--junctions.corner-detail", "0", "--no-warnings", "true"],
                   check=True, capture_output=True)
    return net


def run_one(job: dict) -> dict:
    import traci

    case, w, lat, mgl, seed = job["case"], job["w"], job["lat"], job["mgl"], job["seed"]
    wd = Path(job["out"]) / f"{case}_{w}_{lat}_{mgl}_{seed}"
    wd.mkdir(parents=True, exist_ok=True)
    net = build(wd, case, w)
    flows = {"merge": [("in_a", "in_a out", 3600), ("in_b", "in_b out", 3600)],
             "straight": [("in_a", "in_a out", 7200)], "narrow": [("in_a", "in_a out", 7200)], "widen": [("in_a", "in_a out", 7200)],
             "side": [("in_a", "in_a out", 3600), ("thru", "thru_in out", 900)]}[case]
    rou = wd / "r.rou.xml"
    rou.write_text("<routes>" + vtype(mgl) + "".join(
        f'<route id="r{f}" edges="{e}"/><flow id="{f}" type="moto" route="r{f}" begin="0" end="{SIM_S}" '
        f'vehsPerHour="{q}" departLane="best" departPos="base" departPosLat="random" departSpeed="max"/>' for f, e, q in flows) + "</routes>")
    log = wd / "s.log"
    label = wd.name
    traci.start([sumo_binary("sumo"), "-n", str(net), "-r", str(rou), "--step-length", "0.5", "--lateral-resolution", str(lat),
                 "--time-to-teleport", "300", "--no-step-log", "true", "--end", str(SIM_S), "--seed", str(seed), "--log", str(log),
                 "--no-warnings", "false"], label=label)
    c = traci.getConnection(label)
    tested = {"in_a", "in_b"}
    exits, abreast, pairs, n_on, samples = 0, 0, 0, 0, 0
    prev: set[str] = set()
    while c.simulation.getTime() < SIM_S:
        c.simulationStep()
        t = c.simulation.getTime()
        now: set[str] = set()
        rows = []
        for e in tested:
            if e not in ("in_a", "in_b") or (e == "in_b" and case != "merge"):
                continue
            for v in c.edge.getLastStepVehicleIDs(e):
                now.add(v)
                rows.append((e, c.vehicle.getLanePosition(v)))
        if t > SETTLE_S:
            exits += len(prev - now)
            if t % 5 == 0:
                samples += 1
                n_on += len(rows)
                for i in range(len(rows)):
                    for k in range(i + 1, len(rows)):
                        if rows[i][0] == rows[k][0]:
                            pairs += 1
                            abreast += abs(rows[i][1] - rows[k][1]) < 1.9
        prev = now
    c.close()
    txt = log.read_text(encoding="utf-8", errors="ignore")
    causes = collections.Counter(re.sub(r" with vehicle '[^']+'", "", x) for x in re.findall(r"Teleporting vehicle '[^']+'; ([^,]+),", txt))
    span_h = (SIM_S - SETTLE_S) / 3600.0
    return {"case": case, "w": w, "lat": lat, "mgl": mgl, "seed": seed, "exits_per_h": round(exits / span_h),
            "abreast_share": round(abreast / max(1, pairs), 3), "on_arm": round(n_on / max(1, samples), 1), "teleports": dict(causes)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--widths", type=float, nargs="+", default=[1.0, 1.25, 1.5, 1.75, 1.9, 2.0, 2.25, 2.5, 3.0])
    ap.add_argument("--lats", type=float, nargs="+", default=[0.8, 0.4, 0.2])
    ap.add_argument("--mgls", type=float, nargs="+", default=[0.3])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--cases", nargs="+", default=["straight", "merge", "side"])
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    jobs = [{"case": c, "w": w, "lat": la, "mgl": m, "seed": s, "out": str(args.out)}
            for c in args.cases for w in args.widths for la in args.lats for m in args.mgls for s in args.seeds]
    rows = []
    with ProcessPoolExecutor(args.jobs) as ex:
        for r in ex.map(run_one, jobs):
            rows.append(r)
            print(json.dumps(r), flush=True)
    (args.out / f"cells_{'_'.join(str(m) for m in args.mgls)}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print("WIDTH_CELL_DONE", flush=True)


if __name__ == "__main__":
    main()
