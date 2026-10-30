#!/usr/bin/env bash
# Mapbox probe worker on sol1 (tmux session "probe").
#   bash scripts/probe_sol1.sh start     # build + start the worker in tmux (no-op if running)
#   bash scripts/probe_sol1.sh status    # is it running, last log lines, quota, typical job, data size
#   bash scripts/probe_sol1.sh check     # match live + typical to edges, live-vs-typical diagnostics
#   bash scripts/probe_sol1.sh typical START_DATE [DAYS] [STEP_MIN]   # queue a typical job
#   bash scripts/probe_sol1.sh stop      # stop the worker (cursors keep the resume point)
# Every command also writes its output to $D/reports/<command>_<UTC time>.txt.
set -eo pipefail

ROOT=${ROOT:-$HOME/hcmc-traffic-rl}
D=${PROBE_DATA:-/mnt/data8tb/minhkhoi/hcmc-traffic-rl/ingestion}
CONDA_SH=/mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh
NODE_ENV=/mnt/data8tb/minhkhoi/node-env
PY_ENV=/mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env
W=$ROOT/ingestion-worker
PORT=$(grep -E '^PORT=' "$W/.env" | cut -d= -f2 | tr -d '\r')
PORT=${PORT:-3077}
URL=http://localhost:$PORT
CMD=${1:-status}
mkdir -p "$D/reports" "$D/data_raw" "$D/state"
REPORT=$D/reports/${CMD}_$(date -u +%Y%m%dT%H%M%SZ).txt

running() { pgrep -u "$USER" -f "node dist/main" >/dev/null; }

do_start() {
  if running; then echo "worker already running (tmux probe)"; return; fi
  tmux kill-session -t probe 2>/dev/null || true
  [ -d "$NODE_ENV" ] || { echo "missing $NODE_ENV; create it: conda create -y -p $NODE_ENV -c conda-forge nodejs=22"; exit 1; }
  tmux new -d -s probe "bash -c 'source $CONDA_SH && conda activate $NODE_ENV && cd $W && \
    { [ -d node_modules ] || npm ci; } && npm run build && npm run start:prod 2>&1 | tee -a $D/worker.log; \
    echo worker exited; sleep 86400'"
  sleep 25
  grep -v 'Redis error' "$D/worker.log" | grep -E 'probes ready|Redis disabled|EADDRINUSE|Error' | tail -n 3 || true
  echo "started (tmux probe). Watch: tmux attach -t probe, then Ctrl+b d to leave"
}

do_status() {
  if running; then echo "worker: RUNNING (tmux probe)"; else echo "worker: NOT running -> bash scripts/probe_sol1.sh start"; fi
  echo "== last log lines"; grep -v -E 'Redis error|DEBUG' "$D/worker.log" | tail -n 8 || true
  echo "== errors in log"; grep -cE 'Probe skip|Typical skip|HTTP 4|HTTP 5' "$D/worker.log" || true
  echo "== sweeps done"; grep -c 'Probe sweep' "$D/worker.log" || true
  echo "== quota"; cat "$D/state/mapbox_quota.json" 2>/dev/null || echo none; echo
  echo "== typical job"; curl -s --max-time 5 "$URL/mapbox/probe/typical" || echo "(worker not answering)"; echo
  echo "== live lines per day"; wc -l "$D"/data_raw/mapbox_probe/*.jsonl 2>/dev/null || echo none
  echo "== typical lines"; wc -l "$D"/data_raw/mapbox_typical/*.jsonl 2>/dev/null || echo none
  echo "== disk"; du -sh "$D/data_raw" 2>/dev/null
}

do_check() {
  source "$CONDA_SH" && conda activate "$PY_ENV"
  cd "$ROOT/ml-core"
  python -m data_fusion.match_probe --probes "$D/data_raw/mapbox_probe" \
    --routes ../ingestion-worker/config/probe_routes.quan4.json --out artifacts/out/quan4/probe
  python -m data_fusion.match_probe --probes "$D/data_raw/mapbox_typical" --glob 'typical_*.jsonl' \
    --routes ../ingestion-worker/config/probe_routes.quan4.json --out artifacts/out/quan4/probe_typical
  python -m data_fusion.probe_diagnostics --live artifacts/out/quan4/probe/edge_obs.csv \
    --typical artifacts/out/quan4/probe_typical/edge_obs.csv --out artifacts/out/quan4/probe/diagnostics.json
}

do_typical() {
  [ -n "$2" ] || { echo "usage: typical YYYY-MM-DD [days=7] [stepMin=15]"; exit 1; }
  curl -s -X POST "$URL/mapbox/probe/typical?start=$2&days=${3:-7}&stepMin=${4:-15}"; echo
}

do_stop() {
  if running; then tmux send-keys -t probe C-c; sleep 3; fi
  tmux kill-session -t probe 2>/dev/null || true
  if running; then echo "still running; pkill -u $USER -f 'node dist/main'"; else echo stopped; fi
}

case "$CMD" in
  start) do_start ;;
  status) do_status ;;
  check) do_check ;;
  typical) do_typical "$@" ;;
  stop) do_stop ;;
  *) echo "usage: $0 start|status|check|typical|stop"; exit 1 ;;
esac 2>&1 | tee "$REPORT"
echo "(saved: $REPORT)"
