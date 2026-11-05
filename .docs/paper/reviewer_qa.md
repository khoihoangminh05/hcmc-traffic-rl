# Câu reviewer sẽ hỏi và trạng thái trả lời (2026-11-04)

✅ có câu trả lời. 🟡 có một phần. 🔴 chưa có, phải làm trước khi nộp. Xếp theo mức nguy hiểm.

| # | Câu hỏi | Trạng thái | Trả lời hoặc việc cần làm |
|---|---|---|---|
| 1 | Nhu cầu tổng hợp, sao tin được? | 🔴 | Báo là tổng hợp, quét dạng cầu. Cần đối chiếu hồ sơ tốc độ Mapbox và đo độ nhạy theo cầu (`experiment_protocol` mục 4) |
| 2 | Mô hình hẻm đã kiểm chứng chưa? | 🔴 | Chưa, và đây là giả định bậc nhất: đổi bề rộng làm đảo thứ tự baseline (`DECISIONS.md` D7). OSM 0/1460 có width; footprint nhà chỉ cho 2/730 hẻm. Cần gán nhãn mẫu 50 hẻm (`.docs/alley_width_sample.csv`), quay video nếu được. Phải viết rõ: chưa hiệu chỉnh hành vi trong hẻm |
| 3 | Kết quả có phụ thuộc teleport không? | 🔴 | Có, thứ hạng đổi; teleport còn gộp cả va chạm (`code_review.md` A1). Kết quả chính ở 600 s trở lên, báo theo nguyên nhân |
| 4 | Một seed train có đủ không? | 🔴 | Không. ≥ 5 seed train cho phương pháp chính |
| 5 | Sao không dùng tối ưu tập trung hoặc Frank–Wolfe? | 🟡 | Vì cần biết cầu và không phản ứng online. Cần số: mốc `dso` để cho thấy khoảng còn lại, và lý do mô phỏng động khác gán tĩnh |
| 6 | Baseline có bị làm yếu không? | 🟡 | Chung môi trường. Cần thêm app có ngưỡng kiểu Chan (p.8), vì `app` đổi ở mọi nút có thể bất lợi; tham số greedy chọn trên seed 50000+ |
| 7 | MARL hơn heuristic bao nhiêu, có phân biệt được không? | 🔴 | Chưa có kết quả seed báo cáo. Nhiễu chênh 3–4% trên 48 cặp |
| 8 | Chia công `attrib` có đúng không? | 🔴 | Chưa kiểm được; `code_review.md` mục 2. Không qua thì bỏ khỏi đóng góp |
| 9 | Điều gì mới so với Yun 2024, MA-GRL, Psarou? | 🟡 | `related_work.md` 2.7–2.8. Đọc đủ MA-GRL, chạy Scopus trước khi nộp |
| 10 | Thông tin cho actor có thực tế không? | ✅ | Chỉ báo cáo đội xe có mất và nhiễu, ý định do chính app biết, không biết p. Critic và reward dùng trạng thái thật chỉ khi train. Số mất, nhiễu là tự đặt, được quét |
| 11 | Tuân thủ 90% lấy từ đâu? | 🟡 | Tự đặt. Kim 2025 đo khoảng 68–73% theo link (ô tô), Fadilah 35.6% trong khảo sát. Quét 0.7–1.0, và train ở 0.9 test thấp hơn |
| 12 | Xe bị đẩy vào hẻm thì dân hẻm chịu gì? | 🟡 | Có đo được km; chưa báo tải theo hẻm. Kuncheria 2023 cho thấy SO có thể làm xấu tải đường dân cư |
| 13 | Người bị chọn đi đường dài hơn có chịu không? Công bằng? | 🔴 | Chưa đo phân phối lợi ích. Thêm T_cust theo nhóm, p95, tỉ lệ thiệt so với `app`. Michailidis 2026 về bất bình đẳng |
| 14 | Mạng GNN 3 lớp đủ thấy tắc không? | 🟡 | 3 bước trên line graph chỉ khoảng 3 cạnh, độ dài trung vị xem `code_review.md`. Có vector toàn mạng và thời gian sống. Cần ablation số lớp và MLP |
| 15 | Train ở simulator nào, sim-to-real? | 🟡 | Mọi kết quả trong SUMO, không claim triển khai. Đo độ bền theo tham số SUMO; chưa có kiểm chứng thực địa |
| 16 | Dữ liệu Mapbox có được công bố không? | 🔴 | Trang ToS và Product Terms đọc được không có điều khoản rõ về lưu kết quả Directions. Không công bố dữ liệu thô. Hỏi Mapbox bằng văn bản, hoặc chỉ công bố tham số dẫn xuất |
| 17 | Sao lấy w = 0.5? | 🟡 | Người dùng chốt, a và b suy từ J, không đặt tay. Quét w trong độ nhạy |
| 18 | Tần suất sự cố ở đâu ra? | 🟡 | Tự đặt, không đo được bằng dữ liệu miễn phí. Quét, gồm cả không sự cố |
| 19 | Có chuyển giao được không? | 🔴 | Chưa thử. Không claim. MA-GRL đã có 87% ở ba thành phố |
| 20 | Tái lập được không? | 🟡 | Có git, tham số. Chưa lưu hash mạng và phiên bản SUMO, xem `code_review.md` |
| 21 | Vì sao 8000–10000 chuyến/giờ? | 🟡 | Chọn theo chỉ số tắc 2.18–2.88, không theo số đếm thật. Phải nói thẳng |
| 22 | Vì sao không dừng trên đường hay hoãn khởi hành? | ✅ | Dừng trong hẻm gây chắn. Hoãn là hướng mở rộng |

## Những câu không được viết
"Đầu tiên" cho next-hop RL, không tuân thủ, gợi ý tuyến của nhà cung cấp, credit không chạy lại, mạng lớn nhất. "Đã hiệu chỉnh cho hẻm". "Mapbox đo thời gian thực" (live gần như trùng hồ sơ lịch sử).
