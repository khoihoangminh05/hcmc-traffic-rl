# Kiểm chứng L3: một trục, trục Khánh Hội (2026-11-10)

Mã: `ml-core/routing2/validate/l3_axis.py`. Mạng: `D:\sol1_backup\net_v6` (`routing2/net_rules.py`). Kết quả thô: `D:\sol1_backup\g0\l3_*`.

## Kết luận

**L3 đạt một phần. Chưa được coi là đã khớp hình dạng theo giờ.**

- Mức tốc độ đạt: sai số trung bình 14,1% ở chiều hiệu chỉnh và 9,8% ở chiều giữ riêng.
- Xu hướng theo giờ đúng chiều ở chiều giữ riêng (tương quan 0,82, chỉ 6 khung giờ).
- Biên độ cao điểm không đạt: mô phỏng hoặc gần như phẳng, hoặc sập hẳn lúc 17h. Chiều giữ riêng giảm 9,1%, Mapbox giảm 26,0%.
- Chưa so mật độ, dù kế hoạch yêu cầu: chưa đo chiều dài đường mà camera nhìn thấy.

Một seed, một trục, 6 khung giờ. Chưa đủ để nói về cả mạng.

## Thiết lập

- Mỗi khung giờ 8, 10, 12, 15, 17, 18h chạy riêng: 15 phút khởi động và 1 giờ đo, bước 0,5 s.
- Xe chỉ đi suốt trục theo hai chiều, không có xe từ đường nhánh. Hai chiều cùng lưu lượng.
- Bề rộng 7 m mỗi chiều (giả định), chia đều cho số làn.
- Hình dạng lưu lượng theo giờ lấy từ số xe camera (`n`) hoặc số xe nhân tốc độ Mapbox (`n_v`). Mức tổng là một số `alpha`, xe/giờ mỗi chiều, trung bình trong ngày.
- Tốc độ tự do mỗi đoạn lấy từ Mapbox 5h, có sửa (mục Lỗi đã sửa).
- Mốc so: tốc độ ô tô Mapbox điển hình theo giờ. Chọn `alpha` và hình dạng trên chiều 324, chiều 142 giữ riêng.

## Kết quả cuối (`l3_v6f`, 60 lượt, 3 lượt có teleport, mỗi lượt 1 xe)

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
| `l3_v6f` | 60 | v6 có sửa tốc độ tự do | Kết quả cuối |
| `l3_green` | 36 | v6 có sửa, tỷ lệ xanh 35% và 65% | Kiểm độ nhạy, 1 lượt có teleport |

## Điểm còn lệch

1. **Mô phỏng có ngưỡng gắt.** Chiều 324 lúc 17h ổn ở `alpha` 1000 (19,4 km/h) nhưng còn 7,7 km/h ở 1500 và 3,3 km/h ở 2000. Mapbox không xuống dưới 15 km/h. Kết quả ở `alpha` đã chọn nhạy với mức lưu lượng.
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

## Việc tiếp

- Tìm cơ chế làm tốc độ giảm dần theo lưu lượng khi chưa bão hòa, đối chiếu tài liệu xe máy và ảnh thật.
- Muốn tách lưu lượng khỏi tỷ lệ xanh: đếm xe qua vạch theo chu kỳ ở vài camera, hoặc khoanh tay vùng hàng chờ từng hướng.
- Đo chiều dài nhìn thấy của camera để so mật độ.
- Thêm xe từ đường nhánh khi sang L4; tách lưu lượng theo chiều nếu có dữ liệu.
- Chạy thêm seed và trục Nguyễn Tất Thành để xác nhận.
