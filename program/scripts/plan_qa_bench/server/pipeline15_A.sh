#!/bin/bash
# 쓰던 서버 대기열 6 — Rune 26B-A4B v3(Gemma 4 26B-A4B 결정용 재학습판, Apache-2.0) Q4_K_M GGUF 를 llama-server 의 /v1/systemone 으로 시험한다.
#  출처: mradermacher/rune-26b-a4b-GGUF (기반 michaelfeil/rune-26b-a4b = v3, 16.8GB). 앞 대기열(A5, mix12)이 끝난 뒤 이어서 돈다.
export HF_HOME=/workspace/hf HF_HUB_DISABLE_XET=1
export LD_LIBRARY_PATH=/workspace/deciders/bin:$LD_LIBRARY_PATH
cd /workspace/heavy
LOG=/workspace/heavy/run_A6.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
while ! grep -q ALLDONE_A5 /workspace/heavy/run_A5.log; do sleep 30; done
mkdir -p /workspace/deciders/gguf
say "Rune 내려받기"
/workspace/rtenv/bin/python - >> $LOG 2>&1 <<'PY'
from huggingface_hub import hf_hub_download
print('받음', hf_hub_download('mradermacher/rune-26b-a4b-GGUF', 'rune-26b-a4b.Q4_K_M.gguf', local_dir='/workspace/deciders/gguf'))
PY
/workspace/deciders/bin/llama-server -m /workspace/deciders/gguf/rune-26b-a4b.Q4_K_M.gguf --fit on -c 8192 -np 1 --port 8130 --host 127.0.0.1 > /workspace/deciders/server_rune.log 2>&1 &
SPID=$!
for k in $(seq 1 400); do
  if curl -s -m 20 -X POST http://127.0.0.1:8130/v1/systemone -H 'Content-Type: application/json' -d '{"state":"a","questions":{"t":{"type":"choice","instructions":"x","criteria":{"a":"a","b":"b"}}}}' 2>/dev/null | grep -q answ; then break; fi
  kill -0 $SPID 2>/dev/null || break
  sleep 3
done
say "Rune 서버 준비(또는 실패) — 로그 server_rune.log"
for s in mix10 mix11 mix9 mix8 mix12; do
  say "Rune $s"
  DEC_URL=http://127.0.0.1:8130/v1/systemone DEC_TAG=rune26b SETS=$s python3 dec_run.py 2>&1 | tail -n 3 >> $LOG
done
kill $SPID
sleep 5
rm -f /workspace/deciders/gguf/rune-26b-a4b.Q4_K_M.gguf
say "RUNE_DONE"
echo ALLDONE_A6 >> $LOG
