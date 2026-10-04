#!/bin/bash
# 새 서버 대기열 17 — 「정의 한 줄(먼저 말한 항목이 정답)」을 지시문에 덧붙여 주요 모델을 mix8~12 에서 다시 푼다.
#  Claude 는 이 한 줄로 요청 둘 유형이 33%→98% 로 올랐다(§66) — 로컬·결정 모델도 같은 조건에서 비교한다. B15(생각 켬)가 끝나면 이어서, 끝나면 B16(섞기)가 이어서.
cd /root
export HF_HUB_DISABLE_XET=1 OLLAMA_MODELS=/root/ollama_models OLLAMA_HOST=127.0.0.1:11434
LOG=/root/run_B17.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
stop_ollama() { ollama ps | tail -n +2 | awk '{print $1}' | while read m; do ollama stop $m; done; sleep 5; }
while ! grep -q ALLDONE_B15 /root/run_B15.log; do sleep 30; done
cp /root/work/mix8.json /root/work/mix9.json /root/work/mix10.json /root/work/mix11.json /root/work/mix12.json /root/work2/ 2>/dev/null
cd /root/work2
pgrep -x ollama > /dev/null || (nohup ollama serve > /root/ollama_serve.log 2>&1 & sleep 8)
for s in mix11 mix10 mix12 mix9 mix8; do
  say "Qwen3.8 27B 정의 명시 $s"
  JOB=$s python3 llm_point_heavy.py --proto qwen3.8:27b 2>&1 | tail -n 1 >> $LOG
done
stop_ollama
ollama rm qwen3.8:27b >> $LOG 2>&1
cd /root
say "Decider-12B 8비트 정의 명시"
RULE=1 Q8=1 MODEL=Mapika/decider-12b TAG=decider12bq8rule SETS=mix11,mix10,mix12,mix9,mix8 /root/venv_imajev/bin/python dec_lib_run_q.py > /root/d12q8_rule.log 2>&1
say "8비트 exit=$?"
rm -rf /root/.cache/huggingface/hub/models--Mapika--decider-12b
say "31B 정의 명시"
RULE=1 MODEL=Mapika/decider-chat-gemma4-31b TAG=decider31blrule SETS=mix11,mix10,mix12,mix9,mix8 GPU_GIB=6 CPU_GIB=42 BATCH=2 /root/venv_imajev/bin/python dec_lib_run_off.py > /root/d31_rule.log 2>&1
say "31B exit=$?"
rm -rf /root/.cache/huggingface/hub/models--Mapika--decider-chat-gemma4-31b /root/offload/*
mkdir -p /root/gguf
say "OpenJev 정의 명시"
/root/venv_imajev/bin/python - >> $LOG 2>&1 <<'PY'
from huggingface_hub import hf_hub_download
print('받음', hf_hub_download('ggml-org/OpenJev-GGUF', 'OpenJev-Q4_K_M.gguf', local_dir='/root/gguf'))
PY
/root/llama.cpp/build/bin/llama-server -m /root/gguf/OpenJev-Q4_K_M.gguf --fit on -c 8192 -np 1 --port 8120 --host 127.0.0.1 > /root/openjev_server.log 2>&1 &
SPID=$!
for k in $(seq 1 200); do
  if curl -s -m 20 -X POST http://127.0.0.1:8120/v1/systemone -H 'Content-Type: application/json' -d '{"state":"a","questions":{"t":{"type":"choice","instructions":"x","criteria":{"a":"a","b":"b"}}}}' 2>/dev/null | grep -q answ; then break; fi
  kill -0 $SPID 2>/dev/null || break
  sleep 3
done
( cd /root/work && for s in mix11 mix10 mix12 mix9 mix8; do RULE=1 DEC_URL=http://127.0.0.1:8120/v1/systemone DEC_TAG=openjev26brule SETS=$s /root/venv_imajev/bin/python dec_run.py 2>&1 | tail -n 1 >> $LOG; done )
kill $SPID
sleep 5
rm -f /root/gguf/OpenJev-Q4_K_M.gguf
say "RULE_B_DONE"
echo ALLDONE_B17 >> $LOG
