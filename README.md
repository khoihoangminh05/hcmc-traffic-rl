# HCMC Traffic RL — Quận 4 alley twin + MARL

Digital twin hẻm Quận 4: Mapbox OD seeds → mật độ `k(t)` (nội suy) → SUMO + MARL `(t,O,D)→min travel time`.

**Camera không nhìn vào hẻm** → không phải nguồn chính cho `k` trong hẻm.

## Docs học & train

| File | Khi nào đọc |
|------|-------------|
| [.docs/LEARN_WITH_TEACHER.md](.docs/LEARN_WITH_TEACHER.md) | **Đọc số, hiểu, quyết định** (học cùng train) |
| [.docs/TRAIN_NOW.md](.docs/TRAIN_NOW.md) | Lệnh train trên sol1 |
| [.docs/SERVER_SOL1.md](.docs/SERVER_SOL1.md) | Thông số server |
| [.docs/ENV_UPGRADE_L1_L5.md](.docs/ENV_UPGRADE_L1_L5.md) | Cải tiến data sau baseline v0 |
| [.docs/PROGRESS.md](.docs/PROGRESS.md) | Tiến độ dự án |

## Train nhanh (sol1)

```bash
git clone <URL_REPO> ~/hcmc-traffic-rl
cd ~/hcmc-traffic-rl/ml-core
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install --index-url https://download.pytorch.org/whl/cu124 torch
# output → data8tb
mkdir -p /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs
ln -sfn /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs artifacts/out/quan4/marl_runs
nvidia-smi
CUDA_VISIBLE_DEVICES=1 python -m marl_agent.robust_train \
  --config marl_agent/configs/quan4_h100.yaml --device cuda
```

Chi tiết + cách kéo `summary.json` về: [.docs/TRAIN_NOW.md](.docs/TRAIN_NOW.md).
