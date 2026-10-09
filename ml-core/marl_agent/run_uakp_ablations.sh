#!/usr/bin/env bash
# Run main UAKP + ablations on sol1 (GPU1). Copy-paste or: bash marl_agent/run_uakp_ablations.sh
set -euo pipefail
cd "$(dirname "$0")/.."
CFG=marl_agent/configs/quan4_uakp.yaml
DEV="${CUDA_VISIBLE_DEVICES:-1}"

echo "=== main uakp_v1 ==="
CUDA_VISIBLE_DEVICES="$DEV" python -u -m marl_agent.uakp_train --config "$CFG" --device cuda

echo "=== ablation --no-uncertainty ==="
CUDA_VISIBLE_DEVICES="$DEV" python -u -m marl_agent.uakp_train --config "$CFG" --device cuda --no-uncertainty

echo "=== ablation --risk-lambda 0 ==="
CUDA_VISIBLE_DEVICES="$DEV" python -u -m marl_agent.uakp_train --config "$CFG" --device cuda --risk-lambda 0

echo "UAKP_ABLATIONS_DONE"
echo "Then: python -m marl_agent.uakp_metrics_table artifacts/out/quan4/marl_runs/quan4_uakp_*/summary.json"
