# Rà soát code chính `routing2` (2026-11-04, commit 9b98d82)

Đọc `sumo_env`, `sumo_marl`, `gnn_policy`, `objectives`, `eval_heldout`, `demand`, `sumo_net`. Test `OBJECTIVES`, `GNN_POLICY`, `SUMO_FEATURES` đều qua. Đo local: TraCI, SUMO 1.28, 1 seed, nên chỉ là chỉ báo.

## Đã đúng (đã kiểm)
- `fleet_weights`: a = wp + 1 − w, b = wp đúng là đạo hàm của J theo thời gian khách và xe khác. `potential_shaping` đúng dạng SMDP của Ng. GAE theo giây, reset đúng giữa các xe.
- Không rò thông tin: actor chỉ thấy báo cáo đội xe, ý định, p bị che; `true` chỉ vào critic khi train. Mọi controller chung `max_detour`, tuân thủ, lịch sự cố.
- Hành động ghi là điều đã báo cho tài xế, kể cả khi họ không theo, nên PPO coi việc không tuân thủ là nhiễu của môi trường, đúng.
- Tách seed đúng; `best.pt` chọn trên 50000+; `eval_heldout` ghép cặp theo seed cầu.

## Đã sửa (không đổi kết quả mô phỏng)
| # | Vấn đề | Sửa |
|---|---|---|
| F1 | `build_net` chạy lại netconvert và ghi đè `quan4_v4.net.xml` mỗi lần có job khởi động, trong khi worker của job đang chạy mở file này mỗi episode. Có thể đọc phải file dở, nhất là khi chạy song song | Dựng ở thư mục tạm, chỉ thay nếu nội dung khác, bằng `os.replace` |
| F2 | `args.json` chỉ có commit; từng chạy nhầm commit mà không biết | Thêm `git_dirty_routing2`, `net_sha`, `graph_sha`, `sumo_version` |

## Chưa sửa: làm đổi kết quả, chỉ áp dụng cho chuỗi sau
**Ảnh hưởng tới kết luận**

| # | Vấn đề | Bằng chứng | Đề xuất |
|---|---|---|---|
| A1 | **Teleport đang trộn hai thứ khác hẳn.** `teleports_per_1k_trips` gộp chờ quá lâu với **va chạm** | Local, 300 s, 8000 chuyến/giờ, horizon 900: ff 5/5 do va chạm, app 2/3, random 18/19; 0 do sai làn. `--no-warnings` đang che lý do | Ghi lý do bằng `--log` hoặc API va chạm. Điều tra vì sao xe máy va chạm khi có sublane (bước 0.5 s, `minGapLat`). Độ nhạy `time-to-teleport` chỉ đụng tới loại chờ quá lâu |
| A2 | **Mô hình hẻm**: 1460/1460 cạnh hẻm có cạnh ngược, mỗi cạnh 2.5 m, không có xung đột ngược chiều | `RESEARCH`, `reading/README` mục 7 | Chốt nghĩa của 2.5 m bằng mẫu gán nhãn, rồi đo lại |
| A3 | **`_attribute` bỏ qua quyền ưu tiên.** Mọi xe gần cuối các nhánh khác vào cùng nút đều bị tính, kể cả xe đang đứng chờ; xe trên đường chính bị chậm cũng tính cho xe hẻm đang nhường (dòng 429–430). Xe trong 50 m phía trước bị tính dù xe máy có thể vượt | Đọc code; Psarou 2510 p.4, p.6 | Chỉ tính bên có quyền đi trước cho xe đang nhường, và lọc xe đang đứng. Rồi kiểm phản thực |
| A4 | **Sự kiện cũng bị tính là lỗi của xe phía trước**: `vf` lấy từ đồ thị, không theo tốc độ tạm thời khi có tai nạn hay tan học, nên cả đoàn xe trong vùng sự kiện tính phí lẫn nhau | Dòng 421–426 | Dùng tốc độ giới hạn hiện tại của cạnh |
| A5 | **Một SUMO seed cho mọi đánh giá**: `_worker_run` mặc định `sumo_seed=1` trong eval và heldout | Khoảng tin cậy không tính nhiễu tài xế; lần đo trước, cùng bộ tuyến lệch 170–198 giờ theo seed SUMO | Lấy theo seed cầu, giữ giống nhau giữa các controller |
| A6 | Cạnh có báo cáo trông chậm hơn cạnh không có báo cáo | Cầu rất thấp (500 chuyến/giờ, chỉ số tắc 1.05): thời gian đo / free-flow trung vị 1.06, thêm 0.33 s mỗi cạnh; đoạn 40 cạnh chênh khoảng 13 s. Cạnh không báo cáo trôi về free-flow | App và RL bị đẩy nhẹ sang cạnh chưa ai đi; có thể góp phần vào km +4% của app (chưa chứng minh). Đặt mức nền theo thời gian đo được lúc vắng thay cho free-flow lý thuyết |
| A7 | Bootstrap xe bị cắt bằng `v[i]` của chính quyết định cuối | Horizon 1500 của v7 giảm tỉ lệ cắt nhưng không bỏ | Bootstrap từ trạng thái tại H; đo độ lệch trước |

**Ít nguy hiểm hơn**

| # | Vấn đề | Đề xuất |
|---|---|---|
| B1 | GNN 3 lớp trên line graph chỉ thấy khoảng 3 cạnh, trung vị 17.6 m mỗi cạnh, tức khoảng 53 m (tính lại). Chỉ còn vector toàn mạng và `live_togo` mang thông tin xa | Ablation 3 và 6 lớp, thêm MLP; reviewer sẽ hỏi |
| B2 | `t/H` thực ra là vị trí trong tập, không phải giờ trong ngày; policy có thể học thuộc đỉnh cầu giữa cửa sổ | Thử bỏ, hoặc quét `peak_sd` lúc test |
| B3 | `self._rng` dùng chung cho báo cáo và tuân thủ, số lần rút khác nhau theo controller, nên không phải số ngẫu nhiên chung | Tách luồng theo xe, giảm nhiễu so cặp |
| B4 | Bước chỉ học critic vẫn tính cả GNN của actor và `policy` | Thêm đường chỉ tính critic, nhanh hơn, không đổi kết quả |
| B5 | Khi hết giờ, xe đang teleport không nằm trong `getIDList`, nên bị tính cả tuyến thay vì phần còn lại | Nhỏ, ghi nhận |
| B6 | Không có chuẩn hóa value | `reading/README` mục 3 |

## Đã bác bỏ
- "Báo rẽ muộn 10 m làm xe kẹt sai làn, phạt riêng RL và app": 0 teleport sai làn ở cả ff, app, random; chỉ 69/1828 cạnh có 2 làn.
