#!/bin/bash
# 새 서버 대기열 20 — Clef Flash(9B) → Clef(27B)를 올라마 /v1/systemone 으로, 선택지 상한(26개) 때문에 묶음 대회 방식(dec_run_grouped.py)으로 mix11 → mix10 → mix12 → mix9 → mix8 에서 푼다.
cd /root/work
export OLLAMA_MODELS=/root/ollama_models OLLAMA_HOST=127.0.0.1:11434
LOG=/root/run_B20.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
pgrep -x ollama > /dev/null || (nohup ollama serve > /root/ollama_serve.log 2>&1 & sleep 8)
for m in clef-flash clef; do
  tag=$(echo $m | tr -d '-')g
  for s in mix11 mix10 mix12 mix9 mix8; do
    say "$m 묶음 대회 $s"
    DEC_MODEL=$m DEC_URL=http://127.0.0.1:11434/v1/systemone DEC_TAG=$tag SETS=$s /root/venv_imajev/bin/python dec_run_grouped.py 2>&1 | tail -n 1 >> $LOG
  done
  ollama stop $m
  sleep 5
done
say "CLEF_GROUPED_DONE"
echo ALLDONE_B20 >> $LOG
