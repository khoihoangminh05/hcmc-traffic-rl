# Thiết kế L4: cả mạng, 5–21h (bản nháp 2026-11-11, chưa chạy)

Mục tiêu theo `PLAN_FINAL.md`: cả mạng Quận 4, nhu cầu thay đổi theo giờ, qua được cổng G2 trên dữ liệu giữ riêng. Tài liệu này chỉ là thiết kế: chưa chạy gì, mỗi bước có điều kiện dừng.

## Điều L3 buộc phải tính đến

1. **Lưu lượng không suy ra được từ tốc độ.** Trên trục Khánh Hội, lưu lượng và trễ ở đèn đánh đổi được cho nhau mà tốc độ vẫn khớp (`VALIDATE_L3.md`). L4 phải có ít nhất một nguồn đo độc lập cho lượng xe.
2. **Số xe camera là mật độ, không phải lưu lượng.** Khung nhìn ở nút bị hàng chờ chi phối. Chỉ dùng hình dạng theo giờ và so với mật độ mô phỏng trong đúng vùng nhìn, không đổi thẳng sang lưu lượng.
3. **Chỗ lệch L3 chưa giải quyết.** Để khớp Mapbox, buổi trưa gần như không có xe, trái với camera. L4 có thêm xe ra vào từ đường nhánh, là giả thuyết chưa kiểm được ở L3. Nếu L4 vẫn lệch y như vậy thì đó là giới hạn của mô hình và phải báo.
4. **Cấu hình mô phỏng đã chốt:**
   - mạng `net_v8`: mỗi chiều một làn rộng, tốc độ tự do đo được, bỏ vạch dừng thừa;
   - xe máy IDM;
   - xe đến theo Poisson;
   - sublane 0,4 m, bước 0,5 s, không làn trong nút;
   - `--collision.action warn`.

## Nhu cầu

| Thành phần | Nguồn | Nhãn |
|---|---|---|
| Xe đi xuyên qua quận, vào ra qua 24 cổng vào và 23 cổng ra (cầu, đường chính) | Camera ở cầu cho hình dạng theo giờ; mức tổng là ẩn số | đo được (hình dạng), hiệu chỉnh (mức) |
| Chuyến nội quận | Dân số theo chiều dài hẻm (proxy đang dùng ở `demand.py`), điểm đến theo POI nếu có | giả định |
| Tỷ lệ ô tô theo giờ | Camera (`l3_counts`, mở rộng ra 22 camera) | đo được |
| Đường đi | Ô tô và xe máy chọn đường theo thời gian đi (định tuyến lại định kỳ), ô tô theo `route_bans.json` | mô hình |

Ẩn số mỗi giờ: hệ số mức của nhóm cổng (cầu Khánh Hội, Ông Lãnh, Tân Thuận, Kênh Tẻ, Nguyễn Tất Thành; khoảng 6 nhóm) và một hệ số cho nhu cầu nội quận. Khoảng 7 số mỗi giờ, đủ ít để không vặn cho khớp từng đoạn.

## Hiệu chỉnh và kiểm tra

- **Dữ liệu chia đôi:**
  - Mapbox điển hình chia theo đoạn 300 m: một nửa số đoạn để hiệu chỉnh, nửa kia giữ riêng.
  - Mapbox trực tiếp (`probe_full2`) là nguồn kiểm thứ hai.
  - Camera: hình dạng theo giờ, so với mật độ mô phỏng trong vùng nhìn, đoạn trong bán kính 100 m.
- **Cách tìm:** SPSA hoặc chia lưới thô trên 7 hệ số mỗi giờ, SUMO chạy thật trong vòng lặp. Mỗi giờ hiệu chỉnh riêng, có 15 phút khởi động như L3.
- **Chấm theo cổng G2:**
  - Spearman theo khúc 300 m ≥ 0,5;
  - TTI theo loại đường lệch ≤ 15%;
  - sai số trung vị tốc độ ≤ 20%;
  - thứ hạng mật độ ở camera ≥ 0,5;
  - xe không tới đích ≤ 2%; teleport ≤ 1/1000.

## Các bước, chi phí và điều kiện dừng

| Bước | Việc | Ước lượng | Dừng khi |
|---|---|---|---|
| S0 | Đo thời gian chạy một giờ cả mạng với khoảng 20.000 và 40.000 xe | 2 lượt | Một giờ mô phỏng quá 15 phút thì xem lại quy mô trước khi làm tiếp |
| S1 | Đếm lại 22 camera bằng YOLO UVH (đủ 2 ngày có ảnh), tỷ lệ ô tô và hình dạng theo giờ mỗi camera | khoảng 1 giờ CPU | Camera nào có ảnh tối hoặc hỏng quá 30% thì loại và ghi lại |
| S2 | Sinh nhu cầu theo giờ (cổng + nội quận), chạy một giờ ở mức đoán, mở từng đường chính xem có đường trống hay nghẽn vô lý không | 2–3 lượt | Có đường chính trống hoặc kẹt chết thì sửa nhu cầu hay mạng trước, không hiệu chỉnh |
| S3 | Hiệu chỉnh 7 hệ số cho 8h, 12h, 17h trên nửa hiệu chỉnh | khoảng 20–40 lượt mỗi giờ | Sau 10 vòng không cải thiện thì dừng, báo số |
| S4 | Chấm trên nửa giữ riêng và Mapbox trực tiếp; mở ảnh ở 5 chỗ lệch nhất | — | — |
| S5 | Mở rộng ra 5–21h nếu S4 đạt | — | — |

## Rủi ro đã biết

- **Ít dữ liệu đúng ngày:** Mapbox điển hình là ngày 9 và 10/11, camera mới có 2 ngày, nên tạm thời mới chia được theo đoạn đường, chưa chia theo ngày được. Đủ 2 tuần camera (khoảng 21/11) thì chia thêm theo ngày.
- **Thiếu số đo:** lượng xe đi xuyên quận và tỷ lệ xanh chưa đo; offset đèn rút ngẫu nhiên theo seed.
- **Chuyến nội quận là giả định:** báo kết quả theo dải giả định, không coi là số đo.
