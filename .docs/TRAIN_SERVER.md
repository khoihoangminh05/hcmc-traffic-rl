# Train MARL Quận 4 trên GPU server (H100-ready)

**Lệnh một phát:** xem [TRAIN_NOW.md](./TRAIN_NOW.md).  
**Cải tiến data sau v0:** [ENV_UPGRADE_L1_L5.md](./ENV_UPGRADE_L1_L5.md).

## Artifact bắt buộc trên server

| Path | Bắt buộc |
|------|----------|
| `ml-core/artifacts/out/quan4/alley_graph.json` | Có |
| `ml-core/artifacts/out/quan4/density/alley_density_latest.json` | Có |
| `ingestion-worker/config/od_pairs.quan4.seeds.json` | Có |
| `ml-core/marl_agent/configs/quan4_h100.yaml` | Có |

## Cơ chế chống train bậy (đã bật)

| Cơ chế | Ý nghĩa |
|--------|---------|
| `obs_mode: compact` | Tránh obs ~20k dim |
| Train/val/test OD split | Không leak eval |
| PPO clip + grad clip + adv normalize | Ổn định PG |
| Early stopping + restore best | Không lấy last epoch bừa |
| Val hyper-adapt | Plateau → giảm LR/entropy; nội suy về best |
| NaN / infinite travel guard | Abort sớm |
| `data_tag` + `hyperparameters.snapshot.yaml` | Repro / so version data |

## Metric

1. `val_travel_time` ↓ (early-stop)  
2. `val_regret` → 0  
3. `val_action_acc` ↑  
4. Cuối run: `summary.json` (`test_*`)

## Output mỗi run

```
artifacts/out/quan4/marl_runs/<name>_<data_tag>_<utc>_seed42/
  hyperparameters.snapshot.yaml
  od_split.json
  metrics.jsonl
  metrics_train.csv
  adapt_history.json
  best.pt / last.pt
  summary.json
  run_meta.json
```

Copy: `artifacts/out/quan4/marl/best_robust.pt`, `robust_summary.json`.

## Camera

Camera **không nhìn vào hẻm** → không phải nguồn chính cho `k` trong hẻm. Chỉ dùng như prior thứ cấp (L4 trong ENV_UPGRADE).
