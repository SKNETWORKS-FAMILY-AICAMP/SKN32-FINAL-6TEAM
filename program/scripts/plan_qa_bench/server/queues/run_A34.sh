#!/bin/bash
# 서버 A 대기열 34 (2026-10-07) — 학습용 어려운 문장(H-train)을 oos1 로 풀어 「oos1 이 틀리는 문장」을 채굴한다(두 번째 잡담 보강 학습 자료 고르기용).
#  대기열 33(후보 검토자 시험)이 끝나고 H-train 프롬프트 파일(all_prompts_htrain.json)이 올라오길 기다린다.
LOG=/workspace/heavy/run_A34.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
while ! grep -q ALLDONE_A33 /workspace/heavy/run_A33.log 2>/dev/null; do sleep 20; done
while [ ! -f /workspace/heavy/htrain_ready.flag ]; do sleep 15; done
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5 LOGPROBS=1 PROMPTS=all_prompts_htrain.json
Q4=/workspace/ollama/blobs/sha256-370c2879f17648d337b0ab4e208fdce348e24d1060064e93d7645daafd56d39c
say "34: H-train 채굴 oos1"
GGUF=$Q4 LORA=/workspace/tripilot/oos1_lora_f16.gguf TAG=lp_htrain_q4km_oos1 PORT=8290 python3 d_test_llama_lp.py > lp_htrain_oos1.out 2>&1
say "34: 끝: $(tail -n 1 lp_htrain_oos1.out | cut -c1-60)"
echo ALLDONE_A34 >> $LOG
