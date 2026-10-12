#!/bin/bash
# 쓰던 서버 대기열 9 — ① Rune 26B-A4B v3 를 「결정 정보가 덧붙은」 GGUF(owao/surogate-rune-26b-a4b-GGUF, Q4_K_M 16.8GB)로 다시 시험
#  (앞서 받은 mradermacher 판은 llama.cpp 가 「결정 모델이 아님(501)」이라 거절했다) ② 로컬 모델 생각 켬 시험(E4B QAT·12B·26B, mix11 → mix10).
#  끝나면 A8(OpenJev 회전)이 이어서 돌도록 run_A7.log 에 ALLDONE_A7 을 남긴다.
export HF_HOME=/workspace/hf HF_HUB_DISABLE_XET=1 OLLAMA_HOST=127.0.0.1:11434
export LD_LIBRARY_PATH=/workspace/deciders/bin:$LD_LIBRARY_PATH
cd /workspace/heavy
LOG=/workspace/heavy/run_A9.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
stop_ollama() { for x in $(ollama ps | tail -n +2 | awk '{print $1}'); do ollama stop $x; done; sleep 3; }
rm -f /workspace/deciders/gguf/*.gguf
rm -rf /workspace/deciders/gguf/.cache
rm -f dec_rune26b_mix*.json
say "Rune(결정 정보 포함 GGUF) 내려받기"
/workspace/rtenv/bin/python - >> $LOG 2>&1 <<'PY'
from huggingface_hub import hf_hub_download
print('받음', hf_hub_download('owao/surogate-rune-26b-a4b-GGUF', 'Rune-26B-A4B-v3-Q4_K_M.gguf', local_dir='/workspace/deciders/gguf'))
PY
G=/workspace/deciders/gguf/Rune-26B-A4B-v3-Q4_K_M.gguf
if [ -f "$G" ] && [ "$(stat -c %s $G)" -gt 16000000000 ]; then
  /workspace/deciders/bin/llama-server -m $G --fit on -c 8192 -np 1 --port 8130 --host 127.0.0.1 > /workspace/deciders/server_rune.log 2>&1 &
  SPID=$!
  READY=0
  for k in $(seq 1 120); do
    R=$(curl -s -m 60 -X POST http://127.0.0.1:8130/v1/systemone -H 'Content-Type: application/json' -d '{"state":"a","questions":{"t":{"type":"choice","instructions":"x","criteria":{"a":"a","b":"b"}}}}' 2>/dev/null)
    echo "$R" | grep -q answ && { READY=1; break; }
    echo "$R" | grep -q "not a decision model" && { say "Rune: 이 GGUF 도 결정 모델이 아니라는 응답(501)"; break; }
    kill -0 $SPID 2>/dev/null || break
    sleep 3
  done
  if [ $READY = 1 ]; then
    for s in mix11 mix10 mix12 mix9 mix8; do
      say "Rune $s"
      DEC_URL=http://127.0.0.1:8130/v1/systemone DEC_TAG=rune26b SETS=$s python3 dec_run.py 2>&1 | tail -n 3 >> $LOG
    done
  else
    say "Rune 서버가 안 떴거나 결정 모델이 아님 — server_rune.log 확인"
  fi
  kill $SPID
  sleep 5
else
  say "Rune 파일이 없다(내려받기 실패)"
fi
rm -f $G
say "RUNE_STEP_DONE"
for m in gemma4:e4b-it-qat gemma4:12b gemma4:26b-a4b-it-q4_K_M; do
  for s in mix11 mix10; do
    say "생각 켬 $m $s"
    THINK=true JOB=$s python3 llm_point_think.py $m 2>&1 | tail -n 2 >> $LOG
  done
  stop_ollama
done
say "THINK_A_DONE"
echo ALLDONE_A9 >> $LOG
echo ALLDONE_A7 >> /workspace/heavy/run_A7.log
