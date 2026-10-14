"""DB-backed, tenant-isolated source selection; no provider budget is expanded."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb

from app.application import admin_service


def configuration() -> dict:
    return yaml.safe_load((Path(__file__).resolve().parents[2] / "config/operations-policy.yaml").read_text(encoding="utf-8"))


class SourcePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    allow_paid: bool = Field(default_factory=lambda: configuration()["source_policy"]["allow_paid"])
    daily_paid_cap: int = Field(default_factory=lambda: configuration()["source_policy"]["daily_paid_cap"], ge=0)
    trip_paid_cap: int = Field(default_factory=lambda: configuration()["source_policy"]["trip_paid_cap"], ge=0)
    check_interval_seconds: int = Field(default_factory=lambda: configuration()["source_policy"]["check_interval_seconds"], ge=1)

    def validate_bounds(self) -> None:
        for name, (low, high) in configuration()["bounds"].items():
            if not low <= getattr(self, name) <= high:
                raise ValueError("policy_out_of_range")
        if self.trip_paid_cap > self.daily_paid_cap:
            raise ValueError("trip_cap_exceeds_daily_cap")


def read(conn, tenant: str) -> dict:
    row = conn.execute("SELECT revision,value FROM ops_source_policy WHERE tenant_id=%s", (tenant,)).fetchone()
    value = SourcePolicy.model_validate(row[1] if row else configuration()["source_policy"])
    value.validate_bounds()
    return {"revision": row[0] if row else 0, "policy": value.model_dump(), "bounds": configuration()["bounds"], "free_first": True}


def save(conn, tenant: str, *, expected_revision: int, policy: SourcePolicy, actor: str, reason: str) -> dict:
    policy.validate_bounds()
    if not reason.strip():
        raise ValueError("reason_required")
    # Same lock as reservations: a lowering policy cannot race an old reservation.
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("source-policy:" + tenant,))
    before = read(conn, tenant)
    if before["revision"] != expected_revision:
        raise admin_service.AdminServiceError(409, " 설정이 바뀌었습니다. 현재 값을 다시 읽어 주세요.")
    after = {"revision": expected_revision + 1, "policy": policy.model_dump()}
    conn.execute("INSERT INTO ops_source_policy(tenant_id,revision,value) VALUES(%s,%s,%s) "
                 "ON CONFLICT(tenant_id) DO UPDATE SET revision=EXCLUDED.revision,value=EXCLUDED.value,updated_at=now()",
                 (tenant, after["revision"], Jsonb(after["policy"])))
    admin_service.audit(conn, tenant, actor, "source-policy", tenant, before, after, reason)
    return after


class Verdict(BaseModel):
    """Only a provider's verified verdict; raw provider content is never persisted here."""
    model_config = ConfigDict(extra="forbid", strict=True)
    status: str = Field(pattern=r"^(open|closed|unverifiable)$")
    source: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    checked_at: datetime
    valid_until: datetime
    reason: Literal['place_unmatched'] | None = None


def _verified(value: Verdict, now: datetime) -> bool:
    return (value.status != "unverifiable" and value.checked_at.tzinfo is not None
            and value.valid_until.tzinfo is not None and value.checked_at <= now < value.valid_until)


def claim_free_check(*, connection_factory, tenant, customer_id, trip_id, resource, now):
    """낮 감시의 확인 간격을 원자적으로 확보한다. 건너뜀은 정상 영업 판정이 아니다."""
    key = hashlib.sha256(('daytime:' + resource).encode()).hexdigest()
    with connection_factory() as conn, conn.transaction():
        if not conn.execute('SELECT 1 FROM trips WHERE tenant_id=%s AND customer_id=%s AND trip_id=%s',
                            (tenant, customer_id, trip_id)).fetchone():
            return False
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('source-policy:' + tenant,))
        interval = read(conn, tenant)['policy']['check_interval_seconds']
        last = conn.execute('SELECT checked_at FROM ops_lookup_checks WHERE tenant_id=%s AND trip_id=%s AND resource_hash=%s',
                            (tenant, trip_id, key)).fetchone()
        if last and (now-last[0]).total_seconds() < interval:
            return False
        conn.execute('INSERT INTO ops_lookup_checks VALUES(%s,%s,%s,%s) ON CONFLICT(tenant_id,trip_id,resource_hash) '
                     'DO UPDATE SET checked_at=EXCLUDED.checked_at', (tenant, trip_id, key, now))
    return True


def _select(*, connection_factory, tenant: str, customer_id: UUID, trip_id: UUID, resource: str,
           free: Callable[[], Verdict], paid: Callable[[], Verdict] | None = None,
           provider_reserve: Callable[[], bool] | None = None, paid_provider: str = "google",
           context: str = "daytime", now: datetime | None = None) -> dict:
    """Read-only adapters run outside DB transactions. Reserve before every paid attempt."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("aware_time_required")
    # Scope is verified before any external lookup, including the free adapter.
    try:
        with connection_factory() as conn:
            if not conn.execute("SELECT 1 FROM trips WHERE tenant_id=%s AND customer_id=%s AND trip_id=%s", (tenant, customer_id, trip_id)).fetchone():
                return {"status": "unverifiable", "reason": "trip_not_owned", "paid_attempted": False}
    except Exception:
        return {"status": "unverifiable", "reason": "ownership_unavailable", "paid_attempted": False}
    unknown = {"status": "unverifiable", "reason": "free_unverifiable", "paid_attempted": False}
    try:
        value = free()
        if _verified(value, now):
            return {**value.model_dump(mode="json"), "reason": "verified_free", "paid_attempted": False}
    except Exception:
        unknown["reason"] = "free_lookup_failed"
    try:
        with connection_factory() as conn, conn.transaction():
            rules = read(conn, tenant)
    except Exception:
        return {**unknown, "reason": "policy_unavailable"}
    unknown["policy_revision"] = rules["revision"]
    policy = SourcePolicy.model_validate(rules["policy"])
    if not policy.allow_paid or paid is None or provider_reserve is None:
        return unknown
    local = now.astimezone(ZoneInfo("Asia/Seoul"))
    if paid_provider == "google" and (context != "dawn" or not 3 <= local.hour < 8):
        return {**unknown, "reason": "paid_window_closed"}
    key = hashlib.sha256(resource.encode()).hexdigest()
    try:
        with connection_factory() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("source-policy:" + tenant,))
            rules = read(conn, tenant)
            policy = SourcePolicy.model_validate(rules["policy"])
            unknown["policy_revision"] = rules["revision"]
            if not policy.allow_paid:
                return unknown
            last = conn.execute("SELECT checked_at FROM ops_lookup_checks WHERE tenant_id=%s AND trip_id=%s AND resource_hash=%s",
                                (tenant, trip_id, key)).fetchone()
            if last and (now - last[0]).total_seconds() < policy.check_interval_seconds:
                return {**unknown, "reason": "check_interval"}
            rows = conn.execute("SELECT trip_id,used FROM ops_lookup_usage WHERE tenant_id=%s AND day=%s", (tenant, local.date())).fetchall()
            if sum(r[1] for r in rows) >= policy.daily_paid_cap or sum(r[1] for r in rows if str(r[0]) == str(trip_id)) >= policy.trip_paid_cap:
                return {**unknown, "reason": "budget_exhausted"}
            conn.execute("INSERT INTO ops_lookup_usage(tenant_id,day,trip_id,used) VALUES(%s,%s,%s,1) "
                         "ON CONFLICT(tenant_id,day,trip_id) DO UPDATE SET used=ops_lookup_usage.used+1", (tenant, local.date(), trip_id))
            conn.execute("INSERT INTO ops_lookup_checks VALUES(%s,%s,%s,%s) ON CONFLICT(tenant_id,trip_id,resource_hash) "
                         "DO UPDATE SET checked_at=EXCLUDED.checked_at", (tenant, trip_id, key, now))
        if not provider_reserve():
            return {**unknown, "reason": "provider_budget_exhausted"}
    except Exception:
        return {**unknown, "reason": "reservation_failed"}
    try:
        value = paid()
        if _verified(value, now):
            return {**value.model_dump(mode="json"), "reason": "verified_paid", "paid_attempted": True, "policy_revision": rules["revision"]}
        return {**unknown, "reason": value.reason or "paid_unverifiable", "paid_attempted": True}
    except Exception:
        return {**unknown, "reason": "paid_lookup_failed", "paid_attempted": True}


def select(*, connection_factory, tenant: str, customer_id: UUID, trip_id: UUID, resource: str,
           free: Callable[[], Verdict], paid: Callable[[], Verdict] | None = None,
           provider_reserve: Callable[[], bool] | None = None, paid_provider: str = "google",
           context: str = "daytime", now: datetime | None = None,
           request_id: UUID | None = None, case_id: UUID | None = None, spool=None) -> dict:
    result = _select(connection_factory=connection_factory, tenant=tenant, customer_id=customer_id, trip_id=trip_id,
                     resource=resource, free=free, paid=paid, provider_reserve=provider_reserve,
                     paid_provider=paid_provider, context=context, now=now)
    if result["status"] == "unverifiable" and result["reason"] not in ("trip_not_owned", "ownership_unavailable"):
        from app.application.operations_diagnostics import Event, deployment_version, record
        event = Event(tenant_id=tenant, customer_id=customer_id, trip_id=trip_id, request_id=request_id, case_id=case_id,
                      kind="place_unmatched" if result['reason'] == 'place_unmatched' else "processing_error",
                      code=result["reason"].upper(), deployment=deployment_version(),
                      policy_version="source-" + str(result.get("policy_revision", "unrecorded")))
        result["diagnostic"] = record(event, connection_factory=connection_factory, spool=spool)
    return result
