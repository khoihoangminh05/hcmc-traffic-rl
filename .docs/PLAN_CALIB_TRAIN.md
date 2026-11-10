> **Đã thay bằng `.docs/PLAN_FINAL.md` (2026-11-09).** Giữ lại để tra cứu.

# Kế hoạch triển khai: hiệu chỉnh mô phỏng → kiểm tra còn đất → train MAPPO (lập 2026-11-08)

Nguyên tắc:
- Mỗi bước có **cổng đạt** đo bằng số. Không qua cổng thì không sang bước sau. Nếu bỏ qua một bước, ghi lý do vào nhật ký cuối file.
- Mọi lần chạy ghi vào `.docs/AUDIT_SIM.md` hoặc `PLAN_V4.md`, kể cả lần thất bại.
- Code mới luôn tắt theo mặc định. Chạy test cũ trước khi dùng.
- Không sửa code giữa một loạt chạy. Bản code dùng để thử nằm ở `diag_v6/v14src`.

## Giai đoạn A: chọn mô hình xe (Chủ nhật 8/11 tối)

| Bước | Việc | Đầu ra | Cổng đạt |
|---|---|---|---|
| A1 | Micro với kiểu lái Việt Nam (`cal_vn`: polite / vn1 / vn2 × c20, c4, d14) | tới đích, teleport, ρ khúc 300 m, thời gian chạy | |
| A2 | So với meso 3 hàng xe máy (`cal_moto`, j1 new) | bảng so sánh | Chọn mô hình có tới đích ≥ 0.8 ở c4, ρ đường lớn cao nhất, thời gian mỗi episode ≤ 15 phút |
| A3 | Mở ảnh camera ở 5 cạnh mô phỏng nghẽn nhất (Chủ nhật; ngày thường làm lại ở C2) | ghi chú từng điểm | Có giải thích cho mỗi chỗ lệch |

## Giai đoạn B: thành phần xe và mức tắc (8–9/11)

| Bước | Việc | Cổng đạt |
|---|---|---|
| B1 | Thêm **ô tô nội quận** trong `make_demand_v2` (`internal_car_tph`): chỉ giữa các nút có đường ô tô đi được (kiểm bằng `car_ok`); không vào hẻm. Tham số tỉ lệ ô tô 10–35% | Tỉ lệ ô tô trên trục chính trong mô phỏng nằm trong 20–40%, hiệu chỉnh bằng đếm tay ảnh camera |
| B2 | Dò ngẫu nhiên khoảng 48 bộ: mức nội quận, luồng từng phía cổng, tỉ lệ ô tô, lớp tốc độ (a, k0; b = 1), trên mô hình đã chọn ở A2; 2 seed | |
| B3 | Chấm theo khúc 300 m (`calib/stretch.py`), tách nửa cal và test | **C1 đạt:** ρ toàn bộ ≥ 0.5 (test), đường lớn ≥ 0.4; TTI trung vị primary / secondary / tertiary lệch Mapbox ≤ 15% (1.67 / 1.47 / 1.33); tới đích ≥ 0.8; teleport ≤ 5 trên 1000 chuyến |
| B4 | Giữ 5 bộ tốt nhất làm **tập mô phỏng E** (`PREREG_SCENARIOS.md` §1) | |

Nếu B3 không đạt sau 2 vòng dò, ghi "C1 đạt một phần" kèm số đo, rồi đi tiếp với tập E tốt nhất (người dùng chấp nhận số liệu chưa hoàn hảo).

## Giai đoạn C: camera (9–11/11)

| Bước | Việc | Cổng đạt |
|---|---|---|
| C1 | Vẽ vùng mặt đường (ROI) cho 22 camera; `count_snapshots.py --roi` bỏ xe ngoài vùng | Đếm tay 30 ảnh ban ngày: sai số trung vị ≤ 30% |
| C2 | Đếm ảnh 16–19h thứ Hai đến thứ Tư. Tính tỉ lệ mật độ cao điểm / 10h trên từng camera, và tỉ lệ ô tô | |
| C3 | So với mô phỏng tại cạnh của mỗi camera (cùng tỉ lệ). Mở ảnh ở mọi điểm lệch lớn | ρ thứ hạng giữa camera ≥ 0.5; nếu không đạt, đưa tỉ lệ camera vào vòng dò B2 |

## Giai đoạn D: kiểm tra còn đất (sau B, khoảng 11/11)

| Bước | Việc | Cổng đạt |
|---|---|---|
| D1 | UE so với SO_x (`gate_msa --demand v3`) trên 2 bộ của tập E, đội xe 6000 và 9000, **6 seed** | |
| D2 | ff / app / greedy (queue_s 0.25–1) trên 20 seed, đội xe 3000 / 6000 / 9000: J, CVaR25, xác suất sụp, quãng đường đi hẻm | |
| D3 | Quyết định | Khoảng cách UE → tốt nhất biết được ≥ 5% ở trung bình, **hoặc** CVaR25 của greedy cách cận ≥ 5% → train MAPPO (E). Nếu < 3%: báo người dùng; bài đi theo hướng "ngang greedy_load, hơn hẳn app / ff, cộng pipeline và dữ liệu" |

## Giai đoạn E: train (sau D3)

| Bước | Việc | Ghi chú |
|---|---|---|
| E1 | Chốt `PREREG_SCENARIOS.md` (commit trước khi train) | 6 họ kịch bản, tập E, chỉ số, seed |
| E2 | Smoke + test cũ trên mô hình đã chọn | |
| E3 | MAPPO (reward attrib, khởi đầu từ greedy) **và** IPPO đối chứng, chạy song song | Mục tiêu ≤ 24 giờ: episode 1200–1500 s (làm nóng 600 s), 24 worker mỗi run, khoảng 150 update; ước lượng thời gian sau 2 update |
| E4 | Theo dõi mỗi 25 update: J, CVaR, sụp, so với greedy trên seed 50000+ | Dừng sớm nếu 75 update liên tiếp không cải thiện |
| E5 | `eval_heldout` seed 60000+, 20 seed mỗi (họ × bộ E) | Wilcoxon cặp đôi, khoảng tin cậy bootstrap |

## Nhật ký thay đổi kế hoạch

- 2026-11-08: lập kế hoạch.
- 2026-11-08 19h, **A xong**. Kết quả micro (`cal_vn`):
  - Kiểu lái "lịch sự": tới đích 0.85 / 0.83 / 0.74, teleport 50 / 68 / 324, ρ 0.24 / 0.01 / −0.01.
  - Kiểu lái Việt Nam (vn1, vn2: lcAssertive, minGapLat 0.05–0.1, jmIgnoreFoeProb 0.2–0.5): teleport 24–36 ở c20 và 224–233 ở d14; ρ ≤ 0.19; 1100–1900 s mỗi episode.
  - So với meso có kiểm soát nút + xe máy 3 hàng: 0.87 / 0.81 / 0.63, 0 teleport, ρ 0.51 / 0.37 / 0.39, 620–1500 s.
  - **Chọn mô hình: meso có kiểm soát nút, xe máy 3 hàng.**
- Song song đang chạy:
  - D1 sớm: `msa15`, UE so với SO_x, 6 seed, đội xe 6000, trên mô hình đã chọn.
  - D2 sớm: `k5`, ff / app / greedy 0.5 / greedy 1 trên 20 seed.
  - B2: `cal_b2`, 48 bộ, có ô tô nội quận (`make_demand_v2 internal_car_tph`, mặc định 0; kiểm tra nhu cầu mặc định giống hệt bản cũ) và lớp tốc độ.
- C1: lọc xe đỗ tự động (`cv_tracker/moving_counts.py`, loại khung đứng yên qua nhiều ảnh) **không dùng được**, vì nó loại luôn hàng chờ đèn đỏ (Khánh Hội – Hoàng Diệu: 22 xe máy đếm tay, còn 1–4 sau lọc). Quay lại vẽ ROI bằng tay.
- Đã đếm toàn bộ 6116 ảnh Q4 bằng YOLO11x (khoảng 30 ảnh/giây trên GPU 1), kèm khung của từng xe: `cv/all_counts.csv`, `cv/all_boxes.jsonl`.
- 2026-11-08 19h, C1: vẽ ROI tay cho 22 camera (`cv_tracker/roi_q4.json`, lưới 8×6, một xe được tính khi điểm giữa đáy khung nằm trong ô thuộc ROI; `cv_tracker/roi_counts.py`). So với đếm tay 4 ảnh (xe máy / ô tô):

  | Camera | Đếm tay | YOLO trong ROI |
  |---|---|---|
  | Hoàng Diệu – Đoàn Văn Bơ 1 | 12 / 4 | 17 / 5 |
  | Khánh Hội – Hoàng Diệu | 22 / 7 | 6 / 10 |
  | Nguyễn Tất Thành – Tôn Đản | 10 / 6 | 15 / 9 |
  | Võ Văn Kiệt – Ông Lãnh 1 | 6 / 8 | 0 / 11 |

  - **Ô tô đếm dùng được** (cao hơn đếm tay khoảng 25–40%).
  - **Xe máy không dùng được**: YOLO COCO trên ảnh 512×288 bỏ sót cụm dày và xe ở xa.
  - **Quyết định:** camera chỉ dùng cho tỉ lệ ô tô và hình dạng theo giờ trên từng camera, có ghi sai số. Model xe máy huấn luyện riêng là việc tùy chọn, làm sau.
- `msa14` (UE so với SO_x, đội xe 6000, 2 seed):
  - meso có kiểm soát nút, xe máy cũ: UE → tốt nhất biết được 3.44% (theo seed 0 / 6.87).
  - **micro chống kẹt v3: 0%** (UE 1823, SO_x 1843, tệ hơn 1.1%).
  - Đến giờ chỉ meso có kiểm soát nút cho thấy còn đất. Đang chờ `msa15` (cùng mô hình, xe máy 3 hàng, 6 seed).
- 2026-11-08 23h30, **đính chính "còn đất"**.
  - `msa15` (mô hình đã chọn, 6 seed) báo `gap_ue_best_known` 4.49%, nhưng con số này **do chọn lọc**: nó so UE ở vòng cuối (nhiễu, ví dụ seed 40010: 2091 trong khi vòng tốt nhất của UE là 1923) với tốt nhất của mọi vòng.
  - So công bằng: tốt nhất với tốt nhất, SO_x **tệ hơn** UE 4.2% (theo seed +2.0, −5.6, −5.2, −8.8, +0.9, −8.7); trung bình 5 vòng cuối, tệ hơn 2.8%.
  - Con số 3.44% của `msa14` m1 có cùng lỗi. Câu "đất cho phối hợp nằm ở tương tác tại nút" **chưa có bằng chứng**.
  - Bước "chạy lại trên seed mới" trong `gate_msa` không chống được chọn lọc ở meso: ba lần chạy lại cho kết quả giống hệt nhau (meso tất định với cùng tuyến).
  - SO_x là heuristic, không tìm được không có nghĩa là không có. UE cũng chưa hội tụ (vòng cuối dao động 1868–2091).
  - Lựa chọn mô hình ở bước A vẫn đứng vì các tiêu chí tới đích, teleport, ρ.
- `k5` (mô hình đã chọn, lớp tốc độ nhẹ, đội xe 6000, 20 seed): ff 890, app 834, greedy 836, greedy q1 828. CVaR25: 933 / 880 / 866 / 864. Quãng đi hẻm 6–9%. Cả 20 seed đều có tới đích dưới 0.75 ở mọi chính sách (0.68–0.70), nên ngưỡng "sụp" 0.75 không còn phân biệt được gì ở đây.
- `cal_b2` (48 bộ): **0/48 đạt tới đích ≥ 0.7**; tốt nhất 0.67 (TTI primary 1.04). Cổng C1 không đạt ở vòng 1. Đang chạy `cal_fac` tách riêng tác dụng của lớp tốc độ và ô tô nội quận.
- 2026-11-08 khuya, theo phản hồi của người dùng: **dừng mọi phép đo so sánh (UE–SO, baseline, train) cho tới khi mô phỏng khớp thực tế.** Các lần chạy `msa13–15`, `k1–k5` làm trên mô phỏng chưa đạt nên không có giá trị kết luận. Giai đoạn D và E chỉ mở lại sau khi qua cổng ở B. Mạng đường cũng chưa được kiểm hết: mới kiểm liên thông và tốc độ tự do; số làn, bề rộng, chu kỳ đèn, cấm rẽ chưa đối chiếu với thực tế.
