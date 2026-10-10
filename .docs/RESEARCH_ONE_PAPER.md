# One paper (locked) — MAPPO multi-agent alley routing (Quận 4)

> **Research lock:** một conference paper. Twin hẻm + **MAPPO** đa agent dưới congestion.  
> UAKP single-agent / binary v5 → **appendix too-easy** (không còn claim chính).  
> Train: [SOL1_MAPPO.md](./SOL1_MAPPO.md).

```mermaid
flowchart LR
  twin[Twin_k_u_WCC] --> cand[K_paths_per_agent]
  cand --> actors[Shared_Actor_MAPPO]
  actors --> loads[Edge_loads_N_agents]
  loads --> bpr[BPR_plus_risk]
  bpr --> rew[Multi_obj_reward]
  rew --> critic[Central_Critic_CTDE]
```

---

## Bài toán

Mỗi episode peak `t`: **N=16** agent, mỗi agent một OD trên WCC Quận 4; mỗi agent chọn **1 trong K=8** path ứng viên. Load cộng trên cạnh; travel theo **BPR + density twin + capacity road_class**. Partial obs lúc act; critic trung tâm (CTDE).

### Ràng buộc

| | |
|--|--|
| Domain | Largest alley-core WCC |
| Capacity | Alley thấp (2–3); trục cao hơn |
| Congestion | BPR `α=0.15`, `β=4` + base `k` |
| OD | 50% episode correlated corridor |
| Action | Categorical(K) path — payoff **phụ thuộc joint** |

### Một claim

> Trên twin hẻm Quận 4, MAPPO điều phối đa agent chọn path dưới congestion + uncertainty giảm mean/CVaR fleet travel và chỉ số ùn tắc so với selfish Dijkstra / random / IPPO.

### Appendix (không claim chính)

- Binary `v5_l1l5`: regret=0, không phải MARL  
- UAKP 1-agent: gap=0 = Dijkstra — ceiling quá dễ  

Venue: ITSC / IEEE ITS workshop.

---

## Artifact

| Vai trò | Path |
|---------|------|
| **Train chính** | `marl_agent/configs/quan4_mappo.yaml` (`mappo_v1`) |
| Env / nets / train | `mappo_env.py`, `mappo_nets.py`, `mappo_train.py` |
| Sol1 | [SOL1_MAPPO.md](./SOL1_MAPPO.md) |
| Outline | [PAPER_OUTLINE_MAPPO.md](./PAPER_OUTLINE_MAPPO.md) |
| Legacy UAKP | `quan4_uakp.yaml` |
| Legacy binary | `quan4_v5_final.yaml` |

---

## Pass checklist

- [ ] Unit tests: N↑ → T↑ trên corridor; all-Dijkstra xấu hơn mixed khi cap thấp  
- [ ] Full train sol1 MAPPO → `MAPPO_TRAIN_OK`  
- [ ] MAPPO thắng All-Dijkstra trên fleet mean hoặc CVaR / congestion  
- [ ] Ablation IPPO (independent critic)  
- [ ] Tables + learning curves + limitations  
