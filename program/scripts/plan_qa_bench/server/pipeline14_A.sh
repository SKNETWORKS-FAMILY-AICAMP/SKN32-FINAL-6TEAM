#!/bin/bash
# 쓰던 서버 대기열 4 — mix12 준비·기본 계산(앞단 점수·게이트·E4B QAT·12B·26B·전문가 구조) → Winnow-12B mix12 → Granite 4.2 8B·3B 직접(mix8~mix12).
export OLLAMA_HOST=127.0.0.1:11434 HF_HOME=/workspace/hf HF_HUB_DISABLE_XET=1
cd /workspace/heavy
LOG=/workspace/heavy/run_A5.log
while ! grep -q ALLDONE_A4 /workspace/heavy/run_A4.log; do sleep 30; done
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
stop_ollama() { for x in $(ollama ps | tail -n +2 | awk '{print $1}'); do ollama stop $x; done; sleep 3; }
say "mix12 앞단 점수·게이트"
for t in e16c e16d; do TAG=$t /workspace/rtenv/bin/python score_mix6.py mix12 /workspace/experts/ft_${t}_adapter 2>&1 | tail -n 1 >> $LOG; done
/workspace/rtenv/bin/python gate_embed_mix12.py 2>&1 | tail -n 1 >> $LOG
say "E4B QAT 짚기·확신도"
JOB=mix12 python3 llm_point_heavy.py gemma4:e4b-it-qat 2>&1 | tail -n 1 >> $LOG
JOB=mix12 python3 llm_point_lp.py gemma4:e4b-it-qat 2>&1 | tail -n 1 >> $LOG
stop_ollama
say "12B 짚기"
JOB=mix12 python3 llm_point_heavy.py gemma4:12b 2>&1 | tail -n 1 >> $LOG
stop_ollama
say "26B 직접"
JOB=mix12 python3 llm_point_heavy.py gemma4:26b-a4b-it-q4_K_M 2>&1 | tail -n 1 >> $LOG
stop_ollama
say "전문가 구조"
python3 llm_tasks.py mix12 gemma4:e4b gemma4:12b 2>&1 | tail -n 2 >> $LOG
stop_ollama
say "MIX12_P1_DONE"
# ---- Winnow-12B
export LD_LIBRARY_PATH=/workspace/deciders/bin:$LD_LIBRARY_PATH
W=/workspace/deciders/repos/winnow-inference
WM=/workspace/deciders/winnow_models
mkdir -p $WM/gguf
/workspace/rtenv/bin/python - >> $LOG 2>&1 <<'PY'
from huggingface_hub import hf_hub_download
print('받음', hf_hub_download('EldanRing/Winnow-12B', 'gguf/Winnow-12B-Q8_0.gguf', local_dir='/workspace/deciders/winnow_models'))
PY
( cd $W && python3 scripts/serve.py --profile 5070ti-64k --model-dir $WM --text-only --context 8192 --port 8091 > /workspace/deciders/server_winnow12b.log 2>&1 ) &
SPID=$!
for k in $(seq 1 300); do
  if curl -s -m 20 -X POST http://127.0.0.1:8091/v1/systemone -H 'Content-Type: application/json' -d '{"state":"a","questions":{"t":{"type":"choice","instructions":"x","criteria":{"a":"a","b":"b"}}}}' 2>/dev/null | grep -q answ; then break; fi
  kill -0 $SPID 2>/dev/null || break
  sleep 3
done
DEC_URL=http://127.0.0.1:8091/v1/systemone DEC_TAG=winnow12b SETS=mix12 python3 dec_run.py 2>&1 | tail -n 3 >> $LOG
pkill -P $SPID 2>/dev/null
kill $SPID 2>/dev/null
sleep 3
pkill -f "scripts/serve.py" 2>/dev/null
pkill -f "llama-server" 2>/dev/null
sleep 5
rm -f $WM/gguf/Winnow-12B-Q8_0.gguf
say "WINNOW12_DONE"
echo ALLDONE_A5 >> $LOG
