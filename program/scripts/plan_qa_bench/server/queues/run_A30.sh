#!/bin/bash
# 서버 A 대기열 30 (2026-10-07) — 다시 가르친 짚기 모델(oos<i>)이 항목을 고른 답을 FrogNano · gemma4:12b 가 「짧은 확인 질문」으로 검토한다.
#  순서: 대기열 29(oos<i> 의 D · D2 · D3)가 끝나길 기다림 → 서버 A 안에서 검토 입력을 다시 만듦(기존 시드 1·2·3 답 + oos<i> 답, 같은 키는 건너뜀) → 검토자 둘이 새 입력만 이어서 풀이.
#  사용: bash run_A30.sh oos1
n=${1:-oos1}
LOG=/workspace/heavy/run_A30.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
while ! grep -q ALLDONE_A29_$n /workspace/heavy/run_A29.log 2>/dev/null; do sleep 15; done
mkdir -p vb/results
[ -e vb/results/d_test ] || ln -s /workspace/heavy vb/results/d_test
[ -e vb/results/empty_probe ] || ln -s /workspace/heavy vb/results/empty_probe
cp verify_inputs.json verify_inputs.before_$n.json
VERIFY_EXTRA_TAGS=${EXTRA_TAGS:-$n} python3 vb/build_verify_inputs.py /workspace/heavy/verify_inputs.json >> $LOG 2>&1
say "30: 검토 입력 다시 만듦 ($n 포함) — $(python3 -c "import json;print(len(json.load(open('/workspace/heavy/verify_inputs.json'))))") 건"
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5
say "30: FrogNano 검토 이어서"
GGUF=/workspace/ollama/blobs/sha256-ea42d264c21d88b9bf6ce583bb3fd4dfddb22eb5b30efba9e305c56f75974c86 TAG=frog PORT=8260 python3 verify_llama.py > verify_frog_$n.out 2>&1
say "30: Frog 끝: $(tail -n 1 verify_frog_$n.out | cut -c1-60)"
say "30: gemma4:12b 검토 이어서"
GGUF=/workspace/ollama/blobs/sha256-1278394b693672ac2799eadc9a83fd98259a6a88a40acfb1dcaa6c6fc895a606 TAG=g12b PORT=8261 python3 verify_llama.py > verify_g12b_$n.out 2>&1
say "30: 12B 끝: $(tail -n 1 verify_g12b_$n.out | cut -c1-60)"
echo ALLDONE_A30_$n >> $LOG
