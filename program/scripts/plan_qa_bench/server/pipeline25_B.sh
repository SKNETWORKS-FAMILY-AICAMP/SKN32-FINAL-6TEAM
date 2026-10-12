#!/bin/bash
# CPU 4코어 전용 실측(실제 일정 질문 프롬프트) — run_B21_cpu.sh 가 내려받은 4B·12B 모델로 cpu_bench.py 를 돌린다.
LOG=/root/cpu_bench2.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
while [ ! -f /root/gguf_cpu/gguf/Winnow-12B-Q8_0.gguf ] || ! grep -q ALLDONE_B21 /root/cpu_bench.log; do sleep 10; done
cd /root/work
for M in /root/gguf_cpu/FrogNano-4B-2609-Q8_0.gguf /root/gguf_cpu/gguf/Winnow-12B-Q8_0.gguf; do
  say "CPU 실측 $(basename $M)"
  /root/venv_imajev/bin/python cpu_bench.py $M 60-63 4 2>&1 | tail -n 1 >> $LOG
done
say "CPU_BENCH2_DONE"
echo ALLDONE_B22 >> $LOG
