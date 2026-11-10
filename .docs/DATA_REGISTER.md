# Sổ dữ liệu (giai đoạn 1, `PLAN_FINAL.md`)

Mỗi thông số một dòng. Nhãn: **đo được / lấy mẫu / từ tài liệu / giả định**. Mục chưa có giá trị ghi rõ. Cập nhật mỗi khi có số mới.

| Thông số | Giá trị hiện tại | Nguồn | Nhãn | Sai số, ghi chú |
|---|---|---|---|---|
| Hình học mạng | 3888 cạnh; hẻm 80.5 km, service 32.2, primary 22.5, residential 22.8, tertiary 24.1, secondary 21.5 | OSM, `net_full2` | đo được | Đã kiểm liên thông |
| Số làn | Thẻ OSM; thiếu thì tự gán | OSM | giả định một phần | Chưa đối chiếu ảnh camera |
| Bề rộng đường lớn | chưa có (OSM không ghi) | | | Đo trên ảnh |
| Bề rộng hẻm | 1.25 m mỗi chiều | tự đặt | giả định | Sẽ chạy dải 1–2.5 m; đang tìm tài liệu |
| Kích thước xe máy | dài 1.9, rộng 0.8 m | SUMO; tài liệu 0.65–0.8 m rộng | từ tài liệu | |
| Kích thước ô tô | dài 4.5, rộng 1.8 m | SUMO | giả định | |
| Cấm rẽ | 55 luật gắn được vào cạnh: 20 ràng buộc xe máy, 55 ràng buộc ô tô, 30 theo khung giờ | OSM, `step1/turn_bans.json`, `data_fusion/turn_restrictions.py` | đo được | 76 chưa gắn được: 56 nằm ngoài mạng, 12 có via là đoạn đường, 8 sát mạng (2 ràng buộc xe máy). 18 luật khớp nhiều hơn một cạnh, cần xem lại. Chưa đưa vào mạng |
| Mapbox live, độ phủ thời gian | Đủ ngày 1–6/11 (9700 dòng mỗi ngày), trong đó chỉ 5 ngày thường 2–6/11; bản ghi cuối 12h17 ngày 7/11. Camera Q4 bắt đầu tối 7/11 | `ingestion/data_raw/mapbox_probe` trên sol1 | đo được | Không có thời điểm nào vừa có tốc độ Mapbox live vừa có mật độ camera, nên L1 chưa ghép được hai nguồn |
| Chu kỳ đèn | Mô phỏng hiện vẫn 60 s, đỏ 30 s, offset băm (`sumo_net.py`, sai). Đo 9/11, luật chặt (p<0.01, hai nửa lệch ≤ 5% so với đỉnh), dò 45–300 s. Đạt cả sáng và chiều: Hoàng Diệu–Đoàn Văn Bơ 83 s (2 camera; xem ảnh thấy khoảng 80 s, không phải nửa chu kỳ), Pasteur–Hàm Nghi 84 s, Võ Văn Kiệt–Kỳ Con 125 s, Nguyễn Tất Thành–Cảng SG (Q7→Q4) 182–185 s. Chỉ đạt một khung: Võ Văn Kiệt–Nguyễn Văn Cừ 129 s, Võ Văn Kiệt–Cầu Ông Lãnh 144 s (2 camera), Võ Văn Kiệt–Trần Đình Xu 139 s, Nguyễn Tất Thành–Cầu Khánh Hội 187 s, Khánh Hội–Đường số 41 75 s, Khánh Hội–Cầu Kênh Tẻ 175 s, Khánh Hội–Hoàng Diệu 82 s | chuỗi ảnh 20 s, `cv/cycle2.py`, `cv/cycle2_2026-11-09.txt` trên sol1 | lấy mẫu (một ngày) | 9/22 camera chưa đọc được. Nguyễn Tất Thành–Lê Văn Linh nhìn đèn trong ảnh thấy đỏ lặp khoảng 200–220 s lúc 17h15–17h25; đọc màu đèn tự động còn nhiễu. Chu kỳ có thể đổi theo giờ. Cần thêm các ngày 10–13/11 |
| Số nút có đèn | 82 | OSM | đo được | Chưa kiểm đủ/thiếu |
| Tốc độ theo giờ | Mapbox, ngày thường, 5–21h: phủ primary 65%, secondary 95%, tertiary 95%, residential 26%, hẻm 34%, service 4% theo chiều dài | `probe_full2`, `typ_major_m` | đo được | Tốc độ ô tô; typical ≈ live (ρ 0.99); theo đoạn 40 m rất nhiễu, dùng khúc 300 m |
| Mật độ ô tô tại camera | 22 camera từ 7/11, mỗi 5 phút, trong vùng mặt đường | `cv/roi_counts.csv` | đo được | Cao hơn đếm tay 25–40% (4 ảnh); cần đếm tay thêm |
| Mật độ xe máy tại camera | chưa có | Đang huấn luyện YOLO11m trên UVH-26 (camera cố định Bengaluru, CC-BY-4.0, 100633 khung xe hai bánh), ảnh thu về 512×288 cho giống camera Q4; dự phòng BMD-45; bộ Đà Nẵng không có phản hồi, đã bỏ | đo được nếu đạt | Ảnh huấn luyện chỉ 6–18h. Phải qua G0: sai số trung vị ≤ 30% trên ít nhất 50 ảnh Q4 đếm tay. Kiểm sơ bộ 9/11 trên 12 ảnh Q4 đếm tay, trước khi xem kết quả model: COCO sai trung vị khoảng 50% trên 9 ảnh đếm được; YOLO11s (7 epoch, CPU) khoảng 15% ở ngưỡng 0,25–0,35; YOLO11m (1 epoch) 15% ở ngưỡng 0,35. Ngưỡng chưa chọn độc lập. 3 ảnh kẹt dày không đếm chính xác được và model thiếu 30–65% so với ước lượng tay. Chưa phải chấm G0. |
| Mật độ trong hẻm theo loại xe | chưa có | chưa tìm thấy dataset, bài báo | giả định | Không đo thực địa (người dùng chốt) |
| Năng lực xe máy | Đoạn đường Hà Nội, 2 làn mỗi chiều: 13.358 MCU/h, tới hạn 1.085 xe/km ở 12,3 km/h; ô tô 3,4–3,6 MCU, buýt 11–11,8. Ở nút: chưa có số TP.HCM đáng tin | Nguyen Cao Y và cộng sự; Nakatsuji và cộng sự 2001 (xe máy làm giảm bão hòa của ô tô tới 40%, Hà Nội, Bangkok); xem `VALIDATE_L1L2.md` | từ tài liệu | Bài Hà Nội không ghi bề rộng mặt đường, giả định 7 m. Bài TP.HCM về bão hòa chưa đọc được toàn văn |
| Tỉ lệ vượt đèn | chưa có | | | Đo từ chuỗi ảnh nếu nhìn được |
| Tai nạn, sự cố | 2/giờ, tan trường 1/giờ | tự đặt | giả định | Tìm số liệu công bố |
| Tỉ lệ ô tô trên trục chính | 24–38% (đếm tay 2 nút, Chủ nhật) | ảnh camera | lấy mẫu | Quá ít mẫu; chờ camera ngày thường |

## Mức tin cậy hiện tại (lớp độ tin cậy, `PLAN_FINAL.md`)

A: đo nhiều ngày, qua kiểm tra chéo. B: đo một ngày hoặc một khung giờ. C: suy rộng hoặc từ tài liệu. D: giả định.

| Thông số | Mức | Khoảng dùng khi lấy mẫu | Nâng mức bằng cách nào |
|---|---|---|---|
| Đèn, 4 nút đạt cả sáng và chiều | B | ±5% quanh giá trị đo | Thêm ảnh 10–13/11 |
| Đèn, 7 nút đạt một khung giờ | B- | ±15% | Thêm ảnh 10–13/11; đối chiếu bằng mắt |
| Đèn, các nút còn lại trong 82 nút của mạng (chưa đọc được hoặc không có camera; một số camera đã đọc nằm ngoài Q4, chưa gắn camera với nút) | D | Phân bố đo được, hiện 75–187 s | Đọc thêm ảnh; đoàn xe mô phỏng để kiểm cách ước lượng |
| Pha xanh/đỏ và offset, mọi nút | D | Chưa có số đo | Đọc từ chuỗi ảnh ở nút thấy rõ |
| Tốc độ đường chính theo giờ (ô tô) | B | Theo sai số khúc 300 m | Bật lại Mapbox live nếu còn hạn mức |
| Mật độ ô tô tại camera | C | Cao hơn đếm tay 25–40% | Đếm tay thêm, model mới |
| Mật độ xe máy tại camera | D, chờ G0 | Chưa dùng | Chấm G0 |
| Mật độ đường chính ngoài vùng camera | D | Suy từ camera và phân bố nhu cầu | Hiệu chỉnh L4 |
| Bề rộng và mật độ hẻm | D | 1–2.5 m mỗi chiều; mật độ chưa có khoảng | Tìm tài liệu |
