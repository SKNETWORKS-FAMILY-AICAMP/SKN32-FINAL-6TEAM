#!/bin/bash
# 서버 B 에서: 가르친 E4B GGUF 를 CPU 전용 llama-server 3개(코어 64~126, 학습 대기열이 쓰는 0~31 은 건드리지 않는다)로 띄우고,
#  전체 2,735문제를 생각 모드 끄기로 다시 불러 /root/work/fix_out_<조각>.jsonl 에 남긴다. GPU 는 쓰지 않는다(-ngl 0).
cd /root/work
pkill -f "llama-server -m /root/e4bt-Q8_0.gguf" ; sleep 2
MODE=${1:-nothink}
for k in 0 1 2; do
  lo=$((64 + k*21)); hi=$((lo + 20)); port=$((8211 + k))
  nohup taskset -c $lo-$hi /root/llama.cpp/build/bin/llama-server -m /root/e4bt-Q8_0.gguf -c 4096 -np 1 -t 21 --port $port --host 127.0.0.1 --jinja -ngl 0 > /root/work/llama_fix_$k.log 2>&1 < /dev/null &
done
for k in 0 1 2; do
  port=$((8211 + k))
  until curl -s -m 3 http://127.0.0.1:$port/health | grep -q ok; do sleep 3; done
done
for k in 0 1 2; do
  port=$((8211 + k))
  if [ "$MODE" = thinking_on ]; then
    nohup python3 empty_fix_run.py $port $k 3 all_prompts.json fix_on_$k.jsonl thinking_on > fix_on_run_$k.log 2>&1 < /dev/null &
  else
    nohup python3 empty_fix_run.py $port $k 3 all_prompts.json fix_out_$k.jsonl > fix_run_$k.log 2>&1 < /dev/null &
  fi
done
echo started
