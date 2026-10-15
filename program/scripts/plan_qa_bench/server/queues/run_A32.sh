#!/bin/bash
# 서버 A 대기열 32 (2026-10-07) — 어려운 보류 세트 H(솔 6.1 이 만든 오지목 유발 문장 + 정답 있는 대조 문장, 루나 6.0 이 따로 라벨해 합의한 것만)에서
#  가르친 E4B 시드 1·2·3 과 oos1(서비스 기반 Q4_K_M)을 푼다. D · D2 · D3 에서 잡담 오지목이 바닥이라 못 보이던 차이를 보려는 것.
#  대기열 31 이 끝나고 H 프롬프트 파일(all_prompts_h.json)이 올라오길 기다린다.
LOG=/workspace/heavy/run_A32.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
while ! grep -q ALLDONE_A31 /workspace/heavy/run_A31.log 2>/dev/null; do sleep 15; done
while [ ! -f /workspace/heavy/h_ready.flag ]; do sleep 15; done
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5 LOGPROBS=1 PROMPTS=all_prompts_h.json
Q4=/workspace/ollama/blobs/sha256-370c2879f17648d337b0ab4e208fdce348e24d1060064e93d7645daafd56d39c
for n in e4bt e4bs2 e4bs3 oos1; do
  say "32: H + 확률 $n"
  GGUF=$Q4 LORA=/workspace/tripilot/${n}_lora_f16.gguf TAG=lp_h_q4km_$n PORT=8280 python3 d_test_llama_lp.py > lp_h_$n.out 2>&1
  say "32: H $n 끝: $(tail -n 1 lp_h_$n.out | cut -c1-60)"
done
echo ALLDONE_A32 >> $LOG
