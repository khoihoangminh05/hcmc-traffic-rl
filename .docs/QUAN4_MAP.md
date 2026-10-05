# Quận 4 — Tái tạo bản đồ giao thông & hẻm (bước hiện tại)

**Phạm vi:** Quận 4, TP.HCM  
**Mục tiêu bước này:** topology + định danh hẻm (`alley_id`) + cửa vào/ra + cấu trúc.  
**Chưa làm ở bước này:** mật độ `k(t)` theo thời gian (bước sau).

Máy chạy: **máy local** của bạn (`ml-core`).

---

## Kết quả đã sinh (sau khi chạy builder)

| Artifact | Path | Ý nghĩa |
|----------|------|---------|
| Graph | `ml-core/artifacts/out/quan4/alley_graph.json` | Nodes, edges, `alley_id`, neighbors, entry/exit |
| Index | `ml-core/artifacts/out/quan4/alley_index.json` | Bảng hẻm dễ đọc |
| GeoJSON | `ml-core/artifacts/out/quan4/quan4_alleys.geojson` | Xem trên https://geojson.io hoặc QGIS |
| OD (sau này) | `ml-core/artifacts/out/quan4/od_pairs.json` | entry→exit mỗi hẻm cho Mapbox |
| OD NestJS | `ingestion-worker/config/od_pairs.quan4.json` | Cùng nội dung, sẵn cho poller |
| SUMO net | `sumo-env/networks/quan4_alleys.net.xml` | Twin tĩnh |
| Meta | `ml-core/artifacts/out/quan4/build_meta.json` | Số node/edge |

## Kết quả build (profile detailed_v2 + tách đường to)

| File | Nội dung |
|------|----------|
| **`quan4_alleys.geojson`** | **Chỉ hẻm** (không tertiary/secondary/primary) — dùng file này để xem |
| `quan4_roads_spine.geojson` | Đường to (tertiary/secondary) |
| `quan4_local_streets.geojson` | Residential/service thường (không phải hẻm) |
| `quan4_network_all.geojson` | Tất cả lớp (tham khảo) |

QA tự động: build **FAIL** nếu primary/secondary/tertiary lọt vào layer alley.

```powershell
python -m data_fusion.build_quan4_map
```

**Giới hạn thật:** OSM VN thường thiếu/sai vị trí hẻm. Muốn sát thực địa hơn phải bổ sung JOSM / khảo sát.

---

## A. Setup thư viện (một lần, máy local)

```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl\ml-core

# nếu chưa có venv:
python -m venv .venv
.\.venv\Scripts\activate

pip install -U pip
pip install -r requirements.txt
# osmnx đã nằm trong requirements (numpy/pandas/networkx/torch/osmnx)
```

---

## B. Dựng lại bản đồ Quận 4 (khi cần refresh OSM)

```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl\ml-core
.\.venv\Scripts\activate
$env:PYTHONIOENCODING='utf-8'

python -m data_fusion.build_quan4_map
```

Lệnh mặc định:

- Place: `Quận 4, Thành phố Hồ Chí Minh, Việt Nam`
- Output: `artifacts/out/quan4/`
- Export OD: `../ingestion-worker/config/od_pairs.quan4.json`
- SUMO: `../sumo-env/networks/quan4_alleys.net.xml`

Tuỳ chọn:

```powershell
python -m data_fusion.build_quan4_map --max-edges 100   # thử nhanh
python -m data_fusion.build_quan4_map --min-length-m 20 --max-length-m 400
```

---

## C. Kiểm tra bản đồ đã đúng chưa

### C1. Meta

```powershell
Get-Content artifacts\out\quan4\build_meta.json
```

Pass: `alleys_edges > 0`, `district = Quan_4_HCMC`.

### C2. Xem hẻm trên bản đồ

1. Mở https://geojson.io  
2. Open file → chọn `ml-core/artifacts/out/quan4/quan4_alleys.geojson`  
3. Pass: các đoạn nằm trong ranh Quận 4 (Bến Vân Đồn / Khánh Hội / …).

### C3. Đọc 1 hẻm mẫu

```powershell
Get-Content artifacts\out\quan4\alley_index.json -TotalCount 40
```

Mỗi hẻm cần có: `alley_id`, `length_m`, `road_class`, `entry`/`exit` (`lon`,`lat`).

### C4. SUMO (nếu đã cài SUMO)

```powershell
# chỉ kiểm tra file tồn tại
Test-Path ..\sumo-env\networks\quan4_alleys.net.xml
```

---

## D. (Tuỳ chọn) Chuẩn bị NestJS cho bước mật độ sau

Chưa poll mật độ ở bước này. Khi sang bước sau, trong `ingestion-worker/.env`:

```env
MAPBOX_ACCESS_TOKEN=pk....
MAPBOX_OD_FILE=./config/od_pairs.quan4.json
CAMERA_CATALOG_FILE=./config/cameras.hcmc_seed.json
```

---

## E. Pass / Fail bước “tái tạo bản đồ Quận 4”

| # | Điều kiện | Pass? |
|---|-----------|-------|
| 1 | `build_quan4_map` chạy xong không lỗi | |
| 2 | Có `alley_graph.json` + `quan4_alleys.geojson` | |
| 3 | GeoJSON nằm đúng Quận 4 | |
| 4 | Mỗi hẻm có `alley_id` + entry/exit | |
| 5 | Có `quan4_alleys.net.xml` | |

Khi **đủ 1–5**, báo lại → sang bước **mật độ theo thời gian từng hẻm** (Mapbox theo OD Quận 4 + camera + fusion `k(t)`).

---

## F. Không làm gì ở bước này

- Không cần `/mapbox/poll` hàng loạt (tránh burn quota trước khi chốt map)
- Không train MARL
- Không đòi mật độ realtime
