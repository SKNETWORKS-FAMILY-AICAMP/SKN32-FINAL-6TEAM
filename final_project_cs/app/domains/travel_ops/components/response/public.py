"""고객 완료 상태만 투영한다. 내부 근거/식별자를 공개 상태에 복사하지 않는다."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


QUESTION_STATUSES = ("answered", "needs_input", "unsupported", "failed")


def response_status(result: dict[str, Any]) -> dict[str, Any]:
    """writer 결과의 순서 있는 종결을 enum만으로 제공한다."""
    basis = result.get("basis")
    if isinstance(basis, dict) and "response" in basis:
        response = basis["response"]
        if (not isinstance(response, dict) or not isinstance(response.get("questions"), (list, tuple))
                or any(not isinstance(q, dict) for q in response["questions"])):
            raise ValueError("Invalid response question closures")
        statuses = [question.get("status") for question in response["questions"]]
        completion = response.get("completion")
    elif "response_status" in result or "question_status" in result:
        statuses = result.get("question_status")
        completion = result.get("response_status")
    else:
        return {}
    if (not isinstance(statuses, (list, tuple)) or not statuses
            or any(status not in QUESTION_STATUSES for status in statuses)
            or completion != ("complete" if all(s == "answered" for s in statuses) else "partial")):
        raise ValueError("Invalid response closure statuses")
    return {"response_status": completion, "question_status": list(statuses)}


def developer_basis(basis: dict[str, Any]) -> dict[str, Any]:
    """기존 개발 근거는 보존하고 신규 scope/request 중복만 제외한다."""
    result = deepcopy(basis)
    response = result.get("response")
    if isinstance(response, dict):
        response.pop("scope", None)
        for question in response.get("questions", ()):
            question.pop("request", None)
    return result
