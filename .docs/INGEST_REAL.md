# Cào data thật — Mapbox + Camera (alley-first)

Máy chạy: **local PC** (`ingestion-worker` + script OSM trong `ml-core`).

## Luồng đúng (bạn đã nói đúng)

```text
OSM bbox → xác định hẻm + cửa vào/ra → sinh OD
     → Mapbox poll từng hẻm
Camera cổng GT HCM → snapshot JPEG (ImageHandler)
     → CV / fusion nội suy mật độ mọi alley_id
```

**Không** tự nghĩ vài cặp lon/lat cố định.

---

## Bước 0 — Token Mapbox (bạn đã có)

Trong `ingestion-worker/.env`:

```env
MAPBOX_ACCESS_TOKEN=pk....
MAPBOX_OD_FILE=./config/od_pairs.generated.json
CAMERA_CATALOG_FILE=./config/cameras.hcmc_seed.json
```

Copy từ `.env.example` nếu cần, **giữ token** của bạn.

---

## Bước 1 — Cào bản đồ / xác định hẻm (máy local hoặc GPU)

```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl\ml-core
.\.venv\Scripts\activate
pip install osmnx

# Đổi bbox theo khu vực nghiên cứu (ví dụ quanh Q1 / Thủ Đức — tự chỉnh)
python -m data_fusion.build_alleys_from_osm `
  --north 10.790 --south 10.770 --east 106.710 --west 106.690 `
  --output artifacts/out/alleys `
  --export-od ../ingestion-worker/config/od_pairs.generated.json `
  --max-alleys 60
```

Kết quả:

| File | Nội dung |
|------|----------|
| `artifacts/out/alleys/alley_graph.json` | `alley_id` + cấu trúc |
| `ingestion-worker/config/od_pairs.generated.json` | OD NestJS: mỗi hẻm = origin(u)→destination(v) dạng `lon,lat` |

---

## Bước 2 — Camera cổng https://giaothong.hochiminhcity.gov.vn/Map.aspx

**Không có HLS public.** Ảnh thật:

```text
https://giaothong.hochiminhcity.gov.vn/render/ImageHandler.ashx?id={CAMERA_ID}
```

Seed sẵn 8 camera: `ingestion-worker/config/cameras.hcmc_seed.json`.

**Thêm camera gần hẻm của bạn:**

1. Mở Map.aspx trên Chrome  
2. F12 → tab **Network**  
3. Click icon camera trên bản đồ  
4. Tìm request `ImageHandler.ashx?id=...`  
5. Copy `id`, thêm vào JSON:

```json
{
  "cameraId": "cam_my_alley",
  "name": "Ten giao lo",
  "mode": "snapshot",
  "url": "https://giaothong.hochiminhcity.gov.vn/render/ImageHandler.ashx?id=PASTE_ID_HERE"
}
```

Worker đã hỗ trợ `mode: snapshot` (lưu `.jpg` định kỳ).

---

## Bước 3 — Chạy NestJS cào

```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl
docker compose up -d redis
cd ingestion-worker
npm run start:dev
```

Ép cào:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:3000/mapbox/poll
Invoke-RestMethod -Method Post http://127.0.0.1:3000/camera/crawl
```

Pass:

- Mapbox: `count` ≈ số hẻm trong `od_pairs.generated.json` + CSV trong `data_raw/mapbox/`
- Camera: `segments: 1` mỗi cam + file `.jpg` trong `data_raw/camera/...`

---

## Bước 4 — Mật độ mọi hẻm

Sau khi có CSV Mapbox (+ optional JPG camera):

```powershell
cd ml-core
python -m data_fusion.run_batch --mapbox <csv> --counts <counts_dir> --graph artifacts/out/alleys/alley_graph.json --output artifacts/out/fusion
```

Fusion **nội suy** `density_k` cho hẻm không có camera (graph neighbors + Kalman).

Xem thêm: [ALLEY_FIRST_INGEST.md](./ALLEY_FIRST_INGEST.md) · [DATA_CONTRACTS.md](./DATA_CONTRACTS.md)
