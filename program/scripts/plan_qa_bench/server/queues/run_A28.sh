#!/bin/bash
# 서버 A 대기열 28 (2026-10-07) — 짧은 확인 질문 검토자 후보를 더 넓힌다: gemma4:12b(제품 결정 모델) · 서비스 기반 E4B Q4_K_M(가르치기 전). 같은 입력 1,662건.
LOG=/workspace/heavy/run_A28.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5
say "28: gemma4:12b 검토"
GGUF=/workspace/ollama/blobs/sha256-1278394b693672ac2799eadc9a83fd98259a6a88a40acfb1dcaa6c6fc895a606 TAG=g12b PORT=8242 python3 verify_llama.py > verify_g12b.out 2>&1
say "28: 12B 끝: $(tail -n 1 verify_g12b.out | cut -c1-60)"
say "28: E4B Q4_K_M(서비스 기반, 학습 없음) 검토"
GGUF=/workspace/ollama/blobs/sha256-370c2879f17648d337b0ab4e208fdce348e24d1060064e93d7645daafd56d39c TAG=e4bq4km PORT=8243 python3 verify_llama.py > verify_e4bq4km.out 2>&1
say "28: E4B Q4_K_M 끝: $(tail -n 1 verify_e4bq4km.out | cut -c1-60)"
echo ALLDONE_A28 >> $LOG
