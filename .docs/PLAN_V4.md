# Kế hoạch làm lại toàn bộ: twin hẻm Quận 4 + định tuyến hợp tác, đích TR-C / T-ITS (A\* phụ)

## Context

Đích mới: **bài chính Q1 giao thông (Transportation Research Part C hoặc IEEE T-ITS)**. Nếu phương pháp mạnh trên nhiều quận thì tách thêm **bài A\* (AAMAS hoặc KDD Applied DS)**. Kết quả v3v giữ làm phụ lục (đã đóng băng ở tag `v3v-paper-baseline`). **Chỉ dùng dữ liệu miễn phí.**

Tài nguyên:
- sol1: 2×RTX 4090 dùng chung, 40 lõi CPU. CPU là nút cổ chai. Người dùng tự chạy lệnh; agent không SSH được.
- Máy local (Windows + WSL) chạy ingestion.
- Không giới hạn thời gian.

Bài hiện tại sẽ bị reviewer Q1 bác vì các điểm yếu dưới đây (đã kiểm trên code và dữ liệu thật).

## Kiểm toán điểm yếu (có bằng chứng)

| # | Điểm yếu | Bằng chứng |
|---|---|---|
| D1 | "Quan sát" Mapbox không phải giao thông thật | `mapbox.poller.service.ts` gọi `mapbox/driving` (không có traffic realtime). 5993 dòng, 400 OD, quãng trung vị **18 m / 7 s**, thực chất 3 ngày (10-05, 10-08, 10-09) |
| D2 | Mật độ chủ yếu là nội suy | 379 cạnh observed (21%), 1081 interpolated, 368 prior. Uncertainty = 0.03 ở mọi cạnh. Nội suy theo số bước (hop), không có mô hình xác suất, không có kiểm định giữ-lại |
| D3 | Camera không vào MARL | `density_by_peak` ghi đè file L4 ở mỗi `reset`. L4 chỉ khác file tối ở 34 cạnh. Mới có 8 camera, 4753 ảnh, chưa chạy YOLO |
| D4 | Không có mô hình nhu cầu đi lại | OD bốc ngẫu nhiên, 50 xe, xuất phát trong 120 s, hệ thống đóng. Giao thông nền là tải tĩnh, không tương tác |
| D5 | Không mô hình xe máy | HCM khoảng 90% xe máy, nhưng sim dùng BPR với sức chứa kiểu ô tô (2.5/6/10/8 do mình chọn) và jam spacing 6 m |
| S1 | Mô phỏng tự viết, chưa kiểm chứng | BPR theo sự kiện, chưa so với SUMO hay số đo |
| S2 | Lợi thế chủ yếu nằm ở một hệ số tự chọn | 50 xe: 92% chênh lệch là phần `share_coef` (MAPPO được train trên nó, greedy thì không). Thời gian đi chỉ giảm 3.3 s |
| S3 | Quan sát dùng nội tạng mô phỏng | `tt_pred`, `regret` lấy từ `_forecast_entry`, nên không triển khai được ngoài đời |
| M1 | Kiến trúc yếu, không chuyển được sang mạng khác | MLP trên 8 ô lối ra đệm cố định; embedding nút bằng sin(md5); chỉ một quận |
| M2 | Đóng góp phương pháp không rõ | IPPO ≈ MAPPO, noalley ≈ MAPPO |
| E1 | Baseline chưa đủ cho Q1 | Thiếu tối ưu toàn hệ thống (SO), cân bằng người dùng (DUE), định tuyến lại kiểu ứng dụng dẫn đường, heuristic chi phí biên, MARL baseline khác |
| E2 | Thống kê mỏng | 5 seed, ablation 1 seed, 1 mạng, 1 mô phỏng, tối đa 100 xe |

## Kiến trúc mới (6 pha, mỗi pha có cổng đạt/không đạt)

### P0. Hạ tầng (1–2 tuần)
- Thêm `.gitattributes` (chuẩn hóa LF) để hết cảnh 138 file "modified" giả.
- Package mới `ml-core/routing2/`; giữ nguyên `marl_agent/` cho v3v.
- Registry thí nghiệm: mỗi run có id, config snapshot, git hash. Không ghi đè (giống pattern của `eval_heldout.py`).
- Test theo kiểu `*_TESTS_OK` đang có.

### P1. Dữ liệu miễn phí, mô hình hóa có độ bất định (Paper-A trong bài)
1. **Mapbox `driving-traffic` + `annotations=duration,distance,speed,congestion,congestion_numeric`** và `geometries=geojson&overview=full`: một request cho tốc độ từng đoạn dọc tuyến. Ghép đoạn vào cạnh bằng hình học (điểm giữa gần nhất + cùng hướng), không dựa vào OSM node id. Thiết kế khoảng 100 tuyến dò 0.3–1.5 km phủ đường lớn và các hành lang hẻm. (Chốt 2026-10-30) mỗi 10 phút, 5–22 giờ VN, **7 ngày** (đủ một tuần: ngày thường + cuối tuần) = 71.4k request; trước đó dự kiến 15 phút × 14 ngày = 78.4k (free tier 100k/tháng; mỗi request nhiều tọa độ tính là 1). Thêm chế độ **typical**: `depart_at` cho các ngày tương lai trả hồ sơ lịch sử của Mapbox (prior, không phải số đo), 7 ngày × 68 mốc (5–22 giờ, 15 phút) × 100 tuyến = 47.6k request, xong trong khoảng 6–7 giờ.
   - Sửa `ingestion-worker/src/mapbox/mapbox.poller.service.ts`, config tuyến mới `config/probe_routes.quan4.json`.
2. **Nguồn kiểm định độc lập**: TomTom Traffic Flow (free 2.5k/ngày) trên đường biên. Chỉ dùng để validate, không dùng để fit.
3. **Camera**: mở rộng ra mọi camera công cộng quanh Q4 trên cổng giaothong HCM. Chạy YOLO + đếm theo lớp xe (`cv_tracker/run_batch.py` đã có khung ultralytics). Đầu ra: lưu lượng biên theo giờ và **tỉ lệ xe máy**.
4. **Nhu cầu đi lại**: OSM buildings/POI (trường học kèm giờ tan, chợ) + WorldPop 100 m, sinh chuyến theo nút (mô hình gravity), hồ sơ thời gian lấy từ camera.
5. **Fusion Bayesian trên đồ thị** thay nội suy theo hop: GMRF hoặc GP trên line graph, có covariate (loại đường, chiều dài, độ rộng suy từ OSM, mật độ POI) và chiều thời gian. Ra **phân phối hậu nghiệm** cho tốc độ và mật độ mỗi cạnh. Kiểm định leave-one-route-out, và trên TomTom/camera giữ lại. So với baseline: hop-interp hiện tại, kriging GNN (IGNNK).
- **Cổng P1**: sai số giữ-lại tốt hơn hop-interp; khoảng tin cậy hiệu chỉnh đúng (độ phủ 90% nằm trong khoảng 85–95%). Nếu Mapbox không đi vào hẻm thì hẻm sẽ có hậu nghiệm rộng. Bài báo nói thẳng điều này, và P3 xử lý bằng robust RL.

### P2. Mô phỏng hai tầng
1. **SUMO (tầng kiểm chứng)**: mạng Q4 với vClass xe máy, sublane model, độ rộng hẻm. Tái dùng `export_sumo.write_geo_signal_net` và `fetch_osm_signals`. Đèn: 19 đèn OSM, giả định fixed-time, có phân tích độ nhạy.
   - Hiệu chỉnh nhu cầu (OD estimation) bằng SPSA hoặc Bayesian optimization để khớp tốc độ Mapbox và lưu lượng camera. Dùng `routeSampler` / `flowrouter` của SUMO.
2. **Mô phỏng meso trên GPU (tầng train)**: mô hình link-transmission / point-queue có spillback, viết bằng PyTorch, batch hàng nghìn episode trên một 4090. Đây là lời giải cho nút cổ chai CPU. Tham số lấy từ P1, có domain randomization trên hậu nghiệm.
   - File mới: `routing2/meso_gpu.py`, `routing2/sumo_env.py` (libsumo, nhiều tiến trình).
- **Cổng P2**: thời gian đi của meso so với SUMO trên cùng nhu cầu đạt R² ≥ 0.8; SUMO ≤ 5 s/episode/tiến trình; meso ≥ 10⁴ quyết định/s.

### P3. Bài toán mới (vá S2, S3, D4)
- **Hệ thống mở**: giao thông nền đã hiệu chỉnh (định tuyến SUMO / thiết bị reroute) + đội xe điều khiển chiếm tỉ lệ p (10–100%, coi như người dùng ứng dụng). Xe đến liên tục trong 1–2 giờ cao điểm.
- **Mục tiêu = tổng thời gian đi của toàn hệ thống**, không có hệ số tự chọn. Mức dồn xe trong hẻm và độ trễ của dân hẻm báo riêng như thước đo công bằng. Nếu muốn "bảo vệ hẻm" thì dùng **RL có ràng buộc (Lagrangian)**, không dùng hệ số tay.
- **Thông tin**: chỉ những gì hệ thống thật đo được (tốc độ dò có trễ và nhiễu, ý định của đội xe). Không đọc BPR, file mật độ hay lõi mô phỏng.

### P4. Phương pháp mới (đóng góp chính, phục vụ cả bài A\*)
- **Bộ mã hóa mạng**: graph transformer / GAT trên trạng thái cạnh (tốc độ đo, độ bất định hậu nghiệm). Tính một lần mỗi thời điểm quyết định, trên GPU.
- **Chú ý theo xung đột** (từ mục 12 của bàn giao): mỗi xe chú ý tới top-K xe trong đội lọc bằng đồ thị xung đột (thời gian tới lúc gặp trên đoạn chung), có token loại xe (đội / heuristic / nền).
- **Đầu ra kiểu pointer**: chấm điểm từng lối ra bằng một đầu dùng chung. Bất biến hoán vị, nhận bậc nút tùy ý, không cần đệm, nên chuyển được sang quận khác. Tùy chọn phân cấp: chọn 1 trong k tuyến ở gốc, rồi định tuyến lại theo next-hop.
- **Chia công (kinh tế học + MAS)**: **difference reward / chi phí xã hội biên** (Wolpert & Tumer; thuế Pigou). Reward_i = −(thời gian của mình + độ trễ mình gây cho xe khác), tính phản thực trong meso. Đúng mục tiêu hệ thống, không có hệ số tay. (Mầm sẵn có: `reward_mode="marginal"` và `ext` trong `_commit_entry`.)
- **Huấn luyện**: MAPPO + PopArt; **league đội hỗn hợp** (kiểu AlphaStar: tự chơi + người dùng greedy + nền); curriculum theo tỉ lệ và quy mô đội; **robust RL** bằng domain randomization trên hậu nghiệm twin; báo cáo CVaR.
- File mới: `routing2/models.py`, `routing2/train.py`, `routing2/conflict.py`.

### P5. Baseline và đánh giá (vá E1, E2)
- **Baseline**:
  - đường ngắn nhất (tự do / điển hình);
  - **định tuyến lại kiểu ứng dụng** (rerouting device của SUMO);
  - greedy theo thông tin công khai;
  - **greedy chi phí biên** (port từ `baseline_social_actions`);
  - **DUE và SO** qua `duaIterate.py` / `marouter` của SUMO, cộng cận Frank–Wolfe SO tĩnh;
  - phân luồng tập trung rolling-horizon (MPC);
  - MARL baseline: IPPO-MLP, MAPPO-MLP (port v3v), MAA2C hoặc QMIX, mean-field AC.
- **Kịch bản**: Q4 + 2 quận nhiều hẻm (ví dụ Q3, Bình Thạnh), zero-shot và fine-tune (góc A\*); p = 10–100%; nhu cầu ×0.8–1.4; sự cố; giả định đèn; nhiều mẫu hậu nghiệm.
- **Thống kê**: ≥10 seed cho phương pháp chính, ≥5 seed cho ablation. Test cặp, bootstrap CI, hiệu chỉnh Holm. Báo cáo mọi lần chạy. Seed chọn checkpoint tách hẳn seed test (giữ quy tắc 50000 / 60000).
- **Ablation**: attention vs MLP; K; difference reward vs ích kỷ vs hệ số tay; DR vs không DR; league vs tự chơi; khoảng chênh meso→SUMO.
- Tái dùng: `_paired_stats`, mẫu `evaluate_fair_suite` (chốt OD/sự kiện rồi mới chạy từng luật), `diagnose_policy`, `early_stop.py`, mẫu `mappo_micro_vec.py`.

### P6. Viết bài và công bố
- Mã + dữ liệu (tuyến dò, hậu nghiệm twin, mạng SUMO) công khai, theo đúng điều khoản API.
- Bài TR-C/T-ITS trước; bài AAMAS/KDD nếu thắng rõ khi tổng quát hóa sang quận khác.

## Thứ tự và cổng quyết định

P0 → (P1 cào dữ liệu chạy nền 1 tuần) ∥ P2 → P3 → P4 → P5 → P6.

- Trong lúc chờ dữ liệu: dựng SUMO và meso trên prior hiện có, port MAPPO-MLP sang meso làm mốc.
- **Điểm dừng quan trọng**: sau P5 đợt đầu, nếu phương pháp mới không thắng greedy chi phí biên và DUE rõ ràng thì đổi luận điểm bài sang "twin + phân tích định giá ngoại ứng trong mạng hẻm" (vẫn TR-C được), không cố ép.

## Rủi ro chính
- Mapbox có thể không định tuyến vào hẻm (hẻm gắn tag service/footway). Khi đó hẻm không có quan sát, chỉ có hậu nghiệm rộng, và robust RL là câu trả lời. Ghi rõ trong bài.
- ToS của Mapbox/TomTom về việc lưu và công bố dữ liệu đã cào: kiểm tra trước khi bắt đầu cào.
- sol1 dùng chung: train trên meso GPU, chỉ dùng SUMO để kiểm chứng. Luôn kiểm `uptime`.

## Verification
- Mỗi module mới có script test `*_TESTS_OK` (bảo toàn xe trong meso, ghép OSM node, độ phủ hậu nghiệm), chạy được trên local CPU.
- Cổng P1/P2 đo bằng script riêng; ghi kết quả JSON, không ghi đè.
- Smoke train trên CPU trước mỗi lệnh train sol1. Lệnh đưa cho người dùng là khối dán được nguyên, có `tee`.
- Đánh giá cuối luôn chạy trên SUMO, seed test sạch, so sánh cặp.
- Cập nhật `.docs/PROGRESS.md`, bàn giao mới `.docs/HANDOFF_V4.md`, sửa mục 2 của bàn giao cũ (số liệu thật của D2/D3).

## Trạng thái (cập nhật 30/10/2026)

- [x] P0: `.gitattributes` (hết 138 file "modified" giả do CRLF).
- [x] P1.1 thiết kế tuyến dò: `ml-core/data_fusion/design_probe_routes.py` → `ingestion-worker/config/probe_routes.quan4.json`. 100 tuyến, trung vị 1247 m, phủ 1563/1828 cạnh (hẻm 1359/1460) **nếu** Mapbox đi đúng tuyến thiết kế. Khoảng 86.8k request/31 ngày ở 28 lượt/ngày.
- [x] P1.1 poller: `ingestion-worker/src/mapbox/mapbox.probe.service.ts` (giờ VN 6–20, mỗi 30 phút, có trần tháng, resume giữa chừng, lưu JSON thô). `POST /mapbox/probe` để chạy tay.
- [x] P1.1 ghép cạnh: `ml-core/data_fusion/match_probe.py` + test `python -m data_fusion.test_match_probe` (MATCH_PROBE_TESTS_OK).
- [x] P1.1 (2026-10-30) theo docs Directions: driving-traffic nhận 25 tọa độ, nên mỗi tuyến có thêm tối đa 8 via ở giữa cạnh hẻm (`waypoints=0;N-1`, `bearings` ±45°) để ép đi đúng tuyến. Chế độ typical: `POST /mapbox/probe/typical?start=YYYY-MM-DD&days=7&stepMin=15`, `GET` để xem tiến độ; quota tháng chung cho live + typical (`state/mapbox_quota.json`). Poller seed 18 m cũ tắt (`MAPBOX_OD_FILE=` trống).
- [x] P1.1 worker probe chạy trên sol1 (tmux `probe`, `npm run start:prod`, node trong conda env riêng `/mnt/data8tb/minhkhoi/node-env`), `DATA_RAW_DIR`/`STATE_DIR` ở `/mnt/data8tb/minhkhoi/hcmc-traffic-rl/ingestion/`. `.env` chép tay, không commit.
- [ ] Người dùng: kiểm tra trang giá + ToS Mapbox, chạy thử 1 lượt, xem tỉ lệ Mapbox thực sự đi vào hẻm (`designed_alley_share_driven_median`).
- [ ] P1.2 TomTom (kiểm định), P1.3 YOLO camera, P1.4 nhu cầu, P1.5 fusion Bayesian.
- [ ] P2 trở đi.
