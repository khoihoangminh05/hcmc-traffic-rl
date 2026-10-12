# Train sol1 — MAPPO MICRO (main)

> [SOL1_MAPPO.md](./SOL1_MAPPO.md) · [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md)

```bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
export PATH="/mnt/data8tb/minhkhoi/tools-env/bin:$PATH"
cd ~/hcmc-traffic-rl && git pull && cd ml-core
python -m marl_agent.test_mappo_micro_env

# v2h: holdout BC + closed-loop agree + freeze actor + tight gates.
# Boot: mappo_micro_v2h
# Expect [preflight] spawn embed parity OK
# Expect [bc] holdout_acc≥0.995, paired arr≥0.98, ratio≤1.10, agree≥0.95
# Expect [fair] beats_dijkstra_fair (greedy paired)
CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.mappo_micro_train \
  --config marl_agent/configs/quan4_mappo_micro.yaml --device cuda
```

