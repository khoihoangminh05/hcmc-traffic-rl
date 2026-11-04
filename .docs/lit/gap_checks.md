# Kiểm phản bác các khoảng trống (RESEARCH_V4 §3)

Bản 2026-11-02. Mục tiêu là **cố tìm bài đã làm rồi**. "Không tìm thấy" ở đây chỉ có nghĩa là không thấy qua OpenAlex, arXiv và tìm web; Scopus, Web of Science, Google Scholar và kho luận văn Việt Nam **chưa chạy**. Mã truy vấn khớp với `candidates.md`, chuỗi đầy đủ ghi trong bảng.

| Khoảng trống | Kết luận | Mức đe dọa |
|---|---|---|
| G1 mạng hẻm xe máy | Còn đứng nếu nói hẹp; câu chữ hiện tại sai một phần | Trung bình |
| G2 (đổi) app trong mạng hẻm | Còn đứng, bằng chứng mỏng; ràng buộc phụ đã có khung tổng quát | Thấp đến trung bình |
| G3 chi phí biên không chạy lại | **Phải thu hẹp nhiều**; nhóm cạnh tranh đang hoạt động | **Cao** |
| G4 tham gia một phần | **Câu "hiếm" không còn đúng**; phải đổi cách nói | **Cao** |
| G5 quyết định khi thiếu quan sát | Vế ước lượng đã yếu; vế quyết định còn đứng | Trung bình |
| G6 chuyển giao | **Không còn đúng như đang viết** | **Cao** |

Ngoài ra, RESEARCH_V4 §2.1 viết "MARL chưa thắng được người": đúng với URB, nhưng nhiều bài chỉ so với baseline khác nên không mâu thuẫn. Phải luôn nói rõ so với ai.

---

## G1. "Chưa ai tối ưu định tuyến trên mạng hẻm xe máy"

**Truy vấn**
| Mã | Nguồn | Truy vấn | Kết quả |
|---|---|---|---|
| G1a | OpenAlex, tiêu đề + tóm tắt | `routing optimization alley network motorcycles` | 0 |
| G1b | như trên | `reinforcement learning routing motorcycle traffic` | 2, không liên quan (tải trọng giao hàng; một luận văn tiếng Tây Ban Nha) |
| G1c | như trên | `narrow street informal road network route guidance` | 0 |
| T6 | như trên | `(motorcycle OR motorbike OR "two-wheeler" OR "powered two") AND ("traffic assignment" OR "route choice" OR routing OR "route guidance" OR navigation)` | 1512, xem 100 |
| T7 | như trên | `(alley OR alleys OR alleyway OR alleyways OR hutong OR "narrow road" OR "narrow streets" OR soi) AND (traffic OR "route choice" OR routing OR navigation) AND (motorcycle OR motorbike OR vehicle)` | 378, xem 100 |
| K2 | như trên | `(alley OR alleys OR alleyway OR alleyways OR lane OR "narrow street" OR "narrow streets") AND (motorcycle OR motorbike) AND (routing OR "route choice" OR shortcut OR navigation)` | 79 |
| A4c | arXiv | `(abs:alley OR abs:alleys OR abs:alleyway OR abs:"narrow streets") AND (abs:traffic OR abs:routing OR abs:navigation OR abs:vehicles)` | 12 |
| Web | tìm web | `motorcycle traffic alley network Ho Chi Minh City routing simulation` | không có bài về hẻm |
| Web | tìm web | `Vietnam alley "hẻm" OR "ngõ" motorbike route choice shortcut traffic navigation study...` | không có |
| Web | tìm web | `định tuyến xe máy hẻm ngõ mô phỏng giao thông TP.HCM tối ưu lộ trình luận văn nghiên cứu` | không có bài học thuật |
| Web | tìm web | `reinforcement learning routing narrow lanes alleys motorcycles developing country navigation Grab GoJek...` | không có |

**Tìm thấy, làm yếu claim**
- [Identifying the role of route choice behavior of motorcycle riders](https://doi.org/10.1016/j.trip.2024.101247) (TRIP 2024, đọc tóm tắt): AIMSUN, **mạng lớn** ở quận Ninh Kiều, Cần Thơ, xe máy chiếm đa số, có chọn tuyến động và quét tuân thủ khi cung cấp thông tin; báo cáo cải thiện tới 84%. Không nói về hẻm, không tối ưu hệ thống, không học.
- [Entropy-Based kSP Routing for Motorcycles](https://doi.org/10.14569/ijacsa.2020.0110758) (2020, tóm tắt) và [IoT Solution for Motorcycle Riders](https://doi.org/10.1109/ictc.2018.8539395) (2018, tóm tắt): **dẫn đường xe máy ở Jakarta**, phân tán tuyến bằng EBkSP, bài sau nêu rõ xe máy dùng đường hẹp làm đường tắt. Không học, không hệ thống, nơi đăng yếu.
- [Contextual Route Recommendation in Heterogeneous Traffic](https://doi.org/10.3390/su132313191) (2021, tóm tắt): gợi ý tuyến theo loại xe, xe máy 77,5%.
- [Dealing with mixed and non-normative traffic](https://doi.org/10.1371/journal.pone.0281658) (GAMA, 2023, tóm tắt): mô hình cấp thành phố, xe máy + ô tô kiểu Đông Nam Á.
- Tài liệu xám: Google Maps có chế độ xe máy đi qua ngõ cấm ô tô ([quantrimang](https://quantrimang.com/cach-tim-duong-di-google-maps-cho-xe-may-154718)); Waze ở Sài Gòn gán hẻm là loại đường riêng ([diễn đàn Waze](https://www.waze.com/discuss/t/v-n-d-v-lo-i-d-ng-passageway/345086)). Nghĩa là dẫn đường thương mại qua hẻm đã tồn tại, đây chính là baseline "app".

**Kết luận**: không tìm thấy bài nào tối ưu hệ thống hoặc dùng học tăng cường trên mạng mô hình hẻm tường minh. Nhưng:
- RESEARCH_V4 §3 G1 viết "mô phỏng xe máy ở VN dừng ở hành lang và nút giao" là **sai**; phải sửa (Ninh Kiều là mạng lớn).
- Nên viết lại: *chưa thấy công trình điều phối hướng tới tối ưu hệ thống trên mạng trong đó hẻm được mô hình tường minh, xe máy đa số*.
- Tối thiểu phải đọc toàn văn bài Ninh Kiều; người dùng cần tìm thêm bằng tiếng Việt (mục cuối).

---

## G2 (đã đổi, ưu tiên phụ). "Định tuyến kiểu app trong mạng hẻm"; ràng buộc ngoại ứng là tùy chọn

**Truy vấn**
| Mã | Nguồn | Truy vấn | Kết quả |
|---|---|---|---|
| G2a | OpenAlex, tiêu đề + tóm tắt | `navigation app routing residential streets constraint` | 0 |
| G2b | như trên | `routing with side constraints cut-through traffic limit` | 1, không liên quan |
| G2c | như trên | `alley traffic navigation app Vietnam` | 0 |
| K3 | như trên | `(residential OR neighborhood OR neighbourhood OR "local street" OR "low-capacity") AND ("system optimal" OR "system optimum" OR "routing app" OR "navigation app") AND (constraint OR limit OR cap OR penalty OR impact)` | 28 |
| T15 | như trên | `("side constraint" OR "side constraints" OR "link capacity constraint" OR "capacity constraints") AND ("traffic assignment" OR "traffic equilibrium" OR "traffic equilibria")` | 84 |
| Web | tìm web | `routing apps residential traffic restrictions "environmental capacity" optimization navigation constraint neighborhood` | không có thuật toán |
| Web | tìm web | `system-optimal routing constraint low-capacity residential roads navigation app "neighborhood" traffic limit optimization...` | không có thuật toán đặt trần |

**Tìm thấy**
- **Quan trọng cho luận điểm**: [Socially-aware Evaluation Framework](https://doi.org/10.1080/19427867.2022.2157366) (Kuncheria, Walker, Macfarlane, Transportation Letters 2023; đọc qua snippet): ở Bay Area, **định tuyến SO làm xấu tải đường dân cư và quanh trường học so với UE**. Slide kèm theo cho 4% VMT dân cư ở UE, 5% ở SO theo thời gian, 11% ở SO theo nhiên liệu (số từ slide, phải đối chiếu bài). Nghĩa là mục tiêu TTT của ta có thể đẩy thêm xe vào hẻm; phải đo và báo cáo dù ràng buộc chỉ là tùy chọn.
- [Side-Constrained Dynamic Traffic Equilibria](https://doi.org/10.1287/opre.2023.0577) (Graf & Harks, OR 2024, tóm tắt): khung tổng quát, có ví dụ giới hạn lưu lượng vì an toàn hầm hoặc phát thải khu vực. [Larsson & Patriksson 1999](https://doi.org/10.1016/s0191-2615(98)00024-1) cho trường hợp tĩnh (đã xác minh nguồn mà §6 RESEARCH_V4 ghi cần kiểm tra). Vậy câu "lần đầu đặt ngoại ứng vào bộ định tuyến" **không còn an toàn** ở mức lý thuyết.
- [Traffic jam by GPS](https://doi.org/10.1371/journal.pone.0308260) (PLOS ONE 2024) và [Balancing Mobility Efficiency and Environmental Exposure](https://arxiv.org/abs/2610.37702) (2026): bài sau đưa phơi nhiễm vào routing đa agent, nhưng là phơi nhiễm của người đi xe, không phải của dân.
- Tài liệu xám cho thấy vấn đề có thật ở nơi giống ta: [Bengaluru](https://www.deccanherald.com/india/karnataka/bengaluru/navigation-apps-turn-bengaluru-lanes-into-traffic-hotspots-locals-urge-links-with-city-systems-3794979); dự luật [Massachusetts HD4949](https://malegislature.gov/Bills/194/HD4949.Html) (đề xuất, chưa thấy thông qua).

**Kết luận**: không tìm thấy bài nào về app trong mạng hẻm, và không thấy bộ định tuyến học nào có trần lưu lượng theo đường dân cư. Bằng chứng còn mỏng do T10, T11 chưa xem hết.

---

## G3. "Chi phí biên trong MARL đang phải chạy lại mô phỏng"

**Truy vấn**
| Mã | Nguồn | Truy vấn | Kết quả |
|---|---|---|---|
| G3a | OpenAlex | `marginal cost reward multi-agent reinforcement learning routing without counterfactual` | 0 |
| G3b | như trên | `congestion externality attribution queue agent tolling` | 0 |
| G3c | như trên | `reinforcement learning route choice system optimum autonomous vehicles` | 9 |
| K1 | như trên | `"reinforcement learning" AND (externality OR "marginal delay" OR "delay caused" OR "delay imposed" OR "marginal travel time" OR "marginal cost") AND (routing OR route OR "traffic assignment")` | 210, xem 100 |
| T3 | như trên | `"path marginal cost" OR "marginal travel time" OR "link marginal cost" OR ("marginal cost" AND "dynamic traffic assignment")` | 14 |
| T4 | như trên | `("difference rewards" OR "marginal contribution" OR "Shapley") AND (traffic OR congestion) AND (routing OR "route choice" OR rerouting)` | 86 |
| T5 | như trên | `("marginal external" OR "congestion externality") AND ("agent-based" OR queue OR queueing OR spillback)` | 28 |
| A2b | arXiv | `(abs:"marginal cost" OR abs:"marginal externality" OR abs:"difference rewards") AND abs:"reinforcement learning" AND (abs:traffic OR abs:routing OR abs:congestion)` | 14 |
| Web | tìm web | `Mapping system optimal marginal cost reward reinforcement learning "without" counterfactual simulation vehicles...` | Psarou, Wang |
| Web | tìm web | `Kaddoura queue-based marginal external delay reinforcement learning agents routing reward attribution...` | không thấy bài kết hợp |

**Tìm thấy, làm yếu claim**
1. [Wang et al.](https://arxiv.org/abs/2505.20889) (IEEE OJITS 2026; đọc đoạn phương pháp): reward **là marginal travel time, tính giải tích, không chạy lại**. Hạn chế: một agent trung tâm, gán luồng tĩnh, BPR, lớn nhất 13 nút 48 link, tuân thủ 100%.
2. **PMC đã có nhiều xấp xỉ không chạy lại** trong DTA: [Qian et al. 2012](https://doi.org/10.1016/j.trb.2012.02.008), [TR-C 2018](https://doi.org/10.1016/j.trc.2018.01.002), [TR-B 2020](https://doi.org/10.1016/j.trb.2020.02.004), [lớp xe hỗn hợp, 2026](https://arxiv.org/abs/2602.05565). Có cả [mô hình thay thế marginal travel time cho SUMO](https://doi.org/10.52825/scp.v3i.119) (2022). Đây là dòng phải trích và là baseline tự nhiên; câu "O(N), không chạy lại" một mình **không phải đóng góp mới**.
3. [Kaddoura & Kickhöfer 2014](https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2014/14-01/KaddouraKickhoefer2014CongestionPricing.pdf), [Kaddoura & Nagel 2019](https://doi.org/10.1016/j.retrec.2019.01.002): quy trễ theo agent đã có, và **có nêu tràn ngược**. Đóng góp không nằm ở phép quy này.
4. **Nhóm cạnh tranh (Kucharski, Jagiellonian)**: [Psarou et al. 2510.11410](https://arxiv.org/abs/2510.11410) đúng là chạy lại (đã đọc đoạn phương pháp: N lần chạy thêm cho mỗi hành động chung; 10 AV; họ chọn trường hợp hiếm SO trùng UE). Nhưng [bản 10/2026, 2610.13439](https://arxiv.org/abs/2610.13439) đã thêm **chạy phản thực chọn lọc** và thử nhiều tỉ lệ AV ở Ingolstadt, Provins. Họ có thể ra bản giải tích bất cứ lúc nào.

**Kết luận**: không tìm thấy bài nào dùng quy trễ theo hàng đợi trong SUMO làm reward từng xe cho MARL next-hop. Câu còn đứng được là tổ hợp hẹp: *credit theo hàng đợi, đo trực tiếp từ mô phỏng vi mô, per-vehicle, MARL phi tập trung, kiểm chứng định lượng với chi phí biên phản thực*, cộng so với PMC và với chọn lọc của Psarou. Nên theo dõi nhóm này hằng tuần, và rút ngắn thời gian tới khi có preprint.

---

## G4. "Tỉ lệ tham gia và tuân thủ: lý thuyết tĩnh, thực nghiệm động trên mạng thật hiếm"

**Truy vấn**
| Mã | Nguồn | Truy vấn | Kết quả |
|---|---|---|---|
| G4a | OpenAlex | `penetration rate connected vehicles route guidance reinforcement learning` | 2 |
| G4b | như trên | `partial compliance route guidance dynamic traffic assignment` | 0 |
| G4c | như trên | `mixed autonomy routing Stackelberg reinforcement learning` | 0 |
| T13 | như trên | `(penetration OR "market share" OR compliance) AND ("route guidance" OR "dynamic rerouting" OR "vehicle rerouting") AND (simulation OR SUMO)` | 40 |
| T14 | như trên | `("partial control" OR "fraction of" OR Stackelberg OR "coordinated fleet" OR "mixed autonomy") AND ("system optimal" OR "system optimum" OR "price of anarchy") AND (routing OR assignment)` | 40 |
| K5 | như trên | `("penetration rate" OR "market penetration" OR "fraction of vehicles") AND ("system optimal" OR "system optimum" OR "total travel time") AND ("route guidance" OR routing OR rerouting) AND (reinforcement OR learning)` | 3 |
| Web | tìm web | `navigation provider socially optimal routing fraction of users coordinated Google Maps system optimum study` | Google, Nature Cities |
| Web | tìm web | `reinforcement learning route guidance penetration rate partial compliance system optimal SUMO 2024 2025` | Bang et al. |

**Tìm thấy, làm yếu claim**
- [Arora et al., Nature Cities 2026](https://doi.org/10.1038/s44284-026-00443-x): **thí nghiệm thật của Google** trên khoảng 100 đoạn tắc ở 10 thành phố Mỹ, dưới 2% chuyến bị đổi. Tốc độ trung vị tăng khoảng 2%, lợi ích tới cả người không dùng ([blog Google](https://research.google/blog/the-power-of-collaboration-how-we-can-reduce-traffic-congestion/); số lấy từ blog và tin tức, **chưa đọc bài**). Đây là bài mở đầu tự nhiên của ta: nhà cung cấp dẫn đường đã làm thật, ở p rất thấp, theo cách can thiệp vào chi phí cảm nhận. Đồng thời đặt thước đo: hiệu quả ở p thấp có thể nhỏ.
- [Yun et al., TR-C 2024](https://doi.org/10.1016/j.trc.2024.104721): mô phỏng vi mô, MARL (NFSP), mức không tuân thủ. **Cùng tạp chí đích.**
- [Psarou 2610.13439](https://arxiv.org/abs/2610.13439): nhiều tỉ lệ AV trên mạng thật. [SO-DTA Partial Control](https://doi.org/10.1287/trsc.2017.0800), [ITSC 2023](https://doi.org/10.1109/itsc57777.2023.10421933), [CDC 2023](https://doi.org/10.1109/cdc49753.2023.10383488), [Regional guidance TR-C 2023](https://doi.org/10.1016/j.trc.2023.104440), [TransRL TR-C 2025](https://doi.org/10.1016/j.trc.2025.105040): động, chỉ điều khiển một phần xe hoặc có phần không tuân thủ. [Bài Ninh Kiều](https://doi.org/10.1016/j.trip.2024.101247) cũng quét tuân thủ.

**Kết luận**: câu "thực nghiệm động trên mạng thật hiếm" nên bỏ. Khoảng trống còn lại hẹp hơn: **đường cong lợi ích theo p cho chính sách next-hop phi tập trung trên mạng dày hẻm, có xe nền là xe máy**, kèm phân tách lợi ích giữa xe đội và xe nền, so với kết quả thực của Google.

---

## G5. "Quyết định khi trạng thái hẻm phần lớn không quan sát được, có bất định hiệu chỉnh"

**Truy vấn**
| Mã | Nguồn | Truy vấn | Kết quả |
|---|---|---|---|
| G5a | OpenAlex | `routing under uncertainty traffic state estimation reinforcement learning partial observability` | 0 |
| G5b | như trên | `route guidance sparse probe data uncertainty` | 0 |
| T18 | như trên | `(uncertainty OR "partial observation" OR "partially observed" OR sparse) AND "reinforcement learning" AND ("route guidance" OR rerouting OR "traffic routing")` | 29 |
| K6 | như trên | `"reinforcement learning" AND (routing OR rerouting OR "route guidance") AND (uncertainty OR "partial observability" OR "partially observable" OR "missing data") AND (traffic OR congestion OR vehicles)` | 335, xem 100, phần lớn xe điện và VRP |
| T20 | như trên | `(kriging OR "unobserved locations" OR "unobserved roads" OR "unobserved links") AND traffic AND (uncertainty OR probabilistic OR Bayesian OR "Gaussian process")` | 91 |

**Tìm thấy**
- Vế ước lượng: [AGNP](https://doi.org/10.1016/j.commtr.2023.100099) (nội suy tốc độ xác suất toàn mạng) và [Uncertainty-aware Traffic Prediction under Missing Data](https://arxiv.org/abs/2309.06800) (có bất định ở nơi chưa từng có dữ liệu). **Câu RESEARCH_V4 §2.7 "chưa thấy công trình nào kết hợp kriging GNN với bất định" phải bỏ hoặc kiểm tra lại**; phần "đã hiệu chỉnh" (coverage) và "probe thưa" còn phải đọc toàn văn mới nói được.
- Vế quyết định: [RL-TPVR](https://doi.org/10.1109/access.2022.3179383) (RL + dự báo khi bất định), [TransRL](https://doi.org/10.1016/j.trc.2025.105040) (nhu cầu bất định), [Connection Science 2026](https://doi.org/10.1080/09540091.2026.2658934) (bất định cho xe cấp cứu), [RA-RouteNet](https://doi.org/10.13140/rg.2.2.12941.70886) (2026, ResearchGate; **chỉ thấy tiêu đề, phải đọc**).

**Kết luận**: không thấy bài nào đưa bất định đã hiệu chỉnh của từng cạnh, từ probe thưa, vào MARL routing. Khoảng trống nhỏ nhưng là ý phụ của bài; chưa cần dựa vào nó.

---

## G6. "Chính sách định tuyến chuyển giao được sang quận khác: chưa có, chỉ có cho đèn"

**Truy vấn**
| Mã | Nguồn | Truy vấn | Kết quả |
|---|---|---|---|
| G6a | OpenAlex | `transferable routing policy reinforcement learning different city` | 5 |
| G6b | như trên | `zero-shot generalization vehicle routing reinforcement learning road network` | 0 |
| T17 | như trên | `("transfer learning" OR transferable OR "generalization" OR "unseen") AND "reinforcement learning" AND ("route guidance" OR rerouting OR "route choice" OR "traffic assignment")` | 40 |
| K4 | như trên | `("zero-shot" OR transferable OR "unseen network" OR "unseen networks" OR "cross-city") AND ("multi-agent" OR multiagent) AND (routing OR "route guidance" OR "route choice")` | 260, xem 100 |
| Web | tìm web | `transferable graph neural network policy vehicle routing reinforcement learning unseen road networks zero-shot` | chỉ thấy đèn |

**Tìm thấy, phá claim**
- [MA-GRL, Scientific Reports 2026](https://doi.org/10.1038/s41598-026-56204-2) (tóm tắt): MAPPO + GAT, **theo từng xe**, CTDE, Dec-POMDP; 100 xe, Monaco; **87% giữ hiệu quả zero-shot** giữa Monaco, Luxembourg, Bologna. Cũng là kiến trúc gần giống của ta.
- [TLARG](https://doi.org/10.1109/access.2024.3395430) (IEEE Access 2024): dùng chuyển giao để hội tụ trên mạng rộng.

**Kết luận**: câu "chưa có bản tương ứng cho định tuyến" trong §2.6 và G6 **không còn đúng**. Nếu giữ bài A\*, phải đổi thành thứ MA-GRL chưa có: chuyển giao tới mạng khác hẳn về cấu trúc (mạng hẻm, xe máy) và đội xe lớn hơn nhiều so với 100 xe, có p < 1. Phải đọc toàn văn MA-GRL trước khi quyết định; chỉ dựa vào tóm tắt, chưa kiểm tra chất lượng thực nghiệm.

---

## Việc cần người dùng

**Tìm (quyền truy cập trường hoặc tìm tay)**
1. Scopus, Web of Science: chạy chuỗi mục 3 của `protocol.md`, xuất CSV gửi lại để gộp vào bảng PRISMA. Ưu tiên T1, T6, T7, T10, T11.
2. Google Scholar và kho luận văn BK TP.HCM, ĐH GTVT: `"mạng lưới đường hẻm"`, `hẻm xe máy mô phỏng`, `ngõ hẻm giao thông phân bổ`.
3. Semantic Scholar API key, nếu muốn chạy lại nguồn này.

**Toàn văn cần trước (bản trả phí)**
1. Yun et al., TR-C 2024, `10.1016/j.trc.2024.104721`
2. Arora et al., Nature Cities 2026, `10.1038/s44284-026-00443-x`
3. Kuncheria et al., Transportation Letters 2023, `10.1080/19427867.2022.2157366`
4. Regional route guidance, TR-C 2023, `10.1016/j.trc.2023.104440`
5. Path marginal cost approximation, TR-C 2018, `10.1016/j.trc.2018.01.002`
6. Qian et al., TR-B 2012, `10.1016/j.trb.2012.02.008`
7. Two-way DRL for CAVs, TR-B 2024, `10.1016/j.trb.2024.103014`
8. SO-DTA Partial Control, Transp. Sci. 2018, `10.1287/trsc.2017.0800`
9. Kaddoura & Nagel 2019, `10.1016/j.retrec.2019.01.002`
10. Gibert-Flutre 2018, `10.1177/0308518x17751230` (kiểm số 85%)

---

## Cập nhật sau khi đọc toàn văn (2026-11-04)

Bản thay thế: `.docs/paper/related_work.md` mục 2.8 và `RESEARCH_V4.md` mục 13. Các dòng trên giữ làm nhật ký.

- **G1, sửa:** dòng về bài Ninh Kiều ghi "không nói về hẻm" là sai vì khi đó chỉ đọc tóm tắt. Fadilah 2024 nêu "narrow shortcuts and alleys" (p.2, p.16), nhưng không có tham số hay kết quả riêng cho hẻm (p.6, p.8, p.9).
- **G3, thêm:** Jiang 2023 có difference reward không chạy lại, từ NMFD cấp vùng (p.11); Ramos 2020 có toll cục bộ (p.8). Psarou 2510 p.4, p.6 chỉ ra ma trận chi phí biên không FIFO vì ưu tiên ở nút, đe dọa trực tiếp cách quy theo hàng đợi.
- **G4, thêm:** Kim 2025 có tuân thủ đo thật (p.18), và đo hẻm rất thấp ở ô tô (p.12-13).
- **G6, xác nhận:** MA-GRL đọc từ trang bài: 100 xe điều khiển, 2847 xe nền, giới hạn khoảng 200 agent, phạt phối hợp đặt tay.
