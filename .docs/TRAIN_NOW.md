# Train trên sol1 — UAKP (một paper)

> **Hướng dẫn chính:** [SOL1_UAKP.md](./SOL1_UAKP.md)  
> Research lock: [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md)  
> Server: [SERVER_SOL1.md](./SERVER_SOL1.md).

**Config chính:** `marl_agent/configs/quan4_uakp.yaml` (`data_tag: uakp_v1`)  
**Legacy binary:** `quan4_v5_final.yaml` — không dùng cho claim paper.

**Không dùng** `python3 -m venv` / `apt` trên sol1.  
**Không** `--smoke` cho paper run.

---

## Đường dẫn chuẩn

| Thứ | Path |
|-----|------|
| Code | `~/hcmc-traffic-rl/` |
| Conda env | `/mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env` |
| Train runs | `/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs` |

---

## Mỗi lần SSH

```bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
export PATH="/mnt/data8tb/minhkhoi/tools-env/bin:$PATH"
cd ~/hcmc-traffic-rl && git pull
cd ml-core
python -m marl_agent.test_uakp_env
```

---

## ★ Full train UAKP (GPU1)

```bash
tmux new -s uakp_v1
# re-activate conda trong tmux
mkdir -p /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs
LOG=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/uakp_$(date +%Y%m%d_%H%M%S).log

CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.uakp_train \
  --config marl_agent/configs/quan4_uakp.yaml \
  --device cuda \
  2>&1 | tee "$LOG"
```

Kỳ vọng: `[uakp_train] mode=FULL ... K=8` → logs `[train]` / `[eval]` gap → `UAKP_TRAIN_OK`.

### Ablation

```bash
CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.uakp_train \
  --config marl_agent/configs/quan4_uakp.yaml --device cuda --no-uncertainty

CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.uakp_train \
  --config marl_agent/configs/quan4_uakp.yaml --device cuda --risk-lambda 0
```

### Bảng

```bash
python -m marl_agent.uakp_metrics_table path/to/*/summary.json
```

Chi tiết: [SOL1_UAKP.md](./SOL1_UAKP.md) · outline: [PAPER_OUTLINE_UAKP.md](./PAPER_OUTLINE_UAKP.md).
