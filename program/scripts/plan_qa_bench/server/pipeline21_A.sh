#!/bin/bash
# 쓰던 서버 대기열 12 — 「둘 다 찾기(C)」 데이터: Gemma 4 12B → 26B 가 일정 항목 번호를 배열(items)로 답하게 해 mix8~12 를 푼다(생각 끔·온도 0). A11(정의 한 줄)이 끝나면 이어서.
export OLLAMA_HOST=127.0.0.1:11434 HF_HOME=/workspace/hf
cd /workspace/heavy
LOG=/workspace/heavy/run_A12.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
while ! grep -q ALLDONE_A11 /workspace/heavy/run_A11.log; do sleep 30; done
for m in gemma4:12b gemma4:26b-a4b-it-q4_K_M; do
  for s in mix11 mix10 mix12 mix9 mix8; do
    say "둘 다 찾기 $m $s"
    JOB=$s python3 llm_point_multi.py $m 2>&1 | tail -n 1 >> $LOG
  done
done
say "MULTI_A_DONE"
echo ALLDONE_A12 >> $LOG
