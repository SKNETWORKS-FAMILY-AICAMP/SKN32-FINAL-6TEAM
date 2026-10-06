#!/bin/bash
# 대기열 47 — 대기열 46 이 끝나면: 오늘(2026-10-06) JevBench v1.6.0 에서 4B 급 Jev 계열 결정 모델 상위(Plumb-4B 헤드라인 1위 · spark-s1-4b-v6 지능 1위)와 같은 Gemma-4-E4B 바탕 Jev 계열(jevify-gemma4-e4b)을
#  가르친 E4B · 가르친 Winnow-E4B 와 똑같은 레시피(QLoRA r16 · 2 에폭 · lr 2e-4 · 같은 학습 자료 · 같은 평가)로 가르쳐 비교한다. 후보는 후보 하나씩 받고 → 학습 → 평가 → 기반 모델 폴더 삭제(다시 받을 수 있다).
export HF_HUB_DISABLE_XET=1 OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
PY=/root/venv_imajev/bin/python
LOG=/root/run_B31.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
SETS=val,mix10,mix11,mix12,mix8,mix9
cd /root/work
while ! grep -q ALLDONE_B31 $LOG; do sleep 30; done
say "47: 대기열 46 끝남 — 후보 가르치기 시작"
freegb() { df -BG --output=avail /root | tail -1 | tr -dc 0-9; }
ensure_space() {  # ensure_space <필요GB> — 모자라면 평가가 끝난 시험의 기반 모델 폴더(다시 받을 수 있는 것)만 지운다
  need=$1
  for d in /root/hf_models/gemma-4-E2B-it /root/hf_models/kanana-2-3b-instruct; do
    [ "$(freegb)" -ge "$need" ] && return 0
    [ -d "$d" ] && { say "47: 디스크 여유 $(freegb)GB < ${need}GB — 평가 끝난 기반 모델 폴더 지움 $d"; rm -rf "$d"; }
  done
  [ "$(freegb)" -ge "$need" ]
}
cand() {  # cand <이름> <허깅페이스 저장소> <계열 gemma|qwen> <필요GB> <시드>
  name=$1; repo=$2; fam=$3; need=$4; seed=$5
  model=/root/hf_models/$name
  nt=""; [ "$fam" = qwen ] && nt="1"
  ensure_space $need || { say "47: $name 디스크 부족($(freegb)GB) — 건너뜀"; return; }
  say "47: $name 받기 시작 ($repo)"
  $PY - "$repo" "$model" >> /root/dl_$name.log 2>&1 <<'PYEOF'
import sys
from huggingface_hub import snapshot_download, HfApi
repo, d = sys.argv[1], sys.argv[2]
print('수정판', HfApi().model_info(repo).sha)
snapshot_download(repo, local_dir=d)
print('받음', d)
PYEOF
  say "47: $name 받기 끝 — $(grep 수정판 /root/dl_$name.log | tail -1) · 크기 $(du -sm $model 2>/dev/null | cut -f1)MB"
  [ -f $model/config.json ] || { say "47: $name 모델 폴더 없음 — 건너뜀"; return; }
  taskset -c 0-31 $PY qlora_train2.py $model train.jsonl /root/adapters/smoke_$name --family $fam --epochs 1 --accum 4 --limit 16 --seed $seed > /root/qlora_smoke_$name.log 2>&1
  if [ $? -ne 0 ]; then say "47: $name 학습 스모크 실패 — qlora_smoke_$name.log 확인"; rm -rf $model; return; fi
  say "47: $name 학습 스모크 통과 — 본 학습 시작"
  taskset -c 0-31 $PY qlora_train2.py $model train.jsonl /root/adapters/$name --family $fam --epochs 2 --lr 2e-4 --rank 16 --accum 8 --seed $seed > /root/qlora_train_$name.log 2>&1
  if [ $? -ne 0 ]; then say "47: $name 본 학습 실패 — qlora_train_$name.log 확인"; rm -rf $model; return; fi
  say "47: $name 학습 끝 — 평가 스모크"
  NOTHINK=$nt LIMIT=4 taskset -c 0-31 $PY qlora_eval2.py $model /root/adapters/$name ${name}smoke val --base > /root/qlora_eval_smoke_$name.log 2>&1
  if ! grep -q EVAL_DONE /root/qlora_eval_smoke_$name.log; then say "47: $name 평가 스모크 실패"; rm -rf $model; return; fi
  say "47: $name 평가 스모크 통과 — 본 평가"
  NOTHINK=$nt CONF=1 taskset -c 0-31 $PY qlora_eval2.py $model /root/adapters/$name $name $SETS --base > /root/qlora_eval_$name.log 2>&1
  say "47: $name 평가 끝: $(tail -n 1 /root/qlora_eval_$name.log | cut -c1-80)"
  rm -rf $model
}
cand plumb4b crh225/plumb-4b qwen 12 20261006
cand spark_s1_4b abhishek085/spark-s1-4b-v6 qwen 12 20261006
cand jevify_e4b kushalpatil/jevify-gemma4-e4b gemma 20 20261006
say "47: 대기열 47 끝"
echo ALLDONE_B47 >> $LOG
