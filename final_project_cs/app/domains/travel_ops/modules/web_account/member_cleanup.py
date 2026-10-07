# -*- coding: utf-8 -*-
"""회원 자료 정리 — 약관의 「마지막 이용 후 N일이 지나면 파기」를 서버가 실제로 지키게 한다. `[2026-10-07 사용자 결정 — uiux 전달, 약관 보관 기간]`

계약 `wiki/external/rest-endpoints.md` 「약관 보관 기간」 · 값 `components/customer/retention.py`(기본 `retention.member_idle_days` 365일) · 기록 `retention_runs`(056).

★대상 = **회원**(`web_social_links` 가 붙은 웹 사용자). 에이전트 API 로 만든 고객 · 시드 · 게스트(`guest_cleanup` 몫)는 건드리지 않는다.
★「마지막 이용」 = 사용자 행 생성 · 소셜 연결 · 키(`web_user_keys`)의 발급/사용 · 세션의 마지막 사용 · 에이전트 키의 발급/사용 중 **가장 늦은 때**.
  계획서 링크 열람 · 자동 감시 · 외부 호출은 이용이 아니다(게스트 정리와 같은 정의에 소셜 연결 · 에이전트 키 사용을 더했다). 약관에는 이 한 문장을 쓰면 된다.
★**지우는 일은 되돌릴 수 없다 — 모드로 지킨다**(`retention.purge_mode`, 관리 화면 `/admin/limits`): `off` 아무것도 안 함 · `dry_run`(기본) 대상을 **세기만 하고** `retention_runs` 에 건수를 남김 ·
  `on` 지움. 사용자가 dry_run 의 건수를 보고 승인한 뒤에만 `on` 으로 바꾼다. 한 번에 `retention.purge_batch` 명까지.
★지울 것(회원 한 명): 여행(`trip_delete.delete_trip` — 일정 · 대화 · 접수 · 알림 · 여행 전용 장소 · 그 여행의 처리 기록) · 여행이 안 된 접수 · 활동 기록(`user_activity_events`) · 장소 별칭 ·
  프로필(웹훅 · 복구 이메일 · 텔레그램) · 소셜 연결 · 로그인 표 · 세션 · 키 · 에이전트 키 · 남은 처리 기록(Case) · 사용자 행. **동의 기록은 지우지 않는다**(증빙 — 보관 기간이 따로 있다).
★사용자 행을 가리키는 다른 기록(옛 쇼핑몰 표 등)이 있으면 사용자 행만 남긴다(저장점 — 이 삭제만 되돌린다). 그때 식별 정보(프로필 · 연결 · 키)는 이미 지워져 있다.
★삭제는 사용자마다 **따로 한 트랜잭션** · 센다(조용히 넘기지 않는다).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from psycopg.errors import ForeignKeyViolation
from psycopg.types.json import Json

from app.core.settings import get_guardrails

from app.domains.travel_ops.components.customer import retention
from app.domains.travel_ops.components.itinerary import trip_delete

_CANDIDATES = """
SELECT c.customer_id FROM customers c
CROSS JOIN LATERAL (
    SELECT GREATEST(
        c.created_at,
        COALESCE((SELECT max(l.linked_at) FROM web_social_links l WHERE l.tenant_id=c.tenant_id AND l.customer_id=c.customer_id), c.created_at),
        COALESCE((SELECT max(GREATEST(k.created_at, COALESCE(k.last_used_at, k.created_at))) FROM web_user_keys k
                  WHERE k.tenant_id=c.tenant_id AND k.customer_id=c.customer_id), c.created_at),
        COALESCE((SELECT max(s.last_used_at) FROM web_sessions s WHERE s.tenant_id=c.tenant_id AND s.customer_id=c.customer_id), c.created_at),
        COALESCE((SELECT max(GREATEST(a.created_at, COALESCE(a.last_used_at, a.created_at))) FROM web_agent_keys a
                  WHERE a.tenant_id=c.tenant_id AND a.customer_id=c.customer_id), c.created_at)) AS last_seen
) x
WHERE c.tenant_id=%s AND left(c.external_id, 4) = 'web:'
  AND EXISTS (SELECT 1 FROM web_social_links l WHERE l.tenant_id=c.tenant_id AND l.customer_id=c.customer_id)
  AND x.last_seen < %s
ORDER BY x.last_seen
LIMIT %s
"""

#: 미리보기가 세는 표 — (이름, 고객 번호로 세는 SQL). 지울 때와 같은 범위
_COUNTS: tuple[tuple[str, str], ...] = (
    ("trips", "SELECT count(*) FROM trips WHERE tenant_id=%s AND customer_id = ANY(%s)"),
    ("trip_chat_turns", "SELECT count(*) FROM trip_chat_turns t JOIN trips r ON r.trip_id=t.trip_id WHERE r.tenant_id=%s AND r.customer_id = ANY(%s)"),
    ("trip_intakes", "SELECT count(*) FROM trip_intakes WHERE tenant_id=%s AND customer_id = ANY(%s)"),
    ("customer_cases", "SELECT count(*) FROM customer_cases WHERE tenant_id=%s AND customer_id = ANY(%s)"),
    ("user_activity_events", "SELECT count(*) FROM user_activity_events WHERE tenant_id=%s AND customer_id = ANY(%s)"),
    ("place_aliases", "SELECT count(*) FROM place_aliases WHERE tenant_id=%s AND customer_id = ANY(%s)"),
    ("customer_profiles", "SELECT count(*) FROM customer_profiles WHERE tenant_id=%s AND customer_id = ANY(%s)"),
    ("web_social_links", "SELECT count(*) FROM web_social_links WHERE tenant_id=%s AND customer_id = ANY(%s)"),
    ("web_sessions", "SELECT count(*) FROM web_sessions WHERE tenant_id=%s AND customer_id = ANY(%s)"),
    ("web_user_keys", "SELECT count(*) FROM web_user_keys WHERE tenant_id=%s AND customer_id = ANY(%s)"),
    ("web_agent_keys", "SELECT count(*) FROM web_agent_keys WHERE tenant_id=%s AND customer_id = ANY(%s)"),
)
#: 사용자 번호로 바로 지우는 표 — 여행 삭제가 못 지우는 것들(순서 무관, 모두 사용자 행을 가리킨다)
_BY_CUSTOMER: tuple[str, ...] = ("user_activity_events", "place_aliases", "customer_profiles", "telegram_link_codes",
                                 "web_oauth_states", "web_oauth_tickets", "web_social_links", "web_sessions", "web_user_keys", "web_agent_keys")


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def mode() -> str:
    """지금 정리 모드 — 관리 화면이 바꾼 값(`retention.purge_mode`)이 있으면 그것, 없으면 가드레일 기본값."""
    from app.domains.travel_ops.modules.web_account import web_guard
    from app.core.settings import get_settings

    try:
        return str(web_guard.values(get_settings().tenant_id)["retention.purge_mode"])
    except Exception:                                   # noqa: BLE001 — 값을 못 읽으면 가장 안전한 쪽(지우지 않고 세기만)
        return "dry_run"


def erase_customer(conn, tenant_id: str, customer_id: UUID) -> dict[str, int]:
    """사용자 한 명의 자료를 지운다(회원 · 게스트 공통) — 호출자가 `with conn.transaction():` 으로 감싼다. 센 것을 돌려준다.

    `kept` = 1 이면 사용자 행을 가리키는 다른 기록이 있어 행만 남았다(식별 정보는 지워졌다)."""
    done = {"trips": 0, "cases": 0, "customer": 0, "kept": 0}
    with conn.cursor() as cur:
        cur.execute("SELECT trip_id FROM trips WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))
        trips = [row[0] for row in cur.fetchall()]
    for trip_id in trips:
        if trip_delete.delete_trip(conn, tenant_id=tenant_id, customer_id=customer_id, trip_id=trip_id) is not None:
            done["trips"] += 1
    with conn.cursor() as cur:
        cur.execute("DELETE FROM trip_intakes WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))      # 여행이 안 된 접수(자식은 CASCADE)
        for table in _BY_CUSTOMER:
            cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))
        if get_guardrails().get("retention.case_follows_trip"):
            cur.execute("SELECT case_id FROM customer_cases WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))
            ids = [row[0] for row in cur.fetchall()]
            done["cases"] = trip_delete.purge_cases(conn, tenant_id=tenant_id, case_ids=ids)["customer_cases"]
        try:
            with conn.transaction():                       # 저장점 — 가리키는 기록이 있으면 이 삭제만 되돌린다
                cur.execute("DELETE FROM customers WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))
            done["customer"] = cur.rowcount
        except ForeignKeyViolation:
            done["kept"] = 1
    return done


def candidates(conn, tenant_id: str, now: datetime | None = None, *, limit: int | None = None) -> list[UUID]:
    days = retention.effective(conn, tenant_id)["member_idle_days"]
    cutoff = _now(now) - timedelta(days=days)
    with conn.cursor() as cur:
        cur.execute(_CANDIDATES, (tenant_id, cutoff, limit or int(get_guardrails().get("retention.purge_batch"))))
        return [row[0] for row in cur.fetchall()]


def preview(conn, tenant_id: str, ids: list[UUID]) -> dict[str, int]:
    """이 회원들을 지우면 표별로 몇 줄이 지워지나 — **아무것도 지우지 않고** 센다."""
    out: dict[str, int] = {"members": len(ids)}
    if not ids:
        return {**out, **{name: 0 for name, _sql in _COUNTS}}
    with conn.cursor() as cur:
        for name, sql in _COUNTS:
            cur.execute(sql, (tenant_id, ids))
            out[name] = int(cur.fetchone()[0])
    return out


def run(conn, tenant_id: str, now: datetime | None = None) -> dict[str, Any]:
    """정리 작업 한 번 — 모드에 따라 아무것도 안 하거나(off) 세기만 하거나(dry_run) 지운다(on). `dry_run` · `on` 은 `retention_runs` 에 한 줄을 남긴다."""
    current = mode()
    if current == "off":
        return {"skipped": "off"}
    ids = candidates(conn, tenant_id, now)
    if current != "on":
        counts = preview(conn, tenant_id, ids)
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO retention_runs (tenant_id, mode, counts) VALUES (%s,'dry_run',%s)", (tenant_id, Json(counts)))
        return {"mode": "dry_run", "would_delete": counts}
    totals = {"members": len(ids), "trips": 0, "cases": 0, "customers_deleted": 0, "customers_kept": 0, "errored": 0}
    for customer_id in ids:
        try:
            with conn.transaction():
                done = erase_customer(conn, tenant_id, customer_id)
        except Exception:                                  # noqa: BLE001 — 한 명이 실패해도 나머지는 계속한다(센다)
            totals["errored"] += 1
            continue
        totals["trips"] += done["trips"]
        totals["cases"] += done["cases"]
        totals["customers_deleted"] += done["customer"]
        totals["customers_kept"] += done["kept"]
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO retention_runs (tenant_id, mode, counts) VALUES (%s,'on',%s)", (tenant_id, Json(totals)))
    return {"mode": "on", **totals}


def last_runs(conn, tenant_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT run_id, mode, started_at, counts FROM retention_runs WHERE tenant_id=%s ORDER BY run_id DESC LIMIT %s", (tenant_id, limit))
        return [{"run_id": r[0], "mode": r[1], "at": r[2].isoformat(), "counts": r[3]} for r in cur.fetchall()]


__all__ = ["candidates", "erase_customer", "last_runs", "mode", "preview", "run"]
