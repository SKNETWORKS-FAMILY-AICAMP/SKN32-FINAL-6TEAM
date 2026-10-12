"""Structured diagnostics with idempotent DB aggregation and a bounded durable spool."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.types.json import Jsonb

from app.application.operations_policy import configuration
from app.core.redaction import mask_json

log = logging.getLogger(__name__)


class OwnershipError(ValueError):
    pass


def deployment_version() -> str:
    import re
    value = os.environ.get("ACOP_DEPLOYMENT_VERSION", "unrecorded")
    return value if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value) else "unrecorded"


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    event_id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    kind: Literal["place_unmatched", "processing_error", "suggestion"]
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,79}$")
    deployment: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,80}$")
    policy_version: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,80}$")
    conditions: list[str] = Field(default_factory=list, max_length=12)
    customer_id: UUID | None = None
    trip_id: UUID | None = None
    case_id: UUID | None = None
    request_id: UUID | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("conditions")
    @classmethod
    def code_only(cls, values):
        import re
        if any(not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", v) for v in values):
            raise ValueError("condition_codes_only")
        return sorted(set(values))

    @field_validator("occurred_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("aware_time_required")
        return value

    def fingerprint(self) -> str:
        parts = [self.kind, self.code, self.deployment, self.policy_version, self.conditions]
        return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()


def persist(conn, event: Event) -> bool:
    """Caller commits; retries with identical IDs never increase occurrence counts."""
    fingerprint = event.fingerprint()
    expires = event.occurred_at + timedelta(days=configuration()["diagnostics"]["retention_days"])
    if expires <= datetime.now(UTC):
        return False
    if event.customer_id and not conn.execute("SELECT 1 FROM customers WHERE tenant_id=%s AND customer_id=%s "
                                             "AND external_id NOT LIKE 'erased:%%'", (event.tenant_id, event.customer_id)).fetchone():
        raise OwnershipError("diagnostic_customer_not_owned")
    if event.trip_id and not conn.execute("SELECT 1 FROM trips WHERE tenant_id=%s AND trip_id=%s AND (%s::uuid IS NULL OR customer_id=%s)",
                                         (event.tenant_id, event.trip_id, event.customer_id, event.customer_id)).fetchone():
        raise OwnershipError("diagnostic_trip_not_owned")
    if event.case_id and not conn.execute("SELECT 1 FROM customer_cases WHERE tenant_id=%s AND case_id=%s AND (%s::uuid IS NULL OR customer_id=%s)",
                                         (event.tenant_id, event.case_id, event.customer_id, event.customer_id)).fetchone():
        raise OwnershipError("diagnostic_case_not_owned")
    inserted = conn.execute("INSERT INTO ops_diagnostic_events(tenant_id,event_id,fingerprint,customer_id,trip_id,case_id,request_id,occurred_at,expires_at) "
                            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING event_id",
                            (event.tenant_id, event.event_id, fingerprint, event.customer_id, event.trip_id,
                             event.case_id, event.request_id, event.occurred_at, expires)).fetchone()
    if not inserted:
        return False
    conn.execute("INSERT INTO ops_defects(tenant_id,fingerprint,kind,code,deployment,policy_version,conditions,occurrences,first_at,last_at) "
                 "VALUES(%s,%s,%s,%s,%s,%s,%s,1,%s,%s) ON CONFLICT(tenant_id,fingerprint) DO UPDATE "
                 "SET occurrences=ops_defects.occurrences+1,first_at=LEAST(ops_defects.first_at,EXCLUDED.first_at),last_at=GREATEST(ops_defects.last_at,EXCLUDED.last_at)",
                 (event.tenant_id, fingerprint, event.kind, event.code, event.deployment, event.policy_version,
                  Jsonb(mask_json(event.conditions)), event.occurred_at, event.occurred_at))
    if event.customer_id:
        conn.execute("INSERT INTO ops_defect_customers VALUES(%s,%s,%s,%s,%s) ON CONFLICT(tenant_id,fingerprint,customer_id) "
                     "DO UPDATE SET last_at=GREATEST(ops_defect_customers.last_at,EXCLUDED.last_at),expires_at=GREATEST(ops_defect_customers.expires_at,EXCLUDED.expires_at)",
                     (event.tenant_id, fingerprint, event.customer_id, event.occurred_at, expires))
    return True


class Spool:
    def __init__(self, path: Path | None = None, *, max_bytes: int | None = None, max_events: int | None = None):
        rules = configuration()["diagnostics"]
        self.path = path or Path(os.environ.get("ACOP_DIAGNOSTIC_SPOOL", "var/operations-diagnostics/pending.sqlite3"))
        self.max_bytes = rules["spool_max_bytes"] if max_bytes is None else max_bytes
        self.max_events = rules["spool_max_events"] if max_events is None else max_events

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            # 영속 볼륨 안에서도 다른 사용자에게 고객 UUID 대기 기록을 공개하지 않는다.
            self.path.parent.chmod(0o700)
            fd = os.open(self.path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                os.fchmod(fd, 0o600)
            finally:
                os.close(fd)
        conn = sqlite3.connect(self.path, timeout=1)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("CREATE TABLE IF NOT EXISTS pending (tenant TEXT,event_id TEXT,payload TEXT,PRIMARY KEY(tenant,event_id))")
        conn.execute("CREATE TABLE IF NOT EXISTS metrics (name TEXT PRIMARY KEY,value INTEGER)")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def enqueue(self, event: Event) -> str:
        payload = json.dumps(mask_json(event.model_dump(mode="json")), ensure_ascii=False)
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM pending WHERE tenant=? AND event_id=?", (event.tenant_id, str(event.event_id))).fetchone():
                return "spooled"
            count, size = conn.execute("SELECT count(*),COALESCE(sum(length(CAST(payload AS BLOB))),0) FROM pending").fetchone()
            if count >= self.max_events or size + len(payload.encode()) > self.max_bytes:
                conn.execute("INSERT INTO metrics VALUES('lost',1) ON CONFLICT(name) DO UPDATE SET value=value+1")
                return "collection_degraded"
            conn.execute("INSERT INTO pending VALUES(?,?,?)", (event.tenant_id, str(event.event_id), payload))
        return "spooled"

    def snapshot(self) -> dict:
        with self.connect() as conn:
            count, size = conn.execute("SELECT count(*),COALESCE(sum(length(CAST(payload AS BLOB))),0) FROM pending").fetchone()
            lost = conn.execute("SELECT value FROM metrics WHERE name='lost'").fetchone()
        return {"pending": count, "bytes": size, "lost": lost[0] if lost else 0}

    def replay(self, connection_factory, *, limit: int = 100) -> dict:
        sent = failed = expired = rejected = 0
        with self.connect() as queue:
            rows = queue.execute("SELECT tenant,event_id,payload FROM pending ORDER BY rowid LIMIT ?", (limit,)).fetchall()
        for tenant, identity, payload in rows:
            try:
                event = Event.model_validate_json(payload)
                if event.occurred_at + timedelta(days=configuration()["diagnostics"]["retention_days"]) <= datetime.now(UTC):
                    expired += 1
                else:
                    try:
                        with connection_factory() as conn, conn.transaction():
                            persist(conn, event)
                    except OwnershipError:
                        # A deleted customer/trip must not be resurrected from a local spool.
                        rejected += 1
                with self.connect() as queue:
                    queue.execute("DELETE FROM pending WHERE tenant=? AND event_id=?", (tenant, identity))
                sent += 1
            except Exception:
                failed += 1
        return {"processed": sent, "failed": failed, "expired": expired, "rejected": rejected, **self.snapshot()}


def record(event: Event, *, connection_factory, spool: Spool | None = None) -> dict:
    if event.occurred_at + timedelta(days=configuration()["diagnostics"]["retention_days"]) <= datetime.now(UTC):
        return {"status": "expired", "event_id": str(event.event_id)}
    try:
        with connection_factory() as conn, conn.transaction():
            persist(conn, event)
        return {"status": "stored", "event_id": str(event.event_id)}
    except OwnershipError:
        return {"status": "rejected", "event_id": str(event.event_id)}
    except Exception:
        try:
            status = (spool or Spool()).enqueue(event)
        except Exception:
            status = "collection_degraded"
        # Deliberately no exception text, customer input or credentials in logs.
        log.warning("diagnostic_collection status=%s event_id=%s", status, event.event_id)
        return {"status": status, "event_id": str(event.event_id)}


def execution_recorder(*, connection_factory, policy_version: str, spool: Spool | None = None):
    """실행 경계에 주입하는 콜백. 원문 대신 고정 코드와 소유 객체 UUID만 받는다."""
    codes = {"classification_failed": "CLASSIFICATION_FAILED", "source_failed": "SOURCE_FAILED",
             "error": "EXECUTION_ERROR", "retry": "RETRY_DEFERRED", "team_timeout": "TEAM_TIMEOUT",
             "team_exception": "TEAM_EXCEPTION", "state_conflict": "STATE_CONFLICT",
             "routing_failed": "ROUTING_FAILED", "team_unavailable": "TEAM_UNAVAILABLE"}
    conditions = {"plan_schema_invalid", "plan_version_stale", "plan_input_invalid", "plan_coverage_invalid",
                  "plan_team_forbidden", "plan_order_invalid", "plan_dependencies_invalid", "plan_tools_forbidden",
                  "plan_budget_exceeded", "plan_input_stale", "plan_input_budget_exceeded", "plan_provider_failed",
                  "dependency_deferred", "deadline", "fatal_source_failure", "ToolBudgetExceeded"}

    def collect(payload: dict) -> dict:
        code = codes.get(payload.get("code"))
        if code is None:
            return {"status": "ignored"}  # 복구 관측을 새 오류 발생으로 세지 않는다.
        try:
            identifiers = {name: UUID(str(payload[name])) if payload.get(name) else None
                           for name in ("customer_id", "trip_id", "case_id", "request_id")}
            error = payload.get("error_code")
            event = Event(tenant_id=payload["tenant_id"], kind="processing_error", code=code,
                          deployment=deployment_version(), policy_version=policy_version,
                          conditions=[error.upper()] if error in conditions else [], **identifiers)
        except (ValueError, TypeError, KeyError):
            log.error("diagnostic_execution status=rejected code=INVALID_DIAGNOSTIC")
            return {"status": "rejected"}
        result = record(event, connection_factory=connection_factory, spool=spool)
        level = logging.ERROR if result["status"] == "collection_degraded" else logging.INFO
        log.log(level, "diagnostic_execution status=%s code=%s event_id=%s",
                result["status"], code, event.event_id)
        return result

    return collect


def listing(conn, tenant: str, *, limit: int = 50, before: tuple[datetime, str] | None = None) -> dict:
    limit = max(1, min(limit, configuration()["diagnostics"]["page_size"]))
    condition, args = "", [tenant]
    if before:
        condition = " AND (d.last_at,d.fingerprint)<(%s,%s)"
        args.extend(before)
    args.append(limit + 1)
    rows = conn.execute("SELECT d.fingerprint,d.kind,d.code,d.deployment,d.policy_version,d.conditions,d.occurrences,d.first_at,d.last_at,d.resolved_version,"
                        "(SELECT count(*) FROM ops_defect_customers c WHERE c.tenant_id=d.tenant_id AND c.fingerprint=d.fingerprint AND c.expires_at>now()) "
                        "FROM ops_defects d WHERE d.tenant_id=%s" + condition + " ORDER BY d.last_at DESC,d.fingerprint DESC LIMIT %s", tuple(args)).fetchall()
    names = ("fingerprint", "kind", "code", "deployment", "policy_version", "conditions", "occurrences", "first_at", "last_at", "resolved_version", "affected_customers")
    page = [dict(zip(names, row, strict=True)) for row in rows[:limit]]
    return {"items": page, "next": {"at": page[-1]["last_at"], "fingerprint": page[-1]["fingerprint"]} if len(rows) > limit else None}


def prune(conn) -> dict:
    # Counts and resolution versions stay; personal links follow their original expiry.
    return {"events": conn.execute("DELETE FROM ops_diagnostic_events WHERE expires_at<=now()").rowcount,
            "customers": conn.execute("DELETE FROM ops_defect_customers WHERE expires_at<=now()").rowcount,
            "usage": conn.execute("DELETE FROM ops_lookup_usage WHERE day<current_date-2").rowcount,
            "checks": conn.execute("DELETE FROM ops_lookup_checks WHERE checked_at<now()-interval '2 days'").rowcount}
