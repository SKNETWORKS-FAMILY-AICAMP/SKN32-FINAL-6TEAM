#!/bin/bash
export OLLAMA_HOST=127.0.0.1:11434 HF_HOME=/workspace/hf
cd /workspace/rerank_job
clean() { rm -rf /workspace/hf/hub /workspace/hf/xet; }
m=hf.co/meta-models/Muse-Glimmer-30B-GGUF:Q4_K_M
echo "[$(date +%H:%M)] $m"
if ollama pull "$m" > /tmp/pl8.log 2>&1; then
  python3 llm_point2.py --sets test50,hard40 "$m"
  ollama rm "$m" > /dev/null 2>&1
else
  echo "FAIL pull $(tail -c 200 /tmp/pl8.log | tr '\n\r' '  ')"
fi
rm -f /workspace/ollama/blobs/*-partial*
echo "[$(date +%H:%M)] kanana-3b"
../rtenv/bin/python llm_point2.py --sets test50,hard40 hf-local:kakaocorp/kanana-2-3b-instruct > kanana3b.log 2>&1
grep -E "s/q" kanana3b.log || grep -vE "Warning|warn" kanana3b.log | tail -15
clean
for m in Qwen/Qwen3-Reranker-4B jinaai/jina-reranker-v3.5 Qwen/Qwen3-VL-Reranker-2B Qwen/Qwen3-VL-Embedding-8B; do
  echo "[$(date +%H:%M)] $m"
  ../rtenv/bin/python emb_rr.py "$m" 2>&1 | grep -E " OK | FAIL "
  clean
done
echo "[$(date +%H:%M)] P8DONE"
