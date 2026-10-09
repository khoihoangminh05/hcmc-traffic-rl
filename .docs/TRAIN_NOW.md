# Train trên sol1 — Paper B (sau freeze Paper A)

> **Hướng dẫn thao tác chuẩn (làm theo đây):** [SOL1_PAPER_B.md](./SOL1_PAPER_B.md)  
> Chiến lược 2 paper: [RESEARCH_TWO_PAPERS.md](./RESEARCH_TWO_PAPERS.md).  
> Server: [SERVER_SOL1.md](./SERVER_SOL1.md). Đọc số: [LEARN_WITH_TEACHER.md](./LEARN_WITH_TEACHER.md).

**Không dùng** `python3 -m venv` / `apt` / `snap` trên sol1.  
**Đã ổn:** Miniconda + conda-env train + `tmux` user (`tools-env`).

---

## Đường dẫn chuẩn

| Thứ | Path |
|-----|------|
| Code | `~/hcmc-traffic-rl/` |
| Miniconda | `/mnt/data8tb/minhkhoi/miniconda3` |
| Conda env (train) | `/mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env` |
| Tools (`tmux`) | `/mnt/data8tb/minhkhoi/tools-env` → thêm vào `PATH` qua `~/.bashrc` |
| Pip cache | `/mnt/data8tb/minhkhoi/hcmc-traffic-rl/pip-cache` |
| Train runs | `/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs` |

---

## Mỗi lần SSH (bật env train)

```bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
cd ~/hcmc-traffic-rl/ml-core

which python   # phải .../hcmc-traffic-rl/conda-env/bin/python
which tmux     # phải .../tools-env/bin/tmux  (sau khi đã thêm PATH)
nvidia-smi     # chọn GPU rảnh — thường GPU 1
```

---

## ★ Train lại ngay (baseline v0 — làm theo đây)

**Không** thêm `--smoke`. Smoke chỉ để thử máy (~vài update).

```bash
# --- terminal sol1 ---
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
cd ~/hcmc-traffic-rl/ml-core

# Symlink output (an toàn nếu đã có)
mkdir -p /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs
mkdir -p artifacts/out/quan4
ln -sfn /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs artifacts/out/quan4/marl_runs

nvidia-smi
# GPU 0 bận / GPU 1 ~0% + vài MiB  →  dùng GPU 1

tmux new -s marl
```

**Bên trong tmux** (cần activate lại vì session mới):

```bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
cd ~/hcmc-traffic-rl/ml-core

LOG=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/train_$(date +%Y%m%d_%H%M%S).log

CUDA_VISIBLE_DEVICES=1 python -m marl_agent.robust_train \
  --config marl_agent/configs/quan4_h100.yaml \
  --device cuda \
  2>&1 | tee "$LOG"
```

- Detach (train vẫn chạy): **Ctrl+B** rồi **D**  
- Xem lại: `tmux attach -t marl`  
- List session: `tmux ls`  
- Xong khi thấy `ROBUST_TRAIN_OK` và log có `[train] …/200` (không phải chỉ 6 update)

**Thời gian:** thường **phút → vài chục phút** (bottleneck shortest-path CPU, không phải “10 giây”). Nếu ~10s lại xong → đang nhầm smoke hoặc lệnh sai.

### Sau khi xong

```bash
RUN=$(ls -td /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/quan4_marl_robust_* | head -1)
echo "RUN=$RUN"
cat "$RUN/summary.json"
```

Paste `summary.json` vào chat + đọc [LEARN_WITH_TEACHER.md](./LEARN_WITH_TEACHER.md).

---

## ★ Paper B — train một thể v5 (sau freeze Paper A)

**Trước khi train:** morning peak đã fuse (Paper A pass) + sync `wcc/` + `seeds_l3` lên sol1.  
Bundle local: `ml-core/artifacts/out/quan4/v5_bundle_for_sol1.tar.gz`.  
Config: `marl_agent/configs/quan4_v5_final.yaml` (`data_tag: v5_l1l5`).

Chi tiết checklist twin: [RESEARCH_TWO_PAPERS.md](./RESEARCH_TWO_PAPERS.md) · [ENV_UPGRADE_L1_L5.md](./ENV_UPGRADE_L1_L5.md).

### Paper A — chỉ fuse/QA morning (0 GPU, local)

```powershell
cd …\ml-core
python -m data_fusion.run_quan4_density --l1-peaks --min-positive 3 `
  --graph artifacts/out/quan4/wcc/alley_graph_wcc.json `
  --mapbox ..\ingestion-worker\data_raw\mapbox\travel_time_YYYY-MM-DD.csv `
  --output artifacts/out/quan4/density --latest-peak evening
python -m data_fusion.verify_l3 --mapbox ... --density artifacts/out/quan4/density/alley_density_latest.json
```

### Paper B — sol1 GPU1

```bash
cd ~/hcmc-traffic-rl && git pull
cd ml-core
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env

# sync/extract wcc + seeds từ bundle nếu cần
tmux new -s marl_v5
LOG=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/train_v5_$(date +%Y%m%d_%H%M%S).log
CUDA_VISIBLE_DEVICES=1 python -m marl_agent.robust_train \
  --config marl_agent/configs/quan4_v5_final.yaml --device cuda \
  2>&1 | tee "$LOG"
```

Bảng so v0 vs v5:

```bash
python -m marl_agent.l5_metrics_table path/to/v0/summary.json path/to/v5/summary.json
```

Kéo về Windows (tuỳ chọn):

```bash
tar -czf /tmp/marl_result_v0.tar.gz -C "$RUN" \
  summary.json best.pt metrics.jsonl metrics_train.csv \
  adapt_history.json hyperparameters.snapshot.yaml \
  od_split.json run_meta.json
```

```powershell
scp minhkhoi@SOL1_HOST:/tmp/marl_result_v0.tar.gz `
  D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl\ml-core\artifacts\out\quan4\
```

---

## Log cần nhìn lúc train

| Log | Ý | Ghi chú học |
|-----|---|-------------|
| `[train] N/200` | Update thứ N / tối đa 200 | Phải thấy số tăng dần |
| `return / travel` | Học trên train | Được dao động |
| `[eval] regret / acc` | **Thước chính** | v0 đầu acc ~50% bình thường |
| `[adapt]` | Tự giảm LR/entropy | Không phải lỗi |
| `ROBUST_TRAIN_OK` | Pipeline sạch | Chưa = “đủ paper” |

---

## Setup một lần (đã xong thì bỏ qua)

### Git (Windows → GitHub → sol1)

```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl
git push -u origin main
```

```bash
cd ~ && git clone https://github.com/<USER>/<REPO>.git hcmc-traffic-rl
# sau này: cd ~/hcmc-traffic-rl && git pull
```

### Miniconda + env train

```bash
# cài miniconda → /mnt/data8tb/minhkhoi/miniconda3
# conda tos accept (main + r)
# conda create -y -p /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env python=3.11
# pip install -r requirements.txt + torch cu124
```

Chi tiết lịch sử lỗi: mục cuối file.

### tmux user-space

```bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda create -y -p /mnt/data8tb/minhkhoi/tools-env -c conda-forge tmux

grep -q 'minhkhoi/tools-env/bin' ~/.bashrc || cat >> ~/.bashrc << 'EOF'

# user tools (tmux, etc.)
export PATH="/mnt/data8tb/minhkhoi/tools-env/bin:$PATH"
EOF
source ~/.bashrc
which tmux && tmux -V
```

---

## Lỗi đã gặp (đừng lặp)

| Lỗi | Cách đúng |
|-----|-----------|
| `ensurepip` / không có venv | Miniconda, không `apt` |
| `pip` / `python` not found | `conda activate .../conda-env` trước |
| `CondaToSNonInteractiveError` | `conda tos accept` channel main + r |
| `snap info tmux` | Cài `tools-env` + PATH (không snap) |
| Train xong ~10s | Đừng dùng `--smoke` cho baseline |

---

## Checklist

- [x] Miniconda + ToS + conda-env + torch  
- [x] tmux trong `tools-env` + PATH  
- [ ] Symlink `marl_runs`  
- [ ] Train **full** GPU1 (không `--smoke`) → `ROBUST_TRAIN_OK`  
- [ ] Gửi `summary.json` + đọc LEARN  

Cải data sau v0: [ENV_UPGRADE_L1_L5.md](./ENV_UPGRADE_L1_L5.md).
