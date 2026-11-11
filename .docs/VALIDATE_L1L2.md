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

## Ứng viên cuối (chạy 9/11, chấm 10/11)

Xe máy: `base:maxSpeed=8.5;speedDev=0.2;tau=1.2;minGap=0.3;width=0.8;minGapLat=0.3;jmIgnoreFoeProb=0.3;jmIgnoreFoeSpeed=3;jmTimegapMinor=0.5;impatience=1`, sublane 0,4 m, bước 0,5 s, mạng bỏ làn trong nút. Chạy với `--collision.action warn --collision.mingap-factor 0`, vì trước đó toàn bộ teleport đều do va chạm ở khoảng cách sát của xe máy. Kết quả thô: `val/out_l1e`, `val/out_l2f` (bản sao ở `D:\sol1_backup\data8tb\val`).

**L1, đường vòng 1 làn 7 m, so với đường cong Hà Nội:**

| Mật độ thật (xe/m²) | Tốc độ SUMO (km/h) | Hà Nội (km/h) | Lệch | Lưu lượng (xe/h/m) |
|---|---|---|---|---|
| 0,030 | 29,3 | 32,8 | −10,7% | 862 |
| 0,049 | 28,7 | 26,5 | +8,1% | 1.406 |
| 0,063 | 28,2 | 23,5 | +20,2% | 1.772 |
| 0,073 | 24,9 | 21,6 | +15,2% | 1.820 |
| 0,081 | 23,3 | 20,4 | +14,3% | 1.884 |
| 0,087 | 21,2 | 19,5 | +8,7% | 1.839 |
| 0,106 | 16,0 | 17,0 | −6,0% | 1.700 |

Lệch tốc độ trung bình 11,9%, lớn nhất 20,2%. Năng lực 1.884 so với mốc 1.908 xe/h/m, lệch 1,3%.

Giới hạn: bộ này được chọn trong 12 bộ trên chính đường cong Hà Nội, chưa có dữ liệu giữ riêng. Bề rộng 7 m của mốc là giả định. Không kiểm được trên 0,106 xe/m² vì SUMO không nạp đủ xe, trong khi mật độ tới hạn của Hà Nội quy đổi khoảng 0,155; đỉnh lưu lượng của SUMO đến sớm hơn, quanh 0,08. `maxSpeed` 8,5 m/s chỉ là tham số khớp đường cong, không phải tốc độ tự do đo được.

**L2:** 37 lượt, 74.857 xe, 0 teleport (ngưỡng 300 s), 84 cảnh báo va chạm (1,1/1.000 xe).

- Xả hàng chờ trên 7 m: xe máy thuần 1.760 xe/h/m; có 15% ô tô 1.371 xe/h/m; thời gian mất lúc khởi động 2,3–2,4 s. Trên 3,5 m: 1.662 và 1.273.
- Trễ chưa bão hòa: 17,1 s (x 0,35) và 21,3 s (x 0,71), so với Webster 13,4 và 16,9 s.
- Nút 4 nhánh, 7 m, đủ hướng rẽ:

| Xe/h mỗi nhánh | Xe máy thuần: không tới đích, trễ | 15% ô tô: không tới đích, trễ |
|---|---|---|
| 1.000 | 0%, 17 s | 0%, 19 s |
| 2.000 | 0%, 19 s | 0%, 23 s |
| 3.000 | 0%, 23 s | 0,8%, 122 s |
| 4.000 | 0%, 86 s | 20,7%, 237 s |
| 5.000 | 14,4%, 206 s | 26,7%, 292 s |

- Hẻm ra đường chính: đường chính 1.500–4.000 xe/h, hẻm thoát hết, trễ 7–34 s, riêng hẻm 1,5 m với 800 xe/h ở 4.000 xe/h là 134 s. Đường chính 7.000 xe/h: trễ 23–459 s, hẻm 1,5 m với 800 xe/h có 43/200 xe chưa ra được.

Không xe nào đứng yên liên tục 300 s, nên không có dấu hiệu kẹt chết vĩnh viễn. Chưa rõ 20,7% ở 4.000 xe/h có 15% ô tô (x khoảng 0,86 theo năng lực đi thẳng) là năng lực thật của nút một làn có xe rẽ, hay do mô hình. Chưa có số đo TP.HCM để chấm xả hàng chờ và thời gian chờ ở miệng hẻm.

## Kết luận

| Tiêu chí | Kết quả |
|---|---|
| Sơ đồ cơ bản lệch ≤ 15% | Đạt theo trung bình (tốc độ 11,9%, năng lực 1,3%); một điểm lệch 20,2%; mốc là số Hà Nội, tối ưu trên chính mốc đó |
| Không kẹt chết do mô hình ở nút | Đạt: 0 teleport trên 74.857 xe; nhánh 4.000 xe/h có ô tô cần theo dõi |
| Episode ≤ 5 phút | Đạt nếu episode 15 phút và khoảng 7.000 xe trở xuống, chưa tính thời gian chính sách |

G1 đạt có điều kiện, chọn SUMO micro bỏ làn trong nút, chưa cần tự viết mô phỏng. Điều kiện: L3 phải kiểm lại bằng dữ liệu TP.HCM giữ riêng (tốc độ Mapbox và mật độ camera), mở rộng khỏi vùng mật độ đã khớp, và đo xả hàng chờ tại các nút có camera. Nếu L3 lệch vượt ngưỡng thì mở lại quyết định này.

## Cập nhật 2026-11-11: xe máy đổi sang IDM

**Lý do.** Bộ Krauss ở trên đạt theo sai số trung bình nhưng sai hình dạng. Từ 0,030 lên 0,063 xe/m², Hà Nội giảm 28% tốc độ, Krauss chỉ giảm 4%: tốc độ giữ ở mức tối đa rồi mới gãy khi khoảng cách hẹp. L3 lộ ra đúng lỗi này (mô phỏng phẳng rồi sập). Mốc: S = 98,34 − 12,3·ln D km/h, D xe máy/km trên 7 m (Nguyễn Cao Ý và cs.).

**Dò.** Vòng đường 1 làn 7 m, chỉ xe máy, 9 mật độ. Dò rộng 40 bộ (IDM: tốc độ mong muốn 11 / 12,5 / 14 m/s, khoảng thời gian bám xe 1,2 / 1,6 / 2,0 s, số mũ 2 / 4, khoảng hở ngang 0,3 / 0,5 m; thêm 4 bộ Krauss), dừng sau 120 lượt vì khoảng thời gian bám xe lớn làm sụt năng lực. Dò hẹp 12 bộ (11 / 12 m/s, 0,9 / 1,0 / 1,1 s, số mũ 2 / 3), 96 lượt, 0 teleport. Kết quả thô: `D:\sol1_backup\g0\l1_shape`, `l1_shape2`.

Sửa harness: IDM từ chối chèn xe đứng xếp lưới (113/353 xe ở 0,063 xe/m² không vào, SUMO không báo). Xe xếp lưới giờ chèn với `insertionChecks="none"`; Krauss vốn chèn đủ nên không đổi.

**Chọn:** `base:...;carFollowModel=IDM;maxSpeed=11;tau=1.1;delta=2;minGapLat=0.3` (phần `base` như cũ).

| Mật độ (xe/m²) | 0,020 | 0,030 | 0,044 | 0,059 | 0,079 | 0,098 | 0,128 |
|---|---|---|---|---|---|---|---|
| IDM (km/h) | 34,8 | 33,3 | 30,3 | 27,7 | 22,9 | 18,5 | 13,9 |
| Hà Nội (km/h) | 37,8 | 32,8 | 27,8 | 24,3 | 20,7 | 18,0 | 14,8 |

Sai số trung bình 7,4%, lớn nhất 14,2% (Krauss: 11,9% và 20,2%). Năng lực 1.816 xe/h/m, thấp hơn mốc 1.908 là 5%. Bộ 1,2 s bám hình dạng tốt hơn (6,8%) nhưng năng lực thấp hơn 10%. Vẫn tối ưu trên chính mốc Hà Nội, chưa có dữ liệu giữ riêng.

**L2 chạy lại** (`g0\l2_idm`, 37 lượt, đúng cấu hình cũ):
- Nút 4 nhánh: như cũ đến 3.000 xe/h; ở 4.000 xe/h chỉ xe máy, 46 xe chưa tới đích (cũ 0). Có 3 teleport ở các nhánh có ô tô quá tải.
- Hẻm ra đường chính: như cũ đến 4.000 xe/h; hẻm 1,5 m với 800 xe/h trễ 217 s (cũ 134 s).
- Số "xả hàng chờ" của L2 bị giới hạn bởi khâu chèn xe: kịch bản yêu cầu 28.000 xe/h, SUMO chỉ chèn được 6.400–9.400 xe/h, nên hàng chờ không luôn đầy. Hạn chế này có ở cả bộ cũ. Đo lại bằng hàng chờ xếp sẵn 360 xe trước đèn đỏ: Krauss 1.954, IDM 1.851 xe/h/m, 0 teleport.
- Chèn xe Poisson 3.000 và 6.000 xe/h vào đường 7 m: cả hai mô hình chèn đủ, trễ xuất phát 0,3 s.

**Kết luận.** IDM thay Krauss làm ứng viên G1: hình dạng L1 tốt hơn, L2 tương đương, chỉ kém hơn ở tải rất cao. Trên trục Khánh Hội (L3) đổi mô hình gần như không đổi kết quả, vì mật độ giữa đoạn ở đó thấp (khoảng 0,01 xe/m²); tốc độ trục chủ yếu do đèn.
