#!/usr/bin/env bash
# 기존 두 난수 설정 뒤 세 번째 독립 시드로 학습률 방법의 편차를 확인한다.
set -euo pipefail
export HF_HUB_DISABLE_XET=1 OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
PY=/root/venv_imajev/bin/python
MODEL=/root/hf_models/gemma-4-E4B-it
TRAIN=/root/work/train_oos2.jsonl
PREVIOUS=/root/daily_rag_repeat_20261008
WORK=/root/daily_rag_seed3_20261009
SEED=20261014
mkdir -p "$WORK"
exec 9>"$WORK/queue.lock"
flock -n 9 || { echo '이미 실행 중'; exit 0; }
[ ! -f "$WORK/ALLDONE" ] || { echo '이미 완료'; exit 0; }
cd "$WORK"
trap 'echo "FAILED line=$LINENO exit=$?" >> "$WORK/status.log"' ERR
say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$WORK/status.log"; }
waitgpu() {
  while [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')" -ge 1000 ]; do sleep 30; done
}
[ -f "$MODEL/config.json" ] && [ -f "$TRAIN" ] && [ -f /root/daily_rag_20261008/SMOKE_DONE ]
sha256sum -c "$WORK/frozen_inputs.sha256"
say 'B57 학습·변환·기본 평가 종료 대기; GPU 사용 시작 안 함'
while [ ! -f "$PREVIOUS/ALLDONE" ]; do
  if [ -f "$PREVIOUS/queue.pid" ] && ! kill -0 "$(cat "$PREVIOUS/queue.pid")" 2>/dev/null; then
    say '선행 작업 종료 표시 없이 프로세스가 끝남; 원인 확인 필요'
    exit 2
  fi
  sleep 30
done
say '선행 작업 완료 확인'
# 첫째·셋째는 cosine→finch, 둘째는 finch→cosine 순서다. 독립 보류 검증과 구분한다.
for mode in cosine finch; do
  tag="oos2r_${mode}_5e5_seed${SEED}_20261009"
  if [ -f "$WORK/${mode}_DONE" ]; then continue; fi
  waitgpu
  say "$tag 본 학습 시작"
  taskset -c 0-31 "$PY" qlora_train_finch.py "$MODEL" "$TRAIN" "/root/adapters/$tag" \
    --schedule "$mode" --epochs 2 --lr 5e-5 --finch-base-rate 2e-5 --finch-cap 5e-5 \
    --finch-alpha 0.9 --rank 16 --accum 8 --seed "$SEED" > "$WORK/train_${mode}.log" 2>&1
  "$PY" - "$mode" "$tag" "$SEED" <<'PYEOF'
import json, sys
mode, tag, seed = sys.argv[1:]
r = json.load(open('/root/adapters/' + tag + '/recipe_complete.json'))
assert r['status'] == 'completed' and r['schedule'] == mode and r['seed'] == int(seed)
assert r['epochs'] == 2 and r['rank'] == 16 and r['accum'] == 8
assert r['train_sha256'] == '07e6f7156883f9adb91812b2306b6dd813f60b189ae1da2610ae8c20d2d55a3c'
assert r['optimizer_steps'] == len(r['rate_trace']) and r['optimizer_steps'] > 0
assert all(0 < x['lr'] <= 5e-5 for x in r['rate_trace'])
print('RECIPE_VERIFIED', mode, seed, r['optimizer_steps'])
PYEOF
  say "$tag 학습 완료; 변환 시작"
  CUDA_VISIBLE_DEVICES='' taskset -c 96-111 "$PY" /root/llama.cpp/convert_lora_to_gguf.py \
    --base "$MODEL" --outtype f16 --outfile "$WORK/${tag}_lora_f16.gguf" "/root/adapters/$tag" \
    > "$WORK/convert_${mode}.log" 2>&1
  sha256sum "$WORK/${tag}_lora_f16.gguf" >> "$WORK/adapters.sha256"
  waitgpu
  cd /root/work
  CONF=1 taskset -c 0-31 "$PY" qlora_eval2.py "$MODEL" "/root/adapters/$tag" "$tag" mix10,mix11,mix12,mix8,mix9 \
    > "$WORK/eval_${mode}.log" 2>&1
  grep -q "EVAL_DONE $tag" "$WORK/eval_${mode}.log"
  cd "$WORK"
  touch "$WORK/${mode}_DONE"
  say "$tag 기본 평가 완료; 추가 평가·독립 보류 검증 대기"
done
touch "$WORK/ALLDONE"
say 'B58 세 번째 난수 설정의 학습·변환·기본 평가 완료; 제품 채택 아님'
