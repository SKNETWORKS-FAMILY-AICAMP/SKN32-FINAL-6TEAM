#!/bin/bash
export OLLAMA_HOST=127.0.0.1:11434 HF_HOME=/workspace/hf
cd /workspace/rerank_job
while pgrep -f "[l]lm_point2.py --sets test50,hard40 qwen3.8" > /dev/null; do sleep 30; done
echo "[$(date +%H:%M)] qwen3.8 finished"
ollama rm qwen3.8:27b > /dev/null 2>&1
../rtenv/bin/python llm_point2.py --sets test50,hard40 hf-local:kakaocorp/kanana-2-3b-instruct 2>&1 | grep -E "s/q|Error" | tail -2
rm -rf /workspace/hf/hub/models--*
echo "[$(date +%H:%M)] LLMDONE"
for m in BAAI/bge-m3 nlpai-lab/KURE-v2 Qwen/Qwen3-Embedding-8B Qwen/Qwen3-VL-Embedding-2B Qwen/Qwen3-VL-Embedding-8B jinaai/jina-reranker-v3.5 Qwen/Qwen3-Reranker-4B Qwen/Qwen3-VL-Reranker-2B; do
  ../rtenv/bin/python emb_rr.py "$m" 2>&1 | grep -E " OK | FAIL "
  rm -rf /workspace/hf/hub/models--*
done
echo "[$(date +%H:%M)] ALLDONE"
