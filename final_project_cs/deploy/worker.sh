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
stopping=0
sleep_pid=
round_status=0

request_stop() {
  stopping=1
  # 반복 신호가 자식 회수를 중단하지 않게 한다. 진행 중인 Python에는 전달하지 않는다.
  trap '' TERM INT
  if [ -n "$sleep_pid" ]; then
    # 이미 끝난 sleep과의 경합은 정상이다. 다른 자식이나 프로세스 그룹은 건드리지 않는다.
    kill -TERM "$sleep_pid" 2>/dev/null || :
  fi
}
trap request_stop TERM INT

log_failure() {
  printf '{"job":"%s","exit":%s,"at":"%s"}\n' "$1" "$2" "$(date -Iseconds)" >&2
}

run() {
  [ "$stopping" -eq 0 ] || return 125
  name="$1"; shift
  # 전경 명령은 자연 종료까지 기다린다. 셸 트랩은 그 뒤 후속 작업을 막는다.
  python "$@"
  job_status=$?
  if [ "$job_status" -ne 0 ]; then
    round_status=$job_status
    log_failure "$name" "$job_status"
  fi
  return "$job_status"
}

while [ "$stopping" -eq 0 ]; do
  round_status=0
  run diagnostics -m scripts.replay_operations_diagnostics --prune
  run sweepers -m scripts.run_sweepers --once
  run outbox -m scripts.run_outbox_worker --once --drain
  [ "$stopping" -eq 0 ] || break

  today="$(date +%F)"
  now="$(date +%H%M)"
  if [ "$now" -ge 0910 ] && [ "$(cat "$DAILY_MARK" 2>/dev/null)" != "$today" ]; then
    if run daily_feedback -m scripts.run_daily_feedback --date "$today"; then
      if printf '%s\n' "$today" > "$DAILY_MARK"; then
        :
      else
        round_status=$?
        log_failure daily_feedback_mark "$round_status"
      fi
    fi
  fi
  [ "$stopping" -eq 0 ] || break

  # wait는 트랩으로 중단될 수 있다. 대기만 취소하고 직접 만든 자식은 반드시 회수한다.
  sleep 60 &
  sleep_pid=$!
  if [ "$stopping" -ne 0 ]; then
    kill -TERM "$sleep_pid" 2>/dev/null || :
  fi
  wait "$sleep_pid"
  sleep_status=$?
  if [ "$stopping" -ne 0 ]; then
    # 첫 wait가 신호로 중단됐다면 다시 기다린다. 이미 회수됐으면 반환값은 무시한다.
    wait "$sleep_pid" 2>/dev/null || :
  elif [ "$sleep_status" -ne 0 ]; then
    log_failure idle_wait "$sleep_status"
    exit "$sleep_status"
  fi
  sleep_pid=
done
exit "$round_status"
