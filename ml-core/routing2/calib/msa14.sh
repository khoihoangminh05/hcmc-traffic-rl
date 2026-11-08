#!/bin/bash
# UE vs SO_x on OD v3 with junction interactions: meso with junction control (m1) and micro with anti-deadlock (v3)
source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh; conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
D=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6; cd $D/v12src/ml-core
export PYTHONPATH=. CUDA_VISIBLE_DEVICES= ROUTING2_GRAPH=$D/net_full2/graph/alley_graph_full_v3.json
C="--demand v3 --tph 6000 --seeds 40010 40011 --modes ue so_x --iters 15 --horizon 2700 --drain 900 --fresh-seeds 71 72 73 --jobs 4 --net-dir $D/net_full2 --out-dir $D/msa14"
python -u -m routing2.gate_msa $C --tag m1 --lateral -1 --teleport-s 300 --sumo-extra "--mesosim true --meso-junction-control true" > $D/msa14_m1.log 2>&1 &
python -u -m routing2.gate_msa $C --tag microv3 --lateral 0.4 --teleport-s 120 --sumo-extra "--ignore-junction-blocker 5 --time-to-impatience 20" > $D/msa14_micro.log 2>&1 &
wait
echo MSA_EXIT
