# Ứng viên sau sàng lọc (giai đoạn 1)

Bản 2026-11-02. Sinh từ bản ghi OpenAlex, arXiv, Crossref thật; không có tiêu đề hay DOI nào gõ từ trí nhớ. Đây **chưa phải** danh sách đọc xong.

**Cách đọc bảng**
- **Đã đọc**: `tiêu đề` = mới thấy tiêu đề và thư mục. `trích đoạn` = chỉ thấy qua đoạn trích web hoặc blog. `tóm tắt` = đã đọc tóm tắt, nhiều bài chỉ phần đầu. `một phần toàn văn` = có đọc đoạn cụ thể. Không có bài nào đã đọc toàn văn.
- **Trích dẫn**: số từ OpenAlex hoặc Crossref ngày 02/11; hai nguồn lệch nhau. Để trống là không biết.
- **Truy cập**: `arXiv` = có bản arXiv. `mở*` = **suy ra từ nhà xuất bản**, chưa mở thử. `cần thư viện` = cần quyền trường.
- **Năm và nơi đăng** lấy từ bản đã xuất bản nếu có; ghi chú "theo tiêu đề" nghĩa là chưa kiểm chứng nội dung.

**Tóm tắt số lượng**: S1 29, S2 43, S3 23, S4 29, S5 21, S6 25, tổng 170, trong đó **35 core**. S2 vượt khoảng 15–30 vì gộp nhiều mạch nhỏ (chi phí biên, Stackelberg, tuân thủ, thông tin, ràng buộc phụ).

## 1. Giới hạn của lượt tìm này

- **Semantic Scholar không dùng được**: HTTP 429 ở mọi lần gọi trong suốt phiên. Thay bằng OpenAlex. Vẫn cần chạy lại khi có key.
- OpenAlex tìm theo `title_and_abstract.search` cho số đếm có ý nghĩa; `search` (mã B, H) quét cả toàn văn nên số đếm rất lớn và chỉ lấy 50 kết quả đầu theo độ liên quan.
- Mỗi truy vấn tiêu đề + tóm tắt chỉ lấy tối đa 100 kết quả, sắp theo số trích dẫn, nên **bài mới ít trích dẫn dễ bị bỏ sót**, nhất là ở T1, T6, T7, T10, T11, T12, K1, K4, K6.
- Bài mới phát hiện từ arXiv tới 10/2026 cho thấy lĩnh vực đang chạy nhanh; cần lặp lại truy vấn trước khi nộp.
- Lọc tiêu đề dùng từ khóa trước khi đọc, nên có thể mất bài có tiêu đề lạ.

## 2. Nhật ký tìm kiếm

Ngoài các truy vấn dưới đây còn có 20 lượt tìm web; những lượt dùng cho kiểm phản bác ghi ở `gap_checks.md`. Khoảng 20 ứng viên (kinh điển và bài tìm qua web) được xác minh riêng bằng Crossref hoặc trang gốc, nên không nằm trong 3375 bản ghi của bảng PRISMA. Tìm web trả về khoảng 10 liên kết mỗi lượt và không có số đếm tổng.

**S1**

| Mã | Nguồn | Truy vấn | Số kết quả | Đã lấy về |
|---|---|---|---|---|
| S1a | OpenAlex, tiêu đề + tóm tắt | `multi-agent reinforcement learning route guidance` | 50 | 50 |
| S1b | OpenAlex, tiêu đề + tóm tắt | `multi-agent reinforcement learning vehicle routing traffic network dynamic route choice` | 7 | 7 |
| S1c | OpenAlex, tiêu đề + tóm tắt | `deep reinforcement learning dynamic vehicle rerouting congestion` | 19 | 19 |
| S1d | OpenAlex, tiêu đề + tóm tắt | `reinforcement learning next-hop routing vehicles road network SUMO` | 0 | 0 |
| T1 | OpenAlex, tiêu đề + tóm tắt | `"reinforcement learning" AND ("route guidance" OR "route choice" OR "traffic assignment" OR rerouting OR "route recommendation" OR "routing game")` | 450 | 100 |
| T16 | OpenAlex, tiêu đề + tóm tắt | `("constrained" OR Lagrangian) AND "reinforcement learning" AND ("route guidance" OR "traffic assignment" OR rerouting OR "vehicle routing in road")` | 16 | 16 |
| T17 | OpenAlex, tiêu đề + tóm tắt | `("transfer learning" OR transferable OR "generalization" OR "unseen") AND "reinforcement learning" AND ("route guidance" OR rerouting OR "route choice" OR "traffic assignment")` | 40 | 40 |
| T18 | OpenAlex, tiêu đề + tóm tắt | `(uncertainty OR "partial observation" OR "partially observed" OR sparse) AND "reinforcement learning" AND ("route guidance" OR rerouting OR "traffic routing")` | 29 | 29 |
| T19 | OpenAlex, tiêu đề + tóm tắt | `"graph" AND "reinforcement learning" AND ("route guidance" OR rerouting OR "vehicle navigation" OR "traffic routing")` | 61 | 61 |
| K4 | OpenAlex, tiêu đề + tóm tắt | `("zero-shot" OR transferable OR "unseen network" OR "unseen networks" OR "cross-city") AND ("multi-agent" OR multiagent) AND (routing OR "route guidance" OR "route choice")` | 260 | 100 |
| K6 | OpenAlex, tiêu đề + tóm tắt | `"reinforcement learning" AND (routing OR rerouting OR "route guidance") AND (uncertainty OR "partial observability" OR "partially observable" OR "missing data") AND (traffic OR congestion OR vehicles)` | 335 | 100 |
| B1a | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `"reinforcement learning" AND ("route guidance" OR "route choice" OR "traffic assignment" OR rerouting OR "route recommendation")` | 9874 | 50 |
| B1b | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("multi-agent" OR multiagent) AND "reinforcement learning" AND (routing OR "route choice") AND (traffic OR vehicles OR congestion)` | 24324 | 50 |
| A1a | arXiv API | `all:"reinforcement learning" AND (ti:"route guidance" OR ti:"route choice" OR ti:"traffic assignment" OR ti:rerouting OR ti:"routing games")` | 8 | 8 |
| A1b | arXiv API | `(ti:"multi-agent" OR ti:multiagent OR ti:MARL) AND (ti:routing OR ti:route) AND (abs:traffic OR abs:vehicles OR abs:congestion)` | 46 | 40 |

**S2**

| Mã | Nguồn | Truy vấn | Số kết quả | Đã lấy về |
|---|---|---|---|---|
| S2a | OpenAlex, tiêu đề + tóm tắt | `system optimal routing reinforcement learning marginal cost` | 5 | 5 |
| S2b | OpenAlex, tiêu đề + tóm tắt | `difference rewards credit assignment traffic routing multiagent` | 0 | 0 |
| S2c | OpenAlex, tiêu đề + tóm tắt | `Stackelberg routing partial control selfish users` | 1 | 1 |
| S2d | OpenAlex, tiêu đề + tóm tắt | `route recommendation compliance system optimal navigation` | 6 | 6 |
| S2e | OpenAlex, tiêu đề + tóm tắt | `information design Bayesian persuasion traffic routing` | 6 | 6 |
| S2f | OpenAlex, tiêu đề + tóm tắt | `marginal cost congestion pricing agent-based simulation externality` | 2 | 2 |
| T2 | OpenAlex, tiêu đề + tóm tắt | `"system optimal" AND ("route guidance" OR routing OR "traffic assignment") AND ("reinforcement learning" OR learning)` | 40 | 40 |
| T3 | OpenAlex, tiêu đề + tóm tắt | `"path marginal cost" OR "marginal travel time" OR "link marginal cost" OR ("marginal cost" AND "dynamic traffic assignment")` | 14 | 14 |
| T4 | OpenAlex, tiêu đề + tóm tắt | `("difference rewards" OR "marginal contribution" OR "Shapley") AND (traffic OR congestion) AND (routing OR "route choice" OR rerouting)` | 86 | 86 |
| T5 | OpenAlex, tiêu đề + tóm tắt | `("marginal external" OR "congestion externality") AND ("agent-based" OR queue OR queueing OR spillback)` | 28 | 28 |
| T13 | OpenAlex, tiêu đề + tóm tắt | `(penetration OR "market share" OR compliance) AND ("route guidance" OR "dynamic rerouting" OR "vehicle rerouting") AND (simulation OR SUMO)` | 40 | 40 |
| T14 | OpenAlex, tiêu đề + tóm tắt | `("partial control" OR "fraction of" OR Stackelberg OR "coordinated fleet" OR "mixed autonomy") AND ("system optimal" OR "system optimum" OR "price of anarchy") AND (routing OR assignment)` | 40 | 40 |
| T15 | OpenAlex, tiêu đề + tóm tắt | `("side constraint" OR "side constraints" OR "link capacity constraint" OR "capacity constraints") AND ("traffic assignment" OR "traffic equilibrium" OR "traffic equilibria")` | 84 | 84 |
| K1 | OpenAlex, tiêu đề + tóm tắt | `"reinforcement learning" AND (externality OR "marginal delay" OR "delay caused" OR "delay imposed" OR "marginal travel time" OR "marginal cost") AND (routing OR route OR "traffic assignment")` | 210 | 100 |
| K5 | OpenAlex, tiêu đề + tóm tắt | `("penetration rate" OR "market penetration" OR "fraction of vehicles") AND ("system optimal" OR "system optimum" OR "total travel time") AND ("route guidance" OR routing OR rerouting) AND (reinforcement OR learning)` | 3 | 3 |
| B2a | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("system optimal" OR "system optimum" OR "social optimum") AND (routing OR "route guidance" OR "traffic assignment") AND (learning OR "reinforcement learning")` | 3788 | 50 |
| B2b | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("marginal cost" OR "marginal external cost" OR "marginal social cost") AND (congestion OR traffic) AND ("agent-based" OR "reinforcement learning" OR Q-learning)` | 4149 | 50 |
| B2c | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("difference rewards" OR "credit assignment" OR "reward shaping") AND (traffic OR routing OR congestion)` | 7674 | 50 |
| B2d | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `Stackelberg AND (routing OR "traffic assignment" OR "route guidance") AND (selfish OR "partial control" OR "mixed autonomy" OR compliance)` | 1838 | 50 |
| B2e | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("Bayesian persuasion" OR "information design") AND (traffic OR routing OR navigation)` | 6476 | 50 |
| B2f | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `(compliance OR "non-compliance" OR "penetration rate") AND ("route guidance" OR "route recommendation" OR "dynamic route")` | 5414 | 50 |
| A2a | arXiv API | `(abs:"system optimal" OR abs:"system optimum" OR abs:"social optimum") AND abs:"reinforcement learning" AND (abs:routing OR abs:route)` | 6 | 6 |
| A2b | arXiv API | `(abs:"marginal cost" OR abs:"marginal externality" OR abs:"difference rewards") AND abs:"reinforcement learning" AND (abs:traffic OR abs:routing OR abs:congestion)` | 14 | 14 |
| A2c | arXiv API | `abs:stackelberg AND (abs:routing OR abs:"traffic assignment") AND (abs:selfish OR abs:"mixed autonomy" OR abs:compliance)` | 7 | 7 |
| A2d | arXiv API | `(abs:"Bayesian persuasion" OR abs:"information design") AND (abs:traffic OR abs:routing OR abs:navigation)` | 33 | 33 |

**S3**

| Mã | Nguồn | Truy vấn | Số kết quả | Đã lấy về |
|---|---|---|---|---|
| S3a | OpenAlex, tiêu đề + tóm tắt | `navigation app cut-through traffic residential streets` | 0 | 0 |
| S3b | OpenAlex, tiêu đề + tóm tắt | `routing apps impact traffic congestion neighborhood Waze` | 0 | 0 |
| S3c | OpenAlex, tiêu đề + tóm tắt | `environmental capacity residential street traffic volume livability` | 0 | 0 |
| T10 | OpenAlex, tiêu đề + tóm tắt | `("navigation app" OR "navigation apps" OR "routing app" OR "routing apps" OR Waze) AND (traffic OR congestion OR neighborhood OR residential)` | 404 | 100 |
| T11 | OpenAlex, tiêu đề + tóm tắt | `("cut-through" OR "rat-running" OR "rat running") AND (traffic OR residential OR neighborhood)` | 221 | 100 |
| T12 | OpenAlex, tiêu đề + tóm tắt | `("low traffic neighbourhood" OR "low traffic neighborhoods" OR "traffic calming" OR "through traffic") AND (displacement OR "routing" OR "traffic volume" OR residents)` | 594 | 100 |
| K3 | OpenAlex, tiêu đề + tóm tắt | `(residential OR neighborhood OR neighbourhood OR "local street" OR "low-capacity") AND ("system optimal" OR "system optimum" OR "routing app" OR "navigation app") AND (constraint OR limit OR cap OR penalty OR impact)` | 28 | 28 |
| B3a | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("navigation app" OR "navigation apps" OR "routing app" OR "routing apps" OR Waze OR "Google Maps") AND (traffic OR congestion) AND (neighborhood OR neighbourhood OR residential OR "cut-through" OR "local streets")` | 12875 | 50 |
| B3b | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("cut-through" OR "rat running" OR "rat-running" OR "through traffic") AND (residential OR neighborhood OR neighbourhood) AND (traffic OR street)` | 8615 | 50 |
| B3c | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("environmental capacity" OR "liveable streets" OR "livable streets") AND (traffic OR street OR road)` | 4169 | 50 |
| A3a | arXiv API | `(abs:"navigation apps" OR abs:"routing apps" OR abs:"navigation app" OR abs:Waze OR abs:"routing app") AND (abs:traffic OR abs:congestion)` | 33 | 33 |

**S4**

| Mã | Nguồn | Truy vấn | Số kết quả | Đã lấy về |
|---|---|---|---|---|
| S4a | OpenAlex, tiêu đề + tóm tắt | `motorcycle dominated traffic simulation` | 23 | 23 |
| S4b | OpenAlex, tiêu đề + tóm tắt | `mixed traffic motorcycles Vietnam Ho Chi Minh City` | 7 | 7 |
| S4c | OpenAlex, tiêu đề + tóm tắt | `lane-free disordered heterogeneous traffic flow model` | 3 | 3 |
| S4d | OpenAlex, tiêu đề + tóm tắt | `gap acceptance motorcycles unsignalized intersection` | 5 | 5 |
| T6 | OpenAlex, tiêu đề + tóm tắt | `(motorcycle OR motorbike OR "two-wheeler" OR "powered two") AND ("traffic assignment" OR "route choice" OR routing OR "route guidance" OR navigation)` | 1512 | 100 |
| T7 | OpenAlex, tiêu đề + tóm tắt | `(alley OR alleys OR alleyway OR alleyways OR hutong OR "narrow road" OR "narrow streets" OR soi) AND (traffic OR "route choice" OR routing OR navigation) AND (motorcycle OR motorbike OR vehicle)` | 378 | 100 |
| T8 | OpenAlex, tiêu đề + tóm tắt | `("Ho Chi Minh" OR Hanoi OR Vietnam) AND (motorcycle OR motorbike) AND (simulation OR "traffic flow" OR microscopic OR SUMO OR VISSIM)` | 88 | 88 |
| T9 | OpenAlex, tiêu đề + tóm tắt | `(SUMO) AND (motorcycle OR motorbike OR "two-wheeler") AND (sublane OR "lane-free" OR calibration OR "mixed traffic")` | 4 | 4 |
| T22 | OpenAlex, tiêu đề + tóm tắt | `("mixed traffic" OR "heterogeneous traffic" OR "disordered") AND (motorcycle OR motorbike OR "two-wheeler" OR "powered two") AND ("fundamental diagram" OR capacity OR "gap acceptance" OR critical gap)` | 94 | 94 |
| K2 | OpenAlex, tiêu đề + tóm tắt | `(alley OR alleys OR alleyway OR alleyways OR lane OR "narrow street" OR "narrow streets") AND (motorcycle OR motorbike) AND (routing OR "route choice" OR shortcut OR navigation)` | 79 | 79 |
| B4a | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `(motorcycle OR motorbike) AND (dominated OR dominant) AND traffic AND (simulation OR model OR flow)` | 15645 | 50 |
| B4b | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `(motorcycle OR motorbike) AND (Vietnam OR Hanoi OR "Ho Chi Minh") AND traffic` | 4626 | 50 |
| B4c | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("lane-free" OR "non-lane-based" OR "disordered traffic" OR "porous flow" OR "heterogeneous traffic") AND ("flow" OR simulation OR "fundamental diagram")` | 23366 | 50 |
| B4d | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `"gap acceptance" AND (motorcycle OR motorbike OR "two-wheeler" OR "two wheeler")` | 709 | 50 |
| B4e | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `(alley OR alleyway OR hem OR "narrow street" OR "narrow streets" OR "narrow road") AND ("Ho Chi Minh" OR Vietnam OR Hanoi OR Bangkok OR Jakarta OR Manila) AND (traffic OR mobility OR transport)` | 12000 | 50 |
| A4a | arXiv API | `(abs:motorcycle OR abs:motorbike OR abs:"two-wheeler") AND (abs:routing OR abs:simulation OR abs:"lane-free" OR abs:traffic) AND (abs:dominated OR abs:Vietnam OR abs:mixed)` | 6 | 6 |
| A4b | arXiv API | `(abs:"lane-free" OR abs:"disordered traffic" OR abs:"non-lane") AND abs:traffic` | 31 | 31 |
| A4c | arXiv API | `(abs:alley OR abs:alleys OR abs:alleyway OR abs:"narrow streets") AND (abs:traffic OR abs:routing OR abs:navigation OR abs:vehicles)` | 12 | 12 |

**S5**

| Mã | Nguồn | Truy vấn | Số kết quả | Đã lấy về |
|---|---|---|---|---|
| S5a | OpenAlex, tiêu đề + tóm tắt | `mean field multi-agent reinforcement learning traffic` | 47 | 47 |
| S5b | OpenAlex, tiêu đề + tóm tắt | `graph attention multi-agent reinforcement learning transportation` | 75 | 50 |
| S5c | OpenAlex, tiêu đề + tóm tắt | `transferable reinforcement learning policy traffic network generalization` | 29 | 29 |
| S5d | OpenAlex, tiêu đề + tóm tắt | `scalable multi-agent reinforcement learning large-scale traffic` | 450 | 50 |
| B5a | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("mean field" OR "mean-field") AND ("reinforcement learning") AND (traffic OR routing OR transportation OR vehicles)` | 3320 | 50 |
| B5b | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("graph attention" OR "graph neural network" OR "attention") AND ("multi-agent reinforcement learning") AND (traffic OR routing OR vehicles)` | 12147 | 50 |
| B5c | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `(transferable OR "zero-shot" OR generalization OR inductive) AND "reinforcement learning" AND ("traffic signal" OR routing OR "road network")` | 76346 | 50 |
| A5a | arXiv API | `(abs:"mean field" OR abs:"mean-field") AND abs:"reinforcement learning" AND (abs:traffic OR abs:routing OR abs:vehicles)` | 15 | 15 |
| A5b | arXiv API | `(abs:transferable OR abs:"zero-shot" OR abs:inductive) AND abs:"reinforcement learning" AND (abs:routing OR abs:traffic) AND (abs:network)` | 93 | 40 |

**S6**

| Mã | Nguồn | Truy vấn | Số kết quả | Đã lấy về |
|---|---|---|---|---|
| S6c | OpenAlex, tiêu đề + tóm tắt | `probabilistic traffic speed estimation uncertainty quantification graph` | 1 | 1 |
| S6b | OpenAlex, tiêu đề + tóm tắt | `traffic speed kriging graph neural network unobserved roads uncertainty` | 0 | 0 |
| T20 | OpenAlex, tiêu đề + tóm tắt | `(kriging OR "unobserved locations" OR "unobserved roads" OR "unobserved links") AND traffic AND (uncertainty OR probabilistic OR Bayesian OR "Gaussian process")` | 91 | 91 |
| T21 | OpenAlex, tiêu đề + tóm tắt | `(probe OR "floating car" OR GPS) AND ("traffic state estimation" OR "speed estimation" OR "travel time estimation") AND ("Gaussian process" OR Bayesian OR uncertainty) AND (network OR urban)` | 24 | 24 |
| B6a | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("traffic state estimation" OR "speed estimation") AND (network OR urban) AND (probe OR "floating car" OR sparse)` | 4100 | 50 |
| B6b | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `(kriging OR "unobserved" OR "missing") AND ("graph neural network" OR "graph") AND (traffic speed OR "traffic state")` | 80965 | 50 |
| B6c | OpenAlex, `search` (cả toàn văn; chỉ lấy 50 đầu theo độ liên quan) | `("uncertainty quantification" OR probabilistic OR "conformal") AND ("traffic state" OR "traffic speed" OR "traffic forecasting") AND graph` | 6031 | 50 |
| A6a | arXiv API | `(abs:kriging) AND (abs:traffic) AND (abs:graph)` | 5 | 5 |
| A6b | arXiv API | `abs:"traffic state estimation" AND (abs:sparse OR abs:probe OR abs:uncertainty)` | 23 | 23 |
| A6c | arXiv API | `(abs:uncertainty OR abs:conformal) AND abs:"traffic" AND abs:graph AND abs:(speed OR state)` | 39 | 39 |

**Lần trích dẫn xuôi (OpenAlex `cites:`)**: số bài trích dẫn và số tài liệu tham khảo của bài gốc.

| Bài gốc | Được trích | Tham khảo |
|---|---|---|
| Markov routing games, TR-C 2022 | 69 | 73 |
| Yun, TR-C 2024 | 13 | 52 |
| TransRL, TR-C 2025 | 14 | 74 |
| MARL-OD-DA, 2025 | 8 | 23 |
| RouteRL, 2025 | 3 | 28 |
| Negative externalities of GPS, ITSC 2016 | 44 | 17 |
| Path marginal cost approximation, TR-C 2018 | 17 | 32 |
| SO-DTA with Partial Control, Transp. Sci. 2018 | 22 | 45 |

Lần trích dẫn ngược chưa thực hiện.

## 3. Ứng viên theo mạch

### S1. MARL / deep RL cho dẫn đường và định tuyến động

| Ưu tiên | Đã đọc | Tiêu đề | Năm | Nơi đăng | DOI / arXiv | Trích dẫn | Truy cập | Vì sao liên quan |
|---|---|---|---|---|---|---|---|---|
| **core** | tóm tắt | URB – Urban Routing Benchmark for RL-equipped Connected Autonomous Vehicles | 2025 | NeurIPS 2025 D&B | arXiv:2505.17734 |  | arXiv | 29 mạng thật; MARL hiện đại hiếm khi thắng người lái. Chuẩn so sánh bắt buộc. |
| **core** | tiêu đề | RouteRL: Multi-agent reinforcement learning framework for urban route choice with autonomous vehicles | 2025 | SoftwareX | 10.1016/j.softx.2025.102279; arXiv:2502.20065 | 3 | arXiv | Khung MARL chọn tuyến cho AV trên SUMO, nền của URB và Psarou. |
| **core** | tóm tắt | Multi-agent reinforcement learning for Markov routing games: A new modeling paradigm for dynamic traffic assignment | 2022 | TR-C | 10.1016/j.trc.2022.103560; arXiv:2011.10915 | 69 | arXiv | MARL en-route (mean-field deep Q) cho DTA, nhưng ích kỷ, đích là cân bằng. |
| **core** | tóm tắt | Scalable and reliable multi-agent reinforcement learning for traffic assignment | 2025 | Commun. Transp. Res. | 10.1016/j.commtr.2025.100225; arXiv:2506.17029 | 8 | arXiv | Agent là cặp OD (MARL-OD-DA), mục tiêu gán luồng; hướng mở rộng khác. |
| **core** | tóm tắt | Real-time system optimal traffic routing under uncertainties — Can physics models boost reinforcement learning? | 2025 | TR-C | 10.1016/j.trc.2025.105040; arXiv:2407.07364 | 14 | arXiv | **TransRL**: SO cho một phần xe, RL + mô hình vật lý, mạng vài trăm link. Đối thủ gần ở TR-C. |
| **core** | một phần toàn văn | Reinforcement Learning-Based Sequential Route Recommendation for System-Optimal Traffic Assignment | 2026 | IEEE Open Journal of Intelligent T | 10.1109/ojits.2026.3696779; arXiv:2505.20889 | 4 | arXiv | SO bằng một agent trung tâm, reward là marginal travel time giải tích; tĩnh, 13 nút, tuân thủ 100%. |
| **core** | tóm tắt | Network-Constrained Policy Optimization for Adaptive Multi-agent Vehicle Routing | 2026 | ACM Transactions on Spatial Algori | 10.1145/3822510; arXiv:2510.26089 | 1 | arXiv | Agent ở nút giao, GAT, phân cấp hub; Toronto, Manhattan. Giảm thời gian đi trung bình, không có p. |
| **core** | tóm tắt | Decentralized graph attention multi-agent reinforcement learning for adaptive urban traffic routing | 2026 | Scientific Reports | 10.1038/s41598-026-56204-2 | 0 | mở* | MA-GRL: MAPPO + GAT theo xe, 100 xe, Monaco; 87% giữ hiệu quả zero-shot giữa 3 thành phố. |
| **core** | tiêu đề | Providing real-time en-route suggestions to CAVs for congestion mitigation: A two-way deep reinforcement learning approach | 2024 | TR-B | 10.1016/j.trb.2024.103014 | 9 | **cần thư viện** | DRL hai chiều gợi ý en-route cho CAV, TR-B; không có tóm tắt trong OpenAlex. |
| relevant | tiêu đề | Markov game for CV joint adaptive routing in stochastic traffic networks: A scalable learning approach | 2024 | TR-B | 10.1016/j.trb.2024.102997 | 6 | **cần thư viện** | Trò chơi Markov cho định tuyến CV, TR-B. |
| relevant | tóm tắt | Can Cooperative Routing Mitigate System-Level Inefficiency in Road Networks? | 2026 | Lecture notes in computer science | 10.1007/978-3-032-39395-1_9 | 0 | **cần thư viện** | MARL hợp tác giảm price of anarchy, DTA động có kiểm soát. |
| relevant | tóm tắt | Joint Optimization of Traffic Signal Control and Vehicle Routing in Signalized Road Networks using Multi-Agent Deep Reinforcement Learning | 2023 | arXiv | arXiv:2310.10856 |  | arXiv | MADRL đồng thời đèn và tuyến. |
| relevant | tóm tắt | Hierarchical Reinforcement Learning for Dynamic Autonomous Vehicle Navigation at Intelligent Intersections | 2023 | ACM SIGKDD Conference on Knowledge | 10.1145/3580305.3599839 | 32 | **cần thư viện** | NavTL: AV đổi tuyến + đèn, giao thông hỗn hợp, KDD. |
| relevant | tóm tắt | Dynamic urban traffic rerouting with fog‐cloud reinforcement learning | 2023 | Computer-Aided Civil and Infrastru | 10.1111/mice.13115 | 27 | **cần thư viện** | GAT Q + EBkSP, xử lý chuyển dịch tắc nghẽn. |
| relevant | tóm tắt | Urban Traffic Route Guidance Method With High Adaptive Learning Ability Under Diverse Traffic Scenarios | 2020 | IEEE T-ITS | 10.1109/tits.2020.2978227 | 46 | **cần thư viện** | Dẫn đường thích nghi đa kịch bản. |
| relevant | tóm tắt | Transfer Learning-Based Deep Reinforcement Learning Approach for Robust Route Guidance in Mixed Traffic Environment | 2024 | IEEE Access | 10.1109/access.2024.3395430 | 14 | **cần thư viện** | TLARG: chuyển giao để hội tụ trên mạng rộng, xe hỗn hợp. Liên quan G6. |
| relevant | tóm tắt | Development of Reinforcement Learning-Based Traffic Predictive Route Guidance Algorithm Under Uncertain Traffic Environment | 2022 | IEEE Access | 10.1109/access.2022.3179383 | 12 | **cần thư viện** | RL-TPVR, đặc trưng dự báo khi trạng thái bất định. Liên quan G5. |
| relevant | tiêu đề | XRouting: Explainable Vehicle Rerouting for Urban Road Congestion Avoidance using Deep Reinforcement Learning | 2022 | IEEE International Smart Cities Co | 10.1109/isc255366.2022.9922404 | 8 | **cần thư viện** | Đổi tuyến có giải thích bằng DRL. |
| relevant | tiêu đề | COREAN: Context-conditioned meta-reinforcement learning for expectation-aligned route guidance in time-critical urban mobility | 2026 | TR-C | 10.1016/j.trc.2026.105836 | 0 | **cần thư viện** | Meta-RL cho dẫn đường, TR-C 2026; theo tiêu đề. |
| relevant | tiêu đề | Multi-Agent Coordination in Autonomous Vehicle Routing: A Simulation-Based Study of Communication, Memory, and Routing Loops | 2025 | arXiv | arXiv:2511.17656 |  | arXiv | So sánh giao tiếp, bộ nhớ khi điều phối định tuyến; theo tiêu đề. |
| relevant | tiêu đề | Multi-agent deep reinforcement learning based on cloud-edge computing for urban vehicle route guidance | 2025 | Cluster Computing | 10.1007/s10586-025-05842-8 | 3 | **cần thư viện** | MADRL cho dẫn đường; theo tiêu đề. |
| relevant | tóm tắt | Balancing Mobility Efficiency and Environmental Exposure During Mega Events: A Multi-agent Routing Framework | 2026 | arXiv | arXiv:2610.37702 | 0 | arXiv | SARSA đa agent, cân bằng thời gian và phơi nhiễm; có mục tiêu ngoài thời gian đi. |
| relevant | tiêu đề | Social implications of coexistence of CAVs and human drivers in the context of route choice | 2025 | Scientific Reports | 10.1038/s41598-025-90783-w | 3 | mở* | Tác động xã hội của CAV trong chọn tuyến. |
| relevant | tiêu đề | Analysing Congestion Problems in Multi-agent Reinforcement Learning | 2017 | arXiv | arXiv:1702.08736 |  | arXiv | Tắc nghẽn trong MARL nói chung. |
| relevant | tóm tắt | Bayesian Optimization for Multi-Agent Routing in Markov Games | 2022 | IEEE International Conference on I | 10.1109/itsc55140.2022.9922110 | 1 | **cần thư viện** | Stackelberg hai tầng, đầu dưới là mean-field deep Q. |
| relevant | tiêu đề | A Distributed Assignment Method for Dynamic Traffic Assignment Using Heterogeneous-Adviser Based Multi-Agent Reinforcement Learning | 2020 | IEEE Access | 10.1109/access.2020.3018267 | 10 | **cần thư viện** | MARL cho DTA. |
| background | tiêu đề | A multiagent reinforcement learning approach to en-route trip building | 2016 | International Joint Conference on  | 10.1109/ijcnn.2016.7727899 | 35 | **cần thư viện** | MARL en-route đời đầu. |
| background | tiêu đề | Agentic Large Language Models for day-to-day route choices | 2025 | TR-C | 10.1016/j.trc.2025.105307 | 25 | **cần thư viện** | LLM cho chọn tuyến day-to-day. |
| background | tiêu đề | A bibliometric analysis and review on reinforcement learning for transportation applications | 2023 | Transportmetrica B Transport Dynam | 10.1080/21680566.2023.2179461 | 29 | **cần thư viện** | Khảo sát trắc lượng RL trong giao thông. |

### S2. Tối ưu hệ thống, chi phí biên, chia công, Stackelberg, tuân thủ, thông tin

| Ưu tiên | Đã đọc | Tiêu đề | Năm | Nơi đăng | DOI / arXiv | Trích dẫn | Truy cập | Vì sao liên quan |
|---|---|---|---|---|---|---|---|---|
| **core** | một phần toàn văn | Autonomous Vehicles need Social Awareness to Find Optima in Multi-agent Reinforcement Learning Routing Games | 2026 | Adaptive Agents and Multi-Agents S | 10.65109/fthn6981; arXiv:2510.11410 | 0 | arXiv | Marginal cost bằng chạy lại từng AV; 10 AV; tác giả viết chi phí tăng theo cấp số mũ với không gian hành động; xét trường hợp SO trùng UE. |
| **core** | tóm tắt | Collective Autonomous Vehicle Routing Needs Social Awareness for Coexistence with Human Drivers | 2026 | arXiv | arXiv:2610.13439 | 0 | arXiv | Bản 10/2026: Ingolstadt, Provins, nhiều tỉ lệ AV; chạy phản thực chọn lọc để giảm chi phí. **Đối thủ trực tiếp G3.** |
| **core** | tóm tắt | Navigating the non-compliance effects on system optimal route guidance using reinforcement learning | 2024 | TR-C | 10.1016/j.trc.2024.104721 | 13 | **cần thư viện** | Yun et al.: NFSP, UE/SO với không tuân thủ, mô phỏng vi mô. Đối thủ trực tiếp G4. |
| **core** | tóm tắt | Regional route guidance with realistic compliance patterns: Application of deep reinforcement learning and MPC | 2023 | TR-C | 10.1016/j.trc.2023.104440 | 44 | **cần thư viện** | Dẫn đường theo vùng có mẫu tuân thủ thực tế, DRL + MPC. |
| **core** | tóm tắt | Discrete-Time System Optimal Dynamic Traffic Assignment (SO-DTA) with Partial Control for Physical Queuing Networks | 2018 | Transportation Science | 10.1287/trsc.2017.0800 | 22 | **cần thư viện** | Điều khiển một phần luồng, hàng đợi vật lý, tối ưu liên tục. |
| **core** | tiêu đề | A path marginal cost approximation algorithm for system optimal quasi-dynamic traffic assignment | 2018 | TR-C | 10.1016/j.trc.2018.01.002 | 17 | **cần thư viện** | Xấp xỉ PMC không cần chạy lại; đe dọa phần "tính được" của G3. |
| **core** | tiêu đề | System-optimal dynamic traffic assignment with and without queue spillback: Its path-based formulation and solution via approximate path marginal cost | 2012 | TR-B | 10.1016/j.trb.2012.02.008 | 65 | **cần thư viện** | PMC có tràn ngược, kinh điển. |
| **core** | tiêu đề | Congestion pricing in a real-world oriented agent-based simulation context | 2019 | Res. Transp. Econ. | 10.1016/j.retrec.2019.01.002 | 28 | **cần thư viện** | Kaddoura & Nagel: quy trễ theo hàng đợi cho từng agent, có tràn ngược. |
| **core** | tóm tắt | Optimal Road Pricing: Towards an Agent-based Marginal Social Cost Approach | 2014 | TU Berlin VSP WP 14-01 | https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2014/14-01/KaddouraKickhoefer2014CongestionPricing.pdf |  | mở | Kaddoura & Kickhöfer: cơ sở cho H2, phí theo từng agent trong mô phỏng, có cơ sở dữ liệu ghi tương tác giữa các xe. |
| **core** | tiêu đề | The effectiveness of Stackelberg strategies and tolls for network congestion games | 2012 | ACM TALG | 10.1145/2344422.2344426 | 44 | **cần thư viện** | Swamy: cận PoA theo tỉ lệ điều khiển. |
| **core** | tiêu đề | Side constrained traffic equilibrium models – analysis, computation and applications | 1999 | TR-B | 10.1016/s0191-2615(98)00024-1 | 138 | **cần thư viện** | Larsson & Patriksson. **Đã xác minh nguồn** mà RESEARCH_V4 §6 ghi "cần kiểm tra". Chỉ cần nếu giữ ràng buộc hẻm. |
| **core** | tóm tắt | Proposing a Simulation-Based Dynamic System Optimal Traffic Assignment Algorithm for SUMO: An Approximation of Marginal Travel Time | 2022 | SUMO Conference Proceedings | 10.52825/scp.v3i.119 | 11 | mở* | SB-DSO trong SUMO, mô hình thay thế cho marginal travel time. **Dùng ngay cho Phần 1** (cổng A). |
| **core** | tiêu đề | Toll-Based Learning for Minimising Congestion under Heterogeneous Preferences | 2020 | Adaptive Agents and Multi-Agents S | 10.65109/dzcu8586 | 10 | mở* | GTQ-learning: thu phí biên + Q-learning, AAMAS 2020. |
| relevant | tóm tắt | Path-based system optimal dynamic traffic assignment: A subgradient approach | 2020 | TR-B | 10.1016/j.trb.2020.02.004 | 23 | **cần thư viện** | Tính PMC hiệu quả. |
| relevant | tóm tắt | On Path-based Marginal Cost of Heterogeneous Traffic Flow for General Networks | 2026 | SSRN Electronic Journal | 10.2139/ssrn.6153831; arXiv:2602.05565 | 0 | arXiv | PMC cho dòng hỗn hợp nhiều lớp xe, gần với xe máy + ô tô. |
| relevant | tóm tắt | Stackelberg Routing of Autonomous Cars in Mixed-Autonomy Traffic Networks | 2022 | Proceedings of the ... American Co | 10.23919/acc53348.2022.9867856; arXiv:2204.10457 | 3 | arXiv | Stackelberg, xe tự hành vị tha. |
| relevant | tóm tắt | TASR: A Novel Trust-Aware Stackelberg Routing Algorithm to Mitigate Traffic Congestion | 2024 | IEEE International Conference on S | 10.1109/smartcomp61445.2024.00041; arXiv:2403.19831 | 5 | arXiv | Tuân thủ theo xác suất, trust. |
| relevant | tóm tắt | System-Optimal Dynamic Traffic Assignment with Partial Users Control: An Analysis of Different Strategies | 2023 | IEEE International Conference on I | 10.1109/itsc57777.2023.10421933 | 0 | **cần thư viện** | SO-DTA, phần không tuân thủ phản ứng theo logit. |
| relevant | tóm tắt | Assessing the Impact of Non-Compliant Users Response to System-Optimal Dynamic Traffic Assignment | 2023 | IEEE Conference on Decision and Co | 10.1109/cdc49753.2023.10383488 | 2 | **cần thư viện** | Tương tự, CDC. |
| relevant | tóm tắt | On the impact of coordinated fleets size on traffic efficiency | 2024 | IEEE Conference on Decision and Co | 10.1109/cdc56724.2024.10886835 | 4 | **cần thư viện** | PoA theo quy mô đội xe, có ngưỡng tối thiểu trên mạng hai đầu cuối. |
| relevant | tóm tắt | Traffic Optimization for a Mixture of Self-Interested and Compliant Agents | 2018 | AAAI Publications (The Association | 10.1609/aaai.v32i1.11444 | 32 | mở* | Sharon et al.: số xe tuân thủ tối thiểu để đạt SO. |
| relevant | tóm tắt | Routing for Traffic Networks With Mixed Autonomy | 2020 | IEEE Transactions on Automatic Con | 10.1109/tac.2020.3020059 | 35 | **cần thư viện** | Cận PoA với xe hỗn hợp. |
| relevant | tiêu đề | On Social Optimal Routing Under Selfish Learning | 2016 | IEEE Transactions on Control of Ne | 10.1109/tcns.2016.2619910 | 16 | **cần thư viện** | Stackelberg với người học ích kỷ. |
| relevant | tóm tắt | Information Design in Nonatomic Routing Games With Partial Participation: Computation and Properties | 2022 | IEEE Transactions on Control of Ne | 10.1109/tcns.2022.3165012; arXiv:2005.03000 | 41 | arXiv | Persuasion với tham gia một phần. |
| relevant | tiêu đề | Reducing congestion through information design | 2017 | Allerton Conference on Communicati | 10.1109/allerton.2017.8262884 | 83 | **cần thư viện** | Thiết kế thông tin kinh điển. |
| relevant | tiêu đề | Informational Braess’ Paradox: The Effect of Information on Traffic Congestion | 2018 | Operations Research | 10.1287/opre.2017.1712 | 136 | **cần thư viện** | Thông tin có thể gây hại. |
| relevant | tóm tắt | Minimizing the total travel time with limited unfairness in traffic networks | 2020 | Computers & Operations Research | 10.1016/j.cor.2020.105016 | 31 | **cần thư viện** | SO có ràng buộc công bằng. |
| relevant | tóm tắt | Improving the performance of a traffic system by fair rerouting of travelers | 2021 | European Journal of Operational Re | 10.1016/j.ejor.2021.06.036 | 15 | **cần thư viện** | Tuyến SO chấp nhận được về hành vi. |
| relevant | tóm tắt | Assessing traveler compliance with the social optimum: A stated preference study | 2021 | Travel Behaviour and Society | 10.1016/j.tbs.2020.12.005 | 14 | **cần thư viện** | Khảo sát tuân thủ tuyến xã hội. |
| relevant | tiêu đề | Emergence of cooperative route-choice: A model and experiment of compliance with system-optimal ATIS | 2018 | TR-F | 10.1016/j.trf.2018.09.007 | 43 | **cần thư viện** | Thí nghiệm tuân thủ ATIS tối ưu hệ thống. |
| relevant | trích đoạn | Route Recommendations for Traffic Management Under Learned Partial Driver Compliance | 2025 | arXiv | arXiv:2504.02993 |  | arXiv | Học mức tuân thủ một phần rồi tối ưu luồng. |
| relevant | tiêu đề | Toll-based reinforcement learning for efficient equilibria in route choice | 2020 | The Knowledge Engineering Review | 10.1017/s0269888920000119 | 11 | **cần thư viện** | TQ-learning. |
| relevant | tiêu đề | Analysing the impact of travel information for minimising the regret of route choice | 2018 | TR-C | 10.1016/j.trc.2017.11.011 | 46 | **cần thư viện** | Regret trong chọn tuyến khi có thông tin, TR-C. |
| relevant | tiêu đề | Day-to-day traffic control for networks mixed with regular human-piloted and connected autonomous vehicles | 2023 | TR-B | 10.1016/j.trb.2023.102847 | 24 | **cần thư viện** | Điều khiển day-to-day với xe hỗn hợp, TR-B. |
| relevant | tóm tắt | City-Scale System-Optimal Route Planning with Route Replanning | 2021 | IEEE International Conference on B | 10.1109/bigdata52589.2021.9671357 | 5 | **cần thư viện** | Kế hoạch SO theo lô, có tái lập tuyến; xem thêm bằng sáng chế US12387597. |
| relevant | tóm tắt | Efficient Algorithm for the Traffic Assignment Problem with Side Constraints | 2020 | TRR | 10.1177/0361198120912234 | 16 | **cần thư viện** | ALM + path-based, có thể làm baseline nếu giữ ràng buộc. |
| relevant | tóm tắt | Side-Constrained Dynamic Traffic Equilibria | 2024 | Operations Research | 10.1287/opre.2023.0577 | 2 | **cần thư viện** | Cân bằng động có ràng buộc phụ (Graf & Harks). Chỉ cần nếu giữ ràng buộc hẻm. |
| relevant | tiêu đề | Hypercongestion in downtown metropolis | 2013 | J. Urban Econ. | 10.1016/j.jue.2012.12.004 | 59 | **cần thư viện** | Fosgerau & Small. |
| background | tiêu đề | Bridging the user equilibrium and the system optimum in static traffic assignment: a review | 2023 | 4OR | 10.1007/s10288-023-00540-w | 37 | **cần thư viện** | Tổng quan UE–SO. |
| background | tiêu đề | From user equilibrium to system optimum: a literature review on the role of travel information, bounded rationality and non-selfish behaviour at the network and individual levels | 2016 | Transport Reviews | 10.1080/01441647.2015.1125399 | 80 | **cần thư viện** | Tổng quan vai trò thông tin, lý trí giới hạn. |
| background | tiêu đề | Counterfactual Multi-Agent Policy Gradients | 2018 | AAAI | 10.1609/aaai.v32i1.11794 | 1431 | mở* | COMA, chia công phản thực. |
| background | tiêu đề | Aligning social welfare and agent preferences to alleviate traffic congestion | 2008 | AAMAS | 10.65109/oxjz2271 | 0 | mở* | Tumer et al., difference rewards cho giao thông. |
| background | tiêu đề | Stackelberg scheduling strategies | 2001 | STOC | 10.1145/380752.380783 | 90 | **cần thư viện** | Roughgarden. |

### S3. Tác động của app, đi tắt, ngoại ứng lên đường dân cư

| Ưu tiên | Đã đọc | Tiêu đề | Năm | Nơi đăng | DOI / arXiv | Trích dẫn | Truy cập | Vì sao liên quan |
|---|---|---|---|---|---|---|---|---|
| **core** | tóm tắt | Negative externalities of GPS-enabled routing applications: A game theoretical approach | 2016 | IEEE International Conference on I | 10.1109/itsc.2016.7795614 | 44 | **cần thư viện** | Thai, Laurent-Brouty, Bayen: app tăng tải đường sức chứa thấp ở LA. |
| **core** | tóm tắt | Regrets in Routing Networks | 2019 | ACM Transactions on Spatial Algori | 10.1145/3325916 | 14 | **cần thư viện** | Cabannes et al.: đo tác động app bằng average marginal regret. |
| **core** | trích đoạn | Urban congestion relief experiments through routing-app interventions | 2026 | Nature Cities | 10.1038/s44284-026-00443-x | 2 | **cần thư viện** | Thí nghiệm thật của Google, 10 thành phố Mỹ, dưới 2% chuyến bị đổi; tốc độ trung vị tăng khoảng 2% (số từ blog, chưa đọc bài). |
| **core** | trích đoạn | Socially-aware Evaluation Framework for Transportation | 2023 | Transportation Letters | 10.1080/19427867.2022.2157366 |  | **cần thư viện** | Kuncheria, Walker, Macfarlane: **SO làm xấu tải đường dân cư so với UE**. Bằng chứng cho mục tiêu phụ. |
| **core** | tóm tắt | The traffic concentration effects of urban navigation services | 2026 | Nature Communications | 10.1038/s41467-026-75254-8 | 1 | mở* | Nature Commun.: app càng nhiều, tuyến càng ít đa dạng; Florence, Milan, Rome. |
| relevant | tóm tắt | Traffic jam by GPS: A systematic analysis of the negative social externalities of large-scale navigation technologies | 2024 | PLoS ONE | 10.1371/journal.pone.0308260 | 7 | mở* | Phân tích nội dung 90 bài báo về ngoại ứng lên khu dân cư. |
| relevant | tóm tắt | Achieving social routing via navigation apps: User acceptance of travel time sacrifice | 2024 | Transport Policy | 10.1016/j.tranpol.2024.01.026 | 13 | **cần thư viện** | Mức chấp nhận hy sinh thời gian đi; Amsterdam, Helsinki. |
| relevant | tiêu đề | Measuring Regret in Routing: Assessing the Impact of Increased App Usage | 2018 | IEEE International Conference on I | 10.1109/itsc.2018.8569758 | 10 | **cần thư viện** | Berkeley, ITSC 2018. |
| relevant | tóm tắt | A Decision Support System for Evaluating the Impacts of Routing Applications on Urban Mobility | 2018 | IEEE International Conference on I | 10.1109/itsc.2018.8569622 | 3 | **cần thư viện** | Berkeley: công cụ đánh giá tác động app lên đường phụ. |
| relevant | tóm tắt | Simulating the Impact of Dynamic Rerouting on Metropolitan-scale Traffic Systems | 2023 | ACM Transactions on Modeling and C | 10.1145/3579842 | 18 | **cần thư viện** | Mobiliti: mô phỏng đổi tuyến quy mô đô thị. |
| relevant | tiêu đề | Modeling the impact of on-line navigation devices in traffic flows | 2019 | IEEE Conference on Decision and Co | 10.1109/cdc40024.2019.9030208 | 11 | **cần thư viện** | CDC 2019. |
| relevant | tiêu đề | Navigation Systems May Deteriorate Stability in Traffic Networks | 2024 | IEEE Open Journal of Control Syste | 10.1109/ojcsys.2024.3397270 | 2 | **cần thư viện** | Mất ổn định do app. |
| relevant | trích đoạn | Potential Detrimental Effects of Real-Time Route Recommendations in Traffic Networks | 2024 | SSRN Electronic Journal | 10.2139/ssrn.5022862; arXiv:2303.17923 | 1 | arXiv | Tuân thủ cao có thể làm giảm hiệu quả cân bằng. |
| relevant | tóm tắt | Spatio-temporal road charge: a potential remedy for increasing local streets congestion | 2017 | RePEc: Research Papers in Economic | 10.7922/g2jw8bsq | 1 | mở* | Phí theo không gian–thời gian chống tắc đường địa phương. |
| relevant | tóm tắt | Dynamic Routing of Heterogeneous Users After Traffic Disruptions Under a Mixed Information Framework | 2022 | Frontiers in Future Transportation | 10.3389/ffutr.2022.851069 | 5 | mở* | App gợi ý cho người có thông tin, gián đoạn. |
| relevant | tiêu đề | Impact of navigation apps on congestion and spread dynamics on a transportation network | 2024 | Data Science for Transportation | 10.1007/s42421-024-00099-w | 8 | **cần thư viện** | 30–60% dùng định tuyến động cho kết quả tốt (qua snippet). |
| relevant | tiêu đề | When apps rule the road: The proliferation of navigation apps is causing traffic chaos. It's time to restore order | 2019 | IEEE Spectrum | 10.1109/mspec.2019.8847586 | 41 | **cần thư viện** | Macfarlane, IEEE Spectrum. |
| relevant | tóm tắt | Residential through traffic: Quantitative evidence from participant observation | 2017 | UWE Research Repository (UWE Brist |  | 0 | ? | Cộng đồng tự đếm xe đi xuyên khu dân cư. |
| relevant | tiêu đề | Changes in motor traffic in London’s Low Traffic Neighbourhoods and boundary roads | 2023 | Case Studies on Transport Policy | 10.1016/j.cstp.2023.101124 | 29 | **cần thư viện** | Lưu lượng trong và quanh LTN. |
| relevant | tiêu đề | Evaluation of low traffic neighbourhood (LTN) impacts on NO2 and traffic | 2022 | TR-D | 10.1016/j.trd.2022.103536 | 49 | **cần thư viện** | LTN: tác động lên NO2 và giao thông. |
| background | tiêu đề | In Waze We Trust: Algorithmic Governance of the Public Sphere | 2018 | Media and Communication | 10.17645/mac.v6i4.1710 | 55 | mở* | Quản trị thuật toán, góc độ xã hội. |
| background | tiêu đề | Do algorithms have a right to the city? Waze and algorithmic spatiality | 2020 | Cultural Studies | 10.1080/09502386.2020.1755711 | 38 | **cần thư viện** | Waze và không gian đô thị. |
| background | tóm tắt | City of Alexandria cut-through research report | 2020 | Báo cáo thành phố | https://media.alexandriava.gov/docs-archives/tes/info/city-of-alexandria-cut-through-research---report-5.7.2020%3Dfinal.pdf |  | mở | Tổng hợp Fremont, Leonia; biện pháp có thể làm tắc dời chỗ. |

### S4. Xe máy, không làn, hẻm, chấp nhận khe

| Ưu tiên | Đã đọc | Tiêu đề | Năm | Nơi đăng | DOI / arXiv | Trích dẫn | Truy cập | Vì sao liên quan |
|---|---|---|---|---|---|---|---|---|
| **core** | tóm tắt | Identifying the role of route choice behavior of motorcycle riders in microscopic simulation modeling under mixed traffic conditions | 2024 | TRIP | 10.1016/j.trip.2024.101247 | 1 | mở* | **Gần nhất với G1**: AIMSUN, Ninh Kiều (Cần Thơ), thông tin thời gian thực và tuân thủ; không tối ưu, không nói về hẻm. |
| **core** | tiêu đề | A porous flow approach to modeling heterogeneous traffic in disordered systems | 2011 | Procedia SBS (ISTTT) | 10.1016/j.sbspro.2011.04.534 | 22 | mở* | Nair et al. Bản TR-B ở TRID 1130198. |
| **core** | tóm tắt | Beyond Lanes: Traffic Flow Dynamics in Disordered Conditions Based on High-Resolution Trajectory Data | 2026 | arXiv | arXiv:2608.00602 |  | arXiv | Giản đồ cơ bản 2D từ dữ liệu UAV. |
| **core** | tiêu đề | Rethinking metropolitan production from its underside: A view from the alleyways of Hồ Chí Minh City | 2018 | Env. & Planning A | 10.1177/0308518x17751230 | 16 | **cần thư viện** | Gibert(-Flutre): nguồn của số 85%, cần kiểm tra trên toàn văn. |
| relevant | tóm tắt | Entropy-Based k Shortest-Path Routing for Motorcycles: A Simulated Case Study in Jakarta | 2020 | International Journal of Advanced  | 10.14569/ijacsa.2020.0110758 | 3 | mở* | App xe máy Jakarta, tuyến đa dạng theo EBkSP. **Làm yếu G1 ở mức "định tuyến xe máy".** |
| relevant | tóm tắt | Internet of Things Solution for Motorcycle Riders to Overcome Traffic Jam in Jakarta Using EBkSP | 2018 | International Conference on Inform | 10.1109/ictc.2018.8539395 | 8 | **cần thư viện** | Như trên; ghi rõ dùng đường hẹp làm đường tắt. **Bài cần đọc cho G1.** |
| relevant | tóm tắt | Contextual Route Recommendation System in Heterogeneous Traffic Flow | 2021 | Sustainability | 10.3390/su132313191 | 12 | mở* | Gợi ý tuyến theo loại xe, xe máy 77,5%. |
| relevant | tiêu đề | Modeling and analysis of mixed flow of cars and powered two wheelers | 2018 | TR-C | 10.1016/j.trc.2018.02.004 | 41 | **cần thư viện** | Dòng ô tô + xe hai bánh, TR-C. |
| relevant | tóm tắt | H-CTM for simulating non-lane-based heterogeneous traffic | 2017 | Transportation Letters | 10.1080/19427867.2017.1373439 | 15 | **cần thư viện** | CTM cho dòng không làn. |
| relevant | tóm tắt | Cell Transmission Modeling of Heterogeneous Disordered Traffic | 2019 | Journal of Transportation Engineer | 10.1061/jtepbs.0000248 | 8 | **cần thư viện** | CTM dòng hỗn loạn. |
| relevant | tóm tắt | Empirical Investigation of Fundamental Diagrams in Mixed Traffic | 2023 | IEEE Access | 10.1109/access.2023.3242971 | 14 | **cần thư viện** | FD theo thành phần xe. |
| relevant | tóm tắt | Modelling integrated movements of motorcycles at urban merge sections under mixed traffic conditions | 2021 | Transportmetrica B Transport Dynam | 10.1080/21680566.2021.2007814 | 10 | **cần thư viện** | Xe máy ở đoạn nhập, IDM + lực xã hội. |
| relevant | tóm tắt | Two-dimensional LWR model for lane-free traffic | 2023 | arXiv | arXiv:2310.16904 |  | arXiv | LWR 2D. |
| relevant | tóm tắt | Second-Order Continuum Model for Disordered Traffic | 2026 | arXiv | arXiv:2608.19440 |  | arXiv | Mô hình liên tục bậc hai. |
| relevant | tóm tắt | Effect of vehicle groups on heterogeneous disordered traffic flow | 2026 | arXiv | arXiv:2602.18056 |  | arXiv | Nhóm xe ảnh hưởng tới FD. |
| relevant | tóm tắt | Modeling and benchmarking two-wheeler seepage behavior in dense mixed traffic simulations | 2026 | Computer Networks | 10.1016/j.comnet.2026.112510 | 0 | **cần thư viện** | Tham số SUMO cho xe hai bánh chen khe; minGap mặc định 2,5 m so với 0,906 m đo được. **Dùng cho Phần 3.** |
| relevant | tóm tắt | Behavior of two-wheelers at limited priority uncontrolled T-intersections | 2015 | IATSS Research | 10.1016/j.iatssr.2015.12.002 | 33 | **cần thư viện** | Xe hai bánh ở giao chữ T không đèn. |
| relevant | tóm tắt | Critical Gap of Two-Wheeler in Heterogeneous Traffic: Comparing Occupancy-time Method and Raff's Method | 2025 | Transportation research procedia | 10.1016/j.trpro.2024.12.207 | 0 | mở* | Khe tới hạn xe hai bánh. |
| relevant | tiêu đề | Simulation of Vehicles’ Gap Acceptance Decision at Unsignalized Intersections Using SUMO | 2022 | Procedia Computer Science | 10.1016/j.procs.2022.03.043 | 16 | mở* | Mô phỏng chấp nhận khe trong SUMO. |
| relevant | tóm tắt | An agent-based model for mixed traffic in Vietnam based on virtual local lanes | 2020 | International Conference on Knowle | 10.1109/kse50997.2020.9287400 | 4 | **cần thư viện** | Làn ảo cục bộ, GAMA, Việt Nam. |
| relevant | tóm tắt | Dealing with mixed and non-normative traffic. An agent-based simulation with the GAMA platform | 2023 | PLoS ONE | 10.1371/journal.pone.0281658 | 8 | mở* | GAMA, mô hình cấp thành phố xe máy + ô tô. |
| relevant | tóm tắt | Analysis of motorcycle microscopic characteristics at roundabouts under mixed traffic condition: A case study of Vietnam | 2020 | Journal of Traffic and Transportat | 10.1016/j.jtte.2020.04.005 | 19 | **cần thư viện** | Vi mô xe máy ở vòng xuyến Việt Nam. |
| relevant | tóm tắt | Microscopic Simulation Model for Motorcycle Dominated Networks: A Case Study of a VISSIM Simulation Model for a Mixed Traffic Corridor | 2023 | IOP Conference Series Materials Sc | 10.1088/1757-899x/1289/1/012045 | 5 | mở* | VISSIM, hành lang. |
| relevant | tiêu đề | On Travel Time Functions for Mixed Traffic Systems Dominated by Motorcycles | 2017 | Springer eBooks | 10.1007/978-3-319-67168-0_12 | 0 | **cần thư viện** | Hàm thời gian đi cho mạng xe máy, có thể dùng cho PMC. |
| relevant | tóm tắt | IC4SD-Traffic-HCM: A City-Scale Camera-Sensed Benchmark for Mixed Traffic Perception and Forecasting | 2026 | Zenodo (CERN European Organization | 10.5281/zenodo.22929939 | 0 | mở* | Bộ dữ liệu camera TP.HCM, 608 trạm, 86 ngày. **Có thể kiểm chứng đường lớn.** |
| background | tóm tắt | Exploring the role of configurational accessibility of alleyways on facilitating wayfinding transportation within the organic street network systems | 2024 | Transport Policy | 10.1016/j.tranpol.2024.09.001 | 22 | **cần thư viện** | Hẻm và khả năng tiếp cận (space syntax), đi bộ, không xe máy. |
| background | tóm tắt | Reclaiming Alleyways to Improve Network Connectivity: Lessons from Dubai’s Neighborhoods | 2020 | Journal of Planning Education and  | 10.1177/0739456x20931907 | 13 | **cần thư viện** | Hẻm Dubai, đi bộ. |
| background | tóm tắt | Enhancing Urban Traffic Safety: An Evaluation on Taipei's Neighborhood Traffic Environment Improvement Program | 2024 | arXiv | arXiv:2401.16752 |  | arXiv | Taipei: cải thiện an toàn trong ngõ hẻm. |
| background | tiêu đề | Saturation Flow Rate Analysis at Signalized Intersections for Mixed Traffic Conditions in Motorcycle Dependent Cities | 2016 | Transportation research procedia | 10.1016/j.trpro.2016.06.058 | 23 | mở* | Lưu lượng bão hòa ở thành phố xe máy. |

### S5. Kiến trúc MARL mở rộng được trong giao thông

| Ưu tiên | Đã đọc | Tiêu đề | Năm | Nơi đăng | DOI / arXiv | Trích dẫn | Truy cập | Vì sao liên quan |
|---|---|---|---|---|---|---|---|---|
| **core** | tiêu đề | GAT-MF: Graph Attention Mean Field for Very Large Scale Multi-Agent Reinforcement Learning | 2023 | KDD | 10.1145/3580305.3599359 | 23 | **cần thư viện** | Mean-field có trọng số attention. |
| **core** | tóm tắt | IG-RL: Inductive Graph Reinforcement Learning for Massive-Scale Traffic Signal Control | 2021 | IEEE T-ITS | 10.1109/tits.2021.3070835; arXiv:2003.05738 | 110 | arXiv | GCN, chuyển giao zero-shot, cho đèn. Mẫu kiến trúc cho G6. |
| relevant | tiêu đề | TransferLight: Zero-Shot Traffic Signal Control on any Road-Network | 2024 | arXiv | arXiv:2412.09719 |  | arXiv | GNN + domain randomization, cho đèn. |
| relevant | tiêu đề | X-Light: Cross-City Traffic Signal Control Using Transformer on Transformer as Meta Multi-Agent RL | 2024 | IJCAI | 10.24963/ijcai.2024/11 | 12 | mở* | Chuyển giao giữa thành phố, cho đèn. |
| relevant | tóm tắt | Model-Based Graph Reinforcement Learning for Inductive Traffic Signal Control | 2024 | IEEE Open Journal of Intelligent T | 10.1109/ojits.2024.3376583; arXiv:2208.00659 | 15 | arXiv | MuJAM. |
| relevant | tóm tắt | A General Scenario-Agnostic Reinforcement Learning for Traffic Signal Control | 2024 | IEEE T-ITS | 10.1109/tits.2024.3377106 | 40 | **cần thư viện** | Không phụ thuộc kịch bản, cho đèn. |
| relevant | tiêu đề | Transferable traffic signal control: Reinforcement learning with graph centric state representation | 2021 | TR-C | 10.1016/j.trc.2021.103321 | 58 | **cần thư viện** | Biểu diễn trạng thái theo đồ thị, TR-C. |
| relevant | tiêu đề | Improving the Generalizability and Robustness of Large-Scale Traffic Signal Control | 2023 | IEEE Open Journal of Intelligent T | 10.1109/ojits.2023.3331689; arXiv:2306.01925 | 20 | arXiv | Tổng quát hóa. |
| relevant | tiêu đề | Partially Observable Mean Field Multi-Agent Reinforcement Learning Based on Graph Attention | 2023 | Drones | 10.3390/drones7070476 | 29 | mở* | GAMFQ. |
| relevant | tiêu đề | Multi-Agent Game Abstraction via Graph Attention Neural Network | 2020 | AAAI | 10.1609/aaai.v34i05.6211 | 211 | mở* | Chọn hàng xóm bằng attention. |
| relevant | tiêu đề | Multi-Agent Deep Reinforcement Learning for Large-Scale Traffic Signal Control | 2019 | IEEE T-ITS | 10.1109/tits.2019.2901791 | 1049 | **cần thư viện** | Chu et al., MA2C. |
| relevant | tiêu đề | Toward A Thousand Lights: Decentralized Deep Reinforcement Learning for Large-Scale Traffic Signal Control | 2020 | Proceedings of the AAAI Conference | 10.1609/aaai.v34i04.5744 | 424 | mở* | MPLight, chia sẻ tham số. |
| relevant | tóm tắt | Efficient Ridesharing Order Dispatching with Mean Field Multi-Agent Reinforcement Learning | 2019 | International World Wide Web Confe | 10.1145/3308558.3313433; arXiv:1901.11454 | 251 | arXiv | Mean-field cho điều phối xe. |
| relevant | tiêu đề | Efficient Large-Scale Fleet Management via Multi-Agent Deep Reinforcement Learning | 2018 | ACM SIGKDD Conference on Knowledge | 10.1145/3219819.3219993 | 409 | **cần thư viện** | MARL đội xe lớn. |
| relevant | tiêu đề | Beyond centralization: Non-cooperative perimeter control with extended mean-field reinforcement learning in urban road networks | 2024 | TR-B | 10.1016/j.trb.2024.103016 | 14 | **cần thư viện** | Mean-field mở rộng, TR-B. |
| relevant | tiêu đề | Safe and Scalable Ride-Sourcing Vehicle Rebalancing: A Constrained Mean-Field Reinforcement Learning Approach | 2025 | Repository for Publications and Re | 10.3929/ethz-c-000785609; arXiv:2503.24183 | 0 | arXiv | Constrained mean-field, có bảo đảm dịch vụ. Mẫu cho MARL có ràng buộc. |
| relevant | tiêu đề | Reward design for driver repositioning using multi-agent reinforcement learning | 2020 | TR-C | 10.1016/j.trc.2020.102738; arXiv:2002.06723 | 73 | arXiv | Thiết kế reward MARL, TR-C. |
| relevant | tiêu đề | Dynamic traffic signal control using mean field multi‐agent reinforcement learning in large scale road‐networks | 2023 | IET Intelligent Transport Systems | 10.1049/itr2.12364 | 17 | **cần thư viện** | Mean-field cho đèn. |
| background | tóm tắt | Mean-Field Controls with Q-Learning for Cooperative MARL: Convergence and Complexity Analysis | 2021 | SIAM Journal on Mathematics of Dat | 10.1137/20m1360700; arXiv:2002.04131 | 39 | arXiv | Cận sai số O(1/√N). |
| background | tóm tắt | Learning in Mean Field Games: A Survey | 2022 | arXiv | arXiv:2205.12944 | 13 | arXiv | Khảo sát. |
| background | tiêu đề | The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games | 2022 | NeurIPS | 10.52202/068431-1787 | 642 | **cần thư viện** | MAPPO. |

### S6. Ước lượng trạng thái từ probe thưa, có bất định

| Ưu tiên | Đã đọc | Tiêu đề | Năm | Nơi đăng | DOI / arXiv | Trích dẫn | Truy cập | Vì sao liên quan |
|---|---|---|---|---|---|---|---|---|
| **core** | tóm tắt | AGNP: Network-wide short-term probabilistic traffic speed prediction and imputation | 2023 | Commun. Transp. Res. | 10.1016/j.commtr.2023.100099 | 59 | mở* | Neural process: dự báo và nội suy tốc độ xác suất toàn mạng. |
| **core** | tóm tắt | Uncertainty-aware Traffic Prediction under Missing Data | 2023 | Proceedings | 10.1109/icdm58522.2023.00152; arXiv:2309.06800 | 14 | arXiv | Dự báo có bất định ở nơi chưa từng có dữ liệu. **Làm yếu câu "chưa ai kết hợp" trong RESEARCH_V4 §2.7.** |
| relevant | tóm tắt | Network-wide Freeway Traffic Estimation Using Sparse Sensor Data: A Dirichlet Graph Auto-Encoder Approach | 2025 | arXiv | arXiv:2503.15845 |  | arXiv | DGAE, cao tốc. |
| relevant | tiêu đề | Kriformer: A Novel Spatiotemporal Kriging Approach Based on Graph Transformers | 2024 | arXiv | arXiv:2409.14906 |  | arXiv | Graph transformer cho kriging. |
| relevant | tóm tắt | Inductive Graph Neural Networks for Spatiotemporal Kriging | 2021 | Proceedings of the AAAI Conference | 10.1609/aaai.v35i5.16575 | 186 | mở* | IGNNK. |
| relevant | tóm tắt | Kriging Convolutional Networks | 2020 | Proceedings of the AAAI Conference | 10.1609/aaai.v34i04.5716 | 82 | mở* | KCN. |
| relevant | tóm tắt | Spatial Aggregation and Temporal Convolution Networks for Real-time Kriging | 2021 | arXiv | arXiv:2109.12144 |  | arXiv | SATCN. |
| relevant | tóm tắt | Uncertainty Quantification for Traffic Forecasting: A Unified Approach | 2023 | IEEE International Conference on D | 10.1109/icde55515.2023.00081 | 34 | **cần thư viện** | DeepSTUQ. |
| relevant | tiêu đề | Uncertainty Quantification for Traffic Forecasting Using Deep-Ensemble-Based Spatiotemporal Graph Neural Networks | 2024 | IEEE T-ITS | 10.1109/tits.2024.3381099 | 39 | **cần thư viện** | Deep ensemble + GNN. |
| relevant | tóm tắt | Traffic state estimation from vehicle trajectories with anisotropic Gaussian processes | 2024 | TR-C | 10.1016/j.trc.2024.104646; arXiv:2303.02311 | 37 | arXiv | GP dị hướng từ quỹ đạo. |
| relevant | tóm tắt | Physics-Embedded Gaussian Process for Traffic State Estimation | 2025 | arXiv | arXiv:2512.04004 |  | arXiv | GP nhúng vật lý, probe thưa. |
| relevant | tóm tắt | Quantifying Uncertainty In Traffic State Estimation Using Generative Adversarial Networks | 2022 | arXiv | arXiv:2206.09349 |  | arXiv | GAN + PIDL. |
| relevant | tóm tắt | Traffic State Estimation and Uncertainty Quantification at Signalized Intersections with Low Penetration Rate Vehicle Trajectory Data | 2024 | arXiv | arXiv:2404.08667 |  | arXiv | Tỉ lệ probe thấp, nút có đèn. |
| relevant | tóm tắt | Spatial-Temporal Attention Model for Traffic State Estimation with Sparse Internet of Vehicles | 2024 | arXiv | arXiv:2407.08047 | 0 | arXiv | TSE với IoV thưa. |
| relevant | tóm tắt | Network-wide traffic state estimation using a mixture Gaussian graphical model and graphical lasso | 2017 | TR-C | 10.1016/j.trc.2017.12.007 | 36 | **cần thư viện** | Ước lượng link chưa quan sát từ probe, gần cách làm của ta. |
| relevant | tóm tắt | Sparse Bayesian Learning Assisted Approaches for Road Network Traffic State Estimation | 2020 | IEEE T-ITS | 10.1109/tits.2020.2971031 | 26 | **cần thư viện** | Bayes thưa, mạng đường. |
| relevant | tiêu đề | Bayesian Kernelized Matrix Factorization for Spatiotemporal Traffic Data Imputation and Kriging | 2022 | IEEE T-ITS | 10.1109/tits.2022.3161792 | 64 | **cần thư viện** | Nội suy Bayes có bất định. |
| relevant | tiêu đề | Correlating sparse sensing for large-scale traffic speed estimation: A Laplacian-enhanced low-rank tensor kriging approach | 2022 | arXiv | arXiv:2210.11780 |  | arXiv | Tensor Laplacian. |
| relevant | tiêu đề | Network macroscopic fundamental diagram-informed graph learning for traffic state imputation | 2024 | TR-B | 10.1016/j.trb.2024.102996 | 42 | **cần thư viện** | Nội suy theo MFD, TR-B. |
| relevant | tiêu đề | A dual branch graph neural network based spatial interpolation method for traffic data inference in unobserved locations | 2024 | Information Fusion | 10.1016/j.inffus.2024.102703 | 12 | **cần thư viện** | Nội suy nơi không có cảm biến. |
| relevant | tiêu đề | Travel Time and Weather-Aware Traffic Forecasting in a Conformal Graph Neural Network Framework | 2025 | IEEE T-ITS | 10.1109/tits.2025.3611267; arXiv:2509.12043 | 4 | arXiv | Conformal GNN. |
| relevant | tóm tắt | Citywide Traffic Volume Estimations with Uncertainty: A Network Geostatistical Boosting Approach | 2026 | ERA: Education and Research Archiv | 10.7939/84079 | 0 | mở* | Geostatistics, lưu lượng. |
| background | tóm tắt | Traffic state estimation of urban road networks by multi-source data fusion: Review and new insights | 2022 | Physica A Statistical Mechanics an | 10.1016/j.physa.2022.127079 | 111 | **cần thư viện** | Tổng quan đô thị. |
| background | tiêu đề | Traffic state estimation on highway: A comprehensive survey | 2017 | Annual Reviews in Control | 10.1016/j.arcontrol.2017.03.005 | 404 | **cần thư viện** | Tổng quan cao tốc. |
| background | tóm tắt | Physics-Informed Deep Learning for Traffic State Estimation: A Survey and the Outlook | 2023 | Algorithms | 10.3390/a16060305 | 67 | mở* | Tổng quan PIDL. |
