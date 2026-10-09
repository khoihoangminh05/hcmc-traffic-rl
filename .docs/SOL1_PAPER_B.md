# Paper B trên sol1 — thao tác chuẩn (copy-paste)

> Twin Paper A đã freeze. Bài này chỉ **train MARL** `v5_l1l5` và so với v0.  
> Plan: [RESEARCH_TWO_PAPERS.md](./RESEARCH_TWO_PAPERS.md) · máy: [SERVER_SOL1.md](./SERVER_SOL1.md).

**Không** `--smoke`. **Không** `apt`/`venv` hệ thống. Dùng conda-env + GPU **1**.

---

## 0) Trên Windows (một lần trước khi SSH)

### 0a. Đẩy code lên GitHub

```powershell
cd D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl
git status
git add -A
# (đừng add .env / data_raw ảnh cam nếu không cần)
git commit -m "Paper A freeze twin + Paper B v5 train config"
git push origin main
```

Nếu bạn muốn mình commit hộ — nói một câu trong chat.

### 0b. Copy bundle twin lên sol1

File local (~1MB):

`ml-core\artifacts\out\quan4\v5_bundle_for_sol1.tar.gz`

```powershell
# Đổi SOL1_HOST cho đúng (user@host)
scp D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl\ml-core\artifacts\out\quan4\v5_bundle_for_sol1.tar.gz `
  minhkhoi@SOL1_HOST:/tmp/v5_bundle_for_sol1.tar.gz
```

---

## 1) SSH sol1 — bật env

```bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
export PATH="/mnt/data8tb/minhkhoi/tools-env/bin:$PATH"

cd ~/hcmc-traffic-rl
git pull

which python   # .../hcmc-traffic-rl/conda-env/bin/python
which tmux
nvidia-smi     # chọn GPU rảnh — thường GPU 1
```

---

## 2) Giải bundle twin vào đúng chỗ

```bash
cd ~/hcmc-traffic-rl
mkdir -p ml-core/artifacts/out/quan4 /tmp/v5_stage
tar -xzf /tmp/v5_bundle_for_sol1.tar.gz -C /tmp/v5_stage

# WCC graph + peak densities + l4
rm -rf ml-core/artifacts/out/quan4/wcc
mkdir -p ml-core/artifacts/out/quan4
cp -a /tmp/v5_stage/wcc ml-core/artifacts/out/quan4/

# L1 index + freeze meta
mkdir -p ml-core/artifacts/out/quan4/density
cp -f /tmp/v5_stage/density_l1_index.json ml-core/artifacts/out/quan4/density/ 2>/dev/null || true
cp -f /tmp/v5_stage/paper_a_freeze_meta.json ml-core/artifacts/out/quan4/ 2>/dev/null || true

# Seeds Paper A
mkdir -p ingestion-worker/config
cp -f /tmp/v5_stage/config/od_pairs.quan4.seeds_l3.json ingestion-worker/config/

# Config train (nếu git pull chưa có)
cp -f /tmp/v5_stage/marl_configs/quan4_v5_final.yaml ml-core/marl_agent/configs/ 2>/dev/null || true

# Symlink runs → ổ 8TB
mkdir -p /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs
mkdir -p ml-core/artifacts/out/quan4
ln -sfn /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs ml-core/artifacts/out/quan4/marl_runs
```

### 2b. Kiểm tra file (bắt buộc — phải thấy EXISTS hết)

```bash
cd ~/hcmc-traffic-rl/ml-core
python - <<'PY'
from pathlib import Path
need = [
  "artifacts/out/quan4/wcc/alley_graph_wcc.json",
  "artifacts/out/quan4/wcc/alley_density_l4_cam_wcc.json",
  "artifacts/out/quan4/wcc/alley_density_peak_morning_paper_a_merged_wcc.json",
  "artifacts/out/quan4/wcc/alley_density_peak_afternoon_paper_a_merged_wcc.json",
  "artifacts/out/quan4/wcc/alley_density_peak_evening_paper_a_merged_wcc.json",
  "../ingestion-worker/config/od_pairs.quan4.seeds_l3.json",
  "marl_agent/configs/quan4_v5_final.yaml",
]
bad = False
for r in need:
    p = Path(r)
    ok = p.exists()
    print(("OK  " if ok else "MISS"), p.resolve() if ok else r)
    bad |= not ok
raise SystemExit(1 if bad else 0)
PY
```

Pass: mọi dòng `OK`. Nếu `MISS` — đừng train, sửa path/bundle trước.

---

## 3) Smoke CPU 30s (an toàn)

```bash
cd ~/hcmc-traffic-rl/ml-core
python -m marl_agent.robust_train \
  --config marl_agent/configs/quan4_v5_final.yaml \
  --device cpu --smoke
```

Pass: thấy `L1 density_catalog=...` đủ 3 peak + `ROBUST_TRAIN_OK`.  
(Smoke chỉ 6 update — bình thường.)

---

## 4) Train full GPU1 (Paper B)

```bash
cd ~/hcmc-traffic-rl/ml-core
tmux new -s marl_v5
```

**Trong tmux** (activate lại):

```bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
export PATH="/mnt/data8tb/minhkhoi/tools-env/bin:$PATH"
cd ~/hcmc-traffic-rl/ml-core

LOG=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/train_v5_$(date +%Y%m%d_%H%M%S).log

CUDA_VISIBLE_DEVICES=1 python -m marl_agent.robust_train \
  --config marl_agent/configs/quan4_v5_final.yaml \
  --device cuda \
  2>&1 | tee "$LOG"
```

- Detach: **Ctrl+B** rồi **D**  
- Attach lại: `tmux attach -t marl_v5`  
- Xong khi: `ROBUST_TRAIN_OK` và log `[train] N/200` (hoặc early-stop), **không** chỉ 6 update.

---

## 5) Lấy kết quả

```bash
RUN=$(ls -td /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/quan4_marl_robust_v5_l1l5_* | head -1)
echo "RUN=$RUN"
cat "$RUN/summary.json"
cat "$RUN/run_meta.json" | head -40

# So với v0 (đổi path v0 nếu tên khác)
V0=$(ls -td /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/quan4_marl_robust_v0_* 2>/dev/null | head -1)
cd ~/hcmc-traffic-rl/ml-core
python -m marl_agent.l5_metrics_table "$V0/summary.json" "$RUN/summary.json"
```

Paste `summary.json` (+ bảng metrics nếu có) vào chat.

Đóng gói về Windows (tuỳ chọn):

```bash
tar -czf /tmp/marl_result_v5.tar.gz -C "$RUN" \
  summary.json best.pt metrics.jsonl metrics_train.csv \
  adapt_history.json hyperparameters.snapshot.yaml \
  od_split.json run_meta.json
```

```powershell
scp minhkhoi@SOL1_HOST:/tmp/marl_result_v5.tar.gz `
  D:\LapTrinh\System\HCMC_urban_traffic_optimization\hcmc-traffic-rl\ml-core\artifacts\out\quan4\
```

---

## Lỗi hay gặp

| Hiện tượng | Cách xử |
|------------|---------|
| `Missing density` / `require_l1_catalog` | Chưa giải bundle đúng — làm lại mục 2 + check `OK` |
| Train xong ~10s | Đang `--smoke` — bỏ flag |
| `CUDA out of memory` | `CUDA_VISIBLE_DEVICES=1` và không mở job khác trên GPU1 |
| `python` not found | Quên `conda activate .../conda-env` trong tmux |
| Seeds path miss | File phải nằm `ingestion-worker/config/od_pairs.quan4.seeds_l3.json` |

---

## Checklist nhanh

- [ ] `git pull` code mới  
- [ ] Bundle giải → mọi path `OK`  
- [ ] Smoke CPU `ROBUST_TRAIN_OK`  
- [ ] Full train GPU1 không `--smoke`  
- [ ] Gửi `summary.json` v5 (+ v0 nếu có)
