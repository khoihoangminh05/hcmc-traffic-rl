# Ghi chú đọc, nhóm 5: dẫn đường hệ thống, tuân thủ, chi phí biên, đối thủ gần nhất

Bản 2026-11-04. Đọc từ văn bản trích từ PDF, không xem hình.

Quy ước:
- `p.N` là trang của **tệp PDF**, không phải số trang in.
- "Nhận xét:" là ý của người đọc. "(tính lại)" là phép tính của người đọc từ số trong bài.
- "Không nêu trong bài" nghĩa là không có trong phần văn bản trích. Số chỉ nằm trên hình thì không đọc được, nên cũng ghi như vậy.
- Phạm vi đọc: các bài đọc từ bản đã lọc mảnh công thức ngắn. Chưa đọc: Ramos p.12-13 (lướt p.11-14, chứng minh), Hosseinzadeh p.5-8 (công thức), Li & Duan các định lý ngoài p.1-2, p.10-11. Bảng D.6 của RouteRL chỉ đọc một phần. Không xem hình ở mọi bài.
- Ba bài arXiv tải ngày 2026-11-04, trích bằng script chỉ dùng thư viện chuẩn; chữ công thức có thể vỡ, phần văn và bảng đọc được.

Không kết luận gì về MAPPO của ta từ các bài này: số của ta mới ở update 125, trên seed chọn lọc 50000+, chưa phải kết quả bài báo.

---

## 1. Psarou, Rams, Torbus, Kucharski 2026, 2610.13439 (core, đối thủ gần nhất về credit)

**Trích dẫn.** Psarou, Rams, Torbus, Kucharski. "Collective Autonomous Vehicle Routing Needs Social Awareness for Coexistence with Human Drivers". Preprint arXiv:2610.13439, 9/10/2026 (ngày từ trang abs). Nơi đăng: không nêu trong bài.

**Bài toán, đơn vị.** Chọn tuyến **trước chuyến**, mỗi ngày một lần, trong 4 tuyến cố định theo OD (p.3, p.5, p.7). Agent là từng AV, học độc lập (p.5). Chơi tuần tự theo giờ khởi hành (p.4).

**Mạng, simulator, cầu.** SUMO qua RouteRL (p.3). Ingolstadt 850 nút, 1426 link, 306 OD, 1035 agent, từ InTAS; Provins 2173 nút, 4216 link, 517 OD, 523 xe, từ URB (p.5). Cầu và giờ khởi hành **giữ nguyên qua các ngày** (p.3).

**p và tuân thủ.** Có nhiều mức p (Hình 3, p.6; các mức cụ thể chỉ nằm trên hình), số liệu bảng ở 40% tức khoảng 414 AV (p.7). Tuân thủ: không có, AV làm đúng chính sách. Người lái học 300 ngày, rồi đóng băng và lấy mẫu từ phân phối đã học (p.3, p.5).

**Thông tin.** Ước lượng thời gian từng tuyến dựa trên xe cùng OD khởi hành trước, cộng OD và giờ khởi hành (p.3). Nhận xét: đo được về nguyên tắc, nhưng không có mất gói hay sai số, và không có trạng thái mạng.

**Reward, credit.** r_i = −e_i − β·m_i, m_i là tổng chênh thời gian của mọi xe khác giữa lần có và lần bỏ AV i (p.4, Eq.1-2). **Có chạy lại**: mỗi AV một mô phỏng phản thực mỗi ngày, với 414 AV × 10 000 ngày = 4 140k lần (p.7). Bản chọn lọc: xếp hạng AV theo H_i, độ lệch chuẩn của tổng thời gian hệ thống theo từng tuyến AV chọn, từ 800k joint action lấy mẫu (p.5, p.7). Thưởng cho 40% AV: 1 660k + 800k, tổng khoảng 2 456k lần, giảm khoảng 40% (p.7-8).

**Thuật toán, ngân sách.** REINFORCE, học độc lập (p.5). 10 000 ngày train, 100 ngày test không cập nhật (p.5). Thời gian wall-clock: không nêu trong bài. Siêu tham số ở phụ lục, tệp đã tải không có.

**Baseline.** Selfish (β = 0), so với trạng thái trước khi có AV (p.5-7). Không có AON, không có SO, không có app. Nhận xét: không thể biết gần tối ưu bao nhiêu.

**Kết quả, Ingolstadt, 40% AV, thay đổi tương đối so với trước khi có AV; dương là tốt hơn (Bảng 1, p.7).**

| Cấu hình | Số phản thực | HDV | AV | Toàn hệ |
|---|---|---|---|---|
| β = 0 | 0 | −1.66 ± 0.19 | +3.74 ± 0.75 | +0.50 ± 0.41 |
| β = 0.1, 100% | 4 140k | −1.06 ± 0.17 | +3.79 ± 0.71 | +0.88 ± 0.39 |
| β = 0.1, 50% | 2 070k | −1.17 ± 0.18 | +3.78 ± 0.72 | +0.81 ± 0.39 |
| β = 0.1, 40% | 1 660k | −1.25 ± 0.17 | +3.78 ± 0.73 | +0.76 ± 0.38 |
| β = 0.1, top 10% | 420k | −1.50 ± 0.19 | +3.78 ± 0.74 | +0.61 ± 0.40 |
| β = 0.1, ngẫu nhiên 10% | 420k | −1.60 ± 0.18 | +3.75 ± 0.72 | +0.54 ± 0.39 |

- Giữ lại khoảng 68% và 82% phần cải thiện HDV ở 40% và 50% (p.7). Khớp khi tính lại: 0.41/0.60 và 0.49/0.60.
- Tăng β lên 0.2: HDV thêm 0.1 điểm, AV giảm 1.3, hệ thống giảm 0.5 điểm (p.8). β lớn hơn làm xấu cả hệ thống (p.6).
- Top 10% hơn ngẫu nhiên 10% chỉ 0.1 điểm với HDV (p.7).
- AV nhận chi phí biên chịu thiệt so với AV ích kỷ trong cùng cấu hình: top 10% là −0.18 so với +4.21 (p.8).
- 3 seed (Hình 3, p.6).

**Out of sample.** Không. Test 100 ngày trên đúng cùng OD, giờ khởi hành và tuyến.

**Giới hạn của tác giả.** Trọng số β cao làm mất hiệu năng (p.1, p.8). Chi phí phản thực (p.1-2).

**Giới hạn người đọc thấy.**
- Lời "AV cũng lợi" dựa trên +3.74 so với +3.79, chênh 0.05 trong khi độ lệch khoảng 0.7, với 3 seed (p.7, tính lại). Với toàn hệ, chênh 0.38 khi độ lệch khoảng 0.4. Tóm tắt nói "nhất quán" (p.1), nhưng bảng không đủ để gọi là có ý nghĩa thống kê.
- Giảm 40% tính cả 800k mẫu, nhưng 800k đó là chi phí trả trước, và vẫn còn khoảng 2.4 triệu lần chạy (p.8).
- Không nói rõ có giữ cùng seed SUMO khi chạy phản thực hay không ở bài này; bài trước có (2510.11410 p.4). Nhiễu do bỏ một xe không được đo.
- Bảng chỉ cho một mạng, một p, một β. Câu "giữ cho mọi thành phố" chỉ dựa trên hình.

**Liên quan: core.**
- *Mượn*: bảng ba nhóm HDV/AV/toàn hệ; so với trạng thái trước khi triển khai; quét trọng số; câu khoảng trống: "little attention has been given to designing AV routing objectives" (p.3).
- *Khác*: ta next-hop, chính sách chung, cầu thay đổi theo seed, báo cáo nhiễu, tuân thủ 90%, credit không chạy lại, có baseline app và free flow.
- *Đe dọa*: **cao với câu "mixed autonomy + mục tiêu xã hội + mạng thật + nhiều p"**: họ đã có, mạng Provins lớn hơn ta về số nút. Với claim "ít tốn hơn" cũng là áp lực: họ đã đi hướng đó, và hướng tiếp theo tự nhiên là bỏ phản thực. Nhưng bài này **vẫn chạy lại**, không xấp xỉ giải tích, không en-route. Claim còn đứng: credit không chạy lại và next-hop.
- *Cảnh báo cho `attrib`*: họ thấy trọng số xã hội lớn làm xấu cả hệ thống (p.6, p.8). Kết quả của ta ('attrib' 482.65 tệ hơn 'selfish' 471.91, chưa phải kết quả cuối) có thể cùng hiện tượng này, nên a, b suy từ J cần được kiểm tra bằng quét, dù chúng "được suy ra".

---

## 2. Psarou, Gorczyca, Gaweł, Kucharski 2025, 2510.11410 (core)

**Trích dẫn.** "Autonomous vehicles need social awareness to find optima in multi-agent reinforcement learning routing games". Preprint arXiv:2510.11410v2, 14/10/2025 (p.1). Bản đăng là tóm tắt mở rộng AAMAS 2026, tr. 3417–3419, theo tham chiếu [29] của 2610.13439 (p.10 bài đó); chưa đối chiếu bản đăng.

**Bài toán, đơn vị.** Chọn tuyến trước chuyến, lặp theo ngày (p.3). Agent là từng AV. TRY: 2 tuyến, 22 agent, 10 AV (p.5). Saint-Arnoult: 1289 nút, 2011 cạnh, 111 agent, 10 AV, 3 tuyến (p.8). Tính lại p khoảng 45% và 9%.

**Simulator, cầu, p, tuân thủ.** SUMO qua RouteRL (p.3). Cầu và giờ khởi hành không đổi (p.3). Có bản không tất định bằng cách đổi seed SUMO (p.3). Tuân thủ: không có. Người lái đóng băng sau 200 ngày (p.5).

**Thông tin.** Lựa chọn tuyến của các xe đã khởi hành (p.3). Nhận xét: như URB, không đo từ giao thông, không nhiễu.

**Reward, credit.** r = αe + βm; m là tổng tanh của chênh thời gian khi bỏ xe j (p.4, Eq.2-3), giữ nguyên joint action và seed SUMO (p.4). N lần chạy thêm cho mỗi joint action (p.4). Có hai bản: AV group và System (p.4). Nhận xét: tanh áp lên từng xe, nên m không còn là chi phí biên theo đơn vị giây; 2610.13439 đã bỏ tanh (p.4 bài đó).

**Thuật toán, ngân sách.** UCB, MAPPO, IDQN (p.5). TRY: chạm gần tối ưu sau khoảng 100 vòng (p.5); UCB khoảng 300, IDQN khoảng 400 (p.6). Saint-Arnoult: **chỉ UCB**, 300 vòng, test 10 vòng (p.8). β = 200 ở TRY (p.6), β = 0.3 ở Saint-Arnoult (p.8). Thời gian: không nêu trong bài.

**Kết quả.**
- TRY, xác định, MAPPO, giây (Bảng 1, p.5): selfish AV 62.0, người 64.4; AV group marginal 57.8, 51.9; system marginal 57.7, 51.1.
- TRY, không tất định, MAPPO: selfish 62.0, 64.3; system 57.0, 51.0 (p.5).
- Saint-Arnoult (Bảng 3, p.8): tổng hệ thống 27 493.92 (selfish), 27 494.81 (AV group), 27 488.84 (system); nhóm AV 1855.05, 1851.31, 1847.85. 6/10 AV nhanh hơn.

Seed: có "replication", số lần không nêu trong bài.

**Out of sample.** Không; test trên cùng cầu.

**Giới hạn của tác giả.** Chi phí ma trận chi phí biên; chọn có chủ đích trường hợp hiếm SO trùng UE ở TRY (p.8-9).

**Giới hạn người đọc thấy.**
- Cải thiện hệ thống ở Saint-Arnoult là 5.08 trên 27 493.92, tức 0.018% (tính lại), nằm cạnh độ lệch 15.55 của chính cột selfish. Bản AV group còn **xấu hơn** selfish 0.89 s, trong khi văn nói hệ thống giảm khi có thành phần xã hội (p.8).
- Tóm tắt nói hội tụ về SO trên cả mạng thật (p.1), nhưng Saint-Arnoult chỉ có so sánh với selfish, không có nghiệm SO.
- Bảo toàn cân bằng được chứng minh với giả định "aligned externality" cho TRY (p.8), rồi nói mở rộng dễ dàng (p.7). 2610.13439 cho thấy β lớn đổi kết quả (p.6 bài đó). Không nên trích như một định lý tổng quát.
- p.4 viết hội tụ về "user equilibrium", phần còn lại viết SO; ở TRY hai cái trùng nhau nên không sai, chỉ dễ hiểu nhầm.
- p.8 nói chi phí tăng theo cấp số nhân theo không gian joint action, nhưng thuật toán tốn N lần mỗi joint action gặp phải (p.4).

**Quan sát hay về cơ chế.** Ma trận chi phí biên **không tam giác dưới**: xe khởi hành sau có thể làm chậm xe đi trước, vì ưu tiên ở biển nhường đường, nên không có FIFO (p.6).
- *Rất liên quan tới `attrib`*: cách quy theo thứ tự hàng đợi của ta giả định trễ truyền từ xe trước tới xe sau trong cùng hàng. Bằng chứng này cho thấy một phần ngoại ứng đi qua ưu tiên ở nút, mà thứ tự hàng đợi trên một link có thể không bắt được. Phải kiểm tra trong kiểm chứng phản thực.

**Liên quan: core.**
- *Mượn*: giữ cùng seed SUMO khi so phản thực (p.4); tách AV group với System.
- *Khác*: như mục 1. Họ chỉ dùng deep MARL ở mạng đồ chơi.
- *Đe dọa*: trung bình, phần lớn đã thể hiện ở mục 1. Ý hay: tác giả không thấy khác biệt lớn giữa AV group và system marginal (p.5), tức chỉ tính ngoại ứng lên đội xe có thể đủ ở mạng đồ chơi. Với ta p < 1, thử `attrib` chỉ tính phần lên đội so với lên mọi xe là ablation rẻ, liên quan trực tiếp tới T_cust và T_all.

---

## 3. Yun, Kim, Ham, Kim 2024 (core, đối thủ gần nhất về next-hop + SO + không tuân thủ)

**Trích dẫn.** Yun, Kim, Ham, Kim. "Navigating the non-compliance effects on system optimal route guidance using reinforcement learning". Transportation Research Part C 165, 104721. DOI 10.1016/j.trc.2024.104721 (p.1). **Bản đã đăng**, open access.

**Bài toán, đơn vị.** **Next-hop**: hành động là link ra tại nút (p.6), quyết định khi xe tới nút, bất đồng bộ (p.6). Mục tiêu DSO, cực tiểu TSTT (p.5). Hai bước: (1) **một Q trung tâm** đóng vai TMC, hưởng 100% xe; (2) copy trọng số sang từng người dùng, mỗi người thêm một mạng chính sách riêng, π_i = (1−η)π_SO + ηπ_ind,i (p.10-11, Eq.10).

**Mạng, simulator, cầu.** SUMO (p.6, p.12). Nguyen-Dupuis 13 nút, 19 link, 25 tuyến, 4 OD, 600 xe (p.12). Siheung 87 nút, 206 cạnh, 6 OD, 120 xe mỗi OD, tính lại 720 xe, tác giả gọi là "large-scale" (p.18). Cầu tổng hợp, chạy tới khi mọi xe tới đích (p.12).

**p và tuân thủ.** **Mọi xe trong mạng đều thuộc hệ thống**, không có xe nền (p.12), không có p < 1. Tuân thủ mô hình bằng **một η chung** cho mọi người (p.16), không phải xác suất làm theo: mỗi lựa chọn được lấy từ hỗn hợp chính sách. Chính sách cá nhân học bằng cross-entropy trên các trải nghiệm khám phá có reward cao hơn so với làm theo hỗn hợp (p.10-11, Alg.2).

**Thông tin.** State = one-hot nút + thời gian đi và mật độ **mọi link**, số xe chờ ở mỗi nút, tổng số xe, thời gian (p.6). Nhận xét: quan sát hoàn hảo toàn mạng, lấy từ SUMO, không nhiễu. One-hot nút làm đầu vào không chuyển giao được, và lớn theo mạng.

**Reward, credit.** R(s,a) = −thời gian đi trên link đã chọn (p.7). Không có chi phí biên, không chạy lại. Bài lập luận rằng tổng của các reward này tương ứng với hàm mục tiêu DSO (p.7). Nhận xét, quan trọng: tổng đó đúng là TSTT, nhưng Q-learning tối đa hóa lợi nhuận của **từng xe** theo sau, không tính trễ gây cho xe khác. Về lý thuyết đây là reward ích kỷ với Q chung. Vậy mà bài báo cáo gần khớp DSO (xem dưới). Cách giải thích khả dĩ, của người đọc: cầu nhỏ và cố định, hoặc nghiệm DUE, DSO gần nhau hơn trên tập lặp; bài không phân tích điều này.

**Thuật toán, ngân sách.** DQN với replay, target network, γ = 0.99, ε-greedy (p.7-9). Mask hành động (p.8). Mạng lớn: mask theo 5 đường k-shortest tính trước cho mỗi OD (p.17). NFSP biến đổi (p.10-11). Hội tụ TSTT khoảng 200 đến 250 iteration ở mọi η (p.14). Tiêu chuẩn hội tụ RSG < 0.005, cửa sổ 5 (p.13). Kích thước mạng, lr, thời gian train: không nêu trong văn bản (Hình 3 ở p.11 không đọc được).

**Baseline.** DSO-Iterative (MSA với path marginal travel time, p.13), DUE tương tự (p.14). Không có free flow, không có app phản ứng theo thời gian thực.

**Kết quả, Nguyen-Dupuis (Bảng 1, p.15), TSTT giây.**

| η | 0 | 0.125 | 0.25 | 0.375 | 0.5 | 0.625 | 0.75 | DSO | DUE |
|---|---|---|---|---|---|---|---|---|---|
| TSTT | 68 108 | 68 986 | 69 114 | 70 849 | 72 087 | 76 026 | 77 921 | 68 057 | 73 273 |
| Tổng quãng đường (m) | 694 850 | 692 478 | 690 765 | 690 683 | 690 263 | 691 430 | 730 196 | 698 975 | 687 859 |

- DUE so với DSO: DSO thấp hơn 7.12% (tính lại). η = 0 thiếu DSO 0.07% (tính lại).
- Ở η = 0.25, TSTT tăng 1.48% so với η = 0; vẫn thấp hơn DUE 5.68% (tính lại).
- Từ η = 0.625 **tệ hơn DUE** (p.15).
- Siheung (p.18-19): RL η = 0 119 350; DSO-Iterative 118 834 (hơn 0.43%, p.18); η = 0.25 123 336; DUE 125 346 (p.19). Tính lại: khoảng DUE–DSO 5.2%, η = 0.25 đã mất 69% khoảng này, so với 20% ở Nguyen-Dupuis. Bài chỉ nói tăng rõ hơn ở Siheung (p.19).
- Bất định cầu: thêm cầu đều trong [0, α×50] mỗi OD, 10 seed (p.14). DSO-Iterative 70 312.2 ở α = 0.25 và 76 893.8 ở α = 1; RL 75 512.5 ở α = 1 (p.14), hơn 1.8% (tính lại).
- Gini và tỉ lệ P80/P20 tăng theo η (chỉ trên hình, p.16). Người làm theo chịu nhiều hơn (p.17).

**Thống kê, out of sample.** Bảng 1 và Siheung là một con số, không có seed hay độ lệch. Chỉ thí nghiệm §5.2 có 10 seed và là ngoài mẫu một phần (RL train trên cầu cố định, test trên cầu lệch).

**Giới hạn của tác giả.** η đồng nhất, không xét η = 1, η > 0.75 khó ổn định; chính sách TMC đóng băng khi NFSP chạy, có thể gặp dịch chuyển phân phối (p.20).

**Giới hạn người đọc thấy.**
- Bài dùng η như "mức không tuân thủ" nhưng không có nhóm người làm theo và nhóm không; câu "người làm theo chịu nhiều hơn" (p.17) không có phép đo tách nhóm trong bài.
- Khi chạy thí nghiệm bất định, xe phát sinh của DSO-Iterative đi theo đường ngắn nhất, còn RL xử lý mọi xe (p.14). So sánh đã ưu ái RL theo thiết kế, và chênh chỉ 1.8%.
- Quãng đường nhảy 5.6% ở η = 0.75 (tính lại, p.15) gợi ý xe đi vòng do học không ổn định, không phải do lựa chọn cá nhân. Bài chỉ nói "system disorder".
- Mỗi người dùng một mạng riêng nên không lớn nổi theo số xe; 720 xe là mức đã làm.
- Bài nói "large-scale" với 87 nút. Không nên lặp lại cách gọi này.

**Liên quan: core.**
- *Mượn*: định dạng so sánh RL với DSO-Iterative và DUE. **Baseline MSA + path marginal chạy thẳng được trong SUMO**, là cách trực tiếp có "approximated SO" động cho ta, tốt hơn con số assignment hiện có.
- *Khác*: agent chia sẻ chính sách, không cần copy mạng theo người; p < 1 với xe nền; tuân thủ theo xác suất; thông tin qua báo cáo nhiễu thay vì trạng thái thật; mạng lớn hơn 10 lần về số nút; cầu ngẫu nhiên; mô hình xe máy.
- *Đe dọa*: **cao với các câu "MARL next-hop + SO + có không tuân thủ" và "tuân thủ không đầy đủ trong SUMO"**. Bài này cùng tạp chí đích, đã làm trước. Câu "đầu tiên xét không tuân thủ" là sai. Đóng góp của ta chỉ còn ở tổ hợp nói trên.
- *Ủng hộ nhánh selfish*: Q chung với reward −thời gian trên link đạt gần DSO trên mạng nhỏ. Điều này hợp với số tạm của ta (selfish tốt hơn attrib ở update 125). Reviewer có thể hỏi: nếu selfish đã đủ thì cần gì credit? Phải trả lời bằng thí nghiệm, không phải lập luận.
- *Câu trích được*: tác giả ghi prior work thường dùng "static, predetermined proportions" của người UE, SO (p.4), và kêu gọi xét tỉ lệ cố định làm so sánh sau (p.20). Thiết kế p và 90% của ta chính là kiểu cố định đó, nên phải biết lý do: ở mức nhà cung cấp, p và tuân thủ đo được.

---

## 4. Ma & He 2024 (core về khái niệm, nhà cung cấp thông tin + next-hop)

**Trích dẫn.** Ma, He. "Providing real-time en-route suggestions to CAVs for congestion mitigation: A two-way deep reinforcement learning approach". Transportation Research Part B. DOI 10.1016/j.trb.2024.103014 (p.1). **Bản đã đăng** (nhận 12/6/2024). Số tập: không có trong phần văn bản trích.

**Bài toán, đơn vị.** Hai tầng học cùng lúc. CAV: agent, **chọn link kế tiếp ở mỗi nút quyết định**, ích kỷ, Markov game, γ = 1 (p.5-6). Nhà cung cấp thông tin: **một agent** gợi ý xác suất từng link ở mỗi nút quyết định, cực tiểu tổng thời gian (p.7). Khái niệm giải là correlated equilibrium (CE) (p.12-17).

**Mạng, simulator, cầu.** Braess 10 xe; Nguyen-Dupuis 4 OD, 960 CAV trong 30 phút, cầu 480, 420, 540, 480 xe/giờ (p.18-19). Thời gian link từ biểu đồ cơ bản tam giác (p.13, p.19). Simulator: **không nêu tên, không phải SUMO theo văn bản**; đoán là mã tự viết. Cầu tổng hợp, chia đều trong khung (p.19).

**p và tuân thủ.** Mọi xe là CAV, không có xe nền. **Tuân thủ là nội sinh**: CAV học có làm theo gợi ý hay không, được đẩy bằng thưởng thêm η nếu làm theo (p.11, p.14). Không có mô hình xác suất tuân thủ của người.

**Thông tin.** CAV: giờ, nút, thời gian thực tức thời của mọi sub-route từ nút hiện tại, gợi ý nhận được (p.5-6). Nhà cung cấp: thời gian mọi link liên quan (p.7). Nhận xét: tác giả xem đây là thực tế vì lấy được qua app, nhưng không nhiễu, không mất mẫu, và có thời gian của cả các đường chưa xe nào đi.

**Reward, credit.** CAV: −thời gian đi qua đoạn, cộng phần thưởng thêm theo "base unit" khi làm theo, tổng bằng η cho cả tuyến (p.6, p.11, p.20). Nhà cung cấp: −tổng thời gian mọi CAV trong bước (p.7). **Không có chi phí biên, không credit theo xe, không chạy lại.** Giá trị thời gian 0.1 USD/phút; η thử 1, 2, 3 USD ở Braess và 2, 4, 6 USD ở Nguyen-Dupuis (p.20, p.22).

**Thuật toán, kiến trúc, ngân sách.** CAV: DDQN (p.9). Nhà cung cấp: DDPG (p.10). Mạng con riêng cho từng nút quyết định của mỗi OD, nối "ảo" (p.9). Khám phá chu kỳ (p.11). Nguyen-Dupuis: không đủ tính toán để mỗi xe một mạng, nên chia **3 nhóm mỗi OD**, chung buffer và mạng (p.19). Số tập ở Braess có mốc 200 và 400 (p.18, p.22); tổng số tập, thời gian: không nêu trong văn bản.

**Baseline, kết quả.**
- Braess, tính tay và học (p.13, p.18): UE tổng 80; NE yếu [4,2,4] tổng 74; CE ví dụ 75; SO [5,1,4] tổng 70, đạt với η = 2 cộng khám phá chu kỳ.
- Không có nhà cung cấp, học dao động giữa 74 và 80 (p.18).
- Nguyen-Dupuis: **chỉ có hình** (Hình 11, p.20), 10 lần chạy, trung bình và độ lệch trên hình. Con số: không nêu trong văn bản.
- η nhỏ có thể **tệ hơn** không có gợi ý (p.18, p.22). Khám phá thêm sai thời điểm làm tệ đi (p.22).
- Baseline chỉ là chính nó khi không có nhà cung cấp. Không có MSA, DSO, app, free flow.

**Out of sample.** Không. Đường cong học trên cùng cầu.

**Giới hạn của tác giả.** Mạng thật lớn có thể không hội tụ (p.10). CE cần giả định người tin rằng người khác làm theo; η thực tế phải lớn hơn cận lý thuyết (p.18). Hướng sau: nhiều nhà cung cấp, không đồng nhất (p.23).

**Giới hạn người đọc thấy.**
- **Tiêu đề "không hy sinh UO" và Định lý 2, 4 mâu thuẫn một phần.** Theo chính chứng minh (p.15-16), tập CE có thêm η chứa những phân phối mà lệch khỏi gợi ý thì *rút ngắn được* thời gian đi. Tức là ở SO khi η^SO > 0, tuân thủ chỉ ổn định vì tiền thưởng, không phải vì thời gian. Lập luận p.22 nói không phải đánh đổi thời gian chỉ đúng theo kỳ vọng ở ví dụ Braess.
- Các định lý đều giả định "RL hiệu quả", tức hội tụ tới tối ưu (p.15). Định lý 2 còn giả định học hội tụ về CE tối ưu trong tập, điều không được kiểm tra trên Nguyen-Dupuis.
- Chỉ số thắng trên Nguyen-Dupuis không đọc được từ văn bản.
- Khám phá chu kỳ chọn sau khi nhìn đường cong (p.22) là tinh chỉnh theo kết quả.

**Liên quan: core về khái niệm.**
- *Mượn*: câu trích về khoảng trống CE: "existing studies are limited to static information provision on small networks" (p.2). Phân loại route-based và en-route, và nhắc next-hop độc lập có từ Grunitzki 2014, Bazzan & Grunitzki 2016 (p.3), nên lịch sử next-hop còn sớm hơn Koh.
- *Khác*: ta không để xe tự học, chỉ một chính sách của nhà cung cấp; tuân thủ ngoại sinh 90%; p < 1; SUMO; không có thưởng tiền; mạng lớn hơn hẳn (886 so với 13 nút).
- *Đe dọa*: **cao với câu "nhà cung cấp dẫn đường đưa gợi ý en-route, học bằng RL để giảm tổng thời gian"**: bài này đã có, ở TR-B. Không đe dọa phần xe nền, báo cáo nhiễu, credit, quy mô. Câu "tính khuyến khích" (người có muốn làm theo không) họ có còn ta không: reviewer có thể hỏi 90% tuân thủ có bền khi gợi ý làm người dùng thiệt. Với T_cust trong J, ta có một phần câu trả lời, nhưng cần đo tỉ lệ khách nhanh hơn so với đi free flow.

---

## 5. Ke, Zou, Liu, Qian 2025, TransRL (useful, gần về mục tiêu SO một phần xe)

**Trích dẫn.** Ke, Zou, Liu, Qian. "Real-time system optimal traffic routing under uncertainties — Can physics models boost reinforcement learning?". Transportation Research Part C. DOI 10.1016/j.trc.2025.105040 (p.1). **Bản đã đăng**, open access. Số tập: không có trong phần văn bản trích.

**Bài toán, đơn vị.** **Một agent trung tâm**, mỗi khoảng thời gian chọn **tỉ lệ chia theo tuyến** của OD được điều khiển (p.9-10). Không phải theo xe, không en-route.

**Mạng, simulator, cầu.** Mesoscopic CTM + node model có tràn ngược (p.10). 2-route; corridor 18 link, 16 nút (p.15); TSMO Maryland 621 link, 361 nút, 182 OD, 6:00–13:00, khoảng 15 phút (p.18). Cầu TSMO ước lượng từ đếm thật bằng DODE (p.18), sau đó nhiễu Gauss 10% (p.18).

**p và tuân thủ.** "Một phần nhỏ" xe (p.21). TSMO: 14 trong 182 OD điều khiển được (p.19), tức 7.7% số OD (tính lại), p theo xe không nêu trong bài. Không có mô hình không tuân thủ; xe thuộc OD điều khiển đi theo tỉ lệ.

**Thông tin.** Lưu lượng và tốc độ trung bình của 14 link có cảm biến, cộng thời gian (p.10, p.19). Nhận xét: **đây là mức hạn chế thông tin nghiêm nhất trong nhóm**, không nhiễu đo nhưng đo từ link cố định. Khác ta: nhiều chỗ thiếu quan sát cố định, còn ta thiếu theo báo cáo của đội xe.

**Reward, credit.** r_t = (F_t − F̄_t)/N, F_t là số xe rời vùng (p.11). Lập luận: thay vì đếm xe trên mọi link, chỉ cần theo dõi biên vùng (p.10-11). Chung một agent nên không có credit theo xe. Không chạy lại.

**Thuật toán, ngân sách.** Kiểu SAC + KL về policy thầy, thầy là pre-DSO (MSA + xấp xỉ path marginal cost của Qian 2012) bọc mạng thần kinh, Gauss, tham số σ (p.5-11). PPO, SAC làm so sánh. lr 1e-3, lô 128, γ = 1, α = 0.2 (p.22). PPO chưa hội tụ sau 2000 tập ở corridor và 1000 tập ở TSMO kịch bản B (p.16, p.19). Thời gian: không nêu trong bài.

**Baseline, kết quả.** 100 tập test, cùng seed cho mọi phương pháp (p.13, p.17, p.19). Tổng thời gian trung bình (SD):

| Mạng, kịch bản | UE | pre-DSO | PPO | SAC | TransRL | Trang |
|---|---|---|---|---|---|---|
| 2-route, β = 0.10 | 17 346.28 | 9959.54 | 11 193.19 | 9971.37 | 9817.92 (DP 9730.62) | p.14 |
| Corridor (h) | 117 540.56 | 113 351.17 | 128 814.06 | 116 072.38 | 112 380.91 (σ = 0.10) | p.18 |
| TSMO, sự cố A (h) | 129 028.95 (1932) | 135 113.66 | 126 579.58 | 128 485.32 | 126 506.81 (2002) | p.20 |
| TSMO, sự cố B (h) | 141 198.15 (3059) | 140 529.34 | 145 846.63 | 141 805.64 | 140 072.43 (2627) | p.20 |

Tính lại: TransRL hơn UE 4.39% ở corridor, 1.95% và 0.80% ở TSMO. Trên mạng thật đóng góp là **dưới 2%**, nhỏ hơn SD một tập. TransRL hơn PPO ở kịch bản A chỉ 0.06%.

Rủi ro CTTRaR (10% tập tệ nhất, p.14, p.18, p.21): PPO, SAC âm ở corridor; pre-DSO −6819.32 ở A, TransRL 3216.34 và 1506.50.

**Seed huấn luyện, thống kê.** Số seed train: không nêu trong bài. Báo trung bình, SD trên 100 tập, không kiểm định.

**Out of sample.** Có một phần: cầu mới từ phân phối. **Không** với sự cố: RL được train trên từng kịch bản sự cố cố định (p.19), trong khi pre-DSO không biết sự cố.

**Giới hạn của tác giả.** Cần định lượng lệch mô hình và nối với σ; khoảng cách mô phỏng và thực tế (p.21).

**Giới hạn người đọc thấy.**
- So với pre-DSO không công bằng ở TSMO: RL có quyền thử trên môi trường có sự cố, đúng tại vị trí đó, nên "thích nghi" gần với thuộc lòng.
- Tóm tắt nói TransRL "consistently outperforms"; bảng 1 cho thấy pre-DSO 9592.76 và TransRL 9592.45 ở cầu ít bất định (p.14), chênh 0.003% (tính lại). SAC đáng tin hơn TransRL khi bất định cao (p.14).
- p.16 ghi nhầm "σ = 0.10 ... higher than σ = 0.10".
- UE ở TSMO thực ra là tỉ lệ tuyến từ DODE (p.12), không phải nghiệm cân bằng.
- "Hundreds of links" ở đây là mạng lớn; "up to 41 links" về Lazar (p.2, p.3).

**Liên quan: useful.**
- *Mượn*: chỉ số CTTRaR để báo tập tệ nhất so với không điều khiển; so với policy tính trước kiểu pre-DSO; mức cải thiện 0.8–2% khi hạn chế thật về điều khiển và quan sát là mốc để so 0.8–3.5% của ta. Câu trích: RL thuần "struggle" trên mạng lớn khi lệch mô hình không đáng kể (p.3).
- *Khác*: agent theo xe, next-hop, báo cáo theo đội xe, vi mô, không dùng thầy. Ta không dùng thầy theo quyết định đã có (không BC). KL về thầy cũng là một dạng định hướng theo mô hình, nên nếu làm ablation phải hỏi trước.
- *Đe dọa*: **trung bình**. Bài đã làm "SO thời gian thực, p < 1, cầu bất định, quan sát hạn chế, mạng 621 link". Không còn được nói "chưa ai xét thông tin hạn chế trong SO routing". Nhưng họ theo OD, trung tâm, không vi mô, không nhiễu báo cáo.

---

## 6. Jiang, Tran, Keyvan-Ekbatani 2023 (core về credit, background về quy mô)

**Trích dẫn.** Jiang, Tran, Keyvan-Ekbatani. "Regional route guidance with realistic compliance patterns: Application of deep reinforcement learning and MPC". Transportation Research Part C. DOI 10.1016/j.trc.2023.104440 (p.1). **Bản đã đăng**, CC BY. Số tập: không có trong phần văn bản trích.

**Bài toán, đơn vị.** Agent là từng xe có thiết bị đã đồng ý, **chọn vùng kế tiếp** ở mỗi centroid (p.10). Next-hop, nhưng trên đồ thị vùng, không phải link. Quyết định đồng thời, mỗi 1 phút (p.10, p.16).

**Mạng, simulator, cầu.** Trip-based multi-reservoir, tự cài (p.6, p.15). **7 vùng** (Hình 5, p.15-16). Cùng một NMFD mọi vùng, 667 xe tắc, 5 m/s (p.15). Không có link hẻm hay nút giao. Cầu tổng hợp theo hình, 4000 s; train có nhiễu Gauss (p.15, p.17). Xe nền đi đường ngắn nhất theo khoảng cách (p.15).

**p và tuân thủ.** Mỗi xe được gắn nhãn khi khởi hành: làm theo nếu số ngẫu nhiên ≤ φ (Thuật toán 5, p.16); nhãn đã có thì **làm theo tuyệt đối** (p.4, p.6). Nhận xét: đây thực chất là **p theo xe, không phải tuân thủ theo quyết định**. "Realistic compliance" nghĩa là tách theo cá thể thay vì tỉ lệ vĩ mô. Giá trị φ dùng trong thí nghiệm: không tìm thấy trong văn bản.

**Thông tin.** Trạng thái: tốc độ mọi vùng, lưu lượng vào vừa qua; riêng: vị trí, đích, chiều dài chuyến, tỉ lệ đi thêm ζ (p.10). Giả định xe biết trạng thái toàn mạng qua liên lạc (p.6). Nhận xét: thông tin theo vùng thô nên ít đòi hỏi, nhưng không nhiễu, không mất báo cáo.

**Reward, credit.** Đây là điểm quan trọng nhất của bài với ta.
- UO: −chi phí của xe (p.11).
- **SU: difference reward không chạy lại**: r_dif = N·[G(s′) − G(s′₋ᵢ)], G là tốc độ trung bình có trọng số, G(s′₋ᵢ) **ước lượng từ NMFD** với N_c − 1 ở vùng của xe (p.11, Eq.17-19). Tính lại: chi phí một phép cộng theo vùng, O(số vùng) mỗi xe, không có mô phỏng thêm.
- Thêm phạt: r_fair khi đi quá xa, r_stay theo nghịch đảo phương sai số xe vùng (p.11-12). Tác giả nói chỉ dùng difference reward không đủ vì xe đi vòng (p.11).
- Balance: β₁·UO + β₂(1−β₁)·SU (p.12).

**Thuật toán, ngân sách.** Mạng Q riêng cho mỗi agent, kiểu VDN với trung bình Q và reward chung (p.12-13), double Q, PER (p.13). IQL làm so sánh (p.14). lr 0.001 giảm 90% ở tập 100, 200; γ = 1, lô 256 (p.17). 300 tập, 10 lần train lại; hội tụ 150 đến 200 tập (p.17). Thời gian train: không nêu trong bài. Quyết định 0.002 s; S-MPC 4.172 s, C-MPC 120.168 s, CL-MPC 47.156 s (p.19).

**Baseline, kết quả.** Ba MPC, IQL, không điều khiển. Số trung bình TTT, nhiều số đọc từ văn bản bài:
- Nhẹ: MA-SU khoảng 589 h, CL-MPC khoảng 593 h, I-UO khoảng 613 h (p.18-19); MA-UO thấp hơn I-UO khoảng 8 h (p.18); I-SU cao hơn MA-SU khoảng 14 h (p.18).
- Nặng: không có RG thì gridlock (p.19); MA-SU tốt nhất khoảng 932.5 h, S-MPC và I-UO trung bình khoảng 982.5 h; CL-MPC cao hơn MA-SU khoảng 12 h ở trung bình (p.19-20). TTT nhóm MA-SU thấp hơn I-SU khoảng 30 h (p.20).
- β₁ từ 0 tới 1: TTT từ khoảng 588 lên khoảng 605 h, TTD từ khoảng 7564 xuống 7540 km (p.21). Tính lại: đánh đổi 2.9% thời gian lấy 0.3% quãng đường.
- Thông số đường cong: ρ₁ tốt trong [50, 150], ρ₂ tốt trong [200, 400] (p.17-18).

MA-SU hơn I-UO khoảng 3.9% ở nhẹ (tính lại).

**Out of sample.** Không nêu rõ. Train có nhiễu cầu (p.17); bài không tách cầu test. Seed test: boxplot trên hình, số lần không nêu trong văn bản.

**Giới hạn của tác giả.** NMFD phải chính xác; chiều dài bằng nhau giữa các vùng, một loại xe; xe được kiểm soát tuyệt đối làm theo; xe đồng ý có thể thiệt so với xe không đồng ý, kéo tỉ lệ đồng ý xuống (p.6, p.22); hướng phân cấp xuống link (p.22-23).

**Giới hạn người đọc thấy.**
- Tên "realistic compliance" có thể làm người đọc hiểu nhầm: không có không tuân thủ theo từng quyết định.
- "Difference reward" tính trên NMFD đã biết trước; giả định NMFD đúng, trong khi ở mạng hẻm khó có NMFD. Không được kiểm chứng với mô phỏng phản thực thật.
- r_dif không phụ thuộc hành động qua cơ chế link, chỉ qua vùng; và thực tế phụ thuộc r_stay, ρ₂ phải quét (p.18). Tức trọng số lại được chọn trên chính thí nghiệm.
- Bảng 1 ghi CL-MPC 47.156 s, văn ghi 47.856 s (p.19). p.20 kết luận "SU hơn UO" từ một so sánh MA-UO với I-UO, vốn là so sánh kiến trúc, không phải reward.
- Bài nói Pareto (p.21), nhưng đường MA-B chỉ là đường nối các điểm của chính nó.

**Liên quan: core về credit.**
- *Mượn*: đường trade-off TTT–TTD, giữ quãng đường trong báo cáo; câu chữ tách "label by vehicle" và "theo quyết định"; phạt đi xa là biện pháp họ cần, cho thấy `max_detour` của ta có cơ sở. Câu trích: compliance khối chưa xét riêng xe, "overlook the inherent nature of individual drivers' compliance" (p.1).
- *Khác*: `attrib` đo trực tiếp từ link và hàng đợi vi mô thay vì NMFD; link-level; chính sách dùng chung; thêm không tuân thủ theo quyết định và báo cáo mất mát.
- *Đe dọa*: **cao với "difference reward không chạy lại cho routing MARL theo xe có p < 1"**. Bài này có đúng tổ hợp đó ở cấp vùng, 2023, TR-C. `gap_checks.md` G3 **chưa liệt kê bài này**, nên cần bổ sung. Câu còn đứng: credit đo trực tiếp ở cấp hàng đợi vi mô trên link, có kiểm chứng phản thực.

---

## 7. Ramos, da Silva, Rădulescu, Bazzan, Nowé 2020 (useful về credit)

**Trích dẫn.** Ramos, da Silva, Rădulescu, Bazzan, Nowé. "Toll-based reinforcement learning for efficient equilibria in route choice". The Knowledge Engineering Review 35, e8. DOI 10.1017/S0269888920000119 (p.1). **Bản đã đăng**. Chứng minh ở p.11-14 chỉ đọc lướt; phần phương pháp, thí nghiệm, kết luận đọc đầy đủ.

**Bài toán, đơn vị.** Chọn tuyến trước chuyến, MDP không trạng thái; mỗi tài xế một Q-table (p.5, p.7-9). k tuyến ngắn nhất, k từ 4 tới 16 (p.15-16).

**Mạng, simulator, cầu.** Mô hình vĩ mô VDF, không có simulator vi mô (p.3-4). Braess mở rộng 4 200 tài xế; OW 13 nút, 48 link, 1 700; Anaheim 416 nút, 914 link, 104 694; Eastern Massachusetts 74 nút, 258 link, 65 576; Sioux Falls 24 nút, 76 link, 360 600 (p.15). Mạng và cầu chuẩn của tài liệu. p = 1, tuân thủ không áp dụng.

**Thông tin.** Chỉ thời gian đi của chính xe và thời gian free flow (p.8-9). Tác giả nhấn mạnh: không cần biết trạng thái mạng. Nhận xét: rất nhẹ, nhưng **chỉ đúng nếu VDF đúng dạng đa thức một biến** và biết β.

**Reward, credit.** τ_l = β(f_l − F_l), tức **toll biên từ thời gian đo được và thời gian free flow** (p.8, Hệ quả 1, kế thừa Sharon 2017). r = −(f + τ) = −(f + β(f − F)) (p.9). Tính lại: O(số link trên tuyến) cho mỗi xe, **không chạy lại**. Thu sau chuyến, nên công bằng hơn thu trước (p.14).

**Thuật toán, ngân sách.** Q-learning, ε-greedy, λ, μ decay (p.9, p.16). 10 000 tập; 30 lần lặp (p.15-16). Thời gian: không nêu trong bài. Chọn tham số tốt nhất rồi mới báo (p.16).

**Baseline, kết quả (Bảng 3, p.17), độ gần SO.** TQ 0.99814, Difference rewards 0.99742, Q-learning 0.90726 trung bình. Anaheim 0.99341, 0.99678, 0.98597. Sioux Falls 0.99497, 0.99387, 0.98662. Rút ngắn trung bình 9.1% (p.1, p.17). Khoảng UE–SO trung bình quanh 9% (p.19); tác giả viện Youn 2008 nói trên mạng thật khoảng 30% (p.19). t-test 5% (p.16); "7%" cho chênh tổng thể với DR (p.17).

**Out of sample.** Không; đo ở tập cuối, cùng cầu.

**Giới hạn của tác giả.** Tốc độ hội tụ, ưa thích đồng nhất, phân phối lại thu phí, tác động khi triển khai (p.19).

**Giới hạn người đọc thấy.**
- **Kết quả phụ thuộc VDF**: mô hình không có hàng đợi vật lý, không tràn ngược, thời gian đi là hàm của lưu lượng cả tập. Bài nói công thức bao phủ hầu hết VDF, nhưng trễ do hàng đợi ở hẻm và nút giao thì không phải đa thức.
- Trung bình 0.99814 bị kéo lên bởi các mạng Braess rất nhỏ. Trên mạng thật lớn nhất (Anaheim) DR **tốt hơn** TQ, trong khi văn nói TQ tốt hơn trên mạng nhiều OD, nhiều xe (p.17). Bảng tự mâu thuẫn một phần câu đó.
- Khoảng cách trung bình 9.1% cũng phụ thuộc Braess; riêng Anaheim, Sioux Falls UE gần SO hơn nhiều: Q-learning đã 0.98597 và 0.98662.
- "Đầu tiên chứng minh" với giả định α, ε giảm trong giới hạn.

**Liên quan: useful.**
- *Mượn*: công thức τ = β(f − F) là **baseline rẻ nhất** cho `attrib`: một xe tính được từ thời gian của mình. So sánh `attrib` với "selfish + β(f−F)" là ablation có giá trị, gần như không tốn gì. Số Anaheim, Sioux Falls: Q-learning thuần đã cách SO khoảng 1.4%, đặt kỳ vọng về trần.
- *Khác*: `attrib` đo trễ theo thứ tự hàng đợi, không cần VDF; next-hop; vi mô, có tràn ngược; p < 1.
- *Đe dọa*: **cao với câu "credit từ thông tin cục bộ, không chạy lại, không cần trung tâm"**. Đã có từ 2020, và bản AAMAS 2020 được Psarou trích (2610.13439 p.3). Điều ta thêm phải là chứng tỏ `attrib` tốt hơn công thức đó **khi có hàng đợi và xe nền**, nếu không thì `attrib` thừa.

---

## 8. Akman, Psarou, Gorczyca, Varga, Jamróz, Kucharski 2025, RouteRL (useful, công cụ)

**Trích dẫn.** "RouteRL: Multi-agent reinforcement learning framework for urban route choice with autonomous vehicles". SoftwareX 31, 102279. DOI 10.1016/j.softx.2025.102279 (p.1). **Bản đã đăng**, bài phần mềm, mã MIT.

**Bài toán, đơn vị.** Chọn tuyến **trước chuyến**, mỗi tập một quyết định (p.2, p.3); hướng en-route là giới hạn ghi nhận (p.7). Agent là từng xe hoặc một fleet manager trung tâm (p.2). Người lái có mô hình Gawron, CULO, WeightedAverage (p.4).

**Mạng, simulator.** SUMO + TraCI, IDM (p.2, p.3), PettingZoo AEC, TorchRL (p.2). 11 mạng trong Bảng 2 (p.4). Ingolstadt 381 junction, 850 link; Csömör 878, 2108; Cologne 78, 149.

**p và tuân thủ.** Cologne 40/100 AV, Ingolstadt 20/100; Manhattan 12.5% trở lên (p.5-6). Tuân thủ: không có. AV đi đúng lựa chọn.

**Thông tin.** Lựa chọn tuyến của các xe trước trong cùng tập, tùy chọn giờ khởi hành (p.3). Reward chỉ có khi tới đích (p.3).

**Reward, credit.** r_k = Σφ_i·T_i, T là thời gian của chính xe, nhóm mình, nhóm kia, mọi xe; φ cho altruistic, collaborative, competitive, malicious, selfish, social (Bảng A.3-A.4, p.7). Tính T chỉ trong OD của xe và cửa sổ thời gian [t − L, t + L] (p.7). **Không chi phí biên, không chạy lại**. Nhận xét: cửa sổ không gian thời gian theo OD là một cách giảm nhiễu credit rất rẻ, gần với ý "chỉ tính người bị ảnh hưởng".

**Thuật toán, ngân sách.** MAPPO, QMIX, VDN, IPPO, IQL, ISAC (p.4, p.11). 100 tập người học (p.4), 100 tập test (p.4). 300 policy update × 100 frame ở Cologne, Ingolstadt; 20 × 20 ở Manhattan (Bảng D.5, p.11). Thời gian ở Bảng D.6: Cologne MAPPO khoảng 35 phút, QMIX khoảng 12 phút (p.11); phần còn lại không đọc hết.

**Kết quả.** Chỉ có hình: người đi lâu hơn khi có AV ác ý ở Cologne (Hình 4, p.5); IQL, VDN tốt nhất (Hình 5, p.5); tỉ lệ thời gian người/AV lớn hơn 1, giảm khi tăng thị phần (Hình 6, p.6). Không có số trong văn bản. Seed: có tham số seed tái lập, số lần chạy không nêu trong phần đã đọc.

**Out of sample.** Không; OD chuyến lặp mỗi ngày (p.7).

**Giới hạn của tác giả.** Một OD lặp, trước chuyến, chi phí SUMO, mô hình người chỉ xấp xỉ (p.7).

**Giới hạn người đọc thấy.**
- **Số mạng không khớp giữa các bài cùng nhóm**: Ingolstadt ở đây 381 junction, 850 link (p.4), còn 2610.13439 viết 850 nút, 1426 link (p.5 bài đó). Hoặc hai bản cắt khác nhau, hoặc nhầm cột.
- Manhattan ghi "93 693" và "63 734" ở cột junction, link (p.4): junction nhiều hơn link là lạ, có thể do trích văn bản hoặc nhầm cột.
- "Real-size" (p.4), nhưng thí nghiệm Manhattan chỉ 20 × 20 frame theo bảng D.5, nên không chứng minh học được.
- Tuyên bố "khung đầu tiên cho route choice hỗn hợp ở mức vi mô" (p.2) chỉ đúng với "có sẵn dùng lại", theo cách tác giả tự định nghĩa.

**Liên quan: useful.**
- *Mượn*: mã mở để đối chiếu URB; cấu trúc AV behavior; có thể dùng để chạy baseline của họ trên mạng ta nếu reviewer đòi. Cửa sổ T theo OD và thời gian.
- *Khác*: agent next-hop, cầu ngẫu nhiên, báo cáo thay vì lựa chọn xe trước, tuân thủ.
- *Đe dọa*: thấp, chỉ là hạ tầng. Nhưng nói rõ: "trên RouteRL người ta chưa làm en-route" là **do chính họ ghi ở p.7**, câu này ta trích được.

---

## 9. Kim, Yun, Kim, Kim 2025 (core về bằng chứng tuân thủ thật)

**Trích dẫn.** Kim, Yun, Kim, Kim. "Scalable link cost learning for real-time route guidance systems". Transportation Research Part C. DOI 10.1016/j.trc.2025.105244 (p.1). **Bản đã đăng**. Có tác giả từ Kakao Mobility và trùng nhóm Yun 2024. Số tập: không có trong phần văn bản trích.

**Bài toán, đơn vị.** Không phải RL đa tác tử: **bandit đơn giản trên từng link**, cập nhật hằng ngày. Link cost = W_e·T_e, W_e là hàm logistic của tỉ lệ không tuân thủ theo link (p.5-8). Chọn đường bằng tìm đường ngắn nhất (p.6). Mục tiêu là **tăng tuân thủ**, không phải giảm thời gian hệ thống (p.2, p.9).

**Mạng, dữ liệu.** **Triển khai thật** trên toàn mạng Hàn Quốc của Kakao Mobility, hơn 6 triệu link, trung bình 111 m (p.7, p.11). GPS 5/2024 tới 10/2024 (p.10, p.12). Thí nghiệm online 11–17/11/2024, hơn 18 triệu đường dẫn, mỗi nhánh hơn 9 triệu (p.18). Ô tô.

**Tuân thủ.** Đo thật. Định nghĩa PCR = |đường dẫn ∩ đường đi thật| / |đường dẫn| (p.9); khi tính đã loại 5 link gần điểm đầu và cuối (p.9).

**Thông tin.** GPS của người dùng, trung bình thời gian link cửa sổ trượt 10 phút, cập nhật mỗi phút (p.8). Nhận xét: đây là thực tế của một nhà cung cấp; rất giống báo cáo đội xe của ta, nhưng p thị phần không công bố (p.10).

**Reward, credit.** Tín hiệu là không tuân thủ theo link. Không có ngoại ứng, không chạy lại.

**Thuật toán, ngân sách.** Tìm lưới u, c (190 tổ hợp logistic + 10 tuyến tính) trên lịch sử (p.8). Chọn c = 0.005, u = 4 (p.15). Không cần GPU (p.20).

**Kết quả.**
- **PCR toàn bộ 68.12% → 68.78%** (p.18). Chỉ phần 11.59% khác đường: **64.22% → 70.87%** (p.1, p.18-19). Prefer highway 71.32 → 72.91; easy-to-drive 70.79 → 72.40 (p.19).
- PCR giảm theo quãng đường: 5–10 km 71.79 (naive), 100–300 km 57.58 (Bảng 1, p.19).
- **Tỉ lệ không tuân thủ cao ở đường nhỏ**: **hẻm hẹp 91.06%** (p.13), bến xe buýt 30.16–64.90% (p.13), đường núi 60.95% (p.13); trục lớn dưới 45.04% (p.11). Tỉ lệ giảm khi đường rộng hơn, giới hạn tốc độ và tốc độ thực cao hơn (p.11-12).
- Offline chỉ tăng 53.15 → 53.18 (p.15). Thời gian thực tế: basic giảm 68.66 s, highway giảm 75.64 s, easy-to-drive **tăng** 72.43 s (p.20). Tỉ lệ đường nhỏ giảm mọi nhóm (p.20).
- Trích của họ: van Essen 2019, nếu mọi tài xế làm theo, tổng thời gian có thể giảm khoảng 3.6% (p.9). Số thứ cấp, chưa đọc bài gốc.

**Thống kê.** Không có kiểm định hay CI trong văn bản. Cỡ mẫu cực lớn.

**Out of sample.** Có: online thật, sau khi chọn tham số trên dữ liệu lịch sử. Là thí nghiệm một tuần. Cơ chế gán nhánh chỉ viết "selected one to present" (p.18), không nói rõ ngẫu nhiên.

**Giới hạn của tác giả.** PCR không phải chất lượng tuyến tuyệt đối; trọng số tĩnh, không theo giờ; chưa tính hướng vào link; chưa tách nhóm người dùng (p.20-21).

**Giới hạn người đọc thấy.**
- "Non-compliance" gộp mọi lý do: đường hẹp, đường tắt người dân biết, GPS lỗi, đổi ý. Con số 91% ở một hẻm là một ví dụ được chọn, không phải trung bình cho hẻm.
- Không thể suy ra tuân thủ từng quyết định từ PCR. Ở Việt Nam, xe máy, đường hẻm có thể rất khác; bài không có dữ liệu xe máy. **Chiều ảnh hưởng thật cũng có thể ngược**: tài xế xe máy ở HCMC thường thích hẻm.
- Grid: "19 giá trị c" nhưng khoảng 0.001–0.09 bước 0.001 là 90 giá trị (p.8, tính lại).
- Fig 9 minh họa ổn định bằng một link được chọn (p.13).
- Trọng số phạt link hay bị bỏ qua cũng có thể đẩy xe khỏi đường nhỏ, nên tăng tải đường chính. Bài không đo tác động mạng.
- Kết quả là làm tuyến dễ theo hơn, không có chứng cứ giảm tắc.

**Liên quan: core về hiệu chỉnh.**
- *Mượn*: **đây là con số hiện trường duy nhất trong nhóm về tuân thủ**. Trong điều kiện tốt nhất, chỉ khoảng 68–73% link được dẫn được đi theo (p.18-19). Giả định 90% tuân thủ của ta phải có dải quét xuống tối thiểu khoảng 60–70%, và phải nói rõ khác đơn vị (theo quyết định với theo link trên đường dẫn). Nên thử tuân thủ **phụ thuộc loại link**, vì tuân thủ có cấu trúc theo độ rộng đường (p.11-12). Chỉ số PCR rất dễ tính trong mô phỏng để báo cáo.
- *Khác*: mục tiêu hệ thống, học chính sách.
- *Đe dọa*: **với giả định, không với tính mới**. Reviewer TR-C có thể nêu đúng bài này để bác 90% đồng nhất, nhất là khi kết quả mạng hẻm của ta dựa vào việc đẩy xe vào hẻm.

---

## 10. Hosseinzadeh, Moshahedi, Kattan 2023 (useful về độ bền theo tuân thủ)

**Trích dẫn.** Hosseinzadeh, Moshahedi, Kattan. "An MFD approach to route guidance with consideration of fairness". Transportation Research Part C. DOI 10.1016/j.trc.2023.104359 (p.1). **Bản đã đăng**, CC BY-NC. Số tập: không có trong phần văn bản trích. **Đọc chưa đủ**: p.2-4, p.9-23 phần khung, thí nghiệm, kết luận; **chưa đọc** công thức FC, AC ở p.5-8.

**Bài toán, đơn vị.** Bộ điều khiển trung tâm MPC, không học, đặt **tỉ lệ dẫn đường vùng** θ cho từng cặp vùng (p.4, p.11). Không có agent. BC tối thiểu TTT; FC công bằng tỉ lệ theo tuyến, hai cấp; AC đưa phản ứng của người vào tối ưu (p.1).

**Mạng, simulator, cầu.** **7 vùng giả định** (p.11). Plant là mô hình trip-based (p.10), 180 phút, bước 1 phút (p.12). Plant có nhiễu cầu, điều khiển chỉ biết trung bình (p.12). CasADi trong MATLAB (p.12).

**p và tuân thủ.** Tuân thủ là một hệ số tuyến tính trên tỉ lệ: γθ + (1−γ)θ′ (p.20). Quét 100, 70, 50, 30% (p.16-17), thêm 20, 10, 0% ở hình (p.22).

**Thông tin.** Số xe, lưu lượng vùng (p.4). Không nhiễu đo được nêu trong phần đã đọc.

**Reward, credit.** Không phải RL. Không có credit.

**Baseline, kết quả (Bảng 1, p.13; Bảng 2, p.17).** Tính tại 100%: NC TTT 983 381; BC −18.96%; AC −19.74%; FC −16.69%. std tốc độ: −60.57, −65.94, −84.84%. CPU mỗi vòng: BC 4.31 s, AC 61.68 s, FC 3.17 s.

| Tuân thủ | BC | FC |
|---|---|---|
| 100% | −18.96% | −16.69% |
| 70% | −15.36% | −16.60% |
| 50% | −10.73% | −14.23% |
| 30% | −8.18% | −12.23% |

Tính lại: BC mất 57% lợi ích từ 100 xuống 30%; FC mất 27% (bài ghi dưới 30%, p.18). **Có điểm cắt giữa 100 và 70%**: tối ưu cho hệ thống tốt nhất khi tuân thủ đủ, nhưng thua khi tuân thủ giảm. Dưới 20% FC mất tác dụng đồng đều (p.22).

**Seed, out of sample.** Một lần mô phỏng, không có độ lệch trong bảng. Cầu nhiễu ở plant nhưng không có tập test tách biệt.

**Giới hạn của tác giả.** So thêm với social routing, kết hợp phương án khác (p.23).

**Giới hạn người đọc thấy.**
- Kết luận FC "inherently induces higher compliance" (p.23), nhưng γ là tham số ngoại sinh trong thí nghiệm. Không có dữ liệu nào cho thấy FC làm tăng tuân thủ.
- Các phép đo "% drop" dùng hai cách khác nhau: 28.71% (p.18) và 47.07% (p.19) cùng nói về std accumulation của BC.
- Trong Bảng 2 các hàng std bị dính khi trích, nên số từng hàng cần kiểm lại trên PDF.
- Mạng giả định 7 vùng, chứng cứ mờ cho mạng hẻm.

**Liên quan: useful.**
- *Mượn*: **thí nghiệm chéo tuân thủ**: train ở 90%, test ở 70, 50, 30%, so với baseline. Câu trích: phần lớn nghiên cứu trước dùng "preset rate" tuân thủ (p.3).
- *Khác*: agent theo xe, RL, link, không có mô hình vùng.
- *Đe dọa*: thấp với tính mới. Về lập luận thì đáng lo: `selfish` của ta đang tốt và mức tuân thủ giả định cao; một kết quả "J tốt ở 90%" không chứng minh gì ở 60%.

---

## 11. Kamiński, Kraiński, Mashatan, Prałat, Szufel 2020 (useful về baseline)

**Trích dẫn.** "Multiagent Routing Simulation with Partial Smart Vehicles Penetration". Journal of Advanced Transportation 2020, 3152020. DOI 10.1155/2020/3152020 (p.1). **Bản đã đăng**, open access. Mã mở (p.1-2).

**Bài toán, đơn vị.** **Không học.** Xe thông minh đổi đường theo quy tắc k-shortest + Boltzmann mỗi U giây (p.4-5). Xe thường theo trung bình của "ngày hôm trước" và không đổi đường (p.3-4).

**Mạng, simulator, cầu.** Mã DES tự viết SmartTransitionSim.jl, trên OSM San Francisco (p.5). Tốc độ link là hàm mật độ kiểu LWR, không có hàng đợi riêng, không đèn (p.3). Số nút, link: không nêu trong bài (tệp ở GitHub, p.6). N từ 3000 tới 7500 xe, sinh **cùng lúc** từ khu tài chính sang khu dân cư (p.5, p.7). Cầu tổng hợp. Đã thử Warsaw, Winnipeg, chỉ nói định tính (p.9).

**p và tuân thủ.** α từ 0.05 tới 0.85 (p.7). Không có không tuân thủ.

**Thông tin.** **Toàn bộ tốc độ hiện tại**, không mất dữ liệu, trễ dưới 10 ms, giả định 5G (p.4-5). Nhận xét: tác giả đặt α là tỉ lệ thông minh, nhưng thông tin không phụ thuộc α, nên không có hiệu ứng "thị phần tạo ra dữ liệu".

**Reward, credit.** Không có.

**Ngân sách.** 54 000 lần chạy, 1 500 vCPU-giờ, thêm 10 000 để hiệu chỉnh (p.5). 3 lần lặp mỗi tổ hợp, CV trung bình 14% (p.5-6).

**Baseline, kết quả.**
- Baseline: α = 0 (p.5).
- N = 3000 giảm tới 15%, N = 7500 giảm tới 30% (p.7); đỉnh 32% ở 7 500 xe, U 50 hoặc 100 s (p.9). Các con số còn lại chỉ ở hình.
- **Đỉnh ở α khoảng 85%** bất kể N (p.7).
- **Đổi đường tất định (k = 1) ở α = 0.85: lợi gần 0%**, phương sai lớn (p.7); ở α nhỏ tất định vẫn dùng được (p.7).
- k = 2 tốt nhất, tăng k giảm hiệu năng (p.7). T = 0.1 tệ hơn rõ (p.7).
- U 50 so với 300 s: chênh tới khoảng 10 điểm phần trăm (p.7).

**Out of sample.** Không tách; mỗi lần lấy agent từ một pool 10 000 (p.5).

**Giới hạn của tác giả.** Rerouting đơn giản; tính tổng quát của kết luận cần xem xét (p.10).

**Giới hạn người đọc thấy.**
- **Tính lại**: lưới ở Bảng 3 cho 17 × 10 × 6 × 5 × 3 = 15 300 tổ hợp, nhân 3 là 45 900, không phải 54 000 (p.5, p.7).
- Đỉnh α = 85% **nằm ngay biên lưới** (p.7), và 100% không thử; không thể nói 85% là tối ưu.
- p.9 viết tối ưu "near 5 s", còn lưới nhỏ nhất là 50 s; có lẽ lỗi gõ.
- Mọi xe xuất phát một lúc, mạng là một làn sóng: rất dễ đem lại lợi lớn, không so được với 2% của ta.
- Bài nói ít ai làm với thành phố thật (p.1), điều không còn đúng.

**Liên quan: useful.**
- *Mượn*: **cặp quét k = 1 so với k ≥ 2 theo α** là thí nghiệm rất rẻ. Tương ứng trực tiếp với argmax so với sampled của ta và với `app`. Nên báo độ nhạy theo chu kỳ cập nhật.
- *Khác*: học, mục tiêu hệ thống, nhiễu.
- *Đe dọa*: thấp.

---

## 12. Li & Duan 2024 (background, nhưng có một ý đáng dùng)

**Trích dẫn.** Li, Duan. "Human-in-the-loop Learning for Dynamic Congestion Games". IEEE Transactions on Mobile Computing, theo ghi chú arXiv 2404.15599 và đầu trang (p.1). **Đọc chưa đủ**: tóm tắt, mở đầu, thí nghiệm, kết luận (p.1-2, p.10-11); các định lý không đọc.

**Bài toán, đơn vị.** Phân tích và **cơ chế thông tin**, không có deep RL. Người dùng đến lần lượt, tự chọn đường; nền tảng quyết định ẩn thông tin và gợi ý xác suất (CHAR) (p.1). Mạng song song, đồ thị đường thẳng (p.1); thí nghiệm là mạng lai 3 tuyến, 9 đoạn đường ở Bắc Kinh (p.10).

**Thông tin.** Điểm chính: **thông tin là nội sinh**: đi qua đường bất định thì mới biết được nó, và cũng tạo tắc (p.2). Dữ liệu lấy từ BaiduMap, 432 trạng thái, HMM hai trạng thái (p.10). 121 xe mỗi 5 phút, SD 12.33 (p.10).

**Reward, credit.** Không phải RL. Hàm chi phí xã hội dài hạn.

**Kết quả.** PoA > 2 với cận thiển (myopic), ∞ với ẩn thông tin hay gợi ý tất định, CHAR < 5/4 (p.1). 50 lần thử, 31 khe (p.10). Tổn thất so với tối ưu xã hội: CHAR dưới 5%, cận thiển khoảng 90%, ẩn thông tin khoảng 125% (p.10). Khi ρ = 1: IR cận thiển trên 1.9, ẩn trên 2.2, CHAR dưới 1.1; ρ = 0: trên 1.2, trên 1.5, dưới 1.05 (p.11).

**Out of sample.** Không; mô phỏng trên mô hình đã khớp với dữ liệu.

**Giới hạn người đọc thấy.** Nhận xét, suy đoán: số lớn như 90% đến từ mô hình đã khớp trên một mạng 3 tuyến, không phải đo tổn thất trên mạng thật. Nói về Waze và Google Maps (p.1) dựa trên giả định chúng gợi ý đường ngắn nhất.

**Liên quan: background.**
- *Mượn*: câu trích: nền tảng "do not encourage enough users to travel and learn other paths" (p.1). Với ta: **báo cáo đội xe là nội sinh**: chính sách quyết định đường nào có dữ liệu. GNN trên báo cáo có thể mù ở hẻm chính nó tránh. Cần đo tỉ lệ link có báo cáo theo policy.
- *Khác*: mạng, học, vi mô.
- *Đe dọa*: thấp.

---

## Bảng định vị

Quy ước: "—" là không có; "kn" là không nêu trong bài; số trang của nhóm 1 lấy từ `group1_routing.md`, chưa đọc lại từng bài ở lượt này. Cột chi phí là tính lại của người đọc nếu không ghi trang.

| Bài | Đơn vị agent | En-route / pre-trip | Cỡ mạng | Số agent | Simulator | p<1 | Tuân thủ | Giới hạn thông tin | Cách tính chi phí biên / credit | Chi phí cách đó | Baseline đã thắng | Out-of-sample | Loại xe |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Yun 2024 | Q trung tâm, rồi mạng riêng từng người | En-route, next-hop | 13/19; 87/206 (p.12, p.18) | 600; 720 (p.12, p.18) | SUMO | Không | η trộn chính sách (p.10) | Không, toàn mạng (p.6) | Không; −thời gian link (p.7) | Không | Gần DSO, hơn DUE ở η ≤ 0.5 (p.15) | Một phần, §5.2 (p.14) | Ô tô |
| Ke 2025 | Một agent, tỉ lệ tuyến OD | Theo khoảng 15 phút | Tới 361/621 (p.18) | 1 | CTM meso | Có, 14/182 OD (p.19) | kn, OD theo tỉ lệ | **Có**, 14 link cảm biến (p.19) | Không; số xe ra vùng (p.11) | Không | UE, pre-DSO, PPO, SAC (p.20) | Một phần (p.19) | Ô tô, xe tải (PCU) |
| Ma & He 2024 | CAV từng xe + nhà cung cấp | En-route, next-hop | Braess; 13 nút (p.18-19) | 10; 960, 12 nhóm (p.19) | Không tên, FD tam giác | Không | Nội sinh + thưởng η (p.11) | Không nhiễu (p.5) | Không; TTT cho nhà cung cấp (p.7) | Không | Chính nó không gợi ý (p.18) | Không | CAV |
| Jiang 2023 | Xe, bước vùng | En-route, cấp vùng | 7 vùng (p.15) | kn | Trip-based | Có, φ (p.16) | Nhãn theo xe, tuyệt đối (p.4) | Thô, không nhiễu (p.10) | **Difference từ NMFD** (p.11) | O(vùng) mỗi xe, không chạy lại | MPC, IQL (p.19) | kn | Một lớp |
| Ramos 2020 | Tài xế, Q-table | Pre-trip | Tới 416/914 (p.15) | Tới 360 600 (p.15) | Vĩ mô VDF | Không | — | Rất ít (p.9) | **β(f−F)** (p.8) | O(link tuyến), không chạy lại | Q-learning; ngang DR (p.17) | Không | — |
| Akman RouteRL 2025 | AV hoặc fleet | Pre-trip | 11 mạng (p.4) | 100 trong ví dụ (p.5) | SUMO | Có (p.5) | — | Lựa chọn trước đó (p.3) | φ·T (p.7) | Không | Chỉ hình | Không | AV/người |
| Kim 2025 | Bandit từng link | Dẫn đường thực, đổi khi lệch | Hơn 6 triệu link (p.7) | Người dùng thật | **Thật** | Thị phần kn (p.10) | **Đo thật** PCR (p.18) | Thực tế GPS (p.8) | Không | Không | Bản thường về PCR (p.18) | **Có**, online (p.18) | Ô tô |
| Hosseinzadeh 2023 | Trung tâm MPC | Vùng, 1 phút | 7 vùng (p.11) | — | Trip-based | — | γ tuyến tính (p.20) | Thô | Không | Không | NC, BC (p.17) | Không | Một lớp |
| Kamiński 2020 | Quy tắc xe thông minh | En-route, rule | SF, kn (p.5) | 3000–7500 (p.7) | DES LWR | Có, 5–85% (p.7) | — | Không, thông tin hoàn hảo (p.4) | Không | Không | α = 0 (p.7) | Không | Ô tô |
| Psarou 2510.11410 | AV, độc lập | Pre-trip | TRY; 1289/2011 (p.8) | 10 (p.5, p.8) | SUMO | Có, 45%, 9% | — | Lựa chọn trước đó (p.3) | **Phản thực** tanh (p.4) | N lần chạy mỗi joint action (p.4) | Selfish (p.5, p.8) | Không | AV |
| Psarou 2610.13439 | AV, độc lập | Pre-trip | 850/1426; 2173/4216 (p.5) | Khoảng 414 ở 40% (p.7) | SUMO | Có, nhiều mức (p.6) | — | Ước lượng từ xe trước (p.3) | **Phản thực chọn lọc** (p.4-5) | 4 140k, chọn lọc 2 456k (p.7-8) | Selfish (p.7) | Không | AV |
| Li & Duan 2024 | Không agent học | Pre-trip | 3 tuyến, 9 đường (p.10) | 121 xe/5 phút (p.10) | Mô hình | Theo nhóm | Theo nhóm ẩn/gợi ý (p.1) | Bài toán về thông tin | Không | Không | Cận thiển, ẩn (p.10) | Không | Ô tô |
| URB 2025 | CAV | Pre-trip | 29 mạng | 40% của 222–1035 | SUMO 1.18 | Có | — | Lựa chọn trước | Ích kỷ/nhóm | Không | Hiếm (p.8, p.35) | Không, 100 test cùng cầu | CAV |
| Shou 2022 | Xe, Q theo đích | En-route, next-hop | 69/166 | 120 + 2 100 nền | SUMO | Có | — | (nút, thời gian) | Không | Không | Không có baseline SUMO (p.22) | Không | Ô tô |
| Koh 2020 | Một DQN | En-route | 40–80 cạnh | 20–120 xe | SUMO | kn | — | Không | Không | Không | Dijkstra động (p.29) | kn | Ô tô |
| Wang 2505.20889 | Một agent | Tuyến, gán tĩnh | 13/48 | 1, phục vụ 1 700 | BPR | Không | 100% | Không | **Giải tích** (p.4) | Không chạy lại | UE; thiếu SO 0.35% (p.6) | Không | — |
| Wang 2506.17029 | Cặp OD | Tỉ lệ, tĩnh | 416/914 | 1 406 OD | BPR | — | kn | Theo OD | Gap (p.9) | Không | FW khi ít bước (p.16) | Không | — |
| **Của ta** | Xe, policy chung | En-route, next-hop | 886/1828 | p × cầu | SUMO 1.28 | Có | 90% theo quyết định | Mất 20%, sai 10%, 30% nền dùng app | Trễ đo được theo hàng đợi | O(sự kiện hàng đợi), không chạy lại | **Chưa có kết quả cuối** | Dự kiến có; số hiện tại mới trên seed chọn lọc 50000+ | Xe máy |

Hệ quả về quy mô: Saint-Arnoult, Provins, Ingolstadt, Csömör đều **lớn bằng hoặc hơn** ta, nhưng pre-trip. Trong các bài đã đọc, en-route theo xe có học lớn nhất là 87 nút (Yun), 69 nút (Shou); Ke 621 link nhưng theo tỉ lệ OD. MA-GRL (`gap_checks.md` G6) chưa đọc toàn văn, nên chưa được nói "lớn nhất".

---

## Còn lại gì chưa ai làm, nói hẹp

Chỉ trong phạm vi các bài đã đọc tới nay, cộng tìm kiếm đã ghi trong `gap_checks.md`. Scopus, Web of Science chưa chạy, nên đây không phải khẳng định "chưa ai làm".

**U1. Credit theo xe đo trực tiếp từ hàng đợi vi mô, cho policy next-hop, có đối chiếu định lượng với phản thực.**
Bằng chứng phản bác: Jiang đã có difference không chạy lại cho routing theo xe p<1, ở vùng (p.11). Ramos đã có toll cục bộ (p.8). Wang giải tích (p.4). Psarou phản thực chọn lọc (2610 p.7). Kaddoura có quy theo agent. Psarou 2510 p.6 chỉ ra ngoại ứng không FIFO, điều có thể làm hỏng ý tưởng theo thứ tự hàng đợi. **Và số tạm của ta chưa ủng hộ**: `attrib` đang thua `selfish`. Nếu không đo đối chiếu thì claim này rỗng. Đối chiếu là phần khó làm giả nhất và không bài nào làm: Psarou đo phản thực làm reward, không phải làm thước cho một xấp xỉ.

**U2. Tổ hợp: p<1 có xe nền, không tuân thủ theo từng quyết định, báo cáo mất và sai, cùng lúc, trong next-hop MARL vi mô.**
Bằng chứng phản bác: mỗi bài có vài yếu tố: Yun có η, không có p<1, không nhiễu. Ke có cảm biến thưa, p<1, không theo xe. Jiang có p theo xe. Ma có tuân thủ nội sinh. Hosseinzadeh có γ. Psarou có p. Một reviewer sẽ gọi đây là "kết hợp", không phải mới về khái niệm. Giá trị chỉ có khi **tương tác** giữa các yếu tố là đáng kể; phải đo bằng thiết kế giai thừa.

**U3. Hẻm + xe máy + điều phối hệ thống có học.**
Bằng chứng phản bác: Kim đo hẻm có tuân thủ rất thấp ở ô tô (p.13), gợi ý giả định đẩy xe vào hẻm có thể không thực. Bài Ninh Kiều (`gap_checks` G1, chưa đọc toàn văn). Đây là khác biệt về bối cảnh, không về phương pháp, nên một mình không đủ. Không có dữ liệu Mapbox hiệu chỉnh và cầu tổng hợp thì câu này yếu.

**U4. Báo cáo nội sinh trong next-hop**: policy quyết định link nào có dữ liệu.
Bằng chứng phản bác: Li & Duan đặt vấn đề ở mạng song song, không học (p.2). Ở Ke cảm biến cố định; ở Kim thị phần đủ. Chưa thấy trong MARL theo xe. Nhưng ta **chưa đo** gì về việc này; đây mới là câu hỏi, chưa phải đóng góp.

**U5. Đánh giá ngoài mẫu nhiều seed cho next-hop MARL vi mô với OD ngẫu nhiên.**
Bằng chứng phản bác: Yun §5.2 có 10 seed cầu lệch (p.14); Ke 100 tập (p.13). Đây là độ nghiêm ngặt, không phải tính mới, nên chỉ dùng làm ưu thế phụ.

**Không được nói nữa:** đầu tiên next-hop; đầu tiên xét không tuân thủ (Yun); đầu tiên nhà cung cấp dùng RL gợi ý en-route (Ma); đầu tiên credit không chạy lại (Jiang, Ramos, Wang); mạng thật lớn nhất (Provins, Saint-Arnoult); "đầu tiên xét mục tiêu hỗn hợp" (φ trong RouteRL p.7 đã có dạng tổ hợp, và J = 0.5 T_all + 0.5 T_cust chỉ khác ở trọng số).

---

## Đã có bài làm đúng như ta chưa?

**Trong 12 bài đọc lần này: chưa.** Đếm thô theo 10 thuộc tính (tính lại, phán đoán của người đọc): agent theo xe, next-hop, chính sách chung, vi mô SUMO, p<1, tuân thủ từng quyết định, báo cáo nhiễu, credit đo được, mục tiêu hệ thống, ngoài mẫu.

| Bài | Khớp rõ | Khớp một phần | Khác cốt lõi |
|---|---|---|---|
| **Yun 2024** | next-hop, SUMO, mục tiêu hệ thống | theo xe, chung (trung tâm), không tuân thủ (η), ngoài mẫu | 100% xe trong hệ, trạng thái toàn mạng, 87 nút |
| **Ma & He 2024** | theo xe, next-hop, mục tiêu hệ thống | chung theo nhóm, tuân thủ nội sinh | Không SUMO, 100% CAV, 13 nút, không credit |
| **Psarou 2610** | theo xe, SUMO, p<1 | credit (phản thực), mục tiêu xã hội | Pre-trip, độc lập, không tuân thủ, 3 seed, chạy lại |
| **Jiang 2023** | theo xe, p<1 | next-hop (vùng), credit (NMFD), mục tiêu | Không vi mô, 7 vùng, tuân thủ tuyệt đối |
| Ke 2025 | p<1, mục tiêu hệ thống | ngoài mẫu, thông tin hạn chế | Trung tâm, OD, meso |

**Bài gần nhất là Yun 2024**, TR-C, cùng tạp chí đích, cùng SUMO next-hop mục tiêu SO, và đã có nhóm tác giả tiếp tục với Kakao Mobility (Kim 2025). Rủi ro thực nhất: nhóm Yun mở rộng sang p<1 và báo cáo thực; họ có dữ liệu thật. Rủi ro lớn thứ hai vẫn là nhóm Kucharski bỏ phản thực, hoặc đi en-route.

**Chưa đọc mà có thể gần hơn**: MA-GRL Scientific Reports 2026 (`gap_checks` G6, cùng MAPPO + GAT theo xe, Monaco). Phải đọc trước khi viết phần đóng góp.

## Việc đề xuất cho `gap_checks.md` (chưa sửa)

- G3: thêm Jiang 2023 và Ramos 2020.
- G4: thêm Kim 2025 về tuân thủ thật.
- README mục 2: số nút URB đã có: Saint-Arnoult 1289/2011, Provins 2173/4216, Ingolstadt 850/1426, nhưng RouteRL ghi 381/850 cho Ingolstadt (Akman p.4), nên phải tra trực tiếp trên mạng trước khi trích.
- Có thể đối chiếu hiện trường: van Essen 2019 "3.6%" (Kim p.9) và Tang 2023 về không tuân thủ.
