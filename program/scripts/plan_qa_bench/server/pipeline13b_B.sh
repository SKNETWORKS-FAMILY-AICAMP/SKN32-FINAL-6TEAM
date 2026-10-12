#!/bin/bash
# 새 서버 대기열 13 — 디스크가 가득 차 실패했던 Decider-12B 8비트 mix11 을 대기열 B12 가 끝난 뒤 다시 한다.
cd /root
export HF_HUB_DISABLE_XET=1
LOG=/root/run_B13.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
while ! grep -q ALLDONE_B12 /root/run_B12.log; do sleep 30; done
rm -rf /root/.cache/huggingface/hub/models--Mapika--decider-12b
say "Decider-12B 8비트 mix11 재시도(디스크 확보 뒤)"
Q8=1 MODEL=Mapika/decider-12b TAG=decider12bq8 SETS=mix11 /root/venv_imajev/bin/python dec_lib_run_q.py > /root/d12q8_m11_retry.log 2>&1
say "8비트 exit=$?"
rm -rf /root/.cache/huggingface/hub/models--Mapika--decider-12b
echo ALLDONE_B13 >> $LOG
