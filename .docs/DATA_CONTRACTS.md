# Data Contracts — Schemas & Endpoints

> Nguồn sự thật cho storage + API hiện tại. Không có SQL DB — dùng **Redis (buffer)** + **file artifacts (durable)**.

**Base URL Node 1:** `http://localhost:3000`  
**Redis:** `REDIS_URL` (default `redis://localhost:6379`)

---

## 1. HTTP endpoints (ingestion-worker)

| Method | Path | Body | Response | Ý nghĩa |
|--------|------|------|----------|---------|
| `GET` | `/health` | — | `{ status: "ok"\|"degraded", redis: string }` | Redis ping; `ok` khi `redis === "PONG"` |
| `POST` | `/mapbox/poll` | — | `{ count: number, samples: TravelTimeSample[] }` | Poll Mapbox ngay (không chờ cron) |
| `POST` | `/camera/crawl` | — | `{ results: { cameraId, segments }[] }` | Crawl HLS segments mới |
| `POST` | `/sync/manifest` | — | `SyncManifest` | Sinh `data_raw/sync_manifest.json` |

Cron nội bộ (không phải HTTP):

| Job | Interval | Service |
|-----|----------|---------|
| Mapbox poll | mỗi phút (throttled bởi `MAPBOX_POLL_INTERVAL_MS`) | `MapboxPollerService` |
| Camera crawl | mỗi 5 phút | `CameraCrawlerService` |
| Sync manifest | mỗi giờ | `SyncManifestService` |

---

## 2. Redis schema (Node 1 buffer)

| Key pattern | Type | Value | TTL | Ghi chú |
|-------------|------|-------|-----|---------|
| `travel:{odId}` | LIST | JSON `TravelTimeSample` | không | `LPUSH` + `LTRIM 0 999` |
| `travel:last:{odId}` | STRING | ISO timestamp | không | Lần poll thành công gần nhất |
| channel `ingest:camera:{cameraId}` | PUBLISH | JSON metadata | — | `{ cameraId, segments, dir, at }` |

### `TravelTimeSample` (Redis + API)

```json
{
  "timestamp": "2026-09-22T08:00:00.000Z",
  "odId": "od_01",
  "origin": "106.7,10.77",
  "destination": "106.71,10.78",
  "durationSec": 95.0,
  "distanceM": 420.0
}
```

---

## 3. Cursor / state files (pause–resume)

Thư mục: `ingestion-worker/state/` (`STATE_DIR`)

### `state/mapbox.json`

```json
{
  "lastPollIso": "2026-09-22T08:00:00.000Z",
  "lastSuccessByOd": {
    "od_01": "2026-09-22T08:00:00.000Z"
  }
}
```

### `state/camera.json`

```json
{
  "lastSegmentUriByCamera": {
    "cam_01": "segment_012.ts"
  },
  "lastSuccessIsoByCamera": {
    "cam_01": "2026-09-22T08:05:00.000Z"
  }
}
```

---

## 4. File schemas — Node 1 raw (`data_raw/`)

### 4.1 Mapbox CSV

Path: `data_raw/mapbox/travel_time_YYYY-MM-DD.csv`

| Column | Type | Mô tả |
|--------|------|--------|
| `timestamp` | ISO8601 | Thời điểm sample |
| `od_id` | string | ID cặp O–D |
| `origin` | `lon,lat` | Điểm ở |
| `destination` | `lon,lat` | Điểm đến |
| `duration_sec` | float | Travel time (s) |
| `distance_m` | float | Distance (m) |

### 4.2 Camera segments

Path: `data_raw/camera/{cameraId}/{YYYY-MM-DD}/{segmentFile}`

Binary HLS segments (`.ts` / theo playlist).

### 4.3 Sync manifest

Path: `data_raw/sync_manifest.json`

```json
{
  "generatedAt": "ISO8601",
  "root": "absolute/path/to/data_raw",
  "files": [
    {
      "relativePath": "mapbox/travel_time_2026-09-22.csv",
      "sizeBytes": 1234,
      "mtimeIso": "ISO8601"
    }
  ]
}
```

---

## 5. File schemas — Node 2 (`ml-core` artifacts)

### 5.1 CV counts — `*_counts.json`

```json
{
  "video": "path/to/file.ts",
  "camera_id": "cam_01",
  "frame_count": 300,
  "vehicle_count": 24,
  "avg_confidence": 0.72,
  "method": "stub_hash | yolov10_bytetrack",
  "processed_at": "ISO8601"
}
```

Index: `counts_index.json` → `{ "videos": string[], "count": number }`

### 5.2 Alley graph — `alley_graph.json` (định danh + cấu trúc)

```json
{
  "nodes": ["n0", "n1", "..."],
  "alleys": {
    "alley_01": {
      "alley_id": "alley_01",
      "length_m": 60.0,
      "road_class": "alley | primary | secondary",
      "oneway": false,
      "neighbors": ["main_01", "alley_02"],
      "u": "n1",
      "v": "n1a"
    }
  },
  "edge_list": [
    { "u": "n1", "v": "n1a", "alley_id": "alley_01" }
  ]
}
```

**Khóa duy nhất:** `alley_id` (ổn định trên đồ thị).

### 5.3 Alley density — `alley_density.json` / `.csv` (sản phẩm fusion)

Mỗi phần tử / hàng:

| Field | Type | Mô tả |
|-------|------|--------|
| `alley_id` | string | PK logic |
| `timestamp` | ISO8601 | Cửa sổ ước lượng |
| `length_m` | float | Cấu trúc |
| `road_class` | string | Cấu trúc |
| `oneway` | bool | Cấu trúc |
| `neighbors` | string[] | JSON only — topology |
| `density_k` | float | **Mật độ nội suy** (veh/m) |
| `speed_mps` | float | Speed suy từ Greenshields |
| `uncertainty` | float | √P Kalman |
| `source` | `fused \| interpolated` | Nguồn ước lượng |

### 5.4 SUMO twin

| File | Vai trò |
|------|---------|
| `sumo-env/networks/hcmc_alley_demo.net.xml` | Net; `edge id` = `alley_id` |
| `sumo-env/routes/hcmc_alley_demo.rou.xml` | Routes demo |
| `sumo-env/hcmc_alley_demo.sumocfg` | Config smoke |

### 5.5 MARL outputs

`train_metrics.json`:

```json
{
  "episodes": 30,
  "mean_return": -150.0,
  "min_travel_time_n0_n3": 272.2,
  "checkpoint": "path/to/ppo_alley.pt"
}
```

**Infer contract (north star):**

| In | Out |
|----|-----|
| `t` (sec of day), `origin` (node id), `destination` (node id) | `min_travel_time_sec` |

```json
{
  "t": 28800.0,
  "origin": "n0",
  "destination": "n3",
  "min_travel_time_sec": 272.19
}
```

---

## 6. Env config schema (`.env`)

| Variable | Type | Default | Required để… |
|----------|------|---------|----------------|
| `REDIS_URL` | string | `redis://localhost:6379` | health ok |
| `PORT` | int | `3000` | HTTP |
| `DATA_RAW_DIR` | path | `./data_raw` | ghi raw |
| `STATE_DIR` | path | `./state` | resume |
| `MAPBOX_ACCESS_TOKEN` | string | — | poll thật |
| `MAPBOX_POLL_INTERVAL_MS` | int | `300000` | throttle |
| `MAPBOX_OD_PAIRS` | JSON array `OdPair[]` | `[]` | poll thật |
| `CAMERA_HLS_SOURCES` | JSON array `{cameraId,url}[]` | `[]` | crawl thật |
| `CAMERA_SEGMENT_LIMIT` | int | `30` | giới hạn segment/lần |

`OdPair`: `{ "odId", "origin": "lon,lat", "destination": "lon,lat" }`

---

## 7. Luồng dữ liệu (contract chain)

```text
Mapbox API / HLS
  → NestJS endpoints + cron
  → Redis (travel:*) + data_raw/ + state/
  → sync_manifest.json
  → (copy) ml-core artifacts
  → cv_tracker (*_counts.json)
  → data_fusion (alley_graph.json + alley_density.*)
  → sumo-env (*.net.xml / *.rou.xml)
  → marl_agent (ppo_alley.pt + infer JSON)
```

Xem thêm: [ARCHITECTURE.md](./ARCHITECTURE.md) · [RUNBOOK_VERIFY.md](./RUNBOOK_VERIFY.md)
