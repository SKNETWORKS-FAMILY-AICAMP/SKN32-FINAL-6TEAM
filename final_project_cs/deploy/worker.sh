#!/bin/sh
# 공개 배포 작업 실행기 — 원 스크립트를 직접 호출한다. 로컬 Windows tick/guard 경로와 다르다.
#   되잡기(멈춘 Case · 여행 감시 · 일정 안내)  회차 실행 뒤 60초 대기  (감시만 3분 주기는 작업 안의 문이 지킨다)
#   바깥함 일꾼(통지 배달)                       회차 실행 뒤 60초 대기
#   진단 기록 재전송·만료 연결 정리               회차 실행 뒤 60초 대기(회차별 건수 상한 적용)
#   일일 피드백 집계                             하루 한 번 서울 09:10 (`feedback_analytics.batch_time_utc: 00:10`)
#
# ★한 회차가 실패해도(exit 1) 다음 회차는 돈다 — 실패는 로그에 남고 다음 줄에서 또 시도한다. 조용히 삼키지 않는다: 종료 코드를 로그에 찍는다.
# ★일꾼은 **하나만** 띄운다(`docker compose up` 의 `tripilot-worker` 한 개) — 둘이면 통지가 두 번 나간다.
set -u

DAILY_MARK=/srv/var/ops/daily_feedback.last

run() {
  name="$1"; shift
  python "$@" || echo "{\"job\":\"$name\",\"exit\":$?,\"at\":\"$(date -Iseconds)\"}" >&2
}

while true; do
  run diagnostics -m scripts.replay_operations_diagnostics --prune
  run sweepers -m scripts.run_sweepers --once
  run outbox -m scripts.run_outbox_worker --once --drain

  today="$(date +%F)"
  now="$(date +%H%M)"
  if [ "$now" -ge 0910 ] && [ "$(cat "$DAILY_MARK" 2>/dev/null)" != "$today" ]; then
    if python -m scripts.run_daily_feedback --date "$today"; then
      echo "$today" > "$DAILY_MARK"
    else
      echo "{\"job\":\"daily_feedback\",\"exit\":$?,\"at\":\"$(date -Iseconds)\"}" >&2
    fi
  fi
  sleep 60
done
