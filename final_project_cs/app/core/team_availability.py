"""Operational plugin availability failures, separate from invalid customer input."""
from __future__ import annotations


class TeamUnavailable(RuntimeError):
    code = "team_unavailable"

    def __init__(self, team_id: str, reason: str) -> None:
        self.team_id = team_id
        self.reason = reason
        super().__init__(f"team '{team_id}' is unavailable: {reason}")


class TeamContractViolation(RuntimeError):
    """A registered or remote Team failed its execution contract."""


def unavailable_payload(exc: TeamUnavailable) -> dict:
    """Public domain-neutral error body; HTTP/SSE adapters choose their envelope."""
    return {"error": {
        "code": exc.code, "message": "요청한 업무의 담당 기능을 사용할 수 없습니다",
        "team_id": exc.team_id, "reason": exc.reason,
        "retryable": exc.reason == "remote_unavailable",
    }}

