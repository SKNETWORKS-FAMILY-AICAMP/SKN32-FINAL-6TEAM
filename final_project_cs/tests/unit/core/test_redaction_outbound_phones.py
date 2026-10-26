"""`[2026-10-26 integ-rm9]` 유료 모델로 보내는 글(`redaction.masked_outbound`)은 `masked` 가 놓치는 전화 모양도 가린다.

L03 계획 읽기 유료 대체를 다시 켰을 때 `masked` 가 구분자 없는 휴대폰(01012345678)을 그대로 넘겼다.
경계: 날짜 · 시각 · 예약번호 · 금액 · UUID 숫자를 전화로 오인해 가리면 계획 읽기가 틀린다 — 그대로 남는지 함께 본다.
"""

from __future__ import annotations

import pytest

from app.core.redaction import mask_json, masked, masked_outbound


@pytest.mark.parametrize(("raw", "secret", "kept"), [
    ("연락처 01012345678 입니다", "12345678", "010****5678"),
    ("010 1234 5678", "1234 5678", "010 **** 5678"),
    ("010.1234.5678", "1234.5678", "010.****.5678"),
    ("011-123-4567", "123-4567", "011-****-4567"),
    ("0161234567", "1234567", "016****4567"),
    ("+82 10-1234-5678", "1234-5678", "****-5678"),
    ("+821012345678", "12345678", "****5678"),
    ("+82 2 1234 5678", "1234 5678", "+82 2 **** 5678"),
    ("+82-31-123-4567", "123-4567", "+82-31-****-4567"),
    ("82-10-1234-5678", "1234-5678", "****-5678"),
    ("숙소 02-123-4567", "123-4567", "02-****-4567"),
    ("숙소 0212345678", "12345678", "02****5678"),
    ("031-1234-5678", "1234-5678", "031-****-5678"),
    ("0511234567", "1234567", "051****4567"),
    ("070-1234-5678", "1234-5678", "070-****-5678"),
    ("전화:01098765432)", "98765432", "010****5432"),
])
def test_outbound_hides_phone_shapes_the_storage_rule_misses(raw: str, secret: str, kept: str) -> None:
    out = masked_outbound(raw)
    assert secret not in out and kept in out, out


def test_storage_rule_is_unchanged_for_the_same_shapes() -> None:
    """저장값 가림(`masked` · `mask_json`)은 이번에 바꾸지 않는다 — 좁은 변경(유료 경로만)."""
    assert masked("01012345678") == "01012345678"
    assert mask_json({"phone": "010-1234-5678"}) == {"phone": "010-****-5678"}


@pytest.mark.parametrize("text", [
    "2026-10-26 10:30 경복궁",
    "20261026 1030 출발",
    "10월 26일 09:30~11:30",
    "0930-1130 박물관",
    "예약번호 ABCD-1234",
    "예약번호 2026102612345",
    "예약번호 123456789012",
    "KE1234 편 14:05 도착",
    "입장료 120000원 · 2인 24,000원",
    "1588-1234 고객센터",
    "2026.10.26 - 2026.10.28",
    "0412 1530 출발",
    "3박 4일, 10:00-18:00",
    "trip 3f2a9c1e-0101-4234-8567-012345678901 확인",
    "카드 끝자리 5678",
])
def test_dates_times_booking_numbers_prices_and_uuids_are_not_mistaken_for_phones(text: str) -> None:
    assert masked_outbound(text) == masked(text) == text


def test_longer_digit_runs_are_not_cut_into_a_phone() -> None:
    """앞뒤에 숫자가 더 붙으면 전화가 아니다(더 긴 번호의 일부)."""
    for text in ("901012345678", "010123456789", "1020212345678"):
        assert masked_outbound(text) == text


def test_uuid_digits_stay_even_when_they_look_like_a_phone() -> None:
    uid = "01012345-6789-4abc-8def-012345678901"
    out = masked_outbound(f"{uid} 연락 01012345678")
    assert uid in out and "010****5678" in out


def test_existing_masks_still_apply_on_the_outbound_path() -> None:
    out = masked_outbound("hong@example.com 010-1234-5678 sk-ABCDEF 1234 5678 9012 3456")
    assert "hong@" not in out and "1234-5678" not in out and "sk-ABCDEF" not in out and "5678 9012" not in out
