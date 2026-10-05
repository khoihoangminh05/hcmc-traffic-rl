# Phases — Task Breakdown

## North star (không đổi giữa các phase)

Tái tạo **môi trường giao thông có hẻm** với:

- **`alley_id`** duy nhất (qua đồ thị)
- **Cấu trúc** hẻm (topology, length, type, direction)
- **Mật độ `k(t)`** từng hẻm — **nội suy** từ fusion (camera sparse + Mapbox)

Dùng twin đó cho MARL:

- **In:** `t`, `O`, `D`
- **Out:** thời gian ngắn nhất (route **có thể qua hẻm**)
- **Obs:** cấu trúc + mật độ theo `alley_id` tại `t`

Phase 1 = ID + cấu trúc + density layer. Phase 2 = MARL trên twin đó.

## Phase 0 — Enterprise scaffolding *(complete when PROGRESS says so)*

- [x] Monorepo tree (`ingestion-worker`, `ml-core`, `sumo-env`, `.docs`)
- [x] Technical docs (`README`, `ARCHITECTURE`, `CONVENTIONS`, `PHASES`, `PROGRESS`)
- [x] `docker-compose.yml` (Redis + optional OSRM profile)

---

## Phase 1 — Digital Twin (Alley blind-spot via Data Fusion)

**Goal:** Produce trustworthy per-alley (`alley_id`) structure + density `k(t)` by fusing Mapbox travel times with CV counts (graph interpolation for blind alleys), then emit static SUMO networks & routes.

### 1.A — Node 1: Ingestion worker (NestJS)

| ID | Task | Output |
|----|------|--------|
| P1-A1 | Bootstrap NestJS app in `ingestion-worker/` (modules, config, ESLint/Prettier) | Runnable `npm run start:dev` |
| P1-A2 | Redis client module + health check | Connected buffer on local PC |
| P1-A3 | Mapbox Matrix/Directions poller (async, rate-limited, **resume cursor**) | CSV rows + Redis snapshots |
| P1-A4 | HLS camera crawler → Raw MP4/segments under `data_raw/` (**pause/resume safe**) | Video artifacts + metadata keys |
| P1-A5 | Retention / rotate / manifest for sync to GPU server (Node 2) | Sync manifest JSON |
| P1-A6 | Ops: env sample, logging, failure alerts (retry with backoff) | Operational baseline |

### 1.B — Node 2: Computer Vision batch

| ID | Task | Output |
|----|------|--------|
| P1-B1 | `cv_tracker` package scaffold + CLI (`run_batch`) | Batch entrypoint |
| P1-B2 | YOLOv10 inference on raw video folders | Detections |
| P1-B3 | ByteTrack association + per-edge / per-camera counts | Counts JSON |
| P1-B4 | Quality filters (confidence, ROI, time-of-day buckets) | Clean count tables |

### 1.C — Node 2: Data Fusion

| ID | Task | Output |
|----|------|--------|
| P1-C1 | `data_fusion` scaffold + CLI | Batch entrypoint |
| P1-C2 | Greenshields fundamental diagram fitting per corridor/alley class | v–k parameters |
| P1-C3 | Kalman Filter fusion (Mapbox travel time + CV counts → edge state) | Fused speed/density |
| P1-C4 | Uncertainty / gap-fill for edges without cameras | Interpolated graph attributes |
| P1-C5 | Export tables for SUMO (edge weights, flows) | Parquet/CSV/JSON contract |

### 1.D — SUMO Digital Twin baseline

| ID | Task | Output |
|----|------|--------|
| P1-D1 | Build alley subgraph via OSMnx → `sumo-env/networks/*.net.xml` | Network XML |
| P1-D2 | Generate static route / flow XML from fusion → `sumo-env/routes/` | Route XML |
| P1-D3 | SUMO config + smoke simulation | `.sumocfg` + trip metrics |
| P1-D4 | Validate twin vs held-out Mapbox/CV windows | Validation report |

### Phase 1 exit criteria

- Daily sync of raw data succeeds without Node 2 waiting on live APIs.
- Fused edge attributes cover the target alley set with documented uncertainty.
- SUMO runs a static O-D scenario driven by fusion outputs.

---

## Phase 2 — MARL Bidding System (flexible routing)

**Goal:** Trên twin có hẻm, huấn luyện multi-agent để với `(t, O, D)` trả về **travel time ngắn nhất** (route được phép qua hẻm), cải thiện tận dụng hẻm khi đường lớn tắc.

### 2.A — Environment

| ID | Task | Output |
|----|------|--------|
| P2-A1 | PettingZoo parallel env wrapping SUMO (offline episodes) | `marl_agent/env` |
| P2-A2 | Observation: GNN-ready graph state from fused edges + local queues | Obs schema |
| P2-A3 | Action: route choice / bid vector with constraint masks | Action schema |
| P2-A4 | Reward: travel time, fairness, alley overload penalties | Reward fn |

### 2.B — Agents & training

| ID | Task | Output |
|----|------|--------|
| P2-B1 | GNN encoder over road graph | Shared backbone |
| P2-B2 | PPO (or MAPPO) multi-agent trainer | Training loop (batch episodes) |
| P2-B3 | Checkpointing, seed control, eval vs static SUMO baseline | Metrics |
| P2-B4 | Export improved route sets back to `sumo-env/routes/` | Policy routes XML |

### 2.C — System integration

| ID | Task | Output |
|----|------|--------|
| P2-C1 | Offline “bidding round” simulation reports | HTML/Markdown report |
| P2-C2 | Document inference deployment options (still batch-first on GPU server) | Runbook |
| P2-C3 | Ablations: no-CV / no-Mapbox / full fusion | Comparison table |

### Phase 2 exit criteria

- Agents train and evaluate entirely in batch mode on Node 2.
- MARL policies beat static fusion routes on agreed KPIs (avg travel time, alley overload).
- Artifacts (checkpoints, routes, metrics) are reproducible from a single batch command.

---

## Suggested sequencing (after Phase 0)

1. NestJS bootstrap + Redis (P1-A1, P1-A2)
2. Mapbox poller CSV contract (P1-A3)
3. CV batch scaffold (P1-B1) in parallel once raw sample videos exist
4. Fusion + SUMO (P1-C*, P1-D*) when both Mapbox CSV and counts are available
5. Only then open Phase 2 env wrappers

Next concrete files are always proposed from `.docs/PROGRESS.md` at session start — confirm before coding.
