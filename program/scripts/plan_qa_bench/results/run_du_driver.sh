#!/bin/bash
# 결정 단위 재생을 Codex 모델 하나로 3번 반복(앞 반복이 끝나야 다음) — 동시 호출 수는 인자로
M=$1; W=$2
for r in 1 2 3; do python codex_du_run.py $M $r $W >> results/codex_du/${M}_driver.log 2>&1; done
echo DRIVER_DONE_$M >> results/codex_du/${M}_driver.log
