# Limitations (One paper — MAPPO multi-agent)

> Paper: [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md).

## Scope

- Twin domain = largest alley-core WCC Quận 4 (~886 nodes / ~1.8k edges).
- Density primary = Mapbox OD seeds + interpolation; camera secondary at entries only.
- Decision = **N agents × next-hop (micro)** under **BPR congestion**; MAPPO CTDE + GAE.
- Episode = multi-step until destination / max_steps (not car-following / SUMO).
- Legacy macro K-path = appendix only.

## Twin / data

- OSM alley coverage incomplete; Mapbox ≠ motorcycle probe in narrow alleys.
- Peak `|Δk|` can be small — report honestly.
- Cam seed mostly outside Q4 interior.

## MARL / optimization

- Congestion model = BPR + capacity by road_class + twin base `k` — stylized, not calibrated field counts.
- Reward multi-objective weights are chosen a priori (ablate in paper).
- Parameter-sharing MAPPO; homogeneous agents.
- Legacy: binary v5 and single-agent UAKP are **too easy** (match Dijkstra) — appendix only.

## Ethics

- Public cams / Mapbox ToS: research use, no PII; no token/raw dump release.
