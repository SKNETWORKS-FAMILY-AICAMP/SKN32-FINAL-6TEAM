#!/bin/bash
# 서버 A 대기열 26 (2026-10-07) — D3(Claude 가 쓴 합성 잡담 240 + 정답 있는 질문 120)에서 가르친 E4B 시드 1·2·3(서비스 기반 Q4_K_M)과 FrogNano-4B 의 답을 받는다 (Codex 솔 6.1 은 PC 에서 같은 세트로 풀고 있다). 대기열 25 가 끝나길 기다린다.
LOG=/workspace/heavy/run_A26.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
while ! grep -q ALLDONE_A25 /workspace/heavy/run_A25.log 2>/dev/null; do sleep 15; done
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5 PROMPTS=all_prompts_d3.json
Q4=/workspace/ollama/blobs/sha256-370c2879f17648d337b0ab4e208fdce348e24d1060064e93d7645daafd56d39c
FROG=/workspace/ollama/blobs/sha256-ea42d264c21d88b9bf6ce583bb3fd4dfddb22eb5b30efba9e305c56f75974c86
for n in e4bt e4bs2 e4bs3; do
  say "26: D3 서비스 기반 + $n"
  GGUF=$Q4 LORA=/workspace/tripilot/${n}_lora_f16.gguf TAG=d3_q4km_$n PORT=8230 python3 d_test_llama.py > d3_q4km_$n.out 2>&1
  say "26: $n 끝: $(tail -n 1 d3_q4km_$n.out | cut -c1-60)"
done
say "26: D3 FrogNano-4B"
GGUF=$FROG TAG=d3_frog PORT=8231 python3 d_test_llama.py > d3_frog.out 2>&1
say "26: Frog 끝: $(tail -n 1 d3_frog.out | cut -c1-60)"
echo ALLDONE_A26 >> $LOG
