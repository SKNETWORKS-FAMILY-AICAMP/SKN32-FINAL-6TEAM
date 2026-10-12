#!/bin/bash
# 서버 A 대기열 35 (2026-10-07) — 잡담+일정 섞임 시험(MX: 혼합 문장 2,007 + 요청만 있는 대조 2,007 = 4,014입력)에서 가르친 E4B 시드 1·2·3 과 oos1(서비스 기반 Q4_K_M)을 푼다.
#  이어서 대기열 33 에서 받기가 끊겨 못 잰 Winnow-12B(Q4_K_M)를 다시 받아 검토자 시험을 한다.
LOG=/workspace/heavy/run_A35.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5 LOGPROBS=1 PROMPTS=all_prompts_mx.json
Q4=/workspace/ollama/blobs/sha256-370c2879f17648d337b0ab4e208fdce348e24d1060064e93d7645daafd56d39c
for n in e4bt e4bs2 e4bs3 oos1; do
  say "35: MX $n"
  GGUF=$Q4 LORA=/workspace/tripilot/${n}_lora_f16.gguf TAG=lp_mx_q4km_$n PORT=8310 python3 d_test_llama_lp.py > lp_mx_$n.out 2>&1
  say "35: MX $n 끝: $(tail -n 1 lp_mx_$n.out | cut -c1-60)"
done
unset LOGPROBS PROMPTS
say "35: Winnow-12B 다시 받기"
M=/workspace/cand; mkdir -p $M
HF=https://huggingface.co
f=$(curl -s -m 30 "$HF/api/models/Piotr1215/Winnow-12B-GGUF" | python3 -c "import sys,json,re; d=json.load(sys.stdin); print(next((s['rfilename'] for s in d['siblings'] if re.search('Q4_K_M\\.gguf$', s['rfilename'])), ''))")
curl -L -s -C - --retry 5 -o $M/winnow12b.gguf "$HF/Piotr1215/Winnow-12B-GGUF/resolve/main/$f"
sz=$(stat -c %s $M/winnow12b.gguf); say "35: Winnow-12B 받음 $sz 바이트(기대 7381382912)"
if [ "$sz" -ge 7381000000 ]; then
  GGUF=$M/winnow12b.gguf TAG=winnow12b PORT=8311 python3 verify_llama.py > verify_winnow12b2.out 2>&1
  say "35: Winnow-12B 끝: $(tail -n 1 verify_winnow12b2.out | cut -c1-60)"
fi
rm -f $M/winnow12b.gguf
echo ALLDONE_A35 >> $LOG
