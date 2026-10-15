#!/bin/bash
# 서버 A 대기열 29 (2026-10-07) — 잡담 부정 사례를 더해 다시 가르친 E4B(oos1, 서비스 기반 Q4_K_M)의 D · D2 · D3 시험.
#  목적: 새 잡담 오지목이 줄고 시드마다 갈리던 폭이 좁아지는지(D·D2·D3 모두), 정답 있는 질문이 3%p 넘게 떨어지지 않는지 본다. 같은 틀의 시드 1(e4bt)과 견준다.
LOG=/workspace/heavy/run_A29.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5
Q4=/workspace/ollama/blobs/sha256-370c2879f17648d337b0ab4e208fdce348e24d1060064e93d7645daafd56d39c
n=${1:-oos1}
L=/workspace/tripilot/${n}_lora_f16.gguf
say "29: D + 확률 $n"
LOGPROBS=1 GGUF=$Q4 LORA=$L TAG=lp_q4km_$n PORT=8250 python3 d_test_llama_lp.py > lp_d_$n.out 2>&1
say "29: D $n 끝: $(tail -n 1 lp_d_$n.out | cut -c1-60)"
say "29: D2 + 확률 $n"
LOGPROBS=1 PROMPTS=all_prompts_d2.json GGUF=$Q4 LORA=$L TAG=lp_d2_q4km_$n PORT=8251 python3 d_test_llama_lp.py > lp_d2_$n.out 2>&1
say "29: D2 $n 끝: $(tail -n 1 lp_d2_$n.out | cut -c1-60)"
say "29: D3 $n"
PROMPTS=all_prompts_d3.json GGUF=$Q4 LORA=$L TAG=d3_q4km_$n PORT=8252 python3 d_test_llama.py > d3_q4km_$n.out 2>&1
say "29: D3 $n 끝: $(tail -n 1 d3_q4km_$n.out | cut -c1-60)"
echo ALLDONE_A29_$n >> $LOG
