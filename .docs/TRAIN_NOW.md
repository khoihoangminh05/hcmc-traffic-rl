# Train trên sol1 — Git-first + học cùng thầy

Server: [SERVER_SOL1.md](./SERVER_SOL1.md) (2×RTX 4090, ưu tiên GPU 1, output `/mnt/data8tb`).  
**Cách đọc số:** [LEARN_WITH_TEACHER.md](./LEARN_WITH_TEACHER.md) — bắt buộc đọc song song khi có `summary.json`.

Bạn không chỉ “chạy ra số”: mỗi run là một bài tập. Xong → gửi thầy `summary.json`.

---

## Phần 1 — Windows: Git sẵn sàng

Repo đã `git init` + commit local. Bạn tạo repo trống trên GitHub rồi:

```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl
git remote add origin https://github.com/<USER>/<REPO>.git
git push -u origin main
```

(Nếu remote đã có: chỉ `git push`.)

Trong git đã có: code + `alley_graph.json` + `alley_density_latest.json` + seeds.

---

## Phần 2 — sol1: clone & chuẩn bị ổ

```bash
ssh minhkhoi@SOL1_HOST

cd ~
git clone https://github.com/<USER>/<REPO>.git hcmc-traffic-rl
cd ~/hcmc-traffic-rl/ml-core

mkdir -p /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs
mkdir -p /mnt/data8tb/minhkhoi/hcmc-traffic-rl/pip-cache
mkdir -p artifacts/out/quan4
ln -sfn /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs artifacts/out/quan4/marl_runs

# Kiểm tra data train
ls -lh artifacts/out/quan4/alley_graph.json
ls -lh artifacts/out/quan4/density/alley_density_latest.json
ls ../ingestion-worker/config/od_pairs.quan4.seeds.json
```

Sau này sửa code ở Windows → `git push` → trên sol1: `cd ~/hcmc-traffic-rl && git pull`.

---

## Phần 3 — venv + PyTorch (một lần)

```bash
cd ~/hcmc-traffic-rl/ml-core
python3 -m venv .venv
source .venv/bin/activate
export PIP_CACHE_DIR=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/pip-cache

pip install -U pip
pip install -r requirements.txt
pip install --index-url https://download.pytorch.org/whl/cu124 torch

python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

`cuda False` → đổi wheel CUDA trên pytorch.org (không `sudo pip`).

---

## Phần 4 — Train (có thầy trong đầu)

```bash
nvidia-smi   # chọn GPU IDLE — thường GPU 1
cd ~/hcmc-traffic-rl/ml-core
source .venv/bin/activate

# (1) Smoke — hiểu pipeline chạy được
python -m marl_agent.robust_train --smoke --device cpu
# Kỳ vọng: ROBUST_TRAIN_OK

# (2) Train thật — nên trong tmux
tmux new -s marl
LOG=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/train_$(date +%Y%m%d_%H%M%S).log
CUDA_VISIBLE_DEVICES=1 python -m marl_agent.robust_train \
  --config marl_agent/configs/quan4_h100.yaml \
  --device cuda \
  2>&1 | tee "$LOG"
# Detach tmux: Ctrl+B rồi D
```

### Trong lúc chạy, nhìn gì?

| Log | Ý | Chưa cần lo nếu… |
|-----|---|------------------|
| `[train] return / travel` | Học trên batch train | Số nhảy lên xuống nhẹ |
| `[eval] regret / acc` | **Thước chính** | acc ~50% ở v0 đầu — bình thường |
| `[adapt]` | Tự giảm LR khi val đứng | Không phải lỗi |
| `ROBUST_TRAIN_OK` | Chạy xong sạch | Chưa = “giỏi paper” |

Chi tiết: [LEARN_WITH_TEACHER.md](./LEARN_WITH_TEACHER.md).

---

## Phần 5 — Kéo về + buổi chữa bài với thầy

Trên sol1:

```bash
RUN=$(ls -td /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/quan4_marl_robust_* | head -1)
echo "RUN=$RUN"
cat "$RUN/summary.json"
tar -czf /tmp/marl_result_v0.tar.gz -C "$RUN" \
  summary.json best.pt metrics.jsonl metrics_train.csv \
  adapt_history.json hyperparameters.snapshot.yaml \
  od_split.json run_meta.json
```

Windows:

```powershell
scp minhkhoi@SOL1_HOST:/tmp/marl_result_v0.tar.gz `
  D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl\ml-core\artifacts\out\quan4\
```

**Gửi vào chat:** nội dung `summary.json` (paste) + nói bạn hiểu gì theo 4 câu trong LEARN.  
Thầy sẽ: xác nhận / sửa hiểu sai / chỉ **một** bước tiếp (cải data hay train lại).

---

## Checklist nhanh

- [ ] `git push` được từ Windows  
- [ ] `git clone` trên sol1  
- [ ] Symlink `marl_runs` → `/mnt/data8tb/...`  
- [ ] `nvidia-smi` → GPU rảnh  
- [ ] Smoke CPU OK  
- [ ] Train CUDA → `ROBUST_TRAIN_OK`  
- [ ] Đã đọc LEARN + gửi `summary.json`  

Cải data sau baseline: [ENV_UPGRADE_L1_L5.md](./ENV_UPGRADE_L1_L5.md).
