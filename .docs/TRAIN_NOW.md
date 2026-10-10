# Train trên sol1 — MAPPO (một paper)

> **Hướng dẫn chính:** [SOL1_MAPPO.md](./SOL1_MAPPO.md)  
> Research lock: [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md)

**Config chính:** `marl_agent/configs/quan4_mappo.yaml` (`mappo_v1`)  
**Legacy:** UAKP / binary v5 — appendix only.

```bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
export PATH="/mnt/data8tb/minhkhoi/tools-env/bin:$PATH"
cd ~/hcmc-traffic-rl && git pull && cd ml-core
python -m marl_agent.test_mappo_env

tmux new -s mappo_v1
# re-activate conda
LOG=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/mappo_$(date +%Y%m%d_%H%M%S).log
CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.mappo_train \
  --config marl_agent/configs/quan4_mappo.yaml --device cuda \
  2>&1 | tee "$LOG"
```

Ablation IPPO: thêm `--ippo`.  
Xem kết quả: `cat $RUN/summary.json` — cần `beats_dijkstra_mean` hoặc `beats_dijkstra_cvar` / cong.
