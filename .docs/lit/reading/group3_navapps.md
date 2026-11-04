# Ghi chú đọc, nhóm 3: navigation apps và selfish routing

Quy ước:
- `p.N` là trang thứ N của file PDF, không phải số trang tạp chí (riêng Shen có ghi chú ở mục đó).
- "Số tự tính" là phép tính của người ghi từ số trong bài, bài không in.
- Dòng **Hàm ý cho dự án** là suy luận của người ghi, không phải kết luận của bài. Đây là đọc tài liệu, không phải phán quyết về MARL (chưa train).
- Số đo của dự án lấy từ yêu cầu đọc: J ≈ 485-494 cho ba baseline, 144 episode, p = 0.25/0.5/0.75, congestion index 2.18-2.88; test cục bộ noise live link time làm app xấu đi khoảng 37%.

---

## 1. Chan, Kuncheria, Macfarlane: Simulating the Impact of Dynamic Rerouting on Metropolitan-Scale Traffic Systems

**Citation:** arXiv:2207.12580v1 (26/7/2022), "Manuscript submitted to ACM" (p.1). File tên 2023 nhưng bản đang có là preprint 2022; venue chính thức không nêu trong bản này. Tên chủ đề NavApps đúng.

**Câu hỏi:** tác động hệ thống của tỉ lệ xe dynamic rerouting ở quy mô đô thị (p.1).

**Phương pháp:**
- Simulator Mobiliti, parallel discrete event, mesoscopic: có từng xe và quyết định reroute nhưng không có lane-change hay car-following (p.4). Link có BPR-like delay, timing và storage capacity (p.6-7).
- Signal: cơ chế có sẵn nhưng thí nghiệm **không chạy signal**, chỉ phản ánh qua capacity của link (p.7, p.12).
- Mạng: San Francisco Bay Area, 454,651 node, 1,008,959 link; 19 triệu trip leg (p.12).
- Penetration: 0-100%, bước 10% (p.15).

**Mô hình rerouting và thông tin (Table 1, p.8):**
- Link update khi travel time lệch ít nhất min(t_lsu = 60 s, r_lsu = 1.0 × t_free) so với giá trị đã gửi (p.8).
- Reroute check: tối đa một lần mỗi t_check = 300 s, khi xe đến link mới (p.9-10).
- Chỉ reroute nếu delay vượt max(120 s, 0.2 t_free) **và** tuyến mới tiết kiệm hơn max(120 s, 0.2 t_c) (p.9-10).
- Compliance 100%, không delay; compliance thấp được xấp xỉ bằng penetration thấp (p.10).
- Noise trên link time: không nêu trong bài. Controller đồng nhất như một agency duy nhất; nhiều hãng với thông tin không hoàn hảo để lại cho tương lai (p.10).

**Kết quả:**
- VHD giảm đơn điệu theo penetration, tối thiểu ở 100%, hết "knee" sau 70% (p.15-17, Fig. 19; giá trị VHD từng mức không in thành số). **Không thấy hại ở mức penetration nào** trong chỉ số toàn hệ thống.
- Mean travel time per trip leg 51 → 35 phút ở 100% (Fig. 20a, p.18; p.16-17 viết là một trip được reroute tiết kiệm trung bình 16 phút). Số tự tính: giảm khoảng 31%. Hai cách diễn đạt khác nhau về phạm vi (mọi trip leg và trip được reroute), đáng để ý khi trích.
- Chỉ một phần nhỏ thực sự reroute: 7% số reroutable ở p = 10%, xuống 2% ở p ≥ 70%; số tuyệt đối 130 nghìn ở 10%, 374 nghìn ở 100% (Table 2, p.17). Số tự tính: mức 10% đã chiếm khoảng 35% số trip reroute của mức 100%.
- VMT gần như không đổi: 146,847 → 146,490 nghìn dặm (Table 3, p.18).
- Dịch chuyển sang đường nhỏ: lưu lượng từ FC 2-3 sang FC 4-5 (p.17). 7000 km FC5 nhận thêm xe, 75% trong đó thêm dưới 6 xe ở cao điểm sáng (p.18). 440 km FC5 có v/c > 0.75, tăng trung bình 70 xe; 110 km là tắc **mới** do rerouting (p.18-19).
- So với UE: VHD của UE là 90 nghìn giờ, gần một nửa mức dynamic 100% (Table 5, p.19). Bài nhận định UE không đạt được trong thực tế nên đánh giá thấp congestion (p.19).
- Validation: mức 60% gần thực tế nhất (p.19), khớp khảo sát 55-65% người dùng bản đồ hằng ngày (p.19). R² đếm xe tuyến ≥ 0.76 (p.19), 72% link PeMS có R² > 0.7 (p.21), nhưng chỉ 55% link có speed R² > 0.4 (p.22).

**Độ nhạy về thông tin (quan trọng):**
- Giãn ngưỡng link update: giảm mạnh số message, ảnh hưởng nhỏ đến reroute và system delay, tức "coarse information" là đủ (p.10, Fig. 11).
- Tăng t_check: ảnh hưởng nhỏ vì 98.2% trip reroute chỉ đổi một lần ở p = 60% (p.10-11, Fig. 12).
- Ngưỡng reroute (t_delay, r_delay) có tác động **lớn nhất** đến system delay (p.11, Fig. 13). Ngưỡng nhỏ nhất cho hiệu quả hệ thống tốt nhất, nhưng tác giả nghi ngờ tính khả thi với người lái (p.11).
- Oscillation do reroute đồng loạt: không đo trực tiếp. Ghi nhận ngưỡng lớn làm tăng biến động congestion (p.11).

**Giới hạn:** không signal (p.7), không mô hình hành vi người (p.10), không có knowledge-based route (p.2), mạng cao tốc-arterial-local kiểu Mỹ. Quan sát thêm: không có xe máy, không có mạng hẻm, không có khoảng tin cậy theo seed trong các đường cong chính.

**Liên quan: core.**

**Hàm ý cho dự án:**
- *App baseline:* đây là mô tả app chi tiết nhất trong nhóm. `AppReroute`/`app_cont` hiện chọn exit tốt nhất ở mọi nút, refresh 30-60 s và không có ngưỡng. Như vậy phản ứng mạnh hơn Chan nhiều. `app_sticky` (theta) gần Chan hơn. Nên báo cáo app có ngưỡng làm baseline chính. Ngưỡng tuyệt đối 120 s cần xét lại vì chuyến trong mạng hẻm ngắn hơn nhiều so với Bay Area.
- *Độ chênh baseline:* Chan thấy khoảng 31% giữa free-flow và 100% dynamic, còn ta thấy free flow ≈ app, chênh khoảng 2%. Khác biệt này cần giải thích, không nên bỏ qua. Cơ chế của Chan là có năng lực dư ở đường cấp thấp (p.17-18). Giả thuyết cần kiểm tra: mạng ta thiếu năng lực dư đó, hoặc nút thắt nằm ở chỗ không tránh được.
- *Quét p:* thêm 0.1 và 0.2. Table 2 cho thấy reroute tăng rất nhanh ở p thấp, trong khi ta chỉ có từ 0.25 trở lên.
- *Compliance:* compliance và p có thể gộp theo cách xấp xỉ của bài (p.10).
- *Luận điểm hại đường nhỏ:* 110 km tắc mới (p.19) là số trích được cho thesis về hẻm, nhưng trên mạng Bay Area.

---

## 2. Folsom, Park, Pandey: Dynamic Routing of Heterogeneous Users After Traffic Disruptions Under a Mixed Information Framework

**Citation:** Front. Future Transp. 3:851069, 18/5/2022, doi:10.3389/ffutr.2022.851069 (p.1). Đã xuất bản. Tên NavApps hợp lý một phần: "app" ở đây là kênh phát khuyến nghị system-optimal, không phải app selfish.

**Câu hỏi:** một nhóm informed, được khuyến nghị theo path marginal cost (PMC) dự báo, giảm được bao nhiêu congestion do nhóm uninformed phản ứng day-to-day sau nhiễu loạn (p.1-2).

**Phương pháp:**
- Dynamic Network Loading với LWR, triangular FD, tự cài bằng MATLAB, mở rộng package Han et al. (p.5-7, p.12-13). Không dùng SUMO.
- Mạng Sioux Falls: 24 node, 76 link, 528 OD, 6,180 route, 100 departure time, đơn vị thời gian 6 s (p.5, p.13).
- Uninformed: BRDUE day-to-day, Mlogit, indifference band Δ (p.8-9). Informed: chọn theo PMC nhỏ nhất, PMC ước lượng bằng BPR, có indifference band (p.9-11).
- Informed đổi **cả route lẫn departure time** (p.4, p.15).
- Penetration: 0, 20, 40, 80% (p.14, p.16).

**Thông tin:** dự báo từ mô phỏng offline; app phát thông tin đã mô phỏng sẵn; cập nhật online và kiểm định real-time nằm ngoài phạm vi (p.15-16). Thực chất là oracle về trạng thái dự báo trong ngày. Refresh interval, delay và noise: không nêu trong bài.

**Kết quả:**
- Day 1, khi có nhiễu loạn: congestion giảm khoảng 59.2% ở 20% informed, gần như biến mất ở 80% (p.1). Phần kết luận lại viết 59.2% là cải thiện *average travel time Day 1 so với lời giải BRDUE ngày hôm sau* (p.17). Hai cách nói không đồng nhất, cần thận trọng khi trích số này.
- Gap theo path, Day 1: 0% lên tới 1.5 giờ; 20% giảm 30 phút; 80% dưới 12 phút (p.16, Fig. 13).
- Day 2: dưới 30 phút ở 0%; 12 phút ở 20%; khoảng 10 phút ở 40% và 80% (p.16-17). Kết quả Day 2 rất giống nhau giữa các mức vì nhóm uninformed đã thích nghi, chỉ còn cải thiện nhỏ (p.17).
- Nếu không có congestion đáng kể, informed gần như không đổi route, cơ hội cải thiện nhỏ (p.15).
- Benefit tăng đơn điệu theo p trong các mức đã thử, không thấy hại (p.16-17).

**Dẫn lại từ các bài khác (nguồn thứ cấp, nên đọc bản gốc trước khi trích):**
- Peeta và Mahmassani 1995: khi congestion rất cao, khả năng reroute giảm do gridlock nên reroute không giảm được nhiều (p.2).
- Litescu et al. 2015-2016: khoảng 40% informed cho hiệu năng tốt nhất trên mạng hai tuyến; lệch khỏi đó thì mất ổn định; 40% cũng bền nhất với thông tin sai (p.3). Trong các nghiên cứu đó informed quyết định tức thời theo trạng thái hiện tại (p.3).
- Di et al. 2014: Braess paradox còn xuất hiện trong một khoảng demand nhất định dưới bounded rationality (p.3).

**Giới hạn:**
- Tác giả nêu: chi phí tính toán, tới 1.5 giờ mỗi DSO iteration (p.17); chỉ mô phỏng hai ngày (p.15).
- Quan sát: band được nêu là tới 400 s (p.5) nhưng Δ₂ lại là 800 s (p.11). Không có seed hay khoảng tin cậy. Kết quả có phần do đổi departure time. Mạng đồ chơi.

**Liên quan: useful.** Là một cận lạc quan cho partial-fleet system-optimal, chứ không phải mô tả app.

**Hàm ý cho dự án:**
- *Điều kiện để có gain:* gain tập trung vào giai đoạn chuyển tiếp sau nhiễu loạn (p.15-17). Cùng với dẫn chứng Peeta (p.2) cho thấy hai đầu đều nghèo gain: ít congestion thì không cần, quá congestion thì không reroute được. Congestion index 2.18-2.88 của ta có thể rơi về phía đầu sau, cần quét demand rộng hơn 8000-10000 trips/h.
- *Kịch bản:* nên có kịch bản nhiễu loạn (shock, sự cố), không chỉ peak demand ổn định.
- *Departure time:* bài này cho đổi giờ đi, ta không, nên 59.2% không so trực tiếp được.
- *T_cust:* indifference band là cách ràng buộc thiệt hại của khách hàng, gần với vai trò của T_cust trong J.

---

## 3. Bittihn, Schadschneider: Braess' paradox in the age of traffic information

**Citation:** arXiv:2009.02158v1 (4/9/2020), "Submitted to: J. Stat. Mech." (p.1). Là preprint; file ghi 2021, bản xuất bản không có trong file này. Tên chủ đề đúng.

**Câu hỏi:** các user optimum gây Braess có thực sự đạt được khi tác nhân chọn tuyến theo thông tin giống app và trải nghiệm cá nhân hay không (p.1, p.4).

**Phương pháp:**
- Mạng Braess 4-link và 5-link dựng từ TASEP, biên tuần hoàn nên số xe M bảo toàn (p.7-8). L1 = L3 = 100, L2 = L4 = 500, L0 = 1 (p.8). Monte Carlo riêng, không phải SUMO.
- Bốn trạng thái thử (p.30-32): ⋆1 M = 156, ⋆2 M = 154, ⋆3 M = 248, ⋆4 M = 712; ρ⁽⁵⁾ = 0.12, 0.1, 0.2, 0.5.
- Penetration: toàn bộ tác nhân dùng cùng loại thông tin; **không quét tỉ lệ**. Kết hợp nhiều loại thông tin để lại cho tương lai (p.29).

**Mô hình thông tin:**
- Public predictive (giống app): tính từ vị trí hiện tại của **mọi** xe, T = L/(1−ρ) theo từng edge rồi cộng theo route, tính lại ở mỗi điểm quyết định (p.17). Không delay, không noise đo lường, nhưng sai số mô hình vì bỏ qua chờ ở junction và tương quan (p.17).
- Personal historical: trung bình c_mem = 30 vòng gần nhất của chính tác nhân (p.17-19).
- Public historical: travel time của xe vừa hoàn thành được phát cho tất cả (p.16).
- Tham số: p_info = 0.9, ngưỡng ΔT = 10, κ = 0.1 (p.15-16, p.18-19). Có quyết định lại giữa đường khi bị chặn ở junction (p.16).

**Kết quả:**
- Mốc UO khi gán ngoài, 4-link → 5-link (p.30-32): ⋆1 692 → 615; ⋆2 691 → 670; ⋆3 764 → 978; ⋆4 1991 → 2177.
- Personal historical đạt UO ở cả bốn trạng thái (p.28).
- **Informational effect:** ở ⋆2, personal historical đạt trạng thái "E5 optimal" như mong đợi, travel time 5-link thấp hơn 4-link (p.25-26). Public predictive trên cùng mạng lại dao động quanh UO và travel time 5-link **cao hơn** 4-link, thành trạng thái kiểu Braess (p.20, p.22). Cùng mạng, chỉ khác thông tin, kết quả đổi dấu.
- Dao động: ⋆3 với predictive dao động mạnh quanh puo(ii), mọi route đều cao hơn 4-link (p.20-21, p.23). Personal historical ổn định hơn rõ ở ⋆3 (p.26).
- Public historical: dao động mạnh quanh UO, từng được báo cáo là toàn bộ xe luân phiên giữa hai route (p.13, p.16-17). Kết quả chi tiết không in trong bài, trỏ tới [66] (p.17).
- Theo mật độ: mật độ thấp thì predictive đạt UO; mật độ cao thì tương quan và jam quanh junction làm dự báo kém, gây dao động (p.23-24).
- Sai số dự báo: ⋆1 dưới 15% (p.32); ⋆3 có lúc **hơn 100%**, dự báo route 153 quá cao đi cùng route 14 quá thấp và ngược lại, tác giả cho rằng có thể là nguyên nhân dao động (p.33); ⋆4 dự báo thấp hơn thực tế (p.33-34).
- Overreaction: thông tin dự báo làm thay đổi hành vi và tự vô hiệu hóa chính nó, có dẫn chứng thực tế [37] (p.11-13). Tác dụng phụ: đổ vào đường nhỏ, cư dân phàn nàn [50] (p.12).

**Giới hạn:**
- Mạng đồ chơi, biên tuần hoàn. Kết quả trình bày là một realization, các seed khác được nói là giống nhau (p.20).
- Thông tin hướng tới system optimum được bỏ qua vì tác giả cho rằng chưa dùng thực tế (p.12).
- Không có giá trị cụ thể ngoài UO cho travel time khi dao động; phải đọc từ hình.
- System optimum trong bài là cực tiểu travel time lớn nhất (p.3), khác J của ta.

**Liên quan: core** cho cơ chế; không dùng được về độ lớn.

**Hàm ý cho dự án:**
- *Kết quả 37%:* nguồn gần nhất với hiện tượng của ta. Dao động không cần delay hay noise đo lường, chỉ cần dự báo sai ở mật độ cao và mọi người cùng phản ứng (p.17, p.23-24, p.33). Vì vậy chưa đủ cơ sở để coi 37% là artefact đo lường. Bài không đo noise trực tiếp, nên đây là lý do kiểm tra, không phải bằng chứng.
- *Chẩn đoán:* đo sai số dự báo theo thời gian như Appendix C, và chuỗi thời gian tỉ lệ xe theo tuyến. Dao động phải nhìn theo thời gian, trung bình J theo episode có thể che mất.
- *So sánh thông tin:* thêm baseline personal historical (chỉ dựa trên trải nghiệm riêng) nếu muốn đối chứng ảnh hưởng của loại thông tin.
- *Mạng hẻm:* junction jam là đúng điểm yếu của công thức dự báo đơn giản (p.24).

---

## 4. Shen, Xiao, Gu, Ye: Cognitive Hierarchy in Day-to-day Network Flow Dynamics

**Citation:** arXiv:2409.11908v2 [econ.GN], 19/6/2025 (p.1). **Preprint.**

**Tên file gây hiểu nhầm:** bài không phải về navigation app. Đây là mô hình hành vi day-to-day với lý thuyết cognitive hierarchy. App chỉ xuất hiện ở phần diễn giải (PDF p.11).

**Ghi chú trang:** text có 276 form-feed trong khi số trang in chỉ tới khoảng 56, nhiều trang rỗng chen giữa. Ghi `PDF p.X (in Y)`. Từ trang in 19 đến in 42, PDF lệch 8 (in 19 = PDF 27). Tôi không mở được PDF để xác nhận tổng số trang, vì máy không có thư viện đọc PDF.

**Câu hỏi:** vì sao mô hình day-to-day cũ không tái tạo được dao động thực nghiệm; dự đoán lẫn nhau của traveler ảnh hưởng thế nào đến equilibrium và ổn định (PDF p.1-4).

**Phương pháp:**
- Traveler k-step dự đoán traveler thấp hơn; mở rộng NTP và Logit thành CH-NTP, CH-Logit (PDF p.4).
- Dữ liệu: thực nghiệm online 268 người, 26 vòng, mỗi vòng một ngày thật, mạng Braess ba route, BPR (PDF p.30, in 22).
- Kiểm tra số: mạng 8 route, 2 OD, demand (90, 90) (PDF p.35-36, in 27-28); mạng song song ba route (PDF p.27-28, in 19-20).
- Không dùng traffic simulator; flow theo ngày, không có link dynamics. Tỉ lệ "penetration" ở đây là tỉ lệ các nhóm chiến lược p0, p1.
- Thông tin: traveler thấy luồng toàn cục của hôm qua (có thể qua ATIS) (mục 2.2, PDF p.5). Bước cập nhật là một ngày. Noise, delay: không nêu trong bài.

**Kết quả:**
- Lý luận: nếu mọi người chọn tuyến ngắn nhất hôm qua theo thông tin đầy đủ, luồng dao động vĩnh viễn (PDF p.2-3).
- Thực nghiệm có dao động lớn (PDF p.30, in 22). Ngày 1, 3, 8, 9, 10, 13 tuyến ngắn thứ hai nhận nhiều luồng vào hơn tuyến ngắn nhất (PDF p.32, in 24). Hơn một phần ba số người được phỏng vấn mô tả cách đánh giá chiến lược (PDF p.9).
- Calibration: |K| = 1 không tái tạo được dao động; |K| = 2 và 3 cải thiện log-likelihood có ý nghĩa, p-value dưới 0.0002% (PDF p.35, in 27, Table 1). p0 ước lượng 0.88-0.94 cho |K| = 2 (Table 1, cùng trang).
- Ngày 17-25 fit kém, người chơi có vẻ chuyển sang chọn gần ngẫu nhiên (PDF p.32, 35).
- Ổn định: γ̄ ≈ 0.79 trong ví dụ; γ = 0.78 dập nhiễu, γ = 0.8 mất ổn định. |K| = 1 dao động vĩnh viễn, |K| = 2 về equilibrium không phải DUE (PDF p.36, in 28).
- Dự đoán sai: over-predict thu hẹp vùng ổn định; γ̂ > γ̄ luôn bất ổn; under-predict vừa phải mở rộng vùng ổn định; under-predict nặng tách vùng thành hai phần (PDF p.37-38, 48; in 29-30, 40).
- Non-DUE equilibrium có thể tốt hơn hoặc xấu hơn DUE, tùy tỉ lệ traveler chiến lược và hàm chi phí; có điều kiện cụ thể theo khoảng p0, p1, và tác giả nói các trường hợp còn lại thì strategic thinking hại hiệu quả (PDF p.28-29, in 20-21; PDF p.48, in 40).
- Diễn giải cho hệ thống: k = 0 là app phản ứng, k = 1 là nền tảng dự đoán như Google Maps, k = 2 là trung tâm điều phối. Dẫn bằng chứng giai thoại về Waze (diễn đàn, tác giả nói không kết luận được) và "traffic load-balancing" của Gaode (PDF p.11).

**Giới hạn:** chỉ local stability; phân tích toàn cục khó vì đa equilibrium (PDF p.1). Tham số không đổi theo thời gian (PDF p.35, 48). Thực nghiệm chỉ trên mạng ba route. Quan sát: thang thời gian ngày, không phải trong chuyến đi.

**Liên quan: useful** (hành vi, ổn định); **không phải** bằng chứng về app trên mạng thật.

**Hàm ý cho dự án:**
- *Baseline:* tầng k = 0 chính là app hiện tại của ta. Bài gợi ý app thực tế có thể đã có load-balancing (chỉ là giai thoại, PDF p.11). Vì vậy cần một baseline app có phân tán để không so MARL với đối thủ quá yếu.
- *Tham số đáp ứng:* khi dự đoán chính xác, số bước suy luận không đổi local stability của CH-NTP (PDF p.48, in 40), còn γ thì quyết định (PDF p.36, in 28). Tương ứng với ta là tỉ lệ xe đổi tuyến mỗi lần refresh, nên quét refresh và theta.
- *Luận điểm về p:* non-DUE tốt hơn DUE chỉ khi tỉ lệ strategic nằm trong khoảng tới hạn phụ thuộc hàm chi phí (PDF p.28-29). Đây là lý do lý thuyết để gain chỉ có ở một số p, nhưng ví dụ chỉ là hai tuyến song song tuyến tính.

---

## 5. Waniek, Raman, AlShebli, Peng, Rahwan: Traffic networks are vulnerable to disinformation attacks

**Citation:** arXiv:2003.03723v1 (8/3/2020) (p.1). Là preprint; file ghi 2021, bản xuất bản không có trong file này.

**Tên file gây hiểu nhầm một phần:** bài về tấn công bằng thông tin giả làm thay đổi tuyến, không về hiệu năng app. Rerouting trong mô phỏng là tuyến tĩnh, không phải live routing.

**Câu hỏi:** đối thủ có thể gây gián đoạn cấp thành phố bằng tin giả không, và chọn mục tiêu khó đến đâu (p.1).

**Phương pháp:**
- Khảo sát MTurk n = 3,301 về SMS tai nạn giả (p.2).
- Lý thuyết: Maximizing Disruption là NP-complete, Minimizing Targets là APX-hard (p.3).
- Mô phỏng: Nagel-Schreckenberg mở rộng cho mạng, tự cài; bước 1 s, ô 7.5 m, v_max = 5, p_slow = 0.01 (p.7-8). Không phải SUMO.
- Mạng Chicago từ OSM, gần 80,000 node, 235,000 edge; hơn 5×10⁶ chuyến trong 24 giờ (p.6). 100 mô phỏng cho mỗi cấu hình (p.5, p.8).
- 10 mục tiêu chọn theo greedy (hoặc random), toàn thành phố hoặc trong khu Loop (p.3).
- Follow-through: 25, 50, 75, 100% (p.4-6).

**Mô hình thông tin:** tuyến là shortest path theo **khoảng cách**, tính lúc xuất phát; người follow-through bỏ các cạnh mục tiêu khỏi đồ thị (p.6, p.8). Không có refresh, live time hay reroute giữa đường. Tác giả thừa nhận đây là giới hạn (p.6).

**Kết quả:**
- 89% trả lời xu hướng làm theo ≥ 6/10; 55% xu hướng chuyển tiếp ≥ 6/10 (p.2).
- Với follow-through 75%: trong vòng 50 m xe tăng khoảng 6,500 (tập trung) so với 5,900 (rải); ở 100 m khoảng 2,300 so với 5,300 (p.5).
- Tác động lan xa tới 2 km ở 75% khi mục tiêu tập trung (p.5).
- Chuyến trễ ≥ 60 phút: khoảng 1,100 ở 25% follow-through, khoảng 29,300 ở 75% (p.6). Tăng phi tuyến theo tỉ lệ làm theo.
- Greedy, follow-through 50%: 9.28% trễ và 7.33% nhanh hơn; random: 5.49% trễ và 5.57% nhanh hơn (p.6).
- Một số xe nhanh hơn khi đóng cạnh, tác giả gán cho Braess' paradox (p.6). Không có phép kiểm tra riêng cho nhận định này.
- Ví dụ thực tế: đi bộ với nhiều điện thoại mở Google Maps có thể tạo tắc đường giả trên app (p.2).
- Mean ride time 22.59 phút so với 23.18 phút khảo sát, dùng làm kiểm định (p.8).

**Giới hạn:** khảo sát không phản ánh hành vi thực (p.6); shortest distance thay vì fastest (p.6); kiểm định độ thực tế chỉ thô ở mức trung bình.

**Liên quan: background.** Chỉ dùng được cho độ bền và tính đối kháng.

**Hàm ý cho dự án:**
- *Fleet as sensor:* giả định thu thông tin từ đội xe có thể bị làm giả (p.2). Là một mục trong phần threats nếu dùng fleet làm cảm biến.
- *Tác động phi tuyến theo tỉ lệ làm theo:* cùng tập mức 25/50/75 với quét p của ta. Tuy nhiên đây là đánh giá tấn công, không phải routing tối ưu.
- Không nên dùng làm bằng chứng cho noise live link time, vì bài không mô hình live time.

---

## 6. Roughgarden, Tardos: How Bad Is Selfish Routing?

**Citation:** Journal of the ACM 49(2), March 2002, pp. 236-259 (p.1). Bản tạp chí. Tên file chỉ có Roughgarden, thiếu đồng tác giả Tardos. PDF p.N tương ứng trang tạp chí 235+N.

**Câu hỏi:** tỉ số xấu nhất giữa total latency ở Nash và ở tối ưu (p.1-3).

**Phương pháp và điều kiện:**
- Lý thuyết, không có simulator hay mạng cụ thể.
- Static network flow; latency mỗi edge là hàm không âm, liên tục, không giảm **chỉ của luồng trên edge đó** (p.6). Equilibrium là trạng thái dừng (p.2).
- Nonatomic: vô số tác nhân, mỗi tác nhân không đáng kể (p.2). Thông tin hoàn hảo; bài tách rõ chi phí thiếu phối hợp với chi phí thiếu thông tin (p.2).
- Không có queue, spillback, signal, thời gian hay penetration.

**Kết quả:**
- Tuyến tính: Nash ≤ 4/3 tối ưu (Theorem 4.5, p.16), chặt (Fig. 3, p.11-12).
- Tổng quát: tỉ số không bị chặn (ví dụ x^p, p.12). Nhưng Nash ở rate r ≤ tối ưu ở rate 2r (Theorem 3.1, p.12).
- Latency dạng a·x^p + b: tỉ số ≤ (1 − p(p+1)^(−(p+1)/p))⁻¹ = Θ(p/ln p) (p.17). Số tự tính với p = 4 như BPR: khoảng 2.15. Bài không nhắc BPR.
- Approximate Nash (chỉ phân biệt tuyến lệch quá 1+ε): Nash ở r ≤ tối ưu ở 2r × (1+ε)/(1−ε) (Theorem 5.3, p.18). Tuyến tính: (4+4ε)/(3−ε), chặt (p.19). Số tự tính với ε = 0.2: khoảng 1.71.
- Hữu hạn, splittable: vẫn giữ kết quả 2r với x·ℓ(x) lồi (Theorem 5.4, p.19).
- Hữu hạn, unsplittable: không có bicriteria tổng quát, có thể xấu tùy ý nếu latency dốc (p.18, p.21). Có chặn β/(2−β) nếu một tác nhân đổi tuyến làm latency tăng ít hơn hệ số β < 2 (Theorem 5.5, p.21).
- Friedman 2001 (nguồn thứ cấp): với hầu hết rate vector, chi phí selfish routing nhỏ hơn nhiều so với trường hợp xấu nhất, O(log Γ(r)), Γ(r) = N(r)/N(r/2) (p.22). Theorem 3.1 cho tỉ số Nash/tối ưu ≤ Γ(r) (p.22).
- Roughgarden 2001b (nguồn thứ cấp): quản lý tập trung **một phần cố định** traffic có thể khiến equilibrium chỉ tệ hơn tối ưu một hằng số, nhưng chỉ chứng minh cho link song song (p.22).
- Braess (ví dụ): tuyến 3/2 → 2 khi thêm cạnh latency 0 (p.4).

**Giới hạn:** tĩnh, nonatomic và thông tin đầy đủ; đây là cận xấu nhất, không cho biết gain ở một mạng cụ thể (quan sát của người ghi).

**Liên quan: core** làm khung khái niệm và lý do vì sao gain có thể nhỏ. Không phải cận hợp lệ cho mô phỏng SUMO.

**Hàm ý cho dự án:**
- *Cận không chuyển trực tiếp:* không được dùng 4/3 hoặc 2.15 như giới hạn cho J: hẻm có spillback, nên latency phụ thuộc cạnh kế bên và thời gian, vi phạm giả định edge độc lập. J cũng có T_cust, không chỉ total latency.
- *Phép đo rẻ:* Γ(r) = N(r)/N(r/2) (p.22) gợi ý một chẩn đoán đơn giản: chạy app ở demand r và r/2. Nếu Γ nhỏ thì khoảng tối đa cho điều phối là nhỏ (trong khung tĩnh). Chỉ là chỉ báo.
- *Gain theo demand:* Friedman cho lý do mong đợi gain không đồng đều theo mức demand (p.22). Vì vậy một vài mức demand cao chưa đủ để kết luận.
- *Gain theo p:* kết quả central control (p.22) là chỗ dựa lý thuyết cho việc chỉ kiểm soát một phần fleet, nhưng chỉ trên link song song.
- *Cận thực nghiệm:* cần một baseline SO xấp xỉ, ví dụ theo marginal cost, để biết khoảng trống thực. `gate_msa.py` đã có MSA nên có thể dùng làm điểm khởi đầu. So sánh với baseline tốt hơn app, không chỉ với app.

---

## 7. Bang, Chalaki, Malikopoulos: Combined Optimal Routing and Coordination of Connected and Automated Vehicles

**Citation:** arXiv:2203.11408v2 (17/5/2022), dạng IEEE "letter" (p.1). Là preprint; venue không nêu trong text.

**Tên file gây hiểu nhầm:** chủ đề "CVCompliance" sai. Bài **không có compliance**, giả định 100% CAV và tuân thủ tuyệt đối.

**Câu hỏi:** gộp routing với coordination tại giao lộ không đèn có hiệu quả hơn tách rời không (p.1-2).

**Phương pháp:**
- Routing tuần tự theo thứ tự yêu cầu; xe sau biết toàn bộ trajectory đã lên kế hoạch của xe trước, dùng forward dynamic programming (p.1, p.3-4). Xe sau không làm ảnh hưởng xe trước (p.4).
- Mạng: 70 node, 198 edge, 20 giao lộ, 4 station, đường một làn (p.2, p.5).
- 5 mô phỏng, mỗi lần 1000 yêu cầu (p.5). Simulator: "numerical simulations", không nêu tên.
- Penetration: 100% (p.1). Có một RDU trung tâm (p.2).
- Baseline: cập nhật tuyến ở đầu mỗi trip theo trạng thái lúc đó, rồi vẫn dùng coordination (p.5).
- Thông tin: hoàn hảo, kể cả tương lai (p.1). Refresh, delay, noise: không có theo nghĩa thông thường.

**Kết quả:** tổng travel time 18.7 giờ so với 22.1 giờ (p.5); số tự tính: giảm khoảng 15%. Phương pháp đề xuất ít bị ảnh hưởng bởi số CAV, baseline dao động do chỉ nhận thông tin vào một số thời điểm (p.5). Sử dụng đường trải đều hơn (p.5, Fig. 5 trên p.6).

**Giới hạn (tác giả nêu, p.5):** 100% CAV, không đèn, một làn, không mixed traffic. Quan sát: 5 lần chạy, không có kiểm định.

**Liên quan: background.** Tập trung và có thông tin tương lai, đối lập với giả định decentralised partial-info của ta.

**Hàm ý cho dự án:** có thể trích làm ví dụ cho cận trên kiểu reservation hoàn hảo trong mạng nhỏ: ngay cả vậy gain là khoảng 15%, và ở điều kiện khác xa mạng hẻm. Không có thông tin gì cho p sweep.

---

## Kiểm tra ba file có thể bị xếp nhầm

Chỉ đọc abstract, mục lục và đoạn liên quan đến routing.

### MartinezDiaz_2024_CVCompliance: Impacts of Platooning of Connected Automated Vehicles on Highways
IEEE T-ITS, review về **platooning trên cao tốc** (p.1). Tên file chỉ đúng ở chỗ nhỏ: một nghiên cứu CV được review có compliance cao hoặc thấp trên làn đơn 5 km, 31 và 61 xe, compliance cao cho hiệu quả tốt hơn (p.11). Routing chỉ được nhắc lướt (p.7). **Off-topic.**

### Aradi_2020_SUMORL: Survey of Deep Reinforcement Learning for Motion Planning of Autonomous Vehicles
Survey **motion planning** cho xe tự hành (p.1), không phải routing và cũng không phải bài về SUMO RL. SUMO chỉ xuất hiện như một lựa chọn mô phỏng (p.4). Một câu đáng lưu ý: tác giả nói các bài ở tầng route planning không dùng RL, trong phạm vi survey này (p.1). **Off-topic**; có thể dùng câu đó làm background nhưng nó đã cũ.

### Hua_2025_DiffRewards: Multi-Agent Reinforcement Learning for Connected and Automated Vehicles Control: Recent Advancements and Future Prospects
Survey MARL cho **điều khiển CAV**: platooning, đổi làn, giao lộ không đèn (p.1). Cụm "difference reward" không xuất hiện trong text; gần nhất là counterfactual baseline như COMA (p.6-7). Routing chỉ nhắc lướt: "route-agents" trong một dòng bảng (p.14) và macro-micro energy management có nhắc route efficiency (p.17). **Off-topic với nhóm 3**, có thể là **background** cho nhóm MARL (credit assignment, simulators, SUMO ở p.15).

---

## Tổng hợp cho thiết kế thí nghiệm

Phần này là suy luận của người ghi từ các điểm đã dẫn ở trên.

1. **Không bài nào trong nhóm đo trực tiếp noise trên live link time.** Chan chỉ đo độ thô do ngưỡng cập nhật (p.10), Bittihn đo sai số dự báo nội sinh (p.33). Vì vậy kết quả 37% chưa có đối chứng. Hai bài kéo về hai hướng: Chan nói thông tin thô vẫn ổn, nhưng app đó có ngưỡng reroute lớn; Bittihn cho thấy không ngưỡng lớn và mật độ cao thì dao động. Giả thuyết phân biệt được: ngưỡng reroute lọc noise. Thí nghiệm: quét noise × theta × refresh, ghi cả chuỗi thời gian. Chỉ sau đó mới quyết định có coi 37% là artefact không.
2. **Baseline app.** Baseline chính nên có ngưỡng và refresh kiểu Chan (p.8-10), giữ `app_cont` như biến thể phản ứng mạnh. Cân nhắc thêm app có phân tán tải (Shen PDF p.11, chỉ là giai thoại).
3. **Baseline tốt hơn app.** Cần cận trên thực nghiệm (MSA hoặc marginal cost), vì ba baseline trùng nhau chưa cho biết khoảng trống tới SO.
4. **Quét p.** Thêm p = 0, 0.1, 0.2 và 1. Chan cho thấy reroute tăng nhanh nhất ở p thấp (p.17); Folsom thấy gain lớn ở 20% (p.1, p.16); ngược lại, hai bài này đều đơn điệu theo p, còn giả thuyết "chỉ có ở một số p" chỉ dựa trên nguồn thứ cấp Litescu (Folsom p.3) và ví dụ hai tuyến của Shen (PDF p.28-29).
5. **Quét demand và kịch bản.** Ba mức 8000-10000 trips/h có congestion index 2.18-2.88 có thể quá gần vùng khó reroute (Peeta, qua Folsom p.2) hoặc thiếu năng lực dư (Chan p.17-18). Thêm demand thấp hơn và r/2 để tính Γ (Roughgarden p.22). Thêm shock, vì gain của Folsom tập trung ở lúc có nhiễu loạn (p.15-17).
6. **Kiểm tra mạng có thực sự cho chọn tuyến không.** Chênh khoảng 2% của ta so với khoảng 31% của Chan (p.18) là khác biệt lớn nhất cần giải thích trước khi diễn giải các baseline.
7. **Chỉ số.** Đo cả dao động theo thời gian, tỉ lệ đổi tuyến và sai số dự báo (Bittihn p.32-34), và tải thêm lên hẻm kiểu Chan (p.18-19), không chỉ J trung bình.
