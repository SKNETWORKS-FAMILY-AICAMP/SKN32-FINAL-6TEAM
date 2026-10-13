#!/bin/bash
# 서버 A 대기열 25 (2026-10-07) — 가르친 E4B 시드 1·2·3(서비스 기반 Q4_K_M)의 답 자리 「없음」 확률(p_null)을 D 시험과 D2 보류 세트에서 기록한다.
#  쓰임: ①짚기 모델 자신의 「없음」 확률 문턱 ②FrogNano 가 「없음」이라 한 경우에만 문턱을 낮추는 결합(거부권보다 부드러운 방식) — 사용자 제안 「Frog 가 오지목이라 하면 학습된 모델이 오지목 확률을 높게 책정해 다시 검토」를 오프라인으로 시험.
#  대기열 24 가 끝나길 기다린다(GPU 한 번에 하나).
LOG=/workspace/heavy/run_A25.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
while ! grep -q ALLDONE_A24 /workspace/heavy/run_A24.log 2>/dev/null; do sleep 15; done
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5 LOGPROBS=1
Q4=/workspace/ollama/blobs/sha256-370c2879f17648d337b0ab4e208fdce348e24d1060064e93d7645daafd56d39c
for n in e4bt e4bs2 e4bs3; do
  say "25: D2 + 확률 $n"
  PROMPTS=all_prompts_d2.json GGUF=$Q4 LORA=/workspace/tripilot/${n}_lora_f16.gguf TAG=lp_d2_q4km_$n PORT=8210 python3 d_test_llama_lp.py > lp_d2_$n.out 2>&1
  say "25: D2 $n 끝: $(tail -n 1 lp_d2_$n.out | cut -c1-60) / p_null 기록 $(grep -c p_null d_test_lp_d2_q4km_$n.jsonl)"
  say "25: D + 확률 $n"
  GGUF=$Q4 LORA=/workspace/tripilot/${n}_lora_f16.gguf TAG=lp_q4km_$n PORT=8211 python3 d_test_llama_lp.py > lp_d_$n.out 2>&1
  say "25: D $n 끝: $(tail -n 1 lp_d_$n.out | cut -c1-60)"
done
echo ALLDONE_A25 >> $LOG
