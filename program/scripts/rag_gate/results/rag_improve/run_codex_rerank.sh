#!/bin/bash
# Codex 재순위기 · 판정기를 모델 둘씩 차례로(한 번에 동시 호출 2~3개) — 오류는 다시 부른다
cd "$(dirname "$0")/../../rag_improve" 2>/dev/null || cd /c/Users/playdata2/Documents/final_workspace/program/scripts/rag_gate/rag_improve
for role in rerank judge; do
  for pass in 1 2; do
    python codex_rerank_run.py gpt-6-luna $role 2 >> ../results/rag_improve/codex_run.log 2>&1 &
    python codex_rerank_run.py gpt-6-sol $role 2 >> ../results/rag_improve/codex_run.log 2>&1 &
    wait
  done
done
echo CODEX_RERANK_DONE >> ../results/rag_improve/codex_run.log
