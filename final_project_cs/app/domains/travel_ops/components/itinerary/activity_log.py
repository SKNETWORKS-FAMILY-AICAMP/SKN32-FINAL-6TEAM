# -*- coding: utf-8 -*-
"""사용자 **활동 기록** — 사용자가 무엇을 골랐나 · 눌렀나를 한 줄씩 쌓는다. `[결정 2026-10-06 사용자]` 마이그레이션 054

「사용자가 활동한 모든 데이터는 운영을 위해 기록해야 한다」 — 값을 모를 때 기본값을 정하려면 **실제 선택이 쌓여야** 한다.
★자유 문장은 여기에 안 넣는다(채팅은 `chat_log.record` 가 가린 뒤 저장한다). 여기에는 선택 값 · 식별자만 둔다.
★기록이 실패해도 사용자의 동작을 막지 않는다 — 대신 **경고를 남기고 `False` 를 돌려준다**(조용한 스킵이 아니다). 부르는 쪽이 필요하면 센다.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def record(conn, *, tenant_id: str, kind: str, payload: dict[str, Any], trip_id: UUID | None = None,
           customer_id: UUID | None = None) -> bool:
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO user_activity_events (tenant_id, trip_id, customer_id, kind, payload_json) "
                        "VALUES (%s,%s,%s,%s,%s::jsonb)",
                        (tenant_id, trip_id, customer_id, kind, json.dumps(payload, ensure_ascii=False, default=str)))
        return True
    except Exception:                                   # noqa: BLE001 — 기록 실패가 사용자의 동작을 막지 않는다. 경고로 남긴다
        logger.warning("user_activity_events insert failed kind=%s trip=%s (migration 054?)", kind, trip_id, exc_info=True)
        return False


def latest(conn, *, tenant_id: str, trip_id: UUID, kind: str) -> dict[str, Any] | None:
    """그 종류의 가장 최근 기록 한 줄 — 없거나 표가 없으면 None."""
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT payload_json, created_at FROM user_activity_events WHERE tenant_id=%s AND trip_id=%s AND kind=%s "
                        "ORDER BY event_id DESC LIMIT 1", (tenant_id, trip_id, kind))
            row = cur.fetchone()
    except Exception:                                   # noqa: BLE001
        logger.warning("user_activity_events unreadable kind=%s trip=%s", kind, trip_id, exc_info=True)
        return None
    return None if row is None else {**row[0], "at": row[1].isoformat()}


__all__ = ["latest", "record"]
