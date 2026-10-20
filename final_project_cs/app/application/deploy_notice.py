"""배포 공지(D-CS-019) — x600 서버 자동 배포가 쓴 상태 파일을 읽어 **고객 공지 한 건**으로 만든다.

자동 배포(`deploy/auto_deploy.sh` → `deploy/deploy_notice.py`)가 단계마다 상태 · 한국 시각 · 끊김 예상만 적는다.
여기서 그 상태를 **정해 둔 문구 틀**(한국어 · 영어)에 넣어 운영자 공지와 같은 모양으로 낸다 — 고객 공지 경로(`GET /v1/web/support/notices`)가
운영자 공지 옆에 붙인다. 모델은 부르지 않는다. 시각은 파일의 값을 시:분 그대로 옮긴다(바꾸지 않는다).

파일이 없으면 공지 없음. 읽을 수 없거나 모양이 틀리면 공지 없음 + 경고 기록(조용히 넘기지 않는다).
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

RUNNING = ("preparing", "switching")
#: 끝난 공지를 보이는 시간 — 그 뒤엔 공지 없음. 문제(`trouble`)는 사람이 볼 때까지 더 오래 둔다.
SHOWN_AFTER_END = {"done": timedelta(minutes=5), "kept_previous": timedelta(minutes=5), "trouble": timedelta(minutes=30)}
#: 끝나지 않은 단계가 이만큼 갱신이 없으면 배포 프로세스가 죽었을 수 있다 — 고객에게 보이지 않는다.
#:  빌드 600초 + DB 이주 180초 + 바꾸기 240초 + 지켜보기 30초 ≈ 18분(auto_deploy.sh 의 상한)보다 넉넉하게.
RUNNING_STALE_AFTER = timedelta(minutes=30)

#: 운영자 공지의 종류(관리 콘솔이 고르는 이름) — 화면이 딱지 · 색을 이것으로 고른다(`features/support/service-notices.tsx`).
KIND_PLANNED, KIND_INFO, KIND_DISRUPTION = "점검 예고", "안내", "기능 차질·장애"


def _when(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _clock(value: str) -> str:
    """`2026-10-20T14:05:00+09:00` → `14:05` — 파일의 시각 그대로."""
    return value[11:16]


def read_state(path: Path, now: datetime) -> dict | None:
    """상태 파일 → 지금 보일 상태(없으면 `None`)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning("배포 공지 파일을 읽지 못했다: %s", type(exc).__name__)
        return None
    phase = raw.get("phase") if isinstance(raw, dict) else None
    updated = _when(raw.get("updated_at")) if isinstance(raw, dict) else None
    started = _when(raw.get("started_at")) if isinstance(raw, dict) else None
    outage = raw.get("expected_outage_seconds") if isinstance(raw, dict) else None
    if (phase not in (*RUNNING, *SHOWN_AFTER_END) or not isinstance(raw.get("deploy_id"), str) or updated is None or started is None
            or not isinstance(outage, int) or isinstance(outage, bool) or outage <= 0):
        logger.warning("배포 공지 파일 모양이 틀렸다: phase=%r", phase)
        return None
    if phase in RUNNING and now - updated > RUNNING_STALE_AFTER:
        return None
    if phase in SHOWN_AFTER_END and now - updated > SHOWN_AFTER_END[phase]:
        return None
    return raw


def customer_notice(state: dict) -> dict:
    """상태 → 운영자 공지와 같은 모양의 공지 한 건(정해 둔 한국어 · 영어 문구)."""
    phase = state["phase"]
    minutes = max(1, math.ceil(state["expected_outage_seconds"] / 60))
    started = _clock(state["started_at"])
    switched = _clock(state["switch_started_at"]) if _when(state.get("switch_started_at")) else None
    finished = _clock(state["finished_at"]) if _when(state.get("finished_at")) else _clock(state["updated_at"])
    if phase == "preparing":
        kind, ko, en = KIND_PLANNED, (
            "곧 새 판으로 바뀌어요",
            f"지금은 그대로 쓰실 수 있어요. {started}에 시작한 준비가 끝나면 약 {minutes}분 동안 연결이 끊길 수 있어요. 저장된 일정은 그대로예요."), (
            "A new version is coming shortly",
            f"You can keep using the service for now. When the preparation that started at {started} KST finishes, the connection may drop for about {minutes} min. Your saved plans are safe.")
    elif phase == "switching":
        at = switched or started
        kind, ko, en = KIND_PLANNED, (
            "새 판으로 바꾸는 중이에요",
            f"{at}부터 약 {minutes}분 동안 연결이 끊길 수 있어요. 저장된 일정은 그대로예요. 화면이 안 열리면 잠시 뒤 다시 시도해 주세요."), (
            "Switching to a new version",
            f"From {at} KST the connection may drop for about {minutes} min. Your saved plans are safe. If something does not load, please try again shortly.")
    elif phase == "done":
        kind, ko, en = KIND_INFO, (
            "새 판으로 바뀌었어요", f"{finished}에 끝났어요. 계속 쓰시면 돼요."), (
            "The new version is live", f"Finished at {finished} KST. You can carry on.")
    elif phase == "kept_previous" and switched:
        kind, ko, en = KIND_INFO, (
            "이번 업데이트는 미뤘어요", f"새 판으로 바꾸지 못해 {finished}에 원래 판으로 되돌렸어요. 저장된 일정은 그대로예요."), (
            "This update was postponed", f"The new version could not be switched in, so the previous one was restored at {finished} KST. Your saved plans are safe.")
    elif phase == "kept_previous":
        kind, ko, en = KIND_INFO, (
            "이번 업데이트는 미뤘어요", "새 판 준비가 끝나지 않아 지금 판을 그대로 쓰고 있어요. 이용에는 영향이 없어요."), (
            "This update was postponed", "The new version was not ready, so the current one stays. Nothing changes for you.")
    else:
        kind, ko, en = KIND_DISRUPTION, (
            "새 판으로 바꾸다 문제가 생겼어요", f"{finished}부터 일부 기능이 안 될 수 있어요. 안 되면 잠시 뒤 다시 시도해 주세요."), (
            "A problem occurred while switching versions", f"Since {finished} KST some features may not work. If something fails, please try again shortly.")
    return {"id": f"deploy:{state['deploy_id']}:{phase}", "kind": kind, "title": ko[0], "body": ko[1], "titleEn": en[0], "bodyEn": en[1],
            "startsAt": state["started_at"][:16], "endsAt": None}


def current_notice(now: datetime, path: Path | None = None) -> dict | None:
    """지금 고객에게 보일 배포 공지(없으면 `None`). `now` 는 시간대가 있는 시각."""
    state = read_state(path or Path(get_settings().service_notice_path), now)
    return customer_notice(state) if state else None
