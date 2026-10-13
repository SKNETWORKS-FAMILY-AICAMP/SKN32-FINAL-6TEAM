#!/bin/bash
# 서버에서: E4B 미만 넘김 모델 후보를 heavy·mix4 에서 직접 짚기로 잰다(llm_point_heavy.py, 같은 질의문). 모델은 재고 나서 지워 디스크를 아낀다.
export OLLAMA_HOST=127.0.0.1:11434
cd /workspace/heavy
until [ -f /workspace/experts/ft_e16b_scores.json ] || ! ps aux | grep -q "[f]t_embed.py"; do sleep 20; done
for m in gemma4:e2b qwen3.5:4b qwen3.5:2b qwen3.5:0.8b granite4:3b granite4:1b; do
  echo "[$(date +%H:%M)] $m 받기"
  if ollama pull "$m" > /tmp/pull_small.log 2>&1; then
    JOB=heavy python3 llm_point_heavy.py "$m" 2>&1 | tail -1
    JOB=mix4 python3 llm_point_heavy.py "$m" 2>&1 | tail -1
    ollama rm "$m" > /dev/null 2>&1
  else
    echo "FAIL pull $m $(tail -c 120 /tmp/pull_small.log | tr '\n\r' '  ')"
  fi
done
echo "[$(date +%H:%M)] SMALLDONE"
