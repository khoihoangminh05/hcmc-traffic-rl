# Ghi chú đọc, nhóm 2: reward và training

Thiết kế đang so sánh: `ml-core/routing2/sumo_marl.py` (reward `attrib`, shaping, GAE, PPO).

**Quy ước.**
- `p.N` là trang PDF, lấy theo form-feed của text đã trích.
- Riêng Ng 1999, form-feed cũng là ký tự ligature "fi" (84 đoạn). Ranh giới 10 trang thật được dựng lại từ các form-feed không nằm giữa từ, khớp với 10 trang trong `_index.json`. Số trang của Ng vì vậy là suy ra, chưa đối chiếu với PDF.
- "(tính)" là số tôi tự suy ra từ số liệu trong bài hoặc từ code, bài không in số đó.
- "không nêu" là không có trong text đã trích.
- Các bài deep MARL trong nhóm thử tối đa khoảng 30 agent; Michailidis có 200 agent nhưng là Q-learning stateless. Mọi kết luận cho hàng nghìn agent của ta là ngoại suy.

---

## 1. Castellini et al. 2022, Dr.Reinforce

**Citation.** J. Castellini, S. Devlin, F. A. Oliehoek, R. Savani, *Difference Rewards Policy Gradients*, arXiv:2012.11258v2, 9/11/2023 (p.1). **Preprint** ("A PREPRINT", p.1); bản tóm tắt ở AAMAS'21 pp.1475-1477 (ref [8], p.20). DOI: không nêu. Năm 2022 trong tên file không khớp với ngày trên bản này.

**Ý tưởng và công thức.**
- Difference reward: ΔR_i = R(s,a) − R(s,⟨a_−i,c_i⟩), với c_i là default action (Eq.4, p.3).
- Aristocrat utility bỏ c_i: ΔR_i = R(s,a) − E_{b_i∼π_i} R(s,⟨a_−i,b_i⟩) (Eq.5, p.3).
- Dr.Reinforce dùng REINFORCE, không có critic, với return là tổng ΔR đã discount (Eq.6-7, p.4).
- Dr.ReinforceR học reward network R_ψ(s,a) bằng hồi quy MSE (Eq.8, p.4), rồi tính ΔR = r − Σ π_i(c_i) R_ψ(s,⟨c_i,a_−i⟩). Chi phí tuyến tính theo |A_i| (Eq.9, p.5).

**Cách ước lượng counterfactual.** Dùng reward function đã biết, hoặc reward network tập trung. Không chạy thêm simulation (p.4-5).

**Giả định của lý thuyết.**
- MMDP full observability, reward chung (p.2). Khi đó difference return tương đương trừ đi một baseline không phụ thuộc a_i, nên expected gradient không đổi (Lemma 1, p.5-7).
- Dưới partial observability baseline **không còn unbiased**, nên không có đảm bảo hội tụ (Observation, p.13-15; p.18).

**Setting của ta phá gì.**
- Actor bị partial observability, nên đảm bảo trên không áp dụng.
- `attrib` không có dạng R − b(a_−i): nó cộng charge theo queue order chứ không so với counterfactual. Tính chất "tăng D thì tăng global" (p.3) **chưa được chứng minh cho attrib**.

**Scale.** Grid với N = 3, 5, 8 (p.8-9); SMAC đến 25m và 27m_vs_30m (p.15-17). Khoảng cách giữa các method **thu hẹp khi N tăng** trên multi-rover (p.8).

**Kết quả.**
- Grid: median và percentile 25-75, 30 run (p.8, p.10), nhưng phụ lục ghi mỗi thí nghiệm lặp 10 lần (p.24). Bài tự mâu thuẫn ở điểm này.
- SMAC: 10 run (p.15). t-test có hiệu chỉnh Bonferroni (p.25).
- Kết quả chỉ có dạng đồ thị, **không có bảng số**.
- COMA rất kém ở predator-prey (p.10). so_many_baneling là phản ví dụ: difference return đẩy agent về hành động thưởng ngắn hạn (p.15).
- Thử nhiễu (N=3, uniform policy, 1000 mẫu): chịu được nhiễu đối xứng normal/uniform; **0-masking gây hại rõ nhất**, nặng hơn khi reward dày (p.11-12).

**Liên quan: CORE.**
- *Kiểm tra:* 60% quyết định có charge = 0. Nếu đó là charge bị bỏ sót chứ không phải số 0 thật, sai số giống masking chứ không giống nhiễu đối xứng. Đây chỉ là tương tự: thí nghiệm của bài làm trên baseline, N=3.
- *Không làm ngay:* reward network với target là reward toàn mạng. Ở hàng nghìn agent, ảnh hưởng của một action lên reward toàn mạng rất nhỏ (suy luận của tôi, bài không thử).
- *Có thể thử:* lấy p.19, mục 3 làm hướng lai (Counterfactual as Potential, nguồn thứ cấp [16]).

---

## 2. Yang et al. 2023, LIDR

**Citation.** C. Yang, G. Yang, J. Zhang, *Learning Individual Difference Rewards in Multi-Agent Reinforcement Learning* (Extended Abstract), AAMAS 2023, pp.2418-2420, 3 trang (p.1-3). DOI/arXiv: không nêu. Chỉ là poster, không có phân tích lý thuyết.

**Ý tưởng và công thức.**
- R_i = G + L_i, với G là team reward và L_i = D_i (p.1-2).
- Mạng attention R̄(s,o_i,a), train bằng MSE với r_t: L = ΣΣ (R̄(s,o_i,a_i) − r)² (Eq.1, p.2).
- Lý tưởng thì R̄ hội tụ về E_{a_i=a, a_−i∼π}[r] (Eq.2, p.2).
- **D_i = R̄(s,o_i,a_i) − max_a R̄(s,o_i,a)** (Eq.3, p.2). So với max nên D_i ≤ 0, khác aristocrat utility.

**Counterfactual.** Mạng học, không cần default action hay model (p.1-2).

**Giả định.** Reward decomposition hội tụ ("ideally", p.2). Không có định lý đảm bảo: không nêu.

**Setting của ta phá gì.** Target là r_t chung và marginal hóa theo a_−i. Với hàng nghìn agent, tỷ lệ tín hiệu trên nhiễu của một action rất nhỏ (suy luận).

**Scale.** 6 map SMAC (p.2). Số agent mỗi map và số seed: không nêu.

**Kết quả.** Toàn đồ thị (Fig.2, p.2). Số duy nhất: LIDR đạt win rate 40% ở corridor và 3s5z_vs_3s6z, nơi baseline đều thất bại (p.2).

**Liên quan: BACKGROUND.** Giữ ý tưởng cấu trúc: reward = phần chung + phần phân biệt. Bằng chứng yếu, không đủ để đổi thiết kế.

---

## 3. Foerster et al. 2018, COMA

**Citation.** J. Foerster, G. Farquhar, T. Afouras, N. Nardelli, S. Whiteson, *Counterfactual Multi-Agent Policy Gradients*, AAAI 2018 (copyright p.1), arXiv:1705.08926v3, 11/12/2024 (p.1). Bản này có **errata** sửa chứng minh Lemma 1: critic phải điều kiện theo cả s và joint history τ (p.8). DOI: không nêu.

**Ý tưởng và công thức.**
- Difference reward: D^a = r(s,u) − r(s,(u^−a,c^a)) (p.4).
- Counterfactual baseline: A^a(s,τ,u) = Q(s,τ,u) − Σ_{u'^a} π^a(u'^a|τ^a) Q(s,τ,(u^−a,u'^a)) (Eq.4, p.4).
- Critic nhận u^−a làm input, xuất |U| giá trị thay vì |U|^n (p.4-5).
- Baseline có expected contribution bằng 0 (Eq.9-13, p.10).

**Lý do bài nêu cho thiết kế.** Difference reward cổ điển cần simulator, mỗi agent một counterfactual simulation riêng, và cần chọn default action (p.4). Bài nói ở StarCraft không thể làm thế, còn ở simulator đặt lại được thì làm được nhưng tốn kém (p.5). **SUMO thuộc loại đặt lại được**, nên ta dùng được làm phép kiểm định, dù không làm được ở mức từng reward.

**Giả định hội tụ (p.5, p.11).** Reward bị chặn; policy khả vi; critic train theo target không lệch như TD(1); critic đã hội tụ trước mỗi lần tính gradient; critic representation tương thích.

**Setting của ta phá gì.**
- PPO + GAE λ=0.95, critic chưa hội tụ, EV thấp.
- Input u^−a tuyến tính theo số agent (p.5), không khả thi với agent đến và đi liên tục.
- Agent hành động bất đồng bộ.

**Scale.** Tối đa 5 unit: 3m, 5m, 5w, 2d_3z (p.5). Bài thử critic factored và thấy nút thắt là multi-agent exploration chứ không phải việc tập trung critic (p.6). Scale lớn là future work (p.7). Castellini xác nhận khó dùng khi có hơn vài agent (Castellini p.2).

**Kết quả (Table 1, p.7).** 35 trial; đánh giá 200 episode sau mỗi 100 episode train (p.7). Win %, trung bình 1000 episode cuối, ngoặc là CI 95%:

| Map | Heuristic | IAC-V | IAC-Q | central-V | central-QV | COMA |
|---|---|---|---|---|---|---|
| 3m | 35 | 47(3) | 56(6) | 83(3) | 83(5) | 87(3) |
| 5m | 66 | 63(2) | 58(3) | 67(5) | 71(9) | 81(5) |
| 5w | 70 | 18(5) | 57(5) | 65(3) | 76(1) | 82(3) |
| 2d_3z | 63 | 27(9) | 19(21) | 36(6) | 39(5) | 47(5) |

- Ở 2d_3z, COMA vẫn **thua heuristic** (47 so với 63).
- TD(λ) là hyperparameter nhạy nhất, chọn λ=0.8 (p.6).

**Liên quan: USEFUL.**
- *Giữ:* không dùng joint-action Q.
- *Dùng:* định nghĩa D^a làm chuẩn để kiểm định attrib: giữ nguyên hành động của các xe khác, chỉ đổi hành động của nhóm được thử.

---

## 4. Michailidis et al. 2026

**Citation.** D. Michailidis, S. Ghebreab, F. P. Santos, *Inequality in Congestion Games with Learning Agents*, arXiv:2601.20578v2, 30/1/2026 (p.1). **Preprint**, venue: không nêu.

**Tên file gây hiểu nhầm:** bài **không nói về difference reward**. Đây là mô tả hành vi Q-learning trong congestion game, RL không phải để tối ưu mà để mô phỏng thích nghi (p.5).

**Ý tưởng và công thức.**
- Price of Learning: PoL(t) = C(π_t)/C(a*) (Eq.9, p.4), phiên bản động của PoA.
- Source disparity: SD = AvgCost(s_1) − AvgCost(s_2) (Eq.11, p.4).
- Q-learning stateless, ε-greedy (Eq.12-13, p.5).

**Giả định.** Một lần chơi là một lựa chọn path trọn vẹn, reward tức thì (p.5); latency không giảm theo load (p.3). Ta có quyết định theo từng hop, delay vật lý và spillback, nên các kết quả này chỉ gợi ý.

**Thí nghiệm.** 200 agent chia đều 2 source, 10.000 step, 40 seed, learning rate trung bình 0.2 với các tỷ lệ từ 5/1 đến 1/5 (p.8).

**Kết quả.**
- Table 1, p.6: Braess chưa can thiệp NE=SO=300, PoA 1.0. Sau can thiệp NE=400, SO=300, PoA 1.33.
- Amsterdam NE=SO: 9700, 7349, 6648; SD 27.00, 13.75, 4.52. Cùng trang, Fig.2 ghi PoA 1.008 cho Phase C còn Table 1 ghi 1.0, **hai chỗ không khớp**.
- Learning rate khác nhau gây bất bình đẳng kéo dài dù PoL tương đương (p.8-9). Phase C có thể không hội tụ về NE, PoL ổn định trên 1.0 (p.11). Phần lớn chỉ ở dạng đồ thị.

**Liên quan: BACKGROUND.**
- *Có thể thêm vào đánh giá:* chênh lệch thời gian khách và không khách, và PoL theo update. Rẻ, không đổi training.
- *Không đổi* reward hay kiến trúc theo bài này.

---

## 5. Yu et al. 2022, MAPPO

**Citation.** C. Yu, A. Velu, E. Vinitsky, J. Gao, Y. Wang, A. Bayen, Y. Wu, *The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games*, NeurIPS 2022 Datasets and Benchmarks, arXiv:2103.01955v4 (p.1). DOI: không nêu.

**Giả định của bộ khuyến nghị.** Dec-POMDP **reward chung** (p.3), agent lock-step, số agent cố định, discrete action, phần lớn đồng nhất (p.10), 2 đến 27 agent ở SMAC (p.12). Đây là kết luận **thực nghiệm**, không có lý thuyết (p.10). Ta khác ở: reward từng xe, SMDP, hàng nghìn agent đến và đi.

### So sánh khuyến nghị với setting của ta

| Yếu tố | Yu | Ta (`sumo_marl.py`) | Nhận xét |
|---|---|---|---|
| Value normalization | Dùng running mean/std hoặc PopArt; "never hurts", quan trọng khi return rộng, Spread −200..0 (Suggestion 1, p.7; Alg.1, p.11) | **Không có**; `vf_loss` MSE thô (dòng 472) | **Nên đổi** |
| Input critic | Global + agent-specific, cắt phần dư (Suggestion 2, p.7-8). CL kém khi nhiều agent (p.8) | Global + true state + local, gồm exit candidate (dòng 441-442) | **Giữ** |
| Epochs | Tối đa 10 task khó, 15 task dễ; 15 kém trên MMM2, corridor (Suggestion 3, p.8-9) | 12 Adam step, **chỉ ~27% dữ liệu mỗi update** (tính) | **Xem dưới** |
| Mini-batch | Không chia là tốt nhất, 1 mini-batch thắng 22/23 map, 4 mini-batch thất bại (p.9) | 64 tick mỗi step; 2880 tick chia ra thành 45 phần (tính) | **Đo số quyết định mỗi phần** |
| Clip | Dưới 0.2; 0.05 chậm hơn nhưng ổn định; ≥0.2 hay kém (Suggestion 4, p.9-10). Dùng clip cả value (p.12) | Actor 0.2, không clip value (dòng 302, 472) | Chính Yu dùng 0.2 ở đa số map (p.28), nên 0.2 chấp nhận được; theo dõi clipfrac, 0.1 là arm thử |
| Batch size | Có ngưỡng tới hạn; trên ngưỡng đó có thể phí sample (Suggestion 5, p.10). Batch = envs × buffer × agents (p.26) | ~32 episode, hàng nghìn agent, nhiều hơn SMAC | Thu đủ, **nhưng dùng thiếu** |
| Parameter sharing | MAPPO hơn MAPPO-Ind: MMM2 90.6 so với 13.0, 6h_vs_8z 88.3 so với 11.4 (Table 4, p.14) | Có | **Giữ** |
| Death masking | Thay state xe chết bằng zero + agent ID; hơn các phương án khác (p.14-15) | Xe rời khỏi batch, bootstrap 0 khi tới đích (dòng 239) | Đúng với reward từng xe; **`team` cần xem lại** |
| γ, λ | 0.99, 0.95 theo step (p.26) | 0.9995/giây, λ=0.95 theo quyết định (dòng 307, 316) | Xem GAE |
| Learning rate | Sweep 1e-4..1e-3 (p.27); SMAC 5e-4, Hanabi actor 7e-4, critic 1e-3 (p.28) | Actor 1e-4, critic 5e-4 | Actor ở đáy sweep |
| Entropy | Sweep 0.01-0.015 ở Hanabi/GRF (p.27); 0.015 ở Hanabi (p.28) | 0.03→0.005 trong 400 update | Bắt đầu cao hơn sweep; **ưu tiên thấp** |
| Khác | Huber δ=10, grad clip 10, feature + reward normalization, orthogonal init (p.26); gain 0.01 (p.28) | MSE, grad clip 1.0 (dòng 479), reward chia 60 | Grad clip 1.0 với value thô dễ làm nghẹn critic |

**Ngân sách tối ưu hóa (tính).**
- Ta: 900 s / 10 s = 90 tick mỗi episode, × 32 = 2880 tick mỗi update. 12 × 64 = 768 tick dùng tới, tức **khoảng 27% một lượt qua dữ liệu**.
- Đến update 25: 300 Adam step. Đến update 400: 4800 step ở lr 1e-4.
- SMAC của Yu: 8 × 400 = 3200 env step mỗi update (Table 10, p.27). Đến 10M step (p.5) là khoảng 3125 update, × 5-15 epoch = 15.6k-47k Adam step ở lr 5e-4.
- Hệ quả: entropy gần 1 ở update 25 **chưa nói được gì**, vì actor mới đi 300 step ở lr nhỏ. Không kết luận từ đây.

**Cảnh báo khi đọc số mini-batch.** Khuyến nghị của Yu (p.9) đo bằng *số phần chia* của một batch cỡ 3200 × n. Một chunk 64 tick của ta có thể đã chứa hàng nghìn quyết định, nên "45 phần" không tương đương trực tiếp với "4 mini-batch thất bại". Phải đo số quyết định mỗi chunk trước.

**Agent bất đồng bộ.** Hanabi cộng dồn reward giữa hai lượt của mỗi agent (p.13), có cấu trúc giống SMDP của ta.

**Kết quả.** Median win rate, 6 seed, 32 game, median 10 lần eval cuối (p.4); MPE 10 seed (p.4); GRF 6 seed, 100 rollout (p.5); Hanabi ≥3 seed, 10k game (p.6).
- 25m: MAPPO(FP) 100.0(1.5), QMix 85.9(7.1). 27m_vs_30m: 93.8(2.4) so với 39.1(9.8) (Table 1, p.5).
- GRF 3v.1: 88.03(1.06) so với QMix 8.12(2.83) (Table 2, p.6). Hanabi 5 người: 23.04(0.10) trung bình (Table 3, p.6).

**Liên quan: CORE.** Thay đổi ở phần xếp hạng cuối file.

---

## 6. Ng, Harada, Russell 1999, Reward Shaping

**Citation.** A. Y. Ng, D. Harada, S. Russell, *Policy invariance under reward transformations: Theory and application to reward shaping* (p.1). File không nêu venue; Castellini (ref [34], p.22) dẫn ICML'99, pp.278-287. DOI: không nêu. Text trích bị vỡ, mất ký tự γ và Φ, phải đọc lại từ chứng minh.

**Định lý.**
- M' = (S,A,T,γ,R+F) (p.3). F là potential-based nếu F(s,a,s') = γΦ(s') − Φ(s) (Eq.2, p.4).
- Điều kiện cần và đủ để đảm bảo mọi optimal policy của M' tối ưu trong M, khi không biết T, R (Theorem 1, p.4).
- Q*_M' = Q*_M − Φ, V*_M' = V*_M − Φ (Corollary 2, p.5). Đồng nhất thức đúng với **mọi π** (Remark 1, p.5), nên near-optimal cũng được giữ.
- Φ ≈ V* làm phần còn phải học gần bằng 0; nhưng Φ thô vẫn giúp (p.6-7).

**SMDP.** Bài nêu dạng tổng quát **không kèm chứng minh**: **F(s,a,s',τ) = e^{−βτ}Φ(s') − Φ(s)** (§5, p.8).

### Giả định, đối chiếu với setting của ta

| Giả định | Bài | Ta | Kết luận |
|---|---|---|---|
| Dạng SMDP | p.8 | `(R − gamma^dt R')/60`, với Φ = −R/60, β = −ln γ, τ = dt (dòng 208) | **Khớp** khi transition đầy đủ |
| Φ tại trạng thái kết thúc = 0 | Bắt buộc với γ=1 (p.3, p.5); γ<1 trong bài không có absorbing state (p.3) | R'=0 khi tới đích (dòng 205) | **Đúng** cho bài toán có kết thúc |
| Φ là hàm của state | p.4 | R = min live estimate, có nhiễu và mất report | Không đúng nghĩa đen. **Vẫn ổn (suy luận):** Φ_t đo trước a_t và giá trị ở hai đầu giống nhau, nên tổng vẫn telescope và −Φ_t chỉ đóng vai baseline |
| Φ bị chặn | p.3-4 | Live estimate hữu hạn? | Cần kiểm tra giá trị inf/rất lớn |
| Một MDP, một objective | p.1 | Hàng nghìn agent, policy đổi liên tục | Remark 1 chỉ đúng khi cố định policy các agent khác. Trong multi-agent: giữ tập Nash equilibrium (dẫn [14,15] qua Castellini p.19), **không đảm bảo đạt J** |
| Episode không bị cắt | Không xử lý truncation | **66% xe bị cắt ở 900 s** | **Lý thuyết không phủ**, xem dưới |
| Objective | Discounted như MDP đã cho | J không discount | Invariance là giữa discounted shaped và discounted unshaped, **không phải với J**. GAE nói rõ khác biệt này (GAE p.6) |
| Reward gộp | Không nói | −dt/60 gộp cuối đoạn, không discount trong đoạn | Lệch nhỏ khi dt ≪ 2000 s (tính) |
| Policy class hạn chế | Vẫn đúng (p.8) | Actor chỉ thấy observation | Ổn |

**Truncation (suy luận từ telescoping, không có trong bài).**
- Tổng shaped đến H: Σγ^t r − Φ_0 + γ^T Φ_T. Số hạng γ^T Φ_T phụ thuộc policy, chỉ triệt tiêu khi bootstrap bằng V' = V − Φ **tại đúng state lúc H** (Corollary 2, p.5).
- Code (dòng 204-207, 239) dùng `R' = R` và `boot = v[i]`, tức state của **quyết định cuối**, không phải state lúc H. Điều này tương đương giả định xe không tiến được chút nào trong dt.
- Với xe bị cắt, dt = H − t (`sumo_env.py` dòng 691-692) gần như không phụ thuộc action. Do đó TD error của bước cuối xấp xỉ −a·dt/60 + (1−γ^dt)|V|: lệch âm theo tiến độ thật đã bỏ qua, và phần dt không mang tín hiệu chọn exit.
- Đây là xấp xỉ, không phải lỗi dấu. Cần đo: tỷ lệ các bước cuối này trên tổng quyết định và độ lớn lệch.

**Thí nghiệm.** Grid 10x10, 50x50 và 5x5 có 5 subgoal; undiscounted, 40 run; Sarsa, 0.10-greedy, lr 0.02 (p.6-7). Φ_0 = −manhattan/0.8; 0.5Φ_0 dù xa V* vẫn tăng tốc rõ (Fig.1, p.6-7). Kết quả chỉ có đồ thị; **không có thống kê**.

**Liên quan: CORE.**
- *Giữ:* dạng γ^dt, R' = 0 tại đích, shaping chỉ dùng khi train.
- *Sửa:* bootstrap tại horizon.
- *Thử:* Φ = −a·R/60. Reward có hệ số a = wp + 1 − w ∈ [0.55, 1] khi p ∈ [0.1, 1] và w = 0.5 (dòng 219), trong khi Φ không có a. Với p = 0.1, phần dư V − Φ ≈ +0.45R/60, không gần 0 (tính). a được tính từ J nên không phải trọng số đặt tay.

---

## 7. Schulman et al. 2016, GAE

**Citation.** J. Schulman, P. Moritz, S. Levine, M. I. Jordan, P. Abbeel, *High-Dimensional Continuous Control Using Generalized Advantage Estimation*, ICLR 2016, arXiv:1506.02438v6 (p.1). DOI: không nêu.

**Công thức.**
- δ^V_t = r_t + γV(s_{t+1}) − V(s_t) (p.4).
- **GAE(γ,λ) = Σ_{l≥0} (γλ)^l δ^V_{t+l}** (Eq.16, p.5). λ=0 chỉ còn δ_t; λ=1 thành return − V (Eq.17-18, p.5).
- γ<1 **luôn gây bias**, dù V chính xác; λ<1 chỉ gây bias khi V sai (p.5). γ chủ yếu quyết định scale của V (p.5).
- Quy tắc: γ làm mất các số hạng l ≫ 1/(1−γ); sai số nhỏ nếu ảnh hưởng của action phai nhanh (p.6).

**Liên hệ shaping.** Eq.20-25, p.5-6: shaping để nguyên advantage khi λ=1, và GAE chính là tổng (γλ)-discount của reward shaped với Φ = V. Bài cũng nhấn mạnh Ng xét objective discounted, còn GAE xét objective undiscounted với γ là công cụ giảm variance (p.6).

**Hệ quả với thiết kế (suy luận).**
- δ̃ = r + γ^dt(Φ' + V') − (Φ + V'): shaping với critic V' **giống hệt** không shaping với critic V = V' + Φ. Nói cách khác, Φ là phần khởi đầu cố định của critic, và V' chỉ học phần dư.
- Vì vậy **EV trên target shaped không so được với EV thường**: Φ tốt thì phần dư chủ yếu là nhiễu nên EV thấp là tự nhiên. `metrics` của `sumo_marl.py` chưa ghi EV; cần biết EV 0.24-0.33 đang tính trên target nào. Nên báo thêm EV của V' + Φ so với return chưa shape.

**Truncation/bootstrapping.** Bài chỉ nêu episode kết thúc sau 2000 timestep (p.9); cách bootstrap khi cắt: không nêu. Công thức cho đoạn hữu hạn nằm ở PPO Eq.10-12.

**Khoảng tham số.** Tốt nhất ở trung gian: γ∈[0.99,0.995], λ∈[0.96,0.99], 9 seed (p.10); λ thường trong [0.9,0.99] (p.11). Batch 50.000 đến 200.000 timestep (p.9). Bài test ở robot với step cố định; SMDP: không nêu.

**So với ta (tính).**
- 1/(1−0.9995) = 2000 s, lớn hơn horizon 900 s; γ^900 ≈ 0.64.
- λ áp theo **quyết định** còn γ theo **giây** (dòng 237), nên một đoạn chờ 120 s và một đoạn 5 s cùng bị cắt trace như nhau. Điều này ngoài phạm vi bài; thử λ^(dt/d̄) nhưng ưu tiên thấp.

**Liên quan: USEFUL.**

---

## 8. Schulman et al. 2017, PPO

**Citation.** J. Schulman, F. Wolski, P. Dhariwal, A. Radford, O. Klimov, *Proximal Policy Optimization Algorithms*, arXiv:1707.06347v2, 28/8/2017 (p.1). **Preprint.** DOI: không nêu.

**Công thức.**
- L^CLIP = Ê[min(r_t Â_t, clip(r_t, 1−ε, 1+ε) Â_t)] (Eq.7, p.3).
- Objective chung có value loss và entropy bonus (Eq.9, p.5).
- **Truncation:** chạy T step (T thường nhỏ hơn nhiều so với episode), **bootstrap V(s_T)** tại cuối đoạn (Eq.10, p.5); GAE cắt ngắn là Eq.11-12, p.5.

Ý nghĩa: bootstrap dùng **state ở điểm cắt**. Code của ta dùng state của quyết định trước đó.

**Hyperparameter (p.10).**

| | MuJoCo | Roboschool | Atari |
|---|---|---|---|
| Horizon | 2048 | 512 | 128 |
| Epochs | 10 | 15 | 3 |
| Minibatch | 64 | 4096 | 32×8 |
| γ, λ | 0.99, 0.95 | 0.99, 0.95 | 0.99, 0.95 |
| ε | 0.2 (p.7) | Không nêu; stepsize chỉnh theo KL | 0.1×α |
| Entropy | Không dùng (p.6) | Không nêu | 0.01 |

**Kết quả.** 7 task, 3 seed, 21 run, score chuẩn hóa: không clip −0.39; ε=0.1: 0.76; **ε=0.2: 0.82**; ε=0.3: 0.70; adaptive KL tốt nhất 0.74 (Table 1, p.6). Atari: 3 seed, 40M frame (p.10, p.12).

**Giả định.** Bài chỉ xét một agent. Với nhiều agent, Yu nêu giả thuyết rằng clip nhỏ và ít epoch giúp hạn chế non-stationarity (Yu p.9).

**Liên quan: BACKGROUND.** Giữ cấu trúc. Dẫn chứng chính là cách bootstrap (Eq.10).

---

## 9. Chu et al. 2020, MA2C

**Citation.** T. Chu, J. Wang, L. Codecà, Z. Li, *Multi-Agent Deep Reinforcement Learning for Large-scale Traffic Signal Control*, arXiv:1903.04527v1, 11/3/2019 (p.1). File là **preprint 2019**; journal và DOI: không nêu trong file. Bài này về signal control, không phải routing; agent là nút giao cố định.

**Phạm vi quan sát.** Vùng local V_i = N_i ∪ {i}, một hop (p.3).
- Input có state vùng đã giảm trọng số và **fingerprint**: π_{t−1} của hàng xóm (Eq.8, Eq.10, p.4).
- State: wave và wait trên làn vào, trong 50 m (Eq.15, p.5).

**Spatial discount (Eq.9, p.4).** r̃_{t,i} = Σ_{d=0}^{D_i} Σ_{j: d(i,j)=d} α^d r_{t,j}. α=0 là tham lam, α=1 là hợp tác hoàn toàn; bài dùng **α=0.75** (p.6). Không cần xác định ai gây ra delay, chỉ cần global reward phân rã theo không gian (p.4).

**Truncation.** Nếu tới T thì **coi là terminal, không bootstrap** (Eq.14 và câu sau đó, p.5). Chu coi horizon là kết thúc thật, khác PPO.

**Scale và cài đặt.**
- Mỗi nút có mạng riêng; mô tả "fully scalable" (p.1), nhưng chỉ test **25 và 30 nút** (p.6, p.8).
- γ=0.99, ηθ=5e-4, ηw=2.5e-4, |B|=120, β=0.01, Δt=5 s, T=720, 1M step ≈ 1400 episode (p.6).
- Clip reward [−2, 2], state [0, 2], gradient 40 (p.6).
- Ở Monaco phải **bỏ `wait` khỏi reward và state** để dễ fit value (p.8).

**Kết quả.** 10 episode eval (p.6). Số seed train: không nêu. Thống kê kiểm định: không nêu.
- Grid: R̄ = −414 (MA2C), −845 (IA2C), −972 (Greedy), −1409 (IQL-LR) (p.7).
- Monaco, trung bình theo thời gian (Table I, p.8):

| | Greedy | MA2C | IA2C | IQL-LR | IQL-DNN |
|---|---|---|---|---|---|
| reward | −41.8 | −31.4 | −54.6 | −109.8 | −151.8 |
| queue (veh) | 0.51 | 0.29 | 0.52 | 1.19 | 1.57 |
| delay nút (s/veh) | 65.5 | 23.5 | 60.7 | 100.3 | 127.0 |
| trip delay (s) | 144 | 114 | 165 | 207 | 360 |

Ở Monaco, các MARL khác **không thắng Greedy** về reward (p.8). Đây là tiền lệ: thắng heuristic ở mạng thật là khó, và không nên phán từ vài update đầu.

**Giả định và setting của ta.** Agent cố định, hàng xóm cố định; reward thuộc về nút. Xe của ta di chuyển nên "vùng" phải định nghĩa theo vị trí hiện tại.

**Liên quan: USEFUL.**
- *Giữ:* feature `intent` (`gnn_policy.py` dòng 27, 34) đã đóng vai trò gần giống fingerprint.
- *Thử như một arm:* reward chiết khấu theo không gian thay cho attrib. Không phụ thuộc attribution, nhưng α là **một trọng số đặt tay**, trái với nguyên tắc hiện tại nên chỉ dùng để so sánh, và phải sweep nếu báo cáo.

---

## 10. Hu et al. 2022

**Citation.** Z. Hu, C. Zhuge, W. Ma, *Towards a Very Large Scale Traffic Simulator for Multi-Agent Reinforcement Learning Testbeds* (p.1). Venue, năm, DOI/arXiv: không nêu. **Tên file gây hiểu nhầm:** đây là simulator meso-macro, được so với SUMO, không phải một phương pháp RL trên SUMO. Chỉ trích scale và tốc độ theo yêu cầu.

**Scale.** Turin: 27.231 nút, 79.063 cạnh sau xử lý, 2.2 triệu xe/24 h, bước 1 s, C++ single thread (p.1, p.4).

**Thời gian mô phỏng 24 h (giây, Table 2, p.5):**

| Demand | Bathtub | Hybrid | CTM | SUMO |
|---|---|---|---|---|
| 20% | 19 | 521 | 1359 | 384 |
| 100% | 46 | 669 | 11987 | 13567 |
| 200% | 135 | 976 | | |

SUMO ở 100% mất lâu một phần vì gridlock (p.5). Theo tính toán, 86400/13567 ≈ 6.4 lần thời gian thực, còn ở 20% khoảng 225 lần.

**Liên quan: BACKGROUND.** Mạng của ta nhỏ hơn nhiều (886 nút). Bathtub không có hàng đợi trên link nên không dùng được cho attribution theo queue order. **Không đổi simulator**. Gridlock ở SUMO là rủi ro thật, nên theo dõi khi tăng demand.

---

## Tổng hợp cho thiết kế

**Difference reward đã được thử ở scale nào, ước lượng counterfactual thế nào?**

| Bài | Scale lớn nhất | Counterfactual |
|---|---|---|
| Foerster | 5 unit (p.5) | Central Q, marginal hóa action của một agent (p.4) |
| Castellini | 27 unit (p.15-17) | Reward đã biết, hoặc reward network (p.4-5) |
| Yang | Không nêu số agent (p.2) | Mạng attention, so với max (p.2) |
| Chu | 30 nút (p.8), không phải difference reward | Spatial discount, không có counterfactual (p.4) |
| Yu | 27 agent (p.12), không phải difference reward | Không có |

**Không bài nào thử với hàng nghìn agent, và không bài nào dùng attribution theo queue order.** `attrib` là thiết kế riêng, chưa có đảm bảo từ các bài này. Nó chỉ được coi là đúng sau khi qua kiểm định.

### Xếp hạng theo tác động dự kiến

Thứ tự thực hiện khác với thứ tự tác động: mục 3 và 4 rẻ, nên làm trước mục 1 và 2.

1. **Kiểm định attrib có noise floor, và so sánh các reward.**
   - Noise floor: chạy lại cùng cấu hình chỉ đổi một chi tiết vô hại để đo độ lệch nền của SUMO.
   - Rồi đổi hành động của các nhóm xe, giữ nguyên các xe khác (COMA p.4), hồi quy ΔJ đo được theo tổng charge. Cần thấy slope và R² vượt noise floor; số nhóm phải chọn theo noise floor, 8 nhóm có thể không đủ.
   - Đo tương quan **advantage** giữa các reward thay vì reward thô: 0.956 có thể chủ yếu do dt chung.
   - Tách 60% zero charge thành số 0 thật và bị bỏ sót (Castellini p.11-12).
   - Dựa trên: định nghĩa D^a và SUMO đặt lại được; giả định nhóm nhỏ nên tuyến tính.
2. **Dùng đủ batch mỗi update.** Từ ~27% lên ít nhất một lượt đầy đủ (45 chunk). Cộng dồn gradient giữa các chunk nếu muốn ít Adam step hơn. Sau đó thử actor lr 3e-4. Chi phí: phần cập nhật ×3.75 mỗi lượt, cần đo so với thời gian SUMO. (Yu p.8-9, p.27-28.) Dựa trên: kết luận reward chung, N≤27 chuyển được sang setting của ta.
3. **Bootstrap tại horizon.** Ghi `togo` tại H và chạy critic ở tick cuối cho xe bị cắt. (PPO Eq.10 p.5; Ng Corollary 2 p.5.) Đo trước tỷ lệ các bước này. Có thể thêm arm drain trong training (eval đã có `--eval-drain`), chi phí mô phỏng tối đa gấp đôi. Dựa trên: Φ và V đúng ở state lúc H.
4. **Value normalization và EV rõ nghĩa.** Thêm running mean/std (hoặc PopArt), báo EV của V' + Φ. (Yu p.7, p.11; GAE p.5-6.) Rủi ro thấp. Dựa trên: scale return đổi theo p và demand.
5. **Φ = −a·R/60.** Phần dư nhỏ hơn và không phụ thuộc p, không đổi invariance. (Ng p.5-6; Remark 1.) Dựa trên: a là hằng trong một episode và critic biết p.
6. **Arm reward chiết khấu không gian.** (Chu Eq.9 p.4, α=0.75 p.6.) Dựa trên: tính cục bộ giúp fit và phân bổ tốt hơn attribution sai. Có một trọng số đặt tay.
7. **λ theo thời gian; entropy bắt đầu 0.01-0.015; ε=0.1; value clip; Huber.** (GAE p.5, p.11; Yu p.9-10, p.26-27.) Chỉ thử sau khi các mục trên ổn. Các số này không có bằng chứng trực tiếp cho SMDP.

### Giữ nguyên

- Dạng shaping γ^dt, R'=0 tại đích, chỉ dùng khi train (Ng p.8).
- Shared policy (Yu p.14) và critic global + local (Yu p.7-8).
- Không dùng joint-action Q kiểu COMA (Foerster p.5-7; Castellini p.2, p.10).
- Feature `intent` (Chu p.4).
- Theo quy tắc nghiên cứu: không đổi code giữa một loạt run; đo trên checkpoint thật; báo cáo mọi run.

### Chưa rõ, cần đọc thêm hoặc đo

- Devlin & Kudenko (multi-agent shaping) và Devlin et al. (Counterfactual as Potential) chỉ biết qua Castellini p.19; chưa đọc bản gốc.
- Không có bài nào trong nhóm phân tích potential shaping khi bị truncate hay reward SMDP nhiều agent. Lập luận truncation ở trên là của tôi và nên được kiểm tra bằng số.
- Toàn bộ số trang của Ng là suy ra; đối chiếu với PDF trước khi trích dẫn trong paper.
