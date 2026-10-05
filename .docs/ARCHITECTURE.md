# Architecture — HCMC Urban Traffic Optimization

## North star

Mọi quyết định kiến trúc phải phục vụ:

> **Tái tạo môi trường giao thông có hẻm** — mỗi hẻm có **định danh đồ thị**, **cấu trúc**, và **mật độ `k(t)` nội suy** — đủ tốt để MARL học định tuyến linh hoạt.

- **Twin layers:** `alley_id` (canonical graph) + structure attrs + density `k(t, alley_id)` (và `v` suy ra).
- **MARL I/O:** `(t, O, D) → shortest travel time` (route **được phép qua hẻm**); observation = graph state tại `t`.
- Crawl / CV = quan sát thưa; **`data_fusion` nội suy** mật độ cho hẻm mù — không phải sản phẩm cuối.
- Chất lượng twin (ID ổn định + `k` trên hẻm) > độ “đẹp” của pipeline trung gian.

## Design principles

1. **Physical & temporal split:** Node 1 (máy local) là I/O, chạy khi bạn bật worker — **pause / resume** được; Node 2 (GPU server) là compute-bound, cửa sổ ~8h/ngày.
2. **Async I/O on Node 1:** NestJS uses `async/await` for Mapbox polling and HLS segment writes — no blocking disk/network in the event loop. State resume (last poll, last segment) phải durable.
3. **Batch-only on Node 2:** Every Python entrypoint is `read → process → write`. No real-time wait loops.
4. **Artifact contract:** Redis buffers short-lived state trên máy local; durable truth is CSV/MP4/JSON/XML on disk (sync **Local PC → GPU server**).

## Logical nodes

```mermaid
flowchart TB
  subgraph N1["Node 1 — Local PC (pause / resume)"]
    Nest["ingestion-worker<br/>NestJS + TypeScript"]
    Raw["data_raw/<br/>CSV · MP4"]
    Nest --> Raw
  end

  subgraph Ext["External sources"]
    Mapbox["Mapbox Directions / Matrix API<br/>(Travel Time)"]
    Cam["Camera HLS streams"]
  end

  subgraph Buf["Local buffer"]
    Redis[(Redis)]
  end

  subgraph N2["Node 2 — GPU server (batch, ~8h/day)"]
    CV["ml-core/cv_tracker<br/>YOLOv10 + ByteTrack"]
    Fusion["ml-core/data_fusion<br/>Greenshields + Kalman"]
    Routes["Route XML generator"]
    MARL["ml-core/marl_agent<br/>GNN + PPO / PettingZoo"]
    SUMO["sumo-env<br/>networks + routes"]
  end

  Mapbox -->|poll async| Nest
  Cam -->|HLS download async| Nest
  Nest -->|job meta · queues| Redis
  Raw -->|offline sync| CV
  Redis -.->|optional metadata sync| N2
  CV --> Fusion
  Fusion --> Routes
  Routes --> SUMO
  SUMO --> MARL
```

## End-to-end data flow (Phase 1 → Phase 2)

```mermaid
sequenceDiagram
  autonumber
  participant Cam as Camera HLS
  participant MB as Mapbox API
  participant Nest as NestJS Worker
  participant Redis as Redis
  participant Disk as data_raw /
  participant Sync as Offline Sync
  participant CV as cv_tracker
  participant DF as data_fusion
  participant SUMO as sumo-env
  participant MARL as marl_agent

  Note over Nest,Redis: Node 1 — local I/O (stop/resume OK)
  loop While worker is running
    Nest->>MB: GET travel times (corridor / alley OD pairs)
    MB-->>Nest: duration / distance JSON
    Nest->>Redis: SET / LPUSH travel_time snapshots
    Nest->>Disk: append CSV row + persist poll cursor
  end
  loop While worker is running (HLS)
    Nest->>Cam: fetch .m3u8 + segments
    Cam-->>Nest: TS / fMP4 chunks
    Nest->>Disk: write Raw MP4 / segments + resume cursor
    Nest->>Redis: publish ingest:camera:{id} metadata
  end

  Note over Sync,MARL: Node 2 — GPU server daily batch (~8h)
  Sync->>Disk: rsync / object-store / USB pull to GPU server
  CV->>Disk: read video folder
  CV->>CV: YOLO detect + ByteTrack
  CV->>Disk: write vehicle counts / speeds JSON
  DF->>Disk: read counts + Mapbox CSV
  DF->>DF: Greenshields density–speed + Kalman fuse
  DF->>Disk: fused edge attributes
  DF->>SUMO: emit static route / flow XML
  SUMO->>SUMO: offline simulation baseline
  MARL->>SUMO: PettingZoo wrappers (Phase 2)
  MARL->>MARL: GNN state + PPO train / eval
  MARL->>Disk: checkpoints + metrics
```

## Component responsibilities

### `ingestion-worker/` (NestJS)

| Concern | Behavior |
|---------|----------|
| Mapbox poller | Scheduled async jobs; rate-limit aware; write CSV + Redis keys |
| Camera crawler | HLS playlist resolve → segment download → concatenate / store Raw |
| Redis | Job queues, last-success timestamps / resume cursors, short TTL caches |
| `data_raw/` | Staging on local disk; rotate / sync out to GPU server before Node 2 batch |

### `ml-core/` (Python)

| Package | Batch I/O contract |
|---------|-------------------|
| `cv_tracker/` | `--input` video dir → `--output` count/track artifacts |
| `data_fusion/` | counts + Mapbox CSV → fused speeds/densities + SUMO-ready tables |
| `marl_agent/` | SUMO net/routes + fused state → trained policies / eval logs |

### `sumo-env/`

- `networks/` — `.net.xml` from OSMnx (or netconvert) for the alley subgraph.
- `routes/` — static O-D / route XML produced by fusion (Phase 1) and later by MARL policies (Phase 2).

### `docker-compose.yml`

- **Redis:** required for local Node 1 development.
- **OSRM:** optional `routing` profile for baseline shortest-path checks (not a substitute for alley Digital Twin fusion).

## Sync boundary (Local PC → GPU server)

```mermaid
flowchart LR
  Local["Local PC<br/>data_raw + Redis export"]
  Obj["rsync / SFTP / drive / object store"]
  GPU["GPU server landing zone<br/>ml-core/artifacts/raw"]
  Batch["Batch pipelines (~8h)"]

  Local --> Obj --> GPU --> Batch
```

Recommended cadence: sync khi Node 1 đã gom đủ raw (hoặc trước cửa sổ compute hàng ngày); Node 2 never waits on live NestJS. Gaps do tắt máy local được chấp nhận — fusion phải chịu missing windows.

## Non-goals (enforced)

- Real-time inference loop on the GPU server.
- Mixing NestJS modules into `ml-core/` or Python into `ingestion-worker/src`.
- Treating Mapbox travel time alone as ground truth for alleys (it is one observation fused with CV counts).
- Assuming Node 1 is 24/7 VPS (current deployment = local, resumable).

## Evolution

- **Phase 1:** NestJS ingest → CV counts → Greenshields + Kalman → static SUMO routes (Digital Twin baseline).
- **Phase 2:** PettingZoo multi-agent env over SUMO; GNN + PPO bidding / flexible routing.

See [PHASES.md](./PHASES.md) for task lists and [PROGRESS.md](./PROGRESS.md) for status.
