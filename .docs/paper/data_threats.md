# Data and Threats to Validity (draft 2026-11-05)

Status note, not for the paper. English draft. Update the numbers after the crawl ends on 7 Nov; Mapbox figures below are from the check on 1 Nov. Results sentences wait for held-out runs.

## Data

**Network.** District 4 of Ho Chi Minh City from OpenStreetMap: the largest weakly connected subgraph, 886 nodes and 1828 directed links, 1460 of them alleys, with a median link length of 17.6 m. OpenStreetMap gives no width or lane count for any alley link. Signals come from OpenStreetMap and 3 links end at a signal.

**Speeds.** We queried the Mapbox Directions API (`driving-traffic`) on 100 designed probe routes, with live queries every 10 minutes and historic-profile (`depart_at`) queries at 15-minute slots for one week. 84.8% of driven distance matched our links, giving measurements on 1098 of 1828 links and 880 of 1460 alleys. Live speeds were nearly identical to the profile (ratio p10, p50, p90 of 1.00), and congestion labels were absent on alleys. We therefore treat Mapbox as an hourly speed profile rather than a real-time measurement, and we make no claim about the data other providers hold. A token failure lost most of 31 October (reported, not imputed).

**Demand.** Demand is synthetic, because no free origin-destination data exist for these alleys. Origins are drawn in proportion to adjacent alley length, destinations from 32 zones spread by farthest-point sampling, with a share directed to central hot zones and a peaked departure profile. Levels were chosen by the congestion index they produce, not from counts. Results are thus conditional on these scenarios, which we sweep.

**Simulation.** SUMO 1.28 with the sublane model. Motorbike parameters are drawn from the literature where available and otherwise swept; none is calibrated for alleys.

**Information limits.** The same limits apply to every controller: 20% of fleet reports lost, 10% lognormal time error, 90% compliance, 30% of background traffic on another routing app. These values are assumptions and are swept.

## Threats to validity

*Construct.* J weights all-trip and customer time equally by choice, and we vary the weight. Teleports remove vehicles from a jam without a travel-time cost, so scores depend on the teleport time; we report results at 300 and 600 s and split teleports by cause. Unfinished trips count a lower bound on their remaining time, which favours controllers that leave more vehicles unfinished, so arrival share is always reported beside J.

*Internal.* Checkpoints and baseline settings are selected on seeds 50000+ and reported on 60000+. Controllers share the environment and event schedule, but report noise and compliance draws are not common random numbers, which adds variance to paired comparisons. Several training seeds are used for each configuration because one run is not evidence.

*External.* (1) Demand is synthetic. (2) Alley geometry is partly assumed: widths come from a labelled sample at best, and two-way alleys are modelled as separate directed lanes with no opposing conflict. SUMO's opposite-direction driving was not compatible with the sublane model as of Lopez et al. (2018); check for 1.28. In a local check (2 seeds), the assumed width changed baseline scores by up to about a factor of two and reversed the order of two baselines, so we report results per width. (3) Junction behaviour at alley merges is uncalibrated: we found no measured gap acceptance for alley-to-road merges, and available motorcycle values come from T-junctions elsewhere. (4) Only one district is studied, and we claim no transfer. (5) Compliance is assumed; field values for cars are lower than our default, and motorbike values are unknown. (6) Everything is in simulation, so no benefit is claimed for real deployment.

*Conclusion.* Paired bootstrap intervals over demand seeds, Holm correction over pre-declared comparisons. Differences below about 3-4% on 48 pairs were not distinguishable in baseline measurements, so smaller gains need the larger seed count in the protocol.

*Ethics and side effects.* Coordinating routes shifts load and delay between people. We report load on alleys, non-customer delay and the share of users made worse off, because a lower mean can hide harm to residents (Kuncheria et al., 2023).
