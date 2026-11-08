#!/bin/bash
# MAPPO on the full Q4 net, OD v3, demand v2 with other districts, scenario mix. $1 = tag, $2 = meso junction control (true/false)
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh; conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
D=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6; cd $D/v12src/ml-core
export PYTHONPATH=. CUDA_VISIBLE_DEVICES=1 ROUTING2_GRAPH=$D/net_full2/graph/alley_graph_full_v3.json
if [ "$2" = "true" ]; then EX="--mesosim true --meso-junction-control true"; else EX="--mesosim true --meso-junction-control false --meso-tls-penalty 1 --meso-tauff 0.57 --meso-taufj 0.57 --meso-taujf 0.87 --meso-taujj 0.7"; fi
python -u -m routing2.sumo_marl --demand v3 --zones 85 --net-dir $D/net_full2 --runs-dir $D/runs13 --tag $1 \
  --sumo-extra "$EX" --sd '{"every": 30, "a": 0.6, "b": 1, "k0": 0.1}' \
  --horizon 1800 --tph 1500 9000 --eval-tph 3000 6000 9000 --eval-seeds 8 --eval-every 25 --eval-drain 900 \
  --surge-prob 0.3 --surge 1.3 1.8 --forced-mult 1 3 --incident-rate 2 --school-rate 1 \
  --reward attrib --prior 60 --prior-rule greedy --greedy-queue 0.5 --teleport-s 300 \
  --workers 16 --episodes 16 --updates 200 --device cuda --seed 42
echo TRAIN_EXIT $?
