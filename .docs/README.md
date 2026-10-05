# HCMC Urban Traffic Optimization (Alley Network)

## North star (mục tiêu cốt lõi — luôn ưu tiên)

**Tái tạo tốt nhất có thể môi trường giao thông có chứa hẻm** (Digital Twin / SUMO), đủ giàu để huấn luyện MARL.

Mỗi hẻm trên twin phải có đủ 3 lớp:

| Lớp | Nội dung | Cách có |
|-----|----------|---------|
| **Định danh duy nhất** | `alley_id` ổn định | Đồ thị đường (OSMnx → SUMO edge/node) |
| **Cấu trúc hẻm** | topology, chiều dài, loại/cấp, chiều đi | Graph + OSM attributes |
| **Mật độ theo hẻm** | `k(t)` (và speed suy ra nếu cần) | **Nội suy / data fusion** (Greenshields + Kalman) từ camera thưa + Mapbox |

| Chiều MARL | Hợp đồng |
|------------|----------|
| **Đầu vào** | `t` · `O` · `D` |
| **Đầu ra** | Thời gian ngắn nhất — lộ trình **được qua hẻm** |
| **Quan sát** | State graph: cấu trúc + mật độ theo `alley_id` tại `t` |

Crawl / CV chỉ là quan sát thưa; `ml-core/data_fusion` là máy nội suy mật độ cho mọi hẻm đã định danh.

Phase 1 xây twin (ID + cấu trúc + `k`). Phase 2 MARL: `(t, O, D) → min travel time (via alleys)`.

---

Digital Twin + Multi-Agent Reinforcement Learning (MARL) system for Ho Chi Minh City alley-network traffic. The monorepo splits **I/O (Node 1 / máy local)** from **batch compute (Node 2 / GPU server)**.

## Architecture at a glance

| Node | Role | Runtime | Stack |
|------|------|---------|-------|
| **Node 1 – Local PC** | Collect Mapbox travel times + camera HLS raw video | On-demand: chạy khi mở máy, **tắt / resume** được | NestJS, TypeScript, Redis |
| **Node 2 – GPU server** | Offline CV, Data Fusion, SUMO routes, MARL training | ~8 hours/day trên server GPU khoẻ (chưa bắt buộc H100) | Python 3.10+, PyTorch, YOLOv10, OSRM/GraphHopper, SUMO, PettingZoo |

**Hard rules:**
- Node 2 is batch-only (`read folder → process → write artifacts`). No `while(true)` real-time polling on the GPU server.
- Node 1 must be **resumable**: persist last-success cursors (Mapbox poll time, HLS position) so stop/start không mất continuity.

## Repository layout

```text
hcmc-traffic-rl/
├── .docs/                   # Project governance & technical docs
├── ingestion-worker/        # NestJS (Node 1)
│   ├── src/
│   └── data_raw/            # Temporary CSV / MP4 before sync
├── ml-core/                 # Python batch engine (Node 2)
│   ├── data_fusion/
│   ├── cv_tracker/
│   └── marl_agent/
├── sumo-env/                # Offline SUMO simulation assets
│   ├── networks/
│   └── routes/
└── docker-compose.yml       # Local Redis (+ optional OSRM profile)
```

## Prerequisites

- **Node.js** 20 LTS+ and npm 10+
- **Python** 3.10+ with `venv`
- **Docker** / Docker Compose (Redis, optional OSRM)
- **SUMO** (Node 2 / local sim) — [Eclipse SUMO](https://eclipse.dev/sumo/)
- Node 2: CUDA-capable GPU server + PyTorch matching the driver (H100 optional / future upgrade)

## Quick start (local)

### 1. Clone / enter monorepo

```bash
cd hcmc-traffic-rl
```

### 2. Infrastructure (Redis)

```bash
docker compose up -d redis
```

OSRM (after map data is prepared under `./osrm-data`):

```bash
docker compose --profile routing up -d osrm
```

### 3. Node 1 — ingestion worker (NestJS)

```bash
cd ingestion-worker
npm install
# After NestJS scaffold exists:
npm run start:dev
```

Environment (example — create `.env` locally, do not commit secrets):

```env
REDIS_URL=redis://localhost:6379
MAPBOX_ACCESS_TOKEN=pk.your_token
CAMERA_HLS_URLS=https://example.com/stream.m3u8
DATA_RAW_DIR=./data_raw
```

### 4. Node 2 — ML core (Python batch)

```bash
cd ml-core
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -U pip
pip install -r requirements.txt   # added when Phase 1 starts
```

Typical batch pattern (once modules exist):

```bash
# Example — do NOT run continuous daemons on Node 2
python -m cv_tracker.run_batch --input ../ingestion-worker/data_raw/video --output ./artifacts/counts
python -m data_fusion.run_batch --counts ./artifacts/counts --mapbox ./artifacts/mapbox --output ./artifacts/fusion
python -m marl_agent.train --env-config ../sumo-env --episodes 1000
```

### 5. SUMO environment

Place OSMnx-derived `.net.xml` under `sumo-env/networks/`.  
Route / O-D XML produced by `ml-core` lands in `sumo-env/routes/`.

```bash
# Example (after networks & routes exist)
sumo -c sumo-env/hcmc_alley.sumocfg
```

## Domain separation

- NestJS code lives **only** under `ingestion-worker/`.
- Python / PyTorch / YOLO / MARL code lives **only** under `ml-core/` (and SUMO assets under `sumo-env/`).
- Do not import across language domains; exchange data via files + Redis keys / sync jobs.

## Documentation index

| File | Purpose |
|------|---------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Data-flow diagrams (Mermaid) |
| [DATA_CONTRACTS.md](./DATA_CONTRACTS.md) | **Redis/file schemas + HTTP endpoints** |
| [QUAN4_MAP.md](./QUAN4_MAP.md) | **Quận 4: dựng bản đồ + hẻm** |
| [QUAN4_DENSITY.md](./QUAN4_DENSITY.md) | **Quận 4: mật độ k(t) theo thời gian (bước hiện tại)** |
| [INGEST_REAL.md](./INGEST_REAL.md) | **Cào thật: OSM hẻm → OD → Mapbox; camera ImageHandler** |
| [ALLEY_FIRST_INGEST.md](./ALLEY_FIRST_INGEST.md) | Luồng alley-first + ghi chú cổng GT HCM |
| [RUNBOOK_VERIFY.md](./RUNBOOK_VERIFY.md) | **Cách chạy & checklist Pass/Fail phase này** |
| [CONVENTIONS.md](./CONVENTIONS.md) | Code style, typing, Conventional Commits |
| [PHASES.md](./PHASES.md) | Phase 1 & Phase 2 task breakdown |
| [PROGRESS.md](./PROGRESS.md) | Living checklist |

## Cursor workflow (mandatory)

1. Read `.docs/PROGRESS.md` at session start.
2. Propose the next 1–2 files and wait for confirmation.
3. After a working code block lands, update `.docs/PROGRESS.md`.
4. Keep Node 1 / Node 2 domains strictly separated.

## License / status

Internal R&D — Phase 0 scaffolding complete. See [PROGRESS.md](./PROGRESS.md).
