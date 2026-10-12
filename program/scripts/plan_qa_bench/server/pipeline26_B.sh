#!/bin/bash
# CPU 4코어 실측 3 — 26B-A4B 계열(OpenJev Q4_K_M, Gemma 4 26B-A4B 와 같은 구조: 활성 3.8B · 저장 약 19GB)의 CPU 속도. 앞 실측(B22)이 끝나면 이어서.
export HF_HUB_DISABLE_XET=1
LOG=/root/cpu_bench3.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
while ! grep -q ALLDONE_B22 /root/cpu_bench2.log; do sleep 15; done
/root/venv_imajev/bin/python - >> $LOG 2>&1 <<'PY'
from huggingface_hub import hf_hub_download
print('받음', hf_hub_download('ggml-org/OpenJev-GGUF', 'OpenJev-Q4_K_M.gguf', local_dir='/root/gguf_cpu'))
PY
cd /root/work
say "CPU 실측 OpenJev-Q4_K_M(MoE)"
/root/venv_imajev/bin/python cpu_bench.py /root/gguf_cpu/OpenJev-Q4_K_M.gguf 60-63 4 2>&1 | tail -n 1 >> $LOG
rm -f /root/gguf_cpu/OpenJev-Q4_K_M.gguf
say "CPU_BENCH3_DONE"
echo ALLDONE_B23 >> $LOG
