# Quận 4 — Bước mật độ k(t) theo thời gian từng hẻm

**Máy:** local PC  
**Điều kiện trước:** bản đồ hẻm Quận 4 đã OK (`artifacts/out/quan4/`).

## Ý tưởng

1. Không poll Mapbox cả ~5600 hẻm mỗi lần (cháy quota).  
2. **Sample ~120 seed OD** → NestJS poll Mapbox.  
3. `run_quan4_density` gán quan sát theo `od_id = alley_id`, rồi **nội suy** `k` ra mọi hẻm trên đồ thị.

---

## Bước 1 — Tạo file seed OD (một lần / khi đổi map)

```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl\ml-core
.\.venv\Scripts\activate
$env:PYTHONIOENCODING='utf-8'

python -m data_fusion.sample_od_seeds --n 120
```

→ `ingestion-worker/config/od_pairs.quan4.seeds.json`

---

## Bước 2 — Cấu hình NestJS `.env`

File: `ingestion-worker/.env` (giữ token Mapbox của bạn):

```env
REDIS_URL=redis://localhost:6379
PORT=3000
DATA_RAW_DIR=./data_raw
STATE_DIR=./state

MAPBOX_ACCESS_TOKEN=pk.YOUR_TOKEN
MAPBOX_POLL_INTERVAL_MS=900000
MAPBOX_BATCH_SIZE=15
MAPBOX_REQUEST_DELAY_MS=1500
MAPBOX_OD_FILE=./config/od_pairs.quan4.seeds.json
MAPBOX_MANUAL_FULL=0
CAMERA_CATALOG_FILE=./config/cameras.hcmc_seed.json
```

---

## Bước 3 — Chạy cào Mapbox (máy local)

```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl
docker compose up -d redis

cd ingestion-worker
npm run start:dev
```

Terminal khác — ép poll 1 lần:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:3000/mapbox/poll
```

**Pass:** `count` ≈ 120 (số seed).  
CSV: `ingestion-worker/data_raw/mapbox/travel_time_YYYY-MM-DD.csv`  
Cột quan trọng: `od_id` (= `alley_id` seed).

(Tuỳ chọn camera)

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:3000/camera/crawl
```

---

## Bước 4 — Fusion mật độ mọi hẻm

```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl\ml-core
.\.venv\Scripts\activate
$env:PYTHONIOENCODING='utf-8'

# Đổi ngày CSV cho đúng
python -m data_fusion.run_quan4_density `
  --graph artifacts/out/quan4/alley_graph.json `
  --mapbox ..\ingestion-worker\data_raw\mapbox\travel_time_2026-09-24.csv `
  --output artifacts/out/quan4/density
```

**Pass `density_meta.json`:**

| Field | Ý nghĩa |
|-------|---------|
| `alleys` | ~5600 hẻm có `density_k` |
| `observed` | số hẻm có Mapbox thật |
| `interpolated` | số hẻm nội suy |

Xem map màu mật độ:  
`artifacts/out/quan4/density/quan4_density_latest.geojson` trên geojson.io

---

## Bước 5 — Lặp theo thời gian

Mỗi khung giờ (ví dụ 30–60 phút):

1. `POST /mapbox/poll` lại  
2. Chạy lại `run_quan4_density` (file CSV cùng ngày sẽ append thêm dòng)  
3. Có thêm snapshot `alley_density_<time_bucket>.json`

Worker cron cũng poll theo `MAPBOX_POLL_INTERVAL_MS` nếu để NestJS chạy.

---

## Checklist Pass bước này

- [x] Seed file tồn tại (~120 OD)  
- [x] `/mapbox/poll` trả `count > 0`  
- [x] CSV có `od_id` trùng `alley_id`  
- [x] `alley_density_latest.json` phủ toàn bộ hẻm Quận 4  
- [x] `quan4_density_latest.geojson` mở được  

---

## Bước 6 — Twin SUMO + MARL smoke (sau Nest)

Nest **không** cần chạy thêm. Input: `alley_density_latest.json` + `alley_graph.json` + seeds.

```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl\ml-core
.\.venv\Scripts\activate
$env:PYTHONIOENCODING='utf-8'
python -m data_fusion.run_quan4_twin
```

**Pass:** in `QUAN4_TWIN_OK`.

| Output | Ý nghĩa |
|--------|---------|
| `sumo-env/quan4_alleys.sumocfg` | Scenario SUMO (net speed từ `speed_mps` + routes topology-valid) |
| `sumo-env/routes/quan4_alleys.rou.xml` | 2–3 route từ seed OD có đường đi |
| `artifacts/out/quan4/marl/ppo_alley.pt` | Checkpoint train smoke |
| `artifacts/out/quan4/marl/quan4_twin_meta.json` | Infer 3 OD + train metrics |

Chỉ SUMO (không train):

```powershell
python -m data_fusion.export_sumo `
  --density artifacts/out/quan4/density/alley_density_latest.json `
  --graph artifacts/out/quan4/alley_graph.json `
  --prefix quan4_alleys `
  --seeds ..\ingestion-worker\config\od_pairs.quan4.seeds.json
sumo -c ..\sumo-env\quan4_alleys.sumocfg --no-step-log true
```

Infer một OD:

```powershell
python -m marl_agent.infer `
  --density artifacts/out/quan4/density/alley_density_latest.json `
  --graph artifacts/out/quan4/alley_graph.json `
  --t 28800 --origin 13805829143 --destination 7540613482
```

## Bước 7 — Robust train (chuẩn bị H100)

Xem runbook đầy đủ: [TRAIN_SERVER.md](./TRAIN_SERVER.md).

```powershell
# Smoke CPU
python -m marl_agent.robust_train --smoke --device cpu
# Trên server H100
python -m marl_agent.robust_train --config marl_agent/configs/quan4_h100.yaml --device cuda
```

Theo dõi log `[train]` / `[eval]` / `[adapt]`; sau train đọc `summary.json`.