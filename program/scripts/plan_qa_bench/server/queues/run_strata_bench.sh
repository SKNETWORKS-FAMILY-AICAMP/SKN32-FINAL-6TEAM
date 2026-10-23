#!/bin/bash
# Independent inference experiment; existing training queues keep running.
set -euo pipefail
ROOT=/workspace/strata-bench
mkdir -p "$ROOT/raw"
exec 9>"$ROOT/job.lock"
flock -n 9 || { echo 'Another Strata benchmark is already running'; exit 0; }
cd "$ROOT/Strata"
git rev-parse HEAD > "$ROOT/source_revision.txt"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv > "$ROOT/hardware.csv"
# Original full-expert model; no fine-tuning with our data.
./setup.sh --yes --family qwen --model IQ2_XS --context 4096 \
  --vision no --port 8330 --host 127.0.0.1 --no-browser \
  --parallel 1 --data-dir "$ROOT/data" --no-start
echo INSTALL_DONE
setsid bash ./run-iq2_xs.sh > "$ROOT/service.log" 2>&1 &
service_pid=$!
echo "$service_pid" > "$ROOT/service.pid"
trap 'kill -- -"$service_pid" 2>/dev/null || true' EXIT
ready=0
for ((attempt=0; attempt<240; attempt++)); do
  if ! kill -0 "$service_pid" 2>/dev/null; then
    echo 'SERVICE_FAILED: inspect service.log'; exit 2
  fi
  if curl --silent --fail --max-time 5 http://127.0.0.1:8330/health > "$ROOT/health.json"; then
    ready=1; break
  fi
  sleep 5
done
[[ "$ready" == 1 ]] || { echo HEALTH_TIMEOUT; exit 2; }
echo SERVICE_READY
curl --silent --fail http://127.0.0.1:8330/v1/models > "$ROOT/models.json"
python3 "$ROOT/strata_bench.py" --input /workspace/heavy/all_prompts_mx.json \
  --output "$ROOT/raw/mx_smoke.jsonl" --limit 12
python3 - "$ROOT/raw/mx_smoke.jsonl.summary.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
if s['parse_or_transport_failures']:
    raise SystemExit('SMOKE_FAILED: inspect raw/mx_smoke.jsonl')
PY
echo SMOKE_PASSED
python3 "$ROOT/strata_bench.py" --input /workspace/heavy/all_prompts_mx.json \
  --output "$ROOT/raw/mx_strata_iq2_xs.jsonl"
echo MX_DONE
python3 "$ROOT/strata_bench.py" --input /workspace/heavy/all_prompts_d3.json \
  --output "$ROOT/raw/d3_strata_iq2_xs.jsonl"
echo ALLDONE_STRATA
