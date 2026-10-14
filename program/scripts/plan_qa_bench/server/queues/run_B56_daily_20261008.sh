#!/usr/bin/env bash
# 일일 연구 첫 실험: 기존 대기열을 보존하고 FINCH식 학습률을 코사인 대조군과 비교한다.
# 새 폴더만 사용한다. 모델·자료를 지우거나 새 기반 모델을 받지 않는다.
set -euo pipefail
export HF_HUB_DISABLE_XET=1 OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
PY=/root/venv_imajev/bin/python
MODEL=/root/hf_models/gemma-4-E4B-it
TRAIN=/root/work/train_oos2.jsonl
WORK=/root/daily_rag_20261008
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
[ -f "$MODEL/config.json" ] && [ -f "$TRAIN" ]
sha256sum "$TRAIN" qlora_train_finch.py finch_schedule.py > "$WORK/inputs.sha256"

# B54가 자료 선택을 기다리는 동안 최소 통합 검증을 한다. 본 학습은 B54 뒤다.
if [ ! -f "$WORK/SMOKE_DONE" ]; then
  waitgpu
  say 'FINCH 통합 검증 시작: 학습 자료 첫 16개, optimizer 4회'
  taskset -c 0-31 "$PY" qlora_train_finch.py "$MODEL" "$TRAIN" "/root/adapters/smoke_finch_20261008" \
    --schedule finch --epochs 1 --rank 16 --accum 4 --limit 16 --seed 20261012 \
    > "$WORK/smoke.log" 2>&1
  "$PY" - <<'PYEOF'
import json, math
p='/root/adapters/smoke_finch_20261008/recipe_complete.json'
r=json.load(open(p))
assert r['used_rows']==16 and r['optimizer_steps']==4 and r['status']=='completed'
assert len(r['rate_trace'])==4
assert all(math.isfinite(x['lr']) and 0 < x['lr'] <= 5e-5 for x in r['rate_trace'])
print('SMOKE_VERIFIED 16/16 rows; 4/4 optimizer steps')
PYEOF
  touch "$WORK/SMOKE_DONE"
  say 'FINCH 통합 검증 완료'
fi

say '기존 세 후보 대기열 B54 종료 대기'
while ! grep -q ALLDONE_B54 /root/run_B31.log; do sleep 30; done
say 'B54 종료 확인'
for mode in cosine finch; do
  tag="oos2r_${mode}_5e5_20261008"
  if [ -f "$WORK/${mode}_DONE" ]; then continue; fi
  waitgpu
  say "$tag 본 학습 시작"
  taskset -c 0-31 "$PY" qlora_train_finch.py "$MODEL" "$TRAIN" "/root/adapters/$tag" \
    --schedule "$mode" --epochs 2 --lr 5e-5 --finch-base-rate 2e-5 --finch-cap 5e-5 \
    --finch-alpha 0.9 --rank 16 --accum 8 --seed 20261012 > "$WORK/train_${mode}.log" 2>&1
  say "$tag 본 학습 완료; 변환 시작"
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
  say "$tag 기본 평가 완료; 추가 평가와 독립 보류 평가는 일일 작업에서 이어간다"
done
touch "$WORK/ALLDONE"
say 'B56 학습·변환·기본 평가 완료; 최종 모델 채택 아님'
