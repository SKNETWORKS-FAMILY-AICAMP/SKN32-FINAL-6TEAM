"""배포 공지 상태 쓰기 — 자동 반영(`auto_deploy.sh`)이 단계마다 부른다(D-CS-019).

  python3 deploy_notice.py --dir <state/service-notice> begin --sha <커밋 10자>
  python3 deploy_notice.py --dir <…> step migrate|switch|recover
  python3 deploy_notice.py --dir <…> end done|kept_previous|trouble

★호스트 파이썬 표준 라이브러리만 쓴다(배포 스크립트와 같은 조건). 문장은 쓰지 않는다 — 상태 · 한국 시각 · 끊김 예상만 적고,
  고객 문구는 웹이 정해 둔 한국어·영어 틀로 만든다. 파일은 임시 파일에 쓴 뒤 바꿔 끼운다(api 가 잘린 파일을 읽지 않게).
★실패해도 배포를 멈추지 않는다 — 호출하는 쪽이 `|| log` 로 경고만 남긴다. 원본 기록은 그대로 `deploy.log` 다.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile

KST = timezone(timedelta(hours=9))
NOTICE = "notice.json"
HISTORY = "history.json"
#: 바꾸기(컨테이너 세 개를 새로 만드는 동안) 끊김 예상 — 실측이 없을 때. 2026-10-14 x600 서버 복원 시험에서 한 번에 1~3분이었다(deploy/README.md).
DEFAULT_OUTAGE_SECONDS = 120
OUTAGE_BOUNDS = (30, 300)
HISTORY_KEEP = 5
PHASE_OF_STEP = {"build": "preparing", "migrate": "preparing", "switch": "switching", "recover": "switching"}
ENDINGS = ("done", "kept_previous", "trouble")


def now() -> datetime:
    return datetime.now(KST).replace(microsecond=0)


def _read(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    os.chmod(temporary, 0o644)          # api 컨테이너가 읽는다 — 비밀이 없는 파일이다
    os.replace(temporary, path)


def expected_outage(directory: Path) -> int:
    """최근 바꾸기 실측(초)의 최댓값 — 넉넉하게 잡는다. 없으면 기본값."""
    history = _read(directory / HISTORY)
    seconds = [int(v) for v in history if isinstance(v, (int, float)) and v > 0] if isinstance(history, list) else []
    if not seconds:
        return DEFAULT_OUTAGE_SECONDS
    low, high = OUTAGE_BOUNDS
    return max(low, min(high, max(seconds[-HISTORY_KEEP:])))


def begin(directory: Path, sha: str, at: datetime | None = None) -> dict:
    at = at or now()
    notice = {"version": 1, "deploy_id": f"{sha[:10]}-{int(at.timestamp())}", "phase": "preparing", "step": "build",
              "started_at": at.isoformat(), "switch_started_at": None, "finished_at": None, "updated_at": at.isoformat(),
              "expected_outage_seconds": expected_outage(directory)}
    _write(directory / NOTICE, notice)
    return notice


def _current(directory: Path) -> dict:
    notice = _read(directory / NOTICE)
    if not isinstance(notice, dict) or notice.get("phase") not in ("preparing", "switching"):
        raise SystemExit("진행 중인 배포 공지가 없다 — begin 을 먼저 부른다")
    return notice


def step(directory: Path, name: str, at: datetime | None = None) -> dict:
    at = at or now()
    notice = _current(directory)
    notice.update(phase=PHASE_OF_STEP[name], step=name, updated_at=at.isoformat())
    if name == "switch":
        notice["switch_started_at"] = at.isoformat()
    _write(directory / NOTICE, notice)
    return notice


def end(directory: Path, outcome: str, at: datetime | None = None) -> dict:
    at = at or now()
    notice = _current(directory)
    notice.update(phase=outcome, updated_at=at.isoformat(), finished_at=at.isoformat())
    # 바꾸기가 끝까지 성공했을 때만 그 시간을 다음 예상에 쓴다(지켜보기 30초가 들어 있어 넉넉하다).
    if outcome == "done" and notice.get("switch_started_at") and notice.get("step") == "switch":
        took = int((at - datetime.fromisoformat(notice["switch_started_at"])).total_seconds())
        history = _read(directory / HISTORY)
        history = [v for v in history if isinstance(v, (int, float))] if isinstance(history, list) else []
        _write(directory / HISTORY, (history + [max(0, took)])[-HISTORY_KEEP:])
    _write(directory / NOTICE, notice)
    return notice


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    b = sub.add_parser("begin"); b.add_argument("--sha", required=True)
    s = sub.add_parser("step"); s.add_argument("name", choices=tuple(PHASE_OF_STEP))
    e = sub.add_parser("end"); e.add_argument("outcome", choices=ENDINGS)
    args = parser.parse_args(argv)
    if args.action == "begin":
        notice = begin(args.dir, args.sha)
    elif args.action == "step":
        notice = step(args.dir, args.name)
    else:
        notice = end(args.dir, args.outcome)
    print(f"배포 공지: {notice['phase']} ({notice['deploy_id']})")


if __name__ == "__main__":
    main()
