"""여행 판 쓰기 중 저장소 운영 실패 — 「안 바뀐 것이 확인될 때만」 명시적 `save_failed` `[2026-10-27 C 전수검사 · 알려진 이슈 (d)]`.

채팅 고치기(`chat_edit.run` — 2026-10-26 묶음 L F03)가 쓰던 규칙을 다른 판 쓰기 길(`TripDesk._write` · `journey_progress.apply` ·
`requested_destination.apply`)에도 같게 쓴다. 전에는 그 길들의 psycopg `OperationalError` 가 그대로 올라가 일반 500 이었다.

★`OperationalError` 계열(연결 · 잠금 · 취소 · 디스크)만 본다. 코드 결함(IntegrityError · ProgrammingError …)은 잡지 않는다.
★새 연결로 그 여행 행을 `FOR SHARE` 로 다시 읽어 **기준 판 그대로**일 때만 `save_failed` 다(`chat_edit._unchanged_after_failure` —
  끊긴 연결의 COMMIT 이 끝날 때까지 기다린다). 다시 읽지 못했거나 판이 바뀌었으면 원래 예외를 올린다(숨기지 않는다).
★기록 · 응답에는 예외 종류 이름뿐이다(메시지 · SQL 인자는 고객 값을 담을 수 있다).
"""
from __future__ import annotations

import logging
from typing import Any, Callable
from uuid import UUID

import psycopg

from .chat_edit import SAVE_FAILED_TEXT, _unchanged_after_failure

log = logging.getLogger(__name__)


def guarded(write: Callable[[], Any], *, connect: Callable[[], Any], tenant: str, trip_id: UUID, base_version: int,
            where: str) -> Any:
    try:
        return write()
    except psycopg.OperationalError as exc:
        if not _unchanged_after_failure(connect, tenant, trip_id, base_version):
            raise
        log.error("%s storage write failed trip=%s error=%s (version unchanged)", where, trip_id, type(exc).__name__)
        return {"status": "escalated", "reason": "save_failed", "text": SAVE_FAILED_TEXT, "version": base_version}


__all__ = ["guarded"]
