"""선택 동의 → 제한된 기여량의 합성 후보 → 사람 검토 → 내보내기.

운영 계약: wiki/operations/service-improvement.md. 기계 검사는 익명성 심의를 대신하지 않는다.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from app.core.settings import get_guardrails
from app.domains.travel_ops.components.settings_hook import operator_setting

from . import consents, retention

FIELDS = ("party_bucket", "days_bucket", "items_per_day_bucket")
DOMAINS = (("1", "2-4", "5+"), ("1", "2-3", "4+"), ("1-3", "4-6", "7+"))
BINS = tuple(itertools.product(*DOMAINS))
REVIEW_FIELDS = ("lawful_basis_sha256", "reidentification_sha256", "utility_sha256")


class ImprovementError(ValueError):
    """진행 조건을 만족하지 못하면 원본을 변경하지 않고 중단한다."""


def policy() -> dict[str, int]:
    spec = get_guardrails().get("service_improvement")
    out = {key: int(spec[key]) for key in ("max_generations", "candidate_days", "approved_days", "review_days",
                                         "synthetic_rows", "noisy_min_count")}
    if any(value < 1 for value in out.values()) or out["max_generations"] > 4:
        raise ImprovementError("invalid_policy")
    # 웹에 명시한 기간을 설정만 바꿔 늘릴 수 없다.
    if out["candidate_days"] > 7 or out["approved_days"] > 1825 or out["review_days"] > 365:
        raise ImprovementError("retention_exceeds_terms")
    return out


def lock(conn, tenant_id: str) -> None:
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("service-improvement:" + tenant_id,))


def invalidate_pending(conn, tenant_id: str) -> int:
    """동의 철회와 같은 트랜잭션. 연결표가 없으므로 tenant의 대기 후보를 모두 폐기한다."""
    return conn.execute("DELETE FROM service_improvement_batches WHERE tenant_id=%s AND state='pending'",
                        (tenant_id,)).rowcount


def _geometric() -> int:
    count = 0
    while secrets.randbits(1):
        count += 1
    return count


def bucket(party: int, days: int, items: int) -> tuple[str, str, str]:
    if min(party, days, items) < 1:
        raise ImprovementError("invalid_features")
    return ("1" if party == 1 else "2-4" if party <= 4 else "5+",
            "1" if days == 1 else "2-3" if days <= 3 else "4+",
            "1-3" if items <= 3 * days else "4-6" if items <= 6 * days else "7+")


def synthesize(features, *, rows: int, noisy_min_count: int) -> dict[str, Any] | None:
    """고정된 27개 구간 모두에 독립적인 기하분포 차 잡음. 실제 건수에 따른 분기를 출력하지 않는다."""
    counts = dict.fromkeys(BINS, 0)
    for features_one in features:
        counts[bucket(*features_one)] += 1
    weights = [max(0, counts[key] + _geometric() - _geometric()) for key in BINS]
    total = sum(weights)
    if total < noisy_min_count:
        return None
    cumulative = list(itertools.accumulate(weights))
    generated = []
    for _ in range(rows):
        draw = secrets.randbelow(total)
        index = next(i for i, bound in enumerate(cumulative) if draw < bound)
        generated.append(dict(zip(FIELDS, BINS[index], strict=True)))
    payload = {"schema": "trip_structure_v1", "rows": generated}
    validate(payload, expected_rows=rows)
    return payload


def validate(payload: Any, *, expected_rows: int) -> None:
    if not isinstance(payload, dict) or set(payload) != {"schema", "rows"} or payload["schema"] != "trip_structure_v1":
        raise ImprovementError("invalid_schema")
    rows = payload["rows"]
    if not isinstance(rows, list) or len(rows) != expected_rows:
        raise ImprovementError("invalid_rows")
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise ImprovementError("forbidden_fields")
        if any(row[field] not in domain for field, domain in zip(FIELDS, DOMAINS, strict=True)):
            raise ImprovementError("invalid_bucket")


def digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _features(conn, tenant_id: str, version: str, now: datetime):
    # 사용 직후의 웹 이용자만 대상으로 좁힌다. 회원/게스트 어느 쪽도 파기 기한을 넘지 않는다.
    # 원문/좌표/이름을 SELECT하지 않고 최신 여행의 수치만 읽는다. LIMIT 없음, 사용자당 최대 한 기여.
    guest_hours = operator_setting(tenant_id, "web.guest_idle_hours")
    if guest_hours is None:
        guest_hours = get_guardrails().get("web_guard.guest_idle_hours")
    hours = min(int(guest_hours),
                retention.effective(conn, tenant_id)["member_idle_days"] * 24)
    return conn.execute("""
        WITH eligible AS (
            SELECT c.customer_id FROM customers c
            WHERE c.tenant_id=%s AND EXISTS (
                SELECT 1 FROM web_sessions s WHERE s.tenant_id=c.tenant_id AND s.customer_id=c.customer_id
                AND s.revoked_at IS NULL AND s.last_used_at > %s)
            AND (SELECT count(*) FROM consent_current cc
                 WHERE cc.tenant_id=c.tenant_id AND cc.user_id=c.customer_id
                 AND cc.code IN ('service_terms','privacy','service_improvement')
                 AND cc.agreed AND cc.terms_version=%s) = 3
        ), latest AS (
            SELECT DISTINCT ON (t.customer_id) t.trip_id, t.tenant_id, t.latest_version, t.party_size
            FROM trips t JOIN eligible e ON e.customer_id=t.customer_id
            WHERE t.tenant_id=%s ORDER BY t.customer_id, t.created_at DESC, t.trip_id DESC
        )
        SELECT t.party_size, count(DISTINCT (i.starts_at AT TIME ZONE 'Asia/Seoul')::date), count(*)
        FROM latest t JOIN itinerary_items i ON i.trip_id=t.trip_id AND i.tenant_id=t.tenant_id AND i.version=t.latest_version
        WHERE t.party_size > 0 GROUP BY t.trip_id, t.party_size
    """, (tenant_id, now - timedelta(hours=hours), version, tenant_id)).fetchall()


def prepare(conn, tenant_id: str, *, now: datetime | None = None) -> dict[str, str]:
    """예산을 먼저 확정한다. 실패해도 환불하지 않도록 독립적인 autocommit 연결이 필요하다."""
    if not conn.autocommit or conn.info.transaction_status != TransactionStatus.IDLE:
        raise ImprovementError("dedicated_autocommit_connection_required")
    rules, now = policy(), now or datetime.now(timezone.utc)
    with conn.transaction():
        lock(conn, tenant_id)
        conn.execute("INSERT INTO service_improvement_budget (tenant_id) VALUES (%s) ON CONFLICT DO NOTHING", (tenant_id,))
        reserved = conn.execute("UPDATE service_improvement_budget SET generations=generations+1 "
                                "WHERE tenant_id=%s AND generations < %s RETURNING generations",
                                (tenant_id, rules["max_generations"])).fetchone()
        if reserved is None:
            raise ImprovementError("privacy_budget_exhausted")
    with conn.transaction():
        lock(conn, tenant_id)
        version = consents.current_version(conn, tenant_id)
        payload = synthesize(_features(conn, tenant_id, version, now), rows=rules["synthetic_rows"],
                             noisy_min_count=rules["noisy_min_count"])
        if payload is None:
            return {"status": "insufficient_noisy_support"}
        batch_id = str(uuid4())
        sha = digest(payload)
        conn.execute("INSERT INTO service_improvement_batches "
                     "(batch_id,tenant_id,terms_version,payload,payload_sha256,created_at,expires_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                     (batch_id, tenant_id, version, Jsonb(payload), sha, now, now + timedelta(days=rules["candidate_days"])))
    return {"status": "pending", "batch_id": batch_id, "payload_sha256": sha, "terms_version": version}


def approve(conn, tenant_id: str, batch_id: str, *, expected_sha256: str, review: dict[str, str],
            now: datetime | None = None) -> None:
    rules, now = policy(), now or datetime.now(timezone.utc)
    if set(review) != {"reviewer", *REVIEW_FIELDS} or not review.get("reviewer", "").strip() or len(review["reviewer"]) > 120:
        raise ImprovementError("review_evidence_required")
    if any(not consents._SHA.fullmatch(review[key]) or review[key] == "0" * 64 for key in REVIEW_FIELDS):
        raise ImprovementError("review_evidence_required")
    with conn.transaction():
        lock(conn, tenant_id)
        row = conn.execute("SELECT payload,payload_sha256,terms_version,created_at,expires_at FROM service_improvement_batches "
                           "WHERE tenant_id=%s AND batch_id=%s FOR UPDATE", (tenant_id, batch_id)).fetchone()
        if row is None or row[4] <= now:
            raise ImprovementError("candidate_missing_or_expired")
        payload, sha, version, created, _ = row
        if sha != expected_sha256 or digest(payload) != sha or version != consents.current_version(conn, tenant_id):
            raise ImprovementError("review_scope_changed")
        validate(payload, expected_rows=rules["synthetic_rows"])
        expires = created + timedelta(days=rules["approved_days"])
        if now >= expires:
            raise ImprovementError("candidate_expired")
        conn.execute("UPDATE service_improvement_batches SET state='approved',review=%s,expires_at=%s,review_due_at=%s "
                     "WHERE tenant_id=%s AND batch_id=%s", (Jsonb({**review, "reviewed_at": now.isoformat(), "payload_sha256": sha}),
                     expires, min(expires, now + timedelta(days=rules["review_days"])), tenant_id, batch_id))


def export(conn, tenant_id: str, batch_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    with conn.transaction():
        lock(conn, tenant_id)
        row = conn.execute("SELECT payload,payload_sha256,terms_version,state,expires_at,review_due_at "
                           "FROM service_improvement_batches WHERE tenant_id=%s AND batch_id=%s",
                           (tenant_id, batch_id)).fetchone()
        if row is None or row[3] != "approved" or row[4] <= now or row[5] <= now:
            raise ImprovementError("approved_current_review_required")
        if row[2] != consents.current_version(conn, tenant_id) or digest(row[0]) != row[1]:
            raise ImprovementError("export_scope_changed")
        validate(row[0], expected_rows=policy()["synthetic_rows"])
        return row[0]


def prune_expired(conn, tenant_id: str, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    with conn.transaction():
        lock(conn, tenant_id)
        return conn.execute("DELETE FROM service_improvement_batches WHERE tenant_id=%s AND expires_at <= %s",
                            (tenant_id, now)).rowcount
