"""L2: single-junction checks. Four scenarios, all batch:

  sat    one saturated signalised approach: saturation flow and start-up lost time from the discharge curve
  delay  same approach at set demands: mean delay, to compare with Webster's uniform delay
  grid   four-leg signal, all turning movements: deadlock check (teleports, unfinished vehicles, longest wait)
  alley  alley joining a main road at a priority junction: alley delay and whether the alley can get out at all

    python -m routing2.validate.l2_junction --out /tmp/l2 --workers 8
"""

from __future__ import annotations

import argparse
import itertools
import json
import tempfile
import xml.etree.ElementTree as ET
from multiprocessing import Pool
from pathlib import Path
from statistics import mean

from .common import MOTO_VARIANTS, build_net, edge_data, run_sumo, teleport_reasons, teleports, vtypes

LEG_M = 300.0
GREEN_S, YELLOW_S, RED_CROSS_S = 40.0, 3.0, 37.0  # 83 s cycle, as measured at Hoang Dieu - Doan Van Bo
CYCLE_S = GREEN_S + YELLOW_S + RED_CROSS_S + YELLOW_S
WARM_S = 2 * CYCLE_S


def cross(d: Path, width: float, tls: bool, lanes: int = 1, no_internal: bool = False) -> None:
    pts = {"w": (-LEG_M, 0), "e": (LEG_M, 0), "n": (0, LEG_M), "s": (0, -LEG_M), "c": (0, 0)}
    t = "traffic_light" if tls else "priority"
    nodes = "".join(
        f'<node id="{k}" x="{x}" y="{y}" type="{t if k == "c" else "dead_end"}"/>\n' for k, (x, y) in pts.items()
    )
    edges = "".join(
        f'<edge id="{a}{b}" from="{a}" to="{b}" numLanes="{lanes}" width="{width}" speed="15"/>\n'
        for a, b in [("w", "c"), ("c", "e"), ("e", "c"), ("c", "w"), ("n", "c"), ("c", "s"), ("s", "c"), ("c", "n")]
    )
    build_net(d, nodes, edges, extra=("--no-internal-links", "true") if no_internal else ())


def tls_program(d: Path) -> str:
    """Two-phase program: east-west green first, then north-south. Permitted movements yield as usual."""
    root = ET.parse(d / "net.xml").getroot()
    links, turns = {}, {}
    for c in root.iter("connection"):
        if c.get("tl") == "c":
            links[int(c.get("linkIndex"))] = c.get("from")
            turns[int(c.get("linkIndex"))] = c.get("dir")
    n = max(links) + 1

    def state(ch_on: str, on: tuple[str, ...]) -> str:
        # Left turns and U-turns are permissive ("g"): they yield to oncoming straight traffic.
        def lamp(i: int) -> str:
            if links[i] not in on:
                return "r"
            return "g" if ch_on == "G" and turns[i] in ("l", "L", "t") else ch_on

        return "".join(lamp(i) for i in range(n))

    ew, ns = ("wc", "ec"), ("nc", "sc")
    return (
        '<tlLogic id="c" type="static" programID="vn" offset="0">'
        f'<phase duration="{GREEN_S}" state="{state("G", ew)}"/>'
        f'<phase duration="{YELLOW_S}" state="{state("y", ew)}"/>'
        f'<phase duration="{RED_CROSS_S}" state="{state("G", ns)}"/>'
        f'<phase duration="{YELLOW_S}" state="{state("y", ns)}"/>'
        "</tlLogic>\n"
    )


def flow(fid: str, kind: str, route: str, vph: float, end: float) -> str:
    return (
        f'<flow id="{fid}" type="{kind}" begin="0" end="{end}" vehsPerHour="{vph:.1f}" '
        f'departLane="best" departPosLat="random_free" departSpeed="max"><route edges="{route}"/></flow>\n'
    )


def split(vph: float, car_share: float) -> list[tuple[str, float]]:
    out = [("moto", vph * (1 - car_share))]
    if car_share > 0:
        out.append(("car", vph * car_share))
    return out


def trips(d: Path) -> list[dict]:
    return [dict(t.attrib) for t in ET.parse(d / "trip.xml").getroot().iter("tripinfo")]


def write_rou(d: Path, moto: str, body: str, extra: str = "") -> None:
    (d / "rou.xml").write_text("<routes>\n" + vtypes(moto, extra) + body + "</routes>\n")


def one(job: dict) -> dict:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        sc, W = job["scenario"], job["width"]
        extra = job.get("vtype_extra", "")
        if sc in ("sat", "delay", "grid"):
            cross(d, W, tls=True, lanes=job.get("lanes", 1), no_internal=job.get("no_internal", False))
            prog = tls_program(d)
        else:
            nodes = (
                f'<node id="w" x="{-LEG_M}" y="0" type="dead_end"/>\n<node id="e" x="{LEG_M}" y="0" type="dead_end"/>\n'
                f'<node id="n" x="0" y="{LEG_M}" type="dead_end"/>\n<node id="c" x="0" y="0" type="priority"/>\n'
            )
            edges = (
                f'<edge id="wc" from="w" to="c" numLanes="1" width="{W}" speed="15" priority="5"/>\n'
                f'<edge id="ce" from="c" to="e" numLanes="1" width="{W}" speed="15" priority="5"/>\n'
                f'<edge id="nc" from="n" to="c" numLanes="1" width="{job["alley_w"]}" speed="5" priority="1"/>\n'
            )
            build_net(d, nodes, edges, extra=("--no-internal-links", "true") if job.get("no_internal") else ())
            prog = ""
        horizon = job["horizon"]
        body = ""
        if sc == "sat":
            for kind, v in split(job["vph"], job["car_share"]):
                body += flow(f"{kind}", kind, "wc ce", v, horizon)
        elif sc == "delay":
            for kind, v in split(job["vph"], job["car_share"]):
                body += flow(f"{kind}", kind, "wc ce", v, horizon)
        elif sc == "grid":
            legs = {"w": ("e", "n", "s"), "e": ("w", "s", "n"), "n": ("s", "e", "w"), "s": ("n", "w", "e")}
            for a, (st, lf, rt) in legs.items():
                shares = ((("s", st, 1.0),) if job.get("straight_only") else (("s", st, 0.7), ("l", lf, 0.15), ("r", rt, 0.15)))
                for tag, b, f in shares:
                    for kind, v in split(job["vph"] * f, job["car_share"]):
                        body += flow(f"{a}{tag}{kind}", kind, f"{a}c c{b}", v, horizon)
        else:
            for kind, v in split(job["vph"], job["car_share"]):
                body += flow(f"m{kind}", kind, "wc ce", v, horizon)
            body += flow("a", "moto", "nc ce", job["alley_vph"], horizon)
        write_rou(d, job["moto"], body, extra)
        (d / "add.xml").write_text(
            f'<additional>\n{prog}<edgeData id="e" file="ed.xml" freq="1" begin="0" end="{horizon}" '
            'edges="ce" excludeEmpty="true"/></additional>\n'
        )
        run_extra = ("--ignore-junction-blocker", "5", "--time-to-impatience", "20") if job.get("impatient") else ()
        if prog:
            run_extra = run_extra + ("--tls.all-off", "false")
        if job.get("collision_warn"):
            # Close motorcycle contact is not a crash here: keep the vehicle on the road and count the event.
            run_extra = run_extra + ("--collision.action", "warn", "--collision.mingap-factor", "0")
        wall, err = run_sumo(d, horizon + job.get("drain", 300.0), job["step"], job["lateral"], run_extra)
        tr = trips(d)
        done = [t for t in tr if float(t["arrival"]) >= 0]
        res: dict = {
            **job, "wall_s": round(wall, 1), "teleports": teleports(err), "tele_why": teleport_reasons(err), "n_all": len(tr), "n_done": len(done),
            "unfinished": len(tr) - len(done),
            "max_wait_s": round(max((float(t["waitingTime"]) for t in tr), default=0.0), 1),
            "loss_mean_s": round(mean([float(t["timeLoss"]) for t in done]) if done else -1.0, 1),
        }
        if sc == "sat":
            ed = edge_data(d / "ed.xml", 0.0).get("ce", [])
            # discharge per second by time since green start; only cycles after warm-up and before demand stops
            by_t = [0.0] * int(CYCLE_S)
            n_cyc = 0
            cyc0 = int(WARM_S)
            n_cyc = int((horizon - cyc0) // CYCLE_S)
            for iv in ed:
                t = int(iv["begin"])
                if cyc0 <= t < cyc0 + n_cyc * CYCLE_S:
                    by_t[int((t - cyc0) % CYCLE_S)] += iv.get("entered", 0.0)
            per = [x / max(1, n_cyc) for x in by_t]
            total = sum(per[: int(GREEN_S + YELLOW_S)])
            # saturation rate: mean over green seconds 8..end, after the queue is moving
            sat = mean(per[8 : int(GREEN_S)]) if len(per) > 8 else 0.0
            lost = int(GREEN_S + YELLOW_S) - total / sat if sat > 0 else -1.0
            res.update(
                sat_veh_h=round(sat * 3600), sat_veh_h_m=round(sat * 3600 / W),
                per_cycle=round(total, 1), lost_s=round(lost, 1), curve=[round(x, 2) for x in per[:46]],
            )
        if sc == "alley":
            al = [t for t in done if t["id"].startswith("a.")]
            allall = [t for t in tr if t["id"].startswith("a.")]
            res.update(
                alley_n=len(allall), alley_done=len(al),
                alley_loss_mean=round(mean([float(t["timeLoss"]) for t in al]), 1) if al else -1.0,
                alley_wait_max=round(max((float(t["waitingTime"]) for t in allall), default=0.0), 1),
            )
        return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--scenario", nargs="+", default=["sat", "delay", "grid", "alley"])
    ap.add_argument("--moto", nargs="+", default=list(MOTO_VARIANTS))
    ap.add_argument("--lateral", nargs="+", type=float, default=[0.2, 0.4])
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--vtype-extra", default="", help="extra motorcycle attributes, e.g. jmDriveAfterRedTime")
    ap.add_argument("--no-internal", action="store_true", help="build junctions without internal links")
    ap.add_argument("--collision-warn", action="store_true", help="count collisions without teleporting")
    ap.add_argument("--diag", action="store_true", help="four-leg rescue matrix at high load only")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    jobs: list[dict] = []
    H = WARM_S + 10 * CYCLE_S
    if a.diag:
        for m, lat, vph, ni, so, (ln, w) in itertools.product(
            a.moto, a.lateral, (3000, 5000), (False, True), (False, True), ((1, 7.0), (2, 3.5))
        ):
            jobs.append(dict(
                moto=m, lateral=lat, step=a.step, vtype_extra="", impatient=True, scenario="grid", width=w, lanes=ln,
                car_share=0.15, vph=vph, horizon=1200.0, no_internal=ni, straight_only=so,
                collision_warn=a.collision_warn,
            ))
        a.scenario, a.moto = [], []
    for m, lat in itertools.product(a.moto, a.lateral):
        base = dict(moto=m, lateral=lat, step=a.step, vtype_extra=a.vtype_extra, impatient=True, no_internal=a.no_internal,
                    collision_warn=a.collision_warn)
        for sc in a.scenario:
            if sc == "sat":
                for W, cs in itertools.product((3.5, 7.0), (0.0, 0.15)):
                    jobs.append({**base, "scenario": sc, "width": W, "car_share": cs, "vph": 4000 * W, "horizon": H})
            elif sc == "delay":
                for frac in (0.15, 0.3, 0.45, 0.6, 0.75):
                    jobs.append({**base, "scenario": sc, "width": 7.0, "car_share": 0.0, "vph": 2000 * 7 * frac, "horizon": H, "frac": frac})
            elif sc == "grid":
                for vph, cs in itertools.product((1000, 2000, 3000, 4000, 5000), (0.0, 0.15)):
                    jobs.append({**base, "scenario": sc, "width": 7.0, "car_share": cs, "vph": vph, "horizon": 1200.0})
            else:
                for main_v, al_v, aw in itertools.product((1500, 4000, 7000), (150, 400, 800), (1.5, 2.5)):
                    jobs.append({**base, "scenario": sc, "width": 7.0, "car_share": 0.15, "vph": main_v, "alley_vph": al_v, "alley_w": aw, "horizon": 900.0})
    print(f"[l2] {len(jobs)} runs", flush=True)
    with Pool(a.workers) as p, (a.out / "l2.jsonl").open("w") as f:
        for r in p.imap_unordered(one, jobs):
            f.write(json.dumps(r) + "\n")
            f.flush()
            print({k: v for k, v in r.items() if k != "curve"}, flush=True)
    print("L2_DONE", flush=True)


if __name__ == "__main__":
    main()
