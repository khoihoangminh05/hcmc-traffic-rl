# Limitations (One paper — UAKP)

> Paper: [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md).  
> Legacy hai-paper note: [RESEARCH_TWO_PAPERS.md](./RESEARCH_TWO_PAPERS.md).

## Scope

- Twin domain = **largest alley-core WCC** of Quận 4 OSM (~886 nodes / ~1828 edges), not the full fragmented city graph (370 WCC).
- Density primary source = **Mapbox Directions** on sampled alley OD seeds (~379), graph-interpolated.
- Each alley carries **`density_k` + `uncertainty`** (observed / interpolated / prior levels).
- Camera is **secondary at entries/spine only**; does **not** observe interior alleys.
- Routing decision = **select 1 of K candidate paths** (UAKP), not binary prefer-main/alley, not multi-agent MAPPO.

## Twin / data

- OSM Vietnam alley coverage incomplete / inconsistently tagged (`service=alley` vs residential).
- Mapbox duration ≠ motorcycle probe inside narrow hẻm; zeros dropped (`duration_sec > 0`, `min_positive≥3`).
- Time buckets (UTC peaks mapped to morning / afternoon / evening wall schedule in configs).
- Peak-to-peak `|Δk|` can be small on some calendar days — report honestly.
- `cameras.hcmc_seed.json` is mostly **outside** Quận 4; Q4 L4 may use entry placeholders until a real Q4 catalog exists.

## UAKP / optimization

- Candidates are generated from weighted shortest / simple-path variants — not full path enumeration.
- Oracle-K = best candidate under mean travel (optimistic vs field GPS).
- Risk term uses fused `uncertainty` as a **proxy**, not calibrated predictive variance.
- Single-agent trip choice; no endogenous congestion from many simultaneous agents.
- Binary `quan4_v5` / `v5_l1l5` runs are **legacy toys** (2 actions, often trivial regret=0) — do not cite as main scientific result.

## Ethics

- Public traffic cams / Mapbox ToS: research use, no PII, no re-identification of individuals in frames.
- Cite data sources; do not release Mapbox tokens or raw camera dumps with sensitive content.
