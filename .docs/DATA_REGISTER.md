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
| Cấm rẽ | 55 luật gắn được vào cạnh. Mạng v5 lúc 08:00: 11 kết nối bị xóa thật (luật ràng buộc mọi xe); 18 cặp chỉ cấm ô tô và 15 chuỗi nhiều đoạn nằm ở `route_bans.json`; 9 luật ngoài giờ; 1 luật không có kết nối tương ứng | OSM, `step1/turn_bans.json`, `routing2/net_rules.py` | đo được | 76 luật chưa gắn được vào đồ thị. Bản bỏ làn trong nút của SUMO 1.28 không thực thi quyền theo loại xe trên kết nối (đã thử), nên luật chỉ cấm ô tô chưa có hiệu lực cho tới khi tuyến ô tô được sinh có áp luật. Một lần dựng mạng chỉ đúng cho một khung giờ. Luật 14117976 và 15658117 làm 2 cạnh gần Võ Văn Kiệt–Kỳ Con thành ngõ cụt, cần xem lại trên bản đồ |
| Mapbox live, độ phủ thời gian | Đủ ngày 1–6/11 (9700 dòng mỗi ngày), trong đó chỉ 5 ngày thường 2–6/11; bản ghi cuối 12h17 ngày 7/11. Camera Q4 bắt đầu tối 7/11 | `ingestion/data_raw/mapbox_probe` trên sol1 | đo được | Không có thời điểm nào vừa có tốc độ Mapbox live vừa có mật độ camera, nên L1 chưa ghép được hai nguồn |
| Chu kỳ đèn | Mạng v5 (`routing2/net_rules.py`) đã dùng số đo cho 9/27 cụm đèn; 18 cụm còn lại rút ngẫu nhiên theo seed từ các chu kỳ đo được; `sumo_net.py` cũ vẫn 60 s. 4 camera đo được nhưng cách nút đèn gần nhất trên 180 m nên chưa gán (Pasteur–Hàm Nghi, Nguyễn Tất Thành–Cảng SG, Nguyễn Tất Thành–Cầu Khánh Hội, Khánh Hội–Cầu Kênh Tẻ). Đo 9/11, luật chặt (p<0.01, hai nửa lệch ≤ 5% so với đỉnh), dò 45–300 s. Đạt cả sáng và chiều: Hoàng Diệu–Đoàn Văn Bơ 83 s (2 camera; xem ảnh thấy khoảng 80 s, không phải nửa chu kỳ), Pasteur–Hàm Nghi 84 s, Võ Văn Kiệt–Kỳ Con 125 s, Nguyễn Tất Thành–Cảng SG (Q7→Q4) 182–185 s. Chỉ đạt một khung: Võ Văn Kiệt–Nguyễn Văn Cừ 129 s, Võ Văn Kiệt–Cầu Ông Lãnh 144 s (2 camera), Võ Văn Kiệt–Trần Đình Xu 139 s, Nguyễn Tất Thành–Cầu Khánh Hội 187 s, Khánh Hội–Đường số 41 75 s, Khánh Hội–Cầu Kênh Tẻ 175 s, Khánh Hội–Hoàng Diệu 82 s | chuỗi ảnh 20 s, `cv/cycle2.py`, `cv/cycle2_2026-11-09.txt` trên sol1 | lấy mẫu (một ngày) | 9/22 camera chưa đọc được. Nguyễn Tất Thành–Lê Văn Linh nhìn đèn trong ảnh thấy đỏ lặp khoảng 200–220 s lúc 17h15–17h25; đọc màu đèn tự động còn nhiễu. Chu kỳ có thể đổi theo giờ. Cần thêm các ngày 10–13/11 |
| Số nút có đèn | 82 nút OSM, gộp thành 27 cụm đèn (nút cách nhau ≤ 40 m dùng chung một bộ đèn) | OSM, `routing2/net_rules.py` | đo được, gộp là giả định | Chưa kiểm đủ/thiếu. Bộ đèn tự sinh của netconvert gần như không có đỏ (76/80 nút đỏ ≤ 15% chu kỳ) vì OSM tách ngã tư thành nhiều nút; v5 thay bằng 2 pha theo trục đường, xanh chia đều (giả định). 5 cụm chỉ có một trục: pha 2 đỏ, có thể không đúng |
| Tỷ lệ xanh | Đang giả định chia đều hai trục. Một mẫu: Khánh Hội – Hoàng Diệu sáng 9/11, đỏ ước 52–66 s trên chu kỳ 82 s ở hướng camera thấy; trưa và chiều chưa đo được; đo tự động trên nhiều camera thất bại | Chuỗi ảnh 20 s, so cặp ảnh ở vùng hàng chờ (`VALIDATE_L3.md`) | giả định; mẫu đo một camera | Cần đo nhiều camera, nhiều khung giờ |
| Tốc độ theo giờ | Mapbox, ngày thường, 5–21h: phủ primary 65%, secondary 95%, tertiary 95%, residential 26%, hẻm 34%, service 4% theo chiều dài | `probe_full2`, `typ_major_m` | đo được | Tốc độ ô tô; typical ≈ live (ρ 0.99); theo đoạn 40 m rất nhiễu, dùng khúc 300 m |
| Mật độ ô tô tại camera | 22 camera từ 7/11, mỗi 5 phút, trong vùng mặt đường | `cv/roi_counts.csv` | đo được | Cao hơn đếm tay 25–40% (4 ảnh); cần đếm tay thêm |
| Mật độ xe máy tại camera | Model YOLO11m train trên UVH-26 (50 epoch), ngưỡng 0,25 chốt trên 12 ảnh cũ. Chấm 10/11 trên 50 ảnh mới, 22 camera, 7–17h và 18–19h, ngày 8, 9, 10/11: sai số trung vị 22% (49 ảnh có xe), 18% trên 41 ảnh đếm được; ban ngày 18%, chạng vạng 17%; Spearman 0,87. COCO YOLO11x cùng cách chấm: 50% | `cv/runs/uvh512_y11m_g`; số đếm và kết quả ở `D:\sol1_backup\g0` | đo được, chưa chốt | Số đếm do Claude đếm bằng mắt trước khi chạy model, chưa phải nhãn của người. 8 ảnh dày hoặc khuất: model chỉ đếm được 58% tổng số, sai số trung vị 34%, nên chỗ kẹt xe bị đếm thiếu. Ảnh lệch lớn nhất (số 4: đếm 7, model 17) chưa mở xem. Chưa có ảnh ban đêm. Chưa đủ 2 tuần camera của G0 |
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
| Mật độ xe máy tại camera | C, G0 sơ bộ | Sai số trung vị 18–22%; chỗ dày có thể thiếu 40% | Người đếm lại một phần ảnh; bổ sung ảnh dày; đủ 2 tuần camera |
| Mật độ đường chính ngoài vùng camera | D | Suy từ camera và phân bố nhu cầu | Hiệu chỉnh L4 |
| Bề rộng và mật độ hẻm | D | 1–2.5 m mỗi chiều; mật độ chưa có khoảng | Tìm tài liệu |
