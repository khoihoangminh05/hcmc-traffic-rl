# Kế hoạch tải tài liệu cho Grok Bot

Dán toàn bộ phần dưới đường kẻ vào Grok Bot. File này không chứa mật khẩu.

---

Tải các bài báo sau về `D:\LapTrinh\System\HCMC_urban_traffic_optimization\papers\`. Đề tài: định tuyến đa tác tử (MAPPO, GNN) cho xe máy trong mạng hẻm Quận 4, TP.HCM, mô phỏng bằng SUMO, nhắm tới TR-C hoặc IEEE T-ITS.

## Quy tắc

1. Thứ tự nguồn: arXiv, trang tác giả hoặc repository trường, Semantic Scholar hoặc OpenAlex (link open access), rồi trang nhà xuất bản nếu bài mở.
2. Mỗi bài thử tối đa 2 nguồn, mỗi nguồn 1 lần. Không được thì ghi vào danh sách và chuyển bài khác.
3. Không dùng Sci-Hub, LibGen hay trang lậu. Không vượt captcha, paywall hay giới hạn tải.
4. Bài cần đăng nhập thì không tự đăng nhập, không hỏi mật khẩu. Ghi `need_login` kèm DOI.
5. Nghỉ ít nhất 10 giây giữa hai lần tải. Tối đa 60 file. Bị chặn hoặc gặp lỗi 403, 429 trên một trang thì bỏ trang đó.
6. Chỉ giữ PDF đúng bài: kiểm tra tiêu đề và tác giả. Không tạo số liệu hay trích dẫn; không chắc thì ghi `unverified`.
7. Đặt tên `Tacgia_Nam_TuKhoa.pdf`. Không xóa hay đổi file nào khác trên máy.

## Nhóm A: bài nền (tìm đúng bản gốc)

- Ng, Harada, Russell (1999), Policy invariance under reward transformations
- Schulman et al. (2017), Proximal Policy Optimization Algorithms
- Schulman et al. (2016), High-Dimensional Continuous Control Using Generalized Advantage Estimation
- Yu et al. (2022), The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games
- Foerster et al. (2018), Counterfactual Multi-Agent Policy Gradients
- Wolpert, Tumer (2002), Optimal payoff functions for members of collectives
- Veličković et al. (2018), Graph Attention Networks
- Vinyals, Fortunato, Jaitly (2015), Pointer Networks
- Kool, van Hoof, Welling (2019), Attention, Learn to Solve Routing Problems!
- Lopez et al. (2018), Microscopic Traffic Simulation using SUMO
- Wardrop (1952), Some theoretical aspects of road traffic research
- Roughgarden, Tardos (2002), How bad is selfish routing?
- Chu et al. (2020), Multi-Agent Deep Reinforcement Learning for Large-Scale Traffic Signal Control

## Nhóm B: bài gần đây (2020 trở đi, mỗi chủ đề tối đa 6 bài, ưu tiên TR-C, TR-B, T-ITS, NeurIPS, ICML, ICLR, AAMAS)

1. multi-agent reinforcement learning dynamic route guidance next-hop
2. decentralized vehicle routing reinforcement learning user equilibrium system optimum
3. graph neural network traffic assignment routing reinforcement learning
4. routing with partial or noisy connected vehicle information, driver compliance
5. mixed traffic motorcycle dominated network simulation calibration
6. difference rewards credit assignment congestion games
7. navigation app rerouting congestion externalities, informational Braess paradox
8. SUMO reinforcement learning routing large-scale network

## Kết quả cần trả

Ghi `papers\manifest.csv` với các cột: `title, authors, year, venue, doi, url, file, status, note`. `status` là một trong `ok, need_login, not_found, blocked, unverified`. Cuối cùng báo số bài theo từng `status`.
