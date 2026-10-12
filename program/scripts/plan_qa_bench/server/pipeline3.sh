#!/bin/bash
export OLLAMA_HOST=127.0.0.1:11434 HF_HOME=/workspace/hf
cd /workspace/rerank_job
for m in gpt-oss:20b hf.co/deul/Kanana-2-30b-a3b-instruct-2601-GGUF:Q4_K_M gemma4:26b hf-local:kakaocorp/kanana-2-3b-instruct qwen3.8:27b gemma4:31b hf.co/LGAI-EXAONE/EXAONE-4.5-33B-GGUF:IQ4_XS hf.co/naver-ellm/HyperCLOVAX-SEED-Think-32B-GGUF:Q4_K_M; do
  echo "[$(date +%H:%M)] $m"
  if [[ "$m" == hf-local:* ]]; then
    python3 -c "import torch" 2>/dev/null || true
    ../rtenv/bin/python llm_point2.py --sets test50,hard40 "$m" 2>&1 | grep -E "s/q|Error|error" | tail -2
    rm -rf /workspace/hf/hub/models--*
  elif ollama pull "$m" > /tmp/pl.log 2>&1; then
    python3 llm_point2.py --sets test50,hard40 "$m"
    ollama rm "$m" > /dev/null 2>&1
  else
    echo "FAIL pull $m $(tail -c 160 /tmp/pl.log | tr '\n\r' '  ')"
  fi
done
echo "[$(date +%H:%M)] LLMDONE"
for m in BAAI/bge-m3 nlpai-lab/KURE-v2 Qwen/Qwen3-Embedding-8B Qwen/Qwen3-VL-Embedding-2B Qwen/Qwen3-VL-Embedding-8B jinaai/jina-reranker-v3.5 Qwen/Qwen3-Reranker-4B Qwen/Qwen3-VL-Reranker-2B; do
  ../rtenv/bin/python emb_rr.py "$m" 2>&1 | grep -E " OK | FAIL "
  rm -rf /workspace/hf/hub/models--*
done
echo "[$(date +%H:%M)] ALLDONE"
