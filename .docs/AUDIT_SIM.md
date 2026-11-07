# Rà soát mô phỏng trước mọi cổng (bắt đầu 2026-11-07)

Mục đích: không chạy cổng, không train, không báo kết luận nào cho đến khi mọi mục dưới đây **đạt**. Mỗi mục ghi số đo, nguồn và trạng thái. Mạng đang rà: `data_fusion.build_quan4_full` (sol1 `diag_v6/net_full`). Thiết lập kịch bản: v10. Mapbox: `diag_v6/probe_full`, 63515 mẫu `driving-traffic`, 30/10–07/11, 5–21h giờ VN.

Ký hiệu: ✗ sai, phải sửa; ~ là giả định, phải quét độ nhạy; ✓ đạt.

| # | Mục | Đo được | Trạng thái | Sửa |
|---|---|---|---|---|
| N1 | Có lựa chọn đường | 60.5% chuyến có đường thứ hai ≤1.3× và trùng ≤50% (mạng SUMO); mạng cũ 28% | ✓ | |
| N2 | Đường cấm xe máy | Giữ nhầm 224 cạnh OSM `motorcycle=no`: Võ Văn Kiệt làn chính 152, Hầm Sông Sài Gòn 22, Hàm Nghi 9, Trương Đình Hợi 11, … | ✓ đã sửa (mạng v2, `diag_v6/net_full2`) | Bỏ. Tỉ lệ chuyến có lựa chọn còn 0.498, vì Võ Văn Kiệt làn chính từng là đường vòng giả |
| N3 | Lối vào và lối ra ở biên | Chỉ giữ SCC nên mất 10.0 km primary và 10.9 km secondary: các nhánh một chiều vào và ra của đường lớn, đầu cầu | ✓ đã sửa: lõi 1697 nút + nhánh vào và ra = 1842 nút, 3888 cạnh; 24 cổng vào, 23 cổng ra (cầu Kênh Tẻ, Tân Thuận 1 và 2, Ông Lãnh, Calmette, Nguyễn Văn Cừ, Võ Văn Kiệt phía tây, phố Q1 ở mép vùng đệm) | Giữ nhánh vào (đi tới SCC) và nhánh ra (đi từ SCC) làm cổng |
| N4 | Cầu | Có Nguyễn Văn Cừ, Kênh Tẻ, Tân Thuận 1 và 2, Ông Lãnh, Calmette, Rạch Ông, Khánh Hội, Nguyễn Kiệu, Dừa | phải kiểm lại sau N2–N3 | |
| N5 | Một chiều, số làn | Theo OSM; số làn mỗi chiều = `lanes`, chia đôi nếu hai chiều; thiếu tag thì primary/secondary 2, còn lại 1 | ~ | |
| N6 | Đèn | 84 nút có đèn trong OSM; chu kỳ 60 s, 30/30 và offset băm là **tự đặt**. Đèn thật ở TP.HCM thường 90–150 s | ~ | Quét chu kỳ |
| S1 | Tốc độ tự do theo lớp (m/s) | Đặt: primary 10, secondary 9, tertiary 8, residential 6, service 5, hẻm 4.5. Mapbox 5h: 8.86 / 7.17 / 5.54 / 5.27 / 3.25 / 3.05 (ô tô) | ✓ đã sửa cho bốn lớp đường; hẻm và service vẫn là giả định ~ | Lấy từ Mapbox 5h cho lớp đường. Hẻm: ô tô chậm hơn xe máy, nên giữ 4.5 làm giả định ~ |
| D1 | Xe từ quận khác | Không có. 98.9% điểm xuất phát nằm ở nút có hẻm; cầu chỉ là điểm đến | đang sửa: `demand.make_demand_v2` có luồng nội quận, luồng vào, luồng ra, luồng đi xuyên theo 4 phía (E, N, W, S) | Thêm luồng đi xuyên (cổng → cổng), luồng vào (cổng → Q4), luồng ra (Q4 → cổng) |
| D2 | Mức nhu cầu | Tự đặt (5000–22000 chuyến/giờ). Chưa từng hiệu chỉnh | ✗ | Hiệu chỉnh theo Mapbox (C1) |
| D3 | Hồ sơ thời gian | Xuất phát dồn trong 600 s (đỉnh sd 0.15), không phải một giờ cao điểm | ✗ | Một giờ cao điểm ổn định: làm nóng 900 s, đo 1800 s |
| D4 | Điểm đến | 32 vùng thiết kế cho có lựa chọn, 60% chuyến dồn về 4 vùng giữa (`hot_share` 0.6, tự đặt) | ~ | Giữ vùng thiết kế; hot_share hiệu chỉnh hoặc quét |
| V1 | Loại xe | Chỉ xe máy | đang sửa: ô tô vào và ra qua cổng, SUMO định tuyến theo `passenger`. 190/552 cặp cổng không có đường cho ô tô nên bị loại (ghi `car_dropped`) | Thêm ô tô và xe buýt trên đường lớn; tỉ lệ là giả định ~, quét |
| B1 | Cách chọn đường của xe nền (đang sửa: `bg_route="informed"`) | 70% đi đường free-flow cố định, 30% có thiết bị reroute của SUMO. Người dân thật đi theo thói quen, gần cân bằng, không phải free-flow; vì vậy tắc dồn vào vài nút | ✗ | Tuyến xe nền theo thời gian đi điển hình (cân bằng hoặc trọng số TTI đo được), có nhiễu logit |
| E1 | Sự kiện | Tai nạn 2/giờ, tan trường 1/giờ: tự đặt | ~ | |
| E2 | Teleport | 2–9 trên 1000 chuyến (300 s) | ✓ tạm | |
| C1 | Trạng thái giao thông so với Mapbox | TTI 17–18h theo cạnh: Khánh Hội 1.93 thật, 1.13 mô phỏng; Nguyễn Tất Thành 1.54 / 1.05; Hoàng Diệu 1.54 / 1.15. Spearman theo cạnh: primary 0.25, secondary 0.05, tertiary 0.00 | ✗ | **Cổng hiệu chỉnh:** Spearman theo cạnh ≥ 0.6 trên đường lớn, TTI trung vị mỗi lớp lệch ≤ 15%, trên seed khác seed hiệu chỉnh |

## Rà soát chính dữ liệu Mapbox (M, 2026-11-07)

Dữ liệu: `probe_full2/edge_obs.csv`, gồm 63915 lần hỏi và 2.1 triệu quan sát theo cạnh. Mỗi tuyến hỏi khoảng 6 lần/giờ, từ 30/10 đến 07/11; 96.5% chiều dài khớp được vào mạng v2. Script: `diag_v6/mbx2.py`, `mbx3.py`, `mbx4.py`.

| # | Mục | Đo được | Trạng thái |
|---|---|---|---|
| M1 | Cuối tuần | Lúc 5h Chủ nhật 1/11, tốc độ trung vị đường lớn là 3.06 m/s; lúc 5h thứ Bảy 7/11 là 4.43 m/s. Cả hai đều **chậm hơn** giờ cao điểm chiều (4.7–5.0). Ngày thường lúc 5h là 5.76–5.81 m/s. Mục tiêu cũ trộn cả cuối tuần nên lệch: Spearman giữa hai nửa số ngày chỉ 0.66 | ✗ ở mục tiêu cũ → ✓ chỉ dùng ngày thường (6 ngày) |
| M2 | Mapbox là dữ liệu sống hay hồ sơ điển hình | Mỗi ngày thường, tốc độ trung vị đường lớn lúc 17h gần như trùng khớp (4.696 m/s ở 4 ngày); độ lệch giữa các ngày theo cạnh–giờ là 3.4%. Phần lớn là **hồ sơ điển hình theo giờ trong tuần**; chỉ ngày 6/11 lúc 17h có lệch (4.15) | ~ Dùng được để hiệu chỉnh một giờ cao điểm điển hình. **Không** dùng để đo độ biến động giữa các ngày |
| M3 | Độ lặp lại của mục tiêu | Spearman TTI theo cạnh, chỉ ngày thường, giữa ngày chẵn và ngày lẻ: đường lớn 0.90 (214 cạnh), toàn bộ 0.96 | ✓ Mục tiêu ổn định; cổng Spearman ≥ 0.6 nằm dưới trần 0.9 |
| M4 | 5h có phải tham chiếu tự do | Ngày thường, 5h là giờ nhanh nhất. Với tốc độ theo cạnh, giờ nhanh nhất / 5h có trung vị 1.04 | ✓ |
| M5 | Tốc độ tự do theo lớp | Ngày thường lúc 5h: primary 9.01, secondary 7.17, tertiary 5.80, residential 5.24. Mạng đang đặt 8.86 / 7.17 / 5.54 / 5.27, lệch tối đa 4.7% | ~ chấp nhận được, không dựng lại mạng |
| M6 | Mục tiêu TTI theo lớp (ngày thường, 5h / 17–18h) | primary 1.91, secondary 1.42, tertiary 1.24, residential 1.19, hẻm 1.13. Theo đường: Khánh Hội 1.99, Nguyễn Tất Thành 1.89–2.04, Hoàng Diệu 1.56, Tôn Thất Thuyết 1.42; các đường còn lại 1.19–1.26 | ✓ mục tiêu mới |
| M7 | Phủ không gian | 274 cạnh đường lớn có số đo, dồn ở Đoàn Văn Bơ (58), Tôn Đản (47), Nguyễn Tất Thành (29), Tôn Thất Thuyết (27), Xóm Chiếu (27). Khánh Hội chỉ có 12 cạnh, Hoàng Diệu 14 | ~ Hiệu chỉnh đúng nhất ở khu Đoàn Văn Bơ – Tôn Đản |
| M8 | Định nghĩa TTI của mô phỏng | Cũ: `v_free` theo lớp / tốc độ mô phỏng. Cách này không giống Mapbox, vì đèn và nút giao làm xe chậm cả khi vắng. Mới: tốc độ mô phỏng khi vắng (nội quận 1500, mỗi phía 150 chuyến/giờ; `diag_v6/cal_ref`) / tốc độ mô phỏng giờ cao điểm. Cách này đúng như cách tính 5h / 17–18h của Mapbox | ✓ sửa trong `cal12b.py` |
| M2b | Typical so với live | Cùng tuyến, cùng thứ Năm 5/11: tốc độ typical / live có trung vị 1.000; Spearman theo cạnh 0.997 lúc 5h, 0.988 lúc 17–18h; Spearman TTI 0.97 (đường lớn 0.90). Chi tiết: `diag_v6/typ_vs_live.py` | ✓ Hỏi typical (`depart_at`) cho kết quả như số đo live. Hỏi bù bằng typical là hợp lệ |
| M10 | Ảnh hưởng của bản đồ cũ (dạng cây) | 100 tuyến hỏi Mapbox được `design_probe_routes` thiết kế **trên bản đồ cũ**: mục tiêu là phủ hẻm, và điểm đi qua đặt trong hẻm. Trên mạng v2, tỉ lệ chiều dài có ≥ 20 số đo: primary 11%, secondary 8%, tertiary 35%. **Cổng biên: 0 trên 67 cạnh. Cầu (Nguyễn Văn Cừ, Ông Lãnh, Kênh Tẻ, Calmette, Tân Thuận 1 và 2), Võ Văn Kiệt, Bến Vân Đồn: 0%.** Vì vậy luồng xe từ quận khác không hiệu chỉnh được bằng số liệu hiện có. Bản thân số tốc độ Mapbox không phụ thuộc bản đồ của mình, và khớp lại trên v2 vẫn đạt 96.5% | ✗ → đang sửa: `design_probe_routes --focus major` dựng 40 tuyến dài 0.8–3.5 km, phủ 1070/1192 cạnh đường lớn và cổng. Ngày 7/11 đã hỏi typical cho thứ Hai 9/11 và thứ Ba 10/11, 5–22h, mỗi 30 phút: 2720 lượt, quota còn 20193. Worker sol1 dùng `config/probe_routes.quan4_major.json`; `.env` cũ lưu ở `.env.bak_20261107`; ngừng hỏi live từ 7/11 12h |
| M9 | Phương tiện | Mapbox đo tốc độ ô tô (thiết bị dùng SDK). Mô phỏng tính trung bình mọi xe trên cạnh, chủ yếu xe máy | ~ ghi là giới hạn |

## Thứ tự sửa
1. N2, N3, S1: dựng lại mạng; kiểm lại N1, N4.
2. D1, D3, V1, B1: viết lại phần sinh nhu cầu và xe nền.
3. C1: hiệu chỉnh mức nhu cầu (nội quận, theo từng nhóm cổng, tỉ lệ ô tô) theo TTI Mapbox 17–18h. Chia cạnh có số đo thành phần hiệu chỉnh và phần kiểm tra.
4. Chỉ khi C1 đạt: chạy lại cổng "còn đất" và tìm điểm yếu của greedy.

Mọi kết quả trước khi C1 đạt chỉ là chỉ báo, gồm: thông tin hơn ff 4–7%, UE–SO 8.9%, và oracle ở 8 điểm nóng.

## Nhật ký hiệu chỉnh C1
- Lần chạy thử (`diag_v6/cal_smoke`): nội quận 8000, mỗi phía 2000 chuyến/giờ, đi xuyên 0.5, ô tô 0.15, giờ ổn định 2700 s (đo 900–2700 s). Mỗi episode 561 s. TTI trung vị theo lớp, mô phỏng so với Mapbox: primary 1.45 / 1.85, secondary 1.06 / 1.43, tertiary 1.13 / 1.19, residential 1.07 / 1.19. Spearman theo cạnh khoảng 0. Tới đích 0.72, teleport 138: kẹt cứng. **Chưa đạt.**
- Dò ngẫu nhiên lần 1 (`diag_v6/cal_r1`): 32 bộ tham số × 2 seed. Chấm lại theo mục tiêu ngày thường và theo tham chiếu lúc vắng của chính mô phỏng (`cal12b.py rescore`, tham chiếu `cal_ref`: tới đích 0.87, 0 teleport). Bộ tốt nhất c20 (nội quận 3300, cổng 920–2700 mỗi phía): Spearman cal 0.05, test 0.16. Đường lớn có TTI trung vị 1.00–1.02, trong khi Mapbox là 1.4–1.9. Mọi bộ đều có 6–18% cạnh **kẹt chết** (TTI 20–200, xe gần như đứng yên) và 61–390 teleport. Mô phỏng chia hai cực: kẹt chết ở vài nút, trống ở các chỗ còn lại; thực tế thì chậm vừa phải và đều. **Chưa đạt.**
- Quét tùy chọn chống kẹt (`cal_sw`), ở mức c20 và c4 của cal_r1:
  - v1: `--ignore-junction-blocker 10`.
  - v2: v1 + `--time-to-impatience 30`.
  - v3: `--ignore-junction-blocker 5 --time-to-impatience 20`, teleport 120 s.

  Với v3, tỉ lệ cạnh kẹt chết giảm từ 11.5% xuống 5% và tới đích tăng từ 0.73 lên 0.83. Nhưng đường lớn vẫn có TTI 1.0–1.06 và Spearman vẫn khoảng 0.1. Chống kẹt là cần, nhưng chưa đủ.
- Số liệu Mapbox mới ở đường lớn và cổng (M10, 1188 cạnh có TTI): primary 1.68, secondary 1.47, tertiary 1.36. Nặng nhất: Nguyễn Tất Thành 2.39, cầu Ông Lãnh 1.96, Võ Văn Kiệt 1.67, Khánh Hội 1.51, Tôn Thất Thuyết 1.47, Bến Vân Đồn 1.47. Ở thực tế, đường lớn của cả quận đều chậm vừa phải, nên lượng xe đi xuyên qua cầu lớn hơn nhiều so với mức đã thử. Mục tiêu gộp số liệu cũ và mới: 1145 cạnh (575 cal / 570 test).
- Dò lần 2 (`cal_s60`, `cal_s90`): luồng ở cổng 1000–12000 mỗi phía, nội quận 2000–10000, chống kẹt v3. Chạy theo cặp cùng tham số với chu kỳ đèn 60 s và 90 s (`ROUTING2_TLS_CYCLE`; mạng giống nhau trừ tlLogic). Mỗi lượt có tham chiếu lúc vắng trên cùng mạng.
  - **Kết quả (2026-11-07 17:40), 15 bộ × 2 chu kỳ đèn, 1145 cạnh mục tiêu:**
    - Spearman test của mọi bộ nằm trong khoảng −0.02 đến 0.11.
    - TTI trung vị theo lớp trong mô phỏng là 1.02–1.20; Mapbox là primary 1.75, secondary 1.47, tertiary 1.33.
    - Tăng luồng ở cổng chỉ làm kẹt chết thêm: tới đích giảm từ 0.77 xuống 0.45, teleport tăng từ 340 lên 1430. Đường lớn không chậm đều lên như ngoài thực tế.
    - Đèn 90 s không khác đèn 60 s (một bộ có primary 1.53, nhưng Spearman vẫn 0.10).

    **Luật dừng bị kích hoạt. Kết luận C1: không đạt.** Mô phỏng SUMO này tạo tắc theo kiểu kẹt chết ở nút, không theo kiểu đường chậm đều. Thêm xe không đổi được kiểu tắc đó, nên ước lượng OD theo từng cổng khó sửa được, vì vấn đề nằm ở mô hình nút giao và mô hình xe máy chứ không ở mức nhu cầu.
  - **Luật dừng của vòng này:** nếu bộ tốt nhất chưa đạt Spearman đường lớn ≥ 0.4 trên nửa test và TTI trung vị mỗi lớp lệch ≤ 25%, thì không hiệu chỉnh tiếp bằng tham số chung. Khi đó phải chọn giữa hai hướng: (a) ước lượng OD theo từng cổng (SPSA, nhiều ngày máy, không chắc thành công), hoặc (b) chấp nhận hướng Q2/Q3 theo `RESEARCH_V4` §14.
