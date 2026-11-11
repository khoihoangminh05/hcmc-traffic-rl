# Kế hoạch cuối: từ dữ liệu thật đến train MAPPO trên Quận 4

## Context

Mục tiêu: bài Q1 (TR-C / T-ITS) về điều phối đội xe bằng MAPPO trên mạng đường và hẻm Quận 4, chỉ dùng dữ liệu miễn phí. So đủ ff, app (kiểu Google Maps), greedy_load, IPPO, MAPPO; không làm yếu heuristic. Đóng góp gồm thuật toán, pipeline bản sao số và bộ dữ liệu.

Vì sao phải lập lại kế hoạch. Mấy ngày qua hỏng vì bốn lỗi của cách làm:
1. So baseline, tính UE–SO và train trên mô phỏng chưa khớp thực tế (3 lần). Các kết quả `msa13–15`, `k1–k5`, `v10–v13` đều không dùng được.
2. Luôn thử trên cả mạng, nên khi sai không biết sai ở đâu. Chưa bao giờ kiểm riêng một đoạn đường hay một nút.
3. Đoán nhu cầu chỉ từ tốc độ, trong khi chưa có số đo lượng xe.
4. Nhiều số là tự đặt (bề rộng, chu kỳ đèn, tỉ lệ ô tô) và chưa từng đối chiếu.

Thay đổi chính so với 7 bước hôm trước:
- **Định nghĩa bài toán lên đầu**, vì nó quyết định cần dữ liệu gì và mô phỏng phải chính xác tới đâu.
- **Kiểm mô phỏng từ nhỏ đến lớn:** đoạn đường → nút → trục → cả mạng.
- **Chọn SUMO hay tự viết bằng phép đo ở mức đoạn và nút**, không tranh luận.

Đã chốt với người dùng (2026-11-08):
- Bỏ SUMO meso.
- Hẻm: không đo thực địa. Tìm dataset và bài báo; không có thì giả định, ghi rõ, chạy trên khoảng giá trị.
- Xe máy: thử dữ liệu công khai trước.
- 100–200 xe là **đội xe được điều phối**, chạy giữa dòng xe nền đã hiệu chỉnh.

## Luật làm việc

- Một luồng việc. Chưa qua cổng thì không sang giai đoạn sau, kể cả khi máy rảnh.
- Trước cổng G2 không so chính sách, không tính UE–SO, không train.
- Mỗi con số gắn nhãn: **đo được / lấy mẫu / từ tài liệu / giả định**.
- Mỗi chỗ mô phỏng lệch: mở số đo hoặc ảnh thật, tìm nguyên nhân rồi mới sửa. Không vặn tham số cho khớp số.
- Tách dữ liệu hiệu chỉnh và kiểm tra (ngày khác, đoạn khác). Báo cả kết quả thất bại.

## Giai đoạn 0: định nghĩa bài toán (1 ngày, chỉ viết tài liệu)

Viết `.docs/PROBLEM_DEF.md`, chốt:
- **Ai điều phối:** một nhà vận hành đội xe (kiểu app giao hàng hoặc gọi xe), 100–200 xe, chính sách chung, thực thi phân tán từng xe.
- **Đầu vào của mỗi xe:** điểm đến, vị trí, các cạnh ra có thể chọn; thời gian đi gần đây do đội xe báo về (có trễ, có mất mẫu); số xe trong đội trên các cạnh quanh đó và ý định của chúng. Không dùng dữ liệu xe nền mà thực tế không đo được.
- **Đầu ra:** cạnh kế tiếp tại mỗi nút quyết định; tài xế tuân theo với xác suất cho trước.
- **Đồng bộ thời gian:** quyết định bất đồng bộ theo sự kiện (xe sắp tới nút); báo cáo trạng thái theo chu kỳ, ví dụ 10 s. Trễ và mất mẫu nằm trong mô hình.
- **Mục tiêu:** J = 0.5·T_all + 0.5·T_cust, CVaR25, tỉ lệ không hoàn thành; ràng buộc đi vòng.
- **Luận điểm cần kiểm:** greedy mạnh ở đa số trường hợp; MAPPO ổn định hơn ở kịch bản xấu; lợi thế ở hẻm thông ra đường chính. Đây là giả thuyết, chưa phải kết quả.
- **Mô phỏng phải đạt tới đâu:** các cổng G1, G2 bên dưới.

## Giai đoạn 1: dữ liệu (đến khoảng 20/11, chạy song song với giai đoạn 2)

| Hạng mục | Cách làm | Nhãn dự kiến |
|---|---|---|
| Cấm rẽ | Đưa 131 relation OSM vào netconvert | đo được |
| Số làn trục chính | Đối chiếu OSM với ảnh 22 camera | đo được |
| Bề rộng đường lớn | Đo trên ảnh camera / vệ tinh theo mẫu | lấy mẫu |
| Bề rộng và mật độ hẻm | Tìm dataset, bài báo (TP.HCM, Hà Nội, Đông Nam Á); không có thì giả định dải 1–2.5 m mỗi chiều | từ tài liệu / giả định |
| Chu kỳ đèn | Chuỗi ảnh 20 s (đã đặt lịch 9–13/11): đọc chu kỳ từ nhịp xả hàng chờ ở các nút có camera; nút khác dùng phân bố đo được | đo được / suy rộng |
| Mật độ ô tô theo giờ, thứ | Camera mỗi 5 phút trong vùng mặt đường (`roi_q4.json`), chỉnh theo đếm tay | đo được |
| Mật độ xe máy | Tìm dataset xe máy công khai, huấn luyện trên GPU 1, đo trên ít nhất 50 ảnh camera đếm tay | đo được nếu đạt |
| Tốc độ theo giờ | Mapbox: 5–21h, ngày thường, khúc 300 m; bổ sung phần chưa phủ nếu cần | đo được (ô tô) |
| Đặc tính giao thông VN | Bài báo về xe máy: quy đổi PCU, sơ đồ cơ bản, chấp nhận khe hở, tỉ lệ vượt đèn; đo tỉ lệ vượt đèn trên chuỗi ảnh nếu nhìn được | từ tài liệu / đo được |

Đầu ra: `.docs/DATA_REGISTER.md`, mỗi thông số một dòng gồm giá trị, nguồn, nhãn, sai số.

**Cổng G0:** đếm xe máy sai số trung vị ≤ 30% trên ảnh ban ngày và chạng vạng; đủ 2 tuần camera (1 tuần hiệu chỉnh, 1 tuần kiểm tra); mọi thông số có nhãn. Không đạt phần xe máy thì dùng hình dạng theo giờ trên từng camera và ghi giới hạn.

## Giai đoạn 2: mô phỏng, kiểm từ nhỏ đến lớn

Khu thử chứa code: `ml-core/routing2/validate/` (mới).

**L1 – Một đoạn đường.** Đoạn đường thẳng có dòng xe trộn. So quan hệ mật độ–tốc độ–lưu lượng với số đo ở camera (mật độ) ghép Mapbox (tốc độ), và với tài liệu xe máy.
**L2 – Một nút.** Nút có đèn, có xe vượt đèn; nút không đèn với xe chen khe; hẻm nhập ra đường chính. So lưu lượng xả và thời gian chờ. Phải không có kẹt chết do mô hình.

**Chọn công cụ sau L1–L2 (giới hạn 3–4 ngày cho SUMO):** thử SUMO micro có sublane, tham số kiểu lái VN (`SumoEnvConfig.moto_extra`). Dùng SUMO nếu đạt cả ba: sơ đồ cơ bản lệch ≤ 15%, không kẹt chết ở nút, và một episode nhắm tới đủ nhanh để train (≤ 5 phút). Không đạt thì **tự viết mô phỏng**: mô hình chiếm dụng diện tích (xe máy không theo làn, tốc độ theo diện tích bị chiếm), nút có chen khe, vượt đèn, sự cố. Viết lại trên nền `routing2/meso_gpu.py`, `routing2/graph.py`, `routing2/demand.py`, nhưng hiệu chỉnh theo **số đo thật**, không theo SUMO. Lần trước meso này hỏng vì độ trễ gần 0 khi chưa bão hòa, nên L2 phải kiểm đúng điểm đó. Theo số đo hiện có, SUMO khó đạt tiêu chí tốc độ; nếu tự viết, SUMO micro vẫn giữ vai trò kiểm chứng độc lập trên một phần kịch bản.

**Cổng G1:** L1 và L2 đạt trên công cụ đã chọn.

**L3 – Một trục** (Khánh Hội hoặc Nguyễn Tất Thành): khớp tốc độ và mật độ theo giờ, lưu lượng đầu vào lấy từ camera.

**L4 – Cả mạng, 5–21h, nhu cầu biến thiên theo giờ.** Luồng cổng và cầu từ camera; nhu cầu nội quận từ phân bố dân cư và hẻm; ô tô nội quận theo số đo. Ước lượng OD theo từng giờ. Xe nền có hành vi vào hẻm không điều phối, vượt đèn, tai nạn. Chỗ nào lệch: mở ảnh thật tại đó.

**Cổng G2 (nửa kiểm tra, ngày khác):**
- Spearman theo khúc 300 m, từng giờ cao điểm: ≥ 0.5 toàn bộ, ≥ 0.4 trong đường lớn (trần dữ liệu 0.74).
- TTI theo lớp đường lệch ≤ 15% (primary 1.67, secondary 1.47, tertiary 1.33 ở 17–18h).
- Sai số phần trăm tuyệt đối trung vị của tốc độ khúc đường ≤ 20%.
- Mật độ và tỉ lệ ô tô tại camera khớp thứ hạng ≥ 0.5.
- Chạy thêm thời gian xả xe; xe kẹt không tới đích ≤ 2%; teleport ≤ 1/1000.

Đã làm hết mà chưa đạt: báo số, người dùng quyết định dừng ở mức nào. Giữ 3–5 cấu hình tốt nhất làm **tập mô phỏng E**, kèm dải giả định của hẻm.

## Giai đoạn 3: tìm điểm yếu và kiểm còn đất (chỉ sau G2)

- Baseline ở dạng mạnh nhất, tinh chỉnh trên seed 40000+: ff, app, app_history, greedy_load.
- Trên đội 100–200 xe: tìm kịch bản greedy và app thua; đo cơ chế (dồn đường, đổi đường, chờ ở hẻm thông).
- Cận phối hợp: sửa `routing2/gate_msa.py` trước khi dùng: so trung bình các vòng đã hội tụ, đánh giá trên nhu cầu khác; bỏ cách so vòng cuối với vòng tốt nhất. Thêm oracle chia luồng cho riêng đội xe.
- **Cận tối ưu bằng luồng chi phí nhỏ nhất (chốt 2026-11-11):**
  - Chia luồng tối ưu cho riêng đội xe trên mạng mở rộng theo thời gian. Thời gian đi mỗi cạnh lấy từ mô phỏng đã qua G2, với xe nền giữ cố định; ràng buộc năng lực cạnh từ đo L1/L2.
  - Dùng hai vai: (1) cận để đo khoảng cách của greedy và MAPPO trong G3; (2) baseline phối hợp tập trung, giải lại vài phút một lần.
  - Gọi greedy_load đúng tên trong tài liệu: định tuyến tham lam có tính tải, gần với gán dòng tăng dần và định tuyến lại phản ứng.
  - Chỉ cài đặt và chạy sau G2.

**Cổng G3:** khoảng cách từ greedy tới cận ≥ 5% ở CVaR25 hoặc trung bình, trên ít nhất 10 seed. Dưới 3%: báo người dùng trước khi train; bài chuyển trọng tâm sang pipeline và dữ liệu.

## Lớp độ tin cậy của môi trường (người dùng đề xuất, 2026-11-09)

Ý tưởng: mỗi thông số chưa chắc của môi trường (đèn, hẻm, mật độ đường chính) có giá trị, khoảng và mức tin cậy. Đoàn xe khi chạy đóng vai cảm biến, thu hẹp dần các khoảng đó. Việc này không nhằm làm MAPPO mạnh hơn; nó là đóng góp của pipeline. **Không thay thế và không làm chậm việc hoàn thiện bản đồ, môi trường, mô phỏng.**

**Mức tin cậy** (cột trong `DATA_REGISTER.md`): A đo nhiều ngày và qua kiểm tra chéo; B đo một ngày hoặc một khung giờ; C suy rộng hoặc từ tài liệu; D giả định.

**Cách dùng trong mô phỏng:** mỗi episode lấy "sự thật ẩn" từ khoảng của từng thông số. Mức thấp thì khoảng rộng. Tập E vì vậy phản ánh đúng chỗ ta chưa biết.

**Đoàn xe đo được gì:**

| Thông số | Xe đội quan sát | Kỳ vọng |
|---|---|---|
| Chu kỳ, pha đèn | Thời điểm các xe rời vạch sau khi dừng, gấp theo chu kỳ, theo khung giờ | Tốt ở nút có nhiều lượt qua |
| Tốc độ hẻm, mức cản | Thời gian đi hết hẻm | Trực tiếp, chỉ ở hẻm có xe đi |
| Mật độ đường chính | Gián tiếp qua tốc độ và đường cong tốc độ–mật độ | Kém hơn camera; camera vẫn là nguồn chính |
| Mật độ hẻm | Gián tiếp; lúc thưa xe tốc độ gần như không đổi nên không suy ra được | Yếu; chỉ báo "tốc độ hiệu dụng", không gọi là mật độ |

**Luật:**
1. G2 chỉ chấm bằng dữ liệu thật. Đoàn xe mô phỏng không được dùng để qua G2.
2. Mọi chính sách dùng chung lớp này. Đo tác động lên `greedy_load` trước khi giữ. MAPPO không có quyền đọc riêng.
3. Thí nghiệm chỉ chạy sau G2, khoảng 3–5 ngày.
4. Không có đoàn xe thật, nên trong bài ghi rõ phần đèn và hẻm được kiểm trên mô phỏng có sự thật đã biết. Phần tốc độ có một phép kiểm trên dữ liệu thật: coi một phần tuyến Mapbox là "xe đo", giữ riêng phần còn lại để chấm.

**Thí nghiệm:** bắt đầu từ khoảng ban đầu, cho đoàn 100, 200 xe, 2%, 5%, 10% lưu lượng chạy. Báo: sai số so với sự thật ẩn theo thời gian; tỉ lệ thông số được cập nhật; khoảng 90% có chứa sự thật đúng khoảng 90% số lần không; tác động lên từng chính sách khi bật và tắt lớp này. Có quên dần theo thời gian vì đèn và lưu lượng đổi theo giờ.

## Ước tính thời gian có yếu tố đèn đỏ ở tầm gần (người dùng đề xuất, 2026-11-09, ý tưởng đã lưu, chưa làm)

Chỉ bắt đầu sau khi mạng và mô phỏng đã chuẩn (qua G2). Khi đó thiết kế cùng người dùng để tận dụng tối đa.

- **Ý tưởng:** xe ước tính thời gian tới đích có tính đèn đỏ ở các nút gần. Nút xa thì sai số lớn, nên không dùng pha.
- **Dạng ước tính:** thời gian chờ kỳ vọng theo độ bất định của thời điểm đến và của pha. Khi độ bất định cỡ một chu kỳ, kết quả tự rơi về thời gian chờ trung bình, không cần ngưỡng khoảng cách.
- **Giả thuyết:** có ích nhất ở chỗ có hẻm thông tránh đèn. Nếu chính sách nào cũng có ước tính này, chính sách tham lam dễ dồn xe vào cùng một hẻm, và MAPPO có cơ hội thắng nhờ chia xe. Đây là giả thuyết, chưa có số đo.
- **Thứ tự:**
  1. Phép thử trần: `greedy_load` biết pha chính xác ở tầm gần. Cải thiện dưới khoảng 3% thì bỏ.
  2. Nếu đáng làm: hàm ước tính chỉ dùng thời điểm đoàn xe dừng và rời vạch, gắn với lớp độ tin cậy. Không đọc pha từ SUMO.
  3. Đưa vào MAPPO, IPPO và mọi heuristic như nhau. Có thể báo thêm so sánh với app không biết pha, ghi rõ đó là khác về thông tin.
- **Ngoại lệ cần ghi khi làm:** luật hiện tại chỉ cho quan sát biết nút có đèn hay không. Ước tính này là ngoại lệ, vì chỉ dùng số đoàn xe đo được.
- **Điều kiện dữ liệu:** phải đọc được pha và offset từ ảnh (hiện mức D). Nút có đèn không đều, ví dụ Nguyễn Tất Thành – Lê Văn Linh, phải tự rơi về trung bình.

## Giai đoạn 4: kịch bản và baseline

Chốt `.docs/PREREG_SCENARIOS.md` và commit **trước khi train**. Đội 100–200 xe, xe nền theo tập E:
- ngẫu nhiên; cặp nhiều đường tương đương (bộ OD v3, tính lại trên mạng đã sửa); cực đoan (dâng ở cầu, sự cố trên hẻm thông, mưa, xe vào hẻm cụt dày).

Baseline cuối: ff, app, app_history, greedy_load, thêm một heuristic chia luồng theo tải, IPPO.

## Giai đoạn 5: thiết kế MAPPO và train

- Thiết kế theo `PROBLEM_DEF.md`, tận dụng `routing2/gnn_policy.py`, `routing2/sumo_marl.py`: bất đồng bộ theo sự kiện, thông tin đội xe, critic tập trung.
- Trước khi train dài: test, smoke, kiểm tra gradient và khả năng học trên một kịch bản nhỏ; biết rõ thời gian mỗi update, mục tiêu tổng ≤ 24 giờ.
- Train MAPPO và IPPO cùng lúc. Theo dõi mỗi 25 update trên seed 50000+.

## Giai đoạn 6: đánh giá cuối

`eval_heldout` seed 60000+, 20 seed cho mỗi (họ kịch bản × cấu hình E). Kiểm định Wilcoxon cặp đôi, bootstrap 95%. Báo trung bình, CVaR25, tỉ lệ không thua, chỉ số cơ chế. Kiểm chứng độc lập trên SUMO nếu đã tự viết mô phỏng.

## Mốc thời gian (ước lượng)

| Mốc | Thời điểm |
|---|---|
| Giai đoạn 0 | 9/11 |
| G1 (chọn công cụ) | khoảng 14/11 |
| G0 (dữ liệu đủ 2 tuần) | khoảng 21/11 |
| G2 (mô phỏng khớp) | cuối 11 đến đầu 12 |
| G3 + kịch bản | tuần đầu 12 |
| Train và đánh giá | giữa 12 |

## File chính

- Mới: `.docs/PROBLEM_DEF.md`, `.docs/DATA_REGISTER.md`, `ml-core/routing2/validate/`.
- Sửa: `.docs/PREREG_SCENARIOS.md`, `ml-core/routing2/sumo_net.py` (cấm rẽ, làn, đèn), `ml-core/routing2/demand.py` (nhu cầu theo giờ), `ml-core/routing2/gate_msa.py`, `ml-core/cv_tracker/`.
- Có thể mới: mô phỏng tự viết, nếu SUMO không qua G1.
- `.docs/PLAN_7_STEPS.md` và `PLAN_CALIB_TRAIN.md` đánh dấu đã thay bằng kế hoạch này; ghi lại trong `AUDIT_SIM.md` các kết quả không còn giá trị.

## Kiểm tra

Mỗi cổng là một script in số đo so với ngưỡng, kết quả ghi vào `.docs/`:
- G0: so sánh đếm tay với model.
- G1: `validate/` cho L1, L2 có test tự động.
- G2: chấm khúc 300 m trên ngày và đoạn giữ riêng; mở ảnh ở các điểm lệch lớn.
- G3: nhiều seed, so trên vòng đã hội tụ.
- Trước train: test `routing2/test_*.py` và smoke.
