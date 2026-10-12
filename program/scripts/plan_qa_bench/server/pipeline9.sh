#!/bin/bash
export HF_HOME=/workspace/hf
cd /workspace/rerank_job
until grep -q P8DONE pipeline8.log; do sleep 30; done
for m in KaLM-Embedding/KaLM-Reranker-V1-Large-R2 zeroentropy/zerank-2-reranker Qwen/Qwen3-Reranker-8B Qwen/Qwen3-VL-Reranker-8B; do
  echo "[$(date +%H:%M)] $m"
  ../rtenv/bin/python emb_rr.py "$m" 2>&1 | grep -E " OK | FAIL "
  rm -rf /workspace/hf/hub /workspace/hf/xet
done
echo "[$(date +%H:%M)] P9DONE"
