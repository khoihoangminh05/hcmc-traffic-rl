"""Alley graph as tensors for the meso simulator.

Edges are the directed rows of `edge_list` in the WCC graph JSON. Signals come
from the snapped OSM file the SUMO net and v3v use (`osm_signals_snapped.json`).
A signalized node gets a two-phase program: links arriving roughly north-south
(bearing 45–135° mod 180) are red for the first `red_s` of each cycle, the
others for the second part. v3v held every approach red at the same time.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, fields
from pathlib import Path

import networkx as nx
import torch

from .params import DEFAULT_CLASS, ROAD_CLASS, SimConfig

DEFAULT_GRAPH = Path("artifacts/out/quan4/wcc/alley_graph_wcc.json")
LAT0 = 10.76
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))


@dataclass
class MesoGraph:
    n_nodes: int
    n_edges: int
    node_ids: list[str]
    edge_ids: list[str]
    src: torch.Tensor  # [E] long
    dst: torch.Tensor  # [E] long
    length: torch.Tensor  # [E] m
    v_free: torch.Tensor  # [E] m/s
    cap: torch.Tensor  # [E] veh/s
    storage: torch.Tensor  # [E] vehicles (float)
    is_alley: torch.Tensor  # [E] bool
    rev: torch.Tensor  # [E] long, reverse edge or -1
    out_edges: torch.Tensor  # [n, Dmax] long, -1 padded
    sig_group: torch.Tensor  # [E] long: -1 no signal at dst, else phase group 0/1
    sig_offset: torch.Tensor  # [E] s
    scc_nodes: torch.Tensor  # node indices of the largest strongly connected component
    node_xy: torch.Tensor  # [n, 2] m (equirectangular)

    def to(self, device: torch.device | str) -> MesoGraph:
        kw = {}
        for f in fields(self):
            v = getattr(self, f.name)
            kw[f.name] = v.to(device) if isinstance(v, torch.Tensor) else v
        return MesoGraph(**kw)


def load_graph(
    path: Path = DEFAULT_GRAPH,
    cfg: SimConfig | None = None,
    signals_path: Path | None = None,
    device: torch.device | str = "cpu",
) -> MesoGraph:
    cfg = cfg or SimConfig()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    alleys = data["alleys"]
    geo = data["nodes_geo"]
    rows = data["edge_list"]
    node_ids = sorted({str(e["u"]) for e in rows} | {str(e["v"]) for e in rows})
    nid = {n: i for i, n in enumerate(node_ids)}

    src, dst, length, vf, cap, sto, alley, eids = [], [], [], [], [], [], [], []
    for e in rows:
        a = alleys[e["alley_id"]]
        cls = a.get("road_class") or DEFAULT_CLASS
        p = ROAD_CLASS.get(cls, ROAD_CLASS[DEFAULT_CLASS])
        lanes = float(a.get("lanes") or 1) or 1.0
        L = max(float(a["length_m"]), 1.0)
        src.append(nid[str(e["u"])])
        dst.append(nid[str(e["v"])])
        length.append(L)
        vf.append(p.v_free)
        cap.append(p.cap * lanes)
        sto.append(max(cfg.min_storage, L * p.k_jam * lanes))
        alley.append(cls == "alley")
        eids.append(e["alley_id"])

    n, E = len(node_ids), len(rows)
    by_uv = {(s, d): k for k, (s, d) in enumerate(zip(src, dst))}
    rev = [by_uv.get((d, s), -1) for s, d in zip(src, dst)]
    outs: list[list[int]] = [[] for _ in range(n)]
    for k, s in enumerate(src):
        outs[s].append(k)
    dmax = max(1, max(len(o) for o in outs))
    out_edges = torch.full((n, dmax), -1, dtype=torch.long)
    for i, o in enumerate(outs):
        if o:
            out_edges[i, : len(o)] = torch.tensor(o)

    xy = torch.tensor(
        [[float(geo[x]["lon"]) * M_PER_DEG_LON, float(geo[x]["lat"]) * M_PER_DEG_LAT] for x in node_ids]
    )

    sig_group = torch.full((E,), -1, dtype=torch.long)
    sig_offset = torch.zeros(E)
    if cfg.signals:
        sp = signals_path or Path(path).with_name("osm_signals_snapped.json")
        if sp.exists():
            offs = {}
            for r in json.loads(sp.read_text(encoding="utf-8")).get("signals") or []:
                node = str(r.get("node") or "")
                if node in nid:
                    offs[nid[node]] = float(r.get("offset_s") or 0.0)
            for k in range(E):
                d = dst[k]
                if d in offs and len(outs[d]) >= 1:
                    dx, dy = (xy[d] - xy[src[k]]).tolist()
                    ang = math.degrees(math.atan2(dy, dx)) % 180.0
                    sig_group[k] = 0 if 45.0 <= ang < 135.0 else 1
                    sig_offset[k] = offs[d]

    g = nx.DiGraph(list(zip(src, dst)))
    scc = sorted(max(nx.strongly_connected_components(g), key=len))

    return MesoGraph(
        n_nodes=n,
        n_edges=E,
        node_ids=node_ids,
        edge_ids=eids,
        src=torch.tensor(src),
        dst=torch.tensor(dst),
        length=torch.tensor(length),
        v_free=torch.tensor(vf),
        cap=torch.tensor(cap),
        storage=torch.tensor(sto),
        is_alley=torch.tensor(alley),
        rev=torch.tensor(rev),
        out_edges=out_edges,
        sig_group=sig_group,
        sig_offset=sig_offset,
        scc_nodes=torch.tensor(scc),
        node_xy=xy,
    ).to(device)
