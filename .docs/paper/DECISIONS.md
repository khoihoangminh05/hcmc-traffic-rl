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
| D10 | Không công bố dữ liệu Mapbox thô. Công bố code, mạng, cấu hình, seed và tham số dẫn xuất, sau khi Mapbox trả lời. Email chưa gửi (người dùng giữ lại, 2026-11-05): chỉ cần gửi nếu bản nộp dùng số dẫn xuất từ Mapbox, và khi đó gửi trước lúc nộp ít nhất vài tuần | Trang công khai không có điều khoản rõ | Mapbox cho phép bằng văn bản |
| D11 | Báo cáo argmax hay sample chọn trên seed 50000+; v7 đang chọn argmax | Tránh chọn trên seed báo cáo | |
| D12 | Việc tay chân giao Grok theo `.docs/GROK_TASKS.md`; mọi nhãn Grok điền phải được kiểm mẫu trước khi dùng | Người dùng không làm tay; AI đọc ảnh có thể sai | |
| D13 | Bài báo trình bày là **phương pháp và cơ chế cho mạng thứ cấp dày đặc**, Quận 4 là mạng thử chứ không phải chủ đề. Thêm phép thử ngoài: giữ nguyên policy đã train, không train lại, đánh giá trên ít nhất một mạng khác dựng từ OSM cùng quy trình. Ứng viên: Bình Thạnh hoặc Quận 8 (TP.HCM, dễ kiểm), Tambora (Jakarta, khác thành phố). Mỗi mạng mới ghi rõ là không hiệu chỉnh và không có nhãn bề rộng | Reviewer sẽ hỏi kết quả có chỉ đúng cho Quận 4 không. Đếm OSM cùng ô 0.02° × 0.02°: Quận 4 1541 đường loại service/residential/living_street, Bình Thạnh 1625, Quận 8 1361, Tambora 1822, Tondo 848 (chỉ đếm số đường, chưa kiểm chất lượng) | Policy không chạy được trên mạng khác về kỹ thuật: khi đó báo là train riêng từng mạng; kết quả xấu vẫn báo |
| D14 | Cho phép khởi động ấm bằng bắt chước: mạng bắt đầu đúng như `greedy` q = 0.5. Bài báo phải nêu rõ | Người dùng xác nhận với session train ngày 2026-11-05, theo lời session đó chép lại: "khởi đầu bằng cách bắt chước là chuyện tốt, tôi có cấm đâu". `CLAUDE.md` còn dòng cũ, chưa sửa | Người dùng đổi ý; hoặc ablation cho thấy kết quả chỉ là bản sao của `greedy` |
| D15 | Thêm đội 100–200 xe và bộ kịch bản khó khai thác từ thời gian đứng đo được trên từng cạnh (`routing2/scenarios.py`, seed 40000–40007, dưới `ff`). Bộ này là bộ căng thẳng công khai, báo cạnh cầu thường, **không thay thế** kịch bản chính D2. Khai thác và đánh giá phải trên seed khác nhau | Người dùng yêu cầu, theo session train (2026-11-05). Số đầu, chưa phải kết quả MARL: 1.25 m, 0.4 m, đội 5%, 8 seed: đứng 10834 xe·s ở 5000 chuyến/giờ, 102811 ở 8000; 10 cạnh đầu giữ 52% thời gian chờ; 92% trong 60 cạnh đầu là hẻm. Kịch bản trường học chọn theo hình học đã bỏ: oracle chia 25–75% đội quanh hẻm được ưu tiên thua `ff` 0.4–2.5% ở 5000 chuyến/giờ. Thiên lệch do chọn theo `ff` đã kiểm: top 20 cạnh trùng ff–app 19, ff–greedy 19, app–greedy 20; điểm nóng cuối lấy trung bình cả ba, bỏ số khai thác chỉ theo `ff`. Khai thác vẫn phải tách seed với đánh giá để tránh hồi quy về trung bình. Oracle chia đội tĩnh quanh một cạnh (300 chuyến, 4 seed) so với tốt nhất của ff, app, greedy: −3.5 đến +1.8%, **không phải cận trên**; thông tin sống có tác dụng rõ (8000 chuyến/giờ, một điểm: app 665.2, ff 744.4). Greedy q vẫn 0.5; phải tinh chỉnh trên 40000–40007 trước số cuối, và so với baseline tốt nhất đã tinh chỉnh | Lợi ích chỉ xuất hiện trên bộ khai thác: báo rõ là không tổng quát; khai thác lại theo `app` cho thứ tự khác: báo cả hai |

## D7. Bề rộng hẻm: đây là giả định bậc nhất, không phải chi tiết phụ

Đo local (`ml-core/artifacts/out/quan4/routing2_review/width/`): SUMO 1.28, 8000 chuyến/giờ, p = 0.5, teleport 300 s, horizon 1500 + 300, giới hạn thực tế mặc định, **2 seed cầu**, nên chỉ là chỉ báo. J trung bình (s):

| Bề rộng mỗi chiều | ff | app | Tới đích ff / app | Teleport/1000 ff / app |
|---|---|---|---|---|
| 2.5 m (hiện tại) | 380.0 | 401.6 | 1.00 / 1.00 | 6.4 / 5.2 |
| 1.75 m | 741.2 | 553.6 | 0.76 / 0.92 | 22.9 / 12.0 |
| 1.25 m | 501.0 | 430.4 | 0.94 / 1.00 | 3.0 / 1.9 |

**Đính chính (cùng ngày).** Chạy lại ở độ phân giải ngang 0.4 m, 2 seed: 1.25 m: ff 413.5, app 428.4; 1.75 m: ff 499.5, app 506.5. Ở cả hai, `ff` lại nhỉnh hơn `app`, nên câu "thứ tự baseline đảo theo bề rộng" **không còn đứng vững** và đã rút lại. Trong cùng một cấu hình, có seed J khoảng 390, có seed khoảng 610–650 với chỉ 74–77% xe tới đích, tức có hiện tượng tắc lan hẳn xảy ra hoặc không: **2 seed không đủ để so**. Điều chắc hơn: bề rộng và độ phân giải ngang đều làm đổi kết quả rõ rệt, nên phải quét. Đang chạy lại nhiều seed, đổi SUMO seed, tách teleport theo nguyên nhân (`routing2_review/width_multi`, 6 seed cầu 50010–50015, không trùng seed chọn mô hình).

**Đo nhiều seed (2026-11-05, `routing2_review/width_multi`, `width_multi2b`; công cụ `routing2/width_sweep.py`):** 6 seed cầu 50010–50015, SUMO seed theo seed cầu, cùng kịch bản trên. J trung bình (s), % là `app` so với `ff` ghép theo seed, kèm sai số chuẩn:

| Bề rộng mỗi chiều | Độ phân giải ngang | `ff` | `app` | `app` so với `ff` | `app` thắng | Tới đích ff / app | Teleport va chạm / quá hạn |
|---|---|---|---|---|---|---|---|
| 2.5 m | 0.8 m | 390.7 | 376.1 | −3.7% ± 3.0 | 4/6 | 1.00 / 1.00 | 70 / 34 |
| 2.5 m | 0.4 m | 422.1 | 421.1 | +1.0% ± 7.7 | 3/6 | 1.00 / 1.00 | 15 / 87 |
| 1.75 m | 0.8 m | 714.4 | 653.5 | −6.3% ± 9.4 | 4/6 | 0.79 / 0.85 | 6 / 334 |
| 1.75 m | 0.4 m | 560.8 | 598.8 | +10.5% ± 10.9 | 2/6 | 0.89 / 0.86 | 2 / 236 |
| 1.25 m | 0.8 m | 491.4 | 465.9 | −4.3% ± 5.3 | 3/6 | 1.00 / 0.99 | 2 / 49 |
| 1.25 m | 0.4 m | 447.4 | 416.2 | −6.1% ± 4.8 | 4/6 | 0.98 / 1.00 | 18 / 35 |

Rút ra:
1. **Không ô nào phân định được `ff` và `app`.** Thứ tự đổi dấu giữa các ô đều nằm trong sai số.
2. **Bề rộng không đơn điệu, kể cả ở 0.4 m.** So với 2.5 m ở 0.4 m: 1.75 m tệ hơn +35.9% ± 16.3 (`ff`), +42.9% ± 7.9 (`app`); 1.25 m gần như bằng: +6.9% ± 6.3, −0.4% ± 3.8. Giả thuyết "1.75 m tệ chỉ do độ phân giải 0.8 m" **đã bị bác**. Nguyên nhân **vẫn chưa biết**, xem mục "Điều tra 1.75 m" dưới. Vì thế tiêu đề "giả định bậc nhất" vẫn đúng.
3. **Độ phân giải 0.8 m tạo va chạm giả ở 2.5 m:** teleport do va chạm 70 xuống 15 khi sang 0.4 m. Xe rộng 0.8 m bằng đúng một làn con. Thời gian chạy 0.4 m không cao hơn đáng kể (khoảng 825–1119 s so với 830–1066 s mỗi episode). **Chuỗi sau dùng 0.4 m.** Đang kiểm hội tụ ở 0.2 m (`width_res02`); 0.8 m giữ làm độ nhạy.
4. 1.75 m mỗi chiều tương ứng hẻm 3.5 m, nhóm chỉ có 2/39 nhãn; 2.5 m mỗi chiều tương ứng hẻm 5 m, cũng chỉ có 2/39 (> 4 m). Nghĩa là v6, v7 đang chạy trên hẻm rộng hơn hầu hết hẻm thật.

**Hội tụ độ phân giải (`routing2_review/width_res02`, 1.25 m, cùng 6 seed, 12 run):** 0.2 so với 0.4 m: `ff` −3.6% ± 6.5 (426.6 so với 447.4); `app` +10.0% ± 3.4 (458.7 so với 416.2). `app` so với `ff` ở 0.2 m: +8.1% ± 6.1, thắng 2/6, trong khi ở 0.4 m là −6.1% ± 4.8. **0.4 m chưa được chứng minh đã hội tụ**: mức J của `ff` nằm trong nhiễu, nhưng `app` lệch rõ và thứ tự hai baseline có thể đổi. Thời gian 0.2 m khoảng 1.7 lần (máy đang chạy kèm việc khác, nên chỉ là ước lượng). **Chốt:** train ở 0.4 m vì chi phí; đánh giá cuối phải chạy thêm ở 0.2 m với mọi controller, và chỉ gọi là kết quả vững nếu thứ hạng giữ nguyên ở cả hai.

**Trạng thái chuỗi train (session train, 2026-11-05):** v9 chạy từ 20:49 trên 1.25 m, 0.4 m, commit a059d2a, net sha da8da1aa66d0fcbb, seed 42, **trước khi hai điều kiện được kiểm** (hội tụ 0.2 m, nguyên nhân 1.75 m), nên có thể phải chạy lại. Tinh chỉnh seed 40000–40007, 32 episode mỗi mức trên mạng này: `ff` 537.59, `app` 543.35, `greedy` q 0.25 / 0.5 / 1 / 2 / 4 = 559.13 / 532.74 / 586.20 / 713.92 / 773.11. Lưới `app_ext` đầy đủ chưa chạy trên mạng này.

**Điều tra 1.75 m (2026-11-05, chỉ `ff`, 0.4 m, seed 70000+, code 67378b2; `routing2/width_cell.py`, `routing2/width_diag.py`):**
- J theo bề rộng, seed 70000–70003: 1.25 m 380.1; 1.5 m 374.9; 1.75 m 435.9; 2.0 m 389.2; 2.5 m 365.5. Teleport/1000: 0.8; 0.2; 5.2; 6.0; 1.9. Sáu seed (70000, 70001, 70004–70007) ở 1.75 m: J 541.6, sd 83.7, tới đích 0.76–1.00.
- Kẹt cục bộ: 75/102 teleport ở 1.75 m nằm tại ngã tư toàn hẻm 5778362217 và nút kề 366380708, gồm cả xe kẹt trong hai nhánh đi thẳng ngược chiều.
- **Đã bác:** do va chạm (101/102 là quá hạn); do năng lực một nhánh và chen ngang trên đoạn thẳng (lưu lượng bão hòa khoảng 2350 xe/giờ như nhau ở 1.25–1.75 m, tỉ lệ ngang hàng 0); do luật nhường đường (thay toàn bộ dòng `request` của mạng 1.75 m bằng của 1.25 m: +4.9% ± 4.5, không đổi ở 4/6 seed; chiều ngược lại trên mạng 1.25 m vẫn J 389.8, tới đích 1.00); do tự do vị trí ngang (`latAlignment=center` ở 1.75 m: −2.7% ± 7.6, vẫn kẹt).
- **Chưa kiểm:** hình học nút khác theo bề rộng (nhánh trong nút dài hơn: 5.5 m ở 1.25 m, 6.5 m ở 1.75 m). Đây chỉ là ứng viên còn lại, chưa có bằng chứng.
- Với mạng 1.25 m: cùng cấu hình không thấy kẹt ở ngã tư này (0 teleport ở đó trên 4 seed). Nhưng 1.25 m vẫn có seed tắc (50012 ở 0.4 m, 50010 ở 0.2 m, `ff`, tới đích 0.85–0.87), không ghi vị trí nên **không loại trừ được cùng cơ chế**. Mạng đồ chơi: đường 3.2 m đổ vào hẻm 1.25 m chỉ 1380 xe/giờ, có 7 teleport trên 2 seed, không thấy trên mạng thật với `ff`; policy đẩy nhiều xe từ đường vào hẻm hơn có thể chạm phải, nên phải theo dõi khi đánh giá.
- **Cập nhật từ session train:** ngã tư 5778362217 là **nút cổ chai đang hoạt động ở 1.25 m**, không phải "không liên quan". Seed 40000–40007, 16 episode mỗi controller, 5000 và 8000 chuyến/giờ, p 0.15, dưới `ff`, `app`, `greedy` q 0.5: cạnh 366369352→5778362217 (hẻm, 77.3 m) là điểm nóng 1/6; thời gian đứng cộng dồn 16251 xe·s tại 5778362217, 8095 xe·s tại 366380708. Đây là thời gian đứng, không phải teleport, nên **chưa nói được đây là cùng cơ chế với 1.75 m**. Hệ quả: bộ kịch bản khó xoay quanh đúng một nút có hành vi theo bề rộng chưa giải thích được, nên phải nêu rõ.
- **Kết luận:** nêu là mối đe dọa còn mở trong bài. Bảng độ nhạy trình bày cả 1.75 m với ghi chú này; không dùng 1.75 m để rút ra kết luận về bề rộng thật.

**Nhãn Grok (2026-11-05, `.docs/results_alley/alley_width_sample.csv`):** 17/50 hẻm có nhãn bề rộng từ ảnh Street View: < 2 m: 3; 2–3 m: 11; 3–4 m: 1; > 4 m: 2. `two_way` không xác định được ở cả 50 hẻm. Theo tag OSM: `highway=service` (1298 cạnh hẻm): 15 nhãn, toàn ≤ 4 m, 14 nhãn ≤ 3 m; `highway=residential` (162 cạnh): 2 nhãn, đều > 4 m.

Hạn chế, phải nêu trong bài: chỉ 34% có nhãn, mới gán các nơi có ảnh; 15/20 ảnh từ 2020; ước lượng bằng mắt theo nhóm, nhiều dòng ghi "rough" hoặc chưa xác minh khoảng cách tới đúng cạnh; không phải số đo. Mình kiểm tra 3 ảnh Grok lưu: 412 (< 2 m) hợp lý; Hẻm 76 (> 4 m) đúng, có ô tô đỗ; Hẻm 884 (< 2 m) có thể đã ở mức 2–3 m, không có vật so sánh. Không dùng `alley_width_interpolated.csv`: Grok tự suy từ hẻm cùng tên cách tới 194 m, không phải quan sát.

**Nhãn đợt 2 (2026-11-05, `.docs/results_alley/alley_width_sample2.csv`):** 22/40 hẻm có nhãn: `highway=residential` 16 nhãn (2–3 m: 15; 3–4 m: 1), `highway=service` 6 nhãn (< 2 m: 1; 2–3 m: 5). Cộng hai đợt 39/90 nhãn: < 2 m: 4; 2–3 m: 31; 3–4 m: 2; > 4 m: 2. Theo tag: `service` 21 nhãn (< 2 m: 4; 2–3 m: 16; 3–4 m: 1); `residential` 18 nhãn (2–3 m: 15; 3–4 m: 1; > 4 m: 2). Hai nhãn > 4 m đợt 1 hóa ra là ngoại lệ, không phải đặc trưng của tag, nên **tách bề rộng theo tag không còn lý do**.

Kiểm đợt 2: mọi dòng giữ nguyên id và thứ tự, các cột gốc không đổi, không trùng hẻm với đợt 1, mỗi nhãn đều ghi năm ảnh, vật so sánh và khoảng cách. Đã đối chiếu nhãn với ghi chú; **chưa tự xem ảnh đợt này**. Hạn chế thêm: 14/16 nhãn residential nằm ở 3 hẻm cùng trục Đoàn Văn Bơ (500, 538, 576), nên số nhãn độc lập ít hơn con số 39 và không đại diện cho cả quận; 11/22 ảnh từ 2020. `two_way = y` ở cả 22 dòng thực chất là "không thấy biển một chiều", không phải quan sát xe đi hai chiều, và 5 dòng có biển tròn không đọc được: giả định hai chiều chưa bị bác, nhưng cũng chưa được xác nhận. 20/22 dòng có xe đỗ hoặc hàng quán chiếm mặt đường, nên bề rộng hữu dụng nhỏ hơn bề rộng tường tới tường; mô hình chưa tính phần này.

**Chốt:** v7 giữ nguyên 2.5 m để trọn chuỗi. Chuỗi sau:
1. **Toàn bộ cạnh hẻm 1.25 m mỗi chiều**, tức hẻm 2.5 m, thuộc nhóm 2–3 m chiếm 31/39 nhãn. Không tách theo tag.
2. Độ nhạy bắt buộc: toàn bộ hẻm 2.5 m và 1.75 m mỗi chiều. Kết quả chính nêu thứ hạng controller theo từng trường hợp.
Giả định hai chiều mỗi hẻm là từ OSM, chưa kiểm được.
Việc còn mở: tìm nguyên nhân 1.75 m tệ (xem kẹt ở đâu, chen ngang có phải lý do không), vì reviewer sẽ hỏi nếu bảng độ nhạy không đơn điệu.
Đảo lại khi: có số đo; hoặc kiểm tra 0.2 m cho thấy 1.25 m chưa hội tụ ở 0.4 m.
