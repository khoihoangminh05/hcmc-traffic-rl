# Runbook — Kiểm tra phase hiện tại (trước khi sang bước tiếp)

Phase hiện tại = **Digital Twin demo + MARL smoke** trên đồ thị hẻm demo.  
Chưa cần token Mapbox / HLS để verify pipeline ML; cần Redis nếu muốn `/health = ok`.

Checklist đầy đủ schema: [DATA_CONTRACTS.md](./DATA_CONTRACTS.md).

---

## A. Chuẩn bị (một lần)

### A1. Redis (khuyến nghị)

1. Mở **Docker Desktop** đến khi engine sẵn sàng.
2. Từ root repo:

```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl
docker compose up -d redis
docker compose ps
```

Kỳ vọng: container `hcmc-redis` **Up** / healthy.

### A2. Node 1 — NestJS

```powershell
cd ingestion-worker
# nếu chưa có .env:
Copy-Item .env.example .env -Force
npm install
npm run start:dev
```

Giữ terminal này chạy. Log kỳ vọng: `ingestion-worker listening on :3000`.

### A3. Node 2 — Python venv (nếu chưa)

```powershell
cd ml-core
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
# nếu torch lỗi index: pip install torch --index-url https://download.pytorch.org/whl/cpu
```

---

## B. Kiểm tra Node 1 (ingestion)

Mở PowerShell mới:

```powershell
# 1) Health
Invoke-RestMethod http://127.0.0.1:3000/health
```

| Kết quả | Ý nghĩa |
|---------|---------|
| `status=ok`, `redis=PONG` | Pass |
| `status=degraded` | NestJS sống nhưng Redis chưa lên → làm lại A1 |

```powershell
# 2) Sync manifest (luôn chạy được, không cần token)
Invoke-RestMethod -Method Post http://127.0.0.1:3000/sync/manifest
```

Kỳ vọng: JSON có `generatedAt`, `files` (có thể rỗng). File: `ingestion-worker/data_raw/sync_manifest.json`.

```powershell
# 3) Mapbox / Camera — chỉ khi đã điền .env
# MAPBOX_ACCESS_TOKEN + MAPBOX_OD_PAIRS
Invoke-RestMethod -Method Post http://127.0.0.1:3000/mapbox/poll
# CAMERA_HLS_SOURCES
Invoke-RestMethod -Method Post http://127.0.0.1:3000/camera/crawl
```

**Pass Mapbox:** `count > 0` + CSV mới trong `data_raw/mapbox/`.  
**Pass Camera:** `segments > 0` + file trong `data_raw/camera/...`.  
Nếu `.env` để trống: poll/crawl idle — **không fail phase**, chỉ chưa có data thật.

Cursor resume: tắt NestJS rồi bật lại → `state/mapbox.json` / `state/camera.json` vẫn còn.

---

## C. Kiểm tra Node 2 (fusion + twin + MARL) — bắt buộc trước phase sau

```powershell
cd ml-core
.\.venv\Scripts\activate
$env:PYTHONIOENCODING='utf-8'
python run_smoke_pipeline.py
```

Kỳ vọng cuối log: **`SMOKE_OK`** và infer dạng:

```json
{
  "t": 28800.0,
  "origin": "n0",
  "destination": "n3",
  "min_travel_time_sec": <số dương>
}
```

### C1. Checklist file (Pass / Fail)

| # | File | Pass nếu |
|---|------|----------|
| 1 | `artifacts/out/fusion/alley_graph.json` | Có `alleys` với `alley_id`, `length_m`, `neighbors` |
| 2 | `artifacts/out/fusion/alley_density.json` | Mỗi hẻm có `density_k`, `speed_mps`, `uncertainty` |
| 3 | `artifacts/out/fusion/alley_density.csv` | Cùng cột với JSON (trừ `neighbors`) |
| 4 | `../sumo-env/networks/hcmc_alley_demo.net.xml` | Edge `id` trùng `alley_id` |
| 5 | `../sumo-env/routes/hcmc_alley_demo.rou.xml` | Có `route` / `vehicle` |
| 6 | `../sumo-env/hcmc_alley_demo.sumocfg` | Trỏ net + routes |
| 7 | `artifacts/out/marl/ppo_alley.pt` | Checkpoint tồn tại |
| 8 | `artifacts/out/marl/train_metrics.json` | Có `min_travel_time_n0_n3` |

Xem nhanh density:

```powershell
Get-Content artifacts\out\fusion\alley_density.json | Select-Object -First 40
```

### C2. Infer north star thủ công

```powershell
python -m marl_agent.infer `
  --density artifacts/out/fusion/alley_density.json `
  --graph artifacts/out/fusion/alley_graph.json `
  --t 28800 --origin n0 --destination n3
```

**Pass:** JSON có `min_travel_time_sec` hữu hạn (< 1e5).

### C3. SUMO (nếu đã cài SUMO)

```powershell
sumo -c ..\sumo-env\hcmc_alley_demo.sumocfg
```

**Pass:** chạy hết simulation không crash. (Chưa bắt buộc nếu chưa cài SUMO binary.)

---

## D. Tiêu chí “được sang phase sau”

Coi **phase scaffold / twin-demo hiện tại PASS** khi:

1. [x] NestJS listen `:3000` và `GET /health` trả lời (ok hoặc degraded đã hiểu lý do).
2. [x] `python run_smoke_pipeline.py` → `SMOKE_OK`.
3. [x] Có `alley_graph.json` + `alley_density.json` (ID + cấu trúc + mật độ).
4. [x] Infer `(t, O, D) → min_travel_time_sec` chạy được.
5. [ ] *(Tuỳ chọn nhưng nên có trước field work)* Redis = `PONG`.
6. [ ] *(Phase field thật — chưa bắt buộc để “sang bước kỹ thuật tiếp”)* Mapbox CSV + camera segments thật.

**Chưa làm / để phase tiếp theo (nâng chất twin):**

- OSMnx bbox HCMC thật thay demo graph  
- YOLO thật trên video camera  
- Validation P1-D4 vs held-out Mapbox/CV  
- Báo cáo bidding / ablation MARL  

---

## E. Lệnh một dòng (copy nhanh)

```powershell
# Terminal 1
cd hcmc-traffic-rl; docker compose up -d redis
cd ingestion-worker; npm run start:dev

# Terminal 2
Invoke-RestMethod http://127.0.0.1:3000/health
Invoke-RestMethod -Method Post http://127.0.0.1:3000/sync/manifest

# Terminal 3
cd hcmc-traffic-rl\ml-core
.\.venv\Scripts\activate
$env:PYTHONIOENCODING='utf-8'
python run_smoke_pipeline.py
python -m marl_agent.infer --density artifacts/out/fusion/alley_density.json --graph artifacts/out/fusion/alley_graph.json --t 28800 --origin n0 --destination n3
```
