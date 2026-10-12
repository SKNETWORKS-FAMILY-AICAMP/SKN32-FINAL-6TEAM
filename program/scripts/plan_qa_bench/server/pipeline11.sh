#!/bin/bash
export OLLAMA_HOST=127.0.0.1:11434 HF_HOME=/workspace/hf
cd /workspace/rerank_job
clean() { rm -rf /workspace/hf/hub /workspace/hf/xet; }
echo "[$(date +%H:%M)] 가벼운 LLM (올라마, 4개 묶음 전부)"
for m in gemma4:e4b gemma4:e2b qwen3.5:4b; do
  echo "[$(date +%H:%M)] $m"
  if ollama pull "$m" > /tmp/pl11.log 2>&1; then
    python3 llm_point2.py "$m"
    ollama rm "$m" > /dev/null 2>&1
  else
    echo "FAIL pull $m $(tail -c 160 /tmp/pl11.log | tr '\n\r' '  ')"
  fi
done
rm -f /workspace/ollama/blobs/*-partial*
echo "[$(date +%H:%M)] WeMM 임베딩"
../rtenv/bin/python wemm_run.py tencent/WeMM-Embedding-2B tencent/WeMM-Embedding-4B 2>&1 | grep -E " OK | FAIL "
clean
echo "[$(date +%H:%M)] OpenDecider 설치"
python3 -m venv /workspace/odenv 2>&1 | tail -1
/workspace/odenv/bin/pip install -q "opendecider[small]" 2>&1 | tail -3
echo "[$(date +%H:%M)] OpenDecider 탐침(질문 3개)"
/workspace/odenv/bin/python od_run.py manjunathshiva/opendecider-nano --probe 2>&1 | grep -vE "Warning|warn" | tail -6
echo "[$(date +%H:%M)] OpenDecider nano 전체"
/workspace/odenv/bin/python od_run.py manjunathshiva/opendecider-nano 2>&1 | grep -E "s/q|Error|error" | tail -3
echo "[$(date +%H:%M)] OpenDecider small 전체"
/workspace/odenv/bin/python od_run.py manjunathshiva/opendecider-small 2>&1 | grep -E "s/q|Error|error" | tail -3
clean
echo "[$(date +%H:%M)] P11DONE"
