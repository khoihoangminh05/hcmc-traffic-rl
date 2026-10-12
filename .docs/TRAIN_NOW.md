# Train sol1 — MAPPO MICRO (main)

> [SOL1_MAPPO.md](./SOL1_MAPPO.md) · [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md)

```bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
export PATH="/mnt/data8tb/minhkhoi/tools-env/bin:$PATH"
cd ~/hcmc-traffic-rl && git pull && cd ml-core
python -m marl_agent.test_mappo_micro_env

# v2e: v2d BC gate + paired fair test (same OD/t/seed). Boot: mappo_micro_v2e
# Expect [bc] reached target_acc=0.98 then greedy arr≥0.85 (else aborts).
# Expect [fair] paired eval … beats_dijkstra_fair=…
CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.mappo_micro_train \
  --config marl_agent/configs/quan4_mappo_micro.yaml --device cuda
```

