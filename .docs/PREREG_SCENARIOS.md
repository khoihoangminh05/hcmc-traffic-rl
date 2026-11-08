# Đăng ký trước bộ kịch bản đánh giá (bản nháp, 2026-11-08)

Mục đích: chốt bộ kịch bản, trọng số, chỉ số và seed **trước khi train MAPPO**. Khi có người hỏi "có chọn kịch bản có lợi không", ta chỉ vào commit đầu tiên chứa bản **chốt** của file này. Sau mốc đó, mọi thay đổi phải ghi lý do ở cuối file và báo cáo cả kết quả theo bộ cũ.

Trạng thái: **NHÁP**. Chỉ được chốt khi:
1. C1 đạt mức "hợp lý nhất có thể", kèm tập mô phỏng E.
2. Các kiểm tra K1, K2 (`RESEARCH_V4` §15) cho thấy còn đất.

## 1. Tập mô phỏng E (độ bất định của hiệu chỉnh)

Gồm 5 cấu hình hiệu chỉnh tốt nhất theo điểm khúc 300 m (`routing2/calib/stretch.py`) trên nửa cal, mỗi cấu hình phải có tới đích ≥ 0.8. Một cấu hình gồm:
- mức nội quận;
- luồng theo từng phía cổng (và trọng số cổng nếu có);
- tham số lớp tốc độ (a, b, k0);
- chu kỳ đèn;
- số làn của làn chỉ dành cho xe máy (1 hoặc 2).

Mọi kết quả chính báo cáo trên **cả 5** cấu hình. Kết luận chỉ đứng nếu đúng trên ít nhất 4 trong 5.

## 2. Các họ kịch bản (mỗi họ có lý do thực tế và tần suất)

| Họ | Tham số | Lý do thực tế | Trọng số |
|---|---|---|---|
| S0 thường | đội xe 15% trên cặp C/X, không sự kiện | ngày thường | 0.40 |
| S1 đội xe lớn | đội xe 30% và 50% | thị phần app gọi xe hoặc dẫn đường lớn (Grab, Be, Google Maps) | 0.15 |
| S2 sự cố hẻm thông | 1–2 hẻm thông trên đường thay thế của cặp C bị chậm 70% trong 10–20 phút | xe đỗ hoặc giao hàng chặn hẻm, rất thường gặp | 0.15 |
| S3 dâng ở cầu | luồng một cổng (cầu) tăng 50–100% trong 15 phút | tan ca ở cảng hoặc khu chế xuất, sự kiện | 0.10 |
| S4 mưa | v_free mọi lớp × 0.75, hẻm × 0.6 | mưa chiều mùa mưa | 0.10 |
| S5 tải bắt buộc dày | luồng F (vào hẻm cụt) × 3 | giờ về nhà, khu dân cư trong hẻm | 0.10 |

Trọng số tạm theo tần suất ước lượng; chốt cùng file. Nguồn tần suất (ghi khi chốt): cường độ mưa theo tháng, thị phần app, và số sự cố hẻm nếu có.

## 3. Chỉ số

Báo cáo mọi chỉ số, cho mọi chính sách, trên mọi họ:
- **J** = 0.5·T_all + 0.5·T_cust.
- **Kỳ vọng có trọng số** theo bảng ở mục 2.
- **CVaR25:** trung bình 25% episode xấu nhất của J.
- **Xác suất sụp:** tỉ lệ episode có tới đích dưới 0.75.
- **Tỉ lệ kịch bản không thua:** MAPPO không thua chính sách tốt nhất còn lại quá 1%.
- **Cơ chế:**
  - tỉ lệ quãng đường xe đội đi trong hẻm thông;
  - chỉ số dồn đường: entropy của cách chia xe đội giữa các đường của mỗi cặp C;
  - số lần đổi đường;
  - thời gian chờ trên hẻm thông.

## 4. Chính sách

ff, app, app_history (cập nhật theo chu kỳ, giống ứng dụng thật), greedy_load (tinh chỉnh hệ số trên seed 40000+, không làm yếu), IPPO, MAPPO. Mọi chính sách dùng cùng thông tin quan sát, theo luật công bằng của CLAUDE.md.

## 5. Seed

- Tinh chỉnh: 40000+.
- Chọn model: 50000+.
- Đánh giá cuối: 60000+, mỗi (họ × cấu hình E) 20 seed.

Kiểm định: Wilcoxon cặp đôi theo seed, khoảng tin cậy bootstrap 95%.

## 6. Nhật ký thay đổi sau khi chốt

(trống)
