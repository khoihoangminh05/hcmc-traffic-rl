# Baseline mạnh cho bài (2026-11-11)

Mục tiêu: reviewer không thể nói "MAPPO chỉ thắng heuristic yếu". Phải có một baseline **phối hợp mà không học**, có tên trong tài liệu, chỉ dùng thông tin một nhà vận hành thật có. Đúng quy tắc của `PLAN_FINAL.md`: **viết đặc tả và code có kiểm thử đơn vị được ngay; không chạy so sánh trước G2.**

## 1. Vì sao `greedy_load` hiện tại chưa đủ

Code (`routing2/sumo_marl.py`, `_Score`): chọn cạnh ra có `live_cost + q · (số xe đội trên cạnh kế + số ý định vào cạnh kế)`. Tức là chỉ nhìn **một bước**, không theo thời gian. Hai họ phương pháp đã đăng làm mạnh hơn hẳn:
- Dùng **toàn bộ tuyến dự kiến** của các xe đội khác và thời điểm chúng tới từng cạnh (Pan 2013; Wilkie 2011, 2014).
- Định tuyến theo **chi phí biên** ước từ số đo, gần tối ưu hệ thống (Sharon 2017).

Nếu không có hai thứ này, reviewer sẽ nói phần "phối hợp" của MAPPO chỉ là bản học của một heuristic đã có.

## 2. Đã đọc (toàn văn trừ ghi chú khác)

| Bài | Ý chính | Bằng chứng trong bài | Ghi chú |
|---|---|---|---|
| Pan, Sandu Popa, Zeitouni, Borcea 2013, IEEE TVT 62(8):3551–3568, DOI 10.1109/TVT.2013.2260422 (`papers/Pan_2013_ProactiveRerouting.pdf`) | Máy chủ trung tâm, xe chia sẻ tuyến. Mỗi cạnh có "dấu chân" fc_i = n_i·ω_i, n_i là số xe được giao tuyến qua cạnh trong cửa sổ kế tiếp (p.5, Định nghĩa 2). EBkSP: tính k tuyến ngắn nhất, chọn tuyến có độ "phổ biến" e^E thấp nhất, E là entropy của dấu chân dọc tuyến; giao tuần tự theo độ khẩn, cập nhật dấu chân sau mỗi xe (p.7). DSP = đổi sang tuyến nhanh nhất theo ảnh chụp hiện tại (p.2), tức `app` của ta | SUMO + TraCI (p.10). Chu kỳ 450 s, ngưỡng mật độ 0.7, k = 4 (p.10–11). Gần bằng một DTA mô phỏng, rẻ hơn nhiều (p.2) | Dùng Greenshields để ước thời gian (p.3), cần mật độ cạnh: ta không có, thay bằng thời gian báo cáo |
| Sharon, Levin, Hanna, Rambha, Boyles, Stone 2017, TR-C 84:142–157, DOI 10.1016/j.trc.2017.08.019 (`papers/Sharon_2017_DeltaTolling.pdf`) | Δ-tolling: τ_t = (1−R)τ_{t−1} + R·β·(T_{t−1} − T_0), chỉ cần thời gian đo và thời gian tự do, hai tham số (p.5, phương trình 3) | Với hàm BPR, β đúng bằng số mũ B thì trùng toll chi phí biên, tức tối ưu hệ thống (p.6, Mệnh đề 1; p.8). Mô phỏng: tăng phúc lợi tới 26–33%, R tốt quanh 10^−4 (p.10). Có đèn thì chi phí biên một xe gần 0 khi cầu thấp (p.12) | Phải tinh chỉnh lại khi đổi mô hình giao lộ (p.14). Bài không có tuân thủ < 100% (p.14) |
| Wilkie, Baykal, Lin 2014, SIGSPATIAL, "Participatory Route Planning" (`papers/Wilkie_2014_Participatory.pdf`) | Tuyến đã giao là dự báo; mỗi xe được định tuyến thì cộng mật độ biên dọc tuyến theo thời gian, xe sau dùng trường mật độ đó (p.1, p.4). Mở rộng Wilkie 2011 (AAAI) cho giao lộ có đèn (p.2, p.5) | SUMO (p.5), so với baseline định tuyến khác. Chưa đọc kỹ phần kết quả | Đọc tiếp p.6–9 trước khi trích số |
| Wang, Djahel, Zhang, McManis 2016, IEEE T-ITS 17(10):2888–2899, DOI 10.1109/TITS.2016.2531425, "Next Road Rerouting" | Chọn **cạnh kế tiếp** theo hàm chi phí gồm đích và giao thông cục bộ, nhiều agent (theo tóm tắt) | **Chỉ đọc tóm tắt**: không lấy được PDF | Gần nhất với `greedy_load` về hình thức next-hop. Cần toàn văn trước khi gọi `greedy_load` là "kiểu NRR" |
| Ke, Zou, Liu, Qian 2025, TR-C (ghi chú `lit/reading/group5_guidance.md` §5) | Thầy pre-DSO: MSA + chi phí biên theo tuyến | Trên mạng thật RL hơn UE dưới 2% | Hợp với cận min-cost flow đã chốt |

## 3. Chốt (D16)

Bộ baseline cuối, ánh xạ sang tên trong tài liệu:

| Tên trong code | Tên trong bài | Nguồn | Vai trò |
|---|---|---|---|
| `ff` | Định tuyến theo thời gian tự do | | Mốc dưới |
| `app` | Tuyến nhanh nhất theo ảnh chụp hiện tại (DSP) | Pan 2013 | App thương mại |
| `app_ext` | App có chia tải theo cạnh được chọn | Arora 2026 | App có cân nhắc hệ thống |
| `greedy` | Định tuyến lại tham lam có tính tải một bước | Wang 2016 (chờ đọc), Pan 2013 | Heuristic hiện tại |
| **`foot`** (mới) | **Định tuyến tham gia, dấu chân theo thời gian** | Pan 2013 EBkSP, Wilkie 2014 | **Baseline phối hợp mạnh chính** |
| **`delta`** (mới) | **Định tuyến theo chi phí biên Δ** | Sharon 2017 | Gần tối ưu hệ thống, phi tập trung |
| `foot_delta` (mới) | Hai cái trên gộp | Ghép hai bài, ghi rõ là ta ghép | Baseline mạnh nhất, nếu hơn cả hai |
| `mcf` | Luồng chi phí nhỏ nhất trên mạng mở rộng theo thời gian, giải lại định kỳ | Đã chốt trong `PLAN_FINAL.md` | Cận và baseline tập trung |
| IPPO | | | Ablation học không phối hợp |

Báo cáo MAPPO so với **baseline tốt nhất đã tinh chỉnh** trong bảng, không chọn cái yếu.

## 4. Đặc tả

Chung: chỉ dùng thời gian báo cáo của đội (cộng nguồn đường lớn nếu `PROBLEM_DEF.md` 3a được làm), thời gian tự do, tuyến và ý định của chính đội. Không đọc số xe nền, pha đèn, mật độ thật. Đầu ra vẫn là cạnh kế tiếp, lấy từ cạnh đầu của tuyến đã tính, nên dùng chung khung đánh giá, tuân thủ và `max_detour`. Mọi tham số tinh chỉnh trên seed 40000–40007.

**`delta`.** Mỗi chu kỳ báo cáo (10 s) cập nhật τ_e ← (1−R)τ_e + R·β·max(0, live_e − ff_e). Chọn cạnh ra theo đường ngắn nhất tới đích với chi phí live_e + τ_e. Lưới: β {0.5, 1, 2, 4}, R {0.05, 0.2, 1}. Ghi chú: R của Sharon theo bước mô phỏng mỗi giây; ta cập nhật mỗi 10 s nên R khác thang.

**`foot`.** Bảng dấu chân F[e, b], b là ô thời gian 60 s, trong 20 phút tới.
- Khi một xe đội cần quyết định: tính đường ngắn nhất phụ thuộc thời gian tới đích với chi phí cạnh = live_e + c·F[e, b(t_đến)], t_đến cộng dồn dọc tuyến.
- Ghi tuyến: cộng 1 vào F[e, b] cho mọi cạnh trên tuyến tại ô thời gian dự kiến; xóa phần cũ của xe đó trước. Xe đã qua cạnh thì bỏ dấu chân cạnh đó.
- Thứ tự xét trong cùng bước: ngẫu nhiên, như ý định hiện có. Biến thể theo độ khẩn của Pan (thời gian còn lại trừ thời gian tự do còn lại) để làm ablation.
- Lưới: c {1, 2, 4, 8} s mỗi xe, ô thời gian {30, 60} s. c = 0 trùng `app`, và "chỉ cạnh kế, không thời gian" trùng `greedy`. Nhờ vậy ba baseline là một họ, ablation rõ ràng.

**`foot_delta`.** Chi phí live_e + τ_e + c·F[e, b].

**Kiểm thử đơn vị trước khi chạy:** mạng đồ chơi hai tuyến song song. (1) c = 0 cho đúng quyết định của `app`. (2) Giao 10 xe cùng lúc thì `foot` chia ra hai tuyến, còn `app` dồn một tuyến. (3) `delta` với β = 0 trùng `app`. (4) Thời gian tính một quyết định dưới 50 ms trên mạng 3888 cạnh.

## 5. Công bằng với MAPPO

`foot` thấy toàn bộ tuyến dự kiến của đội, còn MAPPO hiện chỉ thấy ý định cạnh kế và số xe đội trên tuyến nhanh nhất (`_fleet_ahead_table`). Baseline có nhiều thông tin hơn thì chỉ làm bài khó hơn, không sai. Nếu MAPPO thua, có thể cho MAPPO thêm đặc trưng dấu chân F; phải ghi rõ là cùng một thông tin.

## 5b. Đã có ai so RL với EBkSP

Có: Du et al., "Dynamic urban traffic rerouting with fog-cloud reinforcement learning", Computer-Aided Civil and Infrastructure Engineering 2023, DOI 10.1111/mice.13115 (bản arXiv 2110.05532; đã có trong `lit/candidates.md`). Theo kết quả tìm kiếm, họ dùng EBkSP làm baseline luật trong SUMO và báo RL tốt hơn 14–54% về tốc độ và tắc, so với hai baseline. **Chưa đọc toàn văn.** Hệ quả: "RL hơn EBkSP" không mới; cái mới phải là bối cảnh (đội nhỏ giữa xe nền, hẻm, thông tin hạn chế, tuân thủ) và baseline mạnh hơn EBkSP (`foot_delta`, `mcf`).

## 6. Còn phải đọc

- Wang 2016 NRR toàn văn (bản tác giả ở kho UCD hoặc Coventry, hoặc qua tài khoản trường).
- Wilkie 2014 p.6–9 (kết quả); Wilkie 2011 AAAI.
- Tìm thêm: so sánh RL với EBkSP hoặc định tuyến tham gia, để biết đã ai làm chưa (truy vấn: `EBkSP reinforcement learning comparison`, `participatory routing multi-agent reinforcement learning`).
