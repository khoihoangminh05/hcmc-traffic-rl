# Việc cho Grok Bot

Dán từng mục dưới đường kẻ cho Grok. File không chứa mật khẩu. Thư mục dự án: `D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl`.

**Quy tắc chung cho mọi việc:** không xóa, đổi tên hay sửa file nào khác ngoài file được giao. Không đoán, không tạo dữ liệu hay trích dẫn: không chắc thì ghi `unknown`. Không dùng trang lậu, không vượt captcha hay giới hạn tải. Bị chặn thì ghi lại rồi chuyển mục khác. Xong thì báo số mục làm được, số `unknown`, và những gì bị chặn.

---

## Việc 1. Gán nhãn bề rộng 50 hẻm (quan trọng nhất)

File: `.docs\alley_width_sample.csv`. Mỗi dòng là một đoạn hẻm ở Quận 4, TP.HCM. Mở link ở cột `street_view` trong trình duyệt, xem ảnh đường phố, rồi điền vào đúng các cột còn trống:

| Cột | Điền |
|---|---|
| `imagery_found(y/n)` | `y` nếu có ảnh nhìn được **chính con hẻm đó**; `n` nếu không có ảnh hoặc ảnh ở đường khác. Nếu `n` thì các cột sau ghi `unknown` |
| `width_class(<2,2-3,3-4,>4)` | Bề rộng mặt đường từ tường tới tường, chọn một nhóm. Mốc so sánh: xe máy rộng khoảng 0.8 m, ô tô con khoảng 1.8 m |
| `two_way(y/n)` | `y` nếu xe đi được cả hai chiều; không thấy biển cấm và xe đi hai chiều thì `y` |
| `parked_or_stalls(none/some/many)` | Xe đỗ, hàng quán chiếm mặt đường |
| `note` | Năm chụp nếu thấy; điều gì khiến bạn không chắc |

Yêu cầu:
- Chỉ điền theo điều thấy trong ảnh. Không suy từ tên hẻm, không đoán từ hẻm bên cạnh. Không thấy thì ghi `unknown`. Kết quả sẽ dùng trong một bài báo khoa học nên `unknown` tốt hơn nhiều so với đoán.
- Không tải hay lưu ảnh Street View. Không thêm hay xóa dòng, không đổi các cột đã có sẵn dữ liệu.
- Nếu 5 dòng đầu đều không có ảnh, dừng lại và báo ngay, đừng làm tiếp.

## Việc 1b. Gán thêm nhãn 40 hẻm

File: `.docs\results_alley\alley_width_sample2.csv`. Làm giống Việc 1, cùng quy tắc, với các lưu ý:
- Trong cột `note`, ghi **vật so sánh đã dùng để ước lượng** (xe máy, ô tô, cửa nhà), và khoảng cách từ ảnh tới đúng vị trí nếu xem được.
- Không tự suy nhãn cho dòng không có ảnh (lần trước có file nội suy theo hẻm cùng tên, không dùng được). Không cần file nội suy.
- Không lưu ảnh chụp màn hình.
- Không dừng khi vài dòng đầu không có ảnh: lần trước khoảng 60% không có ảnh là bình thường.

## Việc 2. Tải bài báo còn thiếu

Lưu vào `papers\`, đúng tên ở cột cuối. Chỉ giữ PDF đúng bài: kiểm tra tiêu đề và tác giả ở trang đầu. Bản truy cập mở trước; nếu cần tài khoản thì ghi `need_login` kèm DOI.

| Bài | Tìm ở | Tên file |
|---|---|---|
| Chowdhury & Chakraborty 2024, Calibration of SUMO Microscopic Simulation for Heterogeneous Traffic Condition: Khulna, Transportation Engineering | https://doi.org/10.1016/j.treng.2024.100281 | Chowdhury_2024_Khulna.pdf |
| Arora et al. 2026, Urban congestion relief experiments through routing-app interventions, Nature Cities | https://doi.org/10.1038/s44284-026-00443-x | Arora_2026_Google.pdf |
| Wolpert & Tumer 2001, Optimal payoff functions for members of collectives, Advances in Complex Systems | https://doi.org/10.1142/s0219525901000188 | Wolpert_2001_Collectives.pdf |
| Kuncheria et al. 2023, Socially-aware Evaluation Framework for Transportation, Transportation Letters | https://doi.org/10.1080/19427867.2022.2157366 | Kuncheria_2023_Social.pdf |
| Patil & Sangole 2016, gap acceptance, Ấn Độ | Tìm "Patil Sangole gap acceptance" | Patil_2016_Gap.pdf |
| Ibrahim & Sanik 2007, gap acceptance, Malaysia | Tìm "Ibrahim Sanik gap acceptance motorcycle" | Ibrahim_2007_Gap.pdf |
| Graf & Harks 2024, side constraints, Operations Research | Tìm theo tên tác giả | Graf_2024_SideConstraints.pdf |
| Qian et al. 2012, System optimal dynamic traffic assignment with and without queue spillback, TR-B | https://doi.org/10.1016/j.trb.2012.02.008 | Qian_2012_SODTA.pdf |

Cuối cùng ghi `papers\manifest_2.csv` với các cột `title,file,url,status,note`.

## Việc 3. Tìm bài tiếng Việt và bài phản bác

Mục tiêu: tìm công trình có thể đã làm điều bài báo định nói, để không viết sai. Tìm trên Google Scholar, thư viện số các trường Việt Nam (ĐH Bách khoa TP.HCM, ĐH Giao thông Vận tải), và TRID, với các từ khóa:

- `định tuyến xe máy hẻm mô phỏng`, `mạng hẻm TP.HCM giao thông`, `ngõ hẻm luồng xe máy`, `phân luồng hẻm`
- `alley network routing motorcycle Vietnam`, `narrow street motorcycle routing simulation`, `reinforcement learning motorcycle routing`, `SUMO motorcycle calibration Vietnam`
- `alley width Ho Chi Minh City survey`, `hẻm bề rộng khảo sát TP.HCM`

Ghi `papers\search_vn.csv` với các cột `query,source,hits,title,authors,year,venue,url,why_relevant`. Chỉ liệt kê bài thật sự mở được trang của nó và thấy tiêu đề. Ghi cả truy vấn không ra kết quả (`hits` = 0). Ưu tiên bài có **số đo bề rộng hẻm hoặc lưu lượng trong hẻm**. Không cần tải PDF.

## Việc 4. Hỏi Mapbox về quyền công bố (chỉ soạn, không gửi)

Soạn email tiếng Anh ngắn cho Mapbox hỏi: nghiên cứu học thuật đã lưu kết quả Directions API `driving-traffic` của một quận, có được công bố (a) số liệu thô, (b) hồ sơ tốc độ theo giờ đã tổng hợp theo đoạn đường, (c) chỉ các tham số mô hình dẫn xuất không? Ghi vào `papers\mapbox_email_draft.txt`. Không gửi; người dùng sẽ tự gửi.

## Việc 5. Lấy số trong bài Gibert (không gấp)

Mở bằng trình duyệt: https://www.iias.asia/the-newsletter/article/vietnamese-urban-fabric . Chép **nguyên văn** mọi câu có số về bề rộng hẻm, tỉ lệ hẻm, dân số hoặc giao thông trong hẻm của Hà Nội và TP.HCM, kèm nguồn bài đó trích, vào `papers\gibert_numbers.txt`. Không tóm tắt, không suy diễn. Không mở được thì ghi rõ.

## Việc 6. Google Scholar, chạy lại Việc 3 bằng trình duyệt thường (không gấp)

Việc 3 bị Scholar chặn cả 10 truy vấn. Mở Scholar trong trình duyệt thường, mỗi truy vấn của Việc 3 xem trang đầu, ghi bài liên quan vào `papers\search_vn_scholar.csv`, cùng cột như Việc 3. Gặp captcha thì dừng và báo, không tìm cách vượt.

## Việc 7. Xem ảnh đường phố 6 điểm nghẽn (làm trước Việc 5, 6)

File: `.docs\results_alley\hotspots_street_check.csv` (12 dòng, 2 vị trí mỗi đoạn). Quy tắc giống Việc 1b, với các lưu ý:
- Mở link ở cột `street_view`. Chỉ điền theo điều thấy trong ảnh. Không thấy thì `unknown`. Không lưu ảnh, không thêm hay xóa dòng, không đổi các cột đã có.
- `wall_width_class`: bề rộng từ tường tới tường. `clear_width_class`: phần xe còn đi được sau khi trừ xe đỗ, hàng quán. Hai cột này có thể khác nhau, đó là điều cần biết.
- `two_way`: `y` chỉ khi **thấy xe đi cả hai chiều trong ảnh**; không thấy biển một chiều thì ghi `unknown` và ghi vào `note`.
- Đoạn hạng 0 có thể là đường chứ không phải hẻm: vẫn điền, và ghi số làn nếu thấy.
- `note`: năm chụp, vật so sánh, khoảng cách từ ảnh tới đúng vị trí, và có thấy đông xe, kẹt xe, chợ, trường học, hay vật cản cố định gần đó không.

Ảnh không cho biết có tắc thường xuyên hay không. Không suy luận điều đó; chỉ ghi điều thấy trong ảnh đó.
