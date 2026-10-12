# Train sol1 — MAPPO MICRO (main)

> [SOL1_MAPPO.md](./SOL1_MAPPO.md) · [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md)

```bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
export PATH="/mnt/data8tb/minhkhoi/tools-env/bin:$PATH"
cd ~/hcmc-traffic-rl && git pull && cd ml-core
python -m marl_agent.test_mappo_micro_env

# v2f: BC gate + paired fair + greedy early-stop. Boot: mappo_micro_v2f
# Expect [bc] target_acc=0.98, greedy arr≥0.85, paired fleet ≤1.35× Dijkstra.
# Expect [fair] paired eval … beats_dijkstra_fair=…
CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.mappo_micro_train \
  --config marl_agent/configs/quan4_mappo_micro.yaml --device cuda
```

