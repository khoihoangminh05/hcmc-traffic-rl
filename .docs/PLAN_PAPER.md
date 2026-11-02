# Kế hoạch bài báo (bản gốc từ 2026-11-02)

Mục tiêu: một bài **Q1 rank cao** (đích chính Transportation Research Part C; dự phòng IEEE T-ITS). Bài A\* phụ (AAMAS / KDD applied) chỉ khi phương pháp chuyển giao được sang quận khác.

File này là **kế hoạch chính**. `PLAN_V4.md` thành nhật ký kỹ thuật (số liệu, lỗi, quyết định). `RESEARCH_V4.md` là nền khảo sát và hướng chốt.

Luận điểm làm việc (sẽ được kiểm chứng ở Phần 1): *định tuyến tối ưu hệ thống có ràng buộc sức chịu của hẻm, bằng MARL phi tập trung với chia công chi phí biên theo hàng đợi, trên twin hẻm Q4 trong SUMO.*

## Nguyên tắc
- Mỗi phần có **đầu ra** và **cổng đạt / không đạt**. Không sang phần phụ thuộc khi cổng chưa qua.
- Việc tốn thời gian chờ (thu dữ liệu, chạy máy) chạy trước; việc đọc và viết đi song song.
- Không train thật trước khi xong Phần 3 (dữ liệu và twin) và Phần 6 (giao thức thí nghiệm). Lệnh train chỉ đưa khi người dùng yêu cầu.
- Báo cáo mọi lần chạy, kể cả thất bại. Seed chọn mô hình 50000+, seed báo cáo 60000+.
- Mỗi phần sinh ra một đoạn viết được cho bài (cột "vào bài").

## Tổng quan và thứ tự ưu tiên

| # | Phần | Ưu tiên | Phụ thuộc | Thời gian ước tính | Vào bài |
|---|---|---|---|---|---|
| 0 | Thu dữ liệu nền | Đang chạy | — | tới tối 07/11 | Data |
| 1 | **Kiểm chứng bài toán (cổng A, B)** | **Cao nhất, làm ngay** | SUMO (có sẵn) | 1 tuần | Motivation, Fig. 1 |
| 2 | **Tổng quan có hệ thống** | **Cao, song song với 1** | — | 2 tuần | Related Work |
| 3 | Dữ liệu và twin (fusion, hiệu chỉnh nhu cầu) | Sau 07/11 | 0 | 2–3 tuần | Data, Twin |
| 4 | Phát biểu bài toán và lý thuyết | Sau cổng A | 1 | 1–2 tuần | Formulation, Theory |
| 5 | Phương pháp, baseline, train nhỏ | Sau 4 | 3, 4 | 2–3 tuần | Method |
| 6 | Giao thức thí nghiệm (viết trước) rồi chạy chính | Sau 5 | 3, 5 | 3–4 tuần | Experiments, Results |
| 7 | Viết bài | Khung từ tuần 1, hoàn thiện cuối | tất cả | xuyên suốt | toàn bài |

Đường găng: 0 → 3 → 5 → 6. Phần 1 và 2 không nằm trên đường găng nên làm ngay để không tốn lịch.

---

## Phần 0. Thu dữ liệu nền (đang chạy)
- Mapbox live 10 phút, 5–22 giờ, tự dừng 22:00 ngày 07/11; typical đủ 02–08/11. Camera vẫn chụp.
- Kết luận đã có: live ≈ hồ sơ lịch sử → dùng như hồ sơ tốc độ theo giờ.
- Việc người dùng: kiểm tra ToS Mapbox về lưu và công bố dữ liệu dẫn xuất (ảnh hưởng gói dữ liệu công khai của bài).

## Phần 1. Kiểm chứng bài toán (làm ngay)
Câu hỏi: trên mạng hẻm Q4, định tuyến hợp tác có đáng làm không, và hẻm bị đi tắt bao nhiêu?

1.1 **UE**: `duaIterate.py` của SUMO, xe máy, nhu cầu tổng hợp (routing2.demand), quét 4–6 mức nhu cầu, 3 seed.
1.2 **SO xấp xỉ**: gán theo chi phí biên (kiểm tra tùy chọn marginal-cost của duaIterate; nếu không có thì lặp với chi phí cạnh = thời gian + lưu lượng × đạo hàm thời gian ước lượng từ SUMO).
1.3 **Đo**: tổng thời gian đi (TTT), khoảng UE–SO (%), lưu lượng đi tắt trên từng hẻm (xe không có điểm đầu hoặc cuối trong hẻm đó), số hẻm vượt ngưỡng sức chịu (quét 3 ngưỡng).
1.4 **Cổng B**: greedy chi phí biên (không học) trong `routing2/sumo_env.py` đạt bao nhiêu phần khoảng UE–SO; kèm app và free-flow.

**Cổng A**: khoảng UE–SO ≥ 3% ở ít nhất một mức nhu cầu tắc thực tế. Không đạt → đổi luận điểm sang "phân tích ngoại ứng đi tắt và định giá trong mạng hẻm", MARL thành phụ.
**Cổng B**: nếu greedy chi phí biên đạt ≥ 90% khoảng đó ở mọi kịch bản, đóng góp MARL phải chuyển sang kịch bản khó (p thấp, thông tin thiếu, có ràng buộc hẻm).
Đầu ra: `results_gate/` + một trang tóm tắt quyết định; hình đường cong TTT theo nhu cầu (UE, SO, app) làm Fig. 1.

## Phần 2. Tổng quan có hệ thống (song song với Phần 1)
2.1 **Giao thức** (viết trước khi tìm): câu hỏi tổng quan; nguồn (Scopus, Web of Science nếu có quyền truy cập; Google Scholar; Semantic Scholar; arXiv; TRID); chuỗi tìm cho 6 mạch (MARL routing; SO/chi phí biên/chia công; Stackelberg–tuân thủ–thông tin; ngoại ứng đi tắt và sức chịu môi trường; giao thông xe máy và hẻm; ước lượng trạng thái thưa); năm 2015–2026 (lý thuyết kinh điển thì không giới hạn); tiêu chí nhận và loại.
2.2 **Tìm và sàng lọc**: tiêu đề → tóm tắt → toàn văn; ghi số bài mỗi bước (sơ đồ kiểu PRISMA); lần trích dẫn ngược và xuôi từ 5–10 bài lõi.
2.3 **Đọc toàn văn 30–40 bài**, bảng trích xuất: bài toán, mạng, simulator, quan sát, reward, tỉ lệ tham gia, baseline, chỉ số, kết quả, giới hạn.
2.4 **Kiểm khoảng trống**: mỗi câu "chưa có ai" phải qua một lượt tìm phản bác có ghi lại truy vấn.
Đầu ra: `.docs/lit/` (giao thức, bảng trích xuất, sơ đồ sàng lọc), bản nháp Related Work + bảng định vị.
Người dùng: quyền truy cập thư viện trường (Elsevier / IEEE) để lấy toàn văn bài trả phí.

## Phần 3. Dữ liệu và twin (sau 07/11)
3.1 Đóng băng bộ dữ liệu Mapbox (hash, thống kê độ phủ, lỗ hổng 31/10).
3.2 **Fusion tốc độ có bất định** theo khung giờ cho toàn bộ 1828 cạnh (GP / GMRF trên line graph hoặc kriging GNN); kiểm định leave-one-route-out; độ phủ khoảng tin cậy 90% nằm trong 85–95%. So với nội suy theo hop.
3.3 **Hiệu chỉnh nhu cầu SUMO** theo khung giờ để tốc độ SUMO khớp hồ sơ fusion (SPSA hoặc Bayesian optimization; routeSampler). Báo cáo sai số theo cạnh.
3.4 Tham số chưa biết (bề rộng hẻm, chen khe, ngưỡng sức chịu) chuyển thành **dải kịch bản**, không chọn một điểm.
Cổng: sai số tốc độ hiệu chỉnh trên tuyến giữ lại tốt hơn baseline hồ sơ trung bình.

## Phần 4. Phát biểu bài toán và lý thuyết (sau cổng A)
4.1 Phát biểu chính thức: SO có ràng buộc lưu lượng đi tắt trên hẻm; tỉ lệ tham gia p; cấu trúc thông tin (chỉ đo được); tuân thủ.
4.2 Mệnh đề: (a) reward chi phí biên + nhân tử Lagrange → nghiệm SO có ràng buộc (trường hợp phi nguyên tử); (b) quy trễ theo hàng đợi là phân hoạch của tổng trễ; (c) cận sai số so với chi phí biên phản thực; (d) với p < 1: quan hệ với Stackelberg và cận đã biết.
4.3 Kiểm số: so quy trễ theo hàng đợi với chi phí biên tính bằng chạy lại trên mẫu nhỏ xe.
Đầu ra: mục Formulation + Theory (có chứng minh trong phụ lục).

## Phần 5. Phương pháp, baseline, train nhỏ
5.1 Mở rộng `routing2/sumo_env.py`: quy trễ theo hàng đợi, đo lưu lượng đi tắt từng hẻm, cập nhật giá hẻm.
5.2 Policy: pointer (đã có) + tùy chọn chú ý theo xung đột và mean-field (để ablation).
5.3 Baseline đầy đủ: free-flow, app, greedy chi phí biên, khuyến nghị theo nghiệm UE và SO, MAPPO ích kỷ, IPPO.
5.4 Train nhỏ để gỡ lỗi và chỉnh tham số trên seed 50000+ (chỉ khi người dùng duyệt từng lệnh).

## Phần 6. Giao thức thí nghiệm (viết và chốt trước) rồi chạy chính
- Lưới kịch bản: nhu cầu theo khung giờ (từ Phần 3), p ∈ {0.1, 0.25, 0.5, 1.0}, tuân thủ, ngưỡng hẻm, mẫu từ hậu nghiệm tốc độ.
- Chỉ số: TTT, trễ xe nền và xe đội, lưu lượng đi tắt và số hẻm vượt ngưỡng, công bằng (trễ của dân hẻm), CVaR.
- Thống kê: ≥10 seed phương pháp chính, ≥5 seed ablation; test cặp, bootstrap CI, hiệu chỉnh Holm; seed báo cáo 60000+.
- Ablation: reward (ích kỷ / chi phí biên / + giá hẻm); attention; DR; quy trễ theo hàng đợi so với phản thực.
- Tùy chọn A\*: chuyển giao zero-shot sang một quận khác nhiều hẻm.

## Phần 7. Viết bài
- Khung bài ngay tuần 1; mỗi phần đổ chữ vào đúng mục khi xong.
- Mối đe dọa tính hợp lệ viết từ đầu: nhu cầu chưa biết, SUMO không phải thực tế, ngưỡng sức chịu từ nghiên cứu phương Tây, bề rộng hẻm giả định, Mapbox là hồ sơ lịch sử.
- Gói tái lập: code, mạng SUMO, cấu hình, seed (dữ liệu tùy ToS).

---

## Tuần này (02–08/11)
| Việc | Ai | Ghi chú |
|---|---|---|
| Mapbox chạy tới 07/11 | tự chạy | xem `status` 1–2 ngày/lần |
| 1.1–1.3 code UE / SO / đo đi tắt, chạy thử local | Claude | sau đó một khối lệnh quét trên sol1 |
| 2.1 giao thức tổng quan + bắt đầu tìm, sàng lọc | Claude | người dùng duyệt giao thức |
| Kiểm tra ToS Mapbox; quyền truy cập thư viện trường | người dùng | |
| Khung bài (mục lục + vai trò từng mục) | Claude | |

## Giữ lại từ công việc trước
- Mạng SUMO v4 (netconvert), `sumo_env.py`, `bench_sumo.py`, `sumo_marl.py` v1 (thành baseline MAPPO ích kỷ), đo tốc độ SUMO trên sol1.
- Meso GPU: chỉ để thử nhanh code, không cho kết quả báo cáo (hiệu chỉnh thất bại, có ghi trong PLAN_V4).
- Pipeline probe Mapbox và match_probe.
