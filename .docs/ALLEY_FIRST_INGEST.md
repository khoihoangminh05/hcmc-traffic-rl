# Luồng cào đúng (mật độ mọi hẻm)

> Không hardcode vài cặp lon/lat. Thứ tự bắt buộc:

```text
1) Chọn bbox khu vực nghiên cứu
2) OSM → liệt kê hẻm + cửa vào/ra (alley_id ổn định)
3) Sinh MAPBOX OD = mỗi hẻm (origin=u, destination=v)
4) NestJS poll Mapbox theo file OD đó
5) Camera: snapshot ImageHandler (cổng GT HCM) — không phải HLS
6) Fusion nội suy k(t) cho hẻm không có camera
```

Chi tiết thao tác: [INGEST_REAL.md](./INGEST_REAL.md) (đã cập nhật).

## Camera cổng https://giaothong.hochiminhcity.gov.vn/Map.aspx

Portal **không public danh sách HLS**. Cách lấy ảnh:

```text
https://giaothong.hochiminhcity.gov.vn/render/ImageHandler.ashx?id={CAMERA_ID}
```

- Đây là **JPEG snapshot** (refresh ~vài giây), không phải `.m3u8`.
- Seed 8 camera mẫu: `ingestion-worker/config/cameras.hcmc_seed.json`
- Thêm camera: trên Map.aspx mở DevTools → Network → click camera → tìm `ImageHandler.ashx?id=...` → copy `id` vào catalog.

Một số camera có thể có `VideoUrl` HLS nội bộ; player fallback demo m3u8 — **đừng dùng demo URL**. Ưu tiên ImageHandler.
