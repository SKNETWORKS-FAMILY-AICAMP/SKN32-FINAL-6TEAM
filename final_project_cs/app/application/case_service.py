"""Persistence helpers for Controller runs and WAIT/RESUME metadata."""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import Connection
from psycopg.types.json import Json

from app.core.contracts import CaseStatus, StateConflict
from app.infrastructure.db import repository


class ActiveRunError(RuntimeError):
    pass


class ResumeTokenError(ValueError):
    pass


class CaseService:
    def __init__(self, *, graph_revision: str = "controller-v1") -> None:
        self.graph_revision = graph_revision

    def start_run(self, conn: Connection, *, tenant_id: str, case_id: UUID) -> UUID:
        run_id = uuid4()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM agent_runs WHERE tenant_id=%s AND case_id=%s "
                "AND status IN ('active','running','resuming') LIMIT 1 FOR UPDATE",
                (tenant_id, case_id),
            )
            if cur.fetchone() is not None:
                raise ActiveRunError(f"active run already exists for case {case_id}")
            try:
                cur.execute(
                    "INSERT INTO agent_runs(run_id,tenant_id,case_id,graph_revision,status,started_at) "
                    "VALUES(%s,%s,%s,%s,'active',now()) RETURNING run_id",
                    (run_id, tenant_id, case_id, self.graph_revision),
                )
            except psycopg.errors.UniqueViolation as exc:
                # The SELECT above only locks an already-existing row. The
                # partial unique index is the race-safe guard for two empty
                # active-run sets, and exposes the same application failure.
                raise ActiveRunError(f"active run already exists for case {case_id}") from exc
        return run_id

    def finish_run(self, conn: Connection, run_id: UUID, status: str = "succeeded") -> None:
        with conn.cursor() as cur:
            cur.execute("UPDATE agent_runs SET status=%s, finished_at=now() WHERE run_id=%s", (status, run_id))

    def checkpoint(self, *, case_id: UUID, run_id: UUID, node_name: str, runtime_state: dict[str, Any] | None = None) -> dict[str, Any]:
        # Deliberately not a business-state snapshot. A graph checkpoint is disposable.
        return {"case_id": str(case_id), "run_id": str(run_id), "graph_revision": self.graph_revision,
                "node_name": node_name, "runtime_state": dict(runtime_state or {})}

    @staticmethod
    def new_resume_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def resume_metadata(self, token: str, wait_reason: str) -> dict[str, Any]:
        return {"resume_token_hash": self.token_hash(token),
                "resume_token_expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
                "resume_token_used": False, "wait_reason": wait_reason}

    def validate_resume(self, case: dict[str, Any], token: str, *, event_id: str | None = None) -> str | None:
        state = case.get("state_json") or {}
        if event_id and state.get("last_resume_event_id") == event_id:
            return "idempotent"
        if state.get("resume_token_used"):
            raise ResumeTokenError("resume token has already been used")
        if state.get("resume_token_hash") != self.token_hash(token):
            raise ResumeTokenError("invalid resume token")
        expires = datetime.fromisoformat(state["resume_token_expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if datetime.now(UTC) >= expires:
            raise ResumeTokenError("resume token expired")
        return None

