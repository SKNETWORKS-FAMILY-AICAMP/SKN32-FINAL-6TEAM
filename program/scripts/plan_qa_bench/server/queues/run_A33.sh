#!/bin/bash
# 서버 A 대기열 33 (2026-10-07) — 오늘자 조사로 고른 검토자 후보를 받아 「짧은 확인 질문」으로 같은 입력(verify_inputs.json 1,677건)에 풀게 한다. 모델 하나씩: 받기 → 시험 → 지우기(디스크 한도 약 80GB 중 여유 약 12GB).
#  사용자 지시(2026-10-07): 「포그나노는 그냥 써 본 것 — 오지목을 가장 잘 찾는 소형 · 대형 모델을 오늘 기준으로 찾아 받아서 시험」. 후보 근거는 조사 담당 보고(JevBench v1.6.1 · 모델 카드 · 기권 판정 연구).
#  각 모델의 HF 수정판 해시(sha)를 revisions.tsv 에 남긴다(모델 수정판 기록 규칙).
LOG=/workspace/heavy/run_A33.log
say() { echo "[$(date -u +%H:%M)] $*" >> $LOG; }
cd /workspace/heavy
while ! grep -q ALLDONE_A32 /workspace/heavy/run_A32.log 2>/dev/null; do sleep 15; done
export LLAMA_SERVER=/workspace/deciders/bin/llama-server CORES=0-5
HF=https://huggingface.co
M=/workspace/cand; mkdir -p $M
findf() { curl -s -m 30 "$HF/api/models/$1" | python3 -c "import sys,json,re; d=json.load(sys.stdin); print(next((s['rfilename'] for s in d['siblings'] if re.search(sys.argv[1], s['rfilename'])), ''))" "$2"; }
shaof() { curl -s -m 30 "$HF/api/models/$1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('sha',''), d.get('lastModified',''))"; }
cand() {  # cand <이름> <repo> <파일 정규식>
  name=$1; repo=$2; re=$3
  f=$(findf "$repo" "$re")
  [ -z "$f" ] && { say "33: $name 파일 못 찾음 ($repo $re)"; return; }
  echo -e "$name\t$repo\t$f\t$(shaof $repo)\t$(date -u +%F)" >> revisions.tsv
  say "33: $name 받기 $repo/$f"
  curl -L -s -o $M/$name.gguf "$HF/$repo/resolve/main/$f"
  sz=$(stat -c %s $M/$name.gguf 2>/dev/null); say "33: $name 받음 $sz 바이트"
  [ "${sz:-0}" -lt 100000000 ] && { say "33: $name 받기 실패(작음)"; rm -f $M/$name.gguf; return; }
  GGUF=$M/$name.gguf TAG=$name PORT=$((8300 + RANDOM % 90)) python3 verify_llama.py > verify_$name.out 2>&1
  say "33: $name 끝: $(tail -n 1 verify_$name.out | cut -c1-60) / 결과 $(wc -l < verify_$name.jsonl 2>/dev/null) 줄"
  rm -f $M/$name.gguf
}
cand qwen35_4b unsloth/Qwen3.5-4B-GGUF 'Qwen3.5-4B-Q4_K_M\.gguf$'
cand kanana2_3b mradermacher/kanana-2-3b-instruct-GGUF 'Q8_0\.gguf$'
cand granite42_3b ibm-granite/granite-4.2-3b-GGUF 'granite-4.2-3b-Q4_K_M\.gguf$'
cand qwen35_9b unsloth/Qwen3.5-9B-GGUF 'Qwen3.5-9B-Q4_K_M\.gguf$'
cand granite42_8b ibm-granite/granite-4.2-8b-GGUF 'granite-4.2-8b-Q4_K_M\.gguf$'
cand lfm25_26b LiquidAI/LFM2.5-2.6B-GGUF 'LFM2.5-2.6B-Q4_K_M\.gguf$'
cand qwen35_2b unsloth/Qwen3.5-2B-GGUF 'Qwen3.5-2B-Q4_K_M\.gguf$'
cand torchcast12b mradermacher/torchcast-decision-12b-GGUF 'Q4_K_M\.gguf$'
cand winnow12b Piotr1215/Winnow-12B-GGUF 'Q4_K_M\.gguf$'
# 이미 받아 둔 Winnow-E4B(Q8) 는 지우지 않고 그대로 시험
say "33: winnow_e4b(로컬) 시작"
GGUF=/workspace/deciders/winnow_e4b/gguf/Winnow-E4B-Q8_0.gguf TAG=winnow_e4b PORT=8395 python3 verify_llama.py > verify_winnow_e4b.out 2>&1
say "33: winnow_e4b 끝: $(tail -n 1 verify_winnow_e4b.out | cut -c1-60)"
echo ALLDONE_A33 >> $LOG
