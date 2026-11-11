# Kiểm chứng L3: một trục, trục Khánh Hội (2026-11-10)

Mã: `ml-core/routing2/validate/l3_axis.py`. Mạng: `D:\sol1_backup\net_v6` (`routing2/net_rules.py`). Kết quả thô: `D:\sol1_backup\g0\l3_*`.

## Kết luận

**L3 đạt một phần. Mức tốc độ và xu hướng theo giờ khớp, biên độ cao điểm mới bằng khoảng một nửa thực tế hoặc thấp hơn.**

Cấu hình cuối: mạng `net_v7` (mỗi chiều một làn rộng bằng mặt đường), xe đến ngẫu nhiên, hình dạng lưu lượng theo số xe camera, `alpha` 2500, chọn trên chiều 324. Trung bình 2 seed, tổng 12 lượt, 0 teleport:

| | Sai số TB % | Tương quan theo giờ | Tốc độ giảm cao điểm % (mô phỏng / Mapbox) | Tốc độ mô phỏng 8, 10, 12, 15, 17, 18h |
|---|---|---|---|---|
| Chiều 324 (hiệu chỉnh) | 9,1 | 0,63 | 16,6 / 29,9 | 18,1 / 18,5 / 18,1 / 17,7 / 15,4 / 17,2 |
| Chiều 142 (giữ riêng) | 12,0 | 0,83 | 10,8 / 26,0 | 17,6 / 18,1 / 17,6 / 17,3 / 16,2 / 16,9 |

Mapbox: chiều 324 16,1 / 19,0 / 21,5 / 19,9 / 15,1 / 15,5; chiều 142 21,0 / 20,9 / 22,1 / 20,7 / 16,6 / 16,3.

Hai seed cho kết quả gần như nhau. Chưa so mật độ vì chưa đo chiều dài đường camera nhìn thấy. Mức `alpha` chưa có số đo lưu lượng độc lập. Một trục, 6 khung giờ.

## Vì sao trước đó sập

Chiều 324 sập ở 1250–1500 xe/giờ là lỗi dựng mạng, không phải năng lực thật. OSM ghi số làn thay đổi dọc đường trong khi mặt đường liền. Sau nút Khánh Hội – Hoàng Diệu đường từ 2 làn về 1 làn, `netconvert` chỉ nối làn phải (`6772914371_2032267337` lane 0 sang lane 0), nên cả mặt đường dồn vào một làn 3,5 m. Năng lực ước tính khoảng 2.050 xe/giờ (1.273 xe/h/m × 3,5 m × tỷ lệ xanh 0,46, số xả hàng chờ lấy từ L2), khớp lưu lượng nghẽn đo được 1.600–1.770 xe/giờ.

Sửa: `net_rules.py --one-lane`, mỗi chiều một làn, bề rộng bằng tổng các làn cũ. Đây cũng là cấu hình đã qua L1/L2. Ở `alpha` 3000 lúc 17h (4.100 xe/giờ vào) trục mới quá tải, khoảng 3.600 xe/giờ qua được. Kiểm thử tác động: `alpha` 1500 lúc 17h, chiều 324 từ 7,2 lên 19,0 km/h.

Mô hình một làn rộng để SUMO cho xe máy đi ngang hàng trong làn. Năng lực khớp số Hà Nội ở L1/L2, nhưng kiểu len lỏi chưa đối chiếu với dữ liệu xe máy Việt Nam.

## Kết quả trên mạng v7 (`l3_v7`, seed 0, Poisson)

| Hình dạng | alpha | Chiều 324: sai số %, giảm %, tương quan | Chiều 142: sai số %, giảm %, tương quan |
|---|---|---|---|
| n | 1500 | 14,8; 5,9; 0,58 | 10,5; 6,5; 0,70 |
| n | 2000 | 11,4; 8,6; 0,68 | 11,4; 7,2; 0,72 |
| **n** | **2500** | **9,0; 17,0; 0,63** | **11,9; 11,8; 0,81** |
| n | 3000 | 19,3; 56,5; 0,64 | 19,8; 37,2; 0,70 |
| n | 3500 | 42,2; 68,9; 0,61 | 32,2; 34,5; 0,87 |
| n_v | 1500 | 16,1; 4,9; −0,34 | 11,0; 6,1; 0,21 |
| n_v | 2000 | 14,5; 4,7; −0,53 | 13,0; 6,0; −0,09 |
| n_v | 2500 | 13,4; 7,6; −0,35 | 14,4; 7,1; −0,21 |
| n_v | 3000 | 18,9; 37,7; −0,63 | 17,3; 14,8; −0,27 |
| n_v | 3500 | 35,6; 62,7; −0,62 | 29,0; 33,0; −0,17 |

Mapbox giảm 29,9% (324) và 26,0% (142). Hình dạng `n_v` vẫn tương quan âm, nên loại.

Các mục dưới là quá trình dẫn tới đây, trên mạng cũ, giữ để đủ mọi lượt đã chạy.

## Thiết lập

- Mỗi khung giờ 8, 10, 12, 15, 17, 18h chạy riêng: 15 phút khởi động và 1 giờ đo, bước 0,5 s.
- Xe chỉ đi suốt trục theo hai chiều, không có xe từ đường nhánh. Hai chiều cùng lưu lượng.
- Bề rộng 7 m mỗi chiều (giả định), chia đều cho số làn.
- Hình dạng lưu lượng theo giờ lấy từ số xe camera (`n`) hoặc số xe nhân tốc độ Mapbox (`n_v`). Mức tổng là một số `alpha`, xe/giờ mỗi chiều, trung bình trong ngày.
- Tốc độ tự do mỗi đoạn lấy từ Mapbox 5h, có sửa (mục Lỗi đã sửa).
- Mốc so: tốc độ ô tô Mapbox điển hình theo giờ. Chọn `alpha` và hình dạng trên chiều 324, chiều 142 giữ riêng.

## Kết quả trên mạng v6, 2 làn (`l3_v6f`, 60 lượt, 3 lượt có teleport, mỗi lượt 1 xe)

Mapbox, km/h, theo thứ tự 8, 10, 12, 15, 17, 18h:

- Chiều 324: 16,2 / 19,0 / 21,5 / 19,9 / 15,1 / 15,5
- Chiều 142: 21,0 / 20,9 / 22,1 / 20,7 / 16,6 / 16,3

| Hình dạng | alpha | Chiều | Sai số TB % | Giảm cao điểm % (mô phỏng / Mapbox) | Tương quan | Tốc độ mô phỏng theo giờ |
|---|---|---|---|---|---|---|
| n | 1000 | 324 | 15,6 | 4,4 / 29,7 | 0,76 | 20,0 / 20,3 / 20,2 / 20,0 / 19,4 / 19,8 |
| n | 1000 | 142 | 8,5 | 7,4 / 26,0 | 0,84 | 20,3 / 20,5 / 20,4 / 19,9 / 19,0 / 19,7 |
| **n** | **1500** | **324** | **14,1** | **60,0 / 29,7** | **0,67** | 18,5 / 19,3 / 19,2 / 18,4 / 7,7 / 15,7 |
| **n** | **1500** | **142** | **9,8** | **9,1 / 26,0** | **0,82** | 19,0 / 19,4 / 19,0 / 18,5 / 17,6 / 18,3 |
| n | 2000 | 324 | 67,1 | 67,9 / 29,7 | 0,59 | 5,9 / 10,2 / 7,6 / 4,6 / 3,3 / 4,1 |
| n | 2000 | 142 | 10,6 | 10,1 / 26,0 | 0,91 | 18,0 / 18,3 / 18,1 / 17,7 / 16,5 / 17,1 |
| n | 2500 | 324 | 80,6 | 29,1 / 29,7 | 0,67 | 3,4 / 4,1 / 3,8 / 3,3 / 2,9 / 3,2 |
| n | 2500 | 142 | 21,2 | 46,3 / 26,0 | 0,72 | 16,8 / 17,5 / 17,0 / 16,5 / 9,4 / 15,7 |
| n | 3000 | 324 | 82,5 | 17,0 / 29,7 | 0,74 | 3,1 / 3,4 / 3,3 / 3,1 / 2,8 / 2,9 |
| n | 3000 | 142 | 41,3 | 45,6 / 26,0 | 0,72 | 12,2 / 16,2 / 13,7 / 9,6 / 8,8 / 9,0 |
| n_v | 1000 | 324 | 16,6 | 2,6 / 29,7 | −0,17 | 20,2 / 20,1 / 20,2 / 19,7 / 20,0 / 20,0 |
| n_v | 1000 | 142 | 10,4 | 5,1 / 26,0 | 0,12 | 20,4 / 20,5 / 19,7 / 19,5 / 19,7 / 20,0 |
| n_v | 1500 | 324 | 20,9 | 33,7 / 29,7 | −0,66 | 19,3 / 19,4 / 14,7 / 12,9 / 17,6 / 18,7 |
| n_v | 1500 | 142 | 11,6 | 4,9 / 26,0 | 0,29 | 19,3 / 19,1 / 18,5 / 18,3 / 18,5 / 18,6 |
| n_v | 2000 | 324 | 63,7 | 68,2 / 29,7 | −0,54 | 11,1 / 6,7 / 3,9 / 3,5 / 4,7 / 7,2 |
| n_v | 2000 | 142 | 13,3 | 5,9 / 26,0 | −0,11 | 18,3 / 18,2 / 17,4 / 17,2 / 17,5 / 18,1 |
| n_v | 2500 | 324 | 79,9 | 24,6 / 29,7 | −0,37 | 4,2 / 3,8 / 3,2 / 3,1 / 3,3 / 3,5 |
| n_v | 2500 | 142 | 18,4 | 27,6 / 26,0 | −0,24 | 17,5 / 17,2 / 15,3 / 12,7 / 16,1 / 17,0 |
| n_v | 3000 | 324 | 82,7 | 15,1 / 29,7 | 0,13 | 3,1 / 3,4 / 3,0 / 2,9 / 2,9 / 3,0 |
| n_v | 3000 | 142 | 36,8 | 43,1 / 26,0 | −0,08 | 16,2 / 14,1 / 9,3 / 9,2 / 9,4 / 15,0 |

Theo sai số trên chiều 324, chọn `n`, `alpha` = 1500. Đây là chọn theo tiêu chí đặt trước, không phải theo chiều giữ riêng. Hình dạng `n_v` cho tương quan âm hoặc gần 0, nên bị loại.

## Lỗi đã sửa

| Lỗi | Dấu hiệu | Cách sửa | Tác động |
|---|---|---|---|
| Tham số bề rộng áp cho từng làn | Đoạn 2 làn rộng 14 m mỗi chiều thay vì 7 m | Chia bề rộng cho số làn | Năng lực giảm, ngưỡng sập lùi từ trên 1500 xuống 1250 |
| Vạch dừng thừa trong nút | Nút không đèn nằm giữa hai nút có đèn của cùng cụm làm xe gặp vạch dừng thứ hai | `inner_nodes` trong `net_rules.py`, có test; 16/27 cụm đèn đổi, mạng v6 | Tốc độ khi ít xe tăng từ khoảng 17 lên 19 km/h; không hết sập |
| Tốc độ tự do chứa độ trễ tại nút | Đoạn 12 m sau vạch dừng có tốc độ 5h 9,3 km/h, hai bên 25–27 km/h, bóp lưu lượng xả | `free_speeds`: đoạn dưới 60% trung vị lân cận lấy trung vị đó; trục này đổi 1 đoạn | Mức 1500: chiều 324 lúc 12h từ 4,7 lên 14,7 km/h, lúc 15h từ 4,5 lên 12,9 km/h |

Ngưỡng 60% là quy tắc tự đặt. Khi lên L4 phải áp chung cho cả mạng và kiểm số đoạn bị đổi.

## Mọi lượt đã chạy

| Thư mục | Số lượt | Mạng và trạng thái | Ghi chú |
|---|---|---|---|
| `l3_w7` | 6 | v5, chạy liền 14 giờ, mất khi khởi động lại phiên | Sai số 8–12%, phẳng theo giờ |
| `l3_slices` | 23/60 | v5, dừng giữa chừng | `alpha` 5000 trở lên đều bão hòa |
| `l3_edge` | 2 | v5, chẩn đoán | Thêm số liệu từng đoạn |
| `l3_fine` | 60 | v5, sửa bề rộng, còn hai lỗi sau | Ngưỡng sập 1250 |
| `l3_v6` | 27/60 | v6, dừng vì còn lỗi tốc độ tự do | |
| `l3_free` | 2 | v6 có sửa tốc độ tự do, kiểm chứng | |
| `l3_v6f` | 60 | v6 có sửa tốc độ tự do | Còn lỗi giảm làn |
| `l3_poisson` | 55/60 | v6, xe đến ngẫu nhiên | Dừng sớm vì các mức cao đã sập |
| `l3_v7_test` | 6 | v7, kiểm chứng một làn | |
| `l3_v7` | 66 | v7, Poisson, 60 lượt seed 0 và 6 lượt seed 1 | Kết quả cuối |
| `l3_green` | 36 | v6 có sửa, tỷ lệ xanh 35% và 65% | Kiểm độ nhạy, 1 lượt có teleport |

## Điểm còn lệch

1. **Mô phỏng có ngưỡng gắt (mạng cũ, đã giải thích ở mục Vì sao trước đó sập).** Chiều 324 lúc 17h ổn ở `alpha` 1000 (19,4 km/h) nhưng còn 7,7 km/h ở 1500 và 3,3 km/h ở 2000. Mapbox không xuống dưới 15 km/h. Kết quả ở `alpha` đã chọn nhạy với mức lưu lượng.
2. **Thiếu biên độ khi chưa bão hòa.** Dưới ngưỡng, tốc độ gần như chỉ phụ thuộc vào đèn. Có thể do thiếu xe từ đường nhánh, xe đỗ, người đi bộ. Chưa kiểm được.
3. **Lệch chiều lúc 8h không tái hiện được.** Mapbox: 16,2 km/h chiều 324, 21,0 km/h chiều 142. Mô phỏng cho hai chiều lưu lượng bằng nhau vì camera không tách chiều.
4. **Tỷ lệ xanh đang giả định chia đều.** Camera Khánh Hội – Hoàng Diệu, sáng 9/11: gấp theo chu kỳ 82 s thấy khối xe đứng yên liền nhau, đỏ ước 52–66 s trên hướng nhìn thấy. Buổi trưa và chiều không ra cấu trúc rõ, có thể do chu kỳ đổi hoặc hàng chờ ngắn. Mới một camera, chưa đưa vào mô hình.
5. **Xe xếp hàng trước nút.** Ngay cả sau sửa, ở mức 1500 lúc 12–15h xe vẫn chờ khoảng 26 giây ở đoạn 50 m trước vạch Khánh Hội – Hoàng Diệu.

## Độ nhạy theo tỷ lệ xanh (`l3_green`)

Hình dạng `n`, thay tỷ lệ xanh của trục ở hai cụm đèn i15 và i21. Cụm i0 không đổi vì trục xanh ở cả hai pha. Chiều 324, km/h, theo thứ tự 8, 10, 12, 15, 17, 18h:

| alpha | Xanh 35% | Xanh 50% | Xanh 65% |
|---|---|---|---|
| 1000 | 18,4 / 18,8 / 18,6 / 17,9 / 10,2 / 17,6 | 20,0 / 20,3 / 20,2 / 20,0 / 19,4 / 19,8 | 21,6 / 22,0 / 21,9 / 21,5 / 21,2 / 21,2 |
| 1500 | 5,7 / 8,7 / 5,7 / 4,2 / 2,7 / 3,8 | 18,5 / 19,3 / 19,2 / 18,4 / 7,7 / 15,7 | 20,7 / 21,2 / 21,0 / 20,6 / 19,4 / 20,1 |
| 2000 | 2,7 / 3,1 / 2,8 / 2,5 / 2,1 / 2,4 | 5,9 / 10,2 / 7,6 / 4,6 / 3,3 / 4,1 | 19,3 / 20,4 / 19,6 / 16,7 / 5,9 / 12,7 |

Sai số thấp nhất trên chiều 324: 14,2% (xanh 35%, `alpha` 1000), 14,1% (xanh 50%, `alpha` 1500), 17,3% (xanh 65%, `alpha` 1500). Chiều 142 giữ riêng ở ba cặp này: 10,3%, 9,8%, 8,4%.

Rút ra hai điều:

- **Lưu lượng và tỷ lệ xanh không tách được chỉ từ tốc độ.** Tăng tỷ lệ xanh dời ngưỡng sập lên mức lưu lượng cao hơn, ba cặp trên cho sai số gần nhau. Muốn biết lưu lượng thật phải có số đo lưu lượng hoặc tỷ lệ xanh độc lập.
- **Đổi tỷ lệ xanh không tạo ra biên độ cao điểm thực tế.** Ở cả ba mức, mô phỏng vẫn hoặc gần như phẳng, hoặc sập. Vấn đề biên độ cần cơ chế khác.

## Đo tỷ lệ xanh từ ảnh: thất bại

Thử tự động trên 18 cặp camera và khung giờ, ảnh ngày 9/11: chia ô lưới, gấp theo chu kỳ, gom ô thành hai nhóm theo pha. Với đèn hai pha, tổng hai thời gian đỏ phải khoảng 1,05–1,1 lần chu kỳ, số đo ra 0,51–1,59, một camera không ra nhóm nào. Ảnh chồng nhóm cho thấy ô được chọn nằm cả trên nhà và nền đường trống, hai nhóm lẫn trong cùng một làn. Không dùng kết quả này. Mã giữ ở `D:\sol1_backup\g0\scripts\green_split_failed.py`.

Số 52–66 s ở điểm 4 trên là từ vùng khoanh tay trên một camera, vẫn chỉ là một mẫu.

## Xe đến ngẫu nhiên (`l3_poisson`)

Giả thuyết: dòng xe vào đều tăm tắp không gây trễ thêm ở đèn cho đến khi vượt năng lực, nên mô phỏng phẳng rồi sập. Đổi sang dòng Poisson, hình dạng `n`, xanh 50%, 2 seed. Dừng ở 55/60 lượt, phần bỏ dở là một số lượt của `alpha` 2000; 2 xe teleport.

| alpha | Chiều | Sai số TB % | Giảm cao điểm % (mô phỏng / Mapbox) | Tương quan | Tốc độ theo giờ |
|---|---|---|---|---|---|
| 1000 | 324 | 15,5 | 7,8 / 29,7 | 0,51 | 20,0 / 20,5 / 20,2 / 19,5 / 19,0 / 19,7 |
| 1000 | 142 | 9,8 | 5,8 / 26,0 | 0,72 | 19,7 / 20,2 / 19,9 / 19,5 / 19,0 / 19,5 |
| **1250** | **324** | **12,2** | **11,8 / 29,7** | **0,63** | 19,5 / 19,8 / 19,4 / 19,0 / 17,5 / 18,4 |
| **1250** | **142** | **10,1** | **5,8 / 26,0** | **0,88** | 19,2 / 19,4 / 19,5 / 19,2 / 18,4 / 18,9 |
| 1500 | 324 | 16,5 | 62,7 / 29,7 | 0,62 | 18,3 / 19,2 / 18,8 / 16,5 / 7,2 / 15,2 |
| 1500 | 142 | 10,4 | 7,6 / 26,0 | 0,85 | 18,6 / 19,1 / 18,9 / 18,5 / 17,7 / 18,2 |
| 1750 | 324 | 43,9 | 76,2 / 29,7 | 0,64 | 10,5 / 17,4 / 14,0 / 8,1 / 4,1 / 7,4 |
| 1750 | 142 | 10,4 | 9,6 / 26,0 | 0,87 | 18,2 / 18,7 / 18,6 / 17,9 / 16,9 / 17,5 |

Giả thuyết chỉ đúng một phần. Ở mức tốt nhất (`alpha` 1250) sai số giảm còn 12,2% và không còn sập, nhưng biên độ vẫn chỉ 11,8% so với 29,7%, chiều giữ riêng 5,8% so với 26,0%. Lên 1500 chiều 324 vẫn sập lúc 17h. Dòng ngẫu nhiên nên được giữ vì thực tế hơn, nhưng chưa giải thích được phần thiếu.

## Việc tiếp

- Tìm cơ chế làm tốc độ giảm dần theo lưu lượng khi chưa bão hòa, đối chiếu tài liệu xe máy và ảnh thật.
- Muốn tách lưu lượng khỏi tỷ lệ xanh: đếm xe qua vạch theo chu kỳ ở vài camera, hoặc khoanh tay vùng hàng chờ từng hướng.
- Đo chiều dài nhìn thấy của camera để so mật độ.
- Thêm xe từ đường nhánh khi sang L4; tách lưu lượng theo chiều nếu có dữ liệu.
- Kiểm trục Nguyễn Tất Thành để xác nhận cấu hình một làn; xem cấu hình này tác động đến toàn mạng ra sao ở L4.

## Cập nhật 2026-11-11: dò lưu lượng ngược và kiểm bằng camera

Mã: `routing2/validate/l3_invert.py`. Mỗi giờ, mỗi chiều, dò lưu lượng vào (8 vòng chia đôi trên thang log, 30–6.000 xe/h) đến khi tốc độ ô tô mô phỏng bằng Mapbox. Rồi so số xe mô phỏng trong bán kính 100 m quanh 4 camera Khánh Hội với số camera đếm. Chỉ so hình dạng theo giờ, vì chưa biết chiều dài camera nhìn thấy.

| Giờ | Lưu lượng cần, chiều 324 (Krauss / IDM) | Chiều 142 (Krauss / IDM) |
|---|---|---|
| 8h | 3.031 / 2.677 | 451 / 655 |
| 12h | 533 / 490 | 31 / 31 (chạm cận dưới) |
| 17h | 3.431 / 2.908 | 2.790 / 2.790 |

Số xe quanh camera, tỷ lệ giờ cao nhất trên giờ thấp nhất (8, 12, 17h):

| Camera | Mô phỏng (IDM) | Camera |
|---|---|---|
| Kênh Tẻ | 11,7 | 1,23 |
| Hoàng Diệu | 18,6 | 1,59 |
| Vĩnh Hội | 12,1 | 1,30 |
| Đường số 41 | 57,3 | 2,20 |

**Mâu thuẫn.** Để khớp Mapbox, buổi trưa gần như phải không có xe. Nhưng camera thấy buổi trưa vẫn đông, bằng 60–80% giờ cao điểm. Quanh camera Hoàng Diệu lúc 12h, mô phỏng có khoảng 5 xe trong 338 m, camera đếm 36. Dù một phần số camera là xe đỗ hoặc xe đường ngang, chênh lệch vẫn quá lớn.

**Các giả thuyết đã kiểm:**

| Giả thuyết | Cách kiểm | Kết quả |
|---|---|---|
| Kiểu bám xe của xe máy | Đổi Krauss sang IDM (`VALIDATE_L1L2.md`) | L1 tốt hơn, L3 gần như không đổi |
| Ô tô kẹt sau xe máy | Đoạn 1 km, 7 m, không đèn, 20% ô tô | Ở 1.600 xe/h ô tô chỉ chậm 1–2%; xe máy đi bên phải thì gần 0 |
| Trễ dồn ở đèn | Tách trễ theo đoạn (`alpha` 1500 và 2500, 12h) | Đoạn có đèn chỉ thêm 3–11 s; đoạn khác thêm 15–37 s, do xe chậm cản xe nhanh |
| Mapbox "điển hình" sai | So với Mapbox trực tiếp (`probe_full2`, khoảng 250 m mỗi chiều, ngày thường) | Trực tiếp còn giảm mạnh hơn: chiều 324 từ 23,9 (12h) xuống 13,2 km/h (17h), chiều 142 từ 17,9 xuống 12,3 |
| Đèn đổi chu kỳ theo giờ | Đo chu kỳ khung 11:30–12:00 ngày 9/11, cùng phép kiểm như sáng và chiều | Khánh Hội – Hoàng Diệu 82 s (sáng 82), Kỳ Con 125 (như cũ), Nguyễn Văn Cừ 130 (chiều 129), Ông Lãnh 134 (chiều 144); không ủng hộ |

**Còn mở.** Mô phỏng chỉ có xe đi suốt trục thì tốc độ giảm theo lưu lượng sớm hơn thực tế, hoặc lưu lượng trưa thật thấp mà camera đếm cả xe không thuộc trục. Không tách được khi chưa có số đo lưu lượng thật (đếm xe qua vạch) hoặc tỷ lệ xanh theo giờ. Ứng viên chưa kiểm: tỷ lệ xanh theo giờ, xe vào ra đường nhánh dọc trục (ngoài đời một phần xe camera thấy không đi hết trục), số xe đỗ trong khung camera.

Đổi mặc định `MOTO` của `l3_axis.py` sang bộ IDM. Kết quả L3 ở mục Kết luận vẫn là của Krauss; với IDM, phép dò ngược cho số gần như giống.

## Cập nhật 2026-11-11 chiều: nguyên nhân là thiếu xe đường ngang

**Mapbox chỉ chỗ mất thời gian** (trễ so với 5h, theo đoạn). Chiều 324 lúc 8h: 96 s thêm, khoảng 57 s nằm trên 360 m quanh nút Vĩnh Hội (ngã ba không đèn) và trước nút Đường số 41. Nút Khánh Hội – Hoàng Diệu chỉ khoảng 5 s. Chiều 142 lúc 17h: chậm nhất ở 233 m trước nút Vĩnh Hội (25 s). Trễ dồn đúng chỗ đường nhánh nhập vào. Trong L3 các đường đó không có xe.

**Thí nghiệm** (`net_v8`, IDM, Poisson, Khánh Hội `alpha` 1500 hình dạng `n`):

| Giờ | Chiều 324: không xe rẽ / có xe rẽ / Mapbox | Chiều 142: không xe rẽ / có xe rẽ / Mapbox |
|---|---|---|
| 8h | 19,7 / 16,8 / 16,1 | 18,8 / 19,1 / 21,0 |
| 12h | 19,7 / 17,4 / 21,5 | 19,6 / 19,1 / 22,1 |
| 17h | 18,8 / 11,8 / 15,1 | 18,0 / 18,3 / 16,6 |

Xe rẽ là 1.000 xe/h nhân hình dạng camera, mỗi chiều: từ Vĩnh Hội vào Khánh Hội (chỉ rẽ phải vào chiều 324) và từ Khánh Hội vào Vĩnh Hội. Có xe đường ngang, mô phỏng tái hiện được 8h chậm ở chiều 324 mà không chậm ở chiều 142, điều trục trơn không làm được. Trưa thì quá chậm và 17h chậm quá mức, vì mức xe rẽ là giả định theo hình dạng camera đã bị nén.

**Hai lỗi dữ liệu tìm thấy trên đường đi:**

1. **Đường nhánh quá hẹp trong mạng.** Vĩnh Hội rộng 3,2 m mỗi chiều (số làn OSM nhân bề rộng mặc định). Với 1.000 xe/h, xe Vĩnh Hội không vào được: trễ xuất phát 23–119 s, 8–26 teleport "chờ quá lâu". Cho phép xe máy chen (`jmIgnoreFoeSpeed` 3 lên 6 hoặc 9 m/s) không đổi gì. Gán 7 m mỗi chiều thì hết kẹt (trễ 0,5 s, 0 teleport). Bề rộng đường nhánh là giả định chưa đo, ảnh hưởng cả L4.
2. **Số đếm camera không tỷ lệ với lưu lượng:**
   - vùng mặt đường khoanh lúc trước lấn vỉa hè, nên xe máy đỗ trước cửa hàng (8–15 chiếc mỗi camera) được tính là đang chạy; lọc xe đỗ theo độ trùng khung giữa các ảnh 5 phút chỉ bỏ được 10–20%;
   - camera đổi góc theo giờ (Hoàng Diệu, Vĩnh Hội);
   - YOLO đếm thiếu ở cảnh đông (G0: khoảng 58% số xe ở khung dày).

   Đếm bằng mắt ở Vĩnh Hội: trưa khoảng 20–22 xe đang chạy, 17h khoảng 45–50, tức mật độ gấp 2,2–2,5 lần, trong khi YOLO cho 34 và 57. Hình dạng nhu cầu theo giờ lấy từ camera hiện đang bị nén.

**Kết luận.** L3 kiểu "một trục, không xe ngang" không kiểm được mô phỏng: phần lớn biến động theo giờ ngoài đời đến từ xe ra vào ở các nút nhánh. L3 phải làm lại thành "trục cộng các đường ngang chính", lưu lượng đường ngang lấy từ Mapbox của chính đường đó. Đầu vào cần sửa trước:

- vùng mặt đường camera không lấn vỉa hè, tách theo góc nhìn;
- bề rộng đường nhánh đo được, ít nhất cho các đường cắt trục thử.
