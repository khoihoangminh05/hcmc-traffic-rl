# Paper outline — MAPPO micro next-hop (Quận 4)

## Title

Multi-Agent Next-Hop Routing under Alley Congestion: MAPPO on a Quận 4 Twin

## Claim

MAPPO agents selecting **outgoing edges** under BPR loads + peak-aware twin reduce fleet travel vs selfish Dijkstra / random next-hop (and approach load-aware greedy).

## Experiments

- N=16, max_degree=6, max_steps=64, OD ≥6 hops & ≥400 m  
- Baselines: Dijkstra next-hop, random, greedy-load  
- Ablation: IPPO  
- Metrics: fleet mean, CVaR90, congestion  
- Appendix: macro K-path (too constrained / lost to greedy)

## Limitations

BPR stylized; Mapbox≠probe; no field GPS; single district WCC.
