# -*- coding: utf-8 -*-
"""계획서 접수 백업 — **지우기 전에** 접수와 딸린 값을 `intake_backups` 에 통째로 담는다. `[2026-10-16 사용자 지시]` 마이그레이션 906

☆왜: 「7일 뒤 삭제하면 안 되고 우선 DB 에 다 저장을 해놔야 해」 — 고객이 입력한 계획서는 계획 읽기의 골든셋 재료다.
  여행 삭제(`itinerary/trip_delete.py`) · 게스트 정리(`web_account/guest_cleanup.py`) · 회원 정리(`web_account/member_cleanup.py`)가
  `trip_intakes` 를 지우면 원문 · 읽은 값 · 고객이 고친 값이 함께 사라졌다.
★지우는 쪽이 **같은 트랜잭션에서 지우기 직전에** 부른다 — 백업이 실패하면 예외가 그대로 올라가 삭제도 일어나지 않는다(조용히 지우지 않는다).
★한 접수 = 한 행. 같은 접수를 다시 백업하면(다시 연 여행을 지우는 경우 등) 최신 모양으로 덮는다.
★보관 기간 = 관리 화면 `retention.intake_backup_days`(가드레일 `retention.intake_backup_days` 가 기본값). **0 이면 지우지 않는다.**
  기간은 지울 때 읽는다(`purge_expired`) — 관리자가 기간을 바꾸면 이미 쌓인 백업에도 새 기간이 적용된다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

REASONS = ("trip_delete", "guest_cleanup", "member_cleanup")

#: 접수 행과 자식 표의 행을 있는 그대로(`to_jsonb`) 담는다 — 표에 칸이 늘어도 고치지 않게
_BACKUP = """
INSERT INTO intake_backups (tenant_id, intake_id, source_customer_id, source_trip_id, reason, received_at, snapshot)
SELECT i.tenant_id, i.intake_id, i.customer_id, COALESCE(i.trip_id, i.reopen_trip_id), %(reason)s, i.received_at,
       jsonb_build_object(
           'intake', to_jsonb(i),
           'sources', COALESCE((SELECT jsonb_agg(to_jsonb(s) ORDER BY s.position) FROM intake_sources s
                                WHERE s.intake_id = i.intake_id), '[]'::jsonb),
           'claims', COALESCE((SELECT jsonb_agg(to_jsonb(c) ORDER BY c.revision, c.created_at, c.field) FROM intake_claims c
                               WHERE c.intake_id = i.intake_id), '[]'::jsonb),
           'reviews', COALESCE((SELECT jsonb_agg(to_jsonb(r) ORDER BY r.revision) FROM intake_reviews r
                                WHERE r.intake_id = i.intake_id), '[]'::jsonb),
           'survey_answers', COALESCE((SELECT jsonb_agg(to_jsonb(a)) FROM trip_intake_survey_answers a
                                       WHERE a.intake_id = i.intake_id), '[]'::jsonb),
           'test_scenarios', COALESCE((SELECT jsonb_agg(to_jsonb(t)) FROM intake_test_scenarios t
                                       WHERE t.intake_id = i.intake_id), '[]'::jsonb))
FROM trip_intakes i
WHERE i.tenant_id = %(tenant)s AND i.customer_id = %(customer)s {extra}
ON CONFLICT (tenant_id, intake_id) DO UPDATE
   SET snapshot = EXCLUDED.snapshot, reason = EXCLUDED.reason, source_trip_id = EXCLUDED.source_trip_id,
       backed_up_at = now()
"""


def _check(reason: str) -> None:
    if reason not in REASONS:
        raise ValueError(f"모르는 백업 이유: {reason}")


def backup_trip_intakes(conn, *, tenant_id: str, customer_id: UUID, trip_id: UUID, reason: str) -> int:
    """이 여행으로 만든 접수 · 이 여행을 다시 연 수정 접수(여행 삭제가 지우는 것과 같은 범위)를 백업한다. 백업한 수."""
    _check(reason)
    with conn.cursor() as cur:
        cur.execute(_BACKUP.format(extra="AND (i.trip_id = %(trip)s OR i.reopen_trip_id = %(trip)s)"),
                    {"reason": reason, "tenant": tenant_id, "customer": customer_id, "trip": trip_id})
        return cur.rowcount


def backup_customer_intakes(conn, *, tenant_id: str, customer_id: UUID, reason: str) -> int:
    """이 고객의 남은 접수 전부(여행이 안 된 접수 포함)를 백업한다. 백업한 수."""
    _check(reason)
    with conn.cursor() as cur:
        cur.execute(_BACKUP.format(extra=""), {"reason": reason, "tenant": tenant_id, "customer": customer_id})
        return cur.rowcount


def purge_expired(conn, tenant_id: str, *, days: int, now: datetime | None = None) -> dict[str, Any]:
    """보관 기간이 지난 백업을 지운다. `days` 가 0 이면 아무것도 지우지 않는다(`{"skipped": "keep_forever"}`)."""
    if days <= 0:
        return {"skipped": "keep_forever"}
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM intake_backups WHERE tenant_id=%s AND backed_up_at < %s", (tenant_id, cutoff))
        return {"deleted": cur.rowcount, "days": days}


def summary(conn, tenant_id: str) -> dict[str, Any]:
    """관리 화면 · 보고용 — 이유별 백업 수와 가장 오래된 백업 시각."""
    with conn.cursor() as cur:
        cur.execute("SELECT reason, count(*), min(backed_up_at) FROM intake_backups WHERE tenant_id=%s GROUP BY reason",
                    (tenant_id,))
        rows = cur.fetchall()
    return {"by_reason": {r: int(n) for r, n, _ in rows},
            "oldest": min((o for *_, o in rows), default=None)}


__all__ = ["REASONS", "backup_customer_intakes", "backup_trip_intakes", "purge_expired", "summary"]
