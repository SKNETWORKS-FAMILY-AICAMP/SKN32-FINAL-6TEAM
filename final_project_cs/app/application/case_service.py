"""Persistence helpers for Controller runs and WAIT/RESUME metadata."""
from __future__ import annotations

import hashlib
import secrets

from app.core.settings import get_guardrails
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import Connection



class ActiveRunError(RuntimeError):
    pass


class ResumeTokenError(ValueError):
    pass


class ResumeTokenExpired(ResumeTokenError):
    """유효한 토큰의 대기 기간만 만료되었다."""


class ResumeRequestConflict(ValueError):
    """같은 요청 식별자를 다른 입력에 재사용했다."""


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
                "resume_token_expires_at": (
                    # ★가드레일에서 읽는다. 24 가 박혀 있어
                    #   `resume.token_ttl_hours` 를 낮춰도 아무 일이 없었다 —
                    #   보안 한도를 조인 줄 알게 되는 종류다(2026-09-03).
                    datetime.now(UTC)
                    + timedelta(hours=float(get_guardrails().get("resume.token_ttl_hours")))
                ).isoformat(),
                "resume_token_used": False, "wait_reason": wait_reason}

    def validate_resume(self, case: dict[str, Any], token: str, *, event_id: str | None = None,
                        message_hash: str | None = None) -> str | None:
        return self._validate_resume_hash(case, self.token_hash(token), event_id=event_id,
                                          message_hash=message_hash)

    def validate_customer_input(self, case: dict[str, Any], *, event_id: str | None,
                                message_hash: str | None) -> str | None:
        """고객 소유권을 확인한 내부 웹 입구만 사용한다."""
        state = case.get("state_json") or {}
        # 이미 소비한 요청의 재전송은 종료 상태에서도 같은 결과를 반환한다.
        recorded = next((r for r in state.get("resume_requests", [])
                         if event_id and r["request_id"] == event_id), None)
        if recorded is not None:
            return self._validate_resume_hash(case, recorded["token_hash"], event_id=event_id,
                                              message_hash=message_hash)
        if str(case["status"]) != "waiting_input" or state.get("wait_reason") != "customer_input":
            raise ResumeTokenError("case is not waiting for customer input")
        token_hash = state.get("resume_token_hash")
        if not token_hash:
            raise ResumeTokenError("invalid resume token metadata")
        return self._validate_resume_hash(case, token_hash, event_id=event_id,
                                          message_hash=message_hash)

    def _validate_resume_hash(self, case: dict[str, Any], token_hash: str, *,
                              event_id: str | None, message_hash: str | None) -> str | None:
        state = case.get("state_json") or {}
        for request in state.get("resume_requests", []):
            if event_id and request["request_id"] == event_id:
                if request["token_hash"] != token_hash:
                    raise ResumeTokenError("invalid resume token")
                if request.get("message_hash") != message_hash:
                    raise ResumeRequestConflict("resume request id reused with different message")
                return "idempotent"
        # 이전 판에서 만든 콜백·승인 재개 기록도 계속 읽는다.
        if event_id and state.get("last_resume_event_id") == event_id:
            if state.get("resume_token_hash") == token_hash and message_hash is None:
                return "idempotent"
            raise ResumeRequestConflict("resume request id reused with different message")
        if state.get("resume_token_used"):
            raise ResumeTokenError("resume token has already been used")
        if state.get("resume_token_hash") != token_hash:
            raise ResumeTokenError("invalid resume token")
        expires = datetime.fromisoformat(state["resume_token_expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if datetime.now(UTC) >= expires:
            raise ResumeTokenExpired("resume token expired")
        return None

