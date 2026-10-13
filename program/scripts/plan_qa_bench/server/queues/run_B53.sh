#!/bin/bash
# 대기열 53 (2026-10-07) — 「가르친 E4B 의 잡담 오지목이 시드마다 갈리는 문제」의 해결 학습: 학습 자료에 잡담 · 구어체를 정답 「없음」으로 400개 더한 train_oos.jsonl(1,713행, 「없음」 37%)로
#  같은 레시피(QLoRA r16 · 2 에폭 · lr 2e-4)로 시드 3개를 가르친다. 단계마다 GPU 가 비길 기다리고(waitgpu), 학습 → HF 4비트 769문제 평가 → 어댑터를 GGUF 로 변환(CPU)까지 한다.
#  변환한 어댑터는 서버 A(llama.cpp GPU)로 보내 D 시험으로 잰다(잡담 오지목이 시드 사이에 안 갈리는지). 대기열 50 의 남은 단계(Plumb · 시드 4)와 대기열 51(시드 5 · e4bm2 · 시드 6)은 이 해결이 더 급해 접는다(사용자 지시 「원인 찾고 해결」).
export HF_HUB_DISABLE_XET=1 OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
PY=/root/venv_imajev/bin/python
LOG=/root/run_B31.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
E4B=/root/hf_models/gemma-4-E4B-it
SETS=mix10,mix11,mix12,mix8,mix9
cd /root/work
waitgpu() {
  while [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -dc 0-9)" -ge 1000 ]; do sleep 30; done
}
say "53: 시작 — jevify 평가가 끝나 GPU 가 비길 기다림"
waitgpu
[ -f train_oos.jsonl ] || { say "53: train_oos.jsonl 없음 — 중단"; echo ALLDONE_B53 >> $LOG; exit 1; }
i=0
for seed in 20261012 20261013 20261014; do
  i=$((i+1)); name=oos$i
  waitgpu
  taskset -c 0-31 $PY qlora_train2.py $E4B train_oos.jsonl /root/adapters/smoke_$name --family gemma --epochs 1 --accum 4 --limit 16 --seed $seed > /root/qlora_smoke_$name.log 2>&1 || { say "53: $name 학습 스모크 실패"; continue; }
  say "53: $name 스모크 통과 — 본 학습(시드 $seed)"
  waitgpu
  taskset -c 0-31 $PY qlora_train2.py $E4B train_oos.jsonl /root/adapters/$name --family gemma --epochs 2 --lr 2e-4 --rank 16 --accum 8 --seed $seed > /root/qlora_train_$name.log 2>&1 || { say "53: $name 본 학습 실패 — qlora_train_$name.log"; continue; }
  say "53: $name 학습 끝 — 어댑터 GGUF 변환(CPU)"
  CUDA_VISIBLE_DEVICES="" taskset -c 96-111 $PY /root/llama.cpp/convert_lora_to_gguf.py --base $E4B --outtype f16 --outfile /root/work/${name}_lora_f16.gguf /root/adapters/$name > /root/convert_$name.log 2>&1 && say "53: $name 변환 끝 /root/work/${name}_lora_f16.gguf" || say "53: $name 변환 실패"
  waitgpu
  CONF=1 taskset -c 0-31 $PY qlora_eval2.py $E4B /root/adapters/$name $name $SETS > /root/qlora_eval_$name.log 2>&1
  say "53: $name 평가 끝: $(tail -n 1 /root/qlora_eval_$name.log | cut -c1-80)"
done
say "53: 대기열 53 끝"
echo ALLDONE_B53 >> $LOG
