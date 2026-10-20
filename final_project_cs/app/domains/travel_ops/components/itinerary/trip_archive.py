# -*- coding: utf-8 -*-
"""시험 여행 보관함 — **지우기 직전에** 시험 여행 전체를 `trip_archives` 에 담는다. `[2026-10-20 사용자 결정]` D-CS-018 · 마이그레이션 062

☆왜: 실서버 확인 뒤 시험 여행을 지우자 「텍스트라 용량도 작은데 왜 자꾸 지우나 — 시험 여행 보관함 만들어. 지우기 직전에 여행 전체(일정·대안·채팅)를
  보관함에 복사하고, 보관함 여행은 감시·알림에서 빼」 · 「앞으로도 남길 건 거기에 넣게 해」.
★시험 여행만 담는다 — 시험 코드로 만든 여행(`test_code`)과 「남길 시험 여행」 표시를 단 여행(`marked`). 실제 고객 여행은 약관대로 지금처럼 함께 파기한다.
★여행 삭제(`trip_delete.delete_trip`)가 **같은 트랜잭션에서 지우기 직전에** 부른다 — 담기가 실패하면 예외가 그대로 올라가 삭제도 일어나지 않는다.
★원래 표의 행을 있는 그대로(`to_jsonb`) 담는다. 새 표가 여행 번호를 들고 생기면 아래 `_TABLES` 에 더한다(여행 삭제 시험이 새 표를 알려 준다).
★표시를 단 살아 있는 여행은 감시 · 안내에서 빠진다 — 조립이 `watch_scope_sql` 을 감시 대상 좁히기 자리(`trip_scope`)에 꽂는다.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.domains.travel_ops.components.intake import backup as intake_backup

#: (표, 정렬) — `trip_id` 칸으로 이 여행의 행을 고른다. 없는 표(설치 안 된 기능)는 건너뛰고 `missing` 에 이름을 남긴다
_TABLES: tuple[tuple[str, str], ...] = (
    ("itinerary_versions", "version"),
    ("itinerary_items", "version, seq"),                 # 등록 때 붙인 대안은 항목의 `detail.alternates` 에 있다
    ("pending_changes", "created_at"),
    ("trip_chat_turns", "created_at"),
    ("trip_guardian_changes", ""),
    ("trip_safety_pauses", ""),
    ("travel_watch_checks", ""),
    ("place_open_checks", ""),
    ("ops_lookup_checks", ""),
    ("ops_lookup_usage", ""),
    ("ops_diagnostic_events", ""),
    ("user_activity_events", ""),
    ("dining.dn_notice", ""),
    ("lg_offer_shown", ""),
    ("lg_core_place_link", ""),
)
KINDS = ("test_code", "marked")


def mark(conn, *, tenant_id: str, trip_id: UUID, marked_by: str, note: str | None = None) -> None:
    """「남길 시험 여행」 표시를 단다(이미 있으면 말만 바꾼다). 표시가 있으면 지울 때 보관함에 담기고, 그동안 감시 · 안내에서 빠진다."""
    with conn.cursor() as cur:
        cur.execute("INSERT INTO trip_archive_marks (tenant_id, trip_id, note, marked_by) VALUES (%s,%s,%s,%s) "
                    "ON CONFLICT (tenant_id, trip_id) DO UPDATE SET note = EXCLUDED.note, marked_by = EXCLUDED.marked_by, marked_at = now()",
                    (tenant_id, trip_id, note, marked_by))


def unmark(conn, *, tenant_id: str, trip_id: UUID) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM trip_archive_marks WHERE tenant_id=%s AND trip_id=%s", (tenant_id, trip_id))
        return cur.rowcount > 0


def kind_of(conn, *, tenant_id: str, trip_id: UUID) -> str | None:
    """시험 여행이면 그 종류, 아니면 None. 표시가 시험 코드보다 먼저다(표시에는 사람이 남긴 말이 있다)."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM trip_archive_marks WHERE tenant_id=%s AND trip_id=%s", (tenant_id, trip_id))
        if cur.fetchone():
            return "marked"
        cur.execute("SELECT 1 FROM trip_intakes i JOIN intake_test_scenarios s ON s.intake_id = i.intake_id "
                    "WHERE i.tenant_id=%s AND (i.trip_id=%s OR i.reopen_trip_id=%s) LIMIT 1", (tenant_id, trip_id, trip_id))
        return "test_code" if cur.fetchone() else None


def _rows(cur, sql: str, params: tuple) -> list[Any]:
    cur.execute(sql, params)
    value = cur.fetchone()[0]
    return value if value is not None else []


def snapshot(conn, *, tenant_id: str, trip_id: UUID) -> dict[str, Any]:
    """여행 한 건을 한 덩어리로 — {trip, tables, intake_ids, missing, mark}. 원래 행을 있는 그대로 담는다."""
    tables: dict[str, list[Any]] = {}
    missing: list[str] = []
    with conn.cursor() as cur:
        cur.execute("SELECT to_jsonb(t) FROM trips t WHERE t.tenant_id=%s AND t.trip_id=%s", (tenant_id, trip_id))
        trip = cur.fetchone()[0]
        for table, order in _TABLES:
            cur.execute("SELECT to_regclass(%s)", (table,))
            if cur.fetchone()[0] is None:
                missing.append(table)
                continue
            by = f" ORDER BY {', '.join('x.' + c.strip() for c in order.split(','))}" if order else ""
            tables[table] = _rows(cur, f"SELECT jsonb_agg(to_jsonb(x){by}) FROM {table} x WHERE x.trip_id=%s", (trip_id,))
        tables["places"] = _rows(cur, "SELECT jsonb_agg(to_jsonb(p)) FROM places p WHERE p.tenant_id=%s AND p.trip_scope=%s",
                                 (tenant_id, trip_id))
        # 알림 문장 — 지우면 바깥함에서 사라진다(`trip_delete`)
        tables["outbox"] = _rows(cur, "SELECT jsonb_agg(to_jsonb(o) ORDER BY o.available_at) FROM outbox o "
                                      "WHERE o.tenant_id=%s AND o.topic='trip.notice' AND o.dedupe_key LIKE %s", (tenant_id, f"{trip_id}:%"))
        # 이 여행의 Case 와 사건 기록 — 약관 파기(`purge_cases`) 전에 담는다
        tables["customer_cases"] = _rows(cur, "SELECT jsonb_agg(to_jsonb(c) ORDER BY c.created_at) FROM customer_cases c "
                                              "WHERE c.tenant_id=%s AND c.state_json->'subject_ref'->>'id' = %s", (tenant_id, str(trip_id)))
        tables["case_events"] = _rows(cur, "SELECT jsonb_agg(to_jsonb(e) ORDER BY e.case_id, e.aggregate_version) FROM case_events e "
                                           "WHERE e.tenant_id=%s AND e.case_id IN (SELECT c.case_id FROM customer_cases c WHERE c.tenant_id=%s "
                                           "AND c.state_json->'subject_ref'->>'id' = %s)", (tenant_id, tenant_id, str(trip_id)))
        # 접수 — 원문 · 읽은 값 · 고친 값은 접수 백업(`intake_backups`)이 담는다. 여기는 번호와 미리 준비한 대안(접수와 함께 지워진다)만
        cur.execute("SELECT intake_id FROM trip_intakes WHERE tenant_id=%s AND (trip_id=%s OR reopen_trip_id=%s) ORDER BY received_at",
                    (tenant_id, trip_id, trip_id))
        intake_ids = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT to_regclass('intake_alternatives')")
        if cur.fetchone()[0] is None:
            missing.append("intake_alternatives")
        else:
            tables["intake_alternatives"] = _rows(cur, "SELECT jsonb_agg(to_jsonb(a) ORDER BY a.intake_id, a.item_index) FROM intake_alternatives a "
                                                       "WHERE a.tenant_id=%s AND a.intake_id = ANY(%s)", (tenant_id, intake_ids))
        cur.execute("SELECT to_jsonb(m) FROM trip_archive_marks m WHERE m.tenant_id=%s AND m.trip_id=%s", (tenant_id, trip_id))
        row = cur.fetchone()
    return {"trip": trip, "tables": tables, "intake_ids": [str(i) for i in intake_ids], "missing": missing,
            "mark": row[0] if row else None}


def archive_if_test(conn, *, tenant_id: str, customer_id: UUID, trip_id: UUID, reason: str) -> int:
    """시험 여행이면 보관함에 담는다(담은 수 0 · 1). 같은 여행을 다시 담으면 최신 모양으로 덮는다. 호출자의 트랜잭션 안에서 돈다."""
    if reason not in intake_backup.REASONS:
        raise ValueError(f"모르는 삭제 이유: {reason}")
    kind = kind_of(conn, tenant_id=tenant_id, trip_id=trip_id)
    if kind is None:
        return 0
    body = snapshot(conn, tenant_id=tenant_id, trip_id=trip_id)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO trip_archives (tenant_id, source_trip_id, source_customer_id, kind, reason, note, title, snapshot) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb) "
                    "ON CONFLICT (tenant_id, source_trip_id) DO UPDATE SET snapshot = EXCLUDED.snapshot, kind = EXCLUDED.kind, "
                    "reason = EXCLUDED.reason, note = EXCLUDED.note, title = EXCLUDED.title, archived_at = now()",
                    (tenant_id, trip_id, customer_id, kind, reason, (body["mark"] or {}).get("note"),
                     (body["trip"] or {}).get("title"), json.dumps(body, ensure_ascii=False, default=str)))
    return 1


def watch_scope_sql(alias: str = "t") -> str:
    """감시 대상 좁히기 조각 — 「남길 시험 여행」 표시를 단 여행은 감시 · 안내에서 뺀다(`trip_scope` 자리에 조립이 꽂는다)."""
    return (f"NOT EXISTS (SELECT 1 FROM trip_archive_marks m WHERE m.tenant_id = {alias}.tenant_id "
            f"AND m.trip_id = {alias}.trip_id)")


def summary(conn, tenant_id: str) -> dict[str, Any]:
    """보고용 — 종류별 보관 수와 가장 최근 보관 시각."""
    with conn.cursor() as cur:
        cur.execute("SELECT kind, count(*), max(archived_at) FROM trip_archives WHERE tenant_id=%s GROUP BY kind", (tenant_id,))
        rows = cur.fetchall()
    return {"by_kind": {k: int(n) for k, n, _ in rows}, "latest": max((t for *_, t in rows), default=None)}


__all__ = ["KINDS", "archive_if_test", "kind_of", "mark", "snapshot", "summary", "unmark", "watch_scope_sql"]
