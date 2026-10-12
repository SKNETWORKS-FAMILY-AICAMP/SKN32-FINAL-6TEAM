#!/bin/bash
# 대기열 54 (2026-10-07) — 사용자 지시 「Winnow-E4B · jevify-gemma4-e4b · spark-s1-4b-v6 세 모델에 지금까지 가장 잘 나온 학습 방법을 넣어 가르쳐」.
#  지금까지 가장 잘 나온 방법 = 잡담 부정 사례 400개를 더한 학습 자료(train_oos.jsonl 1,713행)로 같은 레시피(QLoRA r16 · 2에폭 · lr 2e-4 · accum 8)를 돌리는 것
#   (가르친 E4B 로 쟀을 때 잡담 오지목 D 5~15% → 0.3% · 어려운 세트 H 27~38% → 9.1%, 769문제는 757 로 안 떨어짐 — §92-18 · §92-22). 시드는 oos1 과 같은 20261012.
#  단계(모델마다): 기반 받기(없으면) → 스모크 → 본 학습 → 어댑터 GGUF 변환(CPU, 서버 A 에서 D · D2 · D3 · H 오지목을 재기 위해) → 769문제 평가(HF 4비트) → 기반 폴더 지움(Winnow 복원본 제외).
#  대기열 55(두 번째 잡담 보강 E4B, oos2r — 대기열 53 뒤)가 끝나길 기다리고 학습 자료는 /root/train_choice.txt 로 고른다.  — GPU 는 한 번에 하나만(겹치면 OOM 으로 조용히 건너뛰어진다).
export HF_HUB_DISABLE_XET=1 OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
PY=/root/venv_imajev/bin/python
LOG=/root/run_B31.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
SETS=mix10,mix11,mix12,mix8,mix9
SEED=20261012
cd /root/work
while ! grep -q ALLDONE_B55 $LOG; do sleep 30; done
# 학습 자료 선택: 두 번째 판(oos2r) 결과를 사람이 본 뒤 /root/train_choice.txt 에 파일 이름(train_oos.jsonl 또는 train_oos2.jsonl)을 적는다. 최대 90분 기다리고 없으면 첫 판(train_oos.jsonl).
TRAIN=train_oos.jsonl
for i in $(seq 1 180); do [ -f /root/train_choice.txt ] && { TRAIN=$(tr -d "[:space:]" < /root/train_choice.txt); break; }; sleep 30; done
say "54: 대기열 55 끝남 — 학습 자료 = $TRAIN · 세 모델 잡담 보강 학습 시작"

waitgpu() { while [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -dc 0-9)" -ge 1000 ]; do sleep 30; done; }
freegb() { df -BG --output=avail /root | tail -1 | tr -dc 0-9; }
run() {  # run <이름> <기반 폴더> <계열 gemma|qwen> <받을 저장소 또는 -> <필요GB> <평가 후 지울지 1|0>
  name=${1}_oos; model=$2; fam=$3; repo=$4; need=$5; del=$6
  nt=""; [ "$fam" = qwen ] && nt="1"
  if [ ! -f $model/config.json ]; then
    [ "$repo" = "-" ] && { say "54: $name 기반 폴더 없음 — 건너뜀"; return; }
    [ "$(freegb)" -ge "$need" ] || { say "54: $name 디스크 부족($(freegb)GB < ${need}GB) — 건너뜀"; return; }
    say "54: $name 받기 시작 ($repo)"
    $PY - "$repo" "$model" >> /root/dl_$name.log 2>&1 <<'PYEOF'
import sys
from huggingface_hub import snapshot_download, HfApi
repo, d = sys.argv[1], sys.argv[2]
print('수정판', HfApi().model_info(repo).sha)
snapshot_download(repo, local_dir=d)
print('받음', d)
PYEOF
    say "54: $name 받기 끝 — $(grep 수정판 /root/dl_$name.log | tail -1) · 크기 $(du -sm $model 2>/dev/null | cut -f1)MB"
  fi
  [ -f $model/config.json ] || { say "54: $name 모델 폴더 없음 — 건너뜀"; return; }
  waitgpu
  taskset -c 0-31 $PY qlora_train2.py $model $TRAIN /root/adapters/smoke_$name --family $fam --epochs 1 --accum 4 --limit 16 --seed $SEED > /root/qlora_smoke_$name.log 2>&1 || { say "54: $name 학습 스모크 실패 — qlora_smoke_$name.log"; [ $del = 1 ] && rm -rf $model; return; }
  say "54: $name 스모크 통과 — 본 학습 시작(시드 $SEED)"
  waitgpu
  taskset -c 0-31 $PY qlora_train2.py $model $TRAIN /root/adapters/$name --family $fam --epochs 2 --lr 2e-4 --rank 16 --accum 8 --seed $SEED > /root/qlora_train_$name.log 2>&1 || { say "54: $name 본 학습 실패 — qlora_train_$name.log"; [ $del = 1 ] && rm -rf $model; return; }
  say "54: $name 학습 끝 — 어댑터 GGUF 변환(CPU)"
  CUDA_VISIBLE_DEVICES="" taskset -c 96-111 $PY /root/llama.cpp/convert_lora_to_gguf.py --base $model --outtype f16 --outfile /root/work/${name}_lora_f16.gguf /root/adapters/$name > /root/convert_$name.log 2>&1 && say "54: $name 변환 끝 /root/work/${name}_lora_f16.gguf" || say "54: $name 변환 실패 — convert_$name.log"
  waitgpu
  NOTHINK=$nt CONF=1 taskset -c 0-31 $PY qlora_eval2.py $model /root/adapters/$name $name $SETS > /root/qlora_eval_$name.log 2>&1
  say "54: $name 평가 끝: $(tail -n 1 /root/qlora_eval_$name.log | cut -c1-80)"
  [ $del = 1 ] && rm -rf $model
}
run winnow_e4b /root/hf_models/winnow-e4b-hf gemma - 0 0
run spark_s1_4b /root/hf_models/spark_s1_4b qwen abhishek085/spark-s1-4b-v6 14 1
run jevify_e4b /root/hf_models/jevify_e4b gemma kushalpatil/jevify-gemma4-e4b 22 1
say "54: 대기열 54 끝"
echo ALLDONE_B54 >> $LOG
