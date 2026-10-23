#!/bin/bash
# 오라클 ARM(dr-a2) 모델 시험 대기열 2 (2026-10-07) — 대기열 1(Frog · E2B Q8 · 12B · bge-m3)이 끝나 CPU 가 비었다. 이어서:
#  ①gemma-4-E4B QAT Q4_0(서버 A GPU 시험의 기반 — ARM 은 Q4_0 을 특히 빨리 읽는다는 가설) ②gemma-4-E2B QAT Q4_0 ③kanana-2-3b Q8 ④EXAONE-4.0-1.2B Q8.
#  한 모델씩, 같은 합성 프롬프트(서버 안에서 생성) · 질문당 지연 · 메모리. 파일 이름은 허깅페이스 API 로 찾는다.
B=$HOME/bench; R=$B/results; M=$B/models; mkdir -p $R $M
say() { echo "[$(date -u +%H:%M:%S)] $*" >> $R/progress.log; }
cd $B
findf() {  # findf <repo> <정규식> → 파일 이름
  curl -s -m 30 "https://huggingface.co/api/models/$1" | python3 -c "import sys,json,re; d=json.load(sys.stdin); print(next((s['rfilename'] for s in d['siblings'] if re.search(sys.argv[1], s['rfilename']) and 'mmproj' not in s['rfilename']), ''))" "$2"
}
get() {  # get <repo> <파일> <저장 이름>
  [ -f $M/$3 ] && [ "$(stat -c %s $M/$3)" -gt 100000000 ] && return 0
  say "받기 $1/$2"
  curl -L -s -C - -o $M/$3 "https://huggingface.co/$1/resolve/main/$2" || say "받기 실패 $2"
  say "받음 $3 $(stat -c %s $M/$3 2>/dev/null) 바이트"
}
run() {  # run <이름> <repo> <파일 정규식> [bench 인자: 추가 cold]
  f=$(findf "$2" "$3")
  [ -z "$f" ] && { say "파일 못 찾음 $2 $3 — 건너뜀"; return; }
  get "$2" "$f" "$1.gguf"
  [ -f $M/$1.gguf ] && bash run_bench_a2.sh $1 $M/$1.gguf 1 ${4:-5}
}
say "=== 모델 시험 대기열 2 시작 ==="
run e4b_qat_q40 google/gemma-4-E4B-it-qat-q4_0-gguf 'E4B_q4_0-it\.gguf$'
run e2b_qat_q40 google/gemma-4-E2B-it-qat-q4_0-gguf 'E2B_q4_0-it\.gguf$'
run kanana2_3b_q8 mradermacher/kanana-2-3b-instruct-GGUF 'Q8_0\.gguf$'
run exaone40_12b_q8 LGAI-EXAONE/EXAONE-4.0-1.2B-GGUF 'Q8_0\.gguf$'
say "=== 모델 시험 대기열 2 끝 ==="
echo ALL_DONE_MODELS2 >> $R/progress.log
