# L5 / Paper limitations (draft)

> Dùng cho **Paper A** (limitation twin) và phần môi trường của **Paper B**.  
> Chiến lược 2 bài: [RESEARCH_TWO_PAPERS.md](./RESEARCH_TWO_PAPERS.md).

## Scope (cả hai bài)
- Twin domain = **largest alley-core WCC** of Quận 4 OSM (~886 nodes / ~1828 alleys), not the full fragmented city graph (370 WCC).
- Density primary source = **Mapbox Directions** on sampled alley OD seeds (~379), graph-interpolated.
- Camera is **secondary at entries/spine only**; does **not** observe interior alleys.

## Paper A — data / twin
- OSM Vietnam alley coverage incomplete / inconsistently tagged (`service=alley` vs residential).
- Mapbox duration ≠ motorcycle probe inside narrow hẻm; zeros dropped (`duration_sec > 0`, `min_positive≥3`).
- Time buckets (UTC): morning 0–5, afternoon 6–9, evening 10–14.
- Catch-up days may leave a peak empty (e.g. morning prior-only) until peak polls exist.
- Peak-to-peak `|Δk|` can be small on some calendar days — report honestly; do not overclaim “strong diurnal signal” without evidence.
- `cameras.hcmc_seed.json` is mostly **outside** Quận 4; Q4 L4 file may use entry placeholders until a real Q4 catalog exists.

## Paper B — routing optimization
- Action space: binary prefer-main vs prefer-alley (compact obs); not full path enumeration.
- Oracle = min(main, alley preference) on fused speeds — optimistic vs field GPS.
- Compare frozen twin (`v5_l1l5` / Paper A tag) vs mixed-day baseline (`v0_seed120_mixed_day`).
- Do not treat intermediate L1–L4 tags as separate GPU campaigns unless ablation is required.

## Ethics
- Public traffic cams / Mapbox ToS: research use, no PII, no re-identification of individuals in frames.
- Cite data sources; do not release Mapbox tokens or raw camera dumps with sensitive content.
