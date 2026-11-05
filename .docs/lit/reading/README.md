# Đọc 53 bài trong `papers/` (2026-11-04)

PDF ở `papers/` (gitignored). Nhóm 5–6 và mục 7 là đợt đọc thứ hai, 14 bài có tài khoản trường và 3 bài arXiv. Trang `p.N` là trang của tệp PDF. Đây là bản đọc từ văn bản trích (không xem hình), một người đọc mỗi bài. Con số quan trọng đã được đối chiếu lại với văn bản gốc được đánh dấu ✓; còn lại phải kiểm trước khi đưa vào bài.

Ghi chú chi tiết: `group1_routing.md`, `group2_reward_training.md`, `group3_navapps.md`, `group4_moto_gnn.md`, `group5_guidance.md`, `group6_moto_calib.md`. Bản nháp Related Work: `.docs/paper/related_work.md`. Manifest gốc: `manifest_grok.csv`. Ghi chú của Grok về khả năng viết survey (`survey_feasibility.md`) chưa được kiểm chứng và không được dùng làm nguồn.

## 1. Những gì đổi so với điều ta đang tin

| Điều ta đang tin / làm | Bài nói gì | Hệ quả |
|---|---|---|
| Con số 37% khi app đọc thời gian tức thời chỉ là lỗi đo (`PLAN_V4`) | Bittihn: dao động có thể xuất hiện không cần nhiễu đo, chỉ cần dự báo sai ở mật độ cao và mọi xe cùng phản ứng (p.17, p.23-24). Chan: ngưỡng đổi tuyến là tham số tác động lớn nhất (p.11) | **Mở lại câu hỏi.** Vừa có thể là lỗi đo, vừa có thể là cơ chế thật. Kiểm được bằng quét nhiễu × ngưỡng × chu kỳ |
| `app` là baseline app thực tế | App của Chan chỉ xét đổi tuyến mỗi 300 s, khi lợi ≥ 120 s và 20% ✓ (p.8). `app` của ta đổi ở mọi nút, không ngưỡng | `app` phản ứng mạnh hơn app thật nhiều. Cần baseline kiểu Chan; 120 s phải xét lại vì chuyến trong hẻm ngắn |
| Ba baseline trùng nhau là do mạng ít đất định tuyến | Chan giảm thời gian trung bình 51 → 35 phút ✓ (p.18) nhờ năng lực dư ở đường cấp thấp, kèm tắc mới | Chênh rất lớn so với ta (khoảng 2%). Khác mạng, khác quy mô, chưa so trực tiếp được; phải giải thích trước khi kết luận về baseline |
| Lợi ích chỉ có ở một số p | Chan và Folsom đều đơn điệu theo p; Chan có knee ở 70% ✓ (p.16). Bằng chứng ngược chỉ là nguồn thứ cấp và ví dụ hai tuyến | Không giả định trước. Quét cả p = 0.1, 0.2, 1 |
| Giới hạn thông tin là điểm riêng | URB: quan sát toàn cục cải thiện IQL từ −12.06% còn −3.49% so với trước khi train ✓ (p.9) | Thông tin có tác dụng đo được với MARL, ủng hộ biến "mức thông tin" |

## 2. Đối thủ và độ mới

- **URB (NeurIPS 2025)** là mốc phải vượt: chọn tuyến trước chuyến, 40% CAV, 5 seed. MAPPO gần như ngẫu nhiên ✓ (p.8), tệ hơn nhiều khi cầu tăng: −5.20%, −9.52%, −61.42% ✓ (p.9). Bỏ bootstrapping, IQL* thắng người ở 2 mạng ✓ (p.35).
- **Nhóm Kucharski (Psarou, Akman)** là đối thủ gần nhất, đang đi tới chi phí biên ít tốn. Bản đọc được chỉ là tóm tắt 3 trang; bản 2610.13439 chưa đọc.
- **Wang 2505.20889**: reward marginal giải tích, không chạy lại, một agent trung tâm, BPR tĩnh, 100% tuân thủ. SO hơn UE 3.93%; RL hơn UE 3.60%, 0.58% hoặc 3.21% tùy tập tuyến ✓ (p.6). Tập hành động quyết định nhiều.
- **Không được viết "đầu tiên"** cho next-hop RL trong SUMO: Koh 2020 và Shou 2022 đã làm (Shou: 69 nút, 120 agent ích kỷ, không baseline ở ví dụ SUMO, p.22).
- **Còn đứng vững trong 39 bài này** (chưa phải toàn bộ tài liệu): quy trễ đo được theo từng xe trong next-hop, kiểm chứng phản thực; báo cáo nhiễu cùng tuân thủ không đầy đủ; xe máy và hẻm (tìm `motorcycle`, `motorbike`, `two-wheeler`, `alley` trên 7 bài nhóm 1 không ra kết quả).

## 3. Đề xuất cho thiết kế (chưa sửa code)

Run v6 đang chạy là một chuỗi: **không đổi giữa chuỗi**, các mục dưới áp dụng cho chuỗi sau. Thứ tự theo tác động kỳ vọng, hai mục đầu rẻ nhất.

| # | Đổi gì | Lý do trong code | Nguồn | Dựa trên giả định |
|---|---|---|---|---|
| 1 | Bootstrap xe bị cắt bằng trạng thái tại H, thay vì `v[i]` của quyết định cuối | ✓ `sumo_marl.py` `gae`: `boot = v[i]`, `potential_shaping` giữ R' = R. Coi như xe không tiến triển trong dt cuối; 66% xe điều phối bị cắt | PPO Eq.10, p.5; Ng p.5 | Suy luận riêng, đo độ lệch trước |
| 2 | Chuẩn hóa value, báo EV của V' + Φ theo return chưa shaping | ✓ Loss critic là MSE thô. Cầu và p làm thang return đổi. EV 0.24–0.33 trên đích đã shaping chưa nói lên critic kém | Yu p.7, p.11; GAE p.5-6 | Thang return đổi theo p, cầu |
| 3 | Dùng toàn bộ batch mỗi update, rồi thử lr actor 3e-4 | ✓ 12 bước × 64 tick = 768 tick; khoảng 2880 tick nếu 32 tập × 90 tick, tức khoảng 27%. Tốn thêm khoảng 3.75 lần ở bước update | Yu p.8-9, p.27-28 | Yu dùng chung reward, N ≤ 27; đo số quyết định mỗi chunk trước |
| 4 | Kiểm `attrib` có đo sàn nhiễu: đổi hành động nhóm xe, giữ nguyên xe khác, hồi quy ΔJ theo tổng phí; so tương quan advantage thay vì reward | 0.956 có thể chỉ do chung dt. 60% phí bằng 0 cần tách thật hay bỏ sót. Không bài nào kiểm chứng cách quy này | Foerster p.4; Castellini p.3, p.11-12 | SUMO reset được, tuyến tính với nhóm nhỏ |
| 5 | Φ = −a·R/60 | Reward có a ∈ [0.55, 1] còn Φ không; thừa khoảng 0.45R/60 ở p = 0.1 | Ng p.5-6 | a không đổi trong tập |
| 6 | Thử λ cao hơn hoặc Monte Carlo | IQL* không bootstrap thắng; tác giả chỉ giả thuyết về critic (URB p.9, p.35). URB chỉ có một quyết định mỗi tập, nên chỉ là gợi ý | URB | Ablation, không thay mặc định |
| 7 | Thí nghiệm: thêm baseline kiểu Chan, p = 0.1–1, cầu thấp hơn, có sự cố, xấp xỉ SO; báo cáo theo từng mức cầu; đo dao động và tải lên hẻm | Một con số J trung bình che mất mọi cơ chế | Chan p.8, p.17-19; Bittihn p.32-34; URB p.9; Wang p.6 | |

**Giữ**: dạng shaping γ^dt và R' = 0 khi tới đích (Ng p.8 ✓, nêu không chứng minh; bảo toàn chỉ giữa mục tiêu có và không shaping, không nói gì về J); policy chung; critic toàn cục + cục bộ; không dùng joint-action Q kiểu COMA; attention có mask cho số lối ra thay đổi (Kool p.3-6, Veličković p.3-5).

**GNN**: không bài nào trong nhóm dùng GNN trên line graph làm policy điều khiển giao thông động; Kool và Lei chỉ cho bài toán tĩnh một tác tử. Lei: GAT thuần từ 3 lớp không hội tụ, thêm phần dư thì sửa được (p.19). Cần kiểm GNN 3 lớp của ta có phần dư chưa.

## 4. SUMO cho xe máy

Không có giá trị trích dẫn được cho chen khe ở chỗ hẻm nhập đường lớn: `jmTimegapMinor`, `impatience`, `lcSublane`, `lcPushy`, `sigma` không xuất hiện trong 4 bài xe máy; `teleport`, `alley` cũng không. Vậy các giá trị này phải là **dải quét**, ghi rõ trong bài.

| Tham số | Của ta | Trích được | Ghi chú |
|---|---|---|---|
| accel | 2.5 | 6.0 ✓ (Salawavidana p.3) | Sri Lanka, nút đèn |
| decel | 4.5 | 4.5 ✓ | |
| length | 1.9 | 2.0 ✓ | |
| minGap | 0.5 | 0.1 ✓; VISSIM standstill 0.5 (Vu p.12, p.17) | Vu: khoảng dừng tác động mạnh nhất, b = 510 s/m ✓ (p.20); VISSIM không chép thẳng sang SUMO |
| maxSpeed | 54 km/h | 60 ✓ | |

Tiêu chí kiểm chứng có thể mượn: MAPE < 15%, GEH < 5 (Salawavidana p.3); kiểm định t trên thời gian đi, kiểm chứng ở chiều khác (Vu p.13-15). Đều là đường lớn, nút đèn; không bài nào cho hẻm.

## 5. File đặt sai chủ đề

`Akman_2025_CVCompliance` = URB. `Sang_2020_SUMORL` = Koh và cộng sự. `Hua_2025_DiffRewards` = survey MARL điều khiển CAV. `Aradi_2020_SUMORL` = survey motion planning (route planning không dùng RL). `MartinezDiaz_2024_CVCompliance` = review platooning, gần như lạc đề. `Bang_2022_CVCompliance` = định tuyến tập trung 100% CAV, không có compliance. `Michailidis_2026_DiffRewards` = bất bình đẳng trong congestion game, không phải difference reward. `Chen_2022_Motorcycle` = CNN dự báo giải tỏa hàng đợi. `Hu_2022_SUMORL` = simulator meso-macro, không phải SUMO. `Lei_2022_GNNAssignment` = TSP/CVRP. `Shen_2025_NavApps` = day-to-day cognitive hierarchy. `Su_2022_MARLRouting` = agent là đèn tín hiệu.

Bản preprint, cần lấy bản đăng trước khi trích: Chan, Bittihn, Waniek, Shen, Bang, Shou, Su, Liu ×2, Lassen, Lei, Castellini, hai bài Wang.

## 6. Chưa lấy được (21 bài trong manifest)

Ưu tiên cao, cần tài khoản trường: Yun TR-C 2024 `10.1016/j.trc.2024.104721`; Jiang TR-C 2023 `10.1016/j.trc.2023.104440`; Ke TR-C 2025 `10.1016/j.trc.2025.105040`; Ma & He TR-B 2024 `10.1016/j.trb.2024.103014`; Ramos KER 2020 `10.1017/s0269888920000119`; Akman RouteRL `10.1016/j.softx.2025.102279`; Fadilah TRIP 2024 `10.1016/j.trip.2024.101247`; Wolpert & Tumer `10.1142/s0219525901000188`; Lopez SUMO ITSC 2018 `10.1109/itsc.2018.8569938`.

Ưu tiên vừa: Kim TR-C 2025 `10.1016/j.trc.2025.105244`; Hosseinzadeh TR-C 2023 `10.1016/j.trc.2023.104359`; Zhou & Gayah TR-C 2023 `10.1016/j.trc.2023.104033`; Kamiński 2020 `10.1155/2020/3152020`; Ni 2022 `10.1016/j.physa.2022.128441`. Còn lại xem `manifest_grok.csv`.

Chưa có trong manifest nhưng nên tìm: Psarou 2610.13439 và 2510.11410 toàn văn; Li & Duan 2404.15599; Chowdhury & Chakraborty 2024; Codeca & Härri 2019; Kuo 2023; và các nguồn thứ cấp Peeta, Litescu, Friedman, Devlin & Kudenko.

## 7. Đợt đọc thứ hai: điều làm đổi quyết định

Đã đối chiếu với văn bản gốc (✓). Chưa áp dụng vào code; chuỗi v6 đang chạy không đổi.

**Mô hình mạng (quan trọng nhất, chưa đo tác động).** ✓ Cả 1460 cạnh hẻm đều có cạnh ngược chiều, mỗi cạnh một làn 2.5 m, OSM không có width, không có cạnh một chiều. Nếu 2.5 m là bề rộng cả con hẻm thì mô phỏng đang có 5 m mặt đường và **không có xung đột ngược chiều**, có thể làm hẻm quá thoáng và đẩy trễ về chỗ nhập. Độ phân giải ngang 0.8 không chia hết 2.5.

**Teleport.** Thứ hạng đổi theo tham số này: ở 180 s `selfish` 471.91, `attrib` 482.65; ở 600 s `attrib` 527.29, `selfish` 566.13 (argmax update 125, 4 seed chọn mô hình). 180 s đang giải phóng tắc thay vì mô tả nó; không bài nào làm cơ sở cho giá trị này. Đề xuất: kết quả chính ở 600 s trở lên, kèm teleport theo nguyên nhân và vị trí, tỉ lệ tới đích.

**Tuân thủ.** 90% của ta cao so với đo thật của Kim 2025: PCR 68.12→68.78% ✓, hẻm hẹp không tuân thủ 91.06% ✓ (p.12-13, ô tô Hàn Quốc, tính theo link). Quét 60–100%, thử theo loại cạnh. Train ở 90%, test thấp hơn: Hosseinzadeh mất 57% lợi ích (BC) so với 27% (FC) khi tuân thủ 100→30% ✓ (p.17, tính lại).

**Baseline SO.** Yun dùng DSO-Iterative trong SUMO ✓ (p.13); khoảng DUE–DSO 5.2–7.12% (tính lại) trên mạng nhỏ, η = 0.25 mất 20–69% khoảng đó. Dùng `gate_msa` theo hướng này làm mốc, ghi rõ là cận tĩnh.

**Reward.** Trong Yun, chia sẻ Q với −thời gian link đã gần DSO (0.07%, tính lại; mạng nhỏ, 100% xe). Psarou 2610: trọng số xã hội lớn làm xấu hệ thống (p.6, p.8). Vậy không mặc định `attrib` hơn `selfish`. Thêm nhánh rẻ `selfish + β(f−F)` (Ramos p.8) nếu cần, và kiểm riêng chỗ nhường đường khi đối chiếu phản thực.

**Chọn tham số SUMO** (chi tiết `group6_moto_calib.md` mục b): sửa lớp mạng → thí nghiệm một nút chữ T để đo gap do SUMO sinh ra so với 3.0–3.2 s → Morris rồi LHS → hiệu chỉnh tổng hợp theo RMSE tốc độ Mapbox trên cạnh không phải hẻm → đánh giá trên 3–5 bộ tham số. Được nói "đo": topology; "hiệu chỉnh": phần qua bước tốc độ; "độ nhạy": `impatience`, `jm*`, `lc*`, `sigma`, bề rộng. **Không được nói "đã hiệu chỉnh cho hẻm".**

**Sửa lỗi.** `Chowdhury_2024_SUMO.pdf` là bài động cơ điện do DOI sai trong danh sách tải. Lần đọc nhóm 1 ghi số hình của Chan chỉ qua văn bản; hàng std Bảng 2 của Hosseinzadeh bị dính khi trích, xem lại PDF.

**Chưa đọc hết:** Ramos p.12-13, Hosseinzadeh p.5-8 và phần sau chưa liền mạch, Li & Duan chỉ p.1-2, p.10-11, Khulna; Arora 2026 toàn văn chưa có.

## 8. Đợt ba (5 bài trong `papers/`, 2026-11-05, đọc có chọn lọc)
- **Arora 2026 (Nature Cities, đã đọc):** phí ngoại ứng cố định trên khoảng 100 đoạn tắc theo lịch sử, thí nghiệm switchback, dưới 2% chuyến bị đổi ✓ (p.2), trần vài phần trăm so với đường nhanh nhất, trung bình đi lâu hơn khoảng 30 s (p.6). Tốc độ đoạn được chọn +2%, mọi đoạn bị ảnh hưởng +0.35% (p.3), thời gian đi 0.7% (p.1). Câu "2%" trước đây không nêu rõ chỉ trên đoạn được chọn. Giới hạn: chỉ đổi giữa đường cùng cấp nên không nói gì về hẻm. Hệ quả: thêm baseline `app_ext`.
- **Ibrahim & Sanik 2007:** critical gap xe máy (s): đường chính một làn 2.8 và 3.0; nhiều làn 3.2, 2.3, 3.3; ô tô 3.2–4.2 (p.8). T-intersection ở Malaysia, không phải hẻm.
- **Kuncheria 2023, Graf 2024, Wolpert 2001:** mới đọc tóm tắt. Khẳng định "SO làm xấu tải đường dân cư" của Kuncheria chưa kiểm được trên văn bản; phải đọc trước khi trích. Graf: khung cân bằng động có ràng buộc phụ, và phản ví dụ về tồn tại nghiệm.
- **Còn thiếu:** Khulna, Patil (Grok báo bị chặn), Qian 2012 (cần đăng nhập). Xem `papers/manifest_2.csv`.

