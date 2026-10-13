# -*- coding: utf-8 -*-
"""장소 · 날짜별 실시간 운영 상태(웹 공지)를 저장하고 읽는다 — `activity.ac_live_status`(304). `[2026-10-13]` 사용자 결정 A안.

    쓰기   배치(`scripts/activity/check_live_status.py`)가 장소 · 날짜당 한 번 웹 검색 판정을 하고 `record` 로 저장한다
    읽기   고객 요청(`team._live_status_check`)은 `lookup` 으로 저장된 값만 읽는다 — 웹을 부르지 않는다

★요청 수가 아니라 「그날 일정에 든 서로 다른 장소 수」에 비례한다 — 경복궁을 100명이 가도 한 번이다.
★모름도 줄로 남긴다(`unknown`) — 다시 볼 때는 `checked_at` 으로 정한다. 줄이 없으면 아직 안 봤다.
★연결(`conn`)은 부르는 쪽이 넘긴다. 팀은 DB 를 직접 읽지 않으므로 `build_lookup` 이 만든 함수를 조립이 꽂는다(`judge_budget` 과 같은 방식).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Callable

VALUES = ("open", "closed", "unknown")
_COLS = ("content_id", "visit_date", "value", "citations", "basis", "model", "checked_at")

#: 같은 곳 · 같은 날짜를 이 시간 안에 다시 확인하지 않는다 — 비용 상한(알아도 모르는 값도 같다)
RECHECK = timedelta(hours=6)


def _row(row: Any) -> dict[str, Any]:
    out = dict(zip(_COLS, row))
    if isinstance(out.get("citations"), str):
        out["citations"] = json.loads(out["citations"])
    return out


def read(conn, content_id: str | None, visit_date: date | None) -> dict[str, Any] | None:
    """한 곳 · 한 날짜의 저장된 값. 없으면 `None`(아직 안 봤다)."""
    if not content_id or visit_date is None:
        return None
    with conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM activity.ac_live_status WHERE content_id = %s AND visit_date = %s",
                    (str(content_id), visit_date))
        row = cur.fetchone()
    return _row(row) if row else None


_LOOKUP_SQL = (
    "SELECT " + ", ".join(f"s.{c}" for c in _COLS) + " FROM places p "
    "JOIN activity.ac_live_status s ON s.content_id = COALESCE(p.source_content_id, p.attributes->>'source_content_id') "
    "WHERE p.tenant_id = %s AND p.place_id = %s AND s.visit_date = %s LIMIT 1"
)


def lookup(conn, tenant_id: str, place_id: str | None, visit_date: date | None) -> dict[str, Any] | None:
    """코어 장소 하나 · 날짜 → 저장된 값. 연결이 없거나 아직 안 봤으면 `None`."""
    if place_id is None or visit_date is None:
        return None
    with conn.cursor() as cur:
        cur.execute(_LOOKUP_SQL, (tenant_id, str(place_id), visit_date))
        row = cur.fetchone()
    return _row(row) if row else None


def record(conn, content_id: str, visit_date: date, value: str, *, citations: list[dict[str, Any]] | None = None,
           basis: str | None = None, model: str | None = None) -> None:
    """확인한 값을 쓴다(같은 곳 · 같은 날짜면 새 값으로). `closed` 는 인용이 있을 때만 — 근거 없는 「닫혔다」를 저장하지 않는다."""
    if value not in VALUES:
        raise ValueError(f"value 는 {VALUES} 중 하나: {value!r}")
    if not isinstance(visit_date, date):
        raise ValueError("visit_date 는 날짜여야 한다")
    cites = [c for c in (citations or []) if isinstance(c, dict)]
    if value == "closed" and not any(c.get("quote") or c.get("url") for c in cites):
        raise ValueError("closed 는 근거(인용)가 있어야 저장한다")
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO activity.ac_live_status (content_id, visit_date, value, citations, basis, model, checked_at) "
            "VALUES (%s, %s, %s, %s::jsonb, %s, %s, now()) "
            "ON CONFLICT (content_id, visit_date) DO UPDATE SET value = EXCLUDED.value, citations = EXCLUDED.citations, "
            "basis = EXCLUDED.basis, model = EXCLUDED.model, checked_at = now()",
            (str(content_id), visit_date, value, json.dumps(cites, ensure_ascii=False), basis, model))


def fresh(row: dict[str, Any] | None, now: datetime, *, recheck: timedelta = RECHECK) -> bool:
    """이미 확인한 줄이라 다시 부르지 않아도 되나."""
    checked = (row or {}).get("checked_at")
    return isinstance(checked, datetime) and now - checked < recheck


def build_lookup(connection_factory: Callable[[], Any]) -> Callable[[str, str | None, date | None], dict[str, Any] | None]:
    """팀에 꽂는 읽기 함수 `(tenant_id, place_id, visit_date) -> 저장된 값 | None` — 조립이 만든다(코어 협의)."""

    def live_lookup(tenant_id: str, place_id: str | None, visit_date: date | None) -> dict[str, Any] | None:
        with connection_factory() as conn:
            return lookup(conn, tenant_id, place_id, visit_date)

    return live_lookup
