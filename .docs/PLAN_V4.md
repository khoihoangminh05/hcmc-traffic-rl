> **Từ 2026-11-02 kế hoạch chính là `PLAN_PAPER.md`.** File này giữ làm nhật ký kỹ thuật (số liệu, lỗi, quyết định) của V4.

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

## Trạng thái (cập nhật 01/11/2026)

- [x] P0: `.gitattributes` (hết 138 file "modified" giả do CRLF).
- [x] P1.1 thiết kế tuyến dò: `ml-core/data_fusion/design_probe_routes.py` → `ingestion-worker/config/probe_routes.quan4.json`. 100 tuyến, trung vị 1247 m, phủ 1563/1828 cạnh (hẻm 1359/1460) **nếu** Mapbox đi đúng tuyến thiết kế. Khoảng 86.8k request/31 ngày ở 28 lượt/ngày.
- [x] P1.1 poller: `ingestion-worker/src/mapbox/mapbox.probe.service.ts` (giờ VN 6–20, mỗi 30 phút, có trần tháng, resume giữa chừng, lưu JSON thô). `POST /mapbox/probe` để chạy tay.
- [x] P1.1 ghép cạnh: `ml-core/data_fusion/match_probe.py` + test `python -m data_fusion.test_match_probe` (MATCH_PROBE_TESTS_OK).
- [x] P1.1 (2026-10-30) theo docs Directions: driving-traffic nhận 25 tọa độ, nên mỗi tuyến có thêm tối đa 8 via ở giữa cạnh hẻm (`waypoints=0;N-1`, `bearings` ±45°) để ép đi đúng tuyến. Chế độ typical: `POST /mapbox/probe/typical?start=YYYY-MM-DD&days=7&stepMin=15`, `GET` để xem tiến độ; quota tháng chung cho live + typical (`state/mapbox_quota.json`). Poller seed 18 m cũ tắt (`MAPBOX_OD_FILE=` trống).
- [x] P1.1 worker probe chạy trên sol1 (tmux `probe`, `npm run start:prod`, node trong conda env riêng `/mnt/data8tb/minhkhoi/node-env`), `DATA_RAW_DIR`/`STATE_DIR` ở `/mnt/data8tb/minhkhoi/hcmc-traffic-rl/ingestion/`. `.env` chép tay, không commit.
- [x] P1.1 kiểm tra đầu tiên trên sol1 (2026-10-30, 2 lượt live + 12.9k typical):
  - Ghép: 85.6% quãng đường; 1091/1828 cạnh có số đo (hẻm 880/1460); trung vị 0.71 cạnh hẻm thiết kế được đi thật.
  - `congestion`: 0% ở hẻm, 2.1% ở đường thường. Mapbox không có phân loại ùn tắc cho Q4, chỉ có tốc độ.
  - Tốc độ thay đổi theo thời gian: cùng hình học, trung vị 33% đoạn đổi >2% giữa hai lượt; thời gian tuyến lượt sau/lượt đầu 0.84–0.96.
  - Typical: hồ sơ ngày rõ ràng (06h 0.86 → 17h 1.07 so với trung vị tuyến, biên độ khoảng 24%), thứ Hai và thứ Ba gần như trùng nhau, tức là hồ sơ lịch sử cố định theo ngày thường.
  - ~~Còn phải kiểm: live có khác typical cùng giờ không~~ → đã kiểm (2026-11-01, `probe_sol1.sh check`, live 30/10–01/11 với typical 02–08/11, ghép theo thứ trong tuần + khung 15 phút):
    - Live/typical: p10 / p50 / p90 = **1.00 / 1.00 / 1.00** ở cả hẻm (565.8k cặp) và đường thường (169.1k cặp). Trung vị theo ngày đều 1.00. Chỉ 13.3% (hẻm) và 10.5% (đường thường) số cặp lệch quá 5%.
    - Kết luận: ở Q4, "live" của Mapbox **gần như trùng hồ sơ lịch sử**. Fusion dùng Mapbox như **prior theo giờ** (hồ sơ typical), không phải số đo thời gian thực. Phần 10–13% lệch báo riêng như tín hiệu thời gian thực có thể có. Biến động thật phải đến từ camera (P1.3) và từ độ bất định hậu nghiệm (robust RL).
    - Hồ sơ typical theo giờ (so với trung vị cạnh): hẻm 1.21 lúc 9h, 0.83 lúc 13h; đường thường 1.12 lúc 5h, 0.89 lúc 19h.
    - Phủ: 1098/1828 cạnh có số đo (hẻm 880/1460), ghép được 84.8% quãng đường, trung vị 71% cạnh hẻm thiết kế được đi thật. `congestion` gần như luôn trống (hẻm 0%, đường thường 0.7%).
- [x] P1.1 kết thúc cào (chốt 2026-11-01): live 10 phút, 5–22 giờ, từ 30/10 tới **tối 07/11** (`MAPBOX_PROBE_UNTIL=2026-11-07T22:00:00+07:00`, worker tự dừng live); typical đủ 02–08/11 (07–08 xếp ngày 01/11). Dự kiến khoảng 70k/95k request tháng 11.
- [!] Sự cố dữ liệu (ghi để báo cáo trung thực): token Mapbox trả 401 "Invalid Token" từ 2026-10-30 21:42 (giờ VN). Mất toàn bộ live ngày 31/10 và typical từ slot 2026-11-05T06:00 trở đi (job vẫn đếm slot là xong). Poller không phân biệt lỗi token. Sửa: 401/403 thì tạm dừng cả hai chế độ, không tiến cursor; `match_probe` khử trùng lặp theo (route, departAt/timestamp); xếp lại typical 05–08/11; kéo live tới tối 07/11.
- [x] P2.2 (2026-10-30) mô phỏng meso GPU `ml-core/routing2/` (graph, demand, meso_gpu, policies, bench_meso). Hàng đợi không gian kiểu MATSim, đơn vị xe máy, vận tốc theo mật độ lúc vào cạnh, sức chứa ra/đỗ theo loại đường (prior, chờ hiệu chỉnh), đèn 2 pha, giải kẹt sau 180 s (tối đa 1 xe vượt sức chứa mỗi cạnh, có đếm). Baseline: ShortestPath, AppReroute (đo được: thời gian cạnh hiện tại), Mixed. Test `python -u -m routing2.test_meso` → MESO_TESTS_OK.
  - CPU, B=8, 30 phút mô phỏng: khoảng 200 giây mô phỏng / giây thực, khoảng 6k quyết định/s. Mới có 3 cạnh có đèn trong WCC (4 đèn snap được).
  - Quét nhu cầu (B=4, 30 phút): 1000 chuyến/giờ tự do; 2000 vừa (AppReroute nhanh hơn ShortestPath khoảng 6%); từ 3000 trở lên tắc nặng. Mức nhu cầu thật sẽ hiệu chỉnh theo hồ sơ tốc độ Mapbox.
  - GPU sol1 (2026-10-31, RTX 4090, 30 phút mô phỏng, 3000 chuyến/giờ): B=1024 chạy 41.8 s, khoảng 44k giây mô phỏng / giây thực, **khoảng 981k quyết định/s (qua cổng 1e4)**, 1.1 GB. Lần chạy này sol1 chưa có file đèn (artifacts không đồng bộ), nên test đèn hỏng; đã thêm dự phòng `sumo-env/quan4_osm_signals.json`.
  - Quét trên GPU (64 env): 1000 chuyến/giờ không gỡ kẹt; 2000 có khoảng 46 lần gỡ kẹt mỗi env và AppReroute **chậm hơn** ShortestPath (342 so với 314 s; thông tin trễ 60 s gây dao động); từ 3000 trở lên khoảng 380 lần gỡ kẹt mỗi env, tức là chế độ kẹt cứng. Kết quả local 4 env ngược lại, nên 4 env là quá ít.
  - P2.1 (2026-10-31) mạng SUMO mới `routing2/sumo_net.py` (netconvert từ plain XML: 1828 cạnh, 8057 kết nối, 3 đèn; id cạnh = alley_id; hẻm cấm ô tô; xe máy sublane). Mạng cũ `quan4_alleys.net.xml` viết tay **không có kết nối** (incLanes=""), xe không qua được giao lộ.
  - `routing2/sumo_check.py`: cùng chuyến, cùng tuyến free-flow, meso FixedRoute so với SUMO. Local (1 seed, 15 phút):
    - R² thời gian chuyến lần lượt 0.997 / 0.992 / 0.984 / 0.805 / 0.612 ở 500 / 1000 / 1500 / 3000 / 5000 chuyến/giờ.
    - R² **độ trễ** (thời gian chuyến trừ free-flow) chỉ −0.31 / 0.16 / 0.16 ở 1000 / 3000 / 5000. Meso tính trễ cao hơn SUMO khoảng 30–50% (16 so với 11, 70 so với 49, 87 so với 69 s).
    - Kết luận: cổng R² ≥ 0.8 trên thời gian chuyến qua ở nhu cầu thấp–vừa, nhưng chỉ vì phần free-flow giống nhau. Mô hình tắc nghẽn của meso **chưa khớp**. Bước tiếp: hiệu chỉnh cap / k_jam / speed_floor của meso theo SUMO (P2.3), và đặt cổng trên R² độ trễ.
  - sol1 (2026-10-31, 4 seed 61000–61003, 30 phút, libsumo), meso mặc định so với SUMO:

    | Chuyến/giờ | R² thời gian chuyến | R² độ trễ | Trễ SUMO (s) | Trễ meso (s) | Meso gỡ kẹt |
    |---|---|---|---|---|---|
    | 500 | 0.989 | −1.82 | 9.3 | 14.9 | 0 |
    | 1000 | 0.978 | −1.18 | 11.9 | 18.8 | 0 |
    | 1500 | 0.946 | −0.34 | 17.6 | 24.1 | 0 |
    | 2000 | −0.84 | −2.01 | 58.8 | 119.6 | 237 |
    | 3000 | −0.77 | −1.01 | 165.5 | 214.9 | 1421 |
    | 4000 | −0.53 | −0.75 | 197.6 | 259.2 | 3016 |

    SUMO 0 teleport ở mọi mức. **Cổng P2 trượt.**
  - Chẩn đoán (local, tách từng thành phần của meso ở 500 / 2000 chuyến/giờ):
    - Gần như toàn bộ trễ meso đến từ **giảm tốc tuyến tính theo mật độ ngay từ cạnh trống**. Tắt nó đi thì trễ giảm từ 14.6 xuống 0.2 s (500 chuyến/giờ) và từ 117 xuống 4.5 s (2000 chuyến/giờ), gỡ kẹt từ 219 về 0.
    - Đèn (3 cạnh) và sức chứa ra không đóng góp gì.
    - SUMO lúc vắng: thời gian chuyến ≈ 1.057 × free-flow (R² 0.999). Xe máy sigma 0.5 chạy dưới giới hạn khoảng 5%, không phải tắc.
    - SUMO 2000 chuyến/giờ: 74% time loss nằm trên hẻm, 16% trong giao lộ; top 5 cạnh giữ 36%. Đó là các điểm nghẽn hành lang và chỗ hẻm nhập đường lớn (nhường đường), meso chưa có cơ chế này.
    - SUMO tự so với chính nó (2 seed RNG tài xế, local 10 phút) chỉ đạt R² độ trễ từng chuyến khoảng 0.75–0.85. Đây là **trần**, nên cổng phải so với trần chứ không phải 0.8 tuyệt đối.
  - P2.3 (2026-10-31) thêm vào meso, mặc định **tắt** (hành vi cũ giữ nguyên, test cũ qua):
    - `speed_factor`;
    - `k_crit`: chưa giảm tốc khi mật độ dưới ngưỡng;
    - `storage_scale`, `cap_scale`;
    - nhường đường ở giao lộ không đèn: cạnh ưu tiên thấp bị giới hạn sức chứa theo chấp nhận khe Siegloch exp(−q(tc − tf/2))/tf, với q là lưu lượng đã làm mượt của các nhánh chính.
    - Mọi tham số chạy được theo từng env, nên mỗi ứng viên là một env trên GPU.
    - `sumo_check --sumo-seeds A B` ghi `sumo_trips_*.json` và trần SUMO-vs-SUMO.
    - `routing2.calib_meso` tìm ngẫu nhiên trong hộp rồi thu hẹp. Mục tiêu: 1 − R² độ trễ trên các chuyến SUMO giao được; chuyến meso chưa tới bị tính trễ tới hết horizon.
    - Chấm điểm trên seed test không dùng khi fit.
    - Smoke local (10 phút, 24 ứng viên × 3 vòng), R² độ trễ trên seed test: 1000 chuyến/giờ từ −0.58 lên 0.70 (trần 0.85); 2000 chuyến/giờ từ −0.26 lên 0.25 (trần 0.84).
  - ~~Cổng P2 (31/10): R² độ trễ từng chuyến ≥ 0.8 × trần~~, thay bằng cổng v2 bên dưới.
  - Hiệu chỉnh v1 trên sol1 (2026-10-31, `calib_meso_20261031T175951Z.json`, 128 ứng viên × 4 vòng, 1,5 giờ GPU, fit 61000–61001, test 61002–61003): **trượt ở mọi mức**. R² độ trễ từng chuyến của best trên test lần lượt 0.55 / 0.17 / −0.09 / −0.23 / −0.20 ở 500 / 1000 / 1500 / 2000 / 3000 chuyến/giờ (trần 0.86 / 0.64 / 0.75 / 0.66 / 0.95).
    - Best là meso **gần như không tắc**: trễ 13 s so với SUMO 54 s ở 2000 chuyến/giờ, 17 s so với 107 s ở 3000; meso giao 89% chuyến, SUMO 70%. cap ×2.4, storage ×2.6, tf 0.67 s (phi thực tế).
    - Nguyên nhân: mục tiêu R² từng chuyến phạt tắc sai chỗ (R² âm sâu) nặng hơn không tắc (R² ≈ 0), và trễ từng chuyến chủ yếu là nhiễu tài xế. Kết quả v1 không dùng.
  - Hiệu chỉnh v2 (2026-11-01): mục tiêu và cổng trên **ô trễ theo cạnh** (`routing2/edge_metrics.py`): trễ cộng dồn theo (cạnh, khung vào 5 phút), lấy từ exitTimes của SUMO vehroute và `hop_exit` của meso, cùng tổng trễ. Loss = (1 − R² ô) + |sai số tổng trễ| / tổng trễ SUMO. Thêm `alley_cap_scale` (sức chứa ra riêng cho hẻm, vì 74% time loss của SUMO nằm trên hẻm); tf trong [1.5, 3.5] s.
    - Local (1500 chuyến/giờ, 10 phút): trần SUMO-vs-SUMO R² ô 0.92–0.99, sai số tổng trễ 2–3%, cao hơn hẳn trần từng chuyến (0.78–0.93). Smoke 8 ứng viên × 2 vòng: R² ô từ −0.01 lên 0.25, sai số tổng trễ từ 43% xuống 13%.
  - Hiệu chỉnh v2 trên sol1 (2026-11-01, `calib_meso_20261101T140913Z.json`, 128 × 4, khoảng 3 giờ GPU): **trượt ở mọi mức**. R² ô trên test lần lượt 0.37 / 0.28 / 0.07 / −0.15 / −1.12 ở 500 / 1000 / 1500 / 2000 / 3000 chuyến/giờ (trần 0.99 / 0.98 / 0.99 / 0.90 / 0.99); sai số tổng trễ 21% / 2% / 27% / 59% / 12%.
  - Chẩn đoán theo cạnh (local, SUMO 1.27.1, 2000 chuyến/giờ, 2 seed):
    - Tuyến free-flow dồn khoảng 75% chuyến qua **một hành lang hẻm** (q4_2294442740 → 1987339152 → 1987339684 → 1987339682 → 10167948038). SUMO chỉ trễ khoảng 3.5 s/xe/cạnh ở đó (giảm tốc mượt, không có hàng đợi). Meso mặc định trễ 10–20 s/xe/cạnh: cap hẻm 0.5 xe/s gần bão hòa, tràn ngược lên đường tertiary phía trước.
    - 30% trễ của SUMO nằm ở **nhánh phụ** (hẻm nhập đường tertiary), lưu lượng thấp (30–110 xe) nhưng chờ 40–50 s/xe. Meso trong hộp v2 (tc ≤ 6 s) chỉ ra khoảng 1 s/xe. Cần tc khoảng 10 s mới tới mức đó.
    - Tham số toàn cục không gỡ được cả hai cùng lúc: chỉnh cho hành lang thì mất trễ ở nhánh phụ, và ngược lại. Bước tiếp: nhận dạng trực tiếp từ dữ liệu SUMO theo từng loại (hàm tốc độ theo mật độ trên hẻm, chấp nhận khe ở nhánh phụ) thay vì tìm hộp đen.
    - Mean delay của SUMO local (1.27.1) ở 2000 chuyến/giờ là 27 s, sol1 khoảng 50 s trên cùng seed fit. Cần ghim phiên bản SUMO cho tham chiếu.
  - **Lỗi nghiêm trọng (phát hiện 2026-11-01): `pick_zones` chỉ chọn 3 nút khác nhau cho 32 vùng** (30/32 vùng là cùng một nút). `torch.cdist` float32 trên tọa độ cỡ 1e7 m sai tới 2.8 km. Hệ quả: gần như mọi chuyến đi về cùng một điểm, nên "75% chuyến qua một hành lang" và hiện tượng meso kẹt từ 2000 chuyến/giờ là **giả**. Mọi kết quả routing2 trước ngày này (quét nhu cầu P2.2, bench, sumo_check, hiệu chỉnh v1 và v2) chạy trên nhu cầu sai. Giữ lại để báo cáo, không dùng. Đã sửa (float64, tọa độ trừ tâm) và thêm test `test_zones_distinct_and_spread`.
  - Sau khi sửa (local, SUMO 1.28.0, seed 61000–61001, 30 phút), meso mặc định so với SUMO:

    | Chuyến/giờ | R² thời gian chuyến | Trễ SUMO / meso (s) | Tổng trễ lệch | R² ô | Trần R² ô | Meso gỡ kẹt |
    |---|---|---|---|---|---|---|
    | 1000 | 0.995 | 12.7 / 17.9 | 47% | 0.08 | 0.98 | 0 |
    | 2000 | 0.992 | 15.1 / 20.4 | 41% | 0.11 | 0.98 | 0 |
    | 3000 | 0.986 | 19.4 / 22.7 | 20% | 0.13 | 0.92 | 0 |
    | 5000 | 0.848 | 46.9 / 29.1 | 40% | 0.03 | 0.84 | 0 |

    - Không còn kẹt ở mức nào. Lệch còn lại là vị trí trễ: ở 5000 chuyến/giờ, SUMO dồn trễ vào vài ngã nhập hẻm → tertiary (top 20 cạnh chiếm 59% trễ, có nhánh phụ chờ khoảng 120 s/xe, và cả đường tertiary đi vào các nút đó). Meso rải đều trễ lên hẻm (top 20 cạnh chỉ 8%).
    - Hiệu chỉnh nhỏ local (24 × 3, tc tới 10 s): R² ô 0.27 (2000) và 0.03 (5000), vẫn trượt. Tham số toàn cục không tái tạo được trễ phụ thuộc hình học từng nút. Hướng tiếp: hàm trễ theo từng cạnh/nút fit từ SUMO trên nhiều mức nhu cầu và nhiều bộ tuyến, kiểm định trên bộ tuyến giữ lại; SUMO làm tầng fine-tune và đánh giá cuối.
  - Thử giai đoạn 2 (local, 2026-11-01): hệ số sức chứa theo từng cạnh, cập nhật nhân có giảm chấn, fit trên 2 bộ tuyến (free-flow, nhiễu σ=0.3 bộ 1), kiểm trên bộ tuyến giữ riêng (σ=0.3 bộ 2). **Phân kỳ**: chỉ một bước cập nhật đã làm meso kẹt cứng (loss từ 1.23 lên khoảng 1400). Trễ ở ngã nhập của SUMO là chờ khe kéo dài nhưng vẫn trôi, còn hàng đợi meso có ngưỡng: dưới sức chứa thì gần như 0, vượt là tràn ngược khắp mạng. Tắt mặc định (`--edge-iters 0`). Sau cùng R² ô trên bộ tuyến giữ riêng: 0.31 (2000 chuyến/giờ), −0.32 (5000).
  - Hệ quả cho kế hoạch: meso hàng đợi không tái tạo được trễ ngã nhập của SUMO bằng cách hiệu chỉnh. Đề xuất: **train và đánh giá MARL trực tiếp trong SUMO (libsumo, nhiều tiến trình)**, meso chỉ dùng để thử nhanh. Thời gian SUMO đo được trên sol1: 30 phút mô phỏng, 3000 chuyến/giờ, khoảng 14–19 s/episode/tiến trình khi chưa có điều khiển.
  - **Quyết định (2026-11-01, người dùng duyệt): train và đánh giá MARL trực tiếp trong SUMO 1.28.0.** `routing2/sumo_env.py`: xe được điều khiển chọn cạnh kế tiếp ở mỗi nút (chỉ trong các kết nối SUMO cho phép), quan sát chỉ gồm thứ đo được (free-flow, thời gian cạnh hiện tại của SUMO, số xe trên cạnh, free-flow tới đích). `routing2/bench_sumo.py`: local TraCI, 2000 chuyến/giờ, 10 phút, 100% điều khiển: 9.8k quyết định, khoảng 30 quyết định/chuyến; chế độ `ff` cho thời gian đi trung bình bằng chế độ không điều khiển (182.9 so với 183.1 s), tức phần điều khiển đúng.
  - sol1 (2026-11-02, libsumo, 80 nhân, 3000 chuyến/giờ, 30 phút): không điều khiển 8.9 s/episode; 100% điều khiển 16.5 s (ff, 53.7k quyết định, thời gian đi 226.9 s so với 227.0 s khi không điều khiển) và 13.4 s (app, 228.5 s). Ở 3000 chuyến/giờ app không hơn free-flow, vì mạng chưa đủ tắc; nên train ở 4000–7000 chuyến/giờ.
  - `routing2/sumo_marl.py` (v1): PPO, policy dùng chung kiểu pointer (chấm điểm từng lối ra từ đặc trưng đo được, không dùng id nút/vùng), critic trên đặc trưng gộp + giờ. Reward v1 = −(thời gian tới quyết định kế tiếp)/60, tức **ích kỷ**: run đầu là baseline MAPPO-selfish cho ablation, chưa phải phương pháp chính (difference reward làm sau). Eval mỗi 25 update trên seed 50000+ so với ff và app; `best.pt` theo thời gian đi trung bình của mọi chuyến. Smoke local qua.
  - Run `sumo_marl_selfish_20261102T090557Z_seed42` (sol1) khởi động ngoài ý người dùng (lệnh train nằm chung khối với smoke) và **đã dừng trước update đầu tiên**. Không dùng. Thứ tự đã chốt: cào Mapbox tới 07/11 → fusion tốc độ toàn mạng → hiệu chỉnh nhu cầu SUMO theo tốc độ đó → mới train MARL. Trước đó chỉ phát triển code và smoke local.
  - Cổng A, thử local (2026-11-02; 6000 chuyến/giờ, cầu 20 phút, **1 seed cầu**, 15 vòng, chạy lại 6 seed SUMO mới; TTT giờ, trung bình ± sd): đường ngắn nhất 180.7 ± 12.1; UE (PSwap) 173.8 ± 2.8; SO chi phí biên trên chính cạnh 182.2 ± 3.9; **SO có thêm ngoại ứng ở ngã nhập (`so_x`) 172.3 ± 2.3**. `duaIterate --marginal-cost` exp 1: 214.8 (Gawron), 203.1 (logit), 1 seed.
    - SO theo cạnh **tệ hơn UE 4.8%**, thêm ngoại ứng ngã nhập thì tốt hơn UE 0.85% và tốt hơn SO theo cạnh 5.4% (chênh theo từng seed 5.0–18.1 giờ). Giả thuyết: trễ ngã nhập là ngoại ứng **giữa các cạnh** mà chi phí biên theo cạnh không thấy. Mới 1 kịch bản.
    - UE − so_x = 1.5 giờ (sd khoảng 2.4 trên 6 seed): **chưa phân biệt được với 0**. Cổng A chưa kết luận. Đường ngắn nhất có đuôi nặng (169.6–197.6), UE và so_x hẹp hơn nhiều.
    - Tín hiệu "UE tệ hơn đường ngắn nhất 6.7%" báo trước đó **đã rút lại**: do MSA chưa hội tụ và chỉ 2 seed chạy lại. Hàm tóm tắt lúc đó cũng lấy nhầm iterate.
  - App phản ứng, cùng chuyến (2026-11-02, local, 6000 chuyến/giờ, 1 seed cầu, 6 seed SUMO; p = 1). Thời gian cạnh đo từ **hành trình của xe** (`live_source=probe`): đường ngắn nhất 172.6 ± 2.6; app đổi liên tục 173.1 ± 5.9 (km +4%); app chỉ đổi khi lợi ≥ 10% 184.3 ± 18.7 (162.6–209.0). Với `edge.getTraveltime` tức thời: app 235.9 và 237.3. **Con số 37% là do thước đo nhiễu của chính app, không phải hiện tượng cần báo cáo như lợi ích điều phối.** Ở kịch bản này mọi cách đều 172–174, tức gần như **không có đất cho định tuyến**. Đuôi 170–198 của đường ngắn nhất từ `gate_msa` không lặp lại trong env (169–176), chưa rõ do cách sinh tuyến hay do seed.
  - Hàm mục tiêu (2026-11-03, `routing2/objectives.py`, người dùng yêu cầu): T_all = thời gian đi trung bình của mọi chuyến, T_cust = của khách hàng, chỉ số tắc = T_all / T_ff, J = w T_all + (1 − w) T_cust. Mẫu số là mọi chuyến trong cầu; đồng hồ tính từ giờ xuất phát dự kiến; chuyến chưa xong cộng thêm thời gian free-flow còn lại. `Episode.metrics` có ở mọi lần chạy env; `sumo_marl` đánh giá có `--eval-drain` (mặc định 900 s) và chọn `best.pt` theo J. `Episode.ttt_s` giữ nguyên, nên `gate_app` không đổi. Kiểm trên mạng thật (3000 chuyến/giờ, cầu 5 phút, p = 0.5): số cũ 121.1 s khi cắt ở 300 s, số mới 228.6 s, chạy xả hết 235.6 s. Reward train vẫn ích kỷ, chưa có thông tin ý định.
  - Ý định và thời gian đo từ xe (2026-11-03, `sumo_env.py`, `sumo_marl.py`, test `routing2/test_sumo_features.py`): thêm đặc trưng số xe khác trong đội đã chọn cạnh mà chưa vào (`FEAT_INTENT`) và thời gian tới đích theo giờ sống (`FEAT_LIVE_TOGO`). `sumo_marl` dùng thời gian cạnh từ probe (30 s), baseline app dùng `live_cost`; đầu vào policy 11 chiều, có `load` = (số xe trên cạnh + ý định) / 10 m. Mặc định của env giữ đặc trưng cũ. Đo local (TraCI, 6000 chuyến/giờ, cầu 15 phút, p = 0.5, free-flow, 1 seed): cùng kết quả T_all 290.0 / T_cust 287.8 s, chi phí 91.1 → 94.9 s (+4%); 33.8% quyết định thấy ít nhất 1 xe khác đã chọn cùng cạnh, 5.8% thấy ít nhất 3, tối đa 12; 1.7% quyết định có xe khác chọn cùng cạnh trong cùng bước nên không thấy nhau. Còn lại: số xe trên cạnh vẫn đếm mọi xe, thứ nhà cung cấp không đo được khi p < 1. w = 0.5 do người dùng chốt.
  - Chế độ micro (2026-11-03, người dùng chốt, `SumoEnvConfig.micro`, `sumo_marl` bật mặc định): SUMO chạy tới thời điểm sớm nhất có xe phải chọn (sắp hết cạnh trong 10 m hoặc 3 s, hoặc vừa xuất phát); nhiều xe cùng lúc thì phục vụ từng xe theo thứ tự ngẫu nhiên, xe sau thấy lựa chọn của xe trước. Đặc trưng số xe chỉ đếm xe trong đội. Báo cáo probe 10 s. Thêm sự kiện học sinh tan học (mọi cạnh quanh một nút chậm 1.5 m/s trong 900 s) bên cạnh tai nạn; lịch theo seed, giống nhau giữa các policy. Thiết kế state rút gọn: congestion từ báo cáo, số xe đội, hẻm hay không, qua GNN; bỏ σ², ý định nhiều mốc, đầu suy luận đối thủ, thưởng thông tin. Đo local (TraCI, 6000 chuyến/giờ, cầu 10 phút, p = 0.5, 1 seed): free-flow micro cho cùng T_all 278.2 / T_cust 277.3 s với cách cũ, wall 81.7 → 96.4 s; app 71.9 → 104.5 s. Mạng ngẫu nhiên chưa train: gần 100k quyết định, 418 s, T_cust 1340 s, tức xe đi lang thang.
  - GNN và mạng quyết định (2026-11-03, `routing2/gnn_policy.py`, test `routing2/test_gnn_policy.py`): GNN 3 lớp trên line graph, truyền hai chiều, chạy lại mỗi 10 s; actor gồm attention giữa các lối ra và MLP sâu, luôn lấy mẫu kể cả khi eval; critic tập trung có GNN riêng, thấy số xe và tốc độ thật của mọi xe; minibatch theo chu kỳ báo cáo. 181k tham số. Giới hạn đi vòng `max_detour` = 0.5 + 60 s, áp dụng cho mọi controller. Đo local (TraCI, 6000 chuyến/giờ, cầu 10 phút, p = 0.5, 1 seed): app có và không có giới hạn T_all 269.4 / 269.6 s; mạng ngẫu nhiên có giới hạn 37.7k quyết định, T_all 530.9, T_cust 692.2 s, 97 xe chưa xong (mạng ngẫu nhiên không giới hạn, kiến trúc cũ: gần 100k quyết định, T_cust 1340 s). Thời gian chạy lần này không dùng được vì máy bận (app 259 s so với 104 s trước đó). Reward vẫn ích kỷ.
  - Reward (2026-11-03). Thử chia trễ cho xe gây ra (`sumo_env._attribute`), kiểm bằng chạy lại khi bỏ nhóm 10% chuyến (`routing2.check_externality`, free-flow, 6000 chuyến/giờ, cầu 10 phút, p = 1). 8 nhóm ngẫu nhiên, seed 61000: tính 3336 s, đo 7754 s, tương quan −0.30. Ba seed 61000–61002, trung bình tính / đo (s): nhóm bị tính nhiều nhất 14333 / 7685, nhóm ít nhất 11 / −9311, nhóm ngẫu nhiên 3998 / 11447. Nhiều nhất hơn ít nhất 3/3 nhưng thua ngẫu nhiên 3/3. Bỏ 100 chuyến gần như không bị tính vẫn làm các xe khác lâu hơn tới 16036 s, tức nhiễu của phép đo lớn cỡ tín hiệu; chưa đo sàn nhiễu. Kết luận: **không dùng cách chia này làm mặc định**, giữ `--reward attrib` để đối chiếu. Mặc định chuyển sang `--reward team`: r = −[(1 − ρ) dt + ρ I / tốc độ trung bình] / 60, với I là tích phân của w (chuyến trong hệ / chuyến) + (1 − w) (khách trong hệ / khách), đúng bằng J khi mọi chuyến xong; ρ = 0.5 là giá trị chọn tay, chưa đánh giá.
  - Train thử lần 1 (2026-11-03, sol1, `sumo_marl_trial_team_20261103T105554Z_seed42` và `sumo_marl_trial_selfish_20261103T105554Z_seed42`, commit 21fd77a): cả hai chết trước update đầu tiên, `OSError: [Errno 24] Too many open files`. Trọng số gửi sang worker dưới dạng tensor, mỗi tensor một file descriptor mỗi tác vụ. Đã sửa bằng numpy. Không có số liệu, không dùng.
  - Train thử lần 2 (2026-11-03, sol1, `sumo_marl_trial_team_20261103T115415Z_seed42` và `sumo_marl_trial_selfish_20261103T115415Z_seed42`, commit d09711b, nhu cầu giả). Eval update 25 (J, s): team 324.75, selfish 319.82, ff 303.25, app 300.17, greedy 378.46. Entropy còn 0.039 / 0.021 ở update 32–33. **Không dùng.**
  - Rà soát so với v3v (2026-11-03). (1) Reward team tương quan 0.996 với reward ích kỷ trên từng quyết định (đo local, TraCI, 6000 chuyến/giờ, 15 phút, p = 0.5, 1 seed, ff và app, chưa đo trên RL), tức gần như không mang ngoại ứng; ablation share0 của v3v cũng thua greedy khi bỏ phạt dồn xe. (2) Theo tính toán, mỗi update khoảng 270 bước Adam ở lr 3e-4, v3v khoảng 12 bước ở lr 1e-4: khoảng 68 lần. (3) 39–41% quyết định chỉ có một lựa chọn. (4) Chỉ số tắc 1.23–1.25, app không hơn ff trên nhu cầu đồng đều: ít đất cho định tuyến. (5) Thiếu tín hiệu dẫn đường và entropy giảm dần của v3v. Người dùng chốt: Mapbox chỉ làm state sát thực tế hơn, thiếu nó vẫn train được bằng số giả hợp lý.
  - Thiết kế v5 (2026-11-04, người dùng duyệt): reward train −(dt + β·C)/60 + tín hiệu thế năng theo thời gian còn lại, C = số xe trên cạnh sắp vào × (cap nhỏ nhất / cap cạnh); chỉ dùng khi train, điểm vẫn là T_all, T_cust, J. lr actor 1e-4, critic 5e-4, entropy 0.03 → 0.005 qua 400 update, 12 bước Adam mỗi update. Xe chỉ có một lối ra không được hỏi. Nhu cầu giả có cao điểm (`--hot-share`, `--peak-sd`), số tự đặt, không đo. Train cùng lúc β = 0, 8, 25 (25 ≈ mức phạt hẻm của v3v).
  - `routing2.check_demand` (local, TraCI, 1 seed 50000, cửa sổ xuất phát 600 s, xả tới 1800 s, p = 0.5; J của ff / app / greedy q=0.5 / greedy q=2): hot 0.3: 6000 chuyến/giờ 345.1 / 334.3 / 339.3 / 383.5, 8000 408.7 / 442.8 / 484.9 / 515.5, 10000 530.1 / 559.5 / 558.8 / 644.2. Hot 0.6: 6000 322.0 / 320.0 / 318.5 / 364.3, 8000 445.1 / 446.8 / 409.2 / 584.4, 10000 564.7 / 490.8 / 541.3 / 713.7. Chỉ số tắc 1.6–3.7. Ff thua baseline tốt nhất 8.1% và 13.1% ở hot 0.6, 8000 và 10000; nhưng hot 0.3 đảo dấu và baseline tốt nhất đổi theo mức nhu cầu, nên 1 seed còn nhiễu. Greedy q=2 luôn tệ nhất, chọn q=0.5 làm baseline. Chọn hot 0.6, train 6000–10000, eval 8000 và 10000.
  - Thiết kế v6 (2026-11-04, thay v5 trước khi train; người dùng: v3v chỉ để tham khảo, không phạt ép tay, mọi thuật toán chung một môi trường không lý tưởng và chỉ biết trong giới hạn thực tế). Bỏ β·C. Reward mặc định `attrib`: −[a(dt + D_cust) + b·D_other]/60 + tín hiệu thế năng, D là trễ đo được chia cho xe gây ra, a và b suy ra từ J; kiểm bằng chạy lại trước đó chưa kết luận vì chưa đo sàn nhiễu. Giới hạn chung cho mọi controller: mất 20% báo cáo, sai số thời gian 10%, số xe đội lấy theo báo cáo gần nhất, tài xế theo chỉ dẫn 90%, 30% xe nền dùng app khác (thiết bị rerouting SUMO), actor không biết tỉ lệ đội. Các số này tự đặt, sẽ quét. Critic và reward vẫn dùng trạng thái thật, chỉ khi train.
  - `routing2.check_demand` với giới hạn trên (local, 1 seed 50000, hot 0.6, p = 0.5; J của ff / app / greedy q=0.5): 8000 chuyến/giờ 526.3 / 408.4 / 449.3, 10000 557.3 / 511.5 / 540.6. Chỉ số tắc 2.09–2.89. App hơn ff 22.4% và 8.2%. 1 seed.
  - `routing2.check_demand` 4 seed trên commit 2056cb3 (sol1, chưa có giới hạn thực tế, hot 0.6, p = 0.5; J của ff / app / greedy q=0.5): 8000 chuyến/giờ 422.3 / 416.3 / 416.8, 10000 518.2 / 545.2 / 514.1. Ff chỉ thua 1.4% và 0.8%, tức 8.1% và 13.1% của 1 seed ở trên là nhiễu.
  - Run `sumo_marl_v6_attrib_20261104T051159Z_seed42` và `sumo_marl_v6_selfish_20261104T051400Z_seed42` (sol1): chạy nhầm trên commit 2056cb3 vì chưa `git pull`, nên thiếu giới hạn thực tế. Đã yêu cầu dừng. **Không dùng.**
  - `routing2.check_demand` 4 seed trên commit 282b34a (sol1, có giới hạn thực tế, hot 0.6, p = 0.5; J của ff / app / greedy q=0.5): 8000 chuyến/giờ 448.0 / 420.8 / 470.3, 10000 559.5 / 501.5 / 510.5. App hơn ff 6.1% và 10.4%. Chỉ số tắc 2.18–2.88, teleport 10.1–15.9 trên 1000 chuyến. Chưa có độ lệch giữa các seed.
  - Run v6 đúng code khởi động trên 282b34a lúc 14:58 và 15:00 ngày 04/11 (tmux `v6_attrib`, `v6_selfish`, load 23.9). Mức cần vượt là baseline tốt nhất trong chính eval, không mặc định là `app`.
  - Eval update 25 của hai run v6 (4 seed 50000+, 8000 và 10000 chuyến/giờ, p = 0.25 và 0.75, J): rl `attrib` 762.42, rl `selfish` 765.99, ff 485.84, app 489.74, greedy q=0.5 491.29. Entropy còn 0.97–1.00. Ba baseline gần như ngang nhau, nên mức hơn 6.1% và 10.4% của app trong `check_demand` (p = 0.5) không giữ được khi lấy trung bình qua p = 0.25 và 0.75. `train_mean_tt_s` cắt ở 900 s, eval chạy thêm 900 s, nên hai số không so được với nhau.
  - Đo baseline trên 282b34a (sol1, `diag_v6`, 8 seed 50000–50007, 8000 và 10000 chuyến/giờ, p = 0.25, 0.5, 0.75, 144 tập; J): app 485.5, ff 491.1, greedy q=0.5 494.1. So cặp trên cùng kịch bản: app hơn ff 0.7% (sai số chuẩn 1.5%), thắng 54% kịch bản; greedy thua ff 1.1% (sai số chuẩn 1.7%). Độ lệch chuẩn J giữa các seed khoảng 60. Ba baseline không phân biệt được, nên mọi chênh lệch dưới khoảng 3–4% trên 48 cặp kịch bản là nhiễu.
  - Critic của `attrib` tại update 25 (8 tập, seed 90000+, thời gian tối đa 900 s): EV 0.24–0.33 với reward attrib, top 1% mẫu chỉ chiếm 6–8% MSE nên giả thuyết vài xe cá biệt không đúng. 66% xe điều phối bị cắt ở 900 s khi chưa tới đích. Tương quan phần reward chưa shaping attrib và selfish trên từng quyết định: 0.956; 60% quyết định có phần phạt bằng 0.
  - Eval update 50: rl `attrib` 600.28, rl `selfish` 648.36 (ff 485.84). Cùng checkpoint `attrib` update 50 trên 4 seed, 8000 và 10000 chuyến/giờ, p = 0.25 và 0.75 (J): lấy mẫu 600.3, nhiệt độ 0.5 537.0, nhiệt độ 0.25 524.1, argmax 518.0, chọn đều trong các lối ra 1032.6. Teleport của argmax 23.4 trên 1000 chuyến, baseline 12–14: teleport không tính vào J nên cần kiểm tra độ nhạy trước khi công bố.
  - Thêm `routing2.eval_heldout`: seed 60000+, so cặp theo seed, khoảng tin cậy bootstrap, báo cả `sample` và `argmax`. Mode dùng cho bài báo phải chọn trên seed 50000+.
  - Eval update 75: rl `attrib` 534.11, rl `selfish` 549.79. Argmax `attrib` update 75 (4 seed 50000+, 8000 và 10000 chuyến/giờ, p = 0.25 và 0.75; J): 490.02, app 489.74, ff 485.84; so với ff −0.86% (khoảng tin cậy 95% −2.05 đến 0.84). Theo mức cầu: 8000 chuyến/giờ 434.55 so với ff 452.53, 10000 chuyến/giờ 545.49 so với ff 519.15. Chưa phân biệt được với baseline.
  - Độ nhạy teleport, cùng checkpoint và kịch bản (`--time-to-teleport` 600 thay cho 180; J): ff 543.22, app 573.34, argmax 638.47; tỉ lệ xe tới đích 0.965, 0.955, 0.897. Argmax thua ff 17.53% (khoảng tin cậy 95% −27.59 đến −9.02). Ở 180 s, teleport đang giải phóng tắc nghẽn và cả ba đều phụ thuộc vào nó, argmax nhiều nhất. Policy được train ở 180 s nên đây là kiểm tra ngoài điều kiện train, nhưng kết quả bài báo phải nêu.
  - Eval update 100 và 125 (rl lấy mẫu, J; ff 485.84, app 489.74, greedy 491.29): `attrib` 510.75 rồi 516.83, `selfish` 509.94 rồi 506.02. Entropy tại update 131: `attrib` 0.124, `selfish` 0.052.
  - Cận phân bổ tĩnh trên nhu cầu v6 (`gate_msa`, p = 1, không sự cố, 15 vòng, 3 seed, 3 seed SUMO mới; TTT theo giờ): 8000 chuyến/giờ ff 166.51, UE 167.60, SO_x 167.13; 10000 chuyến/giờ ff 258.00, UE 255.39, SO_x 254.56. UE và SO cuối gần như bằng ff. Tập đường tốt nhất tìm được, chạy lại trên seed mới: khoảng 153.6 (hơn ff 7.7%) và 249.5 (hơn ff 3.3%). Đây không phải cận trên của điều khiển thích nghi.
  - Quét dạng nhu cầu cùng phép đo, không có SO. Theo thứ tự hot, số vùng nóng, tỉ lệ vào; 8000 rồi 10000 chuyến/giờ; ff, UE, tập tốt nhất trên seed mới: 0.0/4/0.7: 162.9, 169.2, 161.0; 243.2, 289.2, 251.4. 0.3/4/0.7: 161.2, 166.7, 166.8; 249.8, 249.9, 243.4. 0.6/8/0.7: 176.8, 189.1, 185.3; 274.0, 289.1, 264.1. 0.6/4/0.3: 173.7, 165.8, 169.4; 246.2, 253.2, 245.7. 0.9/2/0.7: 201.5, 202.7, 189.2; 387.1, 324.8, 345.9. Lợi ích của tập tốt nhất so với ff từ −4.8% đến 10.6%, chỉ dạng 0.9/2/0.7 có lợi rõ (6.1% và 10.6%). Với 3 seed, sai số cùng cỡ phần lớn các chênh lệch này.
  - Argmax update 125 (4 seed 50000+, cùng kịch bản với eval; J; app 489.74, ff 485.84): `selfish` 471.91, so với app 3.64% (khoảng tin cậy 95% 0.67 đến 8.38), so với ff 2.87% (−1.72 đến 10.29), teleport 11.6 trên 1000 chuyến. `attrib` 482.65, so với app 1.45% (−2.75 đến 5.37), so với ff 0.66% (−4.89 đến 5.71), teleport 18.3. Seed này cũng dùng để chọn checkpoint, khoảng tin cậy từ 4 seed chỉ để tham khảo, không phải kết quả bài báo.
  - Eval update 150 (rl lấy mẫu, J): `attrib` 508.31, `selfish` 483.82.
  - Argmax update 125 trên 4 seed mới 50004–50007 (J; ff 483.25, app 494.81): `selfish` 489.67, so với ff −1.33% (−5.20 đến 1.01); `attrib` 494.44, so với ff −2.31% (−6.69 đến 1.48). Lợi thế 2.87% của `selfish` trên 4 seed trước không lặp lại. Trung bình cả 8 seed: `selfish` 480.8, `attrib` 488.6, ff 484.5, app 492.3. Theo mức cầu của `selfish`: 8000 chuyến/giờ 430.7 so với ff 447.9, 10000 chuyến/giờ 530.9 so với ff 521.2.
  - Teleport 600 s, argmax update 125, 4 seed 50000+ (J; ff 543.22, app 573.34): `attrib` 527.29, so với ff 2.93% (−17.19 đến 20.10), tới đích 0.974; `selfish` 566.13, so với ff −4.22% (−19.24 đến 13.40), tới đích 0.942. Argmax `attrib` update 75 thua ff 17.53% ở cùng phép đo nên phần phụ thuộc teleport giảm mạnh theo huấn luyện. Khoảng tin cậy còn rất rộng.
  - Eval update 175 (rl lấy mẫu, J): `attrib` 530.65, `selfish` 491.58.
  - Teleport 300 s, argmax update 125, 4 seed 50000+ (policy train ở 180 s; J): `attrib` 496.99, `selfish` 499.80, ff 513.27, greedy 522.62, app 524.56. `selfish` so với ff 2.62% (−9.82 đến 14.12), so với app 4.72% (0.34 đến 8.98). Theo mức cầu của `selfish`: 8000 chuyến/giờ 432.15 so với ff 460.92, 10000 chuyến/giờ 567.45 so với ff 565.62. Điểm của ff tăng từ 485.84 lên 513.27 khi tăng thời gian teleport, tức 180 s che bớt tắc nghẽn.
  - Đánh giá lại v3v: ở 50 xe, điểm hơn greedy 39.7 s, trong đó thời gian đi chỉ 3.3 s (0.7%), phần còn lại là phạt dồn xe tự đặt mà greedy không tối ưu (`greedy_city` chưa từng có). Ở 100 xe, hơn 68 s, thời gian đi 25.6 s (4.8%). Môi trường BPR do mình viết, quan sát có sẵn dự báo và câu trả lời của greedy, không có xe nền. Không dùng các con số này làm bằng chứng cho v4.
  - Thiết kế v7 (`d0b5d71`, cùng mạng, cùng baseline, chỉ đổi những điểm đã đo): teleport 300 s là mặc định SUMO; `--horizon 1500 --eval-drain 300` để train thấy cả phần xả tắc thay vì cắt ở 900 s; `--tph 7000 11000` để 10000 không nằm ở rìa khoảng train; eval và chọn `best.pt` theo argmax trên 8 seed, baseline chỉ chạy một lần; thêm 24 bước chỉ học critic mỗi update; log EV và tỉ lệ xe bị cắt; lưu checkpoint mỗi lần eval.
  - Kết quả cuối v6 (hết 300 update, 8 seed 50000+, teleport 180 s, 8000 và 10000 chuyến/giờ, p = 0.25 và 0.75; J; ff 484.55, app 492.27). `selfish`: `last` update 300 argmax 511.46, so với ff −5.55% (−9.25 đến −1.27); `best` update 150 argmax 502.46, −3.70% (−8.05 đến 0.70). `attrib`: `last` update 300 argmax 491.23, −1.38% (−4.86 đến 2.02); `best` update 250 argmax 497.64, −2.70% (−8.27 đến 1.48), lấy mẫu 491.80, −1.50% (−6.24 đến 2.44). Argmax update 125 của `selfish` (480.8) không giữ được: eval dao động và không tăng đều theo update. v6 không thắng ff. Một seed train cho mỗi reward.
  - Cận tĩnh ở teleport 300 s (cùng phép đo, 3 seed; TTT theo giờ): 8000 chuyến/giờ ff 166.06, UE 172.66; 10000 chuyến/giờ ff 253.69, UE 262.21; `gap_ue_best_known` 5.11% và 8.78%. UE không tốt hơn ff.
  - v7 giữa chừng (5/11 10:23; argmax, 8 seed 50000+, teleport 300 s; ff 503.48, app 503.20, greedy 517.16): `selfish` update 225 là 510.46, `attrib` update 200 là 502.52 sau khi dao động 527–587. Khi cầu 8000: `attrib` 436.16 so với ff 448.69; khi cầu 10000: 568.88 so với ff 558.27. Critic: EV 0.76–0.82 (v6 update 25: 0.24–0.33); tỉ lệ xe bị cắt khoảng 6%. Tốc độ 2.4 phút mỗi update.
  - v7 cuối (5/11, argmax, 16 seed mới 50008–50023, teleport 300 s, chưa đụng 60000+; ff 507.37, app 508.38, greedy 506.37): `selfish` u200–u300 = 536.58, 510.22, 506.52, 519.87, 515.21; `attrib` u200–u300 = 533.14, 531.83, 527.21, 540.92, 519.21. Tốt nhất `selfish` u250 hơn ff 0.17% (CI −3.01, 3.08): hoà. `best.pt` của `attrib` (u200) được 502.52 trên 8 seed chọn nhưng 533.14 trên seed mới: chọn trên 8 seed không đáng tin. Teleport 600 s (8 seed): greedy 523.31, app 537.79, selfish u250 547.34, ff 549.34, selfish u300 577.86, attrib u300 589.48, attrib u200 598.45.
  - v7 theo ô (16 seed, so với ff, T_all): `selfish` u250 lần lượt 8000/p0.25 +4.5%, 8000/p0.75 +1.7%, 10000/p0.25 −6.0%, 10000/p0.75 −0.5%. Luận điểm phối hợp chưa được chứng minh: ở 8000, mọi checkpoint đã đọc đều lợi ít hơn khi p cao (p0.25 → p0.75: selfish u250 +4.5 → +1.7; selfish u300 −1.5 → −4.4; attrib u300 +3.8 → −1.4; attrib u200 +3.4 → −10.0). Quy tắc đơn giản từng thắng ở 10000: greedy p0.25 +4.0%, app p0.75 +2.1%, nên ở đó còn đường thắng.
  - Thiết kế v8 (`95ccf75`, chạy từ 5/11 19:51, seed 42, `selfish` và `attrib`, 300 update): mạng khởi đầu đúng bằng ff và học phần chỉnh (`--prior 120`, không học theo dữ liệu mẫu; kiểm: chưa huấn luyện cho J 507.71, trùng ff); thêm đặc trưng số xe đội trên đường đi tới đích; GNN 6 lớp thay vì 3; critic học riêng 10 update đầu; learning rate actor giảm còn 10%; chọn checkpoint trên 16 seed; `_attribute` theo giới hạn tốc độ của sự kiện và bỏ xe đang đứng ở nhánh khác (chưa tính quyền ưu tiên). A1, A5 có từ `4d4118d`: từ v8, điểm dùng SUMO seed theo seed kịch bản nên không so trực tiếp với v7. Chạy kèm `tune_baselines` trên 40000–40007.
  - Mô phỏng sửa (5/11, hẻm 1.25 m mỗi chiều, lateral 0.4 m, seed 40000–40007, 32 episode mỗi phương án): ff 537.59, app 543.35, greedy q 0.25/0.5/1/2/4 = 559.13, 532.74, 586.20, 713.92, 773.11. q đơn điệu không rõ, chênh ff và greedy q 0.5 nằm trong nhiễu. Teleport va chạm giảm mạnh: ff 0.3, greedy q 0.5 2.4 trên 1000 chuyến (v8 cùng SUMO seed theo kịch bản ở mô phỏng cũ: ff 5.6).
  - v8 bị dừng ở update 5 và tune_v8 ở 5%: chạy trên mô phỏng cũ, không có kết quả dùng được. Người dùng cho phép khởi đầu bắt chước (5/11), bỏ ràng buộc cũ.
  - Thiết kế v9 (`a059d2a`, chạy từ 5/11 20:49): mô phỏng sửa; mạng khởi đầu đúng bằng greedy q 0.5 (`--prior-rule greedy`); 36 bước Adam mỗi update thay vì 12, vốn chỉ dùng khoảng 1/3 kỳ báo cáo; `selfish`, `attrib` 600 update, p 0.1–1; `attrib` p 0.1–0.5 làm phép thử việc trộn nhiều mức đội xe, 8 worker, 300 update. Lần khởi động đầu lúc 20:45 hỏng do đường dẫn `~` sai, không có dữ liệu. Chưa giải thích được 1.75 m và kiểm 0.2 m chưa xong: rủi ro đã nêu với người dùng.
  - v9 (khởi đầu greedy) dừng ở update 0–2 lúc 21:21: trên 16 seed chọn 50000–50015, mạng chưa học trùng greedy 555.88, nhưng ff 531.23, app 564.77 (8000: ff 476.48, greedy 484.71; 10000: ff 585.99, greedy 627.05). Chọn greedy là sai, chênh lệch trên seed tinh chỉnh nằm trong nhiễu. v9b (cùng `a059d2a`, `--prior-rule ff`, cùng ba run) chạy từ 21:22. Điểm khởi đầu của policy học được chọn trên 50000+; tham số baseline vẫn không chọn trên đó.
  - Dừng cả ba run v9b (update dưới 10, chưa có điểm sau học): người dùng yêu cầu đội xe 100–200 và kịch bản khó do heuristic tạo. Kịch bản tan trường chọn theo hình học bị bỏ: oracle chia 25–75% đội xe vòng qua hẻm thua ff 0.4–2.5% ở nền 5000 (8 seed), nên hẻm đó không phải điểm tắc thật.
  - Tìm điểm nóng theo thời gian xe đứng (`scenarios.py`, seed 40000–40007, ff, app, greedy q 0.5, mô phỏng sửa): top 20 trùng ff-app 19, ff-greedy 19, app-greedy 20. Tắc rất phi tuyến: 5000 lên 8000 chuyến/giờ thì thời gian đứng tăng 9.5 lần (ff, đội xe 5%, nền đều); 10 cạnh chiếm 52%. Oracle tách cố định trên một cạnh không phải cận trên: so với phương án đơn giản tốt nhất −3.5% đến +1.8% (4 seed). Thông tin trực tiếp có giá trị thật ở điểm nóng: một điểm ở nền 8000 có app 665.2, ff 744.4.
  - Thiết kế v10 (`6bc0859`, từ 5/11 22:50, seed 42): đội xe khoảng 100–200; nền 5000–8000; một nửa số episode học có thêm 300 chuyến dồn vào một trong 6 điểm nóng; tỉ lệ làm theo 0.6–1 mỗi episode, giảm theo độ vòng, và là đầu vào của mạng; điểm báo riêng kịch bản thường và kịch bản khó. `attrib` và `selfish` từ ff 600 update; `attrib` từ app 300 update. Kịch bản khó phải báo là tập stress, chọn trên seed tinh chỉnh; baseline phải chỉnh tham số lại trên kịch bản này trước số cuối. Chưa dùng: phạt tay (SUMO đã phi tuyến).
  - v10 sau khoảng 10 giờ (6/11 09:22; argmax, 16 seed 50000+, mỗi seed 2 nền x 2 kịch bản; ff 557.69 = thường 401.20 + khó 714.19; app 561.32 = 397.81 + 724.82; greedy 572.46 = 403.67 + 741.26). `selfish` u25–u250: 558.60, 561.16, 561.98, 556.25, 552.97, 550.44, 549.79, 564.95, 544.90, 554.26; tốt nhất u225 hơn ff 2.3% (thường 388.21, khó 701.60), chưa ổn định và chọn trên chính seed này. `attrib` u25–u225: 558.95, 558.76, 562.51, 567.78, 566.18, 551.04, 549.93, 556.27, 557.76. `attrib` khởi đầu app không học gì (J giữ 561.27–561.32 tới u150): khoá prior 120 quá chặt, entropy khoảng 0.006, KL dưới 1e-4. Ở hai run khởi đầu ff, KL mỗi update chỉ khoảng 1e-4 đến 1e-3: học quá chậm. Dừng run khởi đầu app; v11 `selfish` prior 60, lr actor 4e-4, 8 worker, 300 update, cùng commit `6bc0859`.
  - 6/11 14:34: `v10_selfish` u353/600 (u250–u350: 554.26, 556.38, 554.19, 543.58, 552.94; trung bình 552.3, hơn ff khoảng 1%; tốt nhất u325 543.58 = thường 387.66 + khó 699.51). `v10_attrib` u349 (u250–u325: 546.22, 547.77, 559.26, 561.88). `v11_selfish_loose` u83/300: u25 560.60, u50 560.72, u75 548.20 (v10_selfish u75 là 561.98); entropy 0.02–0.04 so với khoảng 0.008 của v10. Khoảng 3 phút mỗi update (load khoảng 40), cả ba run xong khoảng 02–03h ngày 7/11. Bước tiếp: đo lại các checkpoint ứng viên trên seed mới không trùng 50000+ và 60000+, tune baseline trên kịch bản v10, rồi mới chạy eval_heldout 60000+.
  - **Cổng P2 v2**: trên seed test, ở mỗi mức nhu cầu, R² ô trễ theo cạnh ≥ 0.8 × trần SUMO-vs-SUMO **và** tổng trễ lệch ≤ 15%. R² thời gian chuyến và R² trễ từng chuyến vẫn báo kèm.
- [ ] Người dùng: kiểm tra trang giá + ToS Mapbox, chạy thử 1 lượt, xem tỉ lệ Mapbox thực sự đi vào hẻm (`designed_alley_share_driven_median`).
- [ ] P1.2 TomTom (kiểm định), P1.3 YOLO camera, P1.4 nhu cầu, P1.5 fusion Bayesian.
- [ ] P2 trở đi.
