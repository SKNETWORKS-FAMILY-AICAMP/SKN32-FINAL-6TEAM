#!/bin/bash
# 쓰던 서버 대기열 11 — 「정의 한 줄」을 덧붙인 올라마 직접 짚기(E4B QAT → 12B → 26B)를 mix8~12 에서. A10(FrogNano)이 끝나면 이어서 돈다(A9 생각 켬과 올라마를 같이 쓴다).
export OLLAMA_HOST=127.0.0.1:11434 HF_HOME=/workspace/hf
cd /workspace/heavy
LOG=/workspace/heavy/run_A11.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
while ! grep -q ALLDONE_A10 /workspace/heavy/run_A10.log; do sleep 30; done
for m in gemma4:e4b-it-qat gemma4:12b gemma4:26b-a4b-it-q4_K_M; do
  for s in mix11 mix10 mix12 mix9 mix8; do
    say "정의 명시 $m $s"
    JOB=$s python3 llm_point_heavy.py --proto $m 2>&1 | tail -n 1 >> $LOG
  done
done
say "RULE_A_DONE"
echo ALLDONE_A11 >> $LOG
