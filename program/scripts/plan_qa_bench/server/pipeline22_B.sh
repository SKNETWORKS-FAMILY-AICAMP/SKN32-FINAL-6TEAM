#!/bin/bash
# 새 서버 대기열 19 — Cloudflare Clef Flash(9B, Qwen3.5-9B 기반)·Clef(27B, Qwen3.8-27B 기반) 결정 모델을 올라마 /v1/systemone 으로 mix11 → mix10 → mix12 → mix9 → mix8 에서 푼다.
#  요청 형식은 지금까지 결정 모델(Jev 호환)과 같다(choice + 선택지 + none). 올라마 0.35.1 이상 필요(이 GPU 서버는 0.35.1).
cd /root/work
export OLLAMA_MODELS=/root/ollama_models OLLAMA_HOST=127.0.0.1:11434
LOG=/root/run_B19.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
pgrep -x ollama > /dev/null || (nohup ollama serve > /root/ollama_serve.log 2>&1 & sleep 8)
for m in clef-flash clef; do
  tag=$(echo $m | tr -d '-')
  say "$m 내려받기"
  ollama pull $m >> $LOG 2>&1
  say "$m 받기 exit=$?"
  for s in mix11 mix10 mix12 mix9 mix8; do
    say "$m $s"
    DEC_MODEL=$m DEC_URL=http://127.0.0.1:11434/v1/systemone DEC_TAG=$tag SETS=$s /root/venv_imajev/bin/python dec_run.py 2>&1 | tail -n 1 >> $LOG
  done
  ollama stop $m
  sleep 5
done
say "CLEF_DONE"
echo ALLDONE_B19 >> $LOG
