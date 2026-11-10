> **Đã thay bằng `.docs/PLAN_FINAL.md` (2026-11-09).** Giữ lại để tra cứu.

# Quy trình 7 bước (người dùng chốt 2026-11-08, thay `PLAN_CALIB_TRAIN.md`)

Xong bước trước mới sang bước sau. **Bỏ SUMO meso.** Các kết quả trước đây trên meso và mọi phép so baseline, UE–SO không dùng được.

1. Có đủ thông tin về mạng thật: mật độ xe theo từng loại, theo từng khung giờ của từng ngày trong tuần; chu kỳ đèn; chi tiết các hẻm cũng phải có các thông số đó.
2. Tái dựng trên SUMO toàn bộ thông số đó, kết hợp đặc điểm giao thông Việt Nam: xe lách làn, không đi đúng làn, vượt đèn, tai nạn, vào hẻm không có điều phối. Phải khớp từng giờ; sai thì tìm nguyên nhân. Nếu SUMO không mô phỏng được giao thông Việt Nam thì viết bộ mô phỏng riêng.
3. Bộ kịch bản: random, đi qua nhiều đường, cực đoan… chỉ 100–200 xe.
4. Thiết kế mạng MAPPO phù hợp nhất.
5. Định nghĩa lại bài toán: đầu vào, đồng bộ thời gian, đầu ra của điều phối, đồng bộ hay bất đồng bộ, xe thấy gì, ai điều phối.
6. Thêm baseline.
7. Cuối cùng mới train.

## Bước 1: kiểm kê (2026-11-08)

| Thông tin cần có | Hiện có | Thiếu | Cách lấy |
|---|---|---|---|
| Hình học mạng | OSM, 3888 cạnh: primary 22.5 km, secondary 21.5, tertiary 24.1, residential 22.8, service 32.2, hẻm 80.5 | | |
| Số làn | Thẻ OSM, chưa đối chiếu; thiếu thì tự gán | Kiểm thực tế | Ảnh camera (trục chính), ảnh vệ tinh |
| Bề rộng đường và hẻm | **Không có:** OSM có 0 cạnh ghi width trong Q4; mạng dùng giả định 1.25 m mỗi chiều; footprint nhà chỉ đủ cho 2/730 hẻm | Toàn bộ | Đo trên ảnh vệ tinh hoặc Street View theo mẫu phân tầng (`alley_width sample`), khảo sát thực địa |
| Cấm rẽ | 131 relation trong OSM, **chưa đưa vào mạng** | Đưa vào netconvert | Overpass |
| Đèn | 82 nút có đèn (OSM). Chu kỳ 60 s, đỏ 30 s và offset là **tự đặt** | Chu kỳ thật | Chuỗi ảnh mỗi 20 s ở 22 camera (khung ảnh cổng thông tin làm mới khoảng 12 s), 9–13/11 giờ 7–8h30, 11h30–12h, 16h30–18h30. Chỉ phủ các nút có camera |
| Tốc độ theo giờ | Mapbox ô tô: phủ chiều dài primary 65%, secondary 95%, tertiary 95%, residential 26%, service 4%, hẻm 34% (giá trị trong hẻm là ô tô, chưa kiểm) | Xe máy, phần chưa phủ | |
| Mật độ ô tô theo giờ, ngày | 22 camera, ảnh mỗi 5 phút từ 7/11; đếm ô tô lệch khoảng 25–40% | Cần đủ các ngày trong tuần (≥ 2 tuần), hiệu chỉnh | Tiếp tục thu |
| Mật độ xe máy theo giờ, ngày | **Chưa đo được:** YOLO COCO sai nhiều (22 đếm tay → 6) | Bộ đếm xe máy | Huấn luyện model riêng trên ảnh đã gán nhãn |
| Mật độ trong hẻm, theo từng loại | **Không có nguồn nào** (không camera, Mapbox không đếm xe) | Toàn bộ | Chỉ có thể khảo sát thực địa theo mẫu, rồi suy rộng cho hẻm khác |
| Vượt đèn, tai nạn | Không có số đo | Tỉ lệ | Đo từ chuỗi ảnh; tai nạn: số liệu công bố nếu có |

Cổng qua bước 1 cần chốt với người dùng: phần hẻm không có nguồn tự động.
