# Ghi chú đọc, nhóm 4: mô phỏng xe máy, mạng đồ thị và pointer network

Bản 2026-11-04. Đọc từ văn bản trích từ PDF (`scratchpad/papers_txt/`), không xem hình.

Quy ước:
- `p.N` là trang của **tệp PDF**, không phải số trang in. Vu có một trang bìa (PDF p.2 là trang in 1). Chouta in 303+, Chen in 267+.
- "Nhận xét:" là ý của người đọc, không phải của tác giả. Số có ghi "tính lại" do người đọc tính từ số trong bài.
- "Không nêu trong bài" nghĩa là không có trong văn bản trích. Số chỉ nằm trên hình hoặc bảng dạng ảnh thì không đọc được, nên cũng ghi như vậy.
- Tìm chuỗi trên 4 bài xe máy: không bài nào chứa `jmTimegapMinor`, `impatience`, `lcSublane`, `minGapLat`, `lcPushy`, `latAlignment`, `sigma`, `teleport`, `alley`, `narrow`. Cụm "gap acceptance" có ở 3 bài nhưng **không kèm con số nào** (Chouta p.2, Salawavidana p.1-2, Vu p.3). Bảng 1 của Salawavidana có cột "Min. Gap" (m) và bài gọi nó là "minimum gap acceptance" (p.2-3); đó là khoảng cách, không phải khoảng thời gian chấp nhận.

vType của ta để so sánh: motorcycle, length 1.9, width 0.8, minGap 0.5, maxSpeed 15 m/s (54 km/h), accel 2.5, decel 4.5, sigma 0.5, speedDev 0, latAlignment arbitrary, minGapLat 0.3, lcSublane 1.0, lcPushy 0.5; lateral resolution 0.8 m, step 0.5 s, time-to-teleport 180 s; hẻm giả định rộng 2.5 m.

**Kết luận chính của phần xe máy.** Trong nhóm này chỉ có 2 bài hiệu chỉnh thật (Salawavidana, Vu), đều trên đường lớn có đèn. Không bài nào có tham số nút giao không đèn, nên chỗ nghẽn của ta (nhập hẻm vào đường cấp ba) **không có giá trị trích dẫn được từ nhóm này**.

---

## Phần A. Mô phỏng xe máy

### 1. Chouta & Facchi 2026 (background)

**Trích dẫn.** Chouta, Facchi. "Improving SUMO for Motorcycles". SUMO Conf Proc 7 (2026), SUMO User Conference 2026, in 303-320, doi 10.52825/scp.v7i.3229 (p.1-2). Tên tệp đúng chủ đề nhưng dễ gây hiểu lầm: bài này mô hình **góc nghiêng (roll)**, không hiệu chỉnh hành vi xe máy.

**Địa điểm, tỉ lệ.** Vòng xuyến Audi-Kreisel và nút Hindenburgstr./Ringlerstr., Ingolstadt, Đức, lấy từ kịch bản InTAS (p.9). Tỉ lệ xe máy: không nêu trong bài; chỉ thêm 13 xe máy vào giao thông có sẵn (p.9), kịch bản vòng xuyến có 1 xe (p.9).

**Simulator.** SUMO có sửa mã nguồn (thêm `MotorcycleRollModel`, `CurvatureFitting`, p.6-8), phiên bản không nêu trong bài. Bước 0.1 s (p.8). Dùng **vType xe máy mặc định** của SUMO, không thêm luật đổi làn hay vượt (p.8); giá trị cụ thể không nêu trong bài.

| Tham số | Giá trị | Có hiệu chỉnh? | So với ta |
|---|---|---|---|
| τκ (lọc độ cong) | 5.0 s | Không, chọn theo kinh nghiệm vì thiếu số đo (p.7) | Không có tương ứng |
| τφ (đáp ứng roll) | 0.6 s | Không (p.7) | Không có tương ứng |
| φ̇max | 1.8 rad/s | Không (p.7) | Không có tương ứng |
| Lwindow, N | 12 m, 10 điểm | Không (p.5, p.7) | Không có tương ứng |
| step-length | 0.1 s | Không (p.8) | Ta 0.5 s; mục đích khác nên không so được |
| Mọi tham số vType, sublane, nút giao | Không nêu trong bài | | |

**Kiểm chứng.** Chỉ kiểm định tính và theo vật lý, không có dữ liệu đo (p.9-10): góc trong khoảng khoảng ±35 độ của giao thông thường, liên tục, đúng chiều cong (p.10). Chưa có sai số định lượng; so với quỹ đạo và IMU thật là việc tương lai (p.16).

**Giới hạn tác giả nêu.** Roll chưa ảnh hưởng điều khiển dọc hay ngang (p.16), nên **không đổi độ trễ**. Lọc độ cong gây trễ ở nút giao (p.16).

**Hẻm hẹp.** Không áp dụng. Nhận xét: ý nghĩa duy nhất là bài nói mô hình SUMO hiện tại xem xe máy gần như xe nhỏ có tham số chỉnh lại (p.2).

**Liên quan: background.** Đề xuất: không trích làm nguồn hiệu chỉnh. Hai tài liệu tham khảo đáng tìm: Codeca & Härri 2019 về xe hai bánh trong SUMO và Kuo et al. 2023 so sánh simulator cho xe hai bánh (p.17).

---

### 2. Salawavidana et al. 2026 (core, nhưng ít số)

**Trích dẫn.** Salawavidana, Pasindu, Bandara, Munasinghe. "Aggregate Level Calibration of SUMO for Heterogeneous Traffic Conditions at Sri Lankan Signalised Intersections". 19th Transport Research Forum 2026, Đại học Moratuwa, doi 10.31705/TRF.2026.1 (p.1). Bài hội nghị ngắn 4 trang, không có bảng kết quả theo từng hướng.

**Địa điểm, tỉ lệ.** 2 nút có đèn: Piliyandala (4 nhánh, để hiệu chỉnh) và Katubedda (3 nhánh, để kiểm tra chuyển giao) (p.1). Có xe máy và 8 loại khác (p.2). Tỉ lệ xe máy: không nêu trong bài.

**Simulator.** SUMO, phiên bản không nêu trong bài. Krauss, lateral resolution 0.1 m (p.3). Lưới dựng từ OSM Web Wizard và pha đèn thật (p.2).

**Tham số hiệu chỉnh của xe máy (Bảng 1, p.3).**

| Tham số | Salawavidana | Ta | Nhận xét |
|---|---|---|---|
| accel | 6.0 m/s² | 2.5 | Của họ gấp 2.4 lần (tính lại) |
| decel | 4.5 m/s² | 4.5 | Trùng |
| length | 2.0 m | 1.9 | Gần như trùng |
| minGap | 0.1 m | 0.5 | Của họ chỉ bằng 1/5 |
| maxSpeed | 60 km/h, tức 16.7 m/s (tính lại) | 15 m/s | Gần nhau |
| lateral resolution | 0.1 m (p.3) | 0.8 m | Của họ mịn hơn 8 lần |
| lcStrategic, lcCooperative | Có chỉnh (p.2-3), giá trị không nêu trong bài | Chưa đặt | Không trích được |
| speed variation | Có chỉnh (p.2), giá trị không nêu trong bài | speedDev 0 | Không trích được |
| car-following | Krauss (p.3) | Không ghi trong đề bài | |
| width, sigma, lcSublane, lcPushy, minGapLat, latAlignment, impatience, jmTimegapMinor, step, teleport | Không nêu trong bài | | |

**Kiểm chứng, sai số.** Dữ liệu: video camera cố định giờ cao điểm, gộp 15 phút, đếm lưu lượng theo loại và hàng đợi làm tròn 5 m (p.2). Ngưỡng chấp nhận: MAPE dưới 15%, GEH dưới 5 cho các loại xe chính (p.3).
- Piliyandala: GEH lưu lượng dưới 5 cho mọi loại; MAPE thường dưới 15%; GEH hàng đợi thường dưới 5, nhưng tối đa 7.8 ở một khoảng 15 phút (p.3). Làn chung sai nhiều hơn làn riêng (p.3).
- Katubedda, không chỉnh lại: MAPE dưới 15% mọi hướng; GEH hàng đợi 0 đến 3.6 (p.4).

**Giới hạn tác giả nêu.** Chỉ 2 nút; một số hướng vượt nhẹ ngưỡng GEH hàng đợi (p.4). Nhận xét: hiệu chỉnh tay, lặp đến khi đạt ngưỡng (p.2-3), không tối ưu tự động. Accel 6.0 và minGap 0.1 có thể bù cho mô hình làn (đoán, bài không phân tích); không nên xem là số đo hành vi.

**Hẻm hẹp.** Bề rộng làn không nêu trong bài; đây là nút có đèn, nên không cho biết gì về nhập không đèn. Dùng được phương pháp, không dùng được số cho hẻm.

**Liên quan: core.** Là bài duy nhất trong nhóm có **giá trị SUMO trực tiếp cho xe máy**. Đề xuất: (a) đưa minGap 0.1, accel 6.0, lateral resolution 0.1 vào sweep như biên trên có nguồn; (b) dùng MAPE dưới 15% và GEH dưới 5 làm tiêu chí; (c) theo cách giữ một địa điểm ngoài để kiểm tra chuyển giao; (d) tìm nguồn họ trích: Chowdhury & Chakraborty 2024 hiệu chỉnh SUMO ở Khulna (p.4).

---

### 3. Vu & Preston 2023 (core về phương pháp; đây là VISSIM)

**Trích dẫn.** Vu, Preston. "Microscopic Simulation Model for Motorcycle Dominated Networks: A Case Study of a VISSIM Simulation Model for a Mixed Traffic Corridor". IOP Conf. Ser.: Mater. Sci. Eng. 1289 (2023) 012045, TISDIC 2023 (p.1-2).

**Địa điểm, tỉ lệ.** Phố Quang Trung, Hà Nội: đoạn 1.5 km, 3 nút đèn thời gian cố định, 4 làn mỗi chiều rộng 3.75 m (p.7, p.9, p.11). Xe máy 77.47%, ô tô 13.72%, buýt 8.81% (p.9). Xe máy dưới 150 cc (p.7). Dữ liệu năm 2018 (p.9).

**Simulator.** VISSIM; bản tham chiếu là sổ tay VISSIM 5.40 (p.18), bài không nói rõ bản đã chạy. Bài chọn VISSIM thay vì SUMO, chê mô hình sublane SUMO 2 làn con rộng 2 m của Izadi et al. vì thực tế có thể 3 xe máy đi ngang hàng (p.4).

**Quy trình.** 9 bước của Park & Schneeberger (p.5-6, p.11): 3 mức cho 4 tham số, 81 tổ hợp, 5 seed mỗi tổ hợp, tổng 405 lần chạy, mỗi lần 60 phút với 15 phút khởi động (p.12); hồi quy tuyến tính làm mặt đáp ứng (p.12); 5 ứng viên chạy 40 seed (p.13); kiểm định t và K-S (p.13-14); kiểm chứng bằng chiều và giờ khác (p.14-15).

| Tham số VISSIM | Lưới thử (p.12) | Chọn: cao điểm (p.17) | Chọn: thấp điểm (p.17) | SUMO gần nhất, của ta | Nhận xét |
|---|---|---|---|---|---|
| Average standstill distance | 2, 1, 0.5 m | 0.5 | 0.5 | minGap 0.5 | Trùng số, khác mô hình. Giá trị chọn nằm ở **biên dưới của lưới**, nên có thể còn thấp hơn |
| Minimum lateral distance at 50 km/h | 1, 0.8, 0.6 m | 0.8 | 1.0 | minGapLat 0.3 | Của họ lớn hơn nhiều, nhưng không cùng định nghĩa; bản ở 0 km/h không nêu trong bài |
| Desired speed xe máy | 50, 40, 30 km/h | 40 (11.1 m/s, tính lại) | 50 (13.9 m/s, tính lại) | maxSpeed 15 m/s | Không có ảnh hưởng đáng kể ở cao điểm (p.16-17) |
| Desired speed ô tô, buýt | 60, 50, 40 km/h | 40 | 50 | Không áp dụng | |
| Gia tốc mong muốn xe máy | Đo: 200 xe, súng radar, hàm theo tốc độ 0-50 km/h (p.9-10) | Đường cong ở Hình 4 (p.11) | Như trên | accel 2.5 hằng số | **Số chỉ nằm trên hình, không đọc được**. Giảm dần theo tốc độ (p.11) |
| Giảm tốc xe máy | Tóm tắt nói có khảo sát (p.2), nhưng phần giới hạn nói chỉ nghiên cứu gia tốc (p.17) | Không nêu trong bài | Không nêu trong bài | decel 4.5 | Bài tự mâu thuẫn |
| Tham số SUMO và tham số nhường đường | Không nêu trong bài | | | | |

**Độ nhạy (hồi quy cao điểm, thời gian đi xe máy, p.20).** Standstill b = 510.43 s/m, p dưới 0.001; lateral b = -128.22 s/m, p = 0.043; tốc độ không có ý nghĩa (p = 0.708 và 0.354); R² = 0.928. Xu hướng cùng dạng với buýt (p.19) và ô tô (p.19). Dấu âm của lateral được tác giả giải thích là khoảng ngang lớn đi với tốc độ lớn, dẫn Nguyen & Sano (p.16).
Nhận xét: không nên ngoại suy độ dốc 510 s/m, vì thời gian đi quanh 216 s (p.13) quá nhỏ so với nó, có thể do các tổ hợp gần tắc kéo lên (đoán). Điều dùng được: khoảng dừng là núm mạnh nhất.

**Kiểm chứng, sai số.**
- Hiệu chỉnh: thực đo buýt/ô tô/xe máy 288.14, 220.17, 213.59 s (p.12), chọn nếu lệch dưới 6 s (p.12). Case 4 (5 seed): 283.04, 224.03, 216.42 s (p.13), tức lệch -1.8%, +1.8%, +1.3% (tính lại).
- Case 1, 2, 5 làm **tắc toàn mạng** khi chạy 40 seed, nguyên nhân được cho là xung đột đổi làn ở vạch dừng (p.13). Cả 5 ứng viên đều có standstill 0.5 (p.13), nên 0.5 không tự gây tắc; nhưng đó cũng là mức thấp nhất của lưới.
- Kiểm chứng: thực đo chiều ngược, 39 buýt, 72 ô tô, 142 xe máy, 259.57, 177.23, 180.21 s (p.15). Case 3, 4 đều qua kiểm định t; chọn Case 4 (p.15). **Giá trị mô phỏng và thống kê t không có trong bài**: p.14 nói ở Phụ lục, nhưng Phụ lục chỉ có hồi quy (p.19-21).
- K-S **không chạy cho xe máy** vì mẫu thực đo quá nhỏ so với mô phỏng, 153 so với 1881 xe (p.14). Với ô tô, buýt chỉ cần 1 trong 40 lần qua là đạt (p.13), là tiêu chí yếu (nhận xét).
- Thấp điểm chỉ hiệu chỉnh theo **thời gian buýt** (p.15), nên 50 km/h và 1.0 m cho xe máy thấp điểm không được kiểm bằng dữ liệu xe máy.

**Dữ liệu.** Đếm video 16:30-18:30 và video cảnh sát Hà Nội (p.9); thời gian đi xe máy do người khảo sát tự chạy, 2 người một xe (p.10).

**Giới hạn tác giả nêu.** Chỉ đo gia tốc xe máy; thiếu tham số khác như khoảng đổi làn; hành lang chỉ 1.5 km (p.17).

**Hẻm hẹp.** Không áp dụng trực tiếp: làn 3.75 m, đường trục, nút có đèn (p.9). Nhận xét: tính lại với hẻm 2.5 m, xe 0.8 m: minGapLat 0.3 cho 2 xe ngang hàng (2×0.8 + 0.3 = 1.9 m), còn 0.8 thì 2×0.8 + 0.8 = 2.4 m, sát giới hạn. Vì vậy trong hẻm tham số này rất có thể đổi hẳn năng lực, nên phải sweep, không nên chép 0.8.

**Liên quan: core.** Vì cùng Việt Nam và cùng dùng **thời gian đi**, thứ ta có từ Mapbox. Đề xuất: (a) dùng khung 9 bước cho sweep: lưới nhỏ, 5 seed, mặt đáp ứng, ứng viên 40 seed; (b) kiểm chứng trên chiều hoặc giờ khác; (c) kiểm tắc mạng và teleport như tiêu chí loại, như bước Evaluation của họ; (d) trích 77.47% làm tỉ lệ đo cho một đường trục ở Hà Nội, **không phải** cho TP.HCM hay hẻm.

---

### 4. Chen et al. 2022 (useful ở mức thấp; tên tệp gây hiểu lầm)

**Trích dẫn.** Chen, Lin, Yeh, Cho, Wu. "Prediction of Queue Dissipation Time for Mixed Traffic Flows With Deep Learning". IEEE Open Journal of ITS, vol. 3, 2022, in 267-277, doi 10.1109/OJITS.2022.3162526 (p.1). **Tên tệp "Motorcycle" gây hiểu lầm**: đây là thị giác máy tính dự báo thời gian giải tỏa hàng đợi, không có simulator nào được hiệu chỉnh.

**Địa điểm, tỉ lệ.** 3 nút đèn ở Đài Loan: Dayuan (2 nút, Taoyuan) và "Aly. 1, Ln. 1, Xipu Rd." (Kaohsiung) (p.7-8). Tỉ lệ xe máy: không nêu trong bài, chỉ nói là lớn (p.4).

**Simulator.** Không có. Mọi tham số vType, sublane, nút giao: không nêu trong bài.

**Phương pháp.** YOLOv4 tạo "vehicle density map", VGG16 rút gọn (RM2: đầu vào 416×416, kernel 52, 104, 208, 416) hồi quy thời gian giải tỏa (p.4-6). Nhãn sinh tự động bằng SORT (p.4). 981,295,415 ảnh hợp lệ, chia 60/20/20 (p.8).

**Kết quả.** RM2 MAPE 10.3771% (p.8); hồi quy tuyến tính 20.34%, SVR 17.65%, XGBoost 25.78%, RF 27.94% (p.8-9). Bỏ xe máy: 31.2912% (p.9). R² 0.9145 (p.3). Cùng thành phần xe, thứ tự khác: khoảng 18 s so với 13 s (p.4).

**Giới hạn.** Dữ liệu chưa công khai (đang thương lượng với Kaohsiung) (p.10). Dữ liệu các nước khác là việc tương lai (p.10). Nhận xét: chia ngẫu nhiên theo ảnh, không theo nút hay ngày (p.8), nên 10.4% không phải sai số chuyển giao; con số 981 triệu ảnh rất lớn so với khoảng 12 ngày quay (p.7-8), bài không giải thích.

**Hẻm hẹp.** Một nút có địa chỉ hẻm (p.8) nhưng hình học không nêu trong bài và không có kết quả riêng từng nút trong văn bản. Không dùng làm bằng chứng cho hẻm.

**Liên quan: useful (thấp).** Trích được ý định tính: xe máy xếp song song và giải tỏa khác ô tô (p.2), thứ tự trong hàng đợi đổi thời gian giải tỏa (p.4). Không có tham số để trích.

---

## Phần B. Đồ thị, pointer network

Bảng tóm tắt. Chỉ có Lei và Kool dùng GNN hoặc attention làm **policy**, và đều cho bài toán tĩnh dựng tuyến, một tác tử. Không bài nào điều khiển giao thông động, dùng line graph, hay nói về teleport.

| Bài | Nhiệm vụ | Nút, cạnh | Độ sâu, head | Mạng lớn nhất | Dữ liệu huấn luyện |
|---|---|---|---|---|---|
| Liu 2024 (HetGAT) | Học luồng UE tĩnh | Nút giao; cạnh thật + cạnh ảo OD | 2 V + 2 R, 8 head (p.9) | Anaheim 416/914 (p.8) | 5000 mỗi kịch bản, 80/20 (p.9) |
| Liu 2024b (HSTGSN) | Học luồng DUE | Nút giao; cạnh thật + cạnh ảo OD | Không nêu trong bài | Chicago 933/2560 (p.6) | 1000, 8:1:1 (p.6) |
| Lassen 2025 | Học luồng SUE | Nút, gồm centroid; cạnh có đặc trưng | 6 GatedGCN, không head (p.4) | Sioux Falls 24/76 (p.4) | 10000, 60/20/20 (p.4) |
| Rahman (GCNN) | Học luồng UE tĩnh | Nút OD; cạnh theo ma trận | 3 lớp (p.7-8) | EMA 74/258 (p.10) | 3500 mỗi điều kiện (p.12) |
| Lei (E-GAT) | **Policy** TSP, CVRP | Đồ thị đủ | 4, 8 head (p.14) | 100 nút; TSPLIB tới 159 (p.20) | Xem mục 9 |
| Kool 2019 (AM) | **Policy** TSP, VRP, OP | Đồ thị đủ, có thể mask | 3, 8 head (p.3, p.6) | 100 nút (p.6) | Xem mục 10 |
| Vinyals 2015 | Có giám sát: hull, Delaunay, TSP | Chuỗi | LSTM 1 lớp (p.6) | n = 500 hull, 50 TSP (p.7-8) | 1M cặp (p.6) |
| Veličković 2018 | Phân loại nút | Nút, cạnh chung | PPI 3 lớp; 4, 4, 6 head (p.7) | 56944 nút/24 đồ thị (p.6) | 20 đồ thị (p.6) |

So sánh: 1828 link của ta lớn hơn mọi mạng ở các bài policy và chỉ nhỏ hơn Chicago ở bài supervised. Số tham số mô hình (ta 181k): không nêu trong cả 8 bài.

### 5. Liu & Meidani 2024, "End-to-End Heterogeneous GNN for Traffic Assignment" (useful)

**Trích dẫn.** Tong Liu, Hadi Meidani. arXiv:2310.13193v3, 16/10/2024, **preprint** (p.1).

**Kiến trúc.** Node feature là vector OD độ dài |V| + 2 tọa độ (p.6). Cạnh ảo OD giảm số hop, nên cần ít lớp hơn (p.7). Thêm mất mát bảo toàn luồng (p.8). 4 lớp, 8 head, hidden 64, lr 0.001, batch 128 (p.9).

**Ngân sách.** Sioux Falls, EMA, Anaheim: giải UE 56.8, 575.2, 2612.5 phút; huấn luyện 26.8, 28.9, 59.7 phút (p.11). Suy luận 1000 đồ thị: 0.13, 0.15, 0.31 phút (p.11). Số epoch: không nêu trong bài.

**Độ chính xác (Anaheim, utilization MAE, p.12).** LMH-LMH 2.97%; L-M 3.31%; M-H 6.66%. Mất 40% OD: 3.12% (p.13).

**Tổng quát hóa.** 20 biến thể topology mỗi mạng: Anaheim 3.29%, GAT 14.94%, GCN 16.29% (p.13). Mạng ngẫu nhiên test N=100: chuẩn 2.75%, transfer 4.18%, đồng nhất 8.46% (p.15). Test N=300: 4.99%, 8.45%, 5.63% (p.15). Nhận xét: bài không nói topology test có bị giữ ngoài tập train hay không (p.13-15).

**Giới hạn.** Node feature phụ thuộc N, nên đổi kích thước phải huấn luyện lại 2 lớp hoặc đệm nút giả (p.14). Chỉ luồng tĩnh; dữ liệu từ solver (p.16). Không phải điều khiển.

**Liên quan: useful.** Đề xuất: không đưa vector OD độ dài N vào encoder nếu còn muốn chuyển mạng; ý tưởng cạnh ảo gợi ý thêm kết nối đường dài (mục tổng hợp).

### 6. Liu & Meidani 2024b, HSTGSN (background)

**Trích dẫn.** Tong Liu, Hadi Meidani. "Heterogeneous Graph Sequence Neural Networks for Dynamic Traffic Assignment". arXiv:2408.04131v1, 7/8/2024, **preprint** (p.1).

**Kiến trúc, dữ liệu.** Encoder-decoder không-thời gian với cạnh OD (p.2-5). Ground truth DTALite, 8 giờ, gộp 5 phút, 97 bước (p.6). 1000 mẫu mỗi mạng, 100 epoch, lr 0.001, 3 seed (p.6). Số lớp, head, hidden: không nêu trong bài.

**Độ chính xác (flow MAE, utilization MAE, p.7).** Sioux Falls 20.46, 0.94%; Anaheim 43.02, 0.62%; Chicago 6.40, 0.18% (HGT 16.60, 0.86%). Mất 40% OD, Chicago 8.15, 0.19% (p.8).

**Tổng quát hóa.** "Generalization" ở đây chỉ là OD thiếu; **không thử mạng chưa thấy**. Capacity chỉ giảm trong U(0.9, 1.0) (p.6), biên độ hẹp (nhận xét). Bỏ cạnh OD làm lỗi tăng lớn (p.7).

**Liên quan: background.** Bằng chứng duy nhất trong nhóm ở cỡ mạng trên 2000 link, nhưng là supervised.

### 7. Lassen et al. 2025 (useful, nhất là về OOD)

**Trích dẫn.** Lassen, Agriesti, Eldafrawi, Gammelli, Cantelmo, Gentile, Pereira. "Learning traffic flows: Graph Neural Networks for Metamodelling Traffic Assignment". arXiv:2505.11230v1, 16/5/2025, **preprint** (p.1).

**Kiến trúc.** Encoder, MPNN GatedGCN, decoder MLP theo cạnh (p.3-4). 6 lớp, chọn theo **đường kính** Sioux Falls, hidden 64 (p.4). AdamW lr 0.001, 200 epoch, batch 32, early stop (p.4). Ground truth PTV Visum SUE, 10000 mẫu LHS (p.4). Nút thường có feature toàn 0, chỉ 11/24 là centroid (p.4).

**Độ chính xác (giá trị chuẩn hóa, p.5).** GatedGCN MAE 0.02899, R² 0.9521; MLP 0.03077, 0.9481; GCN 0.05931, 0.8061; trung bình 0.06565, 0.7713.

**OOD.** Đổi 10-90% link hoặc nút, vượt tới 25% khoảng huấn luyện, 50 kịch bản mỗi mức (p.4). Capacity: GatedGCN tốt nhất, MAE dưới 0.4 ngay cả khi đổi 90% (p.5-6). Tăng OD: từ 70% cặp OD thì GatedGCN thua trung bình; MLP tốt nhất từ 20% (p.6). Nhận xét: 0.4 so với 0.029 trong phân phối là chênh rất lớn; có thể lỗi đơn vị, phải xem Hình 3. Bài **không thử topology khác** (p.4).

**Giới hạn.** LHS khiến tổng cầu ít đổi, các mô hình học cách chia lại một tổng cố định (p.6). Chỉ thử một mạng nhỏ; tác giả đoán GNN lợi hơn ở mạng lớn (p.6). Không điều khiển; chỉ nói tiềm năng ra quyết định thời gian thực (p.1, p.6).

**Liên quan: useful.** Đề xuất: (a) thêm thử nghiệm tăng cầu tới 25% và giảm capacity lúc đánh giá policy; (b) so GNN với MLP cùng thông tin để chứng minh encoder có giá trị, vì bài cho thấy chênh có thể rất nhỏ.

### 8. Rahman & Hasan, "Data-Driven Traffic Assignment" (background)

**Trích dẫn.** Rahman, Hasan. Tệp ghi 2022; văn bản không có tên tạp chí hay năm (p.1), có thể là bản thảo.

**Kiến trúc.** GCNN 3 lớp: tích chập đồ thị, lớp ánh xạ về N×E, lớp ra tuyến tính; tanh (p.7-8). So random walk, Laplacian, phổ (p.10). Tham số Θ là N×N, Wq gắn với N×E (p.6-8), nên gắn cứng với một mạng (nhận xét).

**Dữ liệu, ngân sách.** UE tĩnh bằng Frank-Wolfe, 5000 ma trận OD mỗi điều kiện, 70/20/10 (p.10, p.12). 10,000 vòng lặp, hội tụ khoảng 2000 (p.19). 19 và 30 phút (p.19).

**Độ chính xác.** Sai số trên luồng trung bình: Sioux Falls 0.338-0.355%, EMA 1.431-1.4575%; R² 0.9991-0.9999 (p.13-14).

**Tổng quát hóa.** Không thử mạng khác. Bài nói không cần giả định hành vi (p.21), nhưng dữ liệu sinh từ UE (p.10); nhận xét: chưa có bằng chứng cho khẳng định đó. Lỗi đánh máy về "uncongested" ở p.11.

**Liên quan: background.** Chỉ trích như công trình đầu của hướng này.

### 9. Lei et al., "Solve routing problems with a residual edge-graph attention neural network" (core cho encoder)

**Trích dẫn.** Lei, Guo, Wang, Wu, Zhao. arXiv:2105.02730v1, 6/5/2021, "Preprint submitted to Elsevier" (p.1). **Tên tệp "GNNAssignment" và năm 2022 gây hiểu lầm**: đây là TSP, CVRP bằng DRL, không phải traffic assignment; văn bản là preprint 2021.

**GNN làm policy encoder: có**, nhưng cho TSP, CVRP tĩnh, không tương tác giao thông.

**Encoder.** Residual E-GAT: attention có cạnh, phương trình 3.5 (p.6); phần dư 3.6 (p.6). 4 lớp, 8 head, dx 128, de 64 (p.14). Đồ thị đủ, tổng trên toàn bộ m nút (p.6-7).

**Decoder.** Theo Kool và PtrNet: ngữ cảnh gồm đồ thị, nút đầu, nút vừa chọn (p.8); mask -∞ cho nút đã thăm; clip tanh C = 10 (p.8-9).

**Huấn luyện.** PPO critic dùng chung encoder (p.9); PPO steps 1, epochs 3, lr 1e-4 đến 3e-4 (p.14); 100 epoch (p.14). Mẹo: chuẩn hóa reward từng mini-batch, annealing lr, orthogonal init, gradient clip 2 (p.10-11). Rollout tốt hơn PPO một chút; PPO dùng nửa dữ liệu (p.15).

**Độ sâu, rất đáng chú ý.** GAT thuần từ 3 lớp trở lên **không hội tụ** ở TSP20, gap 171%, trong khi 1, 2 lớp là 0.86%, 1.09% ở lần chạy đầu (p.19). Thêm phần dư sửa được; E-GAT giảm từ 0.85% xuống 0.06% (p.19). L = 3 tệ nhất trong 3, 4, 5, 6; thời gian epoch 536, 632, 712, 805 s (p.26).

**Kết quả.** TSP100 greedy 3.67%, sampling 1.71% (p.15); AM greedy 4.53% (p.15). CVRP100 greedy 6.68% (p.1). Thời gian epoch TSP20: PN 503 s, AM 525 s, E-GAT 636 s (p.18).

**Tổng quát hóa.** Huấn luyện ngẫu nhiên, test TSPLIB 4.1%, CVRPLIB cỡ nhỏ 6.39%, cỡ vừa 10.45% (p.21). Nhận xét: đó là **chọn tour ngắn nhất trong 100 checkpoint cho từng bài** (p.19), không phải một mô hình, nên 4.1% lạc quan.

**Nhận xét về ngân sách.** Bài khoe "384,000 và 768,000 mẫu" so với hơn 1 triệu của Kool (p.15). Theo p.14, 3000 × 128 = 384,000 là mỗi **epoch** và có 100 epoch, tức khoảng 38.4 triệu (tính lại). Nên không trích "dưới 1 triệu mẫu" (p.21).

**Liên quan: core.** Đề xuất ở mục tổng hợp.

### 10. Kool, van Hoof, Welling 2019 (core cho actor)

**Trích dẫn.** "Attention, Learn to Solve Routing Problems!", ICLR 2019 (p.1).

**Encoder.** N = 3, dh 128, 8 head, FF 512, batch norm, skip (p.3, p.6). N = 3 và 5 tốt nhất; chọn 3 vì chi phí (p.15).

**Decoder và mask.** Ngữ cảnh là [đồ thị, nút vừa qua, nút đầu] (p.4). Một lớp đa head, rồi một lớp 1 head để ra xác suất (p.4). Không hợp lệ thì u = -∞; clip tanh C = 10 **trước khi mask** (p.4). Trên đồ thị thường: đặt -∞ cho nút không kề, tức message passing theo cạnh (p.13). Có thể làm thưa để mở rộng, đây là hướng tương lai, chưa làm (p.9).

**Baseline.** REINFORCE, b(s) là greedy rollout của mô hình tốt nhất; đóng băng trong epoch; thay khi t-test ghép cặp đạt α = 5% trên 10000 bài (p.5). Epoch đầu dùng exponential β = 0.8 (p.6). Rollout thêm khoảng 25% thời gian (p.5). Rollout hơn exponential và critic ở cả AM và PN (p.9).

**Ngân sách.** 2500 batch × 512 × 100 epoch (p.6), khoảng 128 triệu bài (tính lại). Epoch 5:30, 16:20, 27:30 phút cho n = 20, 50, 100 (p.6). lr 1e-4 (p.6). Một seed PCTSP phân kỳ, phải chạy lại (p.6).

**Kết quả.** TSP100 greedy 4.53%, sampling 2.26%; CVRP100 7.34%, 3.72% (p.7).

**Tổng quát hóa.** Test với n khác: dùng được, xấu dần khi xa n huấn luyện (p.15). Chỉ khác kích thước, cùng phân phối; không có mạng thật.

**Giới hạn.** Có ràng buộc không thể xử lý bằng mask đơn giản (p.9).

**Liên quan: core.** Mẫu cho actor của ta. Rollout baseline thì không chuyển thẳng được: bài này có một tác tử và bài toán tĩnh, còn ta có môi trường ngẫu nhiên nhiều tác tử (nhận xét).

### 11. Vinyals, Fortunato, Jaitly 2015 (background)

**Trích dẫn.** "Pointer Networks". Văn bản không ghi nơi đăng; Kool trích là Advances in NIPS, 2015 (Kool p.12).

**Cơ chế.** u = vᵀ tanh(W₁eⱼ + W₂dᵢ), softmax trên các vị trí đầu vào, dùng ngay làm "con trỏ" (p.4). Từ điển đầu ra bằng độ dài đầu vào (p.2, p.4). Chi phí O(n²) (p.3, p.7).

**Mask, baseline.** Mask lúc huấn luyện: không nêu trong bài; với hull và Delaunay, decoder không bị ràng buộc (p.7). Với TSP thì beam search chỉ xét tour hợp lệ khi test; nếu không, với n > 20 thì ít nhất 10% bài không ra tour hợp lệ (p.8). Có giám sát, nên không có baseline RL.

**Ngân sách.** LSTM 1 lớp 256 hoặc 512, SGD lr 1.0, batch 128, 1M cặp (p.6).

**Tổng quát hóa.** Hull, học 5-50: n = 50 69.6%, 100 50.3%, 500 1.3%; diện tích giữ 99.2% trở lên (p.7). TSP, học 5-20: n = 30 4.72 so với A3 4.60; n = 50 7.66 so với 5.79 (p.8). Phụ thuộc thứ tự đầu vào (p.6).

**Liên quan: background.** Trích làm nguồn gốc của "chọn trong tập có kích thước thay đổi". Hỏng khi không mask (p.8) là lý do nên mask lối ra không hợp lệ.

### 12. Veličković et al. 2018, GAT (useful, nguồn cho công thức)

**Trích dẫn.** "Graph Attention Networks", ICLR 2018 (p.1).

**Công thức masked attention (p.3-4).**
- eᵢⱼ = a(W hᵢ, W hⱼ), chỉ tính với j ∈ Nᵢ, gồm cả i (1)
- αᵢⱼ = exp(eᵢⱼ) / Σ_{k∈Nᵢ} exp(eᵢₖ) (2)
- a là một lớp feedforward, LeakyReLU với độ dốc âm 0.2 (3)
- h′ᵢ = σ(Σ_{j∈Nᵢ} αᵢⱼ W hⱼ) (4)
- Đa head nối lại (5), lớp cuối lấy trung bình (6)

**Lân cận thay đổi.** Softmax chuẩn hóa trên Nᵢ, nên kích thước lân cận tùy ý; không cần thứ tự trong lân cận; dùng toàn bộ lân cận, không lấy mẫu cỡ cố định như GraphSAGE (p.5). Đồ thị có hướng: bỏ αᵢⱼ nếu không có cạnh j→i (p.5). Chi phí một head O(|V|FF′ + |E|F′) (p.5). Không cần biết trước toàn đồ thị (p.5).

**Ngân sách, kết quả.** PPI: 3 lớp; K = 4, 256 feature; lớp ra K = 6; skip connection (p.7). F1 0.973 so với Const-GAT 0.934 (p.8) trên 2 đồ thị test chưa thấy (p.6). Cora 83.0%, Citeseer 72.5%, Pubmed 79.0% (p.8).

**Giới hạn.** Không phải giao thông. Tổng quát hóa ở đây là đồ thị protein cùng miền (p.6), không nói gì về mạng đường.

**Liên quan: useful.** Trích cho thiết kế attention trên line graph có hướng, nhất là p.5.

---

## Tổng hợp cho policy của ta (nhận xét, có nguồn)

Không có bài nào trong nhóm kiểm chứng một policy GNN cho điều khiển giao thông động, nên các mục sau là gợi ý để thử, không phải kết luận.

1. **Phần dư.** Kiểm tra GNN 3 lớp của ta có skip connection. Lei cho thấy GAT thuần hỏng từ 3 lớp (p.19); GAT (p.7) và Kool (p.3) đều dùng skip.
2. **Độ sâu.** 3 đến 6 trong các bài: Kool 3 (p.6), Lei 4 (p.14), Liu 4 (p.9), Lassen 6 theo đường kính (p.4). Trên 1828 nút line graph, 3 lớp chỉ thấy 3 hop. Tăng lớp làm thời gian epoch tăng gần tuyến tính (Lei p.26).
3. **Thông tin xa.** Hai bài Liu dùng cạnh ảo OD thay cho nhiều lớp (Liu p.7; Liu b p.2) và bỏ nó làm lỗi tăng lớn (Liu b p.7). Với ta: đưa embedding điểm đến vào query của actor như context của Kool (p.4), hoặc thử thêm token toàn cục; nên diễn giải như một ablation riêng.
4. **Actor.** Khớp với thiết kế attention trên lối ra: mask -∞, clip C = 10, một head cuối (Kool p.4, Lei p.9). Lân cận thay đổi có sẵn nhờ softmax trên Nᵢ (GAT p.3, p.5).
5. **Đặc trưng cạnh.** GCN không có đặc trưng cạnh thua rõ (Lassen p.5); đưa cạnh vào attention có lợi (Lei p.19).
6. **Đối chứng.** So thêm với MLP hoặc encoder rút gọn, vì Lassen thấy chênh rất nhỏ (p.5).
7. **Đánh giá.** Tăng cầu tới 25% và giảm capacity (Lassen p.4). Tổng quát hóa phải có mạng giữ ngoài; Liu không nói rõ điều đó (p.13-15), Lei thì chọn checkpoint theo từng bài (p.19). Đừng lặp lại hai lỗi này.
8. **Khoảng trống để nêu trong bài báo.** Trong nhóm này, GNN cho routing chỉ gặp ở bài tĩnh một tác tử (Kool, Lei) hoặc ở học luồng có giám sát (Liu, Lassen, Rahman). Đây là nhận định trên 8 bài này, không phải trên toàn bộ tài liệu.

---

## Bảng tham số

"KN" = không nêu trong bài. Chen và Chouta không có giá trị hiệu chỉnh nên gộp một cột. Khoảng sweep có nguồn thì ghi trang; khoảng không có nguồn được ghi rõ là **thăm dò**, không được trích như giá trị hiệu chỉnh. Giá trị của Vu là VISSIM, nên chỉ là tương tự.

| Tham số | Ta | Chouta, Chen | Salawavidana | Vu (VISSIM) | Khoảng sweep gợi ý và nguồn |
|---|---|---|---|---|---|
| minGap (m) | 0.5 | KN | 0.1 (p.3) | Standstill 0.5; lưới 0.5, 1, 2 (p.12, p.17) | 0.1, 0.3, 0.5, 1.0: dưới Salawavidana p.3, trên Vu p.12. Ưu tiên cao, núm mạnh nhất (Vu p.20) |
| accel (m/s²) | 2.5 | KN | 6.0 (p.3) | Đường cong đo, số trên Hình 4 (p.11) | 2.5, 4, 6: trên Salawavidana p.3. Đọc Hình 4 của Vu trước |
| decel (m/s²) | 4.5 | KN | 4.5 (p.3) | KN | Giữ 4.5 (Salawavidana p.3) |
| length (m) | 1.9 | KN | 2.0 (p.3) | KN | Giữ |
| width (m) | 0.8 | KN | KN | KN | Giữ; không có nguồn |
| maxSpeed (m/s) | 15 | KN | 16.7 (60 km/h, p.3) | 11.1 cao điểm, 13.9 thấp điểm; lưới 30, 40, 50 km/h (p.12, p.17) | 8.3, 11.1, 13.9, 16.7: Vu p.12, Salawavidana p.3. Ưu tiên thấp ở cao điểm (Vu p.17). Tốc độ trong hẻm: không có nguồn |
| speedDev | 0 | KN | Có chỉnh, số KN (p.2) | Phân phối, số KN | Thăm dò 0, 0.1; không có nguồn về giá trị |
| sigma | 0.5 | KN | KN | KN | Không có nguồn |
| minGapLat (m) | 0.3 | KN | KN | 0.8 cao điểm, 1.0 thấp điểm; lưới 0.6, 0.8, 1.0, ở 50 km/h (p.12, p.17) | 0.1, 0.3, 0.6, 0.8: trên theo Vu p.12, dưới thăm dò. Ưu tiên cao cho hẻm 2.5 m |
| lateral resolution (m) | 0.8 | KN | 0.1 (p.3) | Không áp dụng; Izadi 2 m, bị Vu chê (p.4) | 0.1, 0.4, 0.8: Salawavidana p.3. Đo thêm thời gian chạy; bài không nêu chi phí |
| lcSublane | 1.0 | KN | KN | KN | Không có nguồn |
| lcPushy | 0.5 | KN | KN | KN | Không có nguồn |
| lcStrategic, lcCooperative | Chưa đặt | KN | Có chỉnh, số KN (p.2-3) | KN | Cần hỏi tác giả hoặc đọc nguồn Khulna (Salawavidana p.4) |
| latAlignment | arbitrary | KN | KN | KN | Không có nguồn |
| jmTimegapMinor (s) | 0.5, chỉnh tay | KN | KN | KN | **Không có nguồn trong nhóm.** Thăm dò 0.5, 1.0, 1.5, 2.0, 2.5; biên trên theo con số 2.5 s trong đề bài, chưa có trích dẫn |
| impatience | 0.7, chỉnh tay | KN | KN | KN | **Không có nguồn trong nhóm.** Thăm dò 0, 0.35, 0.7, 1.0 |
| step-length (s) | 0.5 | Chouta 0.1 (p.8), vì roll | KN | KN | Giữ; 0.1 của Chouta phục vụ mục đích khác |
| time-to-teleport (s) | 180 | KN | KN | KN | Không sweep làm tham số hiệu chỉnh; báo cáo số teleport và loại bộ tham số gây tắc (theo Vu p.13) |
| Bề rộng làn (m) | 2.5 giả định | Chen: KN | KN | 3.75 đo (p.9) | Thăm dò 2.0, 2.5, 3.0; không có nguồn cho hẻm |

**Mục tiêu kiểm chứng có thể trích.** MAPE dưới 15%, GEH dưới 5 (Salawavidana p.3). Kiểm định t trên thời gian đi, giữ chiều hoặc giờ khác để kiểm chứng (Vu p.13-15).

**Lưu ý về 2.5 s.** Nhận xét: khoảng trống chấp nhận đo ngoài thực địa và `jmTimegapMinor` không nhất thiết là một đại lượng, nên không gán thẳng 2.5 vào tham số; và không bài nào trong nhóm đưa ra phép ánh xạ đó. Giá trị mặc định SUMO cần tra tài liệu SUMO, không có trong 4 bài này.
