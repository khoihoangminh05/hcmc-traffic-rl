# Các quyết định đã chốt thay người dùng (2026-11-05)

Người dùng ủy quyền: "có gì hợp lý thì bạn chốt luôn hộ tôi". Mỗi dòng có lý do và điều kiện đảo lại. Không dòng nào thay đổi chuỗi run đang chạy. Người dùng đổi được bất kỳ dòng nào.

| # | Quyết định | Lý do | Đảo lại khi |
|---|---|---|---|
| D1 | Teleport chính 300 s (mặc định SUMO, như v7). Bắt buộc báo thêm 600 s, và teleport tách theo nguyên nhân | Mốc không do mình tự chọn; 180 s đã bỏ vì giải phóng tắc | Kết quả 300 s và 600 s trái dấu: khi đó không kết luận gì về thứ hạng |
| D2 | Kịch bản chính: cầu {8000, 10000} × p {0.1, 0.25, 0.5, 0.75, 1.0} ở giới hạn mặc định, 30 seed. Tương tác: cầu 2 mức × p {0.25, 0.75} × tuân thủ {0.7, 0.9, 1.0} × mất báo cáo {0, 0.2, 0.5}, 10 seed | Giai thừa đầy đủ 90 kịch bản × 30 seed quá tốn mà tương tác chỉ cần phát hiện có hay không | Đo lại phương sai mức seed cho thấy thiếu lực |
| D3 | 5 seed train cho phương pháp chính, 3 cho mỗi ablation | Một run không đủ làm bằng chứng. URB và Yu đều báo nhiều seed | Hết ngân sách máy: báo rõ số thực tế |
| D4 | Có mốc `dso`, ghi rõ tĩnh và biết trước cầu | Yun có DSO-Iterative; cần biết còn bao nhiêu khoảng trống | `gate_msa` không tốt hơn baseline: báo là mốc không hữu ích |
| D5 | Train tuân thủ 0.9, test {0.7, 0.9, 1.0} | Kim đo khoảng 68–73% với ô tô, nhưng xe máy có thể khác, nên chưa đổi mặc định | Có số đo cho xe máy |
| D6 | `attrib` chỉ là đóng góp nếu qua kiểm chứng phản thực trong protocol mục 6. Chọn reward chính trên seed 50000+, không nhìn seed báo cáo | Chưa có bằng chứng; có lý do cụ thể để nghi (`code_review.md` A3, A4) | |
| D7 | Bề rộng hẻm: xem mục dưới | | |
| D8 | Đích: TR-C trước, T-ITS dự phòng. Viết bài nghiên cứu trước, không viết survey | Ghi chú của Grok cũng khuyên vậy, và TR-C đòi tác giả overview có thành tích | |
| D9 | Không dùng Google Routes API (cần billing). Gán nhãn hẻm qua xem ảnh đường phố; nếu không có ảnh thì chỉ quét | Người dùng không nạp tiền; không bài nào cho số hẻm | Có nguồn số đo mở |
| D10 | Không công bố dữ liệu Mapbox thô. Công bố code, mạng, cấu hình, seed và tham số dẫn xuất, sau khi Mapbox trả lời | Trang công khai không có điều khoản rõ | Mapbox cho phép bằng văn bản |
| D11 | Báo cáo argmax hay sample chọn trên seed 50000+; v7 đang chọn argmax | Tránh chọn trên seed báo cáo | |
| D12 | Việc tay chân giao Grok theo `.docs/GROK_TASKS.md`; mọi nhãn Grok điền phải được kiểm mẫu trước khi dùng | Người dùng không làm tay; AI đọc ảnh có thể sai | |

## D7. Bề rộng hẻm: đây là giả định bậc nhất, không phải chi tiết phụ

Đo local (`ml-core/artifacts/out/quan4/routing2_review/width/`): SUMO 1.28, 8000 chuyến/giờ, p = 0.5, teleport 300 s, horizon 1500 + 300, giới hạn thực tế mặc định, **2 seed cầu**, nên chỉ là chỉ báo. J trung bình (s):

| Bề rộng mỗi chiều | ff | app | Tới đích ff / app | Teleport/1000 ff / app |
|---|---|---|---|---|
| 2.5 m (hiện tại) | 380.0 | 401.6 | 1.00 / 1.00 | 6.4 / 5.2 |
| 1.75 m | 741.2 | 553.6 | 0.76 / 0.92 | 22.9 / 12.0 |
| 1.25 m | 501.0 | 430.4 | 0.94 / 1.00 | 3.0 / 1.9 |

- J của ff đổi gần gấp đôi theo giả định này. **Chiều so sánh còn đảo**: ở 2.5 m app kém ff, ở hẹp hơn app hơn ff. Nhận định "ba baseline trùng nhau" chỉ đúng ở 2.5 m, nên chưa thể coi là tính chất của mạng hẻm.
- Không đơn điệu: 1.75 m tệ hơn 1.25 m. Nghi là do mô hình sublane: 1.75 m gần đủ cho hai xe nên xe chen rồi kẹt, 1.25 m là đi một hàng. Chưa kiểm chứng; có thể là tác dụng của độ phân giải ngang 0.8 m. Đang đo lại với 0.4 m.

**Nhãn Grok (2026-11-05, `.docs/results_alley/alley_width_sample.csv`):** 17/50 hẻm có nhãn bề rộng từ ảnh Street View: < 2 m: 3; 2–3 m: 11; 3–4 m: 1; > 4 m: 2. `two_way` không xác định được ở cả 50 hẻm. Theo tag OSM: `highway=service` (1298 cạnh hẻm): 14 nhãn, toàn ≤ 4 m, 13 nhãn ≤ 3 m; `highway=residential` (162 cạnh): 2 nhãn, đều > 4 m.

Hạn chế, phải nêu trong bài: chỉ 34% có nhãn, mới gán các nơi có ảnh; 15/20 ảnh từ 2020; ước lượng bằng mắt theo nhóm, nhiều dòng ghi "rough" hoặc chưa xác minh khoảng cách tới đúng cạnh; không phải số đo. Mình kiểm tra 3 ảnh Grok lưu: 412 (< 2 m) hợp lý; Hẻm 76 (> 4 m) đúng, có ô tô đỗ; Hẻm 884 (< 2 m) có thể đã ở mức 2–3 m, không có vật so sánh. Không dùng `alley_width_interpolated.csv`: Grok tự suy từ hẻm cùng tên cách tới 194 m, không phải quan sát.

**Chốt:** v7 giữ nguyên 2.5 m để trọn chuỗi. Chuỗi sau:
1. Cạnh `highway=service`: **1.25 m mỗi chiều**, tức hẻm 2.5 m, nằm trong nhóm phổ biến nhất 2–3 m.
2. Cạnh `highway=residential` trong lớp hẻm: 2.5 m mỗi chiều, **tạm thời**, vì mới có 2 nhãn. Đang gán thêm (`alley_width_sample2.csv`, Việc 1b).
3. Độ nhạy bắt buộc: toàn bộ hẻm 2.5 m và 1.75 m mỗi chiều. Kết quả chính nêu thứ hạng controller theo từng trường hợp.
Giả định hai chiều mỗi hẻm là từ OSM, chưa kiểm được.
Đảo lại khi: có số đo; hoặc nhóm residential cho nhãn khác; hoặc các lần đo 0.4 m cho thấy 1.25 m cũng là tác dụng của độ phân giải.
