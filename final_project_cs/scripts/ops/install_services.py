"""상시 실행을 **이 기계에 걸어 둔다.** 기본은 보여만 준다.

    python -m scripts.ops.install_services                     무엇을 걸지 보여만 준다(기본)
    python -m scripts.ops.install_services --status            지금 걸려 있나
    python -m scripts.ops.install_services --apply             실제로 건다
    python -m scripts.ops.install_services --apply --only sweepers,outbox
    python -m scripts.ops.install_services --remove --only app  뗀다

    # DB 는 **공유 클러스터**라 따로, 그리고 확인 플래그가 하나 더 필요하다
    python -m scripts.ops.install_services --only postgres --pgdata "<데이터디렉터리>"
    python -m scripts.ops.install_services --apply --only postgres \\
        --pgdata "<데이터디렉터리>" --yes-shared-cluster        # ★관리자 권한 필요

★**이 기계에 남는 설정이다.** 세션이 끝나도 계속 돈다. 그래서 두 가지를 지킨다 —
  (1) 기본은 미리보기이고 `--apply` 를 줘야 바뀐다 (2) 무엇이 바뀌는지와 **떼는 법**을
  먼저 찍는다. 2026-09-14 에 묻지 않고 등록한 작업이 5분마다 검은 창을 띄워
  일주일 뒤 지워야 했다(`wiki/records/manuals/운영_멈춘Case_되잡기.md` §「폐기됨」).

★**창은 안 뜬다.** 작업이 부르는 것은 `pythonw.exe` 이고, 그 자식도
  `CREATE_NO_WINDOW` 로 뜬다(`scripts/ops/tick.py`).

★이 기계에 있는 것은 `schtasks` 와 `sc` 뿐이다 `[실측 2026-09-22]` —
  `nssm`·`winsw`·`docker`·`systemctl`·`cron` 은 없다. 그래서 여기서 다루는 길은
  **Windows 작업 스케줄러**와 **`pg_ctl register`** 둘뿐이다. 없는 것에 대고
  설정 파일을 미리 써 두지 않는다.
"""
from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ops.jobs import JOBS, Job, schedule_text, select  # noqa: E402

TICK_PY = REPO_ROOT / "scripts" / "ops" / "tick.py"

#: 로컬 PostgreSQL 이 듣는 포트. `postgresql.conf` 에 `port` 가 없어서
#: `-o "-p …"` 를 빠뜨리면 5432 로 뜬다(`wiki/operations/local-setup.md`).
DEFAULT_PG_PORT = 5433


# ── 도구 찾기 ────────────────────────────────────────────────────────

def pythonw() -> str:
    """창 없는 파이썬. 없으면 `python.exe` 로 떨어지되 **그 사실을 말한다.**"""
    candidate = Path(sys.executable).with_name("pythonw.exe")
    if candidate.is_file():
        return str(candidate)
    print("★pythonw.exe 를 못 찾았다 — python.exe 로 건다. **검은 창이 뜬다.**", file=sys.stderr)
    return sys.executable


def find_pg_ctl(explicit: str | None) -> str | None:
    """`pg_ctl.exe` 의 자리. 못 찾으면 None — 미리보기는 그래도 돈다."""
    if explicit:
        return explicit if Path(explicit).is_file() else None
    found = shutil.which("pg_ctl")
    if found:
        return found
    # ★계정 이름을 소스에 적지 않는다. 환경변수로만 조립한다.
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    guess = Path(home) / "anaconda3" / "envs" / "pgv" / "Library" / "bin" / "pg_ctl.exe"
    return str(guess) if guess.is_file() else None


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — 관리자인지 못 알아낸 것과 아닌 것은 다르다
        return False


# ── 걸 명령 만들기 ──────────────────────────────────────────────────

def task_target(job: Job) -> str:
    """작업 스케줄러가 실행할 문자열.

    ★`cmd /c cd /d …` 를 **쓰지 않는다.** 그 형태가 검은 창을 띄웠다. 대신
      `tick.py` 를 **절대 경로**로 부른다 — tick 이 스스로 저장소 루트를
      `sys.path` 와 자식의 cwd 로 잡으므로 시작 디렉터리가 필요 없다.
    """
    tail = " --resident" if job.kind == "resident" else ""
    return f'"{pythonw()}" "{TICK_PY}" {job.name}{tail}'


def create_argv(job: Job) -> list[str]:
    argv = ["schtasks", "/Create", "/TN", job.task_name, "/TR", task_target(job), "/F"]
    if job.kind == "resident":
        argv += ["/SC", "ONLOGON"]
    elif job.daily_at:
        argv += ["/SC", "DAILY", "/ST", job.daily_at]
    else:
        argv += ["/SC", "MINUTE", "/MO", str(job.every_minutes)]
    return argv


def delete_argv(job: Job) -> list[str]:
    return ["schtasks", "/Delete", "/TN", job.task_name, "/F"]


def pg_register_argv(pg_ctl: str, pgdata: str, port: int, name: str) -> list[str]:
    # ★`-S auto` = 기계가 켜지면 자동. ★등록만 하고 **시작하지 않는다** — 지금 도는
    #   postmaster 가 같은 데이터 디렉터리를 쥐고 있어서 지금 시작하면 실패한다.
    #   다음 재부팅에 서비스로 뜬다.
    return [pg_ctl, "register", "-N", name, "-D", pgdata, "-S", "auto",
            "-o", f"-p {port}"]


def pg_unregister_argv(pg_ctl: str, name: str) -> list[str]:
    return [pg_ctl, "unregister", "-N", name]


def shown(argv: list[str]) -> str:
    """미리보기용 문자열. **그대로 붙여 넣어 돌릴 수 있게** 따옴표를 맞춘다.

    ★`/TR` 값은 그 자체가 따옴표를 품는다 — 바깥을 홑따옴표로 싼다(PowerShell 기준).
      이걸 안 맞추면 미리보기와 실제로 도는 것이 달라진다.
    """
    parts = []
    for item in argv:
        if '"' in item:
            parts.append(f"'{item}'")
        elif " " in item:
            parts.append(f'"{item}"')
        else:
            parts.append(item)
    return " ".join(parts)


# ── 실행 ────────────────────────────────────────────────────────────

def _run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def preview(job: Job, *, pg_ctl: str | None, pgdata: str | None, port: int) -> None:
    print(f"[{job.name}] {job.title}")
    print(f"    주기      : {schedule_text(job)}")
    if job.kind == "service":
        print(f"    등록 방법 : Windows **서비스** {job.task_name!r} (pg_ctl register)")
        if not pg_ctl:
            print("    ★pg_ctl.exe 를 못 찾았다 — `--pgctl <경로>` 로 준다")
        if not pgdata:
            print("    ★데이터 디렉터리를 안 줬다 — `--pgdata <경로>` 또는 환경변수 ACOP_PGDATA.")
            print("      값은 `wiki/operations/local-setup.md` 가 갖고 있다(여기 적지 않는다)")
        if pg_ctl and pgdata:
            print(f"    실행할 것 : {shown(pg_register_argv(pg_ctl, pgdata, port, job.task_name))}")
        print("    바뀌는 것 : 기계가 켜지면 DB 가 **자동으로** 뜬다. 콘솔·세션과 수명이 끊긴다.")
        print("              ★지금 도는 것은 **안 건드린다** — 등록만 하고 시작하지 않는다.")
        print("              ★효력은 **다음 재부팅**부터다. 지금 바꾸려면 사람이 직접")
        print("                도는 postmaster 를 정상 종료한 뒤 서비스를 시작한다.")
        print(f"    되돌리기  : python -m scripts.ops.install_services --remove --only {job.name}")
        print(f"              (= {shown(pg_unregister_argv(pg_ctl or 'pg_ctl', job.task_name))})")
        print("    권한      : ★**관리자 필요**")
        print("    ★★이 클러스터는 triPilot 만의 것이 아니다 — 옆 프로젝트 DB 가 같은")
        print("        데이터 디렉터리에 있다. 등록하면 그쪽 수명도 함께 바뀐다.")
        print("        그래서 `--yes-shared-cluster` 를 따로 받는다.")
    else:
        print(f"    등록 방법 : Windows 작업 스케줄러 {job.task_name!r}")
        print(f"    실행할 것 : {shown(create_argv(job))}")
        if job.kind == "resident":
            print("    바뀌는 것 : 이 계정으로 **로그인할 때** 앱이 뜬다. 창은 안 뜬다.")
            print("              ★죽으면 **다시 안 뜬다** — 스케줄러에 재시작이 없다.")
        else:
            print(f"    바뀌는 것 : 로그인해 있는 동안 {schedule_text(job)} 한 회차가 돈다. 창은 안 뜬다.")
            print("              실패하면 스케줄러의 「마지막 결과」가 0 이 아니게 된다.")
        print(f"    기록      : var/ops/heartbeat/{job.name}.json · var/ops/logs/{job.name}-<날짜>.log")
        print(f"    되돌리기  : python -m scripts.ops.install_services --remove --only {job.name}")
        print(f"              (= {shown(delete_argv(job))})")
        print("    권한      : 관리자 필요 없음(이 계정의 작업으로 등록된다)")
    print(f"    왜 상시    : {job.why}")
    print(f"    죽으면     : {job.dead_signal}")
    print()


def status(job: Job) -> bool:
    if job.kind == "service":
        result = _run(["sc", "query", job.task_name])
        ok = result.returncode == 0
        state = next((ln.strip() for ln in result.stdout.splitlines() if "STATE" in ln.upper()
                      or "상태" in ln), "")
        print(f"[{job.name}] {'서비스 등록됨' if ok else '★등록 안 됨'} — {job.task_name}"
              + (f" · {state}" if state else ""))
        return ok
    result = _run(["schtasks", "/Query", "/TN", job.task_name, "/FO", "LIST"])
    if result.returncode != 0:
        print(f"[{job.name}] ★걸려 있지 않다 — {job.task_name!r}")
        return False
    keep = ("작업 이름", "TaskName", "상태", "Status", "다음 실행", "Next Run",
            "마지막 실행", "Last Run", "마지막 결과", "Last Result")
    print(f"[{job.name}] 걸려 있다 — {job.task_name!r}")
    for line in result.stdout.splitlines():
        if any(k in line for k in keep):
            print("    " + line.strip())
    return True


def apply(job: Job, *, pg_ctl: str | None, pgdata: str | None, port: int,
          shared_ok: bool) -> int:
    if job.kind == "service":
        if not shared_ok:
            print(f"★{job.name}: `--yes-shared-cluster` 없이는 등록하지 않는다 "
                  f"(공유 클러스터다).", file=sys.stderr)
            return 1
        if not pg_ctl or not pgdata:
            print(f"★{job.name}: pg_ctl 또는 데이터 디렉터리를 못 정했다 — 등록하지 않았다.",
                  file=sys.stderr)
            return 1
        if not is_admin():
            print("★관리자 권한이 아니다 — 서비스 등록은 안 된다. "
                  "PowerShell 을 「관리자로 실행」 해서 다시 부른다.", file=sys.stderr)
            return 1
        result = _run(pg_register_argv(pg_ctl, pgdata, port, job.task_name))
    else:
        result = _run(create_argv(job))
    if result.returncode != 0:
        print(f"★{job.name} 등록 실패: {(result.stderr or result.stdout).strip()[:300]}",
              file=sys.stderr)
        return 1
    print(f"[{job.name}] 등록했다 — {job.task_name!r}")
    print(f"    떼는 법: python -m scripts.ops.install_services --remove --only {job.name}")
    return 0


def remove(job: Job, *, pg_ctl: str | None) -> int:
    if job.kind == "service":
        if not pg_ctl:
            print(f"★{job.name}: pg_ctl 를 못 찾아 해제하지 못했다.", file=sys.stderr)
            return 1
        if not is_admin():
            print("★관리자 권한이 아니다 — 서비스 해제는 안 된다.", file=sys.stderr)
            return 1
        result = _run(pg_unregister_argv(pg_ctl, job.task_name))
    else:
        result = _run(delete_argv(job))
    if result.returncode != 0:
        print(f"★{job.name} 해제 실패(또는 걸려 있지 않다): "
              f"{(result.stderr or result.stdout).strip()[:200]}", file=sys.stderr)
        return 1
    print(f"[{job.name}] 뗐다 — {job.task_name!r}")
    return 0


def main() -> int:
    # ★윈도 콘솔 기본 인코딩(cp949)으로는 이 표의 글자가 안 나간다 — 출력만 UTF-8 로 돌린다.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="상시 실행을 이 기계에 건다(기본은 미리보기)")
    parser.add_argument("--apply", action="store_true", help="실제로 등록한다")
    parser.add_argument("--remove", action="store_true", help="뗀다")
    parser.add_argument("--status", action="store_true", help="지금 걸려 있나")
    # ★`[2026-09-22]` **두 가지를 다 받는다** — `--only a,b` 도, `--only a --only b` 도.
    #   쉼표만 받던 때 `--only sweepers --only outbox --only daily_feedback` 을 주니 argparse 가
    #   **마지막 하나만** 남겨 셋 중 하나만 걸렸다. 사람이 틀리게 쓴 것이 아니라 받는 쪽이 좁았다.
    parser.add_argument("--only", action="append", default=None,
                        help=f"쉼표로 묶거나 여러 번. 있는 것: {', '.join(JOBS)}")
    parser.add_argument("--pgdata", default=os.environ.get("ACOP_PGDATA"),
                        help="PostgreSQL 데이터 디렉터리(서비스 등록용)")
    parser.add_argument("--pgctl", default=os.environ.get("ACOP_PGCTL"), help="pg_ctl.exe 경로")
    parser.add_argument("--port", type=int, default=DEFAULT_PG_PORT)
    parser.add_argument("--yes-shared-cluster", action="store_true",
                        help="DB 서비스 등록이 옆 프로젝트에도 영향을 준다는 것을 확인했다")
    args = parser.parse_args()

    jobs = select(args.only)
    pg_ctl = find_pg_ctl(args.pgctl)

    if args.status:
        live = sum(1 for job in jobs if status(job))
        print(f"\n걸려 있는 것 {live}/{len(jobs)}개")
        return 0

    if args.remove:
        failed = sum(remove(job, pg_ctl=pg_ctl) for job in jobs)
        print(f"\n뗀 것 {len(jobs) - failed}/{len(jobs)}개")
        return 1 if failed else 0

    if args.apply:
        failed = sum(apply(job, pg_ctl=pg_ctl, pgdata=args.pgdata, port=args.port,
                           shared_ok=args.yes_shared_cluster) for job in jobs)
        print(f"\n등록한 것 {len(jobs) - failed}/{len(jobs)}개")
        print("확인: python -m scripts.ops.install_services --status")
        print("점검: python -m scripts.ops.healthcheck")
        return 1 if failed else 0

    print("=" * 78)
    print("triPilot 상시 실행 — 등록 **미리보기**. 아무것도 바꾸지 않았다")
    print("=" * 78)
    print(f"저장소  : {REPO_ROOT}")
    print(f"파이썬  : {pythonw()}")
    print(f"pg_ctl  : {pg_ctl or '★못 찾았다'}")
    print(f"관리자  : {'예' if is_admin() else '아니오 (서비스 등록에는 필요하다)'}")
    print(f"대상    : {len(jobs)}개 — {', '.join(job.name for job in jobs)}")
    print("=" * 78)
    print()
    for job in jobs:
        preview(job, pg_ctl=pg_ctl, pgdata=args.pgdata, port=args.port)
    print("=" * 78)
    print("★아무것도 등록하지 않았다. 실제로 걸려면 --apply 를 준다.")
    print("★기계에 남는 설정이다 — 떼는 법은 각 항목의 「되돌리기」 줄에 있다.")
    print("★문서: wiki/operations/always-on.md · wiki/operations/move-to-server.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
