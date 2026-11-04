# Khung bài báo (đích TR-C hoặc T-ITS; cập nhật 2026-11-04)

Luận điểm: `RESEARCH_V4.md` mục 13. Related Work: `related_work.md`. Giao thức: `experiment_protocol.md`. Câu reviewer: `reviewer_qa.md`. Rà code: `code_review.md`. Tài liệu tham khảo: `refs.bib`. **Chưa có kết quả nào trong khung này là kết luận.**

Tiêu đề làm việc: *Coordinated navigation in motorcycle-dominated alley networks under partial participation and imperfect reports* (đổi theo kết quả).

| Mục | Nội dung | Nguồn | Trạng thái |
|---|---|---|---|
| 1. Introduction | Hẻm là phần lớn mạng đường; nhà cung cấp dẫn đường có thể điều phối (Arora 2026); câu hỏi nghiên cứu; đóng góp | RESEARCH_V4 §1, §3 | Chờ cổng A |
| 2. Related work | 6 mạch; bảng định vị | `.docs/lit/` | Chờ đọc toàn văn, Scopus / WoS |
| 3. Twin và dữ liệu | Mạng, Mapbox là hồ sơ lịch sử, fusion, hiệu chỉnh nhu cầu | PLAN_PAPER Phần 3 | Chưa làm fusion |
| 4. Phân tích bài toán | Khoảng UE–SO theo nhu cầu; trễ ở đâu; ngoại ứng ngã nhập | `gate_msa`, `theory_merge.md` | Đang quét |
| 5. Phát biểu bài toán | Tỉ lệ người dùng p, thông tin đo được, tuân thủ; tùy chọn ràng buộc hẻm | PLAN_PAPER Phần 4 | Chưa |
| 6. Phương pháp | Policy, reward chia công, huấn luyện | PLAN_PAPER Phần 5 | Mới có v1 ích kỷ |
| 7. Thí nghiệm | Giao thức viết trước; baseline; thống kê | PLAN_PAPER Phần 6 | Chưa |
| 8. Kết quả | Lợi ích theo p, độ tin cậy, tải lên hẻm | | Chưa |
| 9. Thảo luận | Đe dọa tính hợp lệ: cầu tổng hợp, SUMO, chen khe, bề rộng hẻm, Mapbox | RESEARCH_V4 §9 | Có danh sách |
| 10. Kết luận | | | Chưa |

Nếu cổng A trượt: bỏ mục 6–8 dạng MARL, chuyển thành phân tích ngoại ứng và định giá trong mạng hẻm.
