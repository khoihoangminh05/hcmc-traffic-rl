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
  - **Tiếp tục sửa (theo yêu cầu, 2026-11-07 tối):**
    - **SUMO meso** (`cal_meso`, lưới c20/c4/d14/d3). m3 = meso, không kiểm soát nút, tls penalty 1, tau giảm một nửa cho xe máy. Spearman test 0.31–0.36, so với ≤ 0.11 khi chạy micro. Cạnh kẹt chết còn 0.5–4.6%, 0 teleport, nhanh gấp khoảng 1.5 lần. Nhưng đường lớn vẫn có TTI 1.00. m1 (có kiểm soát nút) và m2 kém hơn.
    - **Lớp tốc độ theo mật độ** (`SumoEnvConfig.sd_*`, mặc định tắt; `cal_sd`, 31 bộ). Mức chậm theo lớp đã khớp được: s15 cho primary 1.55 / 1.75, secondary 1.53 / 1.47, tertiary 1.45 / 1.33. Nhưng tới đích giảm còn 0.32 và Spearman chỉ 0.10. **Mức tắc chỉnh được, còn vị trí tắc sai.**
    - **Hiệu chỉnh theo hành lang** (`ipf.py`, `cal_ipf`): luồng riêng cho từng cổng vào (24), trọng số cho từng cổng ra (23) và mức nội quận. Mỗi vòng cập nhật theo phần dư log-TTI trên các cạnh của hành lang, thử 8 bước nhảy × 2 seed. Nền là meso m3 cộng lớp tốc độ ở mức vừa (a 1.55, b 1.88, k0 0.125). `demand.make_demand_v2` có thêm `gate_in_w` và `exit_w`; mặc định vẫn chia đều. Đang chạy.
    - **Kết quả hiệu chỉnh theo hành lang:** sau 6 vòng, Spearman cal 0.20–0.22, đường lớn 1.11–1.14 / 1.67, tới đích 0.62. Cải thiện ít.
    - **Kiểm tra lại chính mục tiêu Mapbox:**
      - Mỗi đoạn có trung vị 40 m, và 40% ngắn hơn 30 m. Đoạn của Mapbox không trùng đoạn của mình.
      - TTI hai đoạn liền nhau trên cùng đường: primary tương quan 0.66, residential 0.67, nhưng secondary chỉ 0.37 và tertiary 0.39. Số theo từng đoạn rất nhiễu, nên cổng "Spearman theo cạnh ≥ 0.6" cao hơn mức chính dữ liệu đạt được.
      - Không đặc trưng cục bộ nào giải thích được TTI trong cùng lớp: đèn, độ dài, số làn, betweenness, khoảng cách tới cổng đều cho |ρ| ≤ 0.33.
    - **Mục tiêu sửa lại: khúc đường khoảng 300 m** (cùng tên đường, ô lưới 300 m, ≥ 3 đoạn): 131 khúc, Spearman giữa hai nửa đoạn (trần dữ liệu) 0.74. Ở mức này, mô phỏng meso m3 có Spearman 0.31–0.39 (cal) và 0.56–0.70 (test, chỉ 65 khúc nên nhiễu). Nhưng **trong cùng lớp gần 0** (primary 0.24, secondary −0.11, tertiary 0.1), và mọi khúc đều có TTI khoảng 1.0. Mô phỏng chỉ đúng chỗ "đường lớn chậm hơn đường nhỏ".
    - **Chẩn đoán:** thứ còn thiếu là **lưu lượng và phân bố không gian của nhu cầu**. Chỉ có tốc độ thì không suy ra được: nhiều phân bố OD cho cùng một bức tranh tốc độ. Camera đang thu là 8 camera ở quận khác (Thủ Đức, Tân Bình), Q4 không có camera nào.
    - **Lớp tốc độ tuyến tính** (`cal_sdlin`, b = 1, a ∈ {0.3, 0.6, 1}, k0 ∈ {0.05, 0.1}, mức c20/c4), chấm theo khúc 300 m:
      - Tốt nhất về mức tắc: c4, a = 1, k0 = 0.05, đường lớn 1.33 / 1.29 / 1.23 (Mapbox 1.67 / 1.47 / 1.33), nhưng tới đích chỉ 0.51.
      - Các bộ yếu hơn tới đích 0.78–0.83 nhưng TTI chỉ 1.02–1.09.
      - Spearman trong tertiary là −0.34 đến −0.51 ở **mọi** bộ: mô phỏng làm chậm các tertiary gom xe từ hẻm (Đoàn Văn Bơ, Tôn Đản), còn Mapbox cho thấy tertiary chậm ở chỗ khác.
      - Kết luận: lớp tốc độ làm đúng việc của nó; **vị trí của xe trong mô phỏng sai**. Điểm xuất phát theo chiều dài hẻm dồn quá nhiều xe vào khu dày hẻm, trục xuyên quận thì thiếu xe. Cần số đếm lưu lượng để sửa.
  - **Kế hoạch sửa (thay luật dừng cũ):**
    1. Mục tiêu theo khúc đường 300 m. Cổng: Spearman toàn bộ ≥ 0.5 và trong đường lớn ≥ 0.4; TTI trung vị mỗi lớp lệch ≤ 15%; tới đích ≥ 0.8 (tham chiếu lúc vắng là 0.87).
    2. Dữ liệu lưu lượng: thêm camera của cổng giaothong.hochiminhcity.gov.vn ở các cầu và đường lớn của Q4, đếm xe trên ảnh chụp mỗi 5 phút bằng pipeline CV có sẵn, ra luồng theo từng cổng.
    3. Mô hình: nền meso m3 (vị trí tắc tốt nhất, không kẹt chết). Lớp tốc độ theo mật độ phải ổn định (b ≈ 1, có giới hạn), để làm chậm mà không làm sập năng lực thông qua. OD theo cổng lấy từ số đếm, rồi chạy vòng hành lang (`ipf.py`) cho phần còn lại.
  - **Dữ liệu lưu lượng: camera Q4 (2026-11-07 19:40)**
    - Danh sách camera công khai lấy đúng như trang Map.aspx tải: phiên ẩn danh của trang, `FolderAjax.SearchQuery` với `Publish:true`, một request. Có 796 camera toàn thành phố, 71 camera trong và quanh Q4.
    - Gắn vào mạng v2 (≤ 40 m): 29 camera, trong đó 22 đang hoạt động. Phủ cầu Tân Thuận 1 và 2, Kênh Tẻ, Khánh Hội, Ông Lãnh, Nguyễn Văn Cừ; 8 camera trên Nguyễn Tất Thành; Khánh Hội ×4, Hoàng Diệu ×2, Võ Văn Kiệt ×6.
    - Danh mục: `ingestion-worker/config/cameras.quan4_real.json` (8 camera cũ + 22 camera Q4). Script: `routing2/calib/parse_cams.py`, `snapcam.py`.
    - Crawler trên sol1 chạy từ 19:40 ngày 7/11, chụp mỗi 5 phút.
    - Đếm xe: `cv_tracker/count_snapshots.py` (YOLO11, COCO, env riêng `/mnt/data8tb/minhkhoi/cv-env`). Một ảnh chụp cho **mật độ** (số xe trong khung hình), không phải lưu lượng; lưu lượng = mật độ × tốc độ Mapbox.
    - **Độ chính xác chưa đạt.** Kiểm tra bằng mắt ảnh đêm 19:40: cầu Khánh Hội đếm 0 xe máy, trong khi thấy được khoảng 4–5 chiếc. Đổi model hoặc ngưỡng làm số đếm lệch nhiều (Ông Lãnh: ô tô 4–22, xe máy 6–14). Phải kiểm tra trên ảnh ban ngày và lúc chạng vạng (17–18h) bằng đếm tay khoảng 20 ảnh, rồi mới dùng. So cùng một camera theo giờ đáng tin hơn so giữa các camera.
    - Kế hoạch: thu ít nhất 3 ngày thường (9–11/11). Đếm tay để chọn cấu hình detector. Dùng tỉ lệ mật độ cao điểm/vắng theo từng camera và thứ hạng mật độ giữa các cổng để ràng buộc luồng theo từng cổng trong `ipf.py`.
  - **Luật dừng cũ của vòng này:** nếu bộ tốt nhất chưa đạt Spearman đường lớn ≥ 0.4 trên nửa test và TTI trung vị mỗi lớp lệch ≤ 25%, thì không hiệu chỉnh tiếp bằng tham số chung. Khi đó phải chọn giữa hai hướng: (a) ước lượng OD theo từng cổng (SPSA, nhiều ngày máy, không chắc thành công), hoặc (b) chấp nhận hướng Q2/Q3 theo `RESEARCH_V4` §14.

## Thiết kế cặp điểm v3 (2026-11-07 tối, theo yêu cầu)

Tiêu chí của người dùng:
1. Có nhiều lựa chọn đường đi.
2. Các lựa chọn tương đương nhau.
3. Có lựa chọn qua hẻm và có lựa chọn không qua hẻm.
4. Hẻm dùng làm đường thay thế phải thông ra đường chính.
5. Xe buộc vào hẻm cụt thì các xe khác phải ước tính trước được.

Script: `routing2/calib/od3.py`, `od3b.py`; kết quả ở sol1 `diag_v6/od_v3.json`.

- **Hẻm cụt:** "túi" là phần mạng chỉ nối với đường chính qua cầu nối (bridge) của đồ thị vô hướng. Túi chiếm 592 nút (32%) và 52.8 / 112.6 km hẻm (47%). Có 990 cạnh hẻm thông.
- **Lựa chọn tương đương:** tối đa 6 đường, sinh bằng phạt các cạnh đã dùng (×1.6 mỗi lần). Mỗi đường chậm hơn đường nhanh nhất ≤ 1.2 lần, trùng nhau ≤ 50% theo chiều dài; đoạn chung bắt buộc ở hai đầu (ví dụ đầu cầu) không tính là trùng. Chuyến ≥ 120 s.
- **Đường qua hẻm:** ≥ 20% chiều dài là hẻm. **Đường không qua hẻm:** ≤ 5%.
- **Tỉ lệ thỏa trên cặp ngẫu nhiên:** ≥ 3 đường là 15%; đủ cả bốn tiêu chí là 6%. Vì vậy phải chọn từng cặp, không chọn theo vùng.
- **Kết quả từ 21620 cặp mẫu:**
  - C: 857 cặp đạt, giữ 240. Mỗi cặp có 4–6 đường; thời gian tự do trung vị 299 s; đường chậm nhất / nhanh nhất có trung vị 1.17.
  - X (qua cổng hoặc cầu): 169 cặp đạt, giữ 80, mỗi cặp 3–6 đường, trung vị 405 s.
  - F (điểm đi hoặc đến trong túi hẻm cụt, buộc vào): 160 cặp.
  - Giới hạn số cặp mỗi nút: 3, riêng nút cổng 8.
- **Còn phải làm:**
  1. Đưa bộ cặp vào phần sinh nhu cầu: xe đội chạy theo các cặp C và X; xe nền vẫn theo nhu cầu đã hiệu chỉnh.
  2. Đặc trưng **"tải bắt buộc"**: mỗi xe có điểm đến trong túi buộc phải đi qua chuỗi cạnh nối vào túi. Hệ thống tính trước số xe sẽ vào mỗi cạnh trong H giây tới: xe đội lấy theo điểm đến đã biết, xe nền lấy theo tốc độ vào túi điển hình đo được. Mọi bộ điều khiển (greedy, app, MARL) đều được dùng đặc trưng này, để công bằng.

## K1: so sánh baseline trên cặp v3 (2026-11-07 đêm)

Mô phỏng: meso m3, lớp tốc độ tuyến tính (a 0.6, b 1, k0 0.1), xe nền mức c4 có xe từ quận khác, thêm 600 chuyến/giờ buộc vào hẻm cụt (F). Xe đội chạy trên các cặp C/X. Script: `routing2/calib/k1.py`.

- **Lượt 1** (seed 40000–40001): ở cỡ đội 6000, ff 502, app 631, greedy 633. Nhìn thì như app/greedy sụp vì dồn đường.
- **Lượt 2** (seed 40002–40004) **không xác nhận lượt 1**:

  | Cỡ đội | ff | app | greedy |
  |---|---|---|---|
  | 4500 | 503 | 503 | 503 |
  | 6000 | 544 (503 / 510 / 620) | 535 (516 / 579 / 510) | 515 (520 / 509 / 518) |
  | 9000 | 737 | 632 | 666 (592–736) |

  Gần ngưỡng năng lực, mỗi episode có thể "sụp" hoặc không, và chuyện đó xảy ra ngẫu nhiên với **bất kỳ** chính sách nào. Kết quả lượt 1 chỉ là do sụp rơi đúng vào app/greedy. **Không có thứ hạng ổn định.** Muốn so phải đo xác suất sụp trên nhiều seed (cổng H).
- **Cơ chế:** thời gian chờ ở hẻm chỉ chiếm 1–3% tổng (15–70 nghìn s so với 1–2.3 triệu s trên đường). Xe đội gần như không đi hẻm thông. Các cạnh chờ nhiều nhất giống nhau ở mọi chính sách: **Võ Văn Kiệt, mô hình 1 làn** (616 m và 367 m), sau đó là Hoàng Diệu. Làn xe máy của Võ Văn Kiệt ngoài thực tế là đường song hành rộng, nên mô hình 1 làn **rất có thể là lỗi số làn trong OSM hoặc lúc dựng mạng**. Nút cổ chai giả này chi phối cả mạng, không chính sách nào tránh được.
- **Việc tiếp theo:** (1) kiểm tra và sửa số làn (bề rộng) của Võ Văn Kiệt và các trục 1 làn khác; (2) đo xác suất sụp theo chính sách trên khoảng 20 seed ở cỡ đội 6000–7500; (3) xem vì sao xe đội không dùng hẻm thông dù cặp C có đường qua hẻm (chi phí thời gian của hẻm trong mô phỏng có hợp lý không).

## Kiểm tra bộ đếm YOLO trên ảnh ban ngày (2026-11-08 10h, Chủ nhật)

Đếm tay 4 ảnh, so với YOLO11 m/x ở conf 0.05–0.1 và imgsz 1280:

| Camera | Xe máy đang chạy (đếm tay) | YOLO | Lỗi |
|---|---|---|---|
| Khánh Hội – Hoàng Diệu | ~22 (cụm dừng đèn) | 3–20 | đếm thiếu cụm dày |
| Nguyễn Tất Thành – Tôn Đản | ~10, cộng ~12 xe đỗ vỉa hè | 19–36 | đếm cả xe đỗ |
| Hoàng Diệu – Đoàn Văn Bơ 1 | ~12 | 15–27 | đếm cả xe đỗ |
| Võ Văn Kiệt – Ông Lãnh 1 | ~6 | 0–2 | xe ở xa quá nhỏ |

Sai số mỗi ảnh khoảng ±50%. **Chưa dùng được số tuyệt đối.**

Cách sửa:
1. Vẽ vùng mặt đường (ROI) cho từng camera để bỏ xe đỗ.
2. Chỉ dùng tín hiệu tương đối: mật độ cao điểm / giờ vắng trên cùng một camera.
3. Báo cáo sai số đếm trong bài.

Số làn Võ Văn Kiệt: OSM ghi làn xe máy riêng (`motorcar=no`, `motorcycle=designated`, `lanes=1`), nên **không phải lỗi gắn nhãn**. Mạng còn 42 đoạn primary và 183 đoạn secondary 1 làn mỗi chiều. Nút cổ chai có thể do luồng phía tây dồn vào. Sẽ kiểm tra bằng 6 camera trên Võ Văn Kiệt; trong lúc đó coi số làn của làn chỉ dành cho xe máy là tham số của tập mô phỏng E (`PREREG_SCENARIOS.md`).

## K2: dùng hẻm và xác suất sụp (2026-11-08)

**Dùng hẻm** (`k2.py`, nền c20, đội 3000 và 6000, 3 seed):
- Ở lớp tốc độ nhẹ, quãng đường xe đội đi trong hẻm: ff 6%, app và greedy 7–7.5%.
- Ở lớp tốc độ thực tế (a 1, k0 0.05): 6–10%, nhưng mô phỏng sụp (tới đích 0.50–0.63).
- Thời gian chờ trong hẻm bằng 5–8% thời gian chờ trên đường.
- **Cơ chế "dồn vào hẻm thông" yếu trong mô phỏng này.** Mức chậm thực tế trên đường chính chỉ đạt được khi mô phỏng sụp; ngoài đời đường chậm 1.3–1.7 lần mà vẫn chảy. Đây là giới hạn của động lực học mô phỏng.

**Xác suất sụp** (`k3.py`, lớp tốc độ nhẹ, đội 6000, 20 seed 40010–40029):

| Chính sách | J trung bình | trung vị | CVaR25 | sụp (tới đích < 0.75) |
|---|---|---|---|---|
| ff | 582 | 553 | 704 | 4/20 |
| app | 553 | 544 | 636 | 2/20 |
| greedy (queue_s 0.5) | 552 | 536 | 633 | 2/20 |

- So theo cặp seed: greedy − ff = −30.6 (thắng 13/20); app − ff = −29.6 (thắng 11/20); greedy − app = −1.1 (thắng 10/20).
- **Sụp phụ thuộc chính sách, không phụ thuộc seed.** Không seed nào cả ba cùng sụp, và các seed sụp của từng chính sách khác nhau. Định tuyến **có** ảnh hưởng tới việc tắc lan thành sụp.
- **Đất cho phối hợp:**
  - Lấy chính sách tốt nhất trên từng seed: J 514, CVaR25 555. So với greedy: tốt hơn 6.9% ở trung bình và **12.3% ở CVaR25**.
  - Đây là cận lạc quan, vì lấy min của 3 kết quả có nhiễu.
  - Episode không sụp có J trung vị 540; episode sụp 662. Một chính sách tránh được sụp sẽ lấy được phần lớn khoảng cách ở nhóm episode xấu.
- **Việc phải làm trước khi tin vào kết quả này:**
  1. Tinh chỉnh queue_s của greedy (0.25 / 0.5 / 1 / 2) trên seed 40000+. Nếu một greedy chỉnh tốt đã tránh được sụp thì không còn đất (luật không làm yếu heuristic).
  2. Tìm cơ chế khởi phát sụp: cạnh nào tắc trước, xe đội có góp phần không.
  3. Chạy split oracle hoặc SO trên cùng các seed.

**Tinh chỉnh greedy** (`k4.py`, cùng 20 seed):

| queue_s | J trung bình | CVaR25 | sụp |
|---|---|---|---|
| 0.25 | 566 | 659 | 4 |
| 0.5 | 552 | 633 | 2 |
| 1 | 557 | 629 | 3 |
| 2 | 671 | 838 | 10 |

- greedy tốt nhất ở queue_s 0.5–1. Không giá trị nào hết sụp.
- queue_s 2 (rải đội xe quá mạnh) làm sụp tới 10/20. Phân tán quá cũng gây sụp, nên có một điểm cân bằng không tầm thường.
- **Ước lượng đất trung thực hơn:**
  - Nếu greedy (0.5) tránh được 2 lần sụp của chính nó (thay bằng trung vị các episode không sụp, 516), thì J trung bình 539 và CVaR25 612. Chỉ tốt hơn **2.3% / 3.4%**.
  - Con số "best-of-3 hơn 12%" chủ yếu do lấy min trên nhiễu.
- **Kết luận tạm:** đất từ việc tránh sụp ở cỡ đội 6000 nhỏ hơn cổng 5% ở CVaR25. Cần cận đúng nghĩa (SO hoặc oracle chia luồng) mới kết luận được K2.
