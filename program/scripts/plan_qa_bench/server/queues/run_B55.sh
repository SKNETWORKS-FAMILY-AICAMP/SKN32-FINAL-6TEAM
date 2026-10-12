#!/bin/bash
# 대기열 55 (2026-10-07) — 두 번째 잡담 보강(train_oos2.jsonl 2,613행 = 첫 판 1,713행 + 솔 6.1 이 만들고 루나 6.0 이 합의한 어려운 문장 900개: 함정 600 · 대조 300, oos1 이 틀린 문장을 유형마다 최대 70% 우선)으로
#  가르친 E4B(Gemma-4 E4B) 한 개. 첫 판(oos1)과 시드(20261012)·레시피(QLoRA r16 · 2에폭 · lr 2e-4 · accum 8)를 같게 해서 **학습 자료 차이만** 비교한다. 이름 oos2r.
#  끝나면 어댑터를 GGUF 로 바꾸고(서버 A 로 보내 D · D2 · D3 · H · MX 오지목을 잼) 769문제도 평가한다. 대기열 53(oos2 · oos3 시드)이 끝나길 기다린다 — GPU 는 한 번에 하나만.
export HF_HUB_DISABLE_XET=1 OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
PY=/root/venv_imajev/bin/python
LOG=/root/run_B31.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
E4B=/root/hf_models/gemma-4-E4B-it
SETS=mix10,mix11,mix12,mix8,mix9
SEED=20261012
cd /root/work
while ! grep -q ALLDONE_B53 $LOG; do sleep 30; done
say "55: 대기열 53 끝남 — 두 번째 잡담 보강(oos2r) 시작"
waitgpu() { while [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -dc 0-9)" -ge 1000 ]; do sleep 30; done; }
[ -f train_oos2.jsonl ] || { say "55: train_oos2.jsonl 없음 — 중단"; echo ALLDONE_B55 >> $LOG; exit 1; }
name=oos2r
waitgpu
taskset -c 0-31 $PY qlora_train2.py $E4B train_oos2.jsonl /root/adapters/smoke_$name --family gemma --epochs 1 --accum 4 --limit 16 --seed $SEED > /root/qlora_smoke_$name.log 2>&1 || { say "55: $name 스모크 실패"; echo ALLDONE_B55 >> $LOG; exit 1; }
say "55: $name 스모크 통과 — 본 학습(시드 $SEED)"
waitgpu
taskset -c 0-31 $PY qlora_train2.py $E4B train_oos2.jsonl /root/adapters/$name --family gemma --epochs 2 --lr 2e-4 --rank 16 --accum 8 --seed $SEED > /root/qlora_train_$name.log 2>&1 || { say "55: $name 본 학습 실패 — qlora_train_$name.log"; echo ALLDONE_B55 >> $LOG; exit 1; }
say "55: $name 학습 끝 — 어댑터 GGUF 변환(CPU)"
CUDA_VISIBLE_DEVICES="" taskset -c 96-111 $PY /root/llama.cpp/convert_lora_to_gguf.py --base $E4B --outtype f16 --outfile /root/work/${name}_lora_f16.gguf /root/adapters/$name > /root/convert_$name.log 2>&1 && say "55: $name 변환 끝 /root/work/${name}_lora_f16.gguf" || say "55: $name 변환 실패"
waitgpu
CONF=1 taskset -c 0-31 $PY qlora_eval2.py $E4B /root/adapters/$name $name $SETS > /root/qlora_eval_$name.log 2>&1
say "55: $name 평가 끝: $(tail -n 1 /root/qlora_eval_$name.log | cut -c1-80)"
echo ALLDONE_B55 >> $LOG
