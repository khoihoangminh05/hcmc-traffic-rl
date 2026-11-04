# Ghi chú đọc, nhóm 6: hiệu chỉnh mô phỏng xe máy và tham số SUMO

Bản 2026-11-04. Đọc toàn văn từ văn bản trích từ PDF (`scratchpad/papers_txt/`), không xem hình.

Quy ước:
- `p.N` là trang của **tệp PDF**. Với Lopez, trang in là 2575-2582, tức PDF p.1-8.
- "Nhận xét:" là ý của người đọc. "Tính lại" là phép tính của người đọc từ số trong bài.
- "Không nêu trong bài" nghĩa là không có trong văn bản trích. Số chỉ nằm trên hình thì không đọc được, nên cũng ghi như vậy.
- Giá trị mặc định của SUMO lấy từ tài liệu SUMO trực tuyến, truy cập 2026-11-04 (không có số trang): [vType](https://sumo.dlr.de/docs/Definition_of_Vehicles,_Vehicle_Types,_and_Routes.html), [mặc định theo vClass](https://sumo.dlr.de/docs/Vehicle_Type_Parameter_Defaults.html), [sublane](https://sumo.dlr.de/docs/Simulation/SublaneModel.html), [teleport](https://sumo.dlr.de/docs/Simulation/Why_Vehicles_are_teleporting.html). Tài liệu này mô tả bản mới nhất; phải đối chiếu lại với 1.28.
- Tìm chuỗi trên Fadilah, Ni, Zhou, Lopez: cả 4 bài đều **0 lần** `teleport`, `jmTimegap`, `impatience`, `lcSublane`, `minGapLat`, `speedFactor`.

**Kết luận chính.**
1. **Tệp `Chowdhury_2024_SUMO` là sai bài.** Đó là bài về động cơ điện, không có một chữ nào về giao thông. Giá trị của Khulna chưa thể trích.
2. Không bài nào đọc được cho **giá trị SUMO của `jm*`, `impatience`, `lc*`**. Nguồn gần nhất cho nhập không đèn là Fadilah, trên AIMSUN: gap acceptance 3.0-3.2 s (nguồn thứ cấp) và bảng turn parameter chỉ cho **đường chính** (p.9).
3. Fadilah **có nói mạng của họ gồm hẻm** (p.2, p.16), nên câu "chưa ai định tuyến trên mạng hẻm" không viết được. Nhưng không có tham số, độ rộng hay kết quả riêng cho hẻm, và số link giảm từ 10,065 xuống 1,533 (p.8). Xem mục (c).
4. Khi đối chiếu với mạng của ta, phát hiện hai điểm cần kiểm tra trước khi hiệu chỉnh gì thêm (mục 6): hẻm hai chiều đang là hai lane 2.5 m riêng, và độ phân giải 0.8 m không chia hết 2.5 m.

vType của ta: motorcycle, length 1.9, width 0.8, minGap 0.5, maxSpeed 15 m/s, accel 2.5, decel 4.5, sigma 0.5, speedDev 0, latAlignment arbitrary, minGapLat 0.3, lcSublane 1.0, lcPushy 0.5; lateral resolution 0.8 m, step 0.5 s, time-to-teleport 180 s. Quét tay: impatience 0.7, jmTimegapMinor 0.5.

---

## 1. Chowdhury & Chakraborty 2024: tệp sai, chưa đọc được

**Tệp đang có.** Pallekonda, Ch. "High gain interleaved PFC converter for torque ripple minimization in industrial PMBLDC motor based drives". Results in Engineering 23 (2024) 102413 (p.1). Tìm chuỗi trên cả 13 trang: `SUMO`, `traffic`, `calibrat`, `motorcycle`, `Khulna` đều 0 lần.

**Nguyên nhân.** Danh mục tham khảo của Salawavidana (p.4) in tên đúng nhưng ghi tạp chí và DOI sai: Results in Engineering 23, 102413. `TO_DOWNLOAD.md` dòng 23 chép lại DOI đó. Nên tệp tải về đúng theo DOI nhưng sai bài.

**Bài thật** (OpenAlex, Crossref): Chowdhury, Chakraborty. "Calibration of SUMO Microscopic Simulation for Heterogeneous Traffic Condition: The Case of the City of Khulna, Bangladesh". *Transportation Engineering* 18 (2024) 100281, doi `10.1016/j.treng.2024.100281`, PII `S2666691X24000551`. OpenAlex ghi là gold OA, CC-BY.

**Những gì biết được, chỉ từ tóm tắt qua bản ghi thư mục ([Smart City Gnosys](https://smartcity.efri.uniri.hr/article.php?id=13247)), không có số trang, chưa đọc PDF.** Khu trung tâm Khulna, nút Powerhouse; dữ liệu lưu lượng, hàng đợi, thời gian đi; hiệu chỉnh theo RMSE; sigma 0.3, tau 1.4; channelization giảm thời gian đi khoảng 10-30%. **Không trích các số này trong bài báo cho tới khi đọc PDF.** Tỉ lệ xe máy, phiên bản, tham số sublane, nút giao, teleport: chưa biết.

**Cần làm.** Người dùng tải PDF bài thật. Tôi không tải được: ScienceDirect và DOAJ trả 403, lần thử tải trực tiếp bị bộ phân loại quyền chặn và tôi không thử lại.

**Nhận xét, liên quan.** Nhiều khả năng là nguồn SUMO trực tiếp cho sigma và tau, nên nên đọc trước khi chốt. Hướng tìm thêm: Sashank, Navali, Bhanuprakash 2020, SUMO cho giao thông hỗn hợp Ấn Độ, đoạn 2 km ở Chennai, Springer LNCE 69, doi `10.1007/978-981-15-3742-4_13` (chỉ thấy qua tìm web, tham số chưa rõ).

---

## 2. Fadilah, Nishiuchi, Ngoc 2024 (core): gần ta nhất về bối cảnh

**Trích dẫn.** Raudhatul Fadilah, Nishiuchi, Ngoc. "Identifying the role of route choice behavior of motorcycle riders in microscopic simulation modeling under mixed traffic conditions". Transportation Research Interdisciplinary Perspectives 28 (2024) 101247 (p.1).

**Địa điểm.** Quận Ninh Kiều, Cần Thơ: 29.46 km², 280,494 dân (p.3). Loại đường: trunk 6.87%, secondary 18.48%, tertiary 27.91%, residential 46.74% (p.3). Đơn vị của tỉ lệ này (chiều dài hay số link) không nêu trong bài.

**Tỉ lệ xe.** Trong mô hình: xe máy 91.57%, ô tô 8.43% (p.8). Đếm xe: gần 90% xe máy (p.5). Nhật ký đi lại ở Ninh Kiều: xe máy 87.84%, ô tô 1.57%, đi bộ 5.00%, xe đạp 5.40% (p.5).

**Simulator.** AIMSUN Next 23 (p.3), kèm Python API cho route choice (p.3, p.8). Bước mô phỏng: không nêu trong bài. Số lần lặp, số seed: không nêu trong bài (`seed` 0 lần, `replicat` chỉ theo nghĩa "tái hiện").

**Mạng.** OSM cộng khảo sát đèn (p.3). Trước và sau hiệu chỉnh: link 10,065 → 1,533, nút 3,313 → 519, vùng OD 35 → 42 (p.8). Giảm 84.8% link và 84.3% nút (tính lại). Bài xếp mình vào mạng lớn, trên 100 nút giao (p.2).

**Dữ liệu.**
- Sơ cấp: pha đèn ở 27 nút, ngày 2/3/2024 (p.5). SP 301 người đi xe máy, 28-30/10/2022, mỗi người 8 lựa chọn với VMS giả định (p.5), 2,408 quan sát (p.6).
- Thứ cấp: nhật ký 7 ngày 17-23/2/2020, 5,841 người, 20,518 dòng, 11,465 dòng ở Ninh Kiều (p.5). Đếm video 24 giờ tại 12 nút, gộp 5 phút, 23-25/2/2020 (p.5). Tốc độ từ nhật ký và lấy mẫu tốc độ (p.8).
- OD: bình phương tối thiểu từ nhật ký và đếm xe, 35 vùng trong, 7 vùng ngoài (p.7). Ma trận theo giờ, theo loại xe (p.8).

### 2.1 Tham số hiệu chỉnh

Bảng 4 (p.9). Bài nêu rõ đây chỉ là **ví dụ cho đường chính** (p.9), tham số được chỉnh theo từng loại đường (p.9). **Giá trị cho residential và đường hẹp: không nêu trong bài.**

| Tham số AIMSUN | Đơn vị | Mặc định | Hiệu chỉnh | Gần nhất trong SUMO (nhận xét, không đồng nhất) | Ta |
|---|---|---|---|---|---|
| Initial safety margin | s | 3.00 | 2.00 | `jmTimegapMinor` | 0.5 |
| Final safety margin | s | 1.00 | 0.50 | `jmTimegapMinor` | 0.5 |
| Initial yield time factor | | 1.00 | 0.70 | Không có tương ứng rõ | |
| Final yield time factor | | 2.00 | 1.30 | Không có tương ứng rõ | |
| Visibility to yield | m | 30 | 20 | `visibility` của connection, cần kiểm tra | Chưa đặt |
| Visibility along main stream | m | 60 | 40 | Như trên | Chưa đặt |
| Look-ahead distance | m | 300 | 250 | Không rõ | |
| Critical look-ahead distance | m | 40 | 25 | Không rõ | |
| Reaction time, ô tô | s | 0.80 | 0.62 | | |
| Reaction time, xe máy | s | 0.45 | 0.44 | Bằng step khi chưa dùng action step (Lopez p.7) | Step 0.5 |
| Lateral clearance, ô tô | m | 0.50 | 0.40 | `minGapLat` | |
| Lateral clearance, xe máy | m | 0.50 | **0.30** | `minGapLat` | **0.3** |

Nguồn khác về gap acceptance mà bài dựa vào (p.9), **nguồn thứ cấp, phải đọc bài gốc trước khi trích**:

| Nơi | Ô tô | Xe máy | Nguồn trong bài (p.9) |
|---|---|---|---|
| Malaysia | 3.7 s | 3.2 s | Ibrahim & Sanik 2007, nút chữ T không đèn (p.17) |
| Ấn Độ | 3.65 s | 3.0 s | Patil & Sangole 2016, nút chữ T không đèn, ưu tiên hạn chế (p.17) |
| Anh | 7.1 s | | Robbins et al. 2018 |
| Mỹ | 7.6 s | | Tupper 2011 |

Bài không nói bảng 4 đã suy ra từ các số này thế nào. Bài chọn Malaysia vì thành phần xe giống (p.9).

**Phương pháp, khoảng tìm.** Thử và sai lặp lại (p.9), so bằng GEH (p.4). Khoảng tìm: không nêu trong bài. Tiêu chí dừng ngoài GEH: không nêu trong bài. Kích thước xe giữ mặc định (p.7), giá trị không nêu trong bài. Non-lane-based bật có mô tả nhưng tham số không nêu (p.9). Tương đương `sigma`, `speedFactor`: phân phối tốc độ chỉ có trên Hình 9 (p.9).

**Teleport.** Không nêu trong bài. Bài có nhắc mô hình đổi làn liều có thể tạo giảm tốc vượt khả năng thực (p.9), và không nói có xử lý tắc mạng hay không.

### 2.2 Chọn tuyến và tuân thủ

**Mô hình.** Recursive Logit (Fosgerau 2013), ước lượng trong R với BFGS (p.5), từ SP. Tiện ích (p.6, phương trình 5): v = −1.582 LL − 0.039 TT − 5.304 TF, với TF là v/c. Dấu trừ mất khi trích văn bản; bài nói các hệ số có dấu kỳ vọng (p.6).

| Biến | Hệ số | t | p (p.6) |
|---|---|---|---|
| Link length | 1.582 (âm) | 8.625 | 0.000 |
| Travel time | 0.039 (âm) | 2.290 | 0.022 |
| Traffic flow conditions | 5.304 (âm) | 57.800 | 0.000 |

LL₀ 9506.175 và LLβ 4224.296 (giá trị tuyệt đối, dấu mất khi trích), ρ² 0.556, ρ̄² 0.555 (p.6). **Bề rộng đường, nút có đèn, tổng trễ không có ý nghĩa nên bị loại** (p.6). 35.6% đổi tuyến theo VMS giả định (p.6). Đơn vị của LL và TT, scale μ: không nêu trong bài.

**Cách đưa vào mô phỏng.** Trước chuyến đi: đường ngắn nhất. Trên đường: dữ liệu thời gian thực kích hoạt đổi tuyến bằng SRC (p.8); giả mã p.8. DTA dùng SRC và DUE (p.8). **Chu kỳ cập nhật thông tin, độ trễ, scaleFactor, cách gán xe tuân thủ: không nêu trong bài.**

**Kịch bản thông tin (p.4).** S0: không có thông tin, pre-trip đường ngắn nhất. S1: VMS trên trunk và secondary. S2: tin về trunk và secondary, ai cũng nhận được. S3: tin về mọi đường, ai cũng nhận được.

**Tuân thủ.** 0-100%, bước 25%, thêm 35.6% (p.4, p.13). Quét riêng xe máy, ô tô giữ 30% (p.14), dựa vào các tỉ lệ cũ: tới 40%, 30%, 6-41%, 50%, 16.9% và 65.4% (p.14).

### 2.3 Kết quả số

**Kiểm chứng toàn mạng, 8 giờ (p.10).**

| Chỉ số | Đo | Mô phỏng | GEH |
|---|---|---|---|
| Tốc độ ô tô (km/h) | 23.97 | 25.26 | 0.26 |
| Tốc độ xe máy (km/h) | 24.19 | 24.39 | 0.04 |
| Lưu lượng ô tô | 35,837 | 36,120 | 1.49 |
| Lưu lượng xe máy | 350,415 | 353,373 | 4.99 |

**Kiểm chứng tại nút (p.10).** R² 0.74, RMSE 293.21, MAE 153.86, PCC 0.86. 60.56% điểm có GEH dưới 5, 39.44% từ 5 đến 10, không điểm nào trên 10.

**Pre-trip so với en-route (Bảng 7, p.15).**

| Chỉ số | Đường ngắn nhất | Route choice en-route |
|---|---|---|
| R² | 0.58 | 0.74 |
| RMSE | 372.48 | 293.21 |
| MAE | 192.44 | 153.86 |
| PCC | 0.76 | 0.86 |

**MFD.** Bài đổi sang MEU và area occupancy (p.4-5). S0 đạt đỉnh 614.99 MEU/h lúc 07:10, ở 16.39% diện tích chiếm dụng (p.10). Lưu lượng 6-7 giờ tăng 146.37% (p.10).

| Kịch bản | Đỉnh (MEU/h) | Lúc | Trang | So với S0 (tính lại) |
|---|---|---|---|---|
| S0 | 614.99 | 07:10 | p.10 | |
| S1 | 1031.66 | 07:15 | p.11 | +67.8% |
| S2 | 990.27 | 07:20 | p.12 | +61.0% |
| S3 | 1132.03 | 07:35 | p.12 | +84.1% |

| Tuân thủ | Xe máy và ô tô cùng đổi (MEU/h) | Ô tô 30%, xe máy đổi | Chênh (p.15) |
|---|---|---|---|
| 0% | 615.7 | 655.0 | 6.37% |
| 25% | 884.7 | 892.9 | 0.93% |
| 35.6% | 986.8 | 921.6 | 6.60% |
| 50% | 1068.4 | 984.0 | 7.89% |
| 75% | 1085.0 | 1023.4 | 5.68% |
| 100% | 1133.0 | 1088.0 | 3.97% |

Tăng từ 35.6% lên 50%, 75%, 100%: 8.27%, 9.92%, 14.81% (p.13). Tính lại ra 8.27%, 9.96%, 14.82%, số thứ hai lệch nhẹ. Từ 0 lên 100%: 84% (p.14). Chênh trung bình 5.24% (p.14). Vòng trễ biến mất khi có thông tin (p.16). Tổng thời gian đi, trễ, quãng đường theo kịch bản: chỉ trên Hình 15; không nêu số trong văn bản.

### 2.4 Giới hạn

**Tác giả nêu (p.16).** Hành vi cá thể phải xấp xỉ; hiệu chỉnh tốn công; không phân tích hành vi ô tô; một MFD cho cả quận bỏ qua khác biệt không gian. Dữ liệu không được chia sẻ (p.16).

**Nhận xét của người đọc.**
- **84% đo đỉnh của một đại lượng trung bình có trọng số độ dài trên chuỗi 5 phút (p.4, p.10), không phải số chuyến hoàn thành.** Đỉnh còn lùi từ 07:10 sang 07:35. Tôi không kết luận được tổng thời gian có giảm hay không: chữ của p.12 lại nói quãng đường và thời gian đi **tăng**, đồng thời "dài hơn nhưng nhanh hơn".
- **Baseline mâu thuẫn.** S0 là "existing" (p.10) nhưng cũng là đường ngắn nhất pre-trip (p.4), đúng cấu hình mà p.15 gọi là chưa hiệu chỉnh, R² 0.58. Mô hình khớp dữ liệu là en-route, R² 0.74. Vậy 84% đo từ một baseline chính tác giả cho là khớp kém hơn. p.12 còn gọi S0 "có lẽ" là UE, trong khi đường ngắn nhất pre-trip không phải UE.
- **Kiểm chứng không độc lập.** Đếm tại 12 nút vừa dùng ước lượng OD (p.7) vừa dùng kiểm chứng (p.10, p.14).
- **GEH bị dùng rộng.** GEH áp cho tốc độ (p.10), và cho tổng 8 giờ, nơi 4.99 chỉ vừa dưới ngưỡng. 60.56% dưới 5 được gọi là chính xác cao (p.10), trong khi Lopez nêu mức điển hình là hơn 85% số đếm lệch dưới 15% (Lopez p.6, tiêu chí khác dạng).
- **Không thấy lặp.** Không có khoảng tin cậy nào. Một đỉnh trên 1 chuỗi mô phỏng là thống kê cực trị, nhạy với nhiễu.
- **35.6% là ý định khai báo trước VMS giả định**, không phải đo tuân thủ, nhưng phần kết gọi là tỉ lệ quan sát (p.16).
- **Điểm lạ trong bài.** Thu nhập khảo sát ghi bằng IDR, 55.81% lặp ở hai dòng (p.5); định nghĩa production và accumulation ở p.4 bị đảo so với p.10; p.15-16 tham chiếu Hình 10, 11 cho MFD nhưng MFD là Hình 12, 13. Không suy ra gì, chỉ ghi để cẩn thận khi trích. 74.65% "local và residential" (p.10) đúng bằng tertiary cộng residential (tính lại).

**Hẻm, đường hẹp.** Có nói: "narrow shortcuts and alleys" (p.2, p.16); đường hẹp chiếm ưu thế (p.3); dữ liệu Google Maps thiếu cho đường nhỏ (p.3). Không có: độ rộng, tốc độ, năng lực, turn parameter hay kết quả theo hẻm; danh sách lớp đường sau khi cắt còn 1,533 link. Nhận xét: tỉ lệ 46.74% residential (p.3) không chứng minh residential vẫn còn trong mạng chạy thật, vì 84.8% link đã bị cắt (p.8).

### 2.5 Gần ta đến đâu

| Tiêu chí | Fadilah | Ta |
|---|---|---|
| Nơi | Ninh Kiều, Cần Thơ (p.3) | Quận 4, TP.HCM |
| Xe | Xe máy 91.57%, ô tô 8.43% (p.8) | Chỉ xe máy |
| Simulator | AIMSUN Next 23 (p.3) | SUMO 1.28, sublane |
| Mạng | 519 nút, 1,533 link, 29.46 km² (p.3, p.8) | 886 nút, 1,828 cạnh có hướng |
| Tỉ phần hẻm | Không nêu trong bài | 1,460 của 1,828 cạnh (79.9%), 25.35 của 34.44 km (73.6%) (tính từ `quan4_v4.net.xml`) |
| Điều khiển | Không; thông tin, mỗi xe tự tối đa tiện ích (p.14) | Next-hop học được, MARL |
| Mục tiêu | Đỉnh MFD (p.11-12) | J, T_all, T_cust |
| Đèn | Đo 27 nút (p.5) | 3 nút, static của netconvert |
| Lặp, held-out | Không nêu trong bài | Seed 60000+, khoảng tin cậy ghép cặp |

**Tóm lại**: gần nhất về nơi và thành phần xe, cũng là cách đặt câu hỏi "cung cấp thông tin thì mạng được gì". Nó **không** phải đối thủ về phương pháp vì không tối ưu, không học. Nó là nguồn trích được cho thông số Việt Nam và là bài bắt buộc phải nhắc đến.

### 2.6 Đề xuất

1. Trích **lateral clearance 0.30 m** (p.9) làm nguồn tương tự cho `minGapLat` 0.3; ghi rõ AIMSUN, đường chính, thử và sai.
2. Đọc Patil & Sangole 2016 và Ibrahim & Sanik 2007 (p.17), đều là nút chữ T. **Đây là đầu mối tốt nhất cho chỗ nghẽn của ta.** Tải thêm.
3. Dùng 30% và 35.6% (p.6, p.14) để biện minh cho khoảng quét tỉ lệ xe nền có rerouting, nhưng ghi rõ device của SUMO không phải tuân thủ.
4. So sánh 90% tuân thủ của đội xe ta với 35.6% (p.6): hai bối cảnh khác nhau (đội xe nhận điều phối và VMS tự nguyện), nhưng nên có một kịch bản tuân thủ thấp.
5. Bề rộng đường không có ý nghĩa trong RL (p.6): chỉ cho thấy khảo sát này không tách được, **không** nên hiểu là bề rộng không quan trọng.
6. Không lấy đỉnh MFD làm chỉ số chính. Báo chuyến hoàn thành và thời gian, có lặp.
7. Baseline ta phải là cấu hình khớp nhất với dữ liệu, tránh mâu thuẫn S0.

---

## 3. Ni, Li, Yuan, Sun 2023 (useful): e-moped, không phải xe máy

**Trích dẫn.** "An operational simulation framework for modelling the multi-interaction of two-wheelers on mixed-traffic road segments". Physica A 611 (2023) 128441, online 28/12/2022 (p.1). Tên tệp ghi 2022.

**Địa điểm, xe.** Đoạn 110 m × 9.8 m ở Thượng Hải; làn xe đạp 2.8 m, làn xe 3.5 m; cách nút 40 m nên hạn chế ảnh hưởng đèn; giới hạn ô tô 50 km/h (p.14). Lưu lượng hai bánh 700-900 xe/h, xe cơ giới 400-500 xe/h (p.14). Video 16:00-17:00, 20/4/2017, độ phân giải 0.065-0.125 m/pixel (p.14). 1,256 quỹ đạo hai bánh (1,050 e-moped và e-bike, 206 xe đạp), 548 xe cơ giới (p.14); 29,591 frame, 0.12 s (p.15). 407 đoạn following, 170 đoạn overtaking (p.15). Theo số quỹ đạo: e-moped và e-bike 58.2%, xe đạp 11.4%, xe cơ giới 30.4% của 1,804 (tính lại); **không có xe máy xăng** (p.14). Không có nút giao.

**Simulator.** Tự viết trên MATLAB, không dùng SUMO (p.19). Bước 0.12 s (p.19). Comfort Zone, Bayesian network, behaviour force trên social force (p.7-13). Không giả định làn (p.7).

**Thống kê đo (Bảng 2, p.15).**

| | Tốc độ TB (m/s) | SD | 15%, 85% | Headway TB (s) | SD | 15%, 85% | Lateral clearance TB | SD | 15%, 85% |
|---|---|---|---|---|---|---|---|---|---|
| E-bike, e-moped | 7.2010 | 1.8797 | 5.4672, 9.0751 | 1.1002 | 0.4192 | 0.6755, 1.4549 | 0.1942 | 0.0721 | 0.1237, 0.2671 |
| Xe đạp | 4.5220 | 1.4567 | 3.0713, 6.0887 | 1.6229 | 0.6044 | 1.0223, 2.2058 | 0.2773 | 0.1089 | 0.1517, 0.3886 |

Lateral clearance là khoảng ngang chia tốc độ mong muốn (p.15), nên đơn vị là giây, **không phải mét**. Nhân lại với 9.08 m/s ra khoảng 1.76 m (tính lại), nhưng điểm đo (tâm tới tâm hay mép tới mép) không nêu trong bài, nên không dùng làm `minGapLat`.

**Tham số hiệu chỉnh (Bảng 5, p.18).**

| Tham số | E-bike, e-moped | Xe đạp | Loại | So với ta |
|---|---|---|---|---|
| Desired speed vd (85%) | 9.08 m/s | 6.09 m/s | Đo | maxSpeed 15 |
| Relaxation τd | 5.06 s | 3.41 s | GA | |
| Max accel/decel am | 1.17 m/s² | 0.55 m/s² | GA | accel 2.5 |
| Comfortable decel bf | 0.94 m/s² | 0.43 m/s² | GA | decel 4.5, khác nghĩa |
| Jam gap s0 | 1.14 m | 0.72 m | GA | minGap 0.5 |
| Headway Td | 1.50 s | 1.96 s | GA | tau, chưa đặt |
| δe | 4.00 | 4.00 | GA | |
| Repulsive A, B với xe đạp | 0.42, 6.43 | | GA | Không tương ứng |
| Repulsive A, B với e-moped | 0.76, 7.11 | | GA | Không tương ứng |
| Repulsive A, B với xe cơ giới | 1.63, 9.31 | | GA | Không tương ứng |
| Shy-away khi vượt | 0.5 m | | Lấy từ nguồn khác (p.11) | minGapLat 0.3 |
| Hệ số kích thước Sm | E-moped 1.6 | Xe đạp và e-bike 1.2 | Theo diện tích mặt cắt (p.11); xe cơ giới 3.6 | |

Comfort zone (Bảng 3, p.16): `a`: α₁ 5.4190, α₂ −0.3064, β₁ 0.2914, δ₁ −2.0870, R² 0.4145, RMSE 0.3929. `b`: α₃ 4.3510, α₄ −0.0038, β₃ 1.9300, δ₂ 0.1027, R² 0.4541, RMSE 0.0556. St: 2.5 cho e-moped, 3.1 cho xe đạp. β₂, β₄ gán −1.

Mọi `jm*`, `lc*`, `sigma`, `speedFactor`, lateral resolution, teleport: không nêu trong bài.

**Phương pháp.** Curve fitting MATLAB cho CZ (p.16). K2 và EM cho BN, chia dữ liệu khoảng 1:1 (p.17-18). GA: mục tiêu RMSPE tốc độ trung bình, quần thể 200, 500 thế hệ, stall 100, dung sai 1e-6, lặp 10 lần, chọn tốt nhất (p.18). **Khoảng tìm và RMSPE cuối: không nêu trong bài.**

**Kiểm chứng.**
- BN: 94.57% train, 94.59% test (p.17), 94.58% toàn bộ (p.18). Free moving 98.13%, following 84.14%, overtaking 83.70% ở test (p.17).
- Vượt: 156/170, 91.76% (p.20); theo bước thời gian 5148/6170, 83.44% (p.21).
- Thời gian đi: đo 17.6336 s (SD 5.7727), mô phỏng 17.7526 s (SD 5.6105). ACT: 7.5765 s (SD 3.0129), 7.9031 s (SD 3.2314) (p.22). Lệch +0.7%, +4.3% (tính lại).
- Lặp: 20 lần mỗi mật độ, 3600 s, bỏ 2000 bước đầu và cuối (p.19). Đường cơ bản chỉ trên Hình 18 (p.23); so sánh định tính với tài liệu (p.22).

**Giới hạn tác giả nêu (p.23-24).** Cần thêm thuộc tính cho CZ, chưa chứng minh dạng ellipse, chưa xét dự đoán của người lái, chưa thử mật độ cao, ngược chiều. Dữ liệu không chia sẻ (p.24).

**Nhận xét.**
- Kiểm chứng là "face validation" với bối cảnh giao thông **lấy từ quan sát**, mô phỏng từng xe một (p.19). Không kiểm được hành vi tập thể hay tắc.
- Chia 1:1 theo frame của cùng các quỹ đạo (p.17), nên test không độc lập. Luôn đoán free moving đã đạt 75.4% ở test (tính lại, 11155/14795), nên 94.59% bớt ấn tượng.
- R² của comfort zone chỉ 0.41-0.45 (p.16).
- Td 1.50 s sau GA khác headway đo 1.10 s (p.15, p.18), cho thấy tham số GA khó xem là số đo hành vi.
- Mô hình đắt và chỉ cho đoạn thẳng, không dùng được ở mạng.

**Hẻm, đường hẹp.** Không áp dụng trực tiếp: đường 9.8 m, đầu vào thưa, tác giả nói muốn thử mật độ cao sau (p.23). Không có nút giao.

**Liên quan: useful.** Đề xuất: (a) dùng headway 0.68-1.45 s (p.15) làm khoảng cho `tau`; (b) CV tốc độ 0.26 (tính lại, 1.8797/7.2010, p.15) làm **cận trên** của `speedDev`, vì trong đó có cả ảnh hưởng tương tác; (c) s0 1.14 m (p.18) làm biên trên cho `minGap`; (d) 0.5 m shy-away (p.11) là một điểm cho `minGapLat`; (e) ghi rõ là e-moped, chưa phải xe máy xăng. Bài cũng cho thấy kiểu GA + RMSPE tốc độ là cách hiệu chỉnh lặp lại được, phù hợp với lời khuyên của Lopez (p.6).

---

## 4. Zhou & Gayah 2023 (useful về thiết kế, không phải về vi mô)

**Trích dẫn.** "Scalable multi-region perimeter metering control for urban networks: A multi-agent deep reinforcement learning approach". Transportation Research Part C 148 (2023) 104033 (p.1).

**Quy mô thật.** 7 vùng, 24 bộ điều khiển trên 12 cặp vùng, nên **12 agent**, mỗi agent 4 hành động (p.6, p.11). Môi trường là **phương trình MFD số**, không có xe riêng lẻ (p.12), chuyển sang vi mô là việc tương lai (p.23). Không có khái niệm link. Tác giả nói đây là mạng perimeter lớn nhất từng xét (p.11), nhưng "scalable" ở đây là 12 agent, không so được với mạng 1,828 cạnh của ta (nhận xét).

**Môi trường (p.12).** MFD Yokohama, n_c 8,240 xe, n_jam 34,000 xe, mỗi vùng co giãn ±10%; C_max 4.6 xe/s, α 0.48; Δt 60 s, 2 giờ, tức 120 bước (tính lại); u 0.1 và 0.9. Vùng 4 khởi đầu 8,750 xe, các vùng khác 3,850 (p.12). Chọn tuyến **ngoại sinh**: softmax theo thời gian đi của đường ngắn nhất, **giống nhau ở mọi phương pháp** (p.5). Policy không chọn tuyến.

**Reward.** Số chuyến hoàn thành mỗi bước, chuẩn hóa về [0, 1] bằng một hằng số lớn, cộng **phạt âm lớn khi gridlock** (p.6). Chung cho mọi agent, để tránh credit assignment (p.6). Giá trị hằng số và mức phạt: không nêu trong bài. Không clip reward. **Chỉ lưu transition có reward > 0.1** (p.11).

**Thuật toán (p.9-11).** QMIX, Double DQN, Ape-X, chia sẻ tham số. Agent: một lớp 64 ReLU, ra 4 (p.11). Tham số chỉ cập nhật nếu loss giảm (p.11). Siêu tham số chọn bằng random search (p.11).

| Siêu tham số (Bảng 2, p.11) | Giá trị |
|---|---|
| Vòng lặp, generator | 250, 6 |
| Replay, batch | 10,000, 1,000 |
| ε đầu, decay, cuối | 0.90, 0.98, 0.01 |
| Số lần cập nhật mỗi vòng | 5 |
| lr đầu, decay, min | 0.003, 0.95, 0.0001 |
| γ | 0.8 |
| Chu kỳ target | 10 |

Tổng tối đa 250 × 6 × 120 = 180,000 transition chung (tính lại, trước khi lọc).

**Baseline.** NC (không điều khiển) làm cận dưới; MPC đủ thông tin, control horizon 2, prediction horizon 3 (p.12-13). 5 seed huấn luyện (p.13), 10 seed khi chuyển giao (p.21). Lý do chọn horizon ngắn: horizon dài chưa chắc tốt hơn vì khó tìm tối ưu toàn cục (p.13).

**Kết quả.** Chỉ có trên hình; **giá trị CTC: không nêu trong bài**. Định tính: ngang MPC, đôi khi hơn nhẹ (p.14). Nhiễu δ 0-60: vẫn tương đương MPC (p.15-16). Sai số n_c ±20%: thua MPC khi ≥ +20% (p.20). Chuyển giao σ, λ ∈ {0, 0.1, 0.2}: hơn MPC (p.21). Nhiễu chưa thấy: hơn MPC khi δ ≤ 28 (p.22). Huấn luyện khoảng 3 lần thời gian áp dụng MPC (p.23). Phần cứng: không nêu trong bài, "không ảnh hưởng tới kết quả" (p.11).

**Giới hạn tác giả nêu.** Chưa phân tích lý thuyết, chưa vi mô, chưa thử số vùng lớn hơn (p.11, p.23). Chỉ đánh giá chuyển giao trong cùng thiết lập; không xét số vùng khác, cầu buổi chiều hay đóng đường (p.22).

**Nhận xét.**
- p.16: với NC, chỉ báo **trung bình các lần chạy không gridlock**. Đây là cách báo cáo chọn mẫu, làm baseline trông tốt hơn; ta không được làm tương tự với teleport.
- Lọc reward > 0.1 và chỉ cập nhật khi loss giảm khiến dữ liệu lệch; bài không đo ảnh hưởng.
- Bài nói random search "không gây overfit" (p.11) mà không có bằng chứng; kết quả chính (p.13) đánh giá trên chính kịch bản đã train.
- Lập luận "policy-based chỉ cho hành động đổi dần" (p.6-7) không áp dụng cho actor categorical của ta.

**Hẻm, teleport, tham số SUMO.** Không có.

**Liên quan: useful, thiết kế.** Đề xuất: (a) giữ kiểu thí nghiệm train sạch rồi thử nhiễu chưa thấy (p.21-22) khi đo độ bền của ta, kể cả trên các bộ tham số SUMO ở mục (b); (b) so với baseline có đầy đủ thông tin mô hình, vì cả MPC cũng có thể thua (p.14) nên cận đó phải kiểm chứng, không giả định; (c) route choice giống nhau cho mọi phương pháp (p.5) ủng hộ quy tắc công bằng của ta; (d) **không** chép phạt gridlock (p.6), vì trái với quyết định không phạt tay của dự án; (e) không xem bài này là bằng chứng scalable cho next-hop.

---

## 5. Lopez et al. 2018 (bắt buộc trích cho SUMO)

**Trích dẫn.** Lopez, Behrisch, Bieker-Walz, Erdmann, Flötteröd, Hilbrich, Lücken, Rummel, Wagner, Wießner. "Microscopic Traffic Simulation using SUMO". 21st IEEE ITSC, Maui, 2018, in 2575-2582 (p.1). Kịch bản minh họa: Bologna (p.2). Phiên bản tổng thể: không nêu trong bài; chỉ nêu ballistic từ 0.28, action point từ 0.32 (p.7).

**Tham số xe máy, `jm*`, `lc*`, `sigma`, teleport.** Không nêu trong bài. Từ `motorcycle` không có; từ `teleport` không có. Không dùng bài này làm nguồn teleport; phải dùng tài liệu SUMO.

**Điều trích được.**

| Nội dung | Trang |
|---|---|
| Tool mở, EPL v2, hơn 35,000 lượt tải mỗi năm | p.1 |
| Mô hình ngẫu nhiên nên chạy nhiều lần rồi kết luận thống kê | p.1 |
| Width, speed, quyền truy cập là hằng số dọc lane | p.2 |
| netconvert suy luận đèn, quyền ưu tiên, hình học khi nhập OSM | p.3 |
| Thiếu chi tiết mạng là khó khăn thường gặp | p.3 |
| UE, SUE và fastest route khi gán lộ trình | p.3 |
| Cadyts hiệu chỉnh route choice theo đếm xe | p.4-5 |
| Calibrator thêm hoặc bớt xe; tránh tắc ảo bằng cách bỏ xe | p.5 |
| Dùng RMSE, không có nhiều lợi ích khi dùng thước đo phức tạp hơn | p.6 |
| Sai số gap 10-20% là điển hình; mạng: hơn 85% số đếm lệch dưới 15% | p.6 |
| **Khuyên mạnh không hiệu chỉnh tay** vì khó lặp lại; nên dùng bộ tối thiểu phi tuyến | p.6 |
| Kiểm tra so với Fundamental Diagram trong HCM và HBS | p.6 |
| Euler và ballistic: hiệu chỉnh phụ thuộc vào scheme, nhất là với Δt lớn | p.7 |
| Thời gian phản ứng mặc định bằng step, action step tách được | p.7 |
| **Sublane**: giao thông không đồng nhất, kỷ luật làn thấp, độ phân giải cấu hình được, vượt trong một lane, giữ khoảng ngang, virtual lane | p.7 |
| **Vượt qua lane ngược chiều chưa tương thích với sublane** (năm 2018) | p.7 |
| TraCI | p.7 |

**Giới hạn.** Là bài tổng quan, không có kiểm chứng định lượng cho hành vi xe máy hay sublane. Hình 3 (p.6) là đối sánh đếm xe Bologna, không có số trong văn bản.

**Hẻm.** Không có. Nhận xét: mô tả sublane trong bài chỉ một đoạn, không trích dẫn nguồn (p.7). Nên trích thêm bài gốc về lane change của Erdmann khi viết phần phương pháp; chưa kiểm tra chi tiết nên phải tải về rồi mới dùng.

**Liên quan: bắt buộc.** Câu p.6 về hiệu chỉnh tay áp dụng thẳng vào `impatience=0.7`, `jmTimegapMinor=0.5` hiện nay: không được gọi đó là hiệu chỉnh.

---

## 6. Hai điểm trên mạng của ta cần kiểm tra trước (nhận xét, không phải từ bài báo)

Đọc `sumo-env/networks/v4/quan4_v4.net.xml` và `ml-core/routing2/sumo_net.py`, chưa sửa gì.

1. **Hẻm hai chiều đang là hai lane 2.5 m riêng.** Cả 1,460 cạnh hẻm đều có cạnh ngược chiều, mỗi cạnh một lane rộng 2.50 m. Nếu 2.5 m là bề rộng **cả hẻm** thì mô phỏng đang có 5.0 m mặt đường và không có xung đột ngược chiều. Biến `WIDTH_PER_LANE` cho thấy có thể chủ đích là mỗi lane, nhưng đề bài ghi bề rộng hẻm 2.5 m và không có số đo. Điều này có thể khiến **thân hẻm không nghẽn, và phần trễ dồn về chỗ nhập** chỉ vì năng lực hẻm bị thổi lên. Chưa đo, đây là giả thuyết. SUMO 2018 cũng không cho sublane đi cùng vượt ngược chiều (Lopez p.7), nên không có cách sửa rẻ bằng cùng một lane chia hai chiều; có thể thử 1.25 m mỗi chiều như một kịch bản nhạy. Phải kiểm lại trên 1.28.
2. **Độ phân giải 0.8 m không chia hết 2.5 m.** Tài liệu SUMO khuyên chọn giá trị chia đều bề rộng lane, phần dư nằm ở sublane trái cùng, và giá trị phải đủ nhỏ cho xe hẹp nhất. Theo quy tắc đó, 2.5/0.8 cho 3 sublane 0.8 m và một sublane 0.1 m (tính lại). Lựa chọn hợp lệ hơn: 0.833 (3 sublane, nhưng chỉ dư 0.033 m so với xe 0.8), 0.625 (4), 0.5 (5). Các loại đường khác có bề rộng 3.2, 4.0, 3.5, 3.0 nên một giá trị chung không chia đều hết được; đo ảnh hưởng thay vì chỉ lý luận.
3. **Ghi chú trong code "khoảng ba xe ngang hàng" chưa khớp với `minGapLat` 0.3.** Tính lại: 2 xe cần 2×0.8 + 0.3 = 1.9 m, 3 xe cần 3×0.8 + 2×0.3 = 3.0 m, lớn hơn 2.5 m. Muốn 3 xe trong 2.5 m thì `minGapLat` ≤ 0.05 m. `lcPushy` 0.5 có thể làm chúng chen lấn hơn; phải đo.
4. **Mặc định của SUMO khác rất xa setup.** `motorcycle` trong tài liệu có length 2.2, width 0.9, minGap 2.5, accel 6, decel 10, maxSpeed 200 km/h, speedDev 0.1; `minGapLat` 0.6; `lcPushy` 0; `jmTimegapMinor` 1; `impatience` 0. Điều này cũng đáng chú ý cho Salawavidana (nhóm 4): accel 6.0 trong "bảng hiệu chỉnh" của họ **trùng mặc định SUMO**, nên có thể không phải giá trị đã chỉnh. Không nên dùng làm biên "có nguồn" mà không kèm lưu ý này.
5. **Đèn.** Mạng có 3 nút `traffic_light` theo chương trình tĩnh của netconvert (chu kỳ 60 s, theo docstring), Fadilah đo 27 nút cho 29.46 km² (p.5). Ta không biết thực tế Quận 4 có bao nhiêu nút đèn trong vùng; `fetch_osm_signals` chỉ biết OSM. Đặt vào giới hạn của bài.

---

## (a) Bảng tham số cập nhật

KN = không nêu trong bài. "Tài liệu" là tài liệu SUMO trực tuyến, không có trang. Salawavidana và Vu là số đã đọc ở nhóm 4 (trang theo nhóm 4). Khulna: chưa đọc PDF, không trích được. Giá trị AIMSUN, VISSIM và Ni chỉ là tương tự, không cùng định nghĩa.

| Tham số | Ta | Fadilah (AIMSUN) | Ni (e-moped) | Salawavidana (SUMO) | Vu (VISSIM) | Zhou, Lopez | Mặc định (tài liệu) | Khoảng quét và nguồn | Có nguồn không? |
|---|---|---|---|---|---|---|---|---|---|
| jmTimegapMinor (s) | 0.5, chọn tay | Tương tự: final margin 0.50, initial 2.00 (p.9); gap 3.0-3.2 thứ cấp (p.9) | KN | KN | KN | KN | 1 | 0.25, 0.5, 1, 1.5, 2: trên từ initial margin Fadilah p.9, giữa từ tài liệu; 0.25 thăm dò | **Không có nguồn SUMO**. Chọn qua gap mô phỏng, mục (b) bước 4 |
| impatience | 0.7, chọn tay | KN. Yield factor 0.70 (p.9) **không phải** impatience, trùng số | KN | KN | KN | KN | 0 | 0, 0.35, 0.7, 1 | **Không có nguồn nào** |
| jmIgnoreFoeProb, jmIgnoreFoeSpeed, jmIgnoreJunctionFoeProb | Chưa đặt | KN; có nói xe máy lách qua khe nhỏ (p.9) | KN | KN | KN | KN | 0, 0, 0 | 0, 0.1, 0.3 với speed ≤ 2 m/s | **Không có nguồn**, thăm dò |
| jmDriveAfterRedTime | Chưa đặt | Rẽ phải khi đỏ thường gặp (p.5), không có số | KN | KN | KN | KN | −1 | −1, 2 | **Không có nguồn số**. Ưu tiên thấp, chỉ 3 đèn |
| jmSigmaMinor | Chưa đặt | KN | KN | KN | KN | KN | Bằng sigma | Theo sigma | **Không có nguồn** |
| Visibility | Chưa đặt | 20 m, 40 m (đường chính, p.9) | KN | KN | KN | KN | Cần kiểm tra | Chỉ thăm dò 4.5, 20 | Tương tự yếu, cần xem ý nghĩa trên 1.28 |
| sigma | 0.5 | Phân phối trên hình (p.9) | Thành phần ngẫu nhiên ξ, KN (p.13) | KN | KN | KN | 0.5 | 0.3, 0.5, 0.7: dưới từ Khulna **khi đọc xong**; trên thăm dò | Chờ Khulna |
| tau (s) | Chưa đặt | Reaction 0.44 (p.9) | Headway đo 0.68-1.45, TB 1.10 (p.15); Td 1.50 (p.18) | KN | KN | KN | Cần kiểm tra | 0.7, 1.0, 1.45: Ni p.15 | Có, e-moped; Khulna 1.4 chờ đọc |
| speedFactor, speedDev | 1, 0 | Trên hình (p.9) | CV 0.26, tính lại (p.15), cận trên | Có chỉnh, số KN (nhóm 4) | Phân phối, số KN | KN | 1, 0.1 | 0, 0.1, 0.26 | Có, cận trên; **giá trị 0 hiện tại không có nguồn** |
| minGapLat (m) | 0.3 | **0.30** (mặc định 0.50, p.9) | Shy-away 0.5 (p.11) | KN | 0.8, 1.0 ở 50 km/h; lưới 0.6, 0.8, 1.0 (p.12, p.17) | KN | 0.6 | 0.1, 0.3, 0.5, 0.8: Fadilah p.9, Ni p.11, Vu p.17; 0.1 thăm dò | Có (tương tự). Ưu tiên cao |
| lateral resolution (m) | 0.8 | Non-lane-based, KN (p.9) | Liên tục (p.7) | 0.1 (p.3) | Không áp dụng; Izadi 2 m bị chê (p.4) | Lopez: cấu hình được (p.7) | Xem mục 6 | 0.1, 0.5, 0.625, 0.833: Salawavidana p.3, tài liệu | Có. **0.8 hiện tại trái khuyến nghị chia đều** |
| lcSublane | 1.0 | KN | KN | KN | KN | KN | 1.0 | 0.5, 1, 2 | **Không có nguồn**, thăm dò |
| lcPushy | 0.5 | Định tính: đổi làn liều (p.9) | KN | KN | KN | KN | 0, thang 0-1 | 0, 0.25, 0.5, 1 | **Không có nguồn số** |
| lcAssertive, lcImpatience | Chưa đặt | Định tính (p.9) | KN | KN | KN | KN | 1, 0 | Thăm dò nếu Morris cho thấy nhạy | **Không có nguồn** |
| lcStrategic, lcCooperative | Chưa đặt | KN | KN | Có chỉnh, số KN (p.2-3) | KN | KN | 1, 1 | Đọc Khulna trước | **Không có số** |
| latAlignment | arbitrary | KN | Dạt trái thực nghiệm (p.14, p.21) | KN | KN | KN | center | arbitrary, compact, nice | **Không có nguồn** |
| maxSpeedLat (m/s) | Chưa đặt | KN | KN | KN | KN | KN | 1.0 | 1, 2 | **Không có nguồn** |
| minGap (m) | 0.5 | KN | s0 1.14; xe đạp 0.72 (p.18) | 0.1 (p.3) | Standstill 0.5; lưới 0.5, 1, 2 (p.12, p.17) | KN | 2.5 | 0.1, 0.3, 0.5, 1.14: Salawavidana p.3, Vu p.17, Ni p.18. Nhạy nhất ở Vu (p.20) | Có |
| accel (m/s²) | 2.5 | KN | 1.17 (p.18) | 6.0 (p.3), trùng mặc định | Đường cong, số trên hình (p.11) | KN | 6 | 1.17, 2.5, 4, 6 | Có, cần lưu ý mục 6 |
| decel (m/s²) | 4.5 | KN | Comfortable 0.94 (p.18) | 4.5 (p.3) | KN | KN | 10 | Giữ 4.5, thử 3 | Có |
| length, width (m) | 1.9, 0.8 | Mặc định, số KN (p.7) | KN | 2.0, KN (p.3) | KN | KN | 2.2, 0.9 | Giữ; có thể thử 2.2, 0.9 của tài liệu | Length có; width chỉ tài liệu |
| maxSpeed (m/s) | 15 | TB mạng 24.39 km/h, tức 6.78 m/s tính lại (p.9) | vd 9.08, TB 7.20 (p.15, p.18) | 16.7 (p.3) | 11.1, 13.9 (p.17) | KN | 55.6 | 9, 11, 15, 16.7. Giới hạn thật do lane speed | Có. Hẻm thì lane speed quyết định |
| Tốc độ hẻm (m/s) | 4.5, Mapbox | Không theo lớp, KN | KN | KN | KN | KN | | 3.5, 4.5, 5.5 | **Không có nguồn học thuật cho hẻm**; số Mapbox là prior |
| Bề rộng hẻm (m) | 2.5 mỗi chiều (mục 6) | KN; loại khỏi RL vì không có ý nghĩa (p.6) | Làn 2.8 m (p.14), không phải hẻm | KN | 3.75 (p.9) | KN | | 1.25, 1.5, 2.0, 2.5, 3.0 mỗi chiều | **Không có nguồn**; đo mẫu nếu được |
| step-length (s) | 0.5 | KN | 0.12 (p.19) | KN | KN | Lopez: phụ thuộc scheme (p.7) | | 0.25, 0.5, sau khi chốt; ghi rõ Euler hay ballistic | Có về nguyên tắc |
| time-to-teleport (s) | 180 | KN | KN | KN | KN | Lopez KN; Vu loại bộ gây tắc (nhóm 4) | 300 | 180, 600, −1, báo cáo cả ba. Không hiệu chỉnh | **Không có nguồn**; xem (b) |
| Xe nền có rerouting | 30% | 35.6% SP (p.6), ô tô 30% (p.14); dải 6-65.4% (p.14) | KN | KN | KN | Zhou: softmax chung (p.5) | | 0, 30, 35.6, 50, 100 | Có (tương tự), device không phải tuân thủ |
| Phần còn lại của xe nền | Free flow | Pre-trip đường ngắn nhất là S0, R² 0.58 (p.15) | KN | KN | KN | Lopez: UE, SUE, fastest (p.3) | | Free flow, SUE từ duarouter | Có nguồn cho câu hỏi; không có giá trị |

**Giới hạn kiểm chứng có thể trích.** GEH < 5, MAPE < 15% (Salawavidana p.3); hơn 85% số đếm lệch dưới 15%, RMSE (Lopez p.6); 10-20% sai số gap (Lopez p.6). Fadilah đạt 60.56% với GEH < 5 (p.10), không nên lấy đó làm mức đủ.

---

## (b) Quy trình chọn tham số, chỉ dùng dữ liệu miễn phí (đề xuất, chưa chạy)

Mọi bước dưới dùng baseline ff, app, greedy; **không tốn train**. Chỉ có bước 7 tốn train nếu chọn huấn luyện lại, khoảng 20 giờ mỗi run ở mức gần nhất dự án đã ghi cho MAPPO (`CLAUDE.md`, v3v); thời gian của v6 cần đo trên sol1. Số lần chạy và thời gian SUMO của bước 4-6 **chưa đo**, phải thử 1 lượt để ước lượng.

**Thứ tự.**

1. **Đóng băng series.** Đổi tham số là một series mới; không đổi giữa các run theo quy tắc của dự án. Kết quả v6 hiện tại được ghi là sinh ra trên cấu hình chọn tay.
2. **Sửa lớp mạng trước, không dùng tham số hành vi bù sai số hình học** (mục 6): chốt nghĩa của 2.5 m; đo xem trễ có còn dồn ở chỗ nhập hay không khi dùng 1.25, 1.5, 2.5 m mỗi chiều; chọn resolution hợp lệ; ghi rõ Euler hay ballistic vì hiệu chỉnh phụ thuộc scheme (Lopez p.7).
3. **Lấy bề rộng hẻm từ nguồn miễn phí.** Lấy mẫu phân tầng khoảng 30-50 hẻm bằng ảnh đường phố, ảnh vệ tinh, hoặc đo tại chỗ. Nếu không có thời gian thì giữ giả định và ghi là giả định.
4. **Neo nút giao bằng thí nghiệm riêng** (chỗ bài báo còn thiếu nhất). Dựng một nhập chữ T đơn lẻ hẻm vào đường cấp ba, cho lưu lượng chính có kiểm soát, và **đo khoảng trống chấp nhận sinh ra trong SUMO** với từng tổ hợp `jmTimegapMinor`, `impatience`, `jmIgnore*`. So với 3.0-3.2 s (Fadilah p.9), sau khi đọc Patil & Sangole và Ibrahim & Sanik. Không gán thẳng 3 s vào `jmTimegapMinor` vì hai đại lượng khác nhau. Loại tổ hợp nào gây tắc cục bộ hay gap ngoài khoảng đã chọn. Phần này là **chuyển giao** từ Ấn Độ và Malaysia, không gọi là hiệu chỉnh Quận 4.
5. **Sàng lọc bằng Morris, rồi quét.** Khoảng ở bảng (a). Morris trên khoảng 12 tham số, 10 quỹ đạo, 5 seed: khoảng 650 run (tính lại). Tiếp theo cho 4 tham số nhạy nhất, LHS 40 điểm, 5 seed, khoảng 200 run; 5 ứng viên 40 seed, khoảng 200 run, theo cách của Vu (nhóm 4, p.12-13). Không tinh chỉnh bằng tay (Lopez p.6). Dùng bộ tối ưu tự động nếu cần, như GA ở Ni (p.18), hoặc SPSA, BO đã có trong `PLAN_V4`.
6. **Hiệu chỉnh mức tổng hợp với dữ liệu thật mà ta có.**
   - Mục tiêu: RMSE tốc độ theo cạnh và giờ của Mapbox (Lopez p.6) **trên cạnh không phải hẻm**, vì Mapbox hầu như không có tín hiệu ùn trong hẻm (`congestion` 0% ở hẻm và "live" gần trùng hồ sơ lịch sử theo `PLAN_V4`).
   - Biến: tỉ lệ cầu cộng 1-2 tham số cung từ bước 5. Cầu và cung không tách được nếu chỉ có tốc độ, nên nói rõ đây là một nghiệm trong nhiều nghiệm và báo cáo tập nghiệm chấp nhận được, không chỉ một điểm.
   - Giữ lại: ngày hoặc giờ khác, chiều khác, như Vu (nhóm 4, p.14-15). Ngưỡng: MAPE < 15% (Salawavidana p.3). Không dùng GEH cho tốc độ.
   - Có thêm camera miễn phí thì dùng đếm xe với GEH cho đường chính; cẩn thận độc lập, không dùng cùng số đếm để ước lượng OD và kiểm chứng, tránh lỗi của Fadilah (p.7, p.10).
7. **Đánh giá chính sách trên họ tham số, không trên một điểm.** Chọn 3-5 bộ chấp nhận được, trải đều năng lực thấp đến cao. Đánh giá `eval_heldout` trên seed 60000+ ghép cặp. Báo **thứ hạng và chênh lệch** với baseline tốt nhất trên từng bộ. Lợi thế chỉ có ý nghĩa khi vượt mức nhiễu 3-4% đã đo trong `PLAN_V4`. Nếu thứ hạng đảo, phải nói. Train trên một bộ, test trên các bộ còn lại, như Zhou (p.21-22); train lại chỉ khi kết quả cho thấy đáng.

**Được nói gì trong bài.**

| Mức | Nội dung | Cách viết |
|---|---|---|
| Đo được, dữ liệu mở | Topology OSM, chiều dài; bề rộng nếu bước 3 làm được | "đo, lấy từ OSM" |
| Hiệu chỉnh | Tỉ lệ cầu và các tham số qua được bước 6, chỉ với tốc độ Mapbox trên đường không phải hẻm | "hiệu chỉnh tổng hợp theo tốc độ, kiểm trên dữ liệu giữ lại; đây không phải hiệu chỉnh hành vi vi mô" |
| Chuyển giao | Gap acceptance từ T-junction Ấn Độ, Malaysia; lateral clearance 0.30 m từ Ninh Kiều | "chọn sao cho phù hợp với số đo từ nơi khác; chưa kiểm ở Quận 4" |
| Chỉ độ nhạy | `impatience`, `jm*` khác, `lc*`, `sigma`, `tau`, `speedDev`, bề rộng hẻm nếu chưa đo, tốc độ hẻm, tỉ lệ xe nền, teleport | "không có nguồn; báo cáo khoảng" |
| Không được nói | "SUMO đã được hiệu chỉnh cho hẻm" hay gọi `impatience=0.7`, `jmTimegapMinor=0.5` là đã hiệu chỉnh | Dữ liệu miễn phí không nhìn thấy hành vi nhập hẻm. Camera cũng không thấy trong hẻm (`CLAUDE.md`) |

Một phần đo miễn phí làm được và sẽ nâng hẳn độ tin cậy: **vài giờ video điện thoại tự quay tại 3-5 điểm nhập hẻm**, đếm gap chấp nhận và thời gian vượt nút. Khi đó nút nhập chuyển từ "chuyển giao" sang "đo trực tiếp, cỡ mẫu nhỏ". Đây là lựa chọn của người dùng.

**Báo cáo teleport trung thực.**

Không bài nào trong nhóm có quy tắc nào: 0 lần `teleport` ở cả 4 bài đọc được. Tài liệu SUMO cho biết xe bị teleport biến khỏi mạng, đi tiếp theo tuyến với tốc độ trung bình của cạnh, rồi chèn lại khi có chỗ. Và lý do `yield` là kẹt ở nhánh ưu tiên thấp không tìm được gap, chính là chỗ nhập của ta. Nên time-to-teleport 180 **bớt đi đúng phần trễ đang muốn đo**.

Số trong `PLAN_V4`: từ 180 lên 600, ff tăng 485.84 → 543.22 (+11.8%), app 489.74 → 573.34 (+17.1%) (tính lại). App ngang ff ở 180 và thua ff 5.5% ở 600 (tính lại). Argmax update 125, 4 seed 50000+ (cũng là seed chọn checkpoint): `attrib` 482.65 → 527.29, tới đích 0.974; `selfish` 471.91 → 566.13, tới đích 0.942; khoảng tin cậy so với ff ở 600 rất rộng (`attrib` −17.19 đến 20.10). `selfish` hơn `attrib` ở 180 nhưng thua ở 600. Argmax `attrib` update 75 là 638.47, tới đích 0.897. Tức cả **thứ hạng** cũng phụ thuộc vào teleport.

Đề xuất:
1. Kết quả chính báo ở time-to-teleport **600 hoặc lớn hơn**; 180 chỉ để đối chiếu. Thử thêm −1 (tắt) để biết có gridlock vĩnh viễn hay không; khi đó phải có trần thời gian rõ ràng.
2. Cân nhắc **train lại ở 600**, vì policy hiện train ở 180. Việc này tốn khoảng một run đầy đủ cho mỗi cấu hình, và nên đo xem trần `train_mean_tt_s` 900 s có còn đủ.
3. Với mọi controller, báo: teleport trên 1000 chuyến **theo lý do** (`yield`, `jam`, `wrong lane`, `blocked`) và theo vị trí (phần ở chỗ nhập hẻm); tỉ lệ tới đích; số xe chưa xong lúc hết giờ.
4. Báo J theo **hai biên**: (a) tính theo số SUMO; (b) phạt công bằng cho chuyến có teleport, ví dụ cộng thời gian ở trạng thái teleport đo được, hoặc chạy `--time-to-teleport.remove` để lấy tỉ lệ tới đích sạch. Cùng cách cho mọi controller. **Không** thêm vào reward; đây chỉ là chỉ số đánh giá, nên không trái quyết định "không phạt tay".
5. Xử lý chuyến chưa xong như **dữ liệu bị cắt**. Tỉ lệ tới đích khác nhau thì J chỉ tính xe xong sẽ thiên lệch, có lợi cho controller để nhiều xe kẹt. Dùng trung bình có giới hạn đến cùng một trần thời gian, trên cùng tập chuyến. Kiểm tra `--tripinfo-output.write-unfinished`, `--statistic-output` trên 1.28.
6. **Không** loại run gridlock khi lấy trung bình (Zhou p.16 làm vậy với NC). Báo mọi run.
7. Dùng teleport để **loại bộ tham số** ở bước 5, như Vu (nhóm 4, p.13). Ngưỡng phải chọn trước khi xem kết quả policy.
8. Không biện minh teleport là "xe máy lách qua tắc". Có thể đúng một phần nhưng không có nguồn nào. Muốn mô hình điều đó thì dùng `jmIgnore*` hoặc `lcPushy` và đặt vào phần độ nhạy.

---

## (c) Câu "chưa ai định tuyến trên mạng hẻm mô hình tường minh" mạnh đến đâu

**Ở dạng rộng này: không viết được.** Fadilah nói thẳng mô hình của họ có đường từ trục chính tới "narrow shortcuts and alleys" (p.2, nhắc lại p.16), dùng OSM (p.3, p.7), có mô hình chọn tuyến theo link (p.5-6), với tin tức trên mọi loại đường (p.4). Phản biện chỉ cần trích p.2. `gap_checks.md` dòng 36 ghi "không nói về hẻm" do chỉ đọc tóm tắt, **cần sửa**.

**Nhưng Fadilah không chứng minh rằng hẻm được mô hình tường minh.**

| Bằng chứng | Trang |
|---|---|
| Từ `alley` chỉ xuất hiện 2 lần, cả hai ở câu mô tả độ phức tạp | p.2, p.16 |
| Link giảm 84.8% (tính lại) khi hiệu chỉnh, từ 10,065 còn 1,533; lớp nào bị bỏ không nêu | p.8 |
| Turn parameter chỉ công bố cho đường chính | p.9 |
| Bề rộng đường bị loại khỏi route choice | p.6 |
| Không có bề rộng, năng lực, tốc độ hay kết quả theo hẻm | Không nêu trong bài |
| Đếm kiểm chứng chỉ ở 12 nút chính | p.5, p.10 |
| Hình thức so sánh chỉ có MFD toàn quận; tác giả tự nhận bỏ qua khác biệt không gian | p.16 |
| Dữ liệu không chia sẻ, không kiểm được | p.16 |
| Không tối ưu, không học, không đội xe; xe đi theo tiện ích riêng | p.14 |

Các bài khác trong nhóm không phản bác hơn: Ni là đoạn 9.8 m, Zhou là phương trình MFD, Lopez là công cụ; tệp Chowdhury sai nên **chưa biết** Khulna có đường hẹp hay không (tóm tắt chỉ nói CBD, chưa đọc); nhóm 4 đều là đường lớn. Hai bài Jakarta trong `gap_checks.md` nhắc xe máy dùng đường hẹp làm đường tắt nhưng chỉ đọc tóm tắt.

**Có thể bảo vệ (mức trung bình, dựa trên tìm kiếm có giới hạn):**

> Trong các công trình tìm được, mô phỏng lớn nhất cho giao thông đa số xe máy ở Việt Nam (Fadilah et al., 2024) có nhắc đường hẹp và hẻm trong phân cấp đường, nhưng không công bố tham số hay kết quả riêng cho chúng và không tối ưu điều phối. Theo hiểu biết của chúng tôi, chưa có công trình nào điều phối đội xe bằng chính sách học được trên một mạng mà các cạnh hẻm được mô hình riêng, có bề rộng và hành vi nhập được nêu rõ.

**Điều làm câu trên còn yếu.**
1. Hẻm của ta cũng **chưa được hiệu chỉnh và bề rộng là giả định**, cộng thêm vấn đề mục 6. Không được chê Fadilah về điểm mà ta cũng chưa có. Lợi thế thực của ta: công khai giả định, 79.9% cạnh là hẻm (tính lại), báo độ nhạy.
2. Chỉ một bài Việt Nam đã đọc toàn văn; tìm bằng tiếng Việt ở `gap_checks.md` không thấy bài học thuật nhưng chưa phải tìm hệ thống; luận văn trong nước chưa vào được.
3. Bài trước của chính nhóm Fadilah (dòng "Fadilah et al., 2024", p.5) chưa đọc; có thể cho biết thêm về mô hình và đường nhỏ. Tên đầy đủ không có trong danh mục tham khảo của bài này.
4. Google Maps có chế độ xe máy qua ngõ (`gap_checks.md`, tài liệu xám), nên dẫn đường qua hẻm **đã có trong thực tế**. Điểm mới chỉ nằm ở tối ưu toàn hệ và phương pháp công khai.

---

## Việc tiếp theo ngoài nhóm này

- Sửa `TO_DOWNLOAD.md` dòng 23 sang `10.1016/j.treng.2024.100281` và tải lại PDF.
- Sửa `gap_checks.md` dòng 36: Fadilah có nhắc hẻm (p.2, p.16).
- Ghi chú nhóm 4, đề xuất (a) cho Salawavidana: accel 6.0 trùng mặc định SUMO.
- Tải thêm: Patil & Sangole 2016 (IATSS Research 40(1), 7-18), Ibrahim & Sanik 2007, Fadilah et al. 2024 (bài SP), Sashank et al. 2020.
- Người dùng quyết định: nghĩa của 2.5 m, có đo bề rộng hoặc quay video chỗ nhập không, có train lại ở time-to-teleport 600 không.
