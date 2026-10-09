# UAKP trên sol1 — train chính (một paper)

> Research lock: [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md)  
> **Không** dùng `quan4_v5_final.yaml` (legacy binary).  
> **Không** `--smoke` cho paper run.

## 0) Sync code + twin

```bash
cd ~/hcmc-traffic-rl && git pull
# Twin WCC + peaks + seeds (nếu chưa có): unpack bundle như SOL1_PAPER_B.md §2
```

## 1) Env

```bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
export PATH="/mnt/data8tb/minhkhoi/tools-env/bin:$PATH"
cd ~/hcmc-traffic-rl/ml-core
python -m marl_agent.test_uakp_env   # phải in UAKP_ENV_TESTS_OK
```

## 2) Full train GPU1

```bash
tmux new -s uakp_v1
# inside tmux — re-activate conda
mkdir -p /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs
LOG=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/uakp_$(date +%Y%m%d_%H%M%S).log

CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.uakp_train \
  --config marl_agent/configs/quan4_uakp.yaml \
  --device cuda \
  2>&1 | tee "$LOG"
```

Dòng đầu: `[uakp_train] mode=FULL ... K=8`. Kết thúc: `UAKP_TRAIN_OK` + `summary.json`.

## 3) Ablations (cùng twin)

```bash
# no uncertainty channel
CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.uakp_train \
  --config marl_agent/configs/quan4_uakp.yaml --device cuda --no-uncertainty

# λ=0 (expected time only)
CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.uakp_train \
  --config marl_agent/configs/quan4_uakp.yaml --device cuda --risk-lambda 0
```

## 4) Bảng metrics

```bash
python -m marl_agent.uakp_metrics_table \
  /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/quan4_uakp_uakp_v1_*/summary.json \
  /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/quan4_uakp_uakp_v1_nou_*/summary.json \
  /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/quan4_uakp_uakp_v1_l0_*/summary.json
```

## Pass trước khi claim

- **Metric chính (uncertainty-aware):** `stochastic_test.policy.stoch_cvar90` **≤** `stochastic_test.dijkstra_mean.stoch_cvar90`  
  (hoặc gần cạnh + rõ tốt hơn `random_k`). Deterministic Dijkstra travel ≈ travel-oracle là **bình thường** (shortest nằm trong K).
- Policy **đánh bại random_k** trên travel và/hoặc CVaR  
- Ablation ±u / λ=0: bảng khác biệt  
- Learning curve: gap giảm dần, **không** kiểu binary `acc=100%` từ update 5  
- Không lấy `v5_l1l5` regret=0 làm main result  

> SSH từ máy dev có thể cần password/key — nếu `Permission denied`, chạy tay lệnh trong §2 trên sol1 sau `git pull`.
