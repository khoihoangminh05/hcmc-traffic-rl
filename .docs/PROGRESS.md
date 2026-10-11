# Progress Tracker — HCMC Urban Traffic Optimization

> Living checklist. Update after every working block.  
> **Research lock:** [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md) — MAPPO **micro** next-hop.

**Last updated:** 2026-10-11  
**Current phase:** MAPPO micro (macro K-path / UAKP = legacy).  
Guides: [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md) · [SOL1_MAPPO.md](./SOL1_MAPPO.md).

**Focus (locked):** Quận 4 — Mapbox-first trong hẻm; camera chỉ secondary.  
**Server:** sol1 — `CUDA_VISIBLE_DEVICES=1`, outputs `/mnt/data8tb/minhkhoi/...`.

**North star (locked):**
- **One paper:** Twin + **MAPPO micro** (next-hop, long OD, peak/time, travel-aligned reward).  
- Legacy: macro K-path / UAKP / binary.

**Deployment note (locked):**
- **Node 1** = local NestJS + Redis (pause/resume).  
- **Node 2** = GPU batch (sol1).  
- Fusion/MARL = `ml-core/`.

---

## Phase 0 — Scaffolding

- [x] Monorepo directory tree created (`hcmc-traffic-rl/`)
- [x] `ingestion-worker/src` + `data_raw` placeholders
- [x] `ml-core/{data_fusion,cv_tracker,marl_agent}` placeholders
- [x] `sumo-env/{networks,routes}` placeholders
- [x] `docker-compose.yml` (Redis + optional OSRM)
- [x] `.docs/README.md`
- [x] `.docs/ARCHITECTURE.md`
- [x] `.docs/CONVENTIONS.md`
- [x] `.docs/PHASES.md`
- [x] `.docs/PROGRESS.md`

**Phase 0 status:** Done

---

## Phase 1 — Digital Twin

### 1.A Ingestion (NestJS)

- [x] P1-A1 NestJS bootstrap (app module, ESLint, Prettier, tsconfig)
- [x] P1-A2 Redis module + health
- [x] P1-A3 Mapbox travel-time poller → CSV + Redis (resume cursor)
- [x] P1-A4 HLS camera crawler → `data_raw/` (pause/resume)
- [x] P1-A5 Sync manifest / retention
- [x] P1-A6 Logging, retries, `.env.example`

### 1.B CV batch

- [x] P1-B1 `cv_tracker` package + `run_batch` CLI
- [x] P1-B2 YOLOv10 inference pipeline (optional ultralytics; stub fallback)
- [x] P1-B3 ByteTrack + count export (via ultralytics track when available)
- [x] P1-B4 ROI / confidence filters (class filter car/moto/bus/truck)

### 1.C Data fusion

- [x] P1-C1 `data_fusion` package + CLI
- [x] P1-C2 Greenshields fitting
- [x] P1-C3 Kalman fusion (Mapbox + CV)
- [x] P1-C4 Gap-fill / uncertainty (graph neighbor interpolation + `alley_id`)
- [x] P1-C5 Export for SUMO (`export_sumo.py` + density CSV/JSON)

### 1.D SUMO twin

- [x] P1-D1 Demo alley graph → `.net.xml` (`hcmc_alley_demo.net.xml`)
- [x] P1-D2 Static routes XML from fusion
- [x] P1-D3 Smoke `.sumocfg`
- [x] P1-D4 Quận 4 twin smoke (`run_quan4_twin` + SUMO cfg; full field validation still open)

**Phase 1 status:** Quận 4 twin runnable (density→SUMO+MARL smoke); Nest density seeds done

---

## Phase 2 — MARL Bidding

- [x] P2-A1 PettingZoo-style SUMO/density env (`marl_agent/env.py`)
- [x] P2-A2 GNN observation schema (flat graph dens + OD + t)
- [x] P2-A3 Action / bid space (prefer main vs alley)
- [x] P2-A4 Reward design (−travel_time)
- [x] P2-B1 GNN encoder
- [x] P2-B2 PPO / MAPPO trainer (batch PPO smoke)
- [x] P2-B3 Eval vs static baseline (`infer.py` min travel time)
- [x] P2-B4 Export policy routes (via SUMO export from density)
- [ ] P2-C1 Bidding simulation report
- [ ] P2-C2 Batch inference runbook (see root README smoke)
- [ ] P2-C3 Ablation study

**Phase 2 status:** Smoke runnable — `(t,O,D)→min_travel_time` via `python -m marl_agent.infer`

---

## Next proposed work (MAPPO)

1. **Done — MAPPO env/train/docs** (`quan4_mappo.yaml`).  
2. **Now — sol1:** [SOL1_MAPPO.md](./SOL1_MAPPO.md) full train + `--ippo` ablation → paste `summary.json`.  
3. Draft: [PAPER_OUTLINE_MAPPO.md](./PAPER_OUTLINE_MAPPO.md).

---

## Change log

| Date | Note |
|------|------|
| 2026-09-22 | Phase 0 scaffolding + docs + compose committed to tree |
| 2026-09-22 | Deploy model: Node 1 = local pause/resume; Node 2 = GPU server (~8h), not H100-required |
| 2026-09-22 | North star locked: alley-aware twin for MARL `(t,O,D)→min travel time via alleys` |
| 2026-09-22 | North star +: alley_id + structure + density k(t) via fusion interpolation |
| 2026-09-22 | Sprint 1–5 implemented; NestJS up; `ml-core/run_smoke_pipeline.py` SMOKE_OK |
| 2026-09-23 | Added DATA_CONTRACTS.md + RUNBOOK_VERIFY.md for schemas/endpoints and phase gate |
| 2026-09-24 | Quận 4 OSM map: ~323 nodes / ~583 alley edges; guide QUAN4_MAP.md |
| 2026-09-24 | Quận 4 detailed map v2: ~5660 alleys; QA no arterial-as-alley |
| 2026-09-24 | Density step: 120 seeds; Mapbox CSV live; gentle batch poller |
| 2026-10-02 | Nest morning+evening peaks; fusion `2026-10-02T14` observed=120 |
| 2026-10-04 | Quận 4 twin: `export_sumo --prefix quan4_alleys` + `run_quan4_twin` → QUAN4_TWIN_OK |
| 2026-10-05 | Robust MARL: `robust_train` + `quan4_h100.yaml` + TRAIN_NOW + ENV_UPGRADE L1–L5 (cam = secondary only) |
| 2026-10-05 | L1: `--l1-peaks` fusion + env density_catalog + `quan4_v1_time_bucket.yaml` |
| 2026-10-05 | Locked: L1→L5 verify only; **one** GPU train after L5 (no per-L retrain) |
| 2026-10-05 | L2-B: `export_wcc_subgraph` + `quan4_v2_wcc.yaml` draft |
| 2026-10-05 | L3: seeds_l3 n=400 + min_positive=3 + hop uncertainty + `verify_l3` |
| 2026-10-05 | Evening poll + L4 cam_secondary + L5 `quan4_v5_final` + limitations |
| 2026-10-06 | Locked **2 conference papers**: RESEARCH_TWO_PAPERS.md (A=data twin, B=routing) |
| 2026-10-09 | **Supersede → one paper UAKP**: RESEARCH_ONE_PAPER + uakp_env/train + quan4_uakp; binary v5 = legacy |
