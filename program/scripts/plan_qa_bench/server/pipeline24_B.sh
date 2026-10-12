#!/bin/bash
# GPU 없는 배포(오라클 ARM 4코어·24GB 등) 가능성 1차 측정 — 이 GPU 서버의 CPU 4코어만 써서(taskset, GPU 끔) llama.cpp 로 프롬프트 처리 속도(pp)와 생성 속도(tg)를 잰다.
#  모델: 4B(FrogNano Q8_0, Qwen3.5-4B 구조) · 12B(Winnow-12B Q8_0, Gemma-4-12B 구조). 이 서버 CPU 는 x86 이라 ARM(Neoverse N1 급)보다 빠르다 — 그대로 쓰지 말고 하한이 아니라 「상한」으로 읽는다.
export HF_HUB_DISABLE_XET=1
LOG=/root/cpu_bench.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
mkdir -p /root/gguf_cpu
lscpu | grep -E "Model name|^CPU\(s\)|Thread|Flags" | cut -c1-140 >> $LOG
/root/venv_imajev/bin/python - >> $LOG 2>&1 <<'PY'
from huggingface_hub import hf_hub_download
print('받음', hf_hub_download('bartowski/FrogNano-4B-2609-GGUF', 'FrogNano-4B-2609-Q8_0.gguf', local_dir='/root/gguf_cpu'))
print('받음', hf_hub_download('EldanRing/Winnow-12B', 'gguf/Winnow-12B-Q8_0.gguf', local_dir='/root/gguf_cpu'))
PY
BENCH=/root/llama.cpp/build/bin/llama-bench
for M in /root/gguf_cpu/FrogNano-4B-2609-Q8_0.gguf /root/gguf_cpu/gguf/Winnow-12B-Q8_0.gguf; do
  for T in 4; do
    say "CPU 벤치 $(basename $M) 스레드 $T"
    taskset -c 60-63 env CUDA_VISIBLE_DEVICES= $BENCH -m $M -t $T -p 256,1024,2048 -n 16 -r 2 -ngl 0 2>&1 | grep -E "\|" >> $LOG
  done
done
say "CPU_BENCH_DONE"
echo ALLDONE_B21 >> $LOG
