# Ngoại ứng ở ngã nhập: lập luận (bản nháp 2026-11-02)

Phạm vi: mô hình **tĩnh, luồng liên tục, hàng đợi dừng**. Đây là lý do cơ chế, chưa phải chứng minh cho SUMO động.

## Mô hình
Nút n có các nhánh chính j (không nhường) và nhánh phụ m (nhường). Q = Σ_j q_j là lưu lượng chính.

- Sức chứa nhánh phụ (Siegloch): c(Q) = exp(−Q(t_c − t_f/2)) / t_f, giảm theo Q.
- Trễ chờ trên nhánh phụ: W(q_m, c), tăng theo q_m, giảm theo c. Ví dụ W = 1/(c − q_m) khi q_m < c.
- Chi phí nhánh chính l_j(q_j) không phụ thuộc q_m (nhánh chính có ưu tiên).

Tổng chi phí: C = Σ_j q_j l_j(q_j) + Σ_m q_m [ l_m(q_m) + W(q_m, c(Q)) ].

## Mệnh đề 1 (chi phí biên có thành phần giữa các cạnh)
∂C/∂q_j = l_j + q_j l_j′ + E_j, với E_j = Σ_{m tại n} q_m (∂W/∂c) c′(Q) ≥ 0.

Với W = 1/(c − q_m): E_j = Σ_m q_m (t_c − t_f/2) c / (c − q_m)².

*Chứng minh*: lấy đạo hàm; ∂W/∂c < 0 và c′ < 0 nên E_j ≥ 0, và E_j > 0 khi có q_m > 0. ∎

Hệ quả: quy tắc "chi phí biên trên chính cạnh" bỏ sót E_j, nên nghiệm của nó nói chung không thỏa điều kiện dừng của SO khi E_j > 0 khác nhau giữa các tuyến. E_j tăng nhanh khi c(Q) → q_m, tức đúng lúc ngã nhập sắp bão hòa.

Jacobian chi phí không đối xứng (∂W/∂Q ≠ 0 nhưng ∂l_j/∂q_m = 0), nên UE không có thế năng Beckmann, phải dùng bất đẳng thức biến phân. Đây là kết quả **đã biết** (xem dưới).

## Mệnh đề 2 (có trường hợp SO theo cạnh tệ hơn UE)
Ví dụ kiểm được: hai tuyến, tuyến A đi qua nút nhập, tuyến B tránh nút. D = 0.5 xe/s, l_A = 60 + 20x, l_B = 50 + 100(D − x), nhánh phụ không đổi tuyến q = 0.10 xe/s, t_c = 4, t_f = 2, W = 1/(c − q). (Tái lập: `python -m routing2.theory_merge_example`.)

| Quy tắc | x (qua nút) | W (s) | Tổng (xe·s/s) | So với UE |
|---|---|---|---|---|
| UE | 0.3333 | 11.91 | 34.525 | — |
| Chi phí biên theo cạnh | 0.3750 | 16.04 | 34.729 | **+0.59%** |
| SO thật | 0.3400 | 12.46 | 34.517 | −0.02% |

Cơ chế: tuyến B dốc hơn nên quy tắc theo cạnh đẩy thêm xe sang A, làm giảm sức chứa nhánh phụ. Đây là ví dụ tự chọn để minh họa khả năng xảy ra, không nói gì về độ lớn trên mạng thật. Lưu ý: trong chính ví dụ này SO thật chỉ hơn UE 0.02%, tức có ngoại ứng lớn **không** đảm bảo khoảng UE–SO lớn. Đó đúng là rủi ro của cổng A.

## Tài liệu đã có: phần lý thuyết này KHÔNG mới
Tương tác giữa các nhánh ở nút trong gán luồng đã được nghiên cứu từ thập niên 1980. Mới thấy qua Crossref, **chưa đọc**:
- Heydecker 1983, *Some Consequences of Detailed Junction Modeling in Road Traffic Assignment*, Transportation Science, 10.1287/trsc.17.3.263.
- Smith 1982, *Junction interactions and monotonicity in traffic assignment*, TR-B, 10.1016/0191-2615(82)90036-4.
- Carey và cộng sự 2012, DTA xấp xỉ kinematic wave, SO và chi phí biên, TR-B, 10.1016/j.trb.2012.01.008.

Vậy bài chỉ có thể nói điều mới ở: đo độ lớn trên mạng hẻm xe máy; công cụ SO thường dùng trong mô phỏng vi mô bỏ sót nó; và đưa nó vào chia công MARL theo từng xe. Không được trình bày như phát hiện lý thuyết.

## Chưa chứng minh
- Tính động, tràn ngược, đèn. Xe nhánh phụ cũng làm chậm nhánh chính trong SUMO, nên chiều ngược lại có thể không bằng 0.
- SUMO có tuân theo Siegloch ở ngã nhập không. `gate_msa` dùng dạng fit thực nghiệm c_m Q², khác công thức ở đây.
- Xe máy không làn và quyền ưu tiên yếu có thể làm mờ phân biệt chính / phụ.
