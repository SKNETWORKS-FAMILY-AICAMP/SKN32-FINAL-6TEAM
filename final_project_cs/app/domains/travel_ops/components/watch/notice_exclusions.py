# -*- coding: utf-8 -*-
"""일정 감시에 보내지 않은 「기타」 재난 문자 기록 · 관리자 조회 `[2026-10-13 사용자 결정]`.

★무엇. 재해구분 「기타」 문자 중 규칙과 모델이 둘 다 「여행 영향 없음」이라 한 것은 에이전트에 보내지 않는다(우리가 못 찾은 영향을
  에이전트가 찾을 수 없다). 대신 버리지 않고 표 `notice_excluded_messages`(마이그레이션 903)에 남겨, 관리자 웹앱에서
  「무슨 사안이 몇 번 왔나」를 본다 — 걸러진 것 중 정말 여행에 영향이 있던 것을 찾아 규칙 · 모델을 고치는 재료다.
★어떻게. `disaster_msg.judge` 가 걸러낸 문자를 `record` 로 넘긴다(조립이 꽂는다 — `register`). 같은 일련번호는 한 번만 쓴다
  (프로세스 안 기억 + DB `ON CONFLICT DO NOTHING`). 기록 실패는 감시를 멈추지 않는다 — 세고 경고로 남긴다(조용히 넘기지 않는다).
★조회(`summary`)는 본문 단위로 묶는다: 본문 · 재해구분 · 건수(서로 다른 문자 수) · 처음/마지막 시각 · 수신지역 예 · 누가 걸렀나.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

STATS: dict[str, int] = {"recorded": 0, "skipped_seen": 0, "failed": 0}
_seen: set[str] = set()
_lock = threading.Lock()
_SEEN_MAX = 20000


def _hash(text: str) -> str:
    return hashlib.sha256(" ".join(str(text or "").split()).encode("utf-8")).hexdigest()


def record(item: dict[str, Any], *, connection_factory: Callable[[], Any]) -> bool:
    """걸러진 문자 한 통을 남긴다. 새로 썼으면 True. 실패해도 예외를 올리지 않는다(감시를 멈추지 않는다)."""
    serial = str(item.get("serial") or "").strip()
    if not serial:
        return False
    with _lock:
        if serial in _seen:
            STATS["skipped_seen"] += 1
            return False
    created = item.get("created_at")
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    try:
        with connection_factory() as conn:
            conn.execute(
                "INSERT INTO notice_excluded_messages (serial, text_hash, body, kind, step, regions, sent_at, judged_by, prompt_version) "
                "VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s) ON CONFLICT (serial) DO NOTHING",
                (serial, _hash(item.get("text", "")), " ".join(str(item.get("text") or "").split()), str(item.get("kind") or ""),
                 str(item.get("step") or ""), json.dumps(item.get("regions") or [], ensure_ascii=False), created,
                 "rule+model" if item.get("model_checked") else "rule", item.get("prompt_version")))
            conn.commit()
    except Exception as exc:                               # noqa: BLE001 — 기록 실패로 감시를 멈추지 않는다(세고 남긴다)
        STATS["failed"] += 1
        logger.warning("걸러진 재난 문자 기록 실패 (serial=%s): %s", serial, exc)
        return False
    with _lock:
        if len(_seen) >= _SEEN_MAX:
            _seen.clear()
        _seen.add(serial)
    STATS["recorded"] += 1
    return True


def summary(conn, *, days: int = 30, limit: int = 100, now: datetime | None = None) -> dict[str, Any]:
    """최근 `days` 일 동안 걸러진 문자를 본문 단위로 묶어 건수가 많은 순으로."""
    since = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    rows = conn.execute(
        "SELECT text_hash, min(body), min(kind), count(*), min(sent_at), max(sent_at), "
        "       (array_agg(regions ORDER BY sent_at DESC))[1], array_agg(DISTINCT judged_by) "
        "FROM notice_excluded_messages WHERE sent_at >= %s GROUP BY text_hash "
        "ORDER BY count(*) DESC, max(sent_at) DESC LIMIT %s", (since, limit)).fetchall()
    total = conn.execute("SELECT count(*), count(DISTINCT text_hash) FROM notice_excluded_messages WHERE sent_at >= %s",
                         (since,)).fetchone()
    items = [{"text_hash": r[0], "body": r[1], "kind": r[2], "count": int(r[3]),
              "first_sent_at": r[4].isoformat() if r[4] else None, "last_sent_at": r[5].isoformat() if r[5] else None,
              "regions_example": r[6], "judged_by": sorted(r[7] or [])} for r in rows]
    return {"days": days, "since": since.isoformat(), "messages": int(total[0]), "distinct_bodies": int(total[1]), "items": items}


def register() -> None:
    """조립 때 한 번 — `disaster_msg` 에 기록 함수를 꽂는다."""
    from app.domains.travel_ops.ports.data_sources import disaster_msg
    from app.infrastructure.db.session import get_connection

    disaster_msg.set_excluded_sink(lambda item: record(item, connection_factory=get_connection))


__all__ = ["STATS", "record", "register", "summary"]
