"""Shared helpers for the L1 and L2 checks: vehicle types, netconvert, SUMO run, edgeData parsing."""

from __future__ import annotations

import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# Name -> motorcycle attributes. "base" is what the simulator uses today (routing2/sumo_check.MOTO_VTYPE).
MOTO_VARIANTS = {
    "base": (
        'length="1.9" width="0.8" minGap="0.5" maxSpeed="15" accel="2.5" decel="4.5" sigma="0.5" '
        'speedDev="0" latAlignment="arbitrary" minGapLat="0.3" lcSublane="1.0" lcPushy="0.5"'
    ),
    "tight": (
        'length="1.9" width="0.7" minGap="0.3" maxSpeed="15" accel="2.5" decel="4.5" sigma="0.5" '
        'speedDev="0.1" tau="0.8" latAlignment="arbitrary" minGapLat="0.15" lcSublane="2.0" '
        'lcPushy="0.8" lcAssertive="2" lcImpatience="1"'
    ),
}
CAR = 'length="4.5" width="1.8" minGap="1.5" maxSpeed="15" sigma="0.5"'


def moto_attrs(moto: str) -> str:
    """A variant name, or "name:attr=value;attr=value" to replace or add attributes of that variant."""
    name, _, over = moto.partition(":")
    attrs = MOTO_VARIANTS[name]
    for pair in filter(None, over.split(";")):
        k, v = pair.split("=")
        new = f'{k}="{v}"'
        attrs, n = re.subn(rf'\b{k}="[^"]*"', new, attrs)
        if n == 0:
            attrs += f" {new}"
    return attrs


def vtypes(moto: str, extra: str = "") -> str:
    return (
        f'<vType id="moto" vClass="motorcycle" {moto_attrs(moto)} {extra}/>\n'
        f'<vType id="car" vClass="passenger" {CAR}/>\n'
    )


def sumo_bin(name: str) -> str:
    import shutil

    p = shutil.which(name)
    if p is None:
        raise FileNotFoundError(f"{name} not on PATH; activate the SUMO environment")
    return p


def build_net(d: Path, nodes: str, edges: str, cons: str = "", extra: tuple[str, ...] = ()) -> Path:
    """nodes and edges are the inner XML. Returns the net file path."""
    (d / "n.nod.xml").write_text(f"<nodes>\n{nodes}</nodes>\n")
    (d / "e.edg.xml").write_text(f"<edges>\n{edges}</edges>\n")
    cmd = [sumo_bin("netconvert"), "-n", "n.nod.xml", "-e", "e.edg.xml", "-o", "net.xml", "--no-warnings"]
    if cons:
        (d / "c.con.xml").write_text(f"<connections>\n{cons}</connections>\n")
        cmd += ["-x", "c.con.xml"]
    subprocess.run(cmd + list(extra), cwd=d, check=True, capture_output=True, text=True)
    return d / "net.xml"


def run_sumo(d: Path, end_s: float, step_s: float, lateral_m: float, extra: tuple[str, ...] = (), seed: int = 1) -> tuple[float, str]:
    """Runs net.xml + rou.xml + add.xml in d. Returns wall seconds and stderr text."""
    cmd = [
        sumo_bin("sumo"), "-n", "net.xml", "-r", "rou.xml", "-a", "add.xml", "--end", str(end_s),
        "--step-length", str(step_s), "--lateral-resolution", str(lateral_m),
        "--no-step-log", "true", "--duration-log.disable", "true",
        "--tripinfo-output", "trip.xml", "--tripinfo-output.write-unfinished", "true",
        "--time-to-teleport", "300", "--seed", str(seed), *extra,
    ]
    t0 = time.perf_counter()
    r = subprocess.run(cmd, cwd=d, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2000:])
    return time.perf_counter() - t0, r.stderr


def edge_data(path: Path, t_from: float) -> dict[str, list[dict]]:
    """Edge -> intervals from an edgeData file, keeping intervals that start at or after t_from."""
    out: dict[str, list[dict]] = {}
    for iv in ET.parse(path).getroot().iter("interval"):
        if float(iv.get("begin")) < t_from:
            continue
        for e in iv.iter("edge"):
            row = {k: float(v) for k, v in e.attrib.items() if k != "id"}
            row["begin"] = float(iv.get("begin"))
            out.setdefault(e.get("id"), []).append(row)
    return out


def teleports(stderr: str) -> int:
    return sum(1 for ln in stderr.splitlines() if "Teleporting vehicle" in ln)


def teleport_reasons(stderr: str) -> dict[str, int]:
    """Teleport counts by SUMO's stated reason (jam, yield, wrong lane, collision), plus raw collision warnings."""
    out: dict[str, int] = {}
    for ln in stderr.splitlines():
        m = re.search(r"Teleporting vehicle '[^']*'; ([^,.(]*)", ln)
        if m:
            key = re.sub(r"'[^']*'", "", m.group(1)).strip()
            out[key] = out.get(key, 0) + 1
        elif "collision with" in ln:
            out["collision_warning"] = out.get("collision_warning", 0) + 1
    return out
