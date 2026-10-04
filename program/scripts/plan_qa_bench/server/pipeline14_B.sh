#!/bin/bash
# 새 서버 대기열 10 — mix12: ① Qwen3.8 27B ② Decider-12B 8비트·bf16 ③ 31B ④ OpenJev ⑤ pplx 27B ⑥ Cygnet·Hopper 12B·Jev-Omni 묶음
#  ⑦ Decider-12B 8비트 순환 회전(확률 평균용, mix8~11) ⑧ Granite 4.2 30B 직접(mix8~11).
cd /root
export HF_HUB_DISABLE_XET=1 OLLAMA_MODELS=/root/ollama_models OLLAMA_HOST=127.0.0.1:11434
LOG=/root/run_B14.log
while ! grep -q ALLDONE_B13 /root/run_B13.log; do sleep 30; done
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
stop_ollama() { ollama ps | tail -n +2 | awk '{print $1}' | while read m; do ollama stop $m; done; sleep 5; }
cp /root/work/mix12.json /root/work2/ 2>/dev/null
cd /root/work2
pgrep -x ollama > /dev/null || (nohup ollama serve > /root/ollama_serve.log 2>&1 & sleep 8)
say "Qwen3.8 27B mix12"
ollama pull qwen3.8:27b >> $LOG 2>&1
JOB=mix12 python3 llm_point_heavy.py qwen3.8:27b 2>&1 | tail -n 1 >> $LOG
stop_ollama
ollama rm qwen3.8:27b >> $LOG 2>&1
cd /root
say "Decider-12B 8비트 mix12"
Q8=1 MODEL=Mapika/decider-12b TAG=decider12bq8 SETS=mix12 /root/venv_imajev/bin/python dec_lib_run_q.py > /root/d12q8_m12.log 2>&1
say "8비트 exit=$?"
say "Decider-12B bf16 mix12"
MODEL=Mapika/decider-12b TAG=decider12bl SETS=mix12 GPU_GIB=6 CPU_GIB=42 BATCH=2 /root/venv_imajev/bin/python dec_lib_run_off.py > /root/d12_m12.log 2>&1
say "bf16 exit=$?"
rm -rf /root/.cache/huggingface/hub/models--Mapika--decider-12b /root/offload/*
say "31B mix12"
MODEL=Mapika/decider-chat-gemma4-31b TAG=decider31bl SETS=mix12 GPU_GIB=6 CPU_GIB=42 BATCH=2 /root/venv_imajev/bin/python dec_lib_run_off.py > /root/d31_m12.log 2>&1
say "31B exit=$?"
rm -rf /root/.cache/huggingface/hub/models--Mapika--decider-chat-gemma4-31b /root/offload/*
mkdir -p /root/gguf
say "OpenJev mix12"
/root/venv_imajev/bin/python - >> $LOG 2>&1 <<'PY'
from huggingface_hub import hf_hub_download
print('받음', hf_hub_download('ggml-org/OpenJev-GGUF', 'OpenJev-Q4_K_M.gguf', local_dir='/root/gguf'))
PY
/root/llama.cpp/build/bin/llama-server -m /root/gguf/OpenJev-Q4_K_M.gguf --fit on -c 8192 -np 1 --port 8120 --host 127.0.0.1 > /root/openjev_server.log 2>&1 &
SPID=$!
for k in $(seq 1 400); do
  if curl -s -m 20 -X POST http://127.0.0.1:8120/v1/systemone -H 'Content-Type: application/json' -d '{"state":"a","questions":{"t":{"type":"choice","instructions":"x","criteria":{"a":"a","b":"b"}}}}' 2>/dev/null | grep -q answ; then break; fi
  kill -0 $SPID 2>/dev/null || break
  sleep 3
done
( cd /root/work && DEC_URL=http://127.0.0.1:8120/v1/systemone DEC_TAG=openjev26b SETS=mix12 /root/venv_imajev/bin/python dec_run.py 2>&1 | tail -n 3 >> $LOG )
kill $SPID
sleep 5
rm -f /root/gguf/OpenJev-Q4_K_M.gguf
say "pplx 27B mix12"
/root/venv_imajev/bin/python - >> $LOG 2>&1 <<'PY'
from huggingface_hub import snapshot_download
print('받음', snapshot_download('perplexity-ai/pplx-decider-v1-27b', local_dir='/root/pplx27b', allow_patterns=['model-*.safetensors']))
PY
SETS=mix12 /root/venv_imajev/bin/python /root/pplx_run.py > /root/pplx_m12.log 2>&1
say "pplx exit=$?"
rm -f /root/pplx27b/model-*.safetensors
say "Cygnet mix12"
MODE=q8 TAG=cygnet SETS=mix12 /root/venv_imajev/bin/python /root/cygnet_hf_run.py > /root/cygnet_m12.log 2>&1
say "Hopper 12B mix12"
MODE=q8 TAG=hopper12b SETS=mix12 /root/venv_imajev/bin/python /root/hopper12b_run.py > /root/hopper_m12.log 2>&1
rm -rf /root/.cache/huggingface/hub/models--google--gemma-4-12B-it
say "Jev-Omni 묶음 mix12"
GROUPED=1 GROUP=20 MODE=q8 TAG=jevomnig SETS=mix12 /root/venv_imajev/bin/python /root/jev_omni_run.py > /root/jevomnig_m12.log 2>&1
rm -rf /root/.cache/huggingface/hub/models--akhilaaa3--Jev-Omni
say "MIX12_B_DONE"
echo ALLDONE_B14 >> $LOG
