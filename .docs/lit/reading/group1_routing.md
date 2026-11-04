# Ghi chú đọc, nhóm 1: đối thủ trực tiếp về MARL định tuyến

Bản 2026-11-04. Đọc từ văn bản trích từ PDF (`scratchpad/papers_txt/`), không xem hình.

Quy ước:
- `p.N` là trang của **tệp PDF**, không phải số trang in. Với URB (in 92700+), Psarou (in 3963+) và Koh (có một trang bìa) hai số này khác nhau.
- "Nhận xét:" là ý của người đọc, không phải của tác giả. Các % có ghi "tính lại" do người đọc tính từ bảng của bài.
- "Không nêu trong bài" nghĩa là không có trong phần văn bản trích. Số chỉ nằm trên trục hình thì không đọc được, nên cũng ghi như vậy.
- Tìm chuỗi trên cả 7 tệp: không tệp nào chứa `teleport`, `motorcycle`, `motorbike`, `two-wheeler`, `alley`.

Không kết luận gì về MAPPO của ta từ các bài này khi trial mới ở đầu ngân sách: chúng chỉ cho biết mức tham chiếu và việc nên thử.

---

## 1. Akman et al. 2025, URB (core)

**Trích dẫn.** Akman, Psarou, Hoffmann, Gorczyca, Kowalski, Gora, Jamróz, Kucharski. "URB - Urban Routing Benchmark for RL-equipped Connected Autonomous Vehicles". NeurIPS 2025, Datasets and Benchmarks. DOI 10.52202/085713-2787 (p.1). **Tên tệp sai chủ đề**: `CVCompliance`, trong khi bài là benchmark định tuyến và không có mô hình tuân thủ. Đây là bản đã xuất bản, có phụ lục.

**Bài toán, đơn vị điều khiển.** Chọn tuyến **trước chuyến**, mỗi tập một lần, trong 4 tuyến tính trước (p.4, p.5, p.30). Agent là từng CAV; một ngày đi làm là một tập (p.4, p.6). Tác giả nêu rõ đổi tuyến dọc đường, nhiều quyết định mỗi tập, là bài khó hơn và **chưa làm** (p.10).

**Mạng, số agent, simulator.** 29 mạng thật, 28 tiểu vùng Île-de-France và Ingolstadt (p.6). Số nút và link **không nêu trong bài**; chỉ có số chuyến và cặp OD (p.34): St. Arnoult 222, Provins 523, Ingolstadt 1035, tối đa 6924 (p.28, p.34). Với 40% CAV tính lại được khoảng 89, 209, 414 CAV. Khung nửa giờ từ 9 giờ sáng (p.24). SUMO 1.18.0 (p.25) qua RouteRL.

**Tỉ lệ thâm nhập, tuân thủ.** 40% ở Kịch bản 1 (p.7), 100% ở Kịch bản 2 chỉ trên St. Arnoult (p.33); chỉnh được từ 0 đến 100% (p.7). Không mô hình không tuân thủ: CAV tự đi. Một đội xe duy nhất (p.10). Người lái học trước, rồi giữ nguyên chính sách trong lúc CAV train (p.6). Mô hình người được đơn giản hóa có chủ đích, tham số nhiễu bằng 0 (p.30).

**Quan sát.** CAV thấy lựa chọn tuyến của các xe khởi hành trước trong cùng tập (p.5). Nhận xét: đây không phải đại lượng đo được từ giao thông, và không có nhiễu báo cáo.

**Reward, credit.** Từ thời gian đi cuối tập. Ích kỷ cho IQL, IPPO; thời gian đi của nhóm cho MAPPO, QMIX (p.8). Không có chi phí biên trong bộ chính. Có các hồ sơ hành vi ích kỷ, xã hội, vị tha, ác ý (p.5, p.7).

**Thuật toán, ngân sách.** IQL, IPPO, MAPPO, QMIX (bản TorchRL) (p.5, p.26). IQL học "mạng Q riêng cho mỗi agent" (p.5). Pha 200 ngày người học, 6 000 tập CAV train, 100 tập test; QMIX thêm bản 20 000 tập (p.8). Thời gian cho 200 + 6000 tập với QMIX: St. Arnoult khoảng 15.5 h, Provins khoảng 44 h, Ingolstadt khoảng 152.5 h (p.26).

**Baseline và kết quả.** Con người, AON (tuyến free-flow), ngẫu nhiên (p.7). 5 seed, trung bình ± độ lệch chuẩn, biểu đồ có CI 95% (p.8, p.19). Bảng 1 (p.8), đơn vị phút:

| Mạng | t_pre | MAPPO t_CAV | Ngẫu nhiên t_CAV | AON t_CAV | Tốt nhất trong RL |
|---|---|---|---|---|---|
| St. Arnoult | 3.15 | 3.51 | 3.58 | 3.01 | QMIX 3.21, WR 80% |
| Provins | 2.80 | 3.05 | 3.04 | 2.76 | IPPO 2.98, WR 0% |
| Ingolstadt | 4.21 | 4.82 | 4.81 | 4.37 | IPPO 4.71, WR 0% |

- MAPPO không vượt được ngẫu nhiên một cách rõ rệt; tác giả viết IQL và MAPPO không hội tụ, hiệu năng gần như ngẫu nhiên (p.8).
- Thời gian của người lái cũng tăng sau khi triển khai CAV (p.8, p.9).
- Độ nhạy trên St. Arnoult, 1 200 tập, % so với t_pre (p.9): MAPPO nửa cầu −5.20%, cầu gốc −9.52%, gấp đôi −61.42%. IQL −5.50%, −12.06%, −79.32%; IQL quan sát toàn cục −3.49%.
- Bản sửa IQL*, IPPO* bỏ bootstrapping trong DQN và critic trong advantage, chỉ dùng kinh nghiệm cục bộ, 2 000 tập (p.35). IQL* t_CAV: St. Arnoult 3.02, Provins 2.76, Ingolstadt 4.22, WR 100%, 100%, 0% (p.35). Bản sửa chỉ làm cho IQL và IPPO, không có cho MAPPO.
- Kịch bản 2, 100% CAV: không phương pháp nào thắng AON (p.33, p.34).

**Giới hạn do tác giả nêu.** Cùng mô hình lái cho người và CAV; chọn tuyến một lần mỗi tập; cầu cố định; một đội xe; thực nghiệm hẹp (p.10). MAPPO: tác giả chỉ *giả thuyết* do critic khó xử lý thông tin toàn cục lớn (p.9).

**Giới hạn người đọc thấy.**
- Episode lặp cùng OD và giờ khởi hành, nên bài toán khác hẳn với cầu ngẫu nhiên trong ngày của ta; không so số trực tiếp được.
- MAPPO ở St. Arnoult: 3.45 sau 1 200 tập (p.9) và 3.51 sau 6 000 tập (p.8). Nếu hai số này so được, thêm 5 lần ngân sách không giúp. Chỉ có QMIX có bản 20 000 tập.
- Bỏ critic giúp có thể chỉ vì mỗi tập chỉ có một quyết định, bootstrapping không có gì để truyền.

**Liên quan: core.**
- *Mượn*: AON là baseline khó, phải luôn báo; thêm chỉ số thời gian của người không dùng dẫn đường; winrate theo seed.
- *Khác*: next-hop nhiều quyết định, chia sẻ tham số (URB không nói rõ MAPPO của họ có chia sẻ hay không), cầu thay đổi, báo cáo nhiễu, xe máy và hẻm.
- *Thử cho ta*: critic EV 0.24–0.33 và hiện `--lam` 0.95. Bài này gợi ý ablation với lợi nhuận Monte Carlo hoặc λ cao hơn; đây là suy luận, không phải kết quả của họ.
- *Tính mới*: củng cố khoảng trống, vì họ xếp next-hop vào phần chưa làm (p.10). Không có kết quả đe dọa. Nhưng cũng không được nói mạng ta lớn hơn URB khi chưa tra số nút của họ.

---

## 2. Psarou 2026 (core, như một bản đồ dẫn tới bài đầy đủ)

**Trích dẫn.** Anastasia Psarou. "Optimizing Urban Route Choice for Autonomous Vehicles using Multi-Agent Reinforcement Learning: Doctoral Consortium". AAMAS 2026. DOI 10.65109/JTZD1181 (p.1). Là **tóm tắt luận án 3 trang**, không phải bài nghiên cứu đầy đủ. Kết quả nằm ở [11] arXiv:2502.13188 và [12] arXiv:2510.11410 (p.3).

**Bài toán.** Chọn tuyến trong RouteRL, AV và người lái trên SUMO, chơi tuần tự theo giờ khởi hành (p.1). Mạng 2 tuyến có giao cắt, Ingolstadt (p.2), Saint-Arnoult của URB (p.2). Số agent, tỉ lệ AV **không nêu trong bài**. Tuân thủ: không nêu.

**Quan sát.** Trạng thái giao thông quan sát được, không nêu chi tiết (p.1).

**Reward, credit.** Thời gian đi ích kỷ cộng chi phí biên phản thực: tổng chênh lệch thời gian của mọi agent khi có và khi bỏ agent i khỏi mô phỏng (p.2). Không đổi nghiệm cân bằng, theo tác giả (p.2).

**Thuật toán.** IDQN, IPPO, ISAC, MASAC, MAPPO, VDN, QMIX cho [11] (p.2). IDQN, MAPPO, UCB cho [12] trên mạng 2 tuyến; **riêng Saint-Arnoult chỉ dùng UCB** (p.2). Ngân sách: "nhiều vòng tương đương vài năm đi làm thật" cho [11] (p.2), không có số.

**Kết quả.** Không có bảng. Một số định lượng duy nhất: **hơn 50%** AV có thời gian ngắn hơn khi dùng reward chi phí biên ở Saint-Arnoult (p.2). Tổng thời gian hệ thống và nhóm AV giảm, không kèm số (p.2). Có nhiễu thì trên mạng đơn giản không hội tụ; ở Ingolstadt không hội tụ và hệ thống mất ổn định (p.2). Seed, thống kê: không nêu.

**Giới hạn của tác giả.** Mỗi vòng cần thêm số lần mô phỏng bằng số AV (p.2). Hướng sau: chỉ tính chi phí biên cho agent ảnh hưởng tới nhiều xe (p.2).

**Giới hạn người đọc thấy.** Kết quả chi phí biên trên mạng thật dùng UCB, không phải deep MARL, nên chưa chứng minh chi phí biên chữa được cho MAPPO trên mạng lớn.

**Liên quan: core.**
- *Mượn*: chi phí biên phản thực là chuẩn đối chiếu cho reward `attrib`, đo trên một mẫu nhỏ.
- *Khác*: `attrib` quy trễ đo được cho xe gây ra, không chạy lại, next-hop, trên mạng lớn.
- *Tính mới*: **đe dọa trực tiếp và đang tăng**. Hướng tương lai của họ (p.2) đi đúng về phía chi phí biên ít tốn. `gap_checks.md` đã ghi bản 2610.13439 có chạy phản thực chọn lọc. Cần đọc toàn văn [12] và bản đó.

---

## 3. Shou, Chen, Fu, Di 2022 (core)

**Trích dẫn.** Shou, Chen, Fu, Di. "Multi-Agent Reinforcement Learning for Markov Routing Games: A New Modeling Paradigm For Dynamic Traffic Assignment". Transportation Research Part C 137, 103560. DOI 10.1016/j.trc.2022.103560 (p.1). Tệp là **preprint arXiv:2011.10915v2**, không phải bản nhà xuất bản (p.1).

**Bài toán, đơn vị.** **Next-hop**: mỗi xe chọn link kế tiếp ở mỗi nút cho tới đích hoặc hết giờ (p.3). Agent là từng xe. Mục tiêu DUE, agent ích kỷ (p.5, p.16). Dạng hợp tác chỉ được định nghĩa (p.9), các ví dụ không chạy.

**Mạng, simulator.** Mạng đơn giản với PQ, SQ, CTM, LTM (p.15); có spillback (p.17); OW 13 nút 24 link, 20 agent (p.19); **thượng Manhattan 69 nút, 166 link trên SUMO** (p.19). Ở SUMO: 120 agent thuộc 4 OD, khoảng 2 100 xe nền, 1 000 s, một tai nạn từ 180 đến 490 s (p.20, p.21).

**Tuân thủ.** Mặc định đầy đủ: xe tự chủ hoặc người lái làm theo hoàn toàn (p.1, p.5). Tỉ lệ thâm nhập không quét.

**Quan sát.** Chỉ (nút, thời gian) (p.8). Mean action là lưu lượng trên link đã chọn ngay sau khi vào (p.9); lúc chọn thì lấy kỳ vọng (p.10). Nhận xét: rất tiết kiệm, không cần cảm biến, nhưng không phản ứng được với trạng thái hiện tại. Tác giả nói agent "đã học được" tai nạn (p.21). Vì tai nạn lặp đúng giờ mỗi tập, agent thuộc lòng, không phản ứng với sự cố ẩn.

**Reward, credit.** Âm thời gian đi (p.8, p.16), γ = 1 (p.8). Không có chia công: ích kỷ. Mean action là cách nắm cạnh tranh (p.9).

**Thuật toán.** MF-MA-DQL, value-based, replay, target network (p.10). Hàm Q dùng chung theo nhóm, ở SUMO là **một Q cho mỗi đích**: Q60 và Q1 (p.20). Tác giả cho rằng value-based hợp với số lối ra thay đổi, còn policy-based thì không (p.11).

**Ngân sách, thời gian (p.22).** 300 tập, 12 h, trong đó mô phỏng 10 h, ở SUMO. Ví dụ nhỏ: 1 phút 29, 6 phút 37, 2 phút 07; điểm bất động 11 s, 57 s, 19 s.

**Kết quả.**
- Mạng đơn giản: thời gian trung bình hội tụ về 13.7, khớp iterative (p.17); có spillback 26 (p.18); OW khoảng 5.5 (p.19).
- SUMO: **ban đầu trên 900 s, một số xe có thể chạm trần 1 000 s; sau 50 tập còn khoảng 600 s; ổn định khoảng 570 s sau 100 tập** (p.21).
- **Không có baseline ở ví dụ SUMO** (p.22 ghi "—" ở cột điểm bất động); không so với free-flow hay app. Seed, độ lệch: không nêu.

**Giới hạn của tác giả.** Chưa có chọn giờ khởi hành, điều khiển tốc độ; chỉ quyết định khi đến nút (p.23).

**Giới hạn người đọc thấy.** Chỉ 4 OD, 2 Q, cầu lặp. Bài ghi tai nạn trên link 26–27 rồi 25–27 (p.21). Con số 570 s không cho biết thuật toán có hơn đi tuyến free-flow không. Không chứng minh hội tụ về DUE ở SUMO.

**Liên quan: core.**
- *Mượn*: làm mốc lịch sử cho next-hop; dạng hội tụ của xe bị cắt ở trần (p.21) khá giống 66% xe bị cắt ở 900 s của ta, và ở họ nó giảm rất sớm, nhưng trên 4 OD lặp lại nên chỉ là mức tham khảo. Điều kiện hóa theo đích, phần `togo` của ta đã làm.
- *Khác*: ta có attention trên lối ra, nên lập luận p.11 không áp dụng; có báo cáo trạng thái; có mục tiêu hệ thống; có baseline; OD thay đổi.
- *Tính mới*: **"next-hop MARL trong SUMO" không còn mới từ 2022**. Không được viết là đầu tiên. Bài này không đe dọa phần chia công hay hẻm.

---

## 4. Wang, Duan, Lyu, Ma, RL Sequential Route Recommendation (useful)

**Trích dẫn.** Wang, Duan, Lyu, Ma. "Reinforcement Learning-based Sequential Route Recommendation for System-Optimal Traffic Assignment". Tệp là **preprint arXiv:2505.20889v1**, 27/5/2025, "submitted to the IEEE" (p.1). Bản đăng theo `candidates.md`, không phải theo tệp: IEEE OJITS 2026, DOI 10.1109/ojits.2026.3696779; chưa đối chiếu nội dung với bản đó. Tên tệp ghi 2026 và `RouteEquilibrium`, thực ra mục tiêu là SO.

**Bài toán, đơn vị.** **Một agent trung tâm** gợi ý tuyến cho từng người lần lượt (p.2). Gán luồng tĩnh, BPR, không simulator (p.3, p.6). Braess, 6 người (p.4); OW 13 nút 48 link, 1 700 người (p.5). **Tuân thủ 100%** để tách biệt phần chính sách (p.2).

**Quan sát.** Thời gian, lưu lượng, marginal trên mọi cạnh, cộng OD và marginal theo tuyến (p.4). Nhận xét: thông tin toàn cục và cần biết hàm BPR, không khả thi ngoài thực tế.

**Reward, credit.** Âm **marginal travel time giải tích** của tuyến: tổng c + v·dc/dv (p.3, p.4). Không chạy lại mô phỏng.

**Thuật toán.** Double dueling DQN (p.3), MSA dẫn hướng khám phá (p.4). Hai tầng 512, 256; γ 0.95; lr 2e-5; lô 128 (p.6). Braess ổn định sau khoảng 240 tập (p.5). OW: số tập chỉ ở hình, không nêu trong văn bản. Thời gian train không nêu.

**Baseline, kết quả (p.6).** MSA, FW cho UE và SO. Tổng thời gian: UE-MSA 57 052.1, SO-MSA 54 809.8 (SO hơn UE **3.93%**). RL: MSA-guided 55 000 (cách SO 0.35%, hơn UE 3.60%); RL-SO 54 950 (0.26%); RL-15-SP 55 220 (0.75%); RL-10-SP 56 720 (3.49%). Braess đạt SO: 498 phút, 83 mỗi người (p.5). Seed, thống kê: không nêu.

**Giới hạn của tác giả.** Tĩnh; hướng sau là tuân thủ một phần, cầu ngẫu nhiên, động (p.6).

**Giới hạn người đọc thấy.** RL cần bước MSA trong lúc train để khám phá; số RL được làm tròn; không có trạng thái thật theo thời gian.

**Liên quan: useful.**
- *Mượn*: mức 3.93% cho thấy khoảng UE–SO có thể nhỏ; nên ước lượng trần tương ứng trên mạng ta trước khi đọc kết quả. Tập hành động ảnh hưởng mạnh (3.49% so với 0.75%), hợp với việc kiểm tra `max_detour`.
- *Khác*: nhiều agent chia sẻ chính sách, next-hop, SUMO, trễ **đo được**, tuân thủ 90%.
- *Tính mới*: **đe dọa câu "reward kiểu chi phí biên không cần chạy lại"**: họ đã có, chỉ khác là giải tích. Cùng nhóm tác giả ghi sẽ làm tuân thủ một phần và động (p.6).

---

## 5. Wang et al. 2025, MARL-OD-DA (useful)

**Trích dẫn.** Wang, Duan, Lyu, Wang, He, Zheng, Ma. "Scalable and Reliable Multi-agent Reinforcement Learning for Traffic Assignment". Tệp là **preprint arXiv:2506.17029v1**, "submitted to Elsevier" (p.1). Bản đăng theo `candidates.md`: Commun. Transp. Res., DOI 10.1016/j.commtr.2025.100225.

**Bài toán, đơn vị.** Agent là **cặp OD**, không phải xe; hành động là tỉ lệ chia cầu trên tối đa 6 tuyến (p.3, p.7, p.10). Bài toán lặp gán luồng tĩnh với BPR, không có thời gian thực (p.12, p.16). OW 4 OD; SiouxFalls 24 nút, 76 link, 528 OD, 360 600 xe; Anaheim 416 nút, 914 link, 1 406 OD, 104 694 xe (p.11). Tuân thủ: không nêu.

**Quan sát.** Tĩnh theo OD và tuyến; động theo tuyến: marginal, v/c, số link tắc, tỉ lệ cầu bước trước (p.6, p.7). "Cục bộ" theo OD, nhưng đại lượng lấy từ mô hình giải tích.

**Reward, credit.** Thay đổi local relative gap giữa các bước (p.9). Không phải credit theo xe.

**Thuật toán, ngân sách.** IPPO, Dirichlet, action pruning (p.8, p.10, p.13). Hidden 512, 3 tầng, lr 4e-5, lô 512, γ 0.75, 50 bước mỗi tập, 5 rollout worker (p.12). Tổng số tập, thời gian train: không nêu trong văn bản.

**Kết quả.** Gap nhỏ nhất trong 50 bước (p.15): SiouxFalls 0.001702, Anaheim 0.000869, OW-cố định 0.000218, so với MARL-Traveler 0.001587 ở OW-cố định. Trung bình 5 thí nghiệm (p.14), không có độ lệch. Sau 10 bước ở SiouxFalls: 0.004626 so với FW 0.092301, hơn 94.99% (p.16). **Cho nhiều bước hơn, FW đuổi kịp**, RL chững lại do sai số xấp xỉ (p.16). MARL-Traveler vượt bộ nhớ GPU trên hai mạng lớn (p.14).

**Giới hạn của tác giả.** Khung giải tích đơn giản, chưa có mô phỏng độ trung thực cao (p.16).

**Giới hạn người đọc thấy.** MARL-Traveler là bản tác giả tự cài với quan sát chỉ gồm OD, không phải mã gốc của Shou (p.13), nên là baseline yếu. Khó triển khai: một agent OD không biết trạng thái dọc đường.

**Liên quan: useful.**
- *Mượn*: câu trích về quy mô: các phương pháp MARL họ rà có mạng lớn nhất không quá 69 nút và 166 link (p.2). Phân loại route-based và en-route (p.4). Lời thừa nhận FW đuổi kịp (p.16) là mẫu báo cáo trung thực.
- *Khác*: agent là xe, đơn vị next-hop, động, vi mô.
- *Tính mới*: không đe dọa trực tiếp, chỉ là đường mở rộng khác (nhóm cầu theo OD). Reviewer có thể hỏi vì sao không gộp theo OD; cần câu trả lời: chính sách next-hop dùng chung đã không tăng theo số xe, và cần phản ứng trong chuyến.

---

## 6. Su et al. 2022, EMVLight (background)

**Trích dẫn.** Su, Zhong, Chow, Dey, Jin. "EMVLight: a Multi-agent Reinforcement Learning Framework for an Emergency Vehicle Decentralized Routing and Traffic Signal Control System". **Preprint arXiv:2206.13441v3**, "submitted to Transportation Research Part C" (p.1). **Tên tệp `MARLRouting` gây hiểu lầm**: agent là đèn tín hiệu, định tuyến không học.

**Bài toán, đơn vị.** Agent là **nút giao**, chọn 1 trong 8 pha mỗi 5 s (p.16). Định tuyến cho **một xe khẩn cấp** bằng Dijkstra động, không phải RL (p.13, p.15). Xe khác không được định tuyến. Lưới 5×5, Manhattan 16×3, Hangzhou 4×4, SUMO (p.20–p.24). Không có tỉ lệ thâm nhập hay tuân thủ.

**Quan sát, reward, thuật toán.** Số xe ở làn của mình và hàng xóm, vòng từ, V2I, ETA, Next (p.16–p.18). Pressure; phạt −1 mỗi bước cho nút có xe khẩn cấp đang tới (p.17). Credit theo loại agent và **spatial discount** α = 0.9 (p.19, p.53). MA2C, LSTM, fingerprint (p.18, p.19, p.53). Tóm tắt nói "policy sharing" (p.1), mô tả lại dùng θ_i riêng (p.18).

**Baseline, kết quả.** Walabi + (A* tĩnh hoặc động) + FT, MP, CDRL, PressLight, CoLight (p.25, p.26). 5 lần chạy, trung bình ± độ lệch (p.26, p.27). Manhattan: T_EMV 292.82 so với tốt nhất 501.26; T_avg 782.13 so với 855.28 (p.31). Hangzhou: 194.52 so với 319.84; 331.42 so với 366.14 (p.32). Hội tụ trong khoảng 500 đến 1 000 epoch (p.30, p.33). Bỏ fingerprint thì hội tụ chậm và dao động hơn (p.37). Tóm tắt nêu tối đa 42.6% và 23.5% (p.1).

**Giới hạn.** Tác giả: cần rất nhiều vòng cập nhật; chưa có nhiều xe khẩn cấp (p.38). Người đọc: số trong bài không nhất quán. Manhattan ghi 38% so với W+static+CL (p.30), tính lại 41.6% so với W+dynamic+CL hoặc 46.3% so với W+static+CL. Hangzhou ghi "115 s (37%)" (p.31), tính lại 125 s, 39.2%. Hình 17 ghi 277.20 và 228.42 (p.35), bảng 8 ghi 377.20 và 328.42 (p.32). Hệ số dự phòng 0.2 (p.22) và 0.25 (p.29). Bảng 9 ghi Hangzhou 5×5 (p.36).

**Liên quan: background.** Không đe dọa tính mới: khác bài toán. *Mượn* tùy chọn: spatial discount là một cách chia công khác, có thể làm ablation. Fingerprint không cần vì ta chia sẻ tham số. Ta không dùng để chứng minh RL thắng trong định tuyến.

---

## 7. Koh et al. 2020 (useful)

**Trích dẫn.** Koh, Zhou, Fang, Yang, Yang, Yang, Guan, Ji. "Real-time deep reinforcement learning based vehicle routing and navigation". Applied Soft Computing 96, 106694. DOI 10.1016/j.asoc.2020.106694 (p.1). **Tên tệp `Sang_2020` sai tác giả**: Songsang Koh, họ là Koh. Bản **accepted manuscript** trên White Rose (p.1).

**Bài toán, đơn vị.** Chọn cạnh kế tiếp trong "decision zone" trước nút (p.12, p.14). Bài nói mỗi xe có một agent (p.12), kết luận nói dẫn đường mọi xe (p.30), nhưng **số xe do agent điều khiển trong mỗi thí nghiệm không nêu trong bài**. Thuật toán là một DQN, một replay (p.19), nên về thực chất là RL đơn agent. SUMO + TraCI (p.8, p.9). Liverpool 40, 60, 80 cạnh (p.27), 20 đến 120 xe (p.29). Tuân thủ: không nêu.

**Quan sát.** Số xe và tốc độ trung bình trên các cạnh, cộng tọa độ xe và đích (p.14). Đọc trạng thái thật qua TraCI (p.22). Nhận xét: quan sát hoàn hảo.

**Reward, credit.** −(T_{t+1} − T_t), thời gian tức thời, ích kỷ (p.16). Không có credit nhiều xe.

**Thuật toán, ngân sách.** Double, dueling, prioritized replay (p.5, p.17); khám phá thiên về cạnh gần đích theo khoảng cách (p.17). 10 000 tập, lr 0.001, γ 0.99, replay 10 000, lô 32 (p.22, p.23). Bản đồ đơn giản hội tụ trong 1 000 tập (p.24). Quyết định 2.7 ms (p.24). Thời gian train: không nêu.

**Baseline, kết quả.** GDUE-Dijkstra, GDUE-A*, Dynamic-Dijkstra, Dynamic-A*, Ant Colony (p.23, p.24). 100 lần chạy mỗi điều kiện; Wilcoxon, mọi p < 0.05 (p.28, p.29). Bảng 5 (p.29), RL so với Dynamic-Dijkstra: map 1 với 50 xe 84.06 so với 90.84; map 3 với 120 xe 159.02 so với 194.32. Thắng ở cả 9 điều kiện. Số seed huấn luyện: không nêu.

**Giới hạn.** Tác giả: chỉ dữ liệu mô phỏng, chưa có phát thải (p.30, p.31). Người đọc: mạng quá nhỏ và ít xe. Bài ghi giảm tối đa 16.4% ở map 1, 50 xe và 4.9%, 12.4%, 22.5% ở map 3 (p.28), nhưng bảng 5 cho 12.0% và 12.3%, 18.6%, 23.7% (tính lại). Công thức 5 viết softmax của (D − D̄)/σ (p.17), đọc theo mặt chữ thì cạnh **xa** đích có xác suất cao hơn, trái với ý định; không kết luận được cách họ cài.

**Liên quan: useful.** *Mượn*: Wilcoxon theo cặp, nhiều lần chạy; baseline Dynamic-Dijkstra tương ứng `app`. *Khác*: quan sát báo cáo, chia sẻ cho nhiều xe, mục tiêu hệ thống, mạng lớn hơn trên 20 lần (tính theo số cạnh). *Tính mới*: cùng với Shou, xác nhận "edge choice RL trong SUMO" đã có từ 2020, không đe dọa gì khác. Khám phá thiên theo khoảng cách không phải BC, nhưng `max_detour` và `togo` của ta đã làm phần lớn việc này.

---

## Bảng so sánh

| Bài | Đơn vị agent | Cỡ mạng | Số agent | Simulator | Thông tin một phần | Chia công | Thắng baseline người/UE? |
|---|---|---|---|---|---|---|---|
| URB (Akman 2025) | Từng CAV, tuyến trước chuyến, 4 lựa chọn | 29 mạng; nút/link không nêu | 40% của 222 đến 1035 chuyến trong thí nghiệm (p.8, p.34) | SUMO 1.18 | Có, nhưng là lựa chọn xe trước; không nhiễu (p.5) | Ích kỷ hoặc nhóm (p.8) | **Hiếm**: chỉ QMIX ở mạng nhỏ nhất, WR 80%; IQL* WR 100% ở 2 mạng (p.8, p.35) |
| Psarou 2026 | Từng AV, tuyến | 2 tuyến; Ingolstadt; St. Arnoult | Không nêu | SUMO | Không nêu chi tiết | Chi phí biên phản thực, thêm N lần chạy (p.2) | Giảm so với ích kỷ, không có số; không so người trong tóm tắt (p.2) |
| Shou 2022 | Từng xe, **next-hop** | 69 nút, 166 link (p.19) | 120 + 2 100 nền (p.20) | SUMO; LTM... | (nút, thời gian) + mean action (p.8, p.9) | Không, ích kỷ | Khớp DUE trên mạng nhỏ (p.17–19); **SUMO không có baseline** (p.22) |
| Wang tuần tự (2505.20889) | **Một** agent trung tâm, tuyến | 13 nút, 48 link (p.5) | 1, phục vụ 1 700 | Không (BPR) | Không, toàn cục (p.4) | Marginal giải tích (p.4) | Có, hơn UE 3.60%, thiếu SO 0.35% (p.6), tĩnh |
| Wang OD (2506.17029) | Cặp OD, tỉ lệ chia | Tới 416 nút, 914 link (p.11) | Tới 1 406 OD | Không (BPR) | Theo OD, số từ mô hình (p.6) | Local relative gap (p.9) | Hơn MSA/FW khi ít bước; FW đuổi kịp (p.16) |
| EMVLight (Su 2022) | Đèn tín hiệu; định tuyến không học | Tới 16×3 (p.23) | Số nút giao; 1 xe khẩn cấp | SUMO | Có, hàng xóm (p.18) | Theo loại agent + spatial discount (p.17, p.19) | Không có baseline người; thắng MP, CoLight... (p.31, p.32) |
| Koh 2020 | Một DQN cho xe, **next-hop** | 40–80 cạnh (p.27) | Không nêu; 20–120 xe trong map (p.29) | SUMO | Không, trạng thái thật (p.14) | Không, ích kỷ | Có, thắng GDUE và dynamic trong 9 điều kiện (p.29), mạng nhỏ |
| **Của ta** | Từng xe, next-hop, chia sẻ tham số | 886 nút, 1828 link, đa số hẻm | Tỉ lệ p của cầu 4000–10000 chuyến/giờ | SUMO 1.28 | Báo cáo nhiễu: mất 20%, lệch 10% thời gian, 30% nền dùng app khác; tuân thủ 90% | Quy trễ đo được + shaping | Chưa có kết quả cuối |

## Ngân sách train đã báo cáo

Quy đổi của ta: `sumo_marl.py` dòng 36 có lệnh mẫu `--workers 32 --updates 400`, mặc định số tập mỗi update bằng số worker. **Nếu** run dùng đúng vậy thì update 25 khoảng 800 tập, update 400 khoảng 12 800 tập, 12 bước Adam mỗi update. Cần xác nhận với run thật. Khác đơn vị: tập của ta có hàng nghìn xe dùng chung một chính sách, trong khi họ thường lặp cùng tập chuyến, nên mỗi tập không so được một đổi một.

| Bài | Ngân sách | Kết quả tại mức đó | Nguồn |
|---|---|---|---|
| URB, MAPPO, IPPO, IQL, QMIX | 6 000 tập (+200 người, +100 test) | MAPPO, IQL gần ngẫu nhiên | p.8 |
| URB, QMIX | 20 000 tập | Tốt hơn ở 2 mạng, không vượt bản ngắn ở Provins | p.8, p.9 |
| URB, độ nhạy | 1 200 tập | MAPPO −9.52% tại cầu gốc | p.9 |
| URB, IQL*, IPPO* | 2 000 tập | IQL* WR 100% ở 2 mạng | p.35 |
| URB, thời gian | 15.5 h, 44 h, 152.5 h (QMIX) | | p.26 |
| Psarou [11] | "vài năm đi làm thật" | Có thuật toán vẫn không đạt tối ưu | p.2 |
| Shou, SUMO | 300 tập, 12 h | Trung bình khoảng 570 s, ổn định sau 100 tập | p.21, p.22 |
| Shou, mạng nhỏ | Khoảng 350, 1 000, 500 tập (trục hình); 300 tập để OW ổn định | Khớp DUE | p.17–p.19 |
| Wang tuần tự, Braess | Khoảng 240 tập | Đạt SO | p.5 |
| Wang OD | 50 bước mỗi tập, 5 worker; tổng không nêu | | p.12 |
| EMVLight | 500 đến 1 000 epoch; 5 s mỗi bước | Hội tụ | p.30, p.33, p.53 |
| Koh | 10 000 tập; bản đồ đơn giản dưới 1 000 tập | Thắng 9/9 điều kiện | p.23, p.24 |

Đọc bảng: ngân sách ta dự kiến (khoảng 12 800 tập, nếu đúng giả định) đã lớn hơn phần lớn các bài, và URB cho thấy ngân sách lớn không tự đảm bảo vượt AON. Vì vậy update 25 chưa nói được gì, và đi hết 400 update cũng chưa bảo đảm gì.

## Việc tiếp theo do nhóm này gợi ra

1. Đọc toàn văn Psarou [11], [12] và 2610.13439 (`gap_checks.md`), vì tóm tắt 3 trang không đủ để đánh giá đe dọa.
2. Tra số nút và link của các mạng URB trước khi nói gì về quy mô.
3. Ước lượng khoảng cách UE và SO trên mạng ta để biết trần lợi ích.
4. Ablation critic: λ cao hơn hoặc Monte Carlo, trên checkpoint thật, theo đúng quy tắc chẩn đoán trước khi sửa.
5. Báo thêm thời gian của người không dùng dẫn đường, vì URB thấy nhóm này bị thiệt (p.8, p.9), và tách được từ dữ liệu của T_all và T_cust.
