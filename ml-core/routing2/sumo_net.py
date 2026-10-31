"""SUMO network of the Quận 4 alley graph, built with netconvert (batch, Node 2).

The old `sumo-env/networks/quan4_alleys.net.xml` was written by hand and has
no connections (every junction has incLanes=""), so no vehicle can pass a
junction. Here plain node/edge files go through netconvert, which builds
lanes, connections and junction logic.

- Edge id = alley_id, node id = graph node id, so routes map 1:1 to the meso graph.
- Speed limit = the meso class free speed (routing2.params), so free-flow times agree.
- Widths per class (OSM has none for these ways): alley 2.5 m, service 3.0,
  residential 4.0, tertiary 3.2 / lane, secondary 3.5 / lane. Motorbikes use the
  sublane model at run time (`--lateral-resolution`), so a 2.5 m alley holds
  about three abreast.
- Cars are not allowed in alleys; the demand is motorbikes only.
- Snapped OSM signals become `traffic_light` nodes with netconvert's static
  program (cycle 60 s). The meso uses a 2-phase 30/30 split; both are stated
  as assumptions.

    python -m routing2.sumo_net --out ../sumo-env/networks/v4
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import quoteattr

from data_fusion.match_probe import _edge_polyline, project

from .graph import DEFAULT_GRAPH, REPO_SIGNALS
from .params import DEFAULT_CLASS, ROAD_CLASS

WIDTH_PER_LANE = {"alley": 2.5, "service": 3.0, "residential": 4.0, "tertiary": 3.2, "secondary": 3.5}
PRIORITY = {"alley": 1, "service": 2, "residential": 3, "tertiary": 4, "secondary": 5}
ALLOW_ALLEY = "motorcycle moped bicycle pedestrian"
ALLOW_ROAD = "motorcycle moped bicycle pedestrian passenger bus delivery truck"


def sumo_binary(name: str) -> str:
    """Prefer the eclipse-sumo wheel's binaries; fall back to PATH."""
    try:
        import sumo  # type: ignore[import-not-found]

        for cand in (Path(sumo.SUMO_HOME) / "bin" / name, Path(sumo.SUMO_HOME) / "bin" / f"{name}.exe"):
            if cand.exists():
                return str(cand)
    except ImportError:
        pass
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f"{name} not found; pip install eclipse-sumo")
    return found


def write_plain(graph_path: Path, out_dir: Path, signals_path: Path | None = None) -> tuple[Path, Path]:
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    geo = data["nodes_geo"]
    alleys = data["alleys"]
    rows = data["edge_list"]
    sp = signals_path or graph_path.with_name("osm_signals_snapped.json")
    if not sp.exists():
        sp = REPO_SIGNALS
    signals = {str(r.get("node")) for r in json.loads(sp.read_text(encoding="utf-8")).get("signals") or []}

    nodes = sorted({str(e["u"]) for e in rows} | {str(e["v"]) for e in rows})
    pts = {n: project(float(geo[n]["lon"]), float(geo[n]["lat"])) for n in nodes}
    x0 = min(p[0] for p in pts.values())
    y0 = min(p[1] for p in pts.values())

    out_dir.mkdir(parents=True, exist_ok=True)
    nod = out_dir / "quan4.nod.xml"
    edg = out_dir / "quan4.edg.xml"
    with nod.open("w", encoding="utf-8") as f:
        f.write("<nodes>\n")
        for n in nodes:
            x, y = pts[n]
            typ = "traffic_light" if n in signals else "priority"
            f.write(f'  <node id={quoteattr(n)} x="{x - x0:.2f}" y="{y - y0:.2f}" type="{typ}"/>\n')
        f.write("</nodes>\n")
    with edg.open("w", encoding="utf-8") as f:
        f.write("<edges>\n")
        for e in rows:
            u, v, aid = str(e["u"]), str(e["v"]), e["alley_id"]
            a = alleys[aid]
            cls = a.get("road_class") or DEFAULT_CLASS
            p = ROAD_CLASS.get(cls, ROAD_CLASS[DEFAULT_CLASS])
            lanes = int(float(a.get("lanes") or 1) or 1)
            width = WIDTH_PER_LANE.get(cls, 3.0)
            allow = ALLOW_ALLEY if cls in ("alley", "service") else ALLOW_ROAD
            shape = " ".join(f"{x - x0:.2f},{y - y0:.2f}" for x, y in _edge_polyline(a, u, v, geo))
            f.write(
                f"  <edge id={quoteattr(aid)} from={quoteattr(u)} to={quoteattr(v)} "
                f'priority="{PRIORITY.get(cls, 2)}" numLanes="{lanes}" speed="{p.v_free:.2f}" '
                f'width="{width:.2f}" allow="{allow}" shape="{shape}"/>\n'
            )
        f.write("</edges>\n")
    return nod, edg


def build_net(graph_path: Path, out_dir: Path) -> Path:
    nod, edg = write_plain(graph_path, out_dir)
    net = out_dir / "quan4_v4.net.xml"
    cmd = [
        sumo_binary("netconvert"),
        "--node-files", str(nod),
        "--edge-files", str(edg),
        "--output-file", str(net),
        "--junctions.join", "false",
        "--geometry.remove", "false",
        "--offset.disable-normalization", "true",
        "--default.junctions.radius", "1.5",
        "--junctions.corner-detail", "0",
        "--tls.default-type", "static",
        "--tls.cycle.time", "60",
        "--no-warnings", "true",
    ]
    subprocess.run(cmd, check=True)
    return net


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    ap.add_argument("--out", type=Path, default=Path("../sumo-env/networks/v4"))
    args = ap.parse_args()
    net = build_net(args.graph, args.out)
    print(f"[sumo_net] wrote {net}", flush=True)


if __name__ == "__main__":
    main()
