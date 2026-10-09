# Paper outline — Uncertainty-aware alley routing (Quận 4)

> Camera-ready skeleton. Claim lock: [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md).  
> Limitations: [L5_LIMITATIONS.md](./L5_LIMITATIONS.md).

## Title (working)

Uncertainty-Aware Alley Routing on a Sparse Urban Twin: Quận 4, Ho Chi Minh City

## Abstract (1 đoạn)

Motorbike traffic in Vietnamese alley networks is poorly observed: Mapbox OD samples are sparse, cameras cannot see interior hẻm, and OSM coverage is incomplete. We build a Quận 4 alley-core twin that fuses time-bucketed Mapbox seeds into edge density with calibrated **uncertainty**, then learn an **UncertaintyAwareKPath (UAKP)** policy that selects among K candidate routes using uncertainty-aware observations and a risk-sensitive reward. On held-out OD×time splits, UAKP reduces gap-to-oracle versus certainty-blind Dijkstra and prefer-alley/main heuristics; ablations isolate the value of the uncertainty channel and risk coefficient λ.

## 1. Introduction

- Problem: alley routing under sparse, uncertain density  
- Why binary “prefer alley” RL is insufficient (and our legacy result was too easy)  
- Contribution triad: twin+u · UAKP · eval protocol  

## 2. Related work

- Urban digital twins / traffic state estimation  
- Route choice / RL for routing  
- Risk-sensitive / uncertainty-aware planning  

## 3. Alley twin with uncertainty (Method A)

- OSM WCC alley-core domain  
- Mapbox fusion, `min_positive`, interpolation hops → `uncertainty` levels  
- Optional camera secondary at entries  
- Figures: peak `k` maps; uncertainty histogram  

## 4. UncertaintyAwareKPath (Method B)

- Candidate generation (weighted shortest + simple-path diversity), K=8  
- Observation: OD embeddings, t, dens stats, **unc stats**, per-path features  
- Reward: `-(T + λ · Σ u_e ℓ_e)`  
- PPO training, early-stop on val risk-adjusted travel  

## 5. Experiments

- Setup: WCC graph, 379 seeds → connected OD pool, train/val/test  
- Baselines: Dijkstra-mean, Dijkstra-ignore-u, prefer-alley, prefer-main, random-K, oracle-K  
- Metrics: travel, risk-adjusted, gap-to-oracle-K  
- **Stochastic realization:** edge times scaled by noise ∝ `uncertainty` → mean & CVaR90 (main uncertainty-aware table)  
- Ablations: `--no-uncertainty`, `λ=0`  
- Tables via `uakp_metrics_table`; learning curves from `metrics.jsonl` / `uakp_plot_curves`  
- Legacy note (appendix): binary v5 triviality  

## 6. Limitations & ethics

→ [L5_LIMITATIONS.md](./L5_LIMITATIONS.md)

## 7. Conclusion

- One claim restated; future: multi-agent congestion / GPS validation  

## Figures / tables checklist

| ID | Content |
|----|---------|
| Fig1 | Schematic twin → UAKP |
| Fig2 | Map k (morning/afternoon/evening) |
| Fig3 | Uncertainty levels histogram |
| Fig4 | Learning curve (gap / risk_adj) |
| Fig5 | Ablation bars |
| Tab1 | Main vs baselines (test) |
| Tab2 | Ablation ±u ±λ |
| Tab3 | Twin QA (observed %, unc levels) |
