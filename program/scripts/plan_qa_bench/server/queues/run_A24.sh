#!/bin/bash
# 서버 A 대기열 24 (2026-10-07) — 새 잡담 보류 세트 D2(1,000문장, 정답 = 없음; 시험 · 학습에 안 쓴 문장)에서 가르친 E4B 시드 1·2·3(서비스 기반 Q4_K_M)과 FrogNano-4B 의 오지목.
#  D 시험의 시드 변동(잡담 오지목 5.1 · 21.5 · 9.4%)이 시험 세트의 우연이 아닌지, 거부권(FrogNano)이 새 문장에서도 통하는지 본다. 다음 점검에서 oos 시드를 같은 방식으로 더 건다.
LOG=/workspace/heavy/run_A24.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5 PROMPTS=all_prompts_d2.json
Q4=/workspace/ollama/blobs/sha256-370c2879f17648d337b0ab4e208fdce348e24d1060064e93d7645daafd56d39c
FROG=/workspace/ollama/blobs/sha256-ea42d264c21d88b9bf6ce583bb3fd4dfddb22eb5b30efba9e305c56f75974c86
for n in e4bt e4bs2 e4bs3; do
  say "24: D2 서비스 기반 + $n"
  GGUF=$Q4 LORA=/workspace/tripilot/${n}_lora_f16.gguf TAG=d2_q4km_$n PORT=8200 python3 d_test_llama.py > d2_q4km_$n.out 2>&1
  say "24: $n 끝: $(tail -n 1 d2_q4km_$n.out | cut -c1-70)"
done
say "24: D2 FrogNano-4B"
GGUF=$FROG TAG=d2_frog PORT=8201 python3 d_test_llama.py > d2_frog.out 2>&1
say "24: Frog 끝: $(tail -n 1 d2_frog.out | cut -c1-70)"
echo ALLDONE_A24 >> $LOG
