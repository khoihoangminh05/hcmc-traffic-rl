#!/usr/bin/env bash
# Unpack Paper A twin bundle on sol1 into repo paths expected by quan4_v5_final.yaml
set -euo pipefail
REPO="${1:-$HOME/hcmc-traffic-rl}"
BUNDLE="${2:-/tmp/v5_bundle_for_sol1.tar.gz}"
STAGE="${TMPDIR:-/tmp}/v5_stage_$$"

if [[ ! -f "$BUNDLE" ]]; then
  echo "Missing bundle: $BUNDLE" >&2
  exit 1
fi
if [[ ! -d "$REPO" ]]; then
  echo "Missing repo: $REPO" >&2
  exit 1
fi

rm -rf "$STAGE"
mkdir -p "$STAGE"
tar -xzf "$BUNDLE" -C "$STAGE"

mkdir -p "$REPO/ml-core/artifacts/out/quan4/density"
mkdir -p "$REPO/ingestion-worker/config"
mkdir -p "$REPO/ml-core/marl_agent/configs"
mkdir -p /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs

rm -rf "$REPO/ml-core/artifacts/out/quan4/wcc"
cp -a "$STAGE/wcc" "$REPO/ml-core/artifacts/out/quan4/"
[[ -f "$STAGE/density_l1_index.json" ]] && cp -f "$STAGE/density_l1_index.json" "$REPO/ml-core/artifacts/out/quan4/density/"
[[ -f "$STAGE/paper_a_freeze_meta.json" ]] && cp -f "$STAGE/paper_a_freeze_meta.json" "$REPO/ml-core/artifacts/out/quan4/"
cp -f "$STAGE/config/od_pairs.quan4.seeds_l3.json" "$REPO/ingestion-worker/config/"
[[ -f "$STAGE/marl_configs/quan4_v5_final.yaml" ]] && cp -f "$STAGE/marl_configs/quan4_v5_final.yaml" "$REPO/ml-core/marl_agent/configs/"

ln -sfn /mnt/data8tb/minhkhoi/hcmc-traffic-rl/marl_runs "$REPO/ml-core/artifacts/out/quan4/marl_runs"

echo "Unpacked OK → $REPO"
ls -la "$REPO/ml-core/artifacts/out/quan4/wcc" | head
rm -rf "$STAGE"
