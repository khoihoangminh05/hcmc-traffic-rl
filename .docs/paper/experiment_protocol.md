# Giao thức thí nghiệm (nháp 2026-11-04, chốt trước khi chạy kết quả chính)

Viết trước để không chọn cách báo cáo sau khi thấy số. Mọi thay đổi sau khi chốt phải ghi ngày và lý do. Số liệu chưa chạy; mục "chưa chốt" cần người dùng duyệt.

## 1. Câu hỏi và giả thuyết
- **H1:** policy học có J thấp hơn baseline tốt nhất, chọn trên seed 50000+, trên seed 60000+.
- **H2:** lợi ích đổi theo p, tuân thủ và mức báo cáo, và các yếu tố này có tương tác.
- **H3:** reward `attrib` hơn `selfish`. Chỉ giữ nếu cách chia công qua kiểm chứng phản thực (mục 6).
- **H4:** tác động lên hẻm: lợi ích không đến từ việc đẩy thêm tải vượt ngưỡng lên hẻm mà không báo cáo.
Kết quả "không hơn baseline" vẫn được báo cáo. Không đổi giả thuyết sau khi thấy kết quả.

## 2. Tách seed
| Việc | Seed |
|---|---|
| Train | từ 1001 tăng dần |
| Chọn checkpoint, chế độ argmax hay sample, tham số greedy | 50000–50007 |
| Báo cáo | 60000–60029, chỉ chạy một lần cho mỗi cấu hình đã chốt |
SUMO seed của lần báo cáo lấy theo seed cầu thay vì cố định 1, để kết quả bao gồm cả nhiễu tài xế.

## 3. Controller
Dùng chung môi trường, chung lịch sự cố, chung giới hạn thông tin, chung `max_detour`:
- `ff`, `app` (đổi ở mọi nút), `app_chan` (kiểm tra mỗi T s, đổi khi lợi ≥ X s và Y%; chọn T, X, Y trên seed 50000+), `greedy` (q chọn trên seed 50000+).
- `dso`: bộ tuyến tốt nhất từ `gate_msa` có ngoại ứng ngã nhập, làm mốc, ghi rõ là tĩnh và có thông tin hoàn hảo về cầu.
- MARL: `selfish`, `attrib` nếu qua mục 6, nhánh rẻ `selfish + β(f − F)` để đối chiếu, MLP không GNN cho ablation.
Không được chỉnh baseline theo seed báo cáo. Mọi luật chung mới phải đo tác động lên baseline trước.

## 4. Kịch bản
**Chính (giai thừa):** cầu {8000, 10000} chuyến/giờ × p {0.1, 0.25, 0.5, 0.75, 1.0} × tuân thủ {0.7, 0.9, 1.0} × mất báo cáo {0, 0.2, 0.5}. Với controller không học, chỉ p và tuân thủ làm đổi kết quả khi thông tin đổi. 
**Độ nhạy (một lần đổi một tham số, trên policy đã chốt):** teleport {300, 600, tắt kèm trần thời gian}; bề rộng và số chiều của hẻm; `jmTimegapMinor`, `impatience`, `minGap`, `accel`, `sigma`, `minGapLat` theo `group6_moto_calib.md`; hình dạng cầu (hot share, số vùng); tỉ lệ sự cố; w ∈ {0.25, 0.5, 0.75}.
Cầu là tổng hợp: báo cáo như vậy, kèm chỉ số tắc nghẽn và so tốc độ trung bình theo giờ với Mapbox để cho thấy dải có hợp lý không.

## 5. Chỉ số và thống kê
- Chính: J, T_all, T_cust. Phụ: p95, tỉ lệ tới đích, teleport trên 1000 chuyến theo nguyên nhân, trễ xe không phải khách (T_other), km, lưu lượng trên hẻm và số hẻm vượt ngưỡng, độ dao động theo thời gian.
- Đơn vị độc lập là seed cầu. Khoảng tin cậy bootstrap ghép cặp 95% (`eval_heldout.paired_gain`), kèm tỉ lệ seed thắng.
- So sánh chính được hiệu chỉnh Holm trên toàn bộ cặp policy × baseline khai báo trước. Không chọn baseline yếu nhất để so.
- Báo cáo mọi run, kể cả hỏng. Nhiều seed train cho mỗi cấu hình (≥ 5 cho phương pháp chính, ≥ 3 cho ablation), không chỉ nhiều seed đánh giá. Hiện mỗi cấu hình mới có 1 seed train: đây là lỗ hổng lớn nhất nếu bài chỉ dùng một run.

**Độ mạnh, ước lượng thô.** `diag_v6`: sai số chuẩn 1.5% trên 48 cặp kịch bản, tức độ lệch khoảng 10.4% mỗi cặp (tính lại, coi các cặp độc lập, điều này lạc quan vì 6 kịch bản dùng chung seed). Số cặp cần để phát hiện gain δ với lực 80%:
| δ | α = 0.05 | α = 0.05/6 (Holm, trường hợp xấu nhất) |
|---|---|---|
| 2% | 212 | 327 |
| 3% | 94 | 145 |
| 5% | 34 | 52 |
30 seed × 6 kịch bản = 180 cặp đủ cho 3%, chưa đủ cho 2%. **Phải đo lại phương sai ở mức seed trước khi chốt số seed.**

## 6. Kiểm chứng chia công (điều kiện để giữ `attrib`)
Giữ nguyên seed SUMO; đổi hành động hoặc bỏ nhóm xe, đo ΔJ thật; hồi quy theo tổng phí. Đo sàn nhiễu bằng cách lặp với nhóm ngẫu nhiên không bị tính phí. Kiểm riêng ở nút có ưu tiên, nơi thứ tự hàng đợi không phản ánh nhân quả (Psarou 2510.11410 p.4, p.6). Báo cáo cả khi không đạt.

## 7. Tái lập
Lưu cho mỗi run: commit và trạng thái sạch của cây code, hash mạng SUMO và đồ thị, phiên bản SUMO, toàn bộ tham số. Công bố code, mạng, cấu hình, seed. Dữ liệu Mapbox tùy điều khoản (xem `reviewer_qa.md`).

## Chưa chốt, cần người dùng duyệt
Dải cầu và p ở mục 4; teleport chính (đề xuất 600 s); số seed train; có dùng baseline `dso` hay không.
