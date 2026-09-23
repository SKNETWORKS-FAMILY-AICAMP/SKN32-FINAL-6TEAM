"""상시 작업 한 회차를 돌리고 **흔적을 남긴다.**

    python -m scripts.ops.tick sweepers --show    부를 명령만 보여 준다(아무것도 안 돈다)
    python -m scripts.ops.tick sweepers           한 회차 돌린다
    python -m scripts.ops.tick outbox

★왜 스케줄러가 `scripts.run_sweepers` 를 직접 부르지 않고 이걸 거치나.

    (1) **죽었는지 알려면 마지막 시도가 남아야 한다.** 지금까지 "안 돌고 있었다"
        를 아무도 몰랐던 이유가 이것이다 — 콘솔에 찍히고 창이 닫히면 끝이었다.
        여기서는 성공이든 실패든 `var/ops/heartbeat/<작업>.json` 에 남는다.
    (2) **창이 안 뜬다.** 자식은 `CREATE_NO_WINDOW` 로 띄운다. 2026-09-14~21 에
        걸려 있던 작업이 5분마다 검은 cmd 창을 띄워 사용자 화면을 끊었다
        (`wiki/records/manuals/운영_멈춘Case_되잡기.md` §「폐기됨」 2번).
    (3) **stdout 계약을 안 깬다.** 원래 스크립트의 JSON 한 줄은 그대로 로그
        파일에 남기고, 이 스크립트는 자식의 exit code 를 **그대로 돌려준다** —
        스케줄러의 「마지막 결과」가 실패를 본다.

★이 스크립트는 **실패를 삼키지 않는다.** 자식이 1 을 내면 여기도 1 을 낸다
  (`CLAUDE.md` §3 「조용한 스킵을 만들지 않는다」).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ops.guard import (Skipped, note_result, only_one, prune_logs,  # noqa: E402
                              send_alert)
from scripts.ops.jobs import HEARTBEAT_DIR, JOBS, LOG_DIR, Job  # noqa: E402

#: 콘솔 창을 만들지 않는다. Windows 전용 플래그라 다른 OS 에서는 0 을 쓴다.
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

#: 한 회차가 이보다 오래 걸리면 죽인다. 되잡기 한 회차는 초 단위로 끝난다 —
#: 10분을 넘겼다면 매달린 것이고, 매달린 채로 두면 다음 회차와 겹친다.
DEFAULT_TIMEOUT_SECONDS = 600


def say(text: str, *, err: bool = False) -> None:
    """사람이 직접 불렀을 때만 찍는다.

    ★`[2026-09-22]` **`pythonw` 로 창 없이 돌면 `sys.stdout` 이 `None` 이다.** 그대로 `write` 를
      부르면 `AttributeError` 로 죽고, 스케줄러의 「마지막 결과」가 **1** 이 된다 — 흔적과 로그에는
      이미 `exit=0` 이 적힌 뒤라 「로그는 성공인데 스케줄러는 실패」라는 엇갈린 상태가 된다.
      실제로 등록 직후 그렇게 났다.
    """
    stream = sys.stderr if err else sys.stdout
    if stream is None:                      # pythonw — 찍을 곳이 없다. 기록은 이미 파일에 남았다
        return
    try:
        stream.write(text if text.endswith(chr(10)) else text + chr(10))
    except (OSError, ValueError):           # 닫힌 파이프도 작업 결과를 덮지 않는다
        pass


def command_for(job: Job, *, python: str | None = None) -> list[str]:
    """이 작업이 실제로 돌릴 명령. 등록 미리보기도 이 함수를 쓴다."""
    if job.kind == "service":
        raise SystemExit(f"★{job.name} 은 서비스다 — tick 이 다루지 않는다.")
    argv = [python or sys.executable, *job.argv]
    if job.name == "daily_feedback":
        # ★`--date` 는 필수 인자다. 스케줄러에 날짜를 박아 두면 그날만 맞는다.
        argv += ["--date", datetime.now().date().isoformat()]
    return argv


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _tail(text: str, limit: int = 2000) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else "…(앞을 잘랐다)…" + text[-limit:]


def write_heartbeat(job: Job, record: dict) -> Path:
    HEARTBEAT_DIR.mkdir(parents=True, exist_ok=True)
    path = HEARTBEAT_DIR / f"{job.name}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def append_log(job: Job, record: dict) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{job.name}-{datetime.now().strftime('%Y%m%d')}.log"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{record['finished_at']}\texit={record['exit_code']}\t"
                 f"{record['duration_seconds']:.1f}s\t{record['stdout_tail'] or '(stdout 없음)'}\n")
        if record["stderr_tail"]:
            for line in record["stderr_tail"].splitlines():
                fh.write(f"{record['finished_at']}\tstderr\t{line}\n")
    return path


def run(job: Job, *, timeout: int) -> int:
    """한 회차. ★`[2026-09-22]` 겹치면 건너뛰고, 연속 실패면 알리고, 오래된 로그를 지운다."""
    try:
        with only_one(HEARTBEAT_DIR / f"{job.name}.lock"):
            return _run_once(job, timeout=timeout)
    except Skipped as exc:
        # ★건너뜀을 **성공으로 적지 않는다.** 흔적에 남겨 점검이 「돌았다」로 읽지 않게 한다.
        record = {"job": job.name, "command": " ".join(command_for(job)), "state": "skipped",
                  "started_at": _now(), "finished_at": _now(), "duration_seconds": 0.0,
                  "exit_code": 0, "stdout_tail": f"건너뜀 — {exc}", "stderr_tail": ""}
        write_heartbeat(job, record)
        append_log(job, record)
        say(f"건너뜀 — {exc}")
        return 0


def _run_once(job: Job, *, timeout: int) -> int:
    argv = command_for(job)
    started = datetime.now()
    try:
        proc = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout,
                              creationflags=CREATE_NO_WINDOW)
        exit_code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        # ★타임아웃을 성공으로 추정하지 않는다. 별도 코드로 남긴다(`CLAUDE.md` §0.2 와 같은 태도).
        exit_code = 124
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        err = f"★{timeout}초 안에 안 끝나 죽였다. 매달린 회차다."
    finished = datetime.now()

    record = {
        "job": job.name,
        "command": " ".join(argv),
        "started_at": started.astimezone().isoformat(timespec="seconds"),
        "finished_at": finished.astimezone().isoformat(timespec="seconds"),
        "duration_seconds": (finished - started).total_seconds(),
        "exit_code": exit_code,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
    }
    write_heartbeat(job, record)
    append_log(job, record)
    removed = prune_logs(LOG_DIR)
    if removed:
        say(f"오래된 로그 {len(removed)}개 지움: {', '.join(removed[:3])}"
            + (" …" if len(removed) > 3 else ""))
    # ★연속 실패면 운영자에게 알린다 — 한 번만. 스케줄러의 「마지막 결과」를 사람이 봐야만
    #   아는 상태를 끝낸다(바깥함 일꾼이 4시간 넘게 안 돌고도 아무 데도 안 떴다).
    verdict = note_result(HEARTBEAT_DIR, job.name, exit_code=exit_code,
                          detail=_tail(err or out, 300))
    if verdict["should_alert"]:
        say(f"운영 알림({verdict['kind']}, 연속 {verdict['streak']}회): "
            + send_alert(job.name, verdict["kind"], streak=verdict["streak"],
                         detail=_tail(err or out, 300)))
    # ★사람이 직접 불렀을 때를 위해 그대로 흘려 준다. 스케줄러(pythonw)가 부르면 아무 데도 안 간다 —
    #   그래서 위에서 파일에 먼저 남겼다.
    if out:
        say(out)
    if err:
        say(err, err=True)
    return exit_code


def run_resident(job: Job) -> int:
    """상주 프로세스를 이 프로세스에 매달아 돌린다(앱).

    ★들고 나는 것을 남긴다 — 앱이 **언제 죽었는지**가 지금은 아무 데도 안 남는다.
      시작할 때 `state=running`, 끝날 때 `state=exited` + exit code 를 적는다.
    ★그래도 **다시 띄워 주지는 않는다.** 작업 스케줄러에는 그 기능이 없다
      (`wiki/operations/move-to-server.md` 길 ① 「이 길이 못 고치는 것」).
    """
    argv = command_for(job)
    started = datetime.now()
    write_heartbeat(job, {"job": job.name, "command": " ".join(argv), "state": "running",
                          "started_at": started.astimezone().isoformat(timespec="seconds"),
                          "finished_at": None, "duration_seconds": 0.0,
                          "exit_code": None, "stdout_tail": "", "stderr_tail": ""})
    proc = subprocess.run(argv, cwd=REPO_ROOT, creationflags=CREATE_NO_WINDOW)
    finished = datetime.now()
    record = {"job": job.name, "command": " ".join(argv), "state": "exited",
              "started_at": started.astimezone().isoformat(timespec="seconds"),
              "finished_at": finished.astimezone().isoformat(timespec="seconds"),
              "duration_seconds": (finished - started).total_seconds(),
              "exit_code": proc.returncode,
              "stdout_tail": "★상주 프로세스의 출력은 여기로 안 온다 — 콘솔 없이 돈다",
              "stderr_tail": ""}
    write_heartbeat(job, record)
    append_log(job, record)
    return proc.returncode


def main() -> int:
    # ★윈도 콘솔 기본 인코딩(cp949)으로는 이 표의 글자가 안 나간다 — 출력만 UTF-8 로 돌린다.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="상시 작업 한 회차를 돌리고 흔적을 남긴다")
    parser.add_argument("job", choices=[name for name, j in JOBS.items() if j.kind != "service"])
    parser.add_argument("--show", action="store_true", help="부를 명령만 보여 주고 끝낸다")
    parser.add_argument("--resident", action="store_true",
                        help="상주 작업(앱)을 이 프로세스에 매달아 돌린다")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    job = JOBS[args.job]
    if args.show:
        say(" ".join(command_for(job)))
        print(f"  작업     : {job.title}")
        print(f"  주기     : {job.every_minutes and f'{job.every_minutes}분마다' or job.daily_at or '상주'}")
        print(f"  기록     : {HEARTBEAT_DIR / (job.name + '.json')}")
        print(f"  로그     : {LOG_DIR / (job.name + '-<날짜>.log')}")
        print("★아무것도 돌리지 않았다.")
        return 0
    if job.kind == "resident":
        if not args.resident:
            raise SystemExit(f"★{job.name} 은 상주 프로세스다 — 한 회차씩 부르지 않는다. "
                             f"돌리려면 --resident 를 준다. 등록은 "
                             f"`python -m scripts.ops.install_services --only {job.name}`.")
        return run_resident(job)
    if args.resident:
        raise SystemExit(f"★{job.name} 은 한 회차짜리다 — --resident 를 주지 않는다.")
    return run(job, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
