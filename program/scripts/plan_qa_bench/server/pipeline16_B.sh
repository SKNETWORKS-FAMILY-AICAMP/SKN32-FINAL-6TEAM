#!/bin/bash
# 새 서버 대기열 15 — ① mix12 의 Decider-12B 8비트 순환 회전(10·21·32 — R4 가 mix12 에서도 나오게) ② Qwen3.8 27B 「생각 켬」(medium) mix11 → mix10 → low mix11.
cd /root
export HF_HUB_DISABLE_XET=1 OLLAMA_MODELS=/root/ollama_models OLLAMA_HOST=127.0.0.1:11434
LOG=/root/run_B15.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
stop_ollama() { ollama ps | tail -n +2 | awk '{print $1}' | while read m; do ollama stop $m; done; sleep 5; }
for r in 10 21 32; do
  say "Decider-12B 8비트 순환 회전 $r (mix12)"
  ROT=$r Q8=1 MODEL=Mapika/decider-12b TAG=decider12bq8rot$r SETS=mix12 /root/venv_imajev/bin/python dec_lib_run_q.py > /root/d12q8_rot${r}_m12.log 2>&1
  say "회전 $r exit=$?"
done
rm -rf /root/.cache/huggingface/hub/models--Mapika--decider-12b
ollama rm granite4.2:30b >> $LOG 2>&1
cp /root/work/mix10.json /root/work/mix11.json /root/work/mix12.json /root/work2/ 2>/dev/null
cd /root/work2
pgrep -x ollama > /dev/null || (nohup ollama serve > /root/ollama_serve.log 2>&1 & sleep 8)
say "Qwen3.8 27B 내려받기"
ollama pull qwen3.8:27b >> $LOG 2>&1
for cfg in "medium mix11" "medium mix10" "low mix11"; do
  set -- $cfg
  say "Qwen3.8 27B 생각 $1 $2"
  THINK=$1 JOB=$2 python3 llm_point_think.py qwen3.8:27b 2>&1 | tail -n 2 >> $LOG
done
stop_ollama
say "THINK_B_DONE"
echo ALLDONE_B15 >> $LOG
