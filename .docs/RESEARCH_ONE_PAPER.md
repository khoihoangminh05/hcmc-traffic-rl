# One paper (locked) — MAPPO micro next-hop alley routing (Quận 4)

> **Main claim:** MAPPO (CTDE) đa agent chọn **cạnh kế (micro)** trên twin hẻm + BPR congestion.  
> Macro K-path / UAKP / binary → **legacy**; micro v1 full run **không đạt** pass (xem audit).

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
Eval: fleet mean/CVaR **và arrival_rate** vs Dijkstra / random / greedy-load next-hop.

## Artifact

| | |
|--|--|
| Config | `quan4_mappo_micro.yaml` (`mappo_micro_v2f`) |
| Env / train | `mappo_micro_env.py`, `mappo_micro_train.py` |
| Audit | `python -m marl_agent._audit_v1_failure` |
| Sol1 | [SOL1_MAPPO.md](./SOL1_MAPPO.md) |

## v1 run (sol1) — facts

From summary `mappo_micro_v1` seed42:

| policy | fleet_mean | congestion |
|--------|------------|------------|
| greedy | 912 | 0.94 |
| random | 2126 | 2.08 |
| Dijkstra | 5410 | 2.57 |
| MAPPO test | 5517 | **57.8** |

Early-stop best val ~4038 @ update 50. MAPPO không thắng baseline trên fleet.

## Evidence sau audit (local, cùng OD filter)

`python -m marl_agent._audit_v1_failure` + đo `true_arr` (tới đích thật, không tính truncate-forced done):

| policy | fleet (approx) | true arrival /16 | hit horizon |
|--------|----------------|------------------|-------------|
| Dijkstra | ~4–6k | **~1.0** | finishes ~66 steps |
| random | low on old metric / high after fair truncate | **~0** | always horizon |
| greedy | looked best on old fleet | **~0.12–0.18** even at max_steps 400 | loops / local minima |
| always action0 | extreme | 0 | collapse signature |

**Kết luận có bằng chứng:**

1. **Metric cũ lệch:** so `fleet_mean` với random/greedy không công bằng — chúng gần như không tới đích; Dijkstra chịu BPR nhưng **arrival=1**.
2. **Greedy không phải “baseline mạnh” theo arrival** — tăng horizon lên 400 cũng không cứu (arr~0.18). BC clone greedy có thể hại.
3. MAPPO v1 cong~58 cùng hướng với policy xấu (action0), nhưng **chưa chứng minh** cơ chế collapse cụ thể từ log entropy.
4. Team-mean reward **không tự động sai** (MAPPO paper dùng shared reward); per-agent GAE = thí nghiệm.

**Giả thuyết còn mở** (có code, chưa có full retrain chứng minh): live occupancy; BC **Dijkstra**; reward shaping.

## v2b full run (sol1) — facts từ metrics

- Best @125 val fleet~9594 arr~0.16; test fleet~9205 arr~0.23 — **không** `beats_dijkstra_fair`
- Train fleet @125 ~5090 (gần Dijkstra) nhưng **greedy/val lệch**; sau u125 val cong nổ (65→200+)
- Entropy sau BC thấp (~0.14) rồi ~0.5 — không phải collapse entropy muộn

## v2c (theo metrics v2b)

- Eval ckpt = **stochastic** (khớp train); log thêm greedy
- Early-stop score = fleet + 12000*(1−arr)
- BC ngắn hơn (40), LR thấp hơn, entropy 0.08, clip 0.15
- **Không đủ** — BC vẫn undertrained

## Root cause (local probe) → v2d

- Obs progress ≡ Dijkstra next-hop **100%** — không phải thiếu feature
- BC cũ (PPO lr, ~1 epoch) dừng ở CE~0.87 ≈ **acc~0.42** → ~36-hop path fail chắc
- BC riêng Adam `lr=1e-3`, multi-epoch → **acc≥0.999**, greedy/stoch arr≈1.0
- Cold critic sau BC → value loss khổng lồ → PPO đạp mất clone
- v2d: BC tới `target_acc=0.98`, fit critic, abort nếu greedy arr&lt;0.85, entropy/LR thấp, seed `best.pt` = BC

## Fair compare (v2e→v2f)

Trước đây policy eval seed `50_000+ep`, baseline `70_000+ep` → **khác OD/episode**.
`evaluate_fair_suite`: lock OD; cùng `(seed, t, ods)` + `env.step`. `beats_dijkstra_fair` = greedy vs Dijkstra.
v2f thêm: early-stop/ckpt theo greedy (không trộn stoch); BC paired fleet-ratio gate trước PPO.

## Pass (cập nhật)

- [ ] `MAPPO_MICRO_ENV_TESTS_OK`
- [ ] Full sol1 → `MAPPO_MICRO_TRAIN_OK` (`mappo_micro_v2f`)
- [ ] `beats_dijkstra_fair` (paired)
- [ ] Ablation `--ippo` (sau baseline v2f)
- [ ] Limitations trung thực (BPR, metric, greedy arrival yếu)
