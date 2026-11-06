# Nghiên cứu nền cho V4: tối ưu giao thông có mạng hẻm

Bản 2026-11-02. Đây là bước 1–4 của quy trình: khảo sát → khoảng trống → hiểu bài toán (ràng buộc vật lý, biết / chưa biết) → hướng giải quyết và lập luận khả thi. Kiến trúc chi tiết và code chỉ làm **sau khi** chốt tài liệu này.

Chú thích độ tin cậy: [đọc] = đã xem tóm tắt hoặc nội dung chính; [snippet] = mới thấy qua trích đoạn, phải đọc toàn văn trước khi trích trong bài.

---

## 1. Câu hỏi nghiên cứu

> Trong một mạng đô thị mà phần lớn đường là hẻm hẹp (xe máy, không làn, không đèn, nhập ra đường lớn bằng chen khe), **một nhà cung cấp dẫn đường (vai trò như Google Maps)**, chỉ biết những gì đo được, nên chỉ đường cho một phần người lái như thế nào để giảm tổng thời gian đi của **toàn hệ thống**?

(Cập nhật 2026-11-02, theo người dùng: hẻm là **tài nguyên để phân luồng**, không phải thứ cần né. Ràng buộc sức chịu của hẻm chỉ là **núm chính sách tùy chọn**, mặc định tắt, dùng để vẽ đường cong đánh đổi trong phần thảo luận. Chỗ khác biệt của bài: mạng hẻm xe máy, mục tiêu toàn hệ thống với tỉ lệ người dùng p < 1, và chỉ dùng thông tin đo được.)

## 2. Khảo sát theo từng mạch

### 2.1 Định tuyến bằng MARL
- **URB** (NeurIPS 2025, 29 mạng thật, 4 thuật toán MARL): MARL hiện đại, dù train lâu và tốn, **hiếm khi thắng được người lái**; học độc lập không mở rộng được và cho kết quả kém hơn người. [đọc tóm tắt] ([arXiv 2505.17734](https://arxiv.org/abs/2505.17734v1), [slide NeurIPS](https://neurips.cc/media/neurips-2025/Slides/121647.pdf))
- **RouteRL** (SoftwareX 2025): khung MARL cho chọn tuyến của xe tự hành, chung đường với người lái. Bài toán ở mức chọn tuyến (route choice), không phải next-hop. [snippet] ([arXiv 2502.20065](https://arxiv.org/pdf/2502.20065))
- **MARL-OD-DA** (Comm. Transp. Res. 2025): agent là cặp OD thay vì từng xe, giảm số agent hai bậc; mục tiêu là cân bằng gán luồng (DTA). [snippet] ([arXiv 2506.17029](https://arxiv.org/abs/2506.17029v1))
- Không tìm thấy survey riêng cho MARL route guidance. Survey gần nhất là về ra quyết định hợp tác đa agent nói chung. ([arXiv 2503.13415](https://arxiv.org/pdf/2503.13415))

### 2.2 Ích kỷ, hệ thống tối ưu và chia công
- Định tuyến ích kỷ của MARL chịu đúng **price of anarchy** mà lý thuyết dự đoán: nhiều bộ định tuyến đồng thời dẫn tới cân bằng kém hiệu quả. ([luận án Warwick 2021](https://wrap.warwick.ac.uk/165597/), [arXiv 2104.00357](https://arxiv.org/pdf/2104.00357)) [snippet]
- Thu phí chi phí biên + Q-learning (GTQ, AAMAS 2020) giảm tắc trên mạng thật; ALA 2018 có kết quả hội tụ tới cân bằng hiệu quả hệ thống. ([AAMAS 2020](https://aamas.csc.liv.ac.uk/Proceedings/aamas2020/pdfs/p1098.pdf), [ALA 2018](https://ala2018.cs.universityofgalway.ie/papers/ALA_2018_paper_42.pdf)) [snippet]
- **Gần nhất với hướng của ta**: Psarou và cộng sự (AAMAS 2026 DC): thêm **chi phí biên** vào reward của xe tự hành giúp hội tụ về System Optimal nhanh hơn. Nhưng chi phí biên được tính bằng **chạy lại mô phỏng, mỗi lần bỏ đi một xe**: hệ 10 xe cần thêm 1024 × 10 lần chạy. Bản sau chỉ tính cho các xe ảnh hưởng nhất. [đọc tóm tắt] ([arXiv 2510.11410](https://arxiv.org/abs/2510.11410v1))
- **Chi phí ngoại ứng theo agent không cần chạy lại**: Kaddoura & Kickhöfer (MATSim) quy trễ của từng xe về đúng xe gây ra nó, dựa trên thứ tự trong hàng đợi, và dùng làm phí. Fosgerau & Small: ngoại ứng gồm hai phần, theo quan hệ tốc độ–lưu lượng của chính cạnh và theo tràn ngược, kéo dài hơn 5 phút. ([Kaddoura 2014](https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2014/14-01/KaddouraKickhoefer2014CongestionPricing.pdf), [Fosgerau & Small](https://sites.socsci.uci.edu/~ksmall/Fosgerau-Small%20paper.pdf)) [snippet]

### 2.3 Tỉ lệ xe tham gia, tuân thủ, thông tin
- **Stackelberg routing**: hệ thống điều khiển một phần luồng, phần còn lại ích kỷ. Bài toán một lần là NP-khó ngay cả trên mạng song song tuyến tính; có cận PoA theo tỉ lệ luồng điều khiển. ([Swamy](https://math.uwaterloo.ca/~cswamy/papers/stackelberg-journ.pdf), [Berkeley](https://bayen.berkeley.edu/sites/default/files/on_social_optimal_routing_under_selfish_learning.pdf)) [snippet]
- Khuyến nghị thời gian thực có thể **có hại** khi tỉ lệ dùng app và mức tuân thủ cao. ([arXiv 2303.17923](https://arxiv.org/html/2303.17923v3)) [snippet]
- Không tuân thủ: TR-C 2024 (Yun và cộng sự) dùng NFSP. Hướng dẫn SO vẫn giữ phần lớn hiệu quả khi có không tuân thủ; định tuyến ích kỷ gây chênh lệch giữa người dùng. ([TR-C 165, 104721](https://aurora.ajou.ac.kr/handle/2018.oak/34303)) Tuân thủ xác suất: TASR. ([arXiv 2403.19831](https://arxiv.org/html/2403.19831v1))
- Thiết kế thông tin (Bayesian persuasion): khuyến nghị riêng phải thỏa ràng buộc **obedience** (người lái không có lợi khi làm trái). ([arXiv 2309.06859](https://arxiv.org/abs/2309.06859)) [snippet]

### 2.4 Ngoại ứng lên đường dân cư (đi tắt, "rat-run")
- Berkeley (Bayen, Cabannes): định tuyến ích kỷ của app tăng **khoảng 300% VMT trên đường sức chứa thấp** ở Los Angeles khi tỉ lệ người dùng app cao. Thông lượng toàn thành phố tăng, nhưng dân khu bị đi tắt chịu trễ, mất an toàn, và thành phố tốn chi phí chống lại. ([Cabannes](https://bayen.berkeley.edu/sites/default/files/cabannes.pdf)) [snippet]
- Thành phố phản ứng bằng biện pháp vật lý (Fremont, Bellevue, Leonia), tức là **ràng buộc được đặt từ bên ngoài, sau khi sự đã rồi**. ([Alexandria report](https://media.alexandriava.gov/docs-archives/tes/info/city-of-alexandria-cut-through-research---report-5.7.2020%3Dfinal.pdf))
- **Sức chịu môi trường** của đường dân cư (Buchanan, Appleyard): khoảng 2000–3000 xe/ngày; Christchurch khoảng 1500–2000. Tiếng ồn, căng thẳng, an toàn và tương tác xã hội tỉ lệ nghịch với lưu lượng. ([TRID](https://trid.trb.org/View/384136), [ViaStrada](https://viastrada.nz/node/2127)) [snippet]

### 2.5 Hẻm và giao thông xe máy ở TP.HCM
- Hẻm chứa khoảng **85% dân số** và khoảng **85% mạng đường** của TP.HCM; là không gian công cộng lớn nhất (buôn bán, sinh hoạt). Hẻm không có điều khiển giao thông, tắc giờ cao điểm, chèn không gian người đi bộ. ([Gibert-Flutre](https://www.researchgate.net/publication/322818097_Rethinking_metropolitan_production_from_its_underside_A_view_from_the_alleyways_of_Ho_Chi_Minh_City), [Wikipedia: Hẻm](https://en.wikipedia.org/wiki/H%E1%BA%BBm)) [snippet; số 85% cần nguồn gốc]
- Mô phỏng xe máy: VISSIM dùng được nếu có bộ tham số riêng cho xe máy (HCMC, Hà Nội); có mô hình agent cho làn hỗn loạn và đi theo bầy. Chưa thấy công trình nào mô hình tường minh mạng hẻm cho định tuyến tối ưu (xem G1 ở mục 3). ([VISSIM HCMC](https://www.researchgate.net/publication/353345030_Application_of_VISSIM_microsimulation_model_for_the_motorcycle_traffic_in_Ho_Chi_Minh_City), [Hanoi corridor](https://www.researchgate.net/publication/373409699_Microscopic_Simulation_Model_for_Motorcycle_Dominated_Networks_A_Case_Study_of_a_VISSIM_Simulation_Model_for_a_Mixed_Traffic_Corridor))
- Vật lý dòng xe không làn: **porous flow** (Nair, Mahmassani; TR-B 2011): xe đi qua "lỗ rỗng" giữa các xe khác, có giản đồ cơ bản theo lớp xe. Giản đồ cơ bản 2D thực nghiệm cho dòng hỗn loạn **vẫn chưa được khám phá nhiều** (2026). ([TRID 1130198](https://trid.trb.org/View/1130198), [arXiv 2608.00602](https://arxiv.org/pdf/2608.00602))
- Chen khe ở giao không đèn: xe máy chấp nhận khe nhỏ hơn ô tô (khoảng 2.46 s so với 3.21 s ở vòng xuyến); ở nước đang phát triển, quyền ưu tiên ít được tôn trọng. ([CEE 2026](https://reference-global.com/2/v2/download/article/10.2478/cee-2026-0002.pdf), [Sri Lanka](https://jsalt.sljol.info/articles/85)) [snippet]

### 2.6 Attention và mở rộng quy mô trong MARL
- **GAT-MF** (KDD 2023): đổi tương tác từng cặp thành tương tác với một mean-field có trọng số attention, cho hệ rất nhiều agent. ([Tsinghua PDF](https://fi.ee.tsinghua.edu.cn/public/publications/e589ec80-643d-11ee-84fe-0242ac120002.pdf))
- **GAMFQ**: attention chọn hàng xóm có ảnh hưởng, rồi mean-field trên tập đó. ([arXiv 2304.12653](https://arxiv.org/abs/2304.12653v3))
- **Đồ thị truyền tin thưa thích nghi**: mỗi agent chỉ chú ý tới vài agent quan trọng nhất, gần như không mất tối ưu. ([arXiv 2003.01040](https://arxiv.org/abs/2003.01040v1))
- Chuyển giao zero-shot sang mạng mới (điều khiển đèn): IG-RL (GCN, Manhattan 3971 đèn), TransferLight, X-Light (transformer). Với định tuyến: xem MA-GRL ở mục 3. ([IG-RL](https://arxiv.org/pdf/2003.05738v5), [TransferLight](https://arxiv.org/html/2412.09719v2), [X-Light](https://ijcai.org/proceedings/2024/0011.pdf))

### 2.7 Ước lượng trạng thái với dữ liệu thưa
- Kriging bằng GNN và graph transformer cho cạnh không có cảm biến (RADGCN 2026, Kriformer, DGAE). Bất định thì có TA-ANP (neural process + MC dropout). (Câu "chưa ai kết hợp" trước đây bị AGNP và 2309.06800 làm yếu, cần đọc toàn văn.) ([Kriformer](https://www.arxiv.org/pdf/2409.14906), [tensor kriging](https://arxiv.org/pdf/2210.11780v1)) [snippet]
- Dữ liệu của ta (đo 2026-11-01): live của Mapbox ở Q4 **trùng hồ sơ lịch sử** (live/typical p10–p90 = 1.00). Có số đo trên 1098/1828 cạnh (hẻm 880/1460).

## 3. Khoảng trống nghiên cứu (có dẫn chứng)

> **Bản sửa 2026-11-02 sau kiểm phản bác** (`lit/gap_checks.md`; chưa đọc toàn văn, chưa chạy Scopus / WoS). Bảng này thay cho bản đầu, vốn nói quá ở G1, G3, G4, G6.

| # | Khoảng trống còn lại (phát biểu hẹp) | Cái đã có, làm yếu bản cũ | Độ chắc |
|---|---|---|---|
| G1 | Chưa thấy định tuyến SO hoặc RL trên mạng **hẻm được mô hình tường minh** | AIMSUN mạng lớn cho xe máy ở Ninh Kiều (có chọn tuyến, tuân thủ); dẫn đường xe máy ở Jakarta dùng hẻm nhỏ nhưng không học, không mục tiêu hệ thống | Vừa; chưa tìm nguồn tiếng Việt |
| G2 (phụ) | SO có thể đẩy thêm tải vào đường dân cư; cần **đo**, kể cả khi ràng buộc tắt | Kuncheria 2023: SO làm xấu tải đường dân cư ở Bay Area. Graf & Harks 2024: khung side-constraint tổng quát, nên không nói "đầu tiên" | Vừa, bằng chứng mỏng |
| G3 | Chia công **đo được theo từng xe trong SUMO** (quy theo hàng đợi) cho MARL next-hop phi tập trung, **kiểm chứng với chi phí biên phản thực** | Xấp xỉ path marginal cost không chạy lại đã có lâu trong DTA (Qian 2012, TR-C 2018, TR-B 2020); Wang 2505.20889 reward giải tích (một agent trung tâm, tĩnh, 13 nút); Kaddoura quy trễ theo agent (dùng làm phí, không phải MARL); Psarou 2610.13439 là đối thủ đang chạy | Vừa, phải theo dõi đối thủ |
| G4 | Đường cong lợi ích theo p cho policy next-hop trên **mạng dày hẻm với nền xe máy** | Google thử thật ở 10 thành phố Mỹ (Nature Cities 2026, dưới 2% chuyến); Yun 2024; Psarou 2026; SO-DTA partial control | Vừa |
| G5 | Ra quyết định khi phần lớn trạng thái hẻm không quan sát được | AGNP và 2309.06800 đã kết hợp kriging với bất định, nên "chưa ai" ở §2.7 phải kiểm lại; RA-RouteNet mới thấy tiêu đề | Vừa |
| ~~G6~~ | **Không còn là khoảng trống như đã viết.** MA-GRL (Sci. Rep. 2026): MAPPO + GAT theo từng xe, 100 xe, báo cáo 87% giữ hiệu quả zero-shot giữa ba thành phố. Bài A\* phải có góc khác: mạng khác hẳn cấu trúc, đội xe lớn hơn nhiều, p < 1 | MA-GRL mới đọc tóm tắt, chưa đánh giá chất lượng | — |

Hệ quả: đóng góp không nên dựa vào câu "chưa ai dùng chi phí biên trong MARL". Điểm mới là **tổ hợp**: mạng hẻm xe máy + nhà cung cấp dẫn đường p < 1 + chia công đo được theo từng xe, kiểm chứng phản thực, ở quy mô hàng nghìn xe.

Google (Arora và cộng sự, Nature Cities 2026) cho thấy vai trò "nhà cung cấp dẫn đường điều phối" là thực tế, và đồng thời đặt mức so sánh: khoảng 2% tốc độ với dưới 2% chuyến bị đổi tuyến. Công cụ cho Phần 1: SB-DSO cho SUMO (Mehrabani và cộng sự 2022, 10.52825/scp.v3i.119). Larsson & Patriksson 1999 đã xác nhận là nguồn cho mục 6.

## 4. Hiểu bài toán: ràng buộc vật lý, cái biết và chưa biết

### 4.1 Vật lý của mạng hẻm (điều phải mô hình đúng)
1. **Dòng không làn, xe máy chiếm đa số**: sức chứa phụ thuộc bề rộng thực (porous flow), không phải số làn.
2. **Trễ dồn vào chỗ nhập**: hẻm nhập ra đường lớn bằng chen khe; xe máy chấp nhận khe khoảng 2.5 s, quyền ưu tiên yếu. Chính SUMO của ta cho thấy 30–60% trễ nằm ở các nhánh phụ này.
3. **Hẻm ngắn** (trung vị khoảng 20–30 m): một chuyến khoảng 30 quyết định, nên tầm nhìn quyết định rất ngắn so với tầm ảnh hưởng của tắc (tràn ngược hơn 5 phút, Fosgerau–Small).
4. **Ngoại ứng hai lớp**: lên xe khác (trễ) và lên dân hẻm (lưu lượng vượt sức chịu môi trường). Lớp thứ hai không nằm trong thời gian đi.
5. **Bất đối xứng thông tin**: hệ thống biết vị trí và ý định của đội xe mình, không biết xe nền.

### 4.2 Biết / chưa biết

| Đại lượng | Trạng thái | Nguồn hoặc cách xử lý |
|---|---|---|
| Hình học mạng, loại đường, đèn | **Biết** (OSM, 3 cạnh có đèn trong WCC) | Twin |
| Tốc độ theo giờ trên 1098/1828 cạnh | **Biết, dạng hồ sơ lịch sử**, không thời gian thực | Mapbox typical |
| Tốc độ trên 580 cạnh hẻm còn lại | **Chưa biết** | Fusion có bất định (G5) |
| Nhu cầu OD | **Chưa biết** | Hiệu chỉnh trong SUMO theo tốc độ; báo cáo theo kịch bản nhu cầu |
| Bề rộng hẻm, xe đỗ, hàng quán | **Chưa biết** (OSM không có) | Giả định theo lớp; phân tích độ nhạy |
| Hành vi chen khe | **Biết một phần** (tài liệu khoảng 2.5 s) | Tham số SUMO; độ nhạy |
| Sức chịu môi trường của hẻm | **Biết theo quy ước** (1500–3000 xe/ngày, nguồn phương Tây) | Ngưỡng là tham số chính sách, quét nhiều mức |
| Trạng thái thời gian thực | **Đo được cho đội xe của ta** (vị trí, tốc độ của xe dùng app) | Đây là quan sát hợp lệ duy nhất lúc chạy |
| Tuân thủ của người lái | **Chưa biết** | Quét mức tuân thủ (G4) |

Hệ quả: mọi kết luận phải đúng **trên một dải kịch bản** (nhu cầu, bề rộng, tuân thủ, ngưỡng), không phải một điểm hiệu chỉnh duy nhất. Twin là "phòng thí nghiệm có kiểm soát", không phải bản sao chính xác.

## 5. Hướng giải quyết đề xuất (giả thuyết, chờ duyệt)

### H1. Bài toán: nhà cung cấp dẫn đường tối ưu toàn hệ thống
Cực tiểu tổng thời gian đi của **mọi** xe (người dùng app + nền). Hẻm được dùng tự do. Tùy chọn: thêm ràng buộc lưu lượng trên hẻm c_e (side constraint) như một núm chính sách.

### H2. Chia công không cần chạy lại: reward = thời gian của mình + trễ mình gây ra + giá hẻm
- Trễ mình gây ra được quy theo hàng đợi trong SUMO (kiểu Kaddoura): một xe đứng trước trong hàng đợi chịu trách nhiệm cho phần trễ của các xe sau nó. Chi phí O(N), không phải O(N × số lần chạy lại) như Psarou. Đóng góp: phương pháp chia công kiểu này trong MARL quy mô lớn.
- Giá hẻm λ_e là nhân tử Lagrange của ràng buộc H1, cập nhật bằng dual ascent trên mức vi phạm đo được. Giá này **diễn giải được**: là mức "phí ảo" mà thành phố có thể dùng làm chính sách.

### H3. Kiến trúc: chú ý theo xung đột trong không gian–thời gian
- Mỗi xe chú ý tới top-K xe trong đội có **ý định đi qua cùng cạnh trong cùng khoảng thời gian** (đồ thị xung đột từ ETA dự kiến), cộng một mean-field cho phần còn lại (ý tưởng GAT-MF và đồ thị thưa thích nghi, nhưng hàng xóm được chọn bằng xung đột vật lý chứ không bằng khoảng cách).
- Đầu ra kiểu pointer trên các lối ra (đã có v1): bất biến hoán vị, không dùng id nút, nên chuyển giao được (G6).
- Đặc trưng cạnh gồm cả **độ bất định** của tốc độ (G5).

### H4. Bền vững với cái chưa biết
Train trên phân phối kịch bản (nhu cầu, bề rộng hẻm, tuân thủ, mẫu từ hậu nghiệm tốc độ); báo cáo trung bình và CVaR.

## 6. Lập luận khả thi (phác thảo, cần viết chặt ở bước sau)

1. **Chi phí biên dẫn tới SO.** Trong trò chơi tắc nghẽn phi nguyên tử với hàm chi phí cạnh tăng, cân bằng khi mỗi người dùng trả chi phí biên xã hội trùng với SO (Beckmann; thuế Pigou). Với ràng buộc lưu lượng trên cạnh, SO có ràng buộc tương đương cân bằng với phí = chi phí biên + nhân tử Lagrange của ràng buộc (kết quả kinh điển về gán luồng có ràng buộc phụ, ví dụ Larsson & Patriksson; **cần kiểm tra lại nguồn**). Vậy reward H2 nhắm đúng điểm tối ưu của H1, ở giới hạn luồng liên tục.
2. **Quy trễ theo hàng đợi là phân hoạch.** Mỗi giây trễ được quy cho đúng một xe gây ra, nên tổng trễ quy được bằng tổng trễ hệ thống. Phần này cần chứng minh cho cách quy cụ thể trong SUMO, và đo phần sai lệch, ví dụ trễ do chen khe không có thứ tự hàng đợi rõ.
3. **Tỉ lệ tham gia p < 1.** Đội xe là leader trong Stackelberg. Có cận PoA theo p cho mạng tuyến tính (Swamy), mà mục tiêu thực nghiệm là đường cong lợi ích theo p.
4. **Tính toán.** Đã đo trên sol1: 54k quyết định trong 16.5 s mỗi tiến trình SUMO; 80 nhân. Quy trễ theo hàng đợi chỉ thêm chi phí đọc trạng thái hàng đợi mỗi bước.

## 7. Điều cần kiểm chứng sớm (trước khi xây kiến trúc lớn)

1. **SO thật sự tốt hơn UE bao nhiêu trên mạng hẻm Q4?** Nếu khoảng cách UE–SO chỉ 1–2% thì bài toán định tuyến hợp tác không có đất. Cách đo: SUMO `duaIterate` (UE) so với gán theo chi phí biên (SO xấp xỉ), ở nhiều mức nhu cầu. **Đây là thí nghiệm quyết định số một.**
2. Lưu lượng đi tắt qua hẻm thay đổi bao nhiêu giữa UE và SO, và giữa có hoặc không có ràng buộc.
3. Quy trễ theo hàng đợi khớp với chi phí biên tính bằng chạy lại tới đâu, trên một mẫu nhỏ xe.

**Giả thuyết mới từ thí nghiệm thử (2026-11-02, 1 kịch bản, chờ kiểm chứng trên sol1):** trong mạng hẻm, xe trên đường lớn gây trễ cho xe chờ nhập từ hẻm, tức ngoại ứng **giữa các cạnh**. Chi phí biên theo cạnh (BPR, SB-DSO) không thấy phần này và cho SO tệ hơn UE; thêm ngoại ứng ngã nhập thì sửa được. Nếu đứng vững qua nhiều kịch bản, đây là đóng góp cơ chế của bài và là lý do chia công phải dựa vào xung đột ở nút. Số liệu ở `PLAN_V4.md`.

## 8. Tài liệu chưa đọc toàn văn nhưng phải đọc trước khi viết bài
URB (2505.17734); Psarou (2510.11410) và bản tiếp theo; Kaddoura & Kickhöfer 2014; Fosgerau & Small; Yun và cộng sự TR-C 2024; Cabannes và cộng sự (Berkeley); Nair và cộng sự porous flow (TR-B 2011); GAT-MF (KDD 2023); Swamy (Stackelberg); Larsson & Patriksson (side constraints).

---

## 9. Tự đánh giá phương pháp nghiên cứu (2026-11-02)

**Phần khảo sát ở trên chỉ là scoping review nhanh** (khoảng 15 lượt tìm web, phần lớn đọc trích đoạn). Nó đủ để định hướng, **không đủ** để viết Related Work hay khẳng định "chưa ai làm". Còn thiếu:

1. **Tổng quan có hệ thống** (theo tinh thần PRISMA): giao thức viết trước (cơ sở dữ liệu Scopus / Web of Science / Google Scholar / arXiv; chuỗi tìm kiếm; khoảng năm; tiêu chí nhận và loại), lần ngược và lần xuôi trích dẫn từ 5–10 bài lõi, bảng trích xuất (bài toán, mạng, mô phỏng, quan sát, reward, baseline, kết quả, giới hạn). Ghi số bài ở từng bước để đưa vào bài.
2. **Đọc toàn văn** khoảng 30–40 bài lõi, và tự kiểm lại mọi khẳng định "chưa có ai" bằng truy vấn ngược ("alley", "narrow street", "ngõ", "hẻm", "informal street network" + "routing").
3. **Kiểm chứng bài toán trước khi làm phương pháp** (mục 7): nếu khoảng UE–SO nhỏ thì luận điểm định tuyến hợp tác yếu.
4. **Giao thức thí nghiệm viết trước khi chạy**: kịch bản, baseline, chỉ số, seed, kiểm định thống kê, ablation, tiêu chí dừng. Giống quy tắc 50000/60000 đã có.
5. **Mối đe dọa tính hợp lệ** liệt kê từ đầu: nhu cầu chưa biết, bề rộng hẻm giả định, SUMO không phải thực tế, ngưỡng sức chịu môi trường lấy từ nghiên cứu phương Tây.

## 10. Hướng chốt

**Tên làm việc** (cập nhật 2026-11-02): dẫn đường tối ưu toàn hệ thống trong mạng hẻm xe máy, bằng MARL phi tập trung với chia công chi phí biên tính theo hàng đợi. Ràng buộc hẻm là núm chính sách tùy chọn. (Các dòng về "giá hẻm" dưới đây áp dụng khi bật núm này.)

**Đóng góp chính (bài TR-C), theo thứ tự ưu tiên**
1. *Bài toán*: nhà cung cấp dẫn đường với mục tiêu toàn hệ thống trên mạng hẻm xe máy (trễ dồn ở ngã nhập, không làn, tỉ lệ người dùng p < 1). Tùy chọn ràng buộc hẻm để thành phố đánh đổi.
2. *Phương pháp*: reward = thời gian của mình + trễ gây ra (quy theo hàng đợi, O(N), không chạy lại mô phỏng) + giá hẻm (nhân tử Lagrange, cập nhật theo vi phạm đo được). Kiểm chứng độ khớp với chi phí biên tính bằng chạy lại, trên mẫu nhỏ.
3. *Thực nghiệm*: twin hẻm Q4 trong SUMO, trên dải kịch bản (nhu cầu, tỉ lệ tham gia p, tuân thủ, ngưỡng hẻm), so với UE (duaIterate), SO xấp xỉ, app, greedy chi phí biên, MAPPO ích kỷ. Kết quả chính: đường cong đánh đổi giữa tổng thời gian đi và lưu lượng đi tắt.

**Không đặt làm đóng góp chính**: attention theo xung đột (để là lựa chọn kiến trúc, đánh giá bằng ablation; nếu thắng rõ và chuyển giao được sang quận khác thì tách thành bài A\*); fusion tốc độ (là đầu vào, trình bày như phương pháp dữ liệu).

**Cổng quyết định**
- G-A (thí nghiệm 1, mục 7): khoảng UE–SO trên Q4 ở nhu cầu tắc. Nếu < 3% ở mọi mức, đổi luận điểm sang "phân tích ngoại ứng đi tắt và định giá trong mạng hẻm" (vẫn TR-C), MARL thành phụ.
- G-B: greedy chi phí biên (không học) đã đạt bao nhiêu phần của khoảng đó. Nếu đạt gần hết, đóng góp của MARL phải nằm ở tỉ lệ tham gia thấp, thông tin không đầy đủ và ràng buộc hẻm, chứ không phải ở con số trung bình.

## 11. Đánh giá lại luận điểm và ứng viên khoảng trống (2026-11-02, chưa chốt)

Luận điểm người dùng đã đồng ý: app đã đưa xe máy vào hẻm nhưng mỗi xe tự chọn; điều phối phi tập trung có giảm các tình huống xấu nhất so với app không, và phụ thuộc tỉ lệ người dùng thế nào. Chưa có số liệu quét để kết luận.

| Ứng viên | Bằng chứng hiện có | Đối thủ | Rủi ro |
|---|---|---|---|
| A. Điều phối để giảm đuôi / ùn tắc diện rộng (luận điểm hiện tại) | 1 kịch bản local | Google 2026, Psarou, MA-GRL | Khoảng UE–SO có thể nhỏ |
| B. **Dẫn đường khi mù thông tin trong hẻm**: app không thấy kẹt hẻm theo thời gian thực; đội xe của chính app vừa đi vừa là cảm biến; giá trị thông tin theo tỉ lệ p | Dữ liệu của ta: Mapbox `congestion` 0% trên hẻm, live ≈ typical, 40% cạnh hẻm không có số đo. Chưa biết Google có giống vậy không | Mảng active sensing (D2FAS) và bandit đường đi, chưa thấy áp dụng cho hẻm hay tắc nghẽn hỗn hợp; mới tìm sơ bộ | Google có thể thấy đủ; chỉ khi đó mới mất điểm tựa |
| C. Chi phí định tuyến có tính ngã nhập, không cần học | Thí nghiệm `so_x`, `theory_merge.md` | Lý thuyết có từ 1980s | Đóng góp mô tả, khó thành bài riêng |
| D. Kết hợp điều khiển vùng (MFD) với dẫn đường | Có sẵn: Transp. Sci. 2023 và các bài trước | Mảng đông người | Lệch khỏi lợi thế của ta |

Đề xuất: giữ A làm câu hỏi chính nhưng thử B bằng hai phép đo rẻ trước khi chốt:
1. `data_fusion.google_route_probe`: Google có báo kẹt trong hẻm không.
2. Trong SUMO: app đủ thông tin so với app mù hẻm (giờ hẻm giữ theo hồ sơ lịch sử). Nếu chênh lớn, thông tin là đòn bẩy lớn hơn điều phối, và A + B thành một luận điểm: đội xe vừa dẫn đường vừa lấp chỗ mù.


## 12. Luận điểm gộp đề xuất (2026-11-02, người dùng gợi ý; chưa kiểm chứng)

**Đội xe vừa là cảm biến vừa là cơ cấu chấp hành**: nhà cung cấp dẫn đường điều phối người dùng trong mạng hẻm khi trạng thái tắc chỉ quan sát được một phần. Mức thông tin là **biến thí nghiệm**, nên bài không khẳng định gì về dữ liệu của Google; script Google tạm gác vì cần billing.

Cấu phần:
- **Niềm tin chung theo cạnh**: prior là hồ sơ theo giờ của Mapbox; cập nhật từ báo cáo của đội xe; gồm trung bình, độ bất định, tuổi quan sát. Lan truyền chéo sang cạnh lân cận bằng mô hình học.
- **Ý định**: số xe trong đội định vào mỗi cạnh trong Δ giây tới. Đây là thứ app biết mà bản đồ tốc độ không có.
- **Hành động**: chọn cạnh kế tiếp. **Không dừng trên đường**, vì chờ giữa hẻm gây chắn và tạo chính cái tắc. "Chờ xem" được hiện thực bằng: giữ lối đi chưa cam kết (giá trị quyền chọn ở nút rẽ), và tùy chọn hoãn xuất phát.
- **Phá đối xứng**: chính sách chung xác định sẽ làm mọi xe cùng chờ hoặc cùng đi. Cần chính sách ngẫu nhiên hoặc nhiễu riêng từng xe để có xe đi thử.

Tài liệu gần nhất (mới đọc trích đoạn): Vasserman và cộng sự, IJCAI 2015; Li & Duan, arXiv 2404.15599 (định tuyến cận thị thăm dò thiếu, PoA > 2); arXiv 2501.03055; bài toán đường đi ngắn nhất trực tuyến với Thompson sampling. Phần lớn là mạng nhỏ hoặc trừu tượng, cần kiểm chứng thêm.

Rủi ro:
1. Trong SUMO, nếu không có nguồn bất định ẩn thì không có gì để thăm dò. Phải thêm **sự cố ẩn trong hẻm** (xe đỗ, chợ, đám), mà tần suất thật thì dữ liệu miễn phí không đo được, nên phải quét.
2. Thompson sampling trên niềm tin chung có thể đạt gần hết lợi ích mà không cần học. Nó phải là baseline, không được bỏ.
3. Người bị chọn đi thử chịu thiệt, nên phải báo cáo công bằng và mức tuân thủ.

Thí nghiệm cổng C, trước khi xây kiến trúc: trong SUMO có sự cố ẩn, quét mức thông tin (không live, chỉ đường lớn, chỉ đội xe với tỉ lệ p, đủ) với app và Thompson. Nếu đủ thông tin không hơn hẳn không live thì hướng này không có đất.

## 13. Luận điểm và đóng góp sau đợt đọc toàn văn (2026-11-04)

Thay cho phần tương ứng ở mục 3, 10, 12. Chưa chạy Scopus / WoS. Kết quả định lượng của phương pháp chưa có, nên đây là điều bài **định** nói.

**Câu hỏi:** một nhà cung cấp dẫn đường điều phối phần xe của mình ở mức next-hop trên mạng có nhiều hẻm, khi chỉ có báo cáo không hoàn hảo và người lái không luôn làm theo, thì giảm được J = 0.5 T_all + 0.5 T_cust bao nhiêu so với app tốt nhất, và lợi ích đổi theo p, tuân thủ, thông tin ra sao?

**Đóng góp định nói, theo thứ tự chắc chắn giảm dần:**
1. Mô hình và đánh giá en-route có học trên mạng hẻm mô hình riêng, xe máy, với bộ giới hạn thực tế chung cho mọi controller. Khác biệt chủ yếu về bối cảnh.
2. Đo tương tác giữa p, tuân thủ theo quyết định và báo cáo nhiễu. Có giá trị chỉ khi tương tác đáng kể.
3. Chia công theo trễ đo được từng xe, có đối chiếu với phản thực. **Hiện chưa có bằng chứng**: kiểm chạy lại chưa đo sàn nhiễu, Psarou 2510 p.4, p.6 cho lý do ở ngã ưu tiên có thể sai, và trên 8 seed chọn mô hình `selfish` 480.8, `attrib` 488.6, ff 484.5, app 492.3 (chưa phân biệt được). Nếu không qua kiểm chứng thì bỏ khỏi đóng góp, giữ làm phân tích.

**Không còn nói được:** "đầu tiên" cho next-hop RL, không tuân thủ, nhà cung cấp gợi ý, credit không chạy lại, mạng lớn nhất. Câu "app chưa tính hẻm" đã bỏ từ trước.

**Đối thủ gần nhất:** Yun 2024 / Kim 2025 (có dữ liệu Kakao thật), nhóm Kucharski (Psarou, Akman), MA-GRL. Theo dõi bản mới của họ trước khi nộp.

## 14. Rà lại luận điểm theo quy trình điểm yếu trước (2026-11-06)

Nguyên tắc người dùng chốt: tìm điểm yếu của baseline → có đáng làm không → ai làm rồi → làm thế nào → khả thi không → có thể tham khảo và kết hợp → triển khai. Không làm thuật toán mạnh rồi chờ thắng. Nếu không còn luận điểm mạnh thì nộp Q2/Q3 với đóng góp thật, rồi sang bài khác.

**Bước 1. Baseline có điểm yếu không (từ toàn bộ nhật ký `PLAN_V4.md`):**
1. Trung bình: không có điểm yếu hệ thống. ff, app, greedy chênh trong ±1% ở 144 tập (v6, app hơn ff 0.7% ± 1.5), ở v7 (16 seed mới: 507.4 / 508.4 / 506.4) và v10 (thường 401 / 398 / 404). Cổng A: UE ≈ SO_x ≈ ff (chênh dưới 1%). Tập đường tĩnh tốt nhất hơn ff 3–8%, rõ chỉ khi nhu cầu rất dồn (dạng 0.9/2/0.7: 6–11%). MARL v6–v11 chỉ ngang ff đến hơn khoảng 1%, và lợi giảm khi p tăng (v7).
2. **Theo từng tập (mới, v7 cuối, 64 tập 50008–50023, teleport 300 s, các file `diag_v6/v7f/t300/*/heldout_eval*.json`):** tập xấu của controller nào cũng được controller khác cứu với mức như nhau. Lợi của X so với Y trên 25% tập xấu nhất của Y: ff hơn app 78.4 s, ff hơn greedy 77.7, app hơn greedy 80.0, greedy hơn app 75.6, app hơn ff 38.7, greedy hơn ff 54.6. Tương quan J giữa hai controller trên cùng kịch bản chỉ 0.27–0.54. Độ lệch chuẩn của chênh lệch ghép cặp khoảng 80 s (khoảng 16% J). Chọn tốt nhất trong 3 heuristic theo từng tập hơn ff 40.5 s, nhưng phần lớn chỉ là chọn may trong nhiễu.
   - Đọc: **greedy không sai ở một tình huống đoán trước được.** Mỗi tập là một lần "lật" tắc cục bộ ở vài nút hẻm, xảy ra hoặc không, và controller nào cũng gặp. Lưu ý: ở v7, SUMO seed chưa theo seed kịch bản (sửa từ v8, A1/A5), nên một phần nhiễu là RNG của SUMO. Phải đo lại trên thiết lập v10.
3. Lựa chọn mô hình hoá làm đổi thứ hạng mạnh hơn controller: bề rộng 1.75 m gây kẹt ở nút 5778362217; độ phân giải ngang 0.2 m so với 0.4 m làm app lệch 10%; teleport 180/300/600 s đổi dấu kết quả (v6: argmax thua ff 17.5% ở 600 s; v7: greedy tốt nhất ở 600 s).
4. Kịch bản dồn xe v10: app và greedy thua ff (725, 741 so với 714). Nhưng ở một điểm nóng đã khai thác thì app thắng ff (665 so với 744). Chưa tách theo từng điểm nóng.

**Kết luận bước 1:** điểm yếu chung của mọi heuristic, và của MARL, là **đuôi do tắc lật cục bộ**, không phải trung bình. Luận điểm §13 ("giảm J bao nhiêu so với app tốt nhất") không đứng được. Đóng góp 3 (`attrib`) bỏ.

**Bước 2. Có đáng làm không:** kẹt cứng hẻm là chuyện thật ở TP.HCM. Nhưng trong twin, hiện tượng này dính với deadlock và teleport của SUMO và với giả định bề rộng. Chỉ đáng làm nếu việc lật có thể điều khiển được: phát hiện sớm và chuyển một phần đội xe thì giảm được xác suất lật.

**Bước 3. Đã có ai làm chưa (tìm nhanh, chưa đọc toàn văn):**
- Gating hoặc perimeter control bằng đèn: Keyvan-Ekbatani và cộng sự 2013, gating ở thượng nguồn; perimeter control kết hợp route guidance (arXiv 2508.08617, T-ITS). Các nút không có đèn (nút ưu tiên) **bị loại khỏi điều khiển** trong các bài này.
- Thông tin trễ gây phản ứng quá mức và tắc; giấu bớt thông tin thì tránh được (Bittihn và Schadschneider, arXiv 2105.11790). Gợi ý đường thời gian thực có thể gây hại (arXiv 2303.17923).
- Ví dụ UXsim: gridlock ở nút nhập, đổi quyền ưu tiên thì hết tắc (arXiv 2309.17114).
- Khuyến nghị 10–20 lần lặp mỗi cấu hình và dùng chung seed (arXiv 2604.23240).
- Chưa thấy bài nào gating nút hẻm không đèn bằng chính chỉ dẫn của nhà cung cấp dẫn đường. Mới tìm nông, phải kiểm thêm.

**Bước 4–5. Cách làm ứng viên và khả thi:** kết hợp, không cần học. Cảnh báo sớm từ báo cáo probe ở các nút dễ lật (danh sách đã khai thác) + bộ điều khiển phản hồi kiểu gating (PI trên số xe đứng ở nút), chuyển một phần xe đội sang nhánh khác. MARL hoặc greedy là baseline. Rủi ro:
- (a) lật có thể không báo trước được;
- (b) đội xe nhỏ có thể không đủ để chặn;
- (c) kết quả có thể không giữ qua SUMO seed, bề rộng, độ phân giải;
- (d) reviewer có thể gọi đây là artifact deadlock của SUMO.

**Cổng H (khoảng 1–2 ngày CPU, không train):**
- Trên thiết lập v10 (SUMO seed theo kịch bản), mỗi controller chạy K = 5 SUMO seed để tách phần nhiễu hỗn loạn khỏi phần controller.
- Thử luật gating đơn giản so với ff, app, greedy đã tune.
- **Đạt** khi luật giảm J trung bình của 25% tập xấu nhất (chọn theo trung bình các controller, không theo chính nó) ít nhất 10%, khoảng tin cậy 95% không chứa 0, không làm tệ trung bình quá 1%, và giữ được ở 0.2 m và ở hẻm 2.5 m.
- **Đạt** → luận điểm mới: nhà cung cấp dẫn đường chặn tắc lật ở nút hẻm không đèn. Nhắm TR-C, dự phòng T-ITS.
- **Trượt** → nộp Q2/Q3, rồi sang bài khác. Bài Q2/Q3 gồm:
    - twin hẻm Q4 từ dữ liệu miễn phí và nhãn bề rộng;
    - kết quả trung thực: điều phối và học chỉ ngang heuristic khoảng 1% trên mạng hẻm xe máy;
    - kết quả bị chi phối bởi tắc lật cục bộ và giả định mô hình (bề rộng, độ phân giải, teleport), kèm khuyến nghị đánh giá.

**Cập nhật 2026-11-06 tối: nguyên nhân gốc là mạng twin, không phải Quận 4.**

Đo bằng OSM (osmnx 2.1.1 trên sol1; script và log ở `diag_v6/cand*.py`, `cand.log`, `cand2.log`). Ô khoảng 2.7 km, cùng bộ lọc đường. "Có lựa chọn" nghĩa là chuyến có đường thay thế dài tối đa 1.3 lần thời gian free-flow và trùng không quá 50% chiều dài.

| Mạng | Nút | Đoạn cắt là tách mạng | Vùng có vòng lớn nhất | Đường không trùng ≤1.3× |
|---|---|---|---|---|
| Twin Q4 đang dùng | 886 | 67% | 16% | 13% |
| Q4, OSM đầy đủ | 2950 | 26% | 67% | 24% |
| Q1 + Q4 | 5496 | 24% | 68% | 28% |
| Q10 | 4312 | 16% | 77% | 38% |
| Q8 | 3104 | 23% | 64% | 14% |
| Bình Thạnh | 2704 | 32% | 60% | 9% |

Tỉ lệ chuyến có lựa chọn ≤1.3×: twin cũ 0.20; Q4 OSM đầy đủ 0.49–0.55, tuỳ cách chọn vùng đích (điểm xa nhau nhất trên mọi nút, trên nút giao, hoặc cổng biên + nút giao).

Nguyên nhân:
1. Bộ lọc của `build_quan4_map` không có `primary` và loại `trunk`.
2. `export_wcc_subgraph` chỉ giữ hẻm cộng các đường cách hẻm 1 bước, nên mất các đường lớn nối các hẻm.

Cách chọn vùng đích chỉ ảnh hưởng ít. **Chốt: giữ Quận 4, dựng lại mạng từ OSM đầy đủ.**

Các cổng trước khi làm phương pháp:
1. Mạng SUMO mới: đo tỉ lệ chuyến có lựa chọn và thời gian chạy.
2. Còn đất: `gate_msa` tập đường tốt nhất so với ff, UE–SO, ở mức tắc vừa.
3. Cổng H (đuôi do tắc lật).

Mọi kết quả v1–v11 chạy trên mạng thiếu đường lớn. Chúng được giữ lại để báo cáo và không dùng làm kết quả chính.
