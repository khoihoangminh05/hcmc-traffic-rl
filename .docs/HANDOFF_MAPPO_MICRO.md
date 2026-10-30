# Bàn giao dự án: MAPPO micro next-hop, mạng hẻm Quận 4 (TP.HCM)

Cập nhật: 25/10/2026. Commit mới nhất khi viết: `8ad774e`.
Tài liệu này đủ để một agent hoặc người khác tiếp tục mà không cần đọc lại lịch sử chat.

**Mốc v3v đóng băng:** tag git `v3v-paper-baseline` giữ đúng code đã sinh mọi kết quả v3v.
Muốn dựng lại: `git checkout v3v-paper-baseline`. Toàn bộ số liệu thô của test sạch
nằm ở `.docs/results_v3v/heldout_raw.txt`. Nếu hướng SUMO (mục 12) thất bại, bài
vẫn viết được từ v3v với các số liệu này.

---

## 0. Đọc trước: quy tắc làm việc với người dùng

Người dùng nói tiếng Việt. Trả lời bằng tiếng Việt, rõ ràng, có số liệu.

**Quy tắc nghiên cứu (bắt buộc):**
1. **Không làm yếu heuristic.** Mọi luật dùng chung (áp cho mọi luật điều khiển) phải đo tác động lên `greedy_load` trước khi giữ. Ví dụ đã bỏ: cấm quay đầu (làm greedy tệ 5–7%), giới hạn số lần ghé nút (tệ 8%).
2. **Công bằng:** mọi luật chạy cùng môi trường, cùng chuyển trạng thái, cùng reward, cùng episode. Chỉ cách chọn hành động khác nhau.
3. **Liêm chính:** báo cáo mọi lần chạy, kể cả lần hỏng. Không thay seed hỏng bằng seed khác mà không nói. Chỉ đánh giá trên seed test sạch (60000+). Không sửa code giữa một loạt chạy; nếu có lỗi thì chạy lại mọi lần bị ảnh hưởng.
4. **Chẩn đoán trước, sửa sau.** Dùng `diagnose_policy` để đo lỗi trên checkpoint thật, không sửa theo đoán. Lịch sử cho thấy mỗi lần sửa theo đoán đều tốn thêm một lần train.
5. **Coi mỗi lần train là lần cuối:** rà và sửa hết rủi ro (test, smoke, kiểm trên bản đồ thật) trước khi đưa lệnh train.
6. **Cân nhắc chi phí train:** mỗi thay đổi phải nói rõ tốn thêm bao nhiêu thời gian. Ưu tiên chi phí một lần ở cuối hơn chi phí cộng vào mỗi vòng.
7. **Không dùng BC (bắt chước heuristic) để khởi động MAPPO.** Người dùng đã bác. Heuristic chỉ là baseline.
8. Đèn giao thông: quan sát chỉ có "nút có đèn hay không", không có pha/chu kỳ. Không ép chuyến đi qua đèn.
9. Khi người dùng nói "xem qua" thì chỉ chẩn đoán, không sửa code. Khi họ nói "sửa đi" hoặc "có gì bất lợi thì sửa ngay" thì sửa.

**Cách đưa lệnh cho người dùng:**
- Agent không SSH được vào sol1 (bị từ chối). Người dùng tự chạy lệnh. Không nhận mật khẩu SSH.
- Viết **đầy đủ từng lệnh**, dán được nguyên khối. Không viết kiểu "lặp lại, thay X".
- Người dùng **không chép được scrollback dài trong tmux**. Ghi kết quả ra file bằng `tee` rồi bảo họ `cat`.
- Trong tmux: `Ctrl+C` **giết lần train**. Thoát ra mà không tắt là `Ctrl+b` rồi `d`.
- Yêu cầu họ gửi kèm tên session tmux hoặc `run_dir=` khi gửi log (đã từng đọc nhầm log của lần chạy khác).

**Mục tiêu bài báo:** ngân sách thoải mái, không giới hạn thời gian, muốn bài **càng mạnh càng tốt**. Đích chính: **IEEE Transactions on ITS (T-ITS)**. Thay thế: Transportation Research Part C. An toàn: IEEE Access.

---

## 1. Hạ tầng

**Repo:** `https://github.com/khoihoangminh05/hcmc-traffic-rl`, nhánh `main`. Push trực tiếp lên `main` (người dùng đồng ý quy trình này để sol1 `git pull`).

**Máy local (Windows, PowerShell):** `D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl`
- PowerShell không có heredoc kiểu bash; viết file `.py` tạm rồi chạy, xóa sau.
- Shell của agent cần quyền `all` (không có sandbox).
- Không commit: `ml-core/density_l1_index.json`, `.docs/SERVER_SOL1.md` (đang sửa dở), các thư mục smoke, file probe.
- Nơi tải kết quả về: `ml-core\artifacts\out\quan4\marl_from_sol1\` (bị gitignore).

**sol1 (Ubuntu, 2× RTX 4090, 40 lõi vật lý, dùng chung nhiều người):**
- SSH: `ssh -p 8000 minhkhoi@sol1.swin.edu.vn`
- Kích hoạt môi trường:
  ```bash
  source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
  conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
  ```
- Repo: `~/hcmc-traffic-rl`, chạy từ `~/hcmc-traffic-rl/ml-core`
- Kết quả: `/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/` (= `ml-core/artifacts/out/quan4/marl_runs`)
- Sao lưu (khóa ghi): `/mnt/data8tb/minhkhoi/hcmc-traffic-rl/backup_runs/`
- GPU: `CUDA_VISIBLE_DEVICES=1`. GPU gần như không phải nút cổ chai; CPU mới là nút cổ chai (thu episode).
- Chạy được 4 lần train song song (tải trung bình khoảng 27). 3 lần + eval từng làm chậm mỗi vòng lên 594s khi tải quá cao. Kiểm `uptime`, số đầu nên dưới khoảng 40.

**Lệnh train mẫu:**
```bash
tmux new -s <tên>
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
cd ~/hcmc-traffic-rl/ml-core
CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.mappo_micro_train --config marl_agent/configs/quan4_mappo_micro.yaml --device cuda [--seed N] [--share-coef X] [--no-alley-info] [--ippo]
```
Một lần train khoảng 20 tiếng (khoảng 900–1300 vòng, mỗi vòng 40–130s).

---

## 2. Dữ liệu

- Đồ thị: `ml-core/artifacts/out/quan4/wcc/alley_graph_wcc.json`. 886 nút, 1828 cạnh có hướng, lấy từ OSM Quận 4. SCC lớn nhất 882 nút; có đúng 1 nút cụt `7560016898` (out-degree 0) và 1 cạnh dẫn vào nó.
- Mật độ/vận tốc: 3 file theo giờ cao điểm `alley_density_peak_{morning,afternoon,evening}_paper_a_merged_wcc.json`. **Sửa 30/10/2026:** mọi cạnh có giá trị, nhưng chỉ 379/1828 cạnh (21%) là `observed` (Mapbox profile `driving`, đoạn trung vị 18 m, không có traffic realtime); 1081 `interpolated`, 368 `prior`; `uncertainty` = 0.03 ở mọi cạnh. File camera `alley_density_l4_cam_wcc.json` chỉ khác file buổi tối ở 34 cạnh, và **không được dùng khi train** vì `density_by_peak` ghi đè nó ở mỗi `reset`. Không được viết rằng MARL chạy trên mật độ đo bằng camera.
- Đèn: `sumo-env/quan4_osm_signals.json`. 19 đèn OSM, 4 snap được, 3 có trong mạng SUMO (stub). Chu kỳ 60s, đỏ 30s.
- Mạng SUMO: `sumo-env/networks/quan4_alleys.net.xml` (dựng từ toạ độ thật, có tlLogic). Đã khớp thời gian đỏ với TraCI.
- Script lấy đèn: `ml-core/data_fusion/fetch_osm_signals.py`; dựng mạng SUMO: `export_sumo.write_geo_signal_net`.

---

## 3. Môi trường: `ml-core/marl_agent/mappo_micro_env.py`

**Đồng hồ sự kiện:** không chạy theo bước khóa. Mỗi `env.step` là một thời điểm quyết định. Đồng hồ nhảy tới sự kiện sớm nhất: xe ra khỏi cạnh, xe xuất phát, xe hết chờ, hoặc sự kiện bắt đầu/kết thúc. Chỉ xe đang đứng ở nút mới hành động. Xe nhanh không chờ xe chậm.

**Thời gian qua cạnh:**
- Thời gian thoáng = chiều dài / vận tốc đo (chặn 0.5–13 m/s).
- BPR: `t0 · (1 + 0.15 · (tải/sức chứa)^4)`, tải chặn ở 12. Tải = mật độ nền + số xe đang trên cạnh + tải sự kiện. Mật độ nền = clip(k/0.06, 0.2, 3).
- Sức chứa luồng: hẻm 2.5, đường dân sinh 6, tertiary/secondary 10, còn lại 8.
- Xe nằm trên cạnh tới khi ra. Xe mới vào làm xe đang trong chậm lại; thời gian ra được tính lại.
- Sức chứa vật lý: `chiều dài / 6m`. Cạnh đầy thì xe chờ ở nút; thời gian chờ tính vào thời gian đi.

**Đèn:** xe tới nút có đèn (không phải đích) lúc đỏ thì bị giữ tới hết đỏ. Quan sát chỉ có cờ "nút có đèn". `greedy_load` tránh nút có đèn nếu còn lối khác (nếu nút có đèn là đích thì vẫn vào).

**Sự kiện (shock):** mỗi episode 1 sự kiện trên cạnh dùng chung nhiều nhất: egress (dân ra hẻm, +4 tải, 30s), school (tan trường, +8 tải, 45s), obstacle (vật cản, tốc độ ×4 chậm, sức chứa /2, 60s). Bắt đầu ngẫu nhiên 10–80s. **Egress và school thấy trước** trong quan sát (lịch có thật). **Obstacle chỉ thấy khi đã xảy ra.**

**Chọn điểm đi/đến:** mỗi episode bốc 50 cặp, gốc và đích đều khác nhau, chọn trong nhiều lần bốc sao cho đường đi gặp nhau trên nhiều phố mà không dồn cả đội vào một hẻm. **Chỉ phụ thuộc seed của episode** (danh sách OD pool không được dùng). Thời điểm xuất phát rải đều trong 120s.

**Lối ra được phép (`_allowed_next`):** bỏ lối không còn đường tới đích (chặn ngõ cụt). Cùng một tập cho mọi luật.

**Ngân sách thời gian mỗi chuyến:** xe chưa tới đích sau `max(1800s, 6 × thời gian chuyến lúc đông)` thì bị tính thất bại. Baseline không bao giờ chạm mức này (dư ít nhất khoảng 578s). Ngoài ra có trần chung 8192 bước.

**Quay đầu:** đi ngược về nút vừa rời tốn thêm 5s (tính theo tốc độ thoáng, nhân với mức tắc), áp cho mọi luật, và `greedy_load` có tính vào dự báo. (Đo được: không làm greedy yếu đi, còn tốt hơn chút.)

**Reward (giống nhau cho mọi luật):** `−(thời gian qua cạnh + phạt dồn xe) / 1000`.
- Phạt dồn xe (city penalty): khi xe vào cạnh đang có `n` xe khác: `share_coef · n · (8 / sức_chứa)`, `share_coef = 8`. Ví dụ hẻm: 25.6s cho mỗi xe đã ở trong. Không cộng vào thời gian đi thật; cộng vào `_city`.
- **Điểm so sánh (objective) = trung bình (thời gian đi + phạt dồn xe)** cho mọi luật.
- Phạt bỏ dở (xe bị cắt): `2000 + 4 · min(thời gian thoáng còn lại, 3600)`, cộng vào thời gian đi.

**Chỉ dùng khi train MAPPO (không vào điểm, không vào baseline):**
- Tín hiệu dẫn đường potential-based: `(R(hiện tại) − γ·R(kế tiếp)) / 1000`, R = thời gian còn lại lúc đông, γ = 0.999 (Ng và cộng sự 1999).
- Phần thưởng khám phá theo số lần ghé: vào nút đã ghé k ≥ 2 lần bị trừ `explore_scale · 5s · (k − 1)`. `explore_scale` giảm tuyến tính 1 → 0 trong 600 vòng đầu (NGU/#Exploration).

**Quan sát (208 chiều):** 43 ô chung + 8 lối ra × 20 ô, đệm tới 208.
- Ô chung: thời điểm, giờ cao điểm, embedding gốc/đích/vị trí, thời gian còn lại thoáng và lúc đông, thời gian đã đi, số lần ghé nút hiện tại (/20), số xe đang tới nút, tóm tắt mật độ.
- Mỗi lối ra: có phải hẻm, thời gian thoáng, độ bất định, mật độ nền, số xe đang trên cạnh, độ đầy phía sau, 1/sức chứa, thời gian còn lại, số xe cùng chọn, **thời gian dự báo**, giá trị q của greedy, **regret** (0 ở lựa chọn của `greedy_load`), lịch sự kiện (đếm ngược, độ lớn), áp lực nhập dòng (xe khác sẽ dùng cạnh này), cờ đèn, **cờ "nút vừa rời"**, **số lần đã ghé nút đó (/20)**.
- `include_alley_info=False` (ablation) ẩn các ô mô tả tĩnh của hẻm, nhưng thời gian dự báo vẫn tính bằng sức chứa thật.
- Trạng thái toàn cục cho critic: trung bình quan sát cục bộ + thống kê, 219 chiều.

**Thước đo dồn xe vật lý:** `crowd_narrow_s` = số giây mỗi xe ở trên hẻm hẹp (sức chứa ≤ 2.5) cùng ít nhất một xe khác, tích phân chính xác. `crowd_entries` = số lần vào hẻm hẹp đang có xe. Không phụ thuộc `share_coef`.

---

## 4. Baseline

- `dijkstra`: đường ngắn nhất theo thời gian thoáng.
- `dijkstra_bpr`: đường ngắn nhất theo BPR(nền+1), tĩnh.
- `random`
- **`greedy_load`** (baseline chính): xét xe theo thứ tự chỉ số; mỗi xe chọn lối ra nhỏ nhất theo (có đèn hay không, thời gian dự báo chính xác qua cạnh + thời gian còn lại lúc đông). Dự báo dùng đúng phương trình của mô phỏng, nên rất mạnh; về thời gian của từng xe, gần như tối ưu.
- `greedy_informed`: như `greedy_load` nhưng dự báo có tính lịch sự kiện (egress/school). Mốc kiểm soát "thông tin". Kết quả gần như trùng `greedy_load`.
- `social`: chỉ để chẩn đoán (thêm độ trễ gây cho xe khác).
- **Chưa có, đang cần:** `greedy_city` = `greedy_load` + phạt dồn xe trong điểm chọn đường. Xem mục 9.

---

## 5. Trainer: `ml-core/marl_agent/mappo_micro_train.py`, config `marl_agent/configs/quan4_mappo_micro.yaml`

Thẻ hiện tại: `mappo_micro_v3v`.

- 50 xe, actor dùng chung + critic trung tâm (CTDE). `--ippo` dùng critic cục bộ.
- PPO: lr actor 1e-4, critic 5e-4, hidden 256, 16 episode mỗi vòng, 16 env tiến trình con, minibatch 8192, 4 epoch, clip 0.2, value coef 0.5, γ 0.999, λ 0.95.
- Entropy: 0.03 → 0.005 trong 400 vòng. Phần thưởng khám phá: 1 → 0 trong 600 vòng.
- **Seed episode train** lấy từ bộ sinh ngẫu nhiên của lần chạy, ≥ 1 000 000 (v3v). Trước v3v, các seed dùng chung 94% episode.
- Eval mỗi 50 vòng trên 8 episode cố định (seed 50000–50007), chính sách tất định. Dừng sớm khi 10 lần eval liên tiếp không tốt hơn 10s. Tối đa 2000 vòng.
- Cuối lần chạy: so sánh cặp 30 episode từ seed 50000. **Chú ý: 8 episode đầu trùng episode dùng chọn `best.pt`.** Con số chính thức phải lấy từ `eval_heldout` (seed 60000).
- BC tắt (`bc.enabled: false`).
- Log mỗi vòng: dòng `[ppo]` với fleet, arrival (tới đích thật), policy_loss, value_loss, entropy, ent_coef, explore, kl.
- Cờ dòng lệnh: `--seed`, `--share-coef`, `--no-alley-info`, `--ippo`, `--smoke`, `--max-updates`, `--n-agents`.

---

## 6. Công cụ

- **Test:** `cd ml-core && python -u -m marl_agent.test_mappo_micro_env` (in `MAPPO_MICRO_ENV_TESTS_OK`).
- **Smoke trainer:** `python -u -m marl_agent.mappo_micro_train --config marl_agent/configs/quan4_mappo_micro.yaml --device cpu --smoke`
- **Test sạch:** `python -u -m marl_agent.eval_heldout --run <run_dir> --episodes 30 [--n-agents 100] [--share-coef 8]`. Seed 60000+. Không ghi đè file cũ. Ghi `heldout_eval[_n100][_share8].json`. In điểm, thời gian đi, phạt dồn xe, crowd, tới đích, chênh lệch cặp, khoảng tin cậy 95%, tỉ lệ thắng.
- **Chẩn đoán:** `python -u -m marl_agent.diagnose_policy --run <run_dir> --episodes 4`. Báo tới đích, mức trùng với greedy, xe hỏng có đi vòng không, có né hẻm không.
- Lần `share0` phải đánh giá với `--share-coef 8` để so được với bảng chính.

---

## 7. Lịch sử phiên bản và bài học

| Thẻ | Thay đổi | Vì sao |
|---|---|---|
| v3a | Bản đầu có BC + PPO, 16 xe | Bước khóa, quên xe trong hẻm. Không dùng làm bằng chứng. |
| v3b–v3h | Đồng hồ sự kiện, xe nằm trong hẻm, 50/100 xe, OD cân bằng, đèn, sự kiện | Sửa MDP |
| v3i | Reward = thời gian đi + phạt dồn xe cho mọi luật | Bản cũ tính trùng ngoại ứng |
| v3j | Đèn chỉ là cờ, không pha | Theo yêu cầu người dùng |
| v3k–v3n | 50 xe, log từng episode, bỏ BC, tối ưu tốc độ | 100 xe quá chậm |
| v3o | Phạt bỏ dở cộng thêm theo khoảng cách (thay vì max(8000, …)) | v3n học cách đi qua lại trên đoạn ngắn |
| v3p | Ngân sách thời gian mỗi chuyến, tín hiệu potential, chặn ngõ cụt | Xe kẹt vĩnh viễn ở ngõ cụt làm treo episode |
| v3q | Ẩn tai nạn trước khi xảy ra, thêm `greedy_informed`, thống kê cặp | Công bằng thông tin |
| v3r | Ô "vừa đi từ đâu"/"đã ghé", phí quay đầu, lr 1e-4 | Chẩn đoán: 88% xe hỏng chạy qua lại 2 nút |
| v3s | Entropy giảm dần, bộ đếm ghé tới 20 | Seed 43 kẹt ở 0.81 |
| v3t | Phạt ghé lại cố định | Bị thay bởi v3u |
| v3u | Phạt ghé lại thành phần thưởng khám phá giảm dần về 0 | Chẩn đoán: xe né hẻm có xe, đi vòng ~38 lần |
| **v3v** | Seed episode độc lập giữa các lần chạy | Các seed dùng chung 94% episode |

Bài học quan trọng:
- Phạt hằng số cho mọi xe chưa tới đích → chính sách lách phạt.
- Chính sách không có trí nhớ → chạy qua lại 2 nút.
- Phạt dồn xe hiện ra ngay khi vào hẻm, còn cái giá của việc đi vòng mãi đến rất muộn → bẫy "đi thêm một vòng".
- `greedy_load` tự nó cũng đi vòng quanh khu tắc (tới 11 lần) mà vẫn đúng, nên không được giới hạn số lần ghé.

---

## 8. Kết quả (test sạch, 30 episode, seed 60000+)

### 8.1 Kết quả chính v3v, MAPPO 5 seed (42–46)

50 xe:

| Seed | best update | Điểm | Thời gian đi | Phạt dồn xe | Crowd | Δ vs greedy_load | Thắng |
|---|---|---|---|---|---|---|---|
| 42 | 300 | 501.4 | 460.6 | 40.8 | 34.9 | −7.3% | 30/30 |
| 43 | 800 | 485.4 | 462.7 | 22.7 | 19.2 | −10.2% | 30/30 |
| 44 | 250 | 513.9 | 460.9 | 53.0 | 46.0 | −4.9% | 26/30 |
| 45 | 400 | 500.2 | 460.9 | 39.3 | 31.3 | −7.5% | 30/30 |
| 46 | 350 | 503.9 | 461.9 | 42.0 | 35.1 | −6.8% | 30/30 |
| **TB** | | **501.0 ± 10.2** | **461.4** | **39.6** | **33.3** | **−7.3%** | 146/150 |
| greedy_load | | 540.7 | 464.7 | 76.0 | 62.7 | | |
| greedy_informed | | 540.6 | 464.6 | 76.0 | 62.8 | | |
| dijkstra | | 650.7 | 541.1 | 109.6 | 165.5 | | |

Khoảng tin cậy 95% theo seed cho Δ (t, 4 bậc tự do): [−52.4, −27.0]s. Tới đích 1.000 cho mọi seed.

100 xe (chính sách train ở 50 xe, không train lại):

| Seed | Điểm | Thời gian đi | Crowd | Δ vs greedy_load |
|---|---|---|---|---|
| 42 | 631.6 | 511.1 | 96.3 | −9.5% |
| 43 | 611.5 | 508.0 | 83.1 | −12.4% |
| 44 | 648.7 | 515.4 | 110.7 | −7.1% |
| 45 | 626.6 | 510.3 | 90.1 | −10.2% |
| 46 | 632.1 | 512.2 | 94.5 | −9.5% |
| **TB** | **630.1 ± 13.3** | **511.4** | **94.9** | **−9.7%** |
| greedy_load | 698.1 | 537.0 | 126.4 | |
| dijkstra | 1408.3 (tới đích 0.939) | 1212.8 | 654.7 | |

Khoảng tin cậy 95% theo seed: [−84.6, −51.5]s. Thắng 150/150.

### 8.2 Ablation v3v (1 seed, seed 42), chấm bằng hệ số phạt 8

| Biến thể | best | Điểm 50 xe | Thời gian đi | Crowd | Δ vs greedy | Điểm 100 xe |
|---|---|---|---|---|---|---|
| MAPPO đầy đủ (TB 5 seed) | | 501.0 | 461.4 | 33.3 | −7.3% | 630.1 |
| share0 (không phạt dồn xe khi train) | 50 | **586.8** | 486.2 | 102.6 | **+8.5%** (thua 30/30) | 788.1 (thời gian đi 601.9) |
| noalley | 350 | 499.6 | 459.8 | 33.4 | −7.6% | 630.1 |
| ippo | 300 | 501.5 | 461.1 | 37.0 | −7.2% | 626.3 |

Chấm `share0` bằng chính mục tiêu của nó (hệ số 0, tức chỉ thời gian đi): 486.2 so với greedy 464.7 (+4.6%, thua 30/30).

### 8.3 Diễn giải

1. MAPPO giữ thời gian đi ngang `greedy_load` ở 50 xe nhưng giảm khoảng 47% thời gian ở chung hẻm hẹp. Điểm so sánh tốt hơn 7.3%.
2. Lợi thế tăng theo mật độ: −9.7% ở 100 xe, và ở đó thời gian đi cũng giảm 4.8%.
3. Thắng nhờ phối hợp, không nhờ thông tin (`greedy_informed` ≈ `greedy_load`).
4. **share0:** bỏ phạt dồn xe thì MAPPO thua greedy, kể cả về thời gian đi. Ở 100 xe, nó chậm hơn MAPPO đầy đủ 18%. Tức là đưa chi phí ngoại ứng vào reward (giống phí tắc đường Pigou) làm cả hệ thống đi nhanh hơn. Đây là bằng chứng nhân quả chính, nhưng mới 1 seed.
5. **noalley ≈ MAPPO:** các ô mô tả tĩnh của hẻm không thêm gì, vì thông tin hẻm đã nằm trong các ô dự báo (tính bằng sức chứa thật). Không được kết luận "dữ liệu hẻm vô ích".
6. **IPPO ≈ MAPPO:** critic trung tâm không có lợi. Khớp tài liệu (de Witt và cộng sự 2020). Không được nhận critic trung tâm là đóng góp.

### 8.4 Kết quả sơ bộ (không dùng làm kết quả chính)

- v3r seed 42 (test sạch): −5.0% ở 50 xe, −8.3% ở 100 xe; crowd −28.9%.
- v3r seed 43 hỏng (kẹt 0.80 tới đích). v3r seed 44 tốt (trong lần chạy −8.9%).
- v3u seed 42/43 đều hội tụ (eval tốt nhất 516.6 / 517.3). Seed 43 từng hỏng ở v3r/v3s đã được sửa.

---

## 9. Việc tiếp theo (theo thứ tự)

1. **`greedy_city` (quan trọng nhất, quyết định nơi nộp):** heuristic = `greedy_load` + phạt dồn xe dự kiến trong điểm chọn đường (cùng công thức môi trường tính: `share_coef · (số xe đang trên cạnh + số xe cùng chọn trước) · 8/sức_chứa`). Thêm làm chế độ baseline trong `mappo_micro_env.py` (giống `greedy_informed`, gọi `_score_waiting` với cờ mới), thêm vào `run_episode_baseline` và danh sách baseline mặc định của `evaluate_fair_suite`. Không đưa vào luật của `greedy_load` gốc. Rồi chạy lại `eval_heldout` trên 5 checkpoint v3v (50 và 100 xe).
   - MAPPO > `greedy_city`: học tăng cường phối hợp nhiều bước → nhắm T-ITS.
   - `greedy_city` ≈ MAPPO: đóng góp là định giá ngoại ứng → Q2/IEEE Access.
2. **Thêm 2 seed cho `share0`** (`--share-coef 0 --seed 43`, `--seed 44`), đánh giá với `--share-coef 8`.
3. **Mốc tối ưu toàn hệ thống** (system-optimal, ví dụ Frank–Wolfe) trên cùng mạng.
4. **Kiểm chứng SUMO vòng kín** (TraCI) cho chính sách và baseline, chỉ để đánh giá.
5. **Độ nhạy:** `--share-coef 4`, `16`; số xe 25/75/150 (chỉ đánh giá); có thể train trực tiếp 100 xe.
6. So vận tốc mô phỏng với số đo camera (hiệu chỉnh).
7. Có thể: quận thứ hai (thiếu dữ liệu camera), baseline MARL khác (MAA2C/QMIX).
8. Công bố mã và dữ liệu.
9. Viết bài theo định dạng T-ITS.

**Điểm phải ghi rõ trong bài (giới hạn và công khai):**
- Mô phỏng BPR theo sự kiện, không phải bám xe đầy đủ như SUMO.
- Hệ số phạt dồn xe do mình chọn (8, nhân 8/sức chứa).
- Đèn có chương trình cố định; sự kiện là tổng hợp.
- Quan sát có ý định đường đi của xe khác (giả định V2X/nền tảng dẫn đường).
- Quan sát có regret của greedy (học phần dư).
- Có tín hiệu potential và phần thưởng khám phá chỉ khi train; điểm đánh giá không đổi.
- `best.pt` được chọn trên seed 50000–50007; kết quả chính lấy trên seed 60000+.
- Ablation hiện mới 1 seed.

---

## 10. Thư mục kết quả trên sol1 (`/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/`)

Loạt chính thức v3v:
- `quan4_mappo_micro_mappo_micro_v3v_20261021T120334Z_seed42`
- `quan4_mappo_micro_mappo_micro_v3v_20261021T120359Z_seed43`
- `quan4_mappo_micro_mappo_micro_v3v_20261021T120451Z_seed44`
- `quan4_mappo_micro_mappo_micro_v3v_20261021T120623Z_seed45`
- `quan4_mappo_micro_mappo_micro_v3v_20261023T024755Z_seed46`
- `quan4_mappo_micro_mappo_micro_v3v_share0_20261023T024831Z_seed42`
- `quan4_mappo_micro_mappo_micro_v3v_noalley_20261023T024918Z_seed42`
- `quan4_mappo_micro_mappo_micro_v3v_ippo_20261023T024958Z_seed42`

Sơ bộ: v3r `..._v3r_20261018T052853Z_seed42`, `..._v3r_20261019T093310Z_seed44`; v3u `..._v3u_20261020T165149Z_seed42`, `..._v3u_20261020T164939Z_seed43`. Các lần hỏng/dừng dở của v3r/v3s/v3t cũng còn trong `marl_runs` và `backup_runs`.

Mỗi thư mục có: `best.pt`, `ckpt_*.pt`, `metrics.jsonl`, `metrics.csv`, `summary.json`, `hyperparameters.snapshot.yaml`, `config.source.yaml`, `od_split.json`, và các `heldout_eval*.json`.

Kết quả test sạch dạng text trên sol1: `~/heldout_v3v_A.txt`, `~/heldout_v3v_B.txt`, `~/heldout_v3v_seed46.txt`, `~/heldout_v3v_share0.txt`, `~/heldout_v3v_noalley.txt`, `~/heldout_v3v_ippo.txt`.

**Chưa tải về máy local.** Lệnh tải (PowerShell trên Windows):
```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl\ml-core\artifacts\out\quan4\marl_from_sol1
scp -P 8000 -r "minhkhoi@sol1.swin.edu.vn:/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/*mappo_micro_v3v*" .
```

---

## 12. Hướng đang bàn (chưa chốt, 25/10/2026): chuyển sang SUMO + kiến trúc chú ý

Người dùng đặt nguyên tắc mới:
- Mọi luật (MARL, greedy, heuristic khác) chỉ được dùng thông tin một hệ thống thật đo được.
  **Không được nhìn vào lõi mô phỏng:** công thức BPR, file nội suy mật độ, lộ trình xe nền.
  Hiện `greedy_load` và các ô dự báo trong quan sát MAPPO đều vi phạm, vì dùng
  `_forecast_entry` (phương trình của chính mô phỏng).
- Lộ trình, giờ đi và hướng sắp đi của **50 xe trong đội** thì mọi luật được biết.
  MARL khai thác; heuristic chỉ dùng nếu người viết heuristic tự viết thêm (vd `greedy_city`).
- Chuyển hẳn lõi mô phỏng sang **SUMO** (`libsumo`; dự phòng chế độ mesoscopic nếu chậm).
- Kiến trúc mới: mỗi xe chú ý (attention) tới tối đa K xe liên quan nhất trong đội, lọc trước
  bằng đồ thị xung đột (thời gian tới lúc gặp trên đoạn chung). Thông tin từng xe: vị trí
  tương đối, thời gian tới lúc gặp, các đoạn sắp đi, **loại xe** (cùng chính sách / heuristic /
  khác). Train với **đội xe hỗn hợp** để mô hình học chơi khác nhau với từng loại.
  Khi chạy thật với nhiều xe hơn, vẫn giữ K xe để đầu vào giống lúc train.
- Đánh giá: tỉ lệ người dùng 10–100%, hệ thống mở (xe đến/đi liên tục), nhiều xe hơn lúc train.

Các giai đoạn: (0) dựng môi trường SUMO và đo tốc độ, cổng ≤ khoảng 5s/episode/tiến trình;
(1) baseline chỉ dùng thông tin công khai; (2) đưa MLP-MAPPO sang SUMO, train 1–2 seed;
(3) kiến trúc mới; (4) loạt chính thức. Kết quả v3v trở thành kết quả sơ bộ / phụ lục.

---

## 11. Lệnh hay dùng trên sol1

Sao lưu mọi lần chạy đã xong (không ghi đè, khóa ghi):
```bash
BK=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/backup_runs
for d in $(ls -d /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/*mappo_micro_v3v*); do
  [ -f "$d/summary.json" ] || continue
  b="$BK/$(basename "$d")"
  [ -e "$b" ] || { cp -a "$d" "$BK/" && chmod -R a-w "$b" && echo "saved $(basename "$d")"; }
done
```

Lịch sử eval của một lần chạy:
```bash
RUN=$(ls -dt /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/*v3v_2*_seed42 | head -1)
grep '"type": "eval"' "$RUN/metrics.jsonl" | grep -oE '"update": [0-9]+|"objective_mean": [0-9.]+|"arrival_rate": [0-9.]+' | paste - - - | tail -6
```

Trạng thái các lần chạy:
```bash
for d in $(ls -dt /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/*mappo_micro_v3v* | head -8); do
  if [ -f "$d/summary.json" ]; then st=done; else st=running; fi
  echo "$(basename "$d") | $st | $(tail -1 "$d/metrics.csv" | cut -d, -f1,3,4)"
done
uptime
```
