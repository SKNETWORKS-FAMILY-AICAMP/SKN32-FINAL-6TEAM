#!/bin/bash
# 새 서버 대기열 18 — 「둘 다 찾기(C)」 데이터: Qwen3.8 27B 가 일정 항목 번호를 배열(items)로 답하게 해 mix8~12 를 푼다(생각 끔·온도 0). B17(정의 한 줄)이 끝나면 이어서, 끝나면 B16(섞기)이 이어서.
cd /root
export HF_HUB_DISABLE_XET=1 OLLAMA_MODELS=/root/ollama_models OLLAMA_HOST=127.0.0.1:11434
LOG=/root/run_B18.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
stop_ollama() { ollama ps | tail -n +2 | awk '{print $1}' | while read m; do ollama stop $m; done; sleep 5; }
while ! grep -q ALLDONE_B17 /root/run_B17.log; do sleep 30; done
cp /root/work/mix8.json /root/work/mix9.json /root/work/mix10.json /root/work/mix11.json /root/work/mix12.json /root/work2/ 2>/dev/null
cd /root/work2
pgrep -x ollama > /dev/null || (nohup ollama serve > /root/ollama_serve.log 2>&1 & sleep 8)
say "Qwen3.8 27B 내려받기"
ollama pull qwen3.8:27b >> $LOG 2>&1
for s in mix11 mix10 mix12 mix9 mix8; do
  say "Qwen3.8 27B 둘 다 찾기 $s"
  JOB=$s python3 llm_point_multi.py qwen3.8:27b 2>&1 | tail -n 1 >> $LOG
done
stop_ollama
ollama rm qwen3.8:27b >> $LOG 2>&1
say "MULTI_B_DONE"
echo ALLDONE_B18 >> $LOG
