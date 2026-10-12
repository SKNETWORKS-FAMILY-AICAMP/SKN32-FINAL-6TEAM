#!/bin/bash
# 결정 단위 Codex 재생에서 시스템 오류(메모리 부족 · 파일 경쟁)로 못 부른 사례만 다시 부른다 — 오류가 0이 될 때까지 최대 3번
for pass in 1 2 3; do
  for M in gpt-6-luna gpt-6-sol; do
    for r in 1 2 3; do
      n=$(python -c "import json;d=json.load(open('results/codex_du/${M}_rep${r}.json',encoding='utf-8'));print(sum(1 for x in d['rows'] if x['got'].get('error')))")
      [ "$n" -gt 0 ] && python codex_du_run.py $M $r 2 >> results/codex_du/retry.log 2>&1
    done
  done
done
echo RETRY_DONE >> results/codex_du/retry.log
