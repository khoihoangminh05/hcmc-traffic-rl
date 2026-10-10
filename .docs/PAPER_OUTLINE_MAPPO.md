# Paper outline — MAPPO multi-agent alley routing (Quận 4)

> Lock: [RESEARCH_ONE_PAPER.md](./RESEARCH_ONE_PAPER.md) · Sol1: [SOL1_MAPPO.md](./SOL1_MAPPO.md)

## Title (working)

Multi-Agent Path Choice under Alley Congestion: MAPPO on a Quận 4 Density Twin

## Abstract

Sparse Mapbox/OSM twins leave alley capacity and uncertainty poorly observed. We train **MAPPO (CTDE)** so N agents jointly select among K routes on a Quận 4 WCC twin with **BPR congestion**, multi-objective rewards (travel, social, risk, fairness, congestion), beating selfish Dijkstra / random / greedy-load and IPPO ablation on fleet mean/CVaR and congestion index.

## Sections

1. Intro — why single-agent UAKP/binary was too easy; need joint congestion  
2. Related work — MARL traffic, MAPPO, urban twins  
3. Twin + BPR congestion game  
4. MAPPO architecture (shared actor, central critic)  
5. Experiments — N=16, K=8; baselines; IPPO ablation; learning curves  
6. Limitations — [L5_LIMITATIONS.md](./L5_LIMITATIONS.md)  
7. Conclusion  

## Figures / tables

| ID | Content |
|----|---------|
| Fig1 | Schematic N agents → loads → BPR |
| Fig2 | Twin k/u peaks |
| Fig3 | Learning curve fleet_mean / congestion |
| Fig4 | Congestion comparison bars vs Dijkstra/random/greedy |
| Tab1 | Main MAPPO vs baselines (test) |
| Tab2 | IPPO ablation |
| Tab3 | Reward-weight sensitivity (optional) |

## Appendix

- Binary v5 & UAKP single-agent results (too easy / equal Dijkstra)
