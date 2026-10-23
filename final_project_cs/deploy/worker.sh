#!/bin/sh
# 공개 배포 작업 실행기 — 원 스크립트를 직접 호출한다. 로컬 Windows tick/guard 경로와 다르다.
#   되잡기(멈춘 Case · 여행 감시 · 일정 안내)  회차 실행 뒤 60초 대기  (감시만 3분 주기는 작업 안의 문이 지킨다)
#   바깥함 일꾼(통지 배달)                       따로 도는 반복 · 배달 뒤 WORKER_DELIVERY_SLEEP(기본 10)초 대기
#   진단 기록 재전송·만료 연결 정리               회차 실행 뒤 60초 대기(회차별 건수 상한 적용)
#   일일 피드백 집계                             하루 한 번 서울 09:10 (`feedback_analytics.batch_time_utc: 00:10`)
#
# ★한 회차가 실패해도(exit 1) 다음 회차는 돈다 — 실패는 로그에 남고 다음 줄에서 또 시도한다. 조용히 삼키지 않는다: 종료 코드를 로그에 찍는다.
# ★일꾼은 **하나만** 띄운다(`docker compose up` 의 `tripilot-worker` 한 개) — 둘이면 통지가 두 번 나간다.
# ★`[2026-10-19]` 배달은 되잡기 회차와 따로 돈다 — 대안 계산이 몇 분 걸려도 이미 정한 위험 안내는 그동안 나간다.
#   ☆오라클 ARM 에서 10-18 손으로 넣어 돌린 「배달 독립 반복」을 종료 처리 v2 위에 다시 만들었다(오라클 판은 v2 종료 시험 13/14 실패).
#   배달 반복은 이 컨테이너에 하나뿐이다. 반복이 혼자 멈추면 다음 회차가 기록하고 다시 띄운다.
set -u

DAILY_MARK=/srv/var/ops/daily_feedback.last
DELIVERY_SLEEP=${WORKER_DELIVERY_SLEEP:-10}
stopping=0
signals=0
sleep_pid=
round_status=0
delivery_pid=
# 되잡기 작업이 자기 종료 코드를 남기는 파일(아래 run) — 일꾼마다 하나.
JOB_STATUS="${TMPDIR:-/tmp}/tripilot-worker-job.$$"

request_stop() {
  stopping=1
  signals=$((signals + 1))
  # 반복 신호가 자식 회수를 중단하지 않게 한다. 진행 중인 Python에는 전달하지 않는다.
  trap '' TERM INT
  if [ -n "$delivery_pid" ]; then
    # 배달 반복에도 멈추라고 알린다. 반복은 진행 중인 발송을 끝까지 기다린 뒤 끝난다.
    kill -TERM "$delivery_pid" 2>/dev/null || :
  fi
  if [ -n "$sleep_pid" ]; then
    # 이미 끝난 sleep과의 경합은 정상이다. 다른 자식이나 프로세스 그룹은 건드리지 않는다.
    kill -TERM "$sleep_pid" 2>/dev/null || :
  fi
}
trap request_stop TERM INT

log_failure() {
  printf '{"job":"%s","exit":%s,"at":"%s"}\n' "$1" "$2" "$(date -Iseconds)" >&2
}

# 비동기 자식을 끝까지 기다려 그 종료 코드를 돌려준다. 신호로 wait 가 깨졌으면(트랩이 돌았으면) 다시 기다린다.
# 자식이 이미 회수돼 다시 기다릴 것이 없으면(127) 앞에서 받은 코드를 쓴다.
wait_child() {
  seen=$signals
  wait "$1"
  child_status=$?
  while [ "$signals" != "$seen" ]; do
    seen=$signals
    wait "$1"
    again=$?
    [ "$again" -eq 127 ] || child_status=$again
  done
  return "$child_status"
}

run() {
  [ "$stopping" -eq 0 ] || return 125
  name="$1"; shift
  # 작업은 비동기로 띄우고 기다린다 — 전경 명령이면 셸이 작업이 끝날 때까지 트랩을 미뤄 배달 반복에 멈춤을 늦게 알린다.
  # 신호는 작업에 넘기지 않는다. 작업은 자연 종료까지 기다린다.
  # ★`[2026-10-23]` 종료 코드는 작업이 파일에 남긴다 — bash 는 wait 가 신호(멈춤)로 깨지는 바로 그때 끝난 자식의 코드를 잃는다
  #   (다시 wait 하면 -1 → return 255, 리눅스 bash 5.2 에서 약 8%). dash 는 잃지 않는다(같은 실험 0/3000). 파일이 없으면(작업이 그 전에 끊김) wait 의 코드를 쓴다.
  rm -f "$JOB_STATUS"
  { python "$@"; printf '%s\n' "$?" > "$JOB_STATUS"; } &
  wait_child "$!"
  job_status=$?
  if [ -s "$JOB_STATUS" ]; then
    job_status=$(cat "$JOB_STATUS")
  fi
  rm -f "$JOB_STATUS"
  if [ "$job_status" -ne 0 ]; then
    round_status=$job_status
    log_failure "$name" "$job_status"
  fi
  return "$job_status"
}

# 배달 반복의 멈춤 — 신호를 받을 때마다 대기 sleep 을 다시 끈다(부모가 1초마다 다시 알린다).
#   ☆막 띄운 sleep 에 보낸 첫 TERM 이 사라지는 경우가 있었다(Git Bash 시험 · exec 중 신호). 그래서 부모의 request_stop 과 달리
#   뒤 신호를 무시하지 않는다. 진행 중인 발송(Python)에는 어느 신호도 보내지 않는다.
stop_delivery() {
  stopping=1
  signals=$((signals + 1))
  if [ -n "$sleep_pid" ]; then
    kill -TERM "$sleep_pid" 2>/dev/null || :
  fi
}

# 배달 반복 — 서브셸 안에서 돈다. 위 변수는 서브셸의 사본이다.
# ★`stopping` 은 되돌리지 않는다 — 서브셸이 뜨자마자 받은 멈춤 요청(부모의 트랩이 서브셸에서 돈 경우)을 지우지 않게.
delivery_loop() {
  sleep_pid=
  trap stop_delivery TERM INT
  while [ "$stopping" -eq 0 ]; do
    python -m scripts.run_outbox_worker --once --drain &
    wait_child "$!"
    delivery_status=$?
    if [ "$delivery_status" -ne 0 ]; then
      log_failure outbox "$delivery_status"
    fi
    [ "$stopping" -eq 0 ] || break
    sleep "$DELIVERY_SLEEP" &
    sleep_pid=$!
    if [ "$stopping" -ne 0 ]; then
      kill -TERM "$sleep_pid" 2>/dev/null || :
    fi
    # 멈춤으로 wait 가 깨져도 sleep 이 실제로 끝나 회수될 때까지 다시 기다린다(신호마다 sleep 을 다시 끈다).
    wait_child "$sleep_pid"
    delivery_sleep_status=$?
    sleep_pid=
    if [ "$stopping" -eq 0 ] && [ "$delivery_sleep_status" -ne 0 ]; then
      # 대기가 깨지면 반복을 끝낸다(쉬지 않고 발송을 띄우지 않게). 다음 회차가 기록하고 다시 띄운다.
      log_failure delivery_wait "$delivery_sleep_status"
      exit "$delivery_sleep_status"
    fi
  done
  exit 0
}

# 배달 반복이 없거나 혼자 멈췄으면 기록하고 다시 띄운다. 멈춘 뒤에는 띄우지 않는다.
ensure_delivery() {
  [ "$stopping" -eq 0 ] || return 0
  if [ -n "$delivery_pid" ]; then
    kill -0 "$delivery_pid" 2>/dev/null && return 0
    wait_child "$delivery_pid"
    log_failure delivery_loop "$?"
    [ "$stopping" -eq 0 ] || return 0
  fi
  # 새 반복이 옛 번호를 물려받지 않게 비우고 띄운다(서브셸의 request_stop 이 끝난 번호에 신호를 보내지 않게).
  delivery_pid=
  delivery_loop &
  delivery_pid=$!
}

while [ "$stopping" -eq 0 ]; do
  round_status=0
  ensure_delivery
  run diagnostics -m scripts.replay_operations_diagnostics --prune
  run sweepers -m scripts.run_sweepers --once
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
    round_status=$sleep_status
    break
  fi
  sleep_pid=
done
# 배달 반복을 멈추고 진행 중인 발송이 끝날 때까지 회수한다. 종료 코드는 되잡기 회차의 것이다.
# ☆갓 뜬 서브셸이 자기 트랩을 걸기 전에 받은 신호는 셸에 따라 처리되지 않고 사라질 수 있다 — 끝날 때까지 1초마다 다시 알린다.
#   반복은 다시 받은 신호로 대기 sleep 만 다시 끈다 — 진행 중인 발송은 끊기지 않는다.
if [ -n "$delivery_pid" ]; then
  while kill -0 "$delivery_pid" 2>/dev/null; do
    kill -TERM "$delivery_pid" 2>/dev/null || :
    sleep 1 &
    wait_child "$!" || :
  done
  wait_child "$delivery_pid" || :
fi
exit "$round_status"
