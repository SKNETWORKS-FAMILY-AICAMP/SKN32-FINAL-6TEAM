#!/bin/bash
# Use existing root-disk space while the persistent model volume is full.
set -euo pipefail
WORK=/tmp/tripilot-oos2r-eval
mkdir -p "$WORK"
exec 9>"$WORK/job.lock"
flock -n 9 || exit 0
cd "$WORK"
for source in /workspace/heavy/*.py /workspace/heavy/all_prompts*.json; do
  [[ -f "$source" ]] || continue
  [[ -e "$WORK/$(basename "$source")" ]] || ln -s "$source" "$WORK/$(basename "$source")"
done
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5
export GGUF=/workspace/ollama/blobs/sha256-370c2879f17648d337b0ab4e208fdce348e24d1060064e93d7645daafd56d39c
export LORA="$WORK/oos2r_lora_f16.gguf"
[[ -s "$LORA" ]] || { echo ADAPTER_MISSING; exit 2; }
while [[ $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -dc 0-9) -ge 1000 ]]; do sleep 30; done
LOGPROBS=1 TAG=lp_q4km_oos2r PORT=8321 python3 d_test_llama_lp.py > lp_d_oos2r.out 2>&1
echo D_DONE
LOGPROBS=1 PROMPTS=all_prompts_d2.json TAG=lp_d2_q4km_oos2r PORT=8322 python3 d_test_llama_lp.py > lp_d2_oos2r.out 2>&1
echo D2_DONE
PROMPTS=all_prompts_d3.json TAG=d3_q4km_oos2r PORT=8323 python3 d_test_llama.py > d3_q4km_oos2r.out 2>&1
echo D3_DONE
LOGPROBS=1 PROMPTS=all_prompts_h.json TAG=lp_h_q4km_oos2r PORT=8324 python3 d_test_llama_lp.py > lp_h_oos2r.out 2>&1
echo H_DONE
LOGPROBS=1 PROMPTS=all_prompts_mx.json TAG=lp_mx_q4km_oos2r PORT=8325 python3 d_test_llama_lp.py > lp_mx_oos2r.out 2>&1
echo ALLDONE_OOS2R_TMP
