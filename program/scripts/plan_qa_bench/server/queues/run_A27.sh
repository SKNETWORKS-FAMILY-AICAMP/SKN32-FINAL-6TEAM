#!/bin/bash
# 서버 A 대기열 27 (2026-10-07) — 거부권 검토자의 「짧은 확인 질문」 판: 짚기 모델(시드 1·2·3)이 항목을 골랐던 모든 답(D 1,258 · D2 201 · D3 203, 중복 제거 1,662건)에 대해 FrogNano 와 가르치기 전 E4B(QAT)가 YES/NO 로 검토한다.
LOG=/workspace/heavy/run_A27.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5
say "27: FrogNano 검토"
GGUF=/workspace/ollama/blobs/sha256-ea42d264c21d88b9bf6ce583bb3fd4dfddb22eb5b30efba9e305c56f75974c86 TAG=frog PORT=8240 python3 verify_llama.py > verify_frog.out 2>&1
say "27: Frog 끝: $(tail -n 1 verify_frog.out | cut -c1-60)"
say "27: 가르치기 전 E4B(QAT) 검토"
GGUF=/workspace/ollama/blobs/sha256-e8b6a059ba86947a44ace84d6e5679795bc41862c25c30513142588f0e9dba1d TAG=e4bbase PORT=8241 python3 verify_llama.py > verify_e4bbase.out 2>&1
say "27: E4B 끝: $(tail -n 1 verify_e4bbase.out | cut -c1-60)"
echo ALLDONE_A27 >> $LOG
