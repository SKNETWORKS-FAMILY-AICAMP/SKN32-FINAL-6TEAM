#!/bin/bash
# 새 서버 대기열 16 — Decider-12B 8비트에서 선택지 순서를 섞어 5번 더(시드 2~6) mix8~mix12 를 푼다 — 순서 민감도를 신뢰구간과 함께 재고, 섞은 답을 모아 고르는 방식의 재료. B15 가 끝나면 이어서.
cd /root
export HF_HUB_DISABLE_XET=1
LOG=/root/run_B16.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
while ! grep -q ALLDONE_B15 /root/run_B15.log; do sleep 30; done
for k in 2 3 4 5 6; do
  say "Decider-12B 8비트 선택지 섞기 시드 $k (mix8~12)"
  SHUF=$k Q8=1 MODEL=Mapika/decider-12b TAG=decider12bq8sh$k SETS=mix8,mix9,mix10,mix11,mix12 /root/venv_imajev/bin/python dec_lib_run_q.py > /root/d12q8_sh${k}.log 2>&1
  say "시드 $k exit=$?"
done
rm -rf /root/.cache/huggingface/hub/models--Mapika--decider-12b
say "SHUF_B_DONE"
echo ALLDONE_B16 >> $LOG
