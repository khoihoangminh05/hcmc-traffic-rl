# Giao thức tổng quan có hệ thống (Phần 2, giai đoạn 1)

Bản 2026-11-02, chờ người dùng duyệt. Đây là tổng quan theo tinh thần PRISMA, không phải một systematic review đầy đủ: một người sàng lọc và các cơ sở dữ liệu trả phí chưa được chạy. Phải ghi rõ hai giới hạn này nếu đưa quy trình vào bài.

Luận điểm làm việc: nhà cung cấp dẫn đường điều phối một tỉ lệ p người lái bằng khuyến nghị next-hop để giảm tổng thời gian đi của toàn hệ thống, trên mạng nhiều hẻm và xe máy chiếm đa số (Quận 4, TP.HCM), bằng MARL phi tập trung train trong SUMO, với chia công theo chi phí biên không cần chạy lại mô phỏng. Sức chịu môi trường của hẻm chỉ là ràng buộc chính sách tùy chọn.

## 1. Câu hỏi tổng quan

- **RQ1.** MARL và deep RL đã được dùng thế nào cho dẫn đường động: bài toán, quy mô mạng, simulator, baseline, và có thắng được hành vi người lái hay cân bằng không?
- **RQ2.** Những cách nào đưa định tuyến về gần tối ưu hệ thống (chi phí biên, difference rewards, thu phí), và chúng tốn bao nhiêu tính toán?
- **RQ3.** Khi chỉ điều khiển được một phần xe, có tuân thủ không đầy đủ, lợi ích thay đổi theo p ra sao, trong lý thuyết và trong thực nghiệm?
- **RQ4.** App dẫn đường tác động gì lên đường nhỏ và khu dân cư, và đã có bộ định tuyến nào xử lý tác động đó ngay trong thuật toán chưa?
- **RQ5.** Đã có mô hình nào cho giao thông xe máy, không làn trên mạng đường, đặc biệt mạng hẻm, và đã có tối ưu định tuyến nào trên đó chưa?
- **RQ6.** Kiến trúc MARL nào mở rộng và chuyển giao được trong giao thông?
- **RQ7.** Trạng thái mạng được ước lượng từ probe thưa, kèm bất định, như thế nào, và có đi vào quyết định định tuyến không?

## 2. Nguồn

| Nguồn | Ai chạy | Trạng thái 02/11 |
|---|---|---|
| OpenAlex API | Agent | Đã chạy, nguồn chính thay cho Semantic Scholar |
| arXiv API | Agent | Đã chạy |
| Crossref API | Agent | Chỉ dùng xác minh thư mục, không dùng đếm kết quả |
| Tìm kiếm web (tương đương phần lộ ra của Google) | Agent | Đã chạy, 20 lượt, dùng cho tài liệu xám và kiểm phản bác |
| Semantic Scholar Graph API | Agent | **Không dùng được**: mọi lần gọi trả HTTP 429. Chạy lại khi có API key |
| Google Scholar | **Người dùng chạy** | Chưa. Không có API; chỉ tìm tay |
| TRID | **Người dùng chạy** | Chưa |
| Scopus, Web of Science | **Người dùng chạy (quyền truy cập trường)** | Chưa |
| IEEE Xplore, ScienceDirect | **Người dùng chạy (quyền truy cập trường)** | Chưa, dùng thêm để lấy toàn văn |

OpenAlex nhắc rằng lấy API key sẽ cần email của người dùng. Agent không tự làm việc đó; nếu muốn tăng hạn mức thì người dùng tự đăng ký.

## 3. Chuỗi tìm kiếm

Năm: 2015–2026. Lý thuyết kinh điển được miễn giới hạn năm (Beckmann, Pigou, Roughgarden, Swamy, Larsson–Patriksson, Appleyard, Buchanan, Qian, Fosgerau–Small, Nair, Wolpert–Tumer).

Cú pháp chung, dán được vào OpenAlex và IEEE Xplore. Với Scopus, bọc trong `TITLE-ABS-KEY( ... ) AND PUBYEAR > 2014`. Với Web of Science, dùng `TS=( ... )` và lọc năm 2015–2026. Với Google Scholar, bỏ ngoặc và lấy 200 kết quả đầu mỗi chuỗi.

**S1. MARL / deep RL cho dẫn đường và định tuyến động**
```
"reinforcement learning" AND ("route guidance" OR "route choice" OR "traffic assignment" OR rerouting OR "route recommendation" OR "routing game")
("multi-agent" OR multiagent OR MARL) AND "reinforcement learning" AND (routing OR "route choice") AND (traffic OR vehicles OR congestion)
"reinforcement learning" AND (routing OR rerouting OR "route guidance") AND (uncertainty OR "partial observability" OR "partially observable" OR "missing data") AND (traffic OR congestion OR vehicles)
```

**S2. Tối ưu hệ thống, chi phí biên, chia công, Stackelberg, tuân thủ, thiết kế thông tin**
```
"system optimal" AND ("route guidance" OR routing OR "traffic assignment") AND ("reinforcement learning" OR learning)
"path marginal cost" OR "marginal travel time" OR "link marginal cost" OR ("marginal cost" AND "dynamic traffic assignment")
("difference rewards" OR "marginal contribution" OR Shapley OR "credit assignment") AND (traffic OR congestion) AND (routing OR "route choice" OR rerouting)
("marginal external" OR "congestion externality") AND ("agent-based" OR queue OR queueing OR spillback)
("partial control" OR "fraction of" OR Stackelberg OR "coordinated fleet" OR "mixed autonomy") AND ("system optimal" OR "system optimum" OR "price of anarchy") AND (routing OR assignment)
(penetration OR "market share" OR compliance) AND ("route guidance" OR "dynamic rerouting" OR "vehicle rerouting") AND (simulation OR SUMO)
("Bayesian persuasion" OR "information design") AND (traffic OR routing OR navigation)
("side constraint" OR "side constraints" OR "link capacity constraint" OR "capacity constraints") AND ("traffic assignment" OR "traffic equilibrium" OR "traffic equilibria")
```

**S3. Tác động của app, đi tắt, ngoại ứng lên đường dân cư**
```
("navigation app" OR "navigation apps" OR "routing app" OR "routing apps" OR Waze) AND (traffic OR congestion OR neighborhood OR residential)
("cut-through" OR "rat-running" OR "rat running") AND (traffic OR residential OR neighborhood)
("low traffic neighbourhood" OR "low traffic neighborhoods" OR "traffic calming" OR "through traffic") AND (displacement OR routing OR "traffic volume" OR residents)
("environmental capacity" OR "liveable streets" OR "livable streets") AND (traffic OR street OR road)
```
Lưu ý: `"cut-through"` kéo về rất nhiều bài chuyển mạch mạng máy tính; phải loại ở bước sàng tiêu đề.

**S4. Xe máy, không làn, hẻm Việt Nam và Đông Nam Á, chấp nhận khe**
```
(motorcycle OR motorbike) AND (dominated OR dominant OR dependent) AND traffic AND (simulation OR model OR flow)
("Ho Chi Minh" OR Hanoi OR Vietnam) AND (motorcycle OR motorbike) AND (simulation OR "traffic flow" OR microscopic OR SUMO OR VISSIM)
("lane-free" OR "non-lane-based" OR "disordered traffic" OR "porous flow" OR "heterogeneous traffic") AND (flow OR simulation OR "fundamental diagram")
"gap acceptance" AND (motorcycle OR motorbike OR "two-wheeler" OR "two wheeler")
(motorcycle OR motorbike OR "two-wheeler" OR "powered two") AND ("traffic assignment" OR "route choice" OR routing OR "route guidance" OR navigation)
(alley OR alleys OR alleyway OR alleyways OR hutong OR "narrow road" OR "narrow streets" OR soi) AND (traffic OR "route choice" OR routing OR navigation) AND (motorcycle OR motorbike OR vehicle)
```
Tiếng Việt, tìm trên Google Scholar và kho luận văn (BK TP.HCM, ĐH GTVT): `"mạng lưới đường hẻm"`, `hẻm xe máy mô phỏng`, `ngõ hẻm giao thông phân bổ`, `mô hình hành vi xe máy SUMO`.

**S5. Kiến trúc MARL mở rộng được trong giao thông**
```
("mean field" OR "mean-field") AND "reinforcement learning" AND (traffic OR routing OR transportation OR vehicles)
("graph attention" OR "graph neural network" OR attention) AND "multi-agent reinforcement learning" AND (traffic OR routing OR vehicles)
(transferable OR "zero-shot" OR generalization OR inductive) AND "reinforcement learning" AND ("traffic signal" OR routing OR "road network")
("zero-shot" OR transferable OR "unseen network" OR "unseen networks" OR "cross-city") AND ("multi-agent" OR multiagent) AND (routing OR "route guidance" OR "route choice")
```

**S6. Ước lượng trạng thái mạng từ probe thưa, có bất định**
```
("traffic state estimation" OR "speed estimation") AND (network OR urban) AND (probe OR "floating car" OR sparse)
(kriging OR "unobserved locations" OR "unobserved roads" OR "unobserved links") AND traffic AND (uncertainty OR probabilistic OR Bayesian OR "Gaussian process")
(probe OR "floating car" OR GPS) AND ("traffic state estimation" OR "speed estimation" OR "travel time estimation") AND ("Gaussian process" OR Bayesian OR uncertainty) AND (network OR urban)
("uncertainty quantification" OR probabilistic OR conformal) AND ("traffic state" OR "traffic speed" OR "traffic forecasting") AND graph
```

## 4. Tiêu chí nhận và loại

**Nhận**
- Tiếng Anh hoặc tiếng Việt; bài tạp chí, hội nghị có phản biện, preprint arXiv, luận án; báo cáo chính thức của thành phố cho S3.
- S1, S2: xe trên mạng đường, có quyết định định tuyến hoặc gán luồng. Đèn tín hiệu chỉ nhận nếu đồng tối ưu với tuyến.
- S3: đo hoặc mô phỏng tác động lên đường nhỏ, khu dân cư, hoặc tác động mạng của app.
- S4: dòng xe máy, xe hai bánh, không làn, chấp nhận khe; mạng ngõ hẻm dưới góc giao thông.
- S5: kiến trúc MARL có đánh giá trên bài toán giao thông, hoặc nền tảng có ảnh hưởng rõ (mean-field, MAPPO).
- S6: suy ra tốc độ hoặc thời gian đi ở nơi không đo được, hoặc có lượng hóa bất định.

**Loại**
- Định tuyến mạng máy tính (SDN, WSN, vệ tinh, packet), UAV, robot, tàu biển, hàng không, chip.
- VRP giao hàng và neural combinatorial optimization khi không có tương tác tắc nghẽn.
- Chỉ dự báo mà không có suy luận cho nơi không quan sát và không có bất định.
- Bài chỉ về xe điện, phát thải, y tế xe máy, nhận dạng ảnh.
- Tài liệu không có đủ thông tin thư mục; bài bị rút; nhà xuất bản đáng ngờ chỉ giữ lại nếu là bằng chứng phản bác, và phải ghi rõ.

## 5. Các bước sàng lọc

1. **Gộp trùng** theo tiêu đề chuẩn hóa, rồi theo DOI.
2. **Tiêu đề**: lọc từ khóa để bỏ nhiễu rõ, rồi đọc danh sách tiêu đề còn lại.
3. **Tóm tắt**: đọc tóm tắt của bài còn lại. Bài không có tóm tắt trong nguồn mở được ghi "tiêu đề" và **chưa được coi là đã sàng ở bước này**.
4. **Toàn văn**: 30–40 bài core, trích vào bảng ở mục 6.
5. **Lần trích dẫn** ngược và xuôi từ 5–10 bài lõi. Đã làm lần xuôi trên 8 bài (xem `candidates.md`); lần ngược chưa làm.

Mọi khẳng định "chưa có ai làm" phải qua `gap_checks.md`.

## 6. Bảng trích xuất (làm ở giai đoạn đọc toàn văn)

| Trường | Nội dung |
|---|---|
| id | DOI hoặc arXiv |
| stream, RQ | S1–S6; RQ1–RQ7 |
| problem | Chọn tuyến trước chuyến / en-route / next-hop / gán luồng tĩnh / DTA |
| objective | UE / SO / tự xe / đa mục tiêu; có ràng buộc gì |
| network | Tên, số nút, số cạnh, thật hay tổng hợp, có đường hẹp hoặc hẻm không |
| fleet | Số xe, số agent, thành phần xe, có xe máy không |
| simulator | SUMO, VISSIM, AIMSUN, MATSim, giải tích, tự viết |
| observation | Cục bộ / toàn cục; có dùng thông tin không đo được không |
| action | Tuyến, next-hop, tỉ lệ chia; agent là xe, nút hay cặp OD |
| reward, credit | Ích kỷ / toàn cục / chi phí biên; cách tính; chi phí tính toán |
| p, compliance | Tỉ lệ tham gia đã thử; mô hình tuân thủ |
| baselines | Có người lái, UE, SO, app, chi phí biên không học không |
| metrics | TTT, trễ xe nền, công bằng, lưu lượng đi tắt |
| results | Con số chính, seed, kiểm định |
| transfer | Có thử trên mạng khác không, kết quả |
| limits | Giới hạn do tác giả nêu và do ta nhận định |
| threat | Ảnh hưởng tới G nào |
| read_status | toàn văn / tóm tắt / tiêu đề, ngày đọc |

## 7. Mẫu đếm kiểu PRISMA

| Bước | S1 | S2 | S3 | S4 | S5 | S6 | Tổng |
|---|---|---|---|---|---|---|---|
| Kết quả tiêu đề + tóm tắt, OpenAlex (cộng thô, có trùng) | 1267 | 565 | 1247 | 2193 | 601 | 116 | 5989 |
| Kết quả arXiv (cộng thô) | 54 | 60 | 33 | 49 | 108 | 67 | 371 |
| Scopus / WoS / Scholar / TRID | chờ | chờ | chờ | chờ | chờ | chờ | chờ |
| Bản ghi thực sự tải về, sau gộp trùng toàn bộ | | | | | | | 3375 |
| Loại ở bước tiêu đề, tóm tắt | | | | | | | 3205 |
| Còn lại (ứng viên) | 29 | 43 | 23 | 29 | 21 | 25 | 170 |
| Core, đọc toàn văn | 9 | 13 | 5 | 4 | 2 | 2 | 35 |
| Đọc toàn văn xong | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Đưa vào bài | | | | | | | chờ |

Số "tải về" nhỏ hơn số "kết quả" vì mỗi truy vấn chỉ lấy tối đa 50 hoặc 100 bản ghi đầu. **Vì vậy bước này chưa phủ hết kết quả** của S3 và S4 (T6: 1512, T10: 404, T12: 594). Bước của người dùng trên Scopus phải bù phần này trước khi đưa số vào bài.
