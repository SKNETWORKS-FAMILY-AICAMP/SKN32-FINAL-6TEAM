#!/bin/bash
export OLLAMA_HOST=127.0.0.1:11434 HF_HOME=/workspace/hf
cd /workspace/rerank_job
until grep -q P9DONE pipeline9.log; do sleep 30; done
echo "[$(date +%H:%M)] 서버가 한가해짐"
../rtenv/bin/python llm_point2.py --sets test50,hard40 hf-local:kakaocorp/kanana-2-3b-instruct > kanana3b.log 2>&1
grep -E "s/q" kanana3b.log || grep -vE "Warning|warn" kanana3b.log | tail -6
rm -rf /workspace/hf/hub /workspace/hf/xet
echo "[$(date +%H:%M)] Muse 짧은 확인"
M=hf.co/meta-models/Muse-Glimmer-30B-GGUF:Q4_K_M
python3 probe3.py $M plain
python3 probe3.py $M think_false
echo "[$(date +%H:%M)] P10DONE"
