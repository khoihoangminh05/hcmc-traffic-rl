# MAPPO trên sol1 — train chính

> Lock: [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md)  
> **Không** train UAKP/binary làm main result.

```bash
cd ~/hcmc-traffic-rl && git pull
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
export PATH="/mnt/data8tb/minhkhoi/tools-env/bin:$PATH"
cd ~/hcmc-traffic-rl/ml-core

python -m marl_agent.test_mappo_env

tmux new -s mappo_v1
# re-activate conda trong tmux
mkdir -p /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs
LOG=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/mappo_$(date +%Y%m%d_%H%M%S).log

CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.mappo_train \
  --config marl_agent/configs/quan4_mappo.yaml \
  --device cuda \
  2>&1 | tee "$LOG"
```

Kỳ vọng: `[mappo_train] mode=FULL N=16 K=8` → `MAPPO_TRAIN_OK`.

### Ablation IPPO

```bash
CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.mappo_train \
  --config marl_agent/configs/quan4_mappo.yaml --device cuda --ippo
```

### Kiểm tra

```bash
RUN=$(ls -dtd /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/quan4_mappo_* | head -1)
cat "$RUN/summary.json"
```

Pass: `fleet_mean` / `fleet_cvar90` / `congestion` của policy **tốt hơn** `baselines.all_dijkstra`.
