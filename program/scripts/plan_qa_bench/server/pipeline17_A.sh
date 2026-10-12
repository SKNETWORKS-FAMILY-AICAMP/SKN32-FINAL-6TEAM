#!/bin/bash
# 쓰던 서버 대기열 8 — OpenJev 26B(앙상블 E1 의 구성원) 순환 회전 10·21·32 를 mix11·mix12·mix10 에서(회전 평균이 큰 모델에도 통하는지). A7 이 끝나면 이어서.
export HF_HOME=/workspace/hf HF_HUB_DISABLE_XET=1
export LD_LIBRARY_PATH=/workspace/deciders/bin:$LD_LIBRARY_PATH
cd /workspace/heavy
LOG=/workspace/heavy/run_A8.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
while ! grep -q ALLDONE_A7 /workspace/heavy/run_A7.log; do sleep 30; done
rm -f /workspace/deciders/gguf/*.gguf
rm -rf /workspace/deciders/gguf/.cache
say "OpenJev 내려받기"
/workspace/rtenv/bin/python - >> $LOG 2>&1 <<'PY'
from huggingface_hub import hf_hub_download
print('받음', hf_hub_download('ggml-org/OpenJev-GGUF', 'OpenJev-Q4_K_M.gguf', local_dir='/workspace/deciders/gguf'))
PY
G=/workspace/deciders/gguf/OpenJev-Q4_K_M.gguf
if [ -f "$G" ] && [ "$(stat -c %s $G)" -gt 15000000000 ]; then
  /workspace/deciders/bin/llama-server -m $G --fit on -c 8192 -np 1 --port 8140 --host 127.0.0.1 > /workspace/deciders/server_openjev.log 2>&1 &
  SPID=$!
  READY=0
  for k in $(seq 1 400); do
    if curl -s -m 20 -X POST http://127.0.0.1:8140/v1/systemone -H 'Content-Type: application/json' -d '{"state":"a","questions":{"t":{"type":"choice","instructions":"x","criteria":{"a":"a","b":"b"}}}}' 2>/dev/null | grep -q answ; then READY=1; break; fi
    kill -0 $SPID 2>/dev/null || break
    sleep 3
  done
  if [ $READY = 1 ]; then
    for r in 10 21 32; do
      for s in mix11 mix12 mix10; do
        say "OpenJev 회전 $r $s"
        ROT=$r DEC_URL=http://127.0.0.1:8140/v1/systemone DEC_TAG=openjev26brot$r SETS=$s python3 dec_run.py 2>&1 | tail -n 2 >> $LOG
      done
    done
  else
    say "OpenJev 서버가 안 떴다"
  fi
  kill $SPID
  sleep 5
else
  say "OpenJev 파일이 없다(내려받기 실패)"
fi
rm -f $G
say "OPENJEV_ROT_DONE"
echo ALLDONE_A8 >> $LOG
