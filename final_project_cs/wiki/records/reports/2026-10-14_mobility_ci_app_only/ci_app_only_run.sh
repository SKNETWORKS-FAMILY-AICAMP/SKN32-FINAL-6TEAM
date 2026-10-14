#!/usr/bin/env bash
# 앱 폴더(final_project_cs)만 꺼낸 임시 환경에서 이동 시험을 돌린다 — 이동 자료 · 저장소 맨 위 datasets/ 없음. CI 의 환경 변수 값(더미)을 그대로 쓴다.
# 사용: ci_app_only_run.sh <git ref> <결과 폴더>
set -u
REF=$1; OUT=$2
REPO=/c/Users/playdata2/Documents/wt_mobility_golden
TMP=$(mktemp -d /c/Users/playdata2/Documents/apponly_tmp.XXXX)
mkdir -p "$OUT"
(cd $REPO && git archive "$REF" final_project_cs final_project_sample) | tar -x -C "$TMP"
# 같은 패치(작업 사본의 미커밋 변경)가 있으면 얹는다
if [ -n "${PATCH:-}" ]; then (cd "$TMP" && git apply --ignore-whitespace "$PATCH") || { echo "patch fail"; exit 3; }; fi
cd "$TMP/final_project_cs"
while IFS= read -r line; do
  k=${line%%:*}; v=${line#*: }; v=${v%%  #*}; v=$(echo "$v" | sed 's/^ *//; s/ *$//')
  case "$k" in PYTHONPATH) export PYTHONPATH="$TMP/final_project_sample:$TMP/final_project_cs";; *) export "$k=$v";; esac
done < /c/Users/playdata2/Documents/final_workspace/.tmp/mobility_claude_resume_20261012_201012/ci-env.txt
unset DATA_DIR ACOP_MOBILITY_DATA_DIR
C:/Users/playdata2/anaconda3/python.exe -X utf8 -m pytest -q -p no:cacheprovider tests/unit/travel/mobility -m "not live" \
  --junitxml "$OUT/apponly.xml" --basetemp "$OUT/pt" > "$OUT/apponly.log" 2>&1
echo "exit=$?"; tail -1 "$OUT/apponly.log"; grep -E "^(FAILED|ERROR)" "$OUT/apponly.log" | sed 's/ - .*//' | head -30
echo "tmp=$TMP"
