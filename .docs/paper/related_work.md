# Related Work (draft 2026-11-04)

Status note, not for the paper. Written from reading the papers in `papers/`, with notes in `.docs/lit/reading/`, by one reader without figures. Not yet read in full: Wolpert and Tumer, Graf and Harks, Kuncheria; Kaddoura only pp.3-8. No Scopus or Web of Science run yet, so "we found no" must stay limited to the search reported. Preprints marked [pre] need their published version. Fill in numbers for our method only after the held-out evaluation.

## 2.1 Selfish routing and the system optimum

When drivers minimise their own travel time, the network settles at a user equilibrium whose total travel time can exceed the system optimum; for linear latencies the ratio is at most 4/3 (Roughgarden and Tardos, 2002). Such bounds assume latencies that depend only on a link's own flow, which fails under spillback and at priority junctions. The usual route to the optimum charges each user its marginal cost, by tolls learned from local flow (Ramos et al., 2020), analytic marginal travel times on static BPR links (Wang et al., 2025 [pre]), or surrogates in microscopic assignment (Yun et al., 2024).

## 2.2 Learning to route

Three designs dominate. *Pre-trip* route choice is the most developed on large real networks: RouteRL (Akman et al., 2025) and the URB benchmark (Akman et al., 2025) let autonomous vehicles pick a route before departure, and URB reports that state-of-the-art MARL rarely beats human drivers, with MAPPO close to random after 6000 episodes and much worse under high demand. *Aggregate* controllers set flows or splits: one agent per OD pair in static assignment (Wang et al., 2025 [pre]), a central agent on OD proportions with sparse sensors (Ke et al., 2025), or regional guidance on an MFD (Jiang et al., 2024; Hosseinzadeh et al., 2023). *En-route next-hop* control is closest to ours and is smaller in scale: Koh et al. (2020) on 40-80 edges, Shou et al. (2022) on 69 nodes with selfish agents, Ma and He (2024) on 13 nodes with a provider suggesting routes, and Yun et al. (2024) in SUMO on up to 87 nodes with a system-optimal objective and a non-compliance parameter, at full penetration with a network-wide state. MA-GRL (Mahmoud et al., 2026) combines MAPPO and a GAT per vehicle among 2847 background vehicles in Monaco, with 100 controlled vehicles, a hand-weighted penalty for simultaneous route changes, and a stated limit near 200 agents.

## 2.3 Credit assignment

Difference rewards (Wolpert and Tumer, 2001; Castellini et al., 2022) and counterfactual baselines (Foerster et al., 2018) separate an agent's contribution from the team reward, but have been tested with tens of agents, and Castellini et al. lose their guarantee under partial observability. In routing, Psarou et al. (2025 [pre], 2026 [pre]) add a counterfactual marginal cost to the reward, which needs repeated simulations even in the selective form. Without re-simulation, Jiang et al. (2024) compute a difference reward from a regional MFD, and Ramos et al. (2020) use a local toll. Kaddoura and Kickhöfer (2014) attribute queue delay to individual agents to set tolls, not to train a policy. We found no study that checks a re-simulation-free per-vehicle charge against measured counterfactual delay in a microscopic simulator.

## 2.4 Partial participation, compliance and information

Benefits generally grow with penetration in the large simulations we read (Chan et al., 2023 [pre], with a knee near 70%; Folsom et al., 2022), while rule-based partial penetration can give almost no gain at some settings (Kamiński et al., 2020). Reactive information can itself cause harm: oscillation appears when all vehicles respond to a shared prediction (Bittihn and Schadschneider, 2021 [pre]), and rerouting thresholds are the most influential parameter of a metropolitan rerouting model (Chan et al., 2023 [pre]). Compliance is usually a free parameter, and realised values are lower than often assumed: on Kakao Mobility, path compliance was about 68-73% and a cited narrow alley had 91% non-compliance, for cars (Kim et al., 2025). Hosseinzadeh et al. (2023) show that a controller that assumes full compliance loses more when compliance falls. Li and Duan (2024) treat information as endogenous, because routes taken decide what is observed, but on small parallel networks without deep learning. In the strongest field evidence, Google added a fixed externality cost on about 100 historically congested segments in 10 US cities, in a switchback experiment on under 2% of trips. Median speed rose about 2% on targeted segments and 0.35% on all affected ones, with travel times improved 0.7% (Arora et al., 2026). The authors call existing app routing essentially individualistic, and leave open how much more optimal dynamic penalties could achieve. Rerouting stayed within roads of equivalent class, so it says nothing about alleys.

## 2.5 Motorcycle-dominated traffic

Microsimulation of such traffic is mostly calibrated at corridors and signalised junctions, in VISSIM (Vu and Preston, 2023) and SUMO (Salawavidana et al., 2026); Chouta and Facchi (2026) add lean-angle behaviour to SUMO without calibrating delay. The largest network we found is Ninh Kieu, Vietnam (Fadilah et al., 2024), with 519 nodes and 1533 links in AIMSUN, 91.57% motorcycles and a recursive-logit route choice from a stated-preference survey. It mentions alleys in the road hierarchy, but reports no alley-specific widths, capacities or results, and does not optimise coordination. We found no calibrated values for merging from an alley into a road; motorcycle critical gaps of 2.3-3.3 s were measured at T-intersections in Malaysia (Ibrahim and Sanik, 2007), against 3.2-4.2 s for cars, and Patil and Sangole (2016) report similar values in India (second-hand so far). None concerns an alley entrance.

## 2.6 Graph and attention architectures

GNNs are mostly used as surrogates that learn equilibrium flows (Liu and Meidani, 2024 [pre]; Lassen et al., 2025 [pre]; Rahman and Hasan, 2022 [pre]). As policy encoders, attention with masked decoding and residual connections work for static routing problems (Kool et al., 2019; Lei et al., 2021 [pre]). MA-GRL is the one traffic-control example we read; it reports 87% zero-shot retention across three cities, and is limited by the agent count above.

## 2.7 Positioning

| Work | Agent | Decision | Network (nodes/links) | Controlled | Simulator | p < 1 | Compliance | Information limits | Credit, and how |
|---|---|---|---|---|---|---|---|---|---|
| URB 2025 | CAV | pre-trip | 29 nets | 40% of 222-1035 | SUMO | yes | no | past choices | selfish or group |
| Psarou 2026 [pre] | AV | pre-trip | up to 2173/4216 | about 414 at 40% | SUMO | yes | no | estimate from earlier vehicles | counterfactual, re-simulated |
| Yun 2024 | central Q, then per user | next-hop | 13/19; 87/206 | 600; 720 | SUMO | no | eta mixture | none | none (link time) |
| Ma & He 2024 | CAV + provider | next-hop | 13 nodes | 960 | own | no | endogenous | none | none |
| Shou 2022 | vehicle | next-hop | 69/166 | 120 | SUMO | yes | no | node and time | selfish |
| MA-GRL 2026 | vehicle, GAT | route at decision points | Monaco, sizes to check | 100 | SUMO | yes | no | 3-hop local | hand penalty |
| Ke 2025 | one agent | OD split, 15 min | up to 361/621 | n/a | CTM | yes | n/a | 14 sensors | none |
| Jiang 2024 | vehicle, regional | region | 7 regions | not stated | trip-based | yes | per-vehicle label | coarse | difference, from MFD |
| Fadilah 2024 | none (logit) | route choice | 519/1533 | none | AIMSUN | fluctuating | survey 35.6% | n/a | none |
| **This work** | vehicle, GNN | next-hop | 886/1828, alleys explicit | p x demand, thousands | SUMO | yes | per decision | report loss, noise | measured queue delay, re-simulation check **to be done** |

## 2.8 Gap, stated narrowly

We found no work that coordinates a fleet with a learned policy at next-hop level in a microscopic simulator on a network whose alley links are modelled separately, with partial penetration, per-decision non-compliance and imperfect reports together. Each element exists alone. The claim only carries value if (a) the interaction of these factors is measured, and (b) the per-vehicle charge passes a counterfactual check. Do not claim "first" for next-hop RL, non-compliance, provider suggestions, re-simulation-free credit, or largest network.
