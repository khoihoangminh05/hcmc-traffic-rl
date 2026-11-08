#!/bin/bash
# D1 early: UE vs SO_x on OD v3, meso with junction control and motorcycles 3 files per lane, fleet 6000, 6 seeds
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh; conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
D=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6; cd $D/v14src/ml-core
export PYTHONPATH=. CUDA_VISIBLE_DEVICES= ROUTING2_GRAPH=$D/net_full2/graph/alley_graph_full_v3.json
python -u -m routing2.gate_msa --demand v3 --tph 6000 --seeds 40010 40011 40012 40013 40014 40015 --modes ue so_x --iters 15 \
  --horizon 2700 --drain 900 --fresh-seeds 71 72 73 --jobs 12 --tag m1moto --net-dir $D/net_full2 --out-dir $D/msa15 \
  --lateral -1 --teleport-s 300 --sumo-extra "--mesosim true --meso-junction-control true" --vtype-extra 'length="0.5" minGap="0.2"'
echo MSA_EXIT $?
