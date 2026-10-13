#!/bin/bash
# 쓰던 서버에서 끼워 넣는 짧은 시험 — Microsoft FrogNano-4B-2609(Qwen3.5-4B 를 코딩 에이전트로 강화학습한 4B, MIT/Apache) 를 올라마 GGUF 로 우리 문제에 직접 짚기.
#  비교용으로 같은 계열 기본 모델(Qwen3.5-4B)도 받을 수 있으면 같이 푼다. 질의문·형식은 llm_point_heavy.py(생각 끔·온도 0·번호만 JSON) 그대로.
#  A9(Rune·생각 켬)와 같은 올라마를 쓰되 4B Q8(약 5GB)이라 16GB GPU 에 같이 올라간다.
export OLLAMA_HOST=127.0.0.1:11434 HF_HOME=/workspace/hf
cd /workspace/heavy
LOG=/workspace/heavy/run_A10.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
FROG='hf.co/bartowski/FrogNano-4B-2609-GGUF:Q8_0'
say "FrogNano 받기"
ollama pull $FROG >> $LOG 2>&1
say "FrogNano 받기 exit=$?"
ollama pull qwen3.5:4b >> $LOG 2>&1
say "Qwen3.5-4B 받기 exit=$?"
for s in mix11 mix10 mix12 mix9 mix8; do
  say "FrogNano 생각 끔 $s"
  JOB=$s python3 llm_point_heavy.py $FROG 2>&1 | tail -n 1 >> $LOG
done
if ollama list | grep -q "qwen3.5:4b"; then
  for s in mix11 mix10 mix12 mix9 mix8; do
    say "Qwen3.5-4B 생각 끔 $s"
    JOB=$s python3 llm_point_heavy.py qwen3.5:4b 2>&1 | tail -n 1 >> $LOG
  done
fi
say "FROG_DONE"
echo ALLDONE_A10 >> $LOG
