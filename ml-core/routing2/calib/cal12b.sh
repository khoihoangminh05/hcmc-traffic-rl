#!/bin/bash
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh; conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
D=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6; cd $D/v12src/ml-core
export PYTHONPATH=. CUDA_VISIBLE_DEVICES= ROUTING2_GRAPH=$D/net_full2/graph/alley_graph_full_z.json
python -u $D/cal12b.py "$@"
echo CAL_EXIT $?
