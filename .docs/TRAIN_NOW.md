# Train sol1 — MAPPO MICRO (main)

> [SOL1_MAPPO.md](./SOL1_MAPPO.md) · [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md)

```bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
export PATH="/mnt/data8tb/minhkhoi/tools-env/bin:$PATH"
cd ~/hcmc-traffic-rl && git pull && cd ml-core
python -m marl_agent.test_mappo_micro_env          # expect MAPPO_MICRO_ENV_TESTS_OK

# v3a: MDP fix (reward = marginal BPR travel, rank-ordered contention obs,
# per-agent GAE, critic = global ⊕ own obs, BC teacher = greedy_load).
# 1) MDP probe (CPU, ~2 min) — expect obs_regret_argmin_matches_greedy_load = 1.0,
#    greedy_load ≈ 780s vs dijkstra ≈ 5830s (val n=24)
python -m marl_agent.probe_mdp_alignment --out probe_mdp_alignment.json

# 2) BC-only preflight (no PPO) — expect [bc] ratio_vs_teacher≤1.10, agree≥0.95
CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.mappo_micro_train \
  --config marl_agent/configs/quan4_mappo_micro.yaml --device cuda --bc-only \
  2>&1 | tee bc_only_v3a.log

# 3) Full run. Boot tag mappo_micro_v3a. Real bar = beats_greedy_load_fair.
CUDA_VISIBLE_DEVICES=1 nohup python -u -m marl_agent.mappo_micro_train \
  --config marl_agent/configs/quan4_mappo_micro.yaml --device cuda \
  > train_v3a.log 2>&1 &
```
