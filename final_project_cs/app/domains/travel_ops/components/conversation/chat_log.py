# -*- coding: utf-8 -*-
"""여행 채팅 **대화 기록** — 결정 단위가 「그 식당」「거기」「방금 바꾼 거」를 앞 대화로 푼다. `[2026-09-29]` 마이그레이션 034

★전에는 대화가 웹 브라우저에만 있었다 — 서버의 해석은 앞 대화를 몰라 「아니 그 식당 세부정보 알려달라고」에 무관한 규정 조각을
  답했다(ui 세션 실서버). 고객 문장은 **가린 뒤** 저장한다(CLAUDE.md §1 — 원문 PII 는 masking 후 저장).
★append-only — 고치지 않는다. 같은 요청(request_id)을 두 번 받으면 기록도 한 번이다(부르는 쪽이 중복을 거른 뒤 부른다).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

#: 결정 단위에 넣는 최근 대화 수(고객 + 답 = 2턴이 한 번 주고받음). ★우리가 고른 값 — 가리키는 말은 대개 바로 앞을 본다
RECENT_TURNS = 6
#: 답 한 줄의 길이 상한 — 앞 대화는 「무엇을 말했나」만 알면 된다(긴 일정 요약이 프롬프트를 채우지 않게)
TURN_CHARS = 160


def record(conn, *, tenant_id: str, trip_id: UUID, customer_text: str, answer: str | None,
           case_id: UUID | str | None) -> None:
    from app.domains.travel_ops.components.core_hooks.feedback import masked

    with conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO trip_chat_turns (tenant_id, trip_id, role, text, case_id) VALUES (%s,%s,'customer',%s,%s)",
                    (tenant_id, trip_id, masked(customer_text), case_id))
        if answer:
            cur.execute("INSERT INTO trip_chat_turns (tenant_id, trip_id, role, text, case_id) "
                        "VALUES (%s,%s,'assistant',%s,%s)", (tenant_id, trip_id, answer, case_id))


def recent(conn, *, tenant_id: str, trip_id: UUID, limit: int = RECENT_TURNS) -> list[dict[str, Any]]:
    """오래된 것부터 최근 `limit` 턴. 표가 없는 DB(시험 · 다른 조립)면 빈 목록."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role, text, case_id, created_at FROM trip_chat_turns WHERE tenant_id=%s AND trip_id=%s "
                        "ORDER BY turn_id DESC LIMIT %s", (tenant_id, trip_id, limit))
            rows = cur.fetchall()
    except Exception as exc:                          # noqa: BLE001 — 기록이 없으면 앞 대화 없이 해석한다
        if type(exc).__name__ != "UndefinedTable":
            raise
        conn.rollback()
        return []
    return [{"role": r[0], "text": r[1], "case_id": str(r[2]) if r[2] else None, "at": r[3].isoformat()}
            for r in reversed(rows)]


__all__ = ["RECENT_TURNS", "TURN_CHARS", "record", "recent"]
