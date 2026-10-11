# One paper (locked) — MAPPO micro next-hop alley routing (Quận 4)

> **Main claim:** MAPPO (CTDE) đa agent chọn **cạnh kế (micro)** trên twin hẻm + BPR congestion.  
> Macro K-path / UAKP / binary → **legacy appendix** (quá dễ hoặc thua greedy trên travel).

```mermaid
flowchart LR
  twin[Twin_k_u_peak] --> obs[Local_obs_time_peak_neighbors]
  obs --> actor[Shared_Actor_next_hop]
  actor --> step[Sync_step_BPR_loads]
  step --> rew[Travel_aligned_reward]
  rew --> critic[Central_Critic_GAE]
```

## Bài toán

N=16 agent; mỗi bước chọn **1 outgoing edge** (masked); horizon tới đích / `max_steps`.  
OD lọc **≥6 hops và ≥400 m**. Time trong state: `t_norm` + **peak one-hot** + density peak.  
Reward: **travel-dominant** (+ mild congestion/risk). Eval: fleet mean/CVaR vs Dijkstra / random / greedy-load next-hop.

## Vì sao micro

Macro K-path nhốt policy trong menu path; greedy tuần tự thắng travel.  
Micro = điều hướng thật, đổi hướng theo load/local obs, time/peak có đất diễn.

## Artifact

| | |
|--|--|
| Config | `marl_agent/configs/quan4_mappo_micro.yaml` |
| Env / train | `mappo_micro_env.py`, `mappo_micro_train.py` |
| Sol1 | [SOL1_MAPPO.md](./SOL1_MAPPO.md) |
| Outline | [PAPER_OUTLINE_MAPPO.md](./PAPER_OUTLINE_MAPPO.md) |
| Legacy macro | `quan4_mappo.yaml` |

## Pass

- [ ] `MAPPO_MICRO_ENV_TESTS_OK`  
- [ ] Full sol1 → `MAPPO_MICRO_TRAIN_OK`  
- [ ] `beats_dijkstra_mean` và **`beats_random_mean`** (ideal: gần / thắng greedy)  
- [ ] Ablation `--ippo`  
- [ ] Limitations trung thực (BPR stylized, Mapbox twin)  
