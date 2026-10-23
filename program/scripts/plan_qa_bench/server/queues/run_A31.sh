#!/bin/bash
# 서버 A 대기열 31 (2026-10-07) — oos1(잡담 부정 사례를 더해 다시 가르친 E4B)을 다른 기반 양자화(QAT Q4_0)에서도 시험한다: 잡담 오지목 감소가 기반 양자화에 묶인 값이 아닌지.
#  서비스 기반 Q4_K_M 에서의 값(대기열 29)과 같은 세트 · 같은 설정. 시드 1(e4bt)도 QAT 기반에서 같이 잰다(비교 짝) — D2 · D3 만, D 는 시간상 oos1 만.
LOG=/workspace/heavy/run_A31.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5
QAT=/workspace/ollama/blobs/sha256-e8b6a059ba86947a44ace84d6e5679795bc41862c25c30513142588f0e9dba1d
L1=/workspace/tripilot/oos1_lora_f16.gguf
L0=/workspace/tripilot/e4bt_lora_f16.gguf
say "31: D3 oos1 QAT"
PROMPTS=all_prompts_d3.json GGUF=$QAT LORA=$L1 TAG=d3_qat_oos1 PORT=8270 python3 d_test_llama.py > d3_qat_oos1.out 2>&1
say "31: D3 e4bt QAT"
PROMPTS=all_prompts_d3.json GGUF=$QAT LORA=$L0 TAG=d3_qat_e4bt PORT=8271 python3 d_test_llama.py > d3_qat_e4bt.out 2>&1
say "31: D2 oos1 QAT"
LOGPROBS=1 PROMPTS=all_prompts_d2.json GGUF=$QAT LORA=$L1 TAG=lp_d2_qat_oos1 PORT=8272 python3 d_test_llama_lp.py > lp_d2_qat_oos1.out 2>&1
say "31: D2 e4bt QAT"
LOGPROBS=1 PROMPTS=all_prompts_d2.json GGUF=$QAT LORA=$L0 TAG=lp_d2_qat_e4bt PORT=8273 python3 d_test_llama_lp.py > lp_d2_qat_e4bt.out 2>&1
say "31: D oos1 QAT"
LOGPROBS=1 GGUF=$QAT LORA=$L1 TAG=lp_qat_oos1 PORT=8274 python3 d_test_llama_lp.py > lp_d_qat_oos1.out 2>&1
say "31: D oos1 QAT 끝: $(tail -n 1 lp_d_qat_oos1.out | cut -c1-60)"
echo ALLDONE_A31 >> $LOG
