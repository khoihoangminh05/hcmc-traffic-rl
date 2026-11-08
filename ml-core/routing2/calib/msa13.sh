#!/bin/bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh; conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
D=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6; cd $D/v12src/ml-core
export PYTHONPATH=. CUDA_VISIBLE_DEVICES= ROUTING2_GRAPH=$D/net_full2/graph/alley_graph_full_v3.json
python -u -m routing2.gate_msa --demand v3 --tph 6000 9000 --seeds 40010 40011 --modes ue so_x --iters 15 --horizon 2700 --drain 900 \
  --fresh-seeds 71 72 73 --jobs 8 --tag v3meso --net-dir $D/net_full2 --out-dir $D/msa13 --lateral -1 --teleport-s 300 \
  --sumo-extra "--mesosim true --meso-junction-control false --meso-tls-penalty 1 --meso-tauff 0.57 --meso-taufj 0.57 --meso-taujf 0.87 --meso-taujj 0.7"
echo MSA_EXIT $?
