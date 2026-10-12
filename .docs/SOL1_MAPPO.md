# MAPPO MICRO trên sol1

> Lock: [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md)  
> Config: `quan4_mappo_micro.yaml` (next-hop). Macro `quan4_mappo.yaml` = legacy.

```bash
ssh -p 8000 minhkhoi@sol1.swin.edu.vn
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
export PATH="/mnt/data8tb/minhkhoi/tools-env/bin:$PATH"

cd ~/hcmc-traffic-rl && git pull
cd ml-core
python -m marl_agent.test_mappo_micro_env

tmux new -s mappo_micro
# re-activate conda
mkdir -p /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs
LOG=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/mappo_micro_$(date +%Y%m%d_%H%M%S).log

# n_envs=32 subproc + APSP-cached env + minibatch 8192 (4090). Watch: nvidia-smi / htop
CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.mappo_micro_train \
  --config marl_agent/configs/quan4_mappo_micro.yaml \
  --device cuda \
  2>&1 | tee "$LOG"
```

Boot: `mappo_micro_v2h`. Bắt buộc thấy `[preflight] spawn embed parity OK`.
BC abort trừ khi: holdout_acc≥0.995, paired greedy arr≥0.98, ratio≤1.10,
closed_loop_agree≥0.95. PPO: freeze actor 75 updates (chỉ train critic).
Pass: `beats_dijkstra_fair` (greedy paired). `best_u=0` + greedy thua Djk = fail BC.


Ablation IPPO: thêm `--ippo`.

Xong:

```bash
RUN=$(ls -dtd /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs/quan4_mappo_micro_* | head -1)
cat "$RUN/summary.json"
```

Pass: `MAPPO_MICRO_TRAIN_OK` + thắng Dijkstra **và** random trên `fleet_mean` (greedy càng gần càng tốt).
