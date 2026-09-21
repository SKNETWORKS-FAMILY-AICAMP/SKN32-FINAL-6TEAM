"""마스킹 규칙별 회귀 — 2026-08-31 추가.

기존 `tests/security/test_pii_redaction_runtime.py` 는 Case 메시지 한 건이
DB·API·감사 로그에서 가려지는지를 끝에서 끝까지 본다. 그래서 **어느 규칙이
살아 있는지**는 세지 않았다. 실제로 이메일 규칙을 무력화하고 리스트 재귀를
끊어도 전체 424개가 전부 통과했다(`../program/research/테스트_사각지대_실측.md`).

여기서는 규칙을 하나씩 센다. 규칙 하나가 빠지면 그 종류의 원문이 그대로 저장된다.
"""

from __future__ import annotations

import pytest

from app.core.redaction import mask_json, masked


def test_email_keeps_only_the_first_letter() -> None:
    """이메일은 첫 글자만 남는다. 지역부가 그대로 남으면 마스킹이 아니다."""
    result = masked("문의자 hong.gildong@example.com 입니다")
    assert "hong.gildong" not in result
    assert "h***@example.com" in result


def test_api_key_is_replaced() -> None:
    assert "sk-" not in masked("key=sk-ABCDEF1234567890")


def test_payment_id_is_replaced() -> None:
    assert "pay_" not in masked("결제 pay_9f8e7d6c 건")


@pytest.mark.parametrize(
    ("raw", "leaked"),
    [
        ("010-1234-5678", "1234"),
        ("1234 5678 9012 3456", "5678"),
    ],
)
def test_number_rules_hide_the_middle(raw: str, leaked: str) -> None:
    assert leaked not in masked(raw)


def test_mask_json_descends_into_lists() -> None:
    """재귀가 끊기면 리스트 안의 원문이 그대로 저장된다.

    payload 는 보통 중첩 구조라 실제로 걸리는 경로가 많다.
    """
    masked_value = mask_json({"items": ["sk-ABCDEF1234567890", "safe"]})
    assert masked_value["items"][0] == "[REDACTED_API_KEY]"
    assert masked_value["items"][1] == "safe"


def test_mask_json_descends_into_nested_lists_of_dicts() -> None:
    masked_value = mask_json({"a": [{"b": ["hong@example.com"]}]})
    assert "hong@example.com" not in str(masked_value)


def test_mask_json_leaves_non_strings_alone() -> None:
    """숫자와 불린은 마스킹 대상이 아니다. 값을 바꿔 버리면 그것도 결함이다."""
    assert mask_json({"n": 12000, "ok": True, "none": None}) == {
        "n": 12000, "ok": True, "none": None
    }
