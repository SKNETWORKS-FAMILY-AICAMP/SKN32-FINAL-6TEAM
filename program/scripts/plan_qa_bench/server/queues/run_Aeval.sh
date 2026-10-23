#!/bin/bash
# 서버 A 범용 시험 대기열 (2026-10-07) — 새로 가르친 짚기 모델(어댑터 <이름>_lora_f16.gguf)을 서비스 기반 Q4_K_M 에서 D · D2 · D3 · H · MX 로 잰다.
#  사용: bash run_Aeval.sh <이름> <기다릴 신호 로그:문구>   예) bash run_Aeval.sh oos2 run_A35.log:ALLDONE_A35
#  끝나면 run_Aeval_<이름>.log 에 ALLDONE_AEVAL_<이름>. 어댑터는 /workspace/tripilot/<이름>_lora_f16.gguf 에 있어야 한다.
n=$1; WAIT=$2
LOG=/workspace/heavy/run_Aeval_$n.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
if [ -n "$WAIT" ]; then wf=${WAIT%%:*}; wk=${WAIT#*:}; while ! grep -q "$wk" /workspace/heavy/$wf 2>/dev/null; do sleep 20; done; fi
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5
Q4=/workspace/ollama/blobs/sha256-370c2879f17648d337b0ab4e208fdce348e24d1060064e93d7645daafd56d39c
L=/workspace/tripilot/${n}_lora_f16.gguf
[ -f $L ] || { say "어댑터 없음 $L"; echo ALLDONE_AEVAL_$n >> $LOG; exit 1; }
say "D + 확률 $n";  LOGPROBS=1 GGUF=$Q4 LORA=$L TAG=lp_q4km_$n PORT=8321 python3 d_test_llama_lp.py > lp_d_$n.out 2>&1
say "D2 $n";        LOGPROBS=1 PROMPTS=all_prompts_d2.json GGUF=$Q4 LORA=$L TAG=lp_d2_q4km_$n PORT=8322 python3 d_test_llama_lp.py > lp_d2_$n.out 2>&1
say "D3 $n";        PROMPTS=all_prompts_d3.json GGUF=$Q4 LORA=$L TAG=d3_q4km_$n PORT=8323 python3 d_test_llama.py > d3_q4km_$n.out 2>&1
say "H $n";         LOGPROBS=1 PROMPTS=all_prompts_h.json GGUF=$Q4 LORA=$L TAG=lp_h_q4km_$n PORT=8324 python3 d_test_llama_lp.py > lp_h_$n.out 2>&1
say "MX $n";        LOGPROBS=1 PROMPTS=all_prompts_mx.json GGUF=$Q4 LORA=$L TAG=lp_mx_q4km_$n PORT=8325 python3 d_test_llama_lp.py > lp_mx_$n.out 2>&1
say "끝: $(tail -n 1 lp_mx_$n.out | cut -c1-60)"
echo ALLDONE_AEVAL_$n >> $LOG
