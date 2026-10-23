"""현재 접수 판을 잠근 뒤 식당 필수 확인을 등록·수정 확정에 반영한다."""
from __future__ import annotations

from typing import Any

from app.domains.travel_ops.components.intake import dining_review, review


class RegistrationRefused(Exception):
    def __init__(self, status: int, code: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.detail = status, code, message, detail


def confirmed_trip_id(conn: Any, tenant_id: str, intake_id: Any) -> Any:
    """require_review가 잡은 접수 잠금 안에서 다른 등록 경로의 완료도 확인한다."""
    with conn.cursor() as cur:
        cur.execute("SELECT trip_id FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND status='confirmed'",
                    (tenant_id, intake_id))
        row = cur.fetchone()
    return row[0] if row else None


def require_review(conn: Any, tenant_id: str, intake_id: Any, revision: int) -> dict[str, Any] | None:
    """호출자의 쓰기 트랜잭션 안에서 사용한다. 잠금은 실제 등록/확정이 끝날 때까지 유지해야 한다.

    이미 확정한 요청의 재시도는 기존 멱등 결과를 돌려줄 수 있게 과거 검사 실패로 막지 않는다.
    기존 metadata 없는 검사와 disabled는 하위 계약의 호환 규칙을 따른다.
    """
    state = review.intake_state(conn, tenant_id, intake_id)
    if state is None:
        raise RegistrationRefused(404, "not_found", "접수를 찾을 수 없어요")
    status, current_revision = state
    if current_revision != revision:
        raise RegistrationRefused(409, "stale_revision", "그 사이 일정이 바뀌었어요 — 최신 내용을 확인해 주세요",
                                  current_revision=current_revision)
    if status not in ("review", "confirmed"):
        raise RegistrationRefused(409, "intake_not_ready", "아직 등록할 수 없어요", intake_status=status)
    payload = review.load(conn, tenant_id, intake_id, revision)
    if status == "confirmed":
        return payload
    if payload is not None:
        payload = dining_review.refresh(conn, tenant_id, intake_id, revision, payload)
        issue = dining_review.registration_issue(payload)
        if issue is not None:
            raise RegistrationRefused(issue["status"], issue["code"], issue["message"], **issue.get("detail", {}))
    return payload
