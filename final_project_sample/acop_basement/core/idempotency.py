"""Deterministic idempotency keys shared by Teams and server action writers."""
from __future__ import annotations

import hashlib
from typing import Any


def idempotency_key(*, tenant_id: str, request_id: str, action_type: str, business_subject: str) -> str:
    """Return the v5 §10-1 key: sha256(tenant_id + request_id + action_type + subject).

    ★버그사냥 2026-08-17 — 필드를 구분자 없이 그냥 이어 붙이면 서로 다른 논리
    요청이 같은 문자열이 될 수 있다: `("ab","c","d","e")` 와 `("a","bc","d","e")`
    는 둘 다 `"abcde"` 다. 필드 각각을 먼저 고정 길이 해시로 줄인 뒤 이어 붙인다
    — 어떤 필드에 어떤 문자가 들어와도 경계가 흔들리지 않는다."""
    hashed_parts = "".join(
        hashlib.sha256(part.encode("utf-8")).hexdigest()
        for part in (tenant_id, request_id, action_type, business_subject))
    return hashlib.sha256(hashed_parts.encode("utf-8")).hexdigest()


def request_id_for_case(case: dict[str, Any]) -> str:
    """Use the originating request id, with a stable case id fallback for older cases."""
    state = case.get("state_json") or {}
    return str(state.get("request_id") or case["case_id"])

