# Định nghĩa bài toán (giai đoạn 0, `PLAN_FINAL.md`; bản nháp 2026-11-09 chờ người dùng chốt)

Cột "Code hiện có" đối chiếu `routing2/sumo_env.py` và `routing2/gnn_policy.py`. Thiết kế không phụ thuộc công cụ mô phỏng: nếu tự viết mô phỏng thì giữ nguyên giao diện này.

## 1. Bài toán một câu

Một nhà vận hành có một đội xe máy (cỡ đội: mục 3b) đang chạy giữa dòng xe nền không điều khiển được. Tại mỗi nút, hệ thống chọn cạnh kế tiếp cho từng xe trong đội, để giảm thời gian đi của đội và không làm hại dòng xe chung, nhất là trong các kịch bản xấu.

## 2. Các quyết định

| Câu hỏi | Chốt đề xuất | Code hiện có |
|---|---|---|
| Ai điều phối | Máy chủ của nhà vận hành. Một chính sách dùng chung, gọi riêng cho từng xe | Có |
| Khi nào quyết định | Theo sự kiện, bất đồng bộ: khi xe xuất phát hoặc sắp hết cạnh (cách cuối cạnh ≤ 10 m hoặc ≤ 3 s) | `decide_ahead_*` |
| Đồng bộ thời gian | Xe báo về theo chu kỳ 10 s (có mất mẫu 20%, sai số 10%). Mọi quyết định trong một chu kỳ dùng cùng ảnh chụp trạng thái | `live_every_s`, `fleet_snapshot`, `report_drop/noise` |
| Xử lý nhiều xe cùng lúc | Xét lần lượt theo thứ tự ngẫu nhiên trong cùng bước; xe sau thấy **ý định** của xe trước. Đây là cơ chế phối hợp | `_intent`, `FEAT_INTENT` |
| Đầu ra | Một cạnh ra, trong các cạnh không vượt ngưỡng đi vòng | `max_detour` |
| Tài xế | Làm theo với xác suất c, giảm khi đường đề xuất xa hơn; c được quét | `compliance*` |
| Xe thấy gì | 8 đặc trưng cho mỗi cạnh ra: thời gian tự do, thời gian gần đây, số xe đội, thời gian còn lại, chiều dài, ý định, thời gian còn lại theo trạng thái hiện tại, tải đội phía trước. Trạng thái mạng: tắc theo báo cáo, tải đội. Tĩnh: có phải hẻm, chiều dài | `N_FEAT = 8`, `_edge_state` |
| Xe không được thấy | Số xe nền thật, pha đèn, tốc độ thật, tai nạn chưa báo | Critic mới thấy, và chỉ lúc train |
| Critic | Tập trung, chỉ dùng khi train, thấy mật độ và tốc độ thật | `critic_gnn` |
| Công bằng | ff, app, greedy, MAPPO, IPPO dùng cùng thông tin và cùng tập episode | Có |

## 3. Hai điểm phải sửa trong định nghĩa

**a) Nguồn thông tin giao thông.** 100–200 xe trên 3888 cạnh nên phần lớn cạnh không có báo cáo mới. Một nhà vận hành thật còn mua được dữ liệu giao thông đường lớn. Đề xuất hai lớp, mọi chính sách đều được dùng:
1. Tốc độ đường lớn từ nguồn ngoài, kiểu Mapbox/Google, cập nhật khoảng 5 phút, có sai số, không có trong hẻm.
2. Báo cáo của đội xe, kể cả trong hẻm.

Code hiện chỉ có lớp 2 (`live_source="probe"`).

**b) Cỡ đội xe là biến được quét** (người dùng 2026-11-09: 100–200 chỉ là số ước tính, đổi được). Các mức: 100–200 xe (dưới 1% lưu lượng), 2%, 5%, 10%. Giá trị dùng để train chốt sau G2, theo mức mà đội xe bắt đầu ảnh hưởng tới tắc. Với đội nhỏ nhất:
- Đội xe không làm thay đổi tắc trên đường lớn. Phối hợp chỉ có tác dụng ở nơi đội xe chiếm phần đáng kể của sức chứa: **hẻm thông hẹp** và các điểm đội xe dồn về cùng lúc.
- Chỉ tiêu chính nên là **T_cust** và CVaR25 của đội. T_all dùng để kiểm tra đội xe không gây hại.
- Đội phải tập trung theo không gian và thời gian (ví dụ cùng khu vực trong 20–30 phút) thì mới có chuyện phối hợp. Bộ kịch bản phải có đặc điểm này.
- Trọng số J = 0.5·T_all + 0.5·T_cust không còn hợp: T_all gần như không đổi nên làm loãng khác biệt.

## 4. Chỉ tiêu

- Chính: T_cust trung bình, CVaR25 của T_cust (25% episode xấu nhất), tỉ lệ xe đội không hoàn thành.
- Ràng buộc: T_other (xe nền) không tăng quá 0.5%; thời gian chờ trong hẻm.
- Cơ chế: entropy cách chia đội giữa các đường, số lần đổi đường, tỉ lệ quãng đường đi hẻm.

## 5. Episode

- Khung giờ lấy từ hồ sơ theo giờ đã hiệu chỉnh (5–21h); xe nền chạy trước để mạng có trạng thái thật (làm nóng).
- Đội xe xuất phát trong 20–30 phút, mỗi xe một cặp điểm theo bộ kịch bản.
- Episode kết thúc khi đội tới đích hoặc hết thời gian tối đa.
- Không dùng tỉ lệ tới đích tại mốc cố định làm chỉ số (bị cắt theo thời gian kết thúc: ngay lúc vắng cũng chỉ 0.87).

## 6. Giả thuyết cần kiểm (chưa phải kết quả)

1. Greedy_load mạnh ở đa số kịch bản.
2. Khi đội tập trung và hẻm thông hẹp, chọn đường tham lam dồn xe vào hẻm; phối hợp giảm được.
3. MAPPO ổn định hơn ở kịch bản xấu.

Mỗi giả thuyết được kiểm ở giai đoạn 3, sau cổng G2.
