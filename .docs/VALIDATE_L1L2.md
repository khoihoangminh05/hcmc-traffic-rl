# Kiểm mô phỏng một đoạn đường và một nút (L1, L2), 2026-11-09

Công cụ thử: SUMO 1.28 micro, sublane. Code: `ml-core/routing2/validate/`. Kết quả thô trên sol1: `hcmc-traffic-rl/val/out_l1*`, `out_l2*`. Mọi chạy, kể cả thất bại, đều giữ lại.

## Mốc so sánh

Chỉ có mốc từ tài liệu, chưa có số đo TP.HCM.

| Mốc | Giá trị | Nguồn, giới hạn |
|---|---|---|
| Sơ đồ cơ bản đoạn đường, 2 làn mỗi chiều | S = 98.34 − 12.3 ln(D) km/h, D xe máy/km; năng lực 13.358 MCU/h; mật độ tới hạn 1.085/km; tốc độ tới hạn 12,3 km/h | Nguyen Cao Y và cộng sự, 12 đoạn đường ở Hà Nội, giờ cao điểm. Bài không ghi bề rộng mặt đường; mình giả định 7 m, tức khoảng 1.908 xe/h/m |
| Quy đổi | Ô tô 3,4–3,6 MCU; buýt 11–11,8 | Cùng bài |
| Năng lực xe máy thuần theo làn | 5.600 xe/h (2,5 m), 8.300 xe/h (3,75 m) | Lan và cộng sự 2003, được bài trên trích dẫn; không phải đo ở Việt Nam |
| Xe máy ở nút TP.HCM | 4.500–6.000 xe/làn/h (đếm thô), 11.300 xe/làn/h | Blog Altago, nguồn thứ cấp, không rõ bề rộng; chỉ để tham khảo |

## L1: một đoạn đường

Đường vòng kín 800 m, giữ mật độ cố định, chỉ xe máy.

- Cấu hình cũ (`maxSpeed` 15 m/s, `tau` 1): năng lực 2.200–2.700 xe/h/m, cao hơn mốc 15–40%. Tốc độ lúc thưa quá cao.
- Tốt nhất sau khi dò 12 bộ tham số: `maxSpeed` 11–12,5, `tau` 1,4, `minGap` 0,5, một làn 7 m. Năng lực 1.759 xe/h/m, lệch 8%. Tốc độ lệch trung bình 18% (4 điểm).
- Không đạt ngưỡng 15%. Chỉ kiểm được tới mật độ khoảng 0,13–0,25 xe/m² vì SUMO không xếp đủ xe vào đường; nhánh gần kẹt cứng chưa kiểm.

## L2: một nút

Chu kỳ 83 s, xanh 40/37, vàng 3. Đường 7 m.

- **Xả hàng chờ:** xe máy thuần 2.350–2.870 xe/h/m; có 15% ô tô 1.790–2.030 xe/h/m; thời gian mất lúc khởi động 3–4,4 s. Chưa có số TP.HCM đáng tin để chấm.
- **Trễ khi chưa bão hòa:** SUMO 15–23 s so với Webster 11–15 s ở độ bão hòa dưới 0,7. Có trễ thật, không còn lỗi trễ gần 0 của meso.
- **Nút 4 nhánh đủ hướng rẽ:** ổn ở 1.000 xe/h mỗi nhánh. Ở 2.000 xe/h trễ đã tăng mạnh. Ở 3.000 xe/h mỗi nhánh, mức chỉ bằng khoảng 40% năng lực đo ở phép xả hàng, 900–1.500 trong 4.000 xe không tới đích kể cả sau 300 s xả, với mọi kiểu lái. Đã sửa rẽ trái phải nhường (`g`) và chạy lại, kết quả không đổi; xem phần thử cứu bên dưới.
- **Hẻm ra đường chính:** kiểu lái lịch sự chờ 150–460 s khi đường chính 4.000 xe/h. Kiểu chen ngang (`jmIgnoreFoeProb` 0,3, `impatience` 1) chỉ chờ 17–115 s, nhưng đường chính 7.000 xe/h vẫn 217–449 s. Không có số đo thực tế về thời gian chờ ở miệng hẻm.

## Thử cứu SUMO (cùng ngày)

Kết luận ban đầu "SUMO không qua, phải tự viết" đưa ra quá sớm và đã được rút lại.

Nút 4 nhánh, 15% ô tô, tham số L1 tốt nhất cộng kiểu lái chen ngang, chạy 1.200 s, xả thêm 300 s:

| Cấu hình | 3.000 xe/h mỗi nhánh | 5.000 xe/h mỗi nhánh |
|---|---|---|
| Có làn trong nút, đủ hướng rẽ, 1 làn 7 m | 41% xe không tới đích | 40% |
| Chỉ đi thẳng | 0% | 0% |
| **Bỏ làn trong nút (`--no-internal-links`), đủ hướng rẽ, 1 làn 7 m** | **0,3%**, teleport 9, trễ 119 s | 25% |
| **Bỏ làn trong nút, đủ hướng rẽ, 2 làn 3,5 m** | **0%**, teleport 25, trễ 45 s | 21% |

Nguyên nhân kẹt là xung đột của xe rẽ trong nút, không phải dòng xe máy nói chung. 5.000 xe/h mỗi nhánh đã sát năng lực (khoảng 77%), nên chưa biết phần không tới đích ở mức đó là kẹt do mô hình hay do quá tải thật. Teleport vẫn cao hơn ngưỡng 1/1000 của G2.

## Tốc độ trên mạng Q4 thật

Mạng `quan4_v4`, 15 phút mô phỏng, bước 0,5 s, lateral 0,4, OD ngẫu nhiên chưa hiệu chỉnh (chỉ để đo tốc độ tính, không phản ánh giao thông thật), 6 lượt chạy song song.

| Xe đồng thời trung bình | Có làn trong nút | Bỏ làn trong nút |
|---|---|---|
| khoảng 4.000–4.500 | 189 s | 126 s |
| khoảng 9.000–10.500 | 499 s | 396 s |
| khoảng 20.000–22.500 | 1.104 s | 958 s |

Số xe đồng thời thật ở Q4 chưa biết. Với 4.000–10.000 xe, episode 15 phút tốn khoảng 2–7 phút máy, chưa tính thời gian ra quyết định của chính sách.

## Kết luận

| Tiêu chí | Kết quả |
|---|---|
| Sơ đồ cơ bản lệch ≤ 15% | Chưa đạt: năng lực 8%, tốc độ 18%; mốc còn là số Hà Nội |
| Không kẹt chết do mô hình ở nút | Đạt ở tải vừa khi bỏ làn trong nút; chưa rõ ở sát năng lực |
| Episode ≤ 5 phút | Đạt nếu episode 15 phút và khoảng 7.000 xe trở xuống |

G1 chưa qua, nhưng SUMO chưa bị loại. Hướng chính: SUMO micro bỏ làn trong nút, tham số VN. Mô phỏng tự viết chỉ làm nếu cách này không qua G1.
