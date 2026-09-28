"""멈춘 Case 되잡기(sweeper)를 **주기 실행에 건다.** 기본은 명령만 보여 준다.

    python -m scripts.install_sweeper_task            # 무엇을 걸지 보여만 준다(기본)
    python -m scripts.install_sweeper_task --apply    # 실제로 등록한다
    python -m scripts.install_sweeper_task --status   # 지금 걸려 있나
    python -m scripts.install_sweeper_task --remove   # 뗀다

★**이 기계에 있는 스케줄러는 `schtasks` 하나뿐이다**(2026-09-07 실측).
  `docker`·`systemctl`·`cron`·`crontab` 전부 없다 — `docs/manuals/
  2026-08-12_1520_환경_기동절차.md` 가 적어 둔 환경 그대로다. 그래서 이 파일은
  **Windows 작업 스케줄러만** 다룬다.

  ★없는 것에 대고 설정 파일을 미리 써 두지 않는다. 이 저장소는 Docker·Terraform
  에서 이미 그렇게 했다가 "build/run/validate/apply 전부 미검증" 을 문서에 적어야
  했다(`CLAUDE.md` §5). 컨테이너·systemd 배선은 **그 형태가 정해지고 실제로 돌려
  볼 수 있을 때** 붙인다(v9 §12·§28, Phase 2).

★왜 `--once` 를 반복해서 거는가 (상주 `--interval` 이 아니라).

    (1) 프로세스가 죽으면 상주 루프는 그냥 멈춘다. 스케줄러가 매번 새로 띄우면
        한 회차가 죽어도 다음 회차가 돈다
    (2) `--once` 는 `errored` 가 있으면 **exit 1** 이다. 스케줄러가 그걸 실패로
        기록한다 — 상주 모드에는 볼 exit code 가 없다
    (3) "언제 도는지" 가 코드가 아니라 스케줄러에 적힌다

★주기는 **안전이 아니라 복구 지연**을 정한다. 안전은 임계값
  (`config/guardrails.yaml` 의 `reliability.*_stuck_after_seconds`)이 정한다 —
  임계값을 넘겨야 후보가 되므로, 주기를 짧게 해도 정상 처리 중인 Case 를 안 건드린다.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: 작업 이름. ★저장소 이름을 넣는다 — 한 기계에 여러 대상이 있을 수 있다.
TASK_NAME = "A-COP cs sweeper"

#: 분 단위. 60초보다 짧게 할 실익이 없다(임계값을 넘겨야 잡힌다). `schtasks` 의
#: 최소 단위가 1분이라 이보다 잘게는 못 건다 — 필요하면 상주 `--interval` 을 쓴다.
DEFAULT_MINUTES = 1


def _schtasks() -> str:
    exe = shutil.which("schtasks")
    if not exe:
        raise SystemExit(
            "★schtasks 가 없다. 이 스크립트는 Windows 작업 스케줄러만 다룬다.\n"
            "  다른 환경이면 상주 실행을 쓴다: python -m scripts.run_sweepers --interval 60")
    return exe


def _command() -> str:
    """스케줄러가 실행할 명령.

    ★`cd` 를 붙인다. 작업 스케줄러는 시작 디렉터리를 보장하지 않는데,
      `run_sweepers` 는 `config/guardrails.yaml` 을 상대 경로로 읽는다.
    ★`sys.executable` 을 쓴다. `python` 이 PATH 의 어느 것인지는 스케줄러
      세션에서 다를 수 있다 — 이 저장소는 conda env 를 쓴다.
    """
    return f'cmd /c cd /d "{REPO_ROOT}" && "{sys.executable}" -m scripts.run_sweepers --once'


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def status(name: str) -> int:
    result = _run([_schtasks(), "/Query", "/TN", name, "/FO", "LIST"])
    if result.returncode != 0:
        print(f"걸려 있지 않다: {name!r}")
        return 1
    for line in result.stdout.splitlines():
        if any(k in line for k in ("작업 이름", "TaskName", "상태", "Status",
                                   "다음 실행", "Next Run", "마지막 결과", "Last Result")):
            print("   " + line.strip())
    return 0


def install(name: str, minutes: int) -> int:
    command = _command()
    result = _run([_schtasks(), "/Create", "/TN", name, "/TR", command,
                   "/SC", "MINUTE", "/MO", str(minutes), "/F"])
    if result.returncode != 0:
        print("★등록 실패:", (result.stderr or result.stdout).strip()[:200])
        return 1
    print(f"등록했다: {name!r} · {minutes}분마다")
    print(f"   {command}")
    print()
    print("★확인:  python -m scripts.install_sweeper_task --status")
    print("★해제:  python -m scripts.install_sweeper_task --remove")
    return 0


def remove(name: str) -> int:
    result = _run([_schtasks(), "/Delete", "/TN", name, "/F"])
    if result.returncode != 0:
        print("★해제 실패(또는 걸려 있지 않다):", (result.stderr or result.stdout).strip()[:160])
        return 1
    print(f"뗐다: {name!r}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="실제로 등록한다")
    parser.add_argument("--status", action="store_true", help="지금 걸려 있나")
    parser.add_argument("--remove", action="store_true", help="뗀다")
    parser.add_argument("--minutes", type=int, default=DEFAULT_MINUTES)
    parser.add_argument("--name", default=TASK_NAME)
    args = parser.parse_args()

    if args.status:
        return status(args.name)
    if args.remove:
        return remove(args.name)
    if args.apply:
        return install(args.name, args.minutes)

    print(f"작업 이름 : {args.name!r}")
    print(f"주기      : {args.minutes}분마다")
    print(f"실행할 것 : {_command()}")
    print()
    print("★아무것도 등록하지 않았다. 실제로 걸려면 --apply 를 준다.")
    print("  ★기계에 지속되는 설정이다 — 뗄 때는 --remove.")
    print()
    print("★`errored` 가 나오면 `--once` 가 exit 1 을 내고 스케줄러가 실패로 기록한다.")
    print("  (`wiki/records/manuals/운영_멈춘Case_되잡기.md`)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
