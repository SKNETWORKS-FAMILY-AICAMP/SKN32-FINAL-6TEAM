#!/bin/bash
export HF_HOME=/workspace/hf
cd /workspace/rerank_job
until grep -q P11DONE pipeline11.log; do sleep 30; done
echo "[$(date +%H:%M)] qwen_vl_utils 설치"
../rtenv/bin/pip install -q qwen_vl_utils 2>&1 | tail -2
echo "[$(date +%H:%M)] WeMM 임베딩 다시"
../rtenv/bin/python wemm_run.py tencent/WeMM-Embedding-2B tencent/WeMM-Embedding-4B 2>&1 | grep -E " OK | FAIL "
rm -rf /workspace/hf/hub /workspace/hf/xet
echo "[$(date +%H:%M)] P12DONE"
