"""멱등키의 요청 식별자 — 2026-08-31 추가.

`request_id_for_case` 가 원래 요청 식별자를 버리고 Case id 로만 키를 만들어도
전체 424개가 전부 통과했다. 그러면 같은 Case 안의 서로 다른 요청이 같은 키를 갖고,
두 번째 요청이 중복으로 취급돼 조용히 사라진다.
"""

from __future__ import annotations

from uuid import uuid4

from app.core.idempotency import idempotency_key, request_id_for_case


def test_request_id_is_preferred_over_case_id() -> None:
    case_id = uuid4()
    case = {"case_id": case_id, "state_json": {"request_id": "REQ-1"}}
    assert request_id_for_case(case) == "REQ-1"
    assert request_id_for_case(case) != str(case_id)


def test_two_requests_on_one_case_get_different_keys() -> None:
    """같은 Case 라도 요청이 다르면 키가 달라야 한다."""
    case_id = uuid4()
    first = request_id_for_case({"case_id": case_id, "state_json": {"request_id": "REQ-1"}})
    second = request_id_for_case({"case_id": case_id, "state_json": {"request_id": "REQ-2"}})
    assert first != second
    key = {
        "tenant_id": "t1", "action_type": "refund.issue", "business_subject": "ORD-1",
    }
    assert idempotency_key(request_id=first, **key) != idempotency_key(request_id=second, **key)


def test_case_id_is_used_only_when_request_id_is_absent() -> None:
    """옛 Case 를 위한 fallback 이다. 있는 요청 식별자를 덮지 않는다."""
    case_id = uuid4()
    assert request_id_for_case({"case_id": case_id, "state_json": {}}) == str(case_id)
    assert request_id_for_case({"case_id": case_id, "state_json": None}) == str(case_id)
