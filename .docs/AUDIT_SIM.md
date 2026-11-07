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

## Thứ tự sửa
1. N2, N3, S1: dựng lại mạng; kiểm lại N1, N4.
2. D1, D3, V1, B1: viết lại phần sinh nhu cầu và xe nền.
3. C1: hiệu chỉnh mức nhu cầu (nội quận, theo từng nhóm cổng, tỉ lệ ô tô) theo TTI Mapbox 17–18h. Chia cạnh có số đo thành phần hiệu chỉnh và phần kiểm tra.
4. Chỉ khi C1 đạt: chạy lại cổng "còn đất" và tìm điểm yếu của greedy.

Mọi kết quả trước khi C1 đạt chỉ là chỉ báo, gồm: thông tin hơn ff 4–7%, UE–SO 8.9%, và oracle ở 8 điểm nóng.

## Nhật ký hiệu chỉnh C1
- Lần chạy thử (`diag_v6/cal_smoke`): nội quận 8000, mỗi phía 2000 chuyến/giờ, đi xuyên 0.5, ô tô 0.15, giờ ổn định 2700 s (đo 900–2700 s). Mỗi episode 561 s. TTI trung vị theo lớp, mô phỏng so với Mapbox: primary 1.45 / 1.85, secondary 1.06 / 1.43, tertiary 1.13 / 1.19, residential 1.07 / 1.19. Spearman theo cạnh khoảng 0. Tới đích 0.72, teleport 138: kẹt cứng. **Chưa đạt.**
- Dò ngẫu nhiên lần 1 (`diag_v6/cal_r1`): 32 bộ tham số × 2 seed, đang chạy.
