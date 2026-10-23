"""이동 계산기의 근거 출처 종류를 공통 계약 종류로 옮긴다 — 계약 밖 값이면 판정 전체가 계약 검사에서 죽었다(2026-10-14)."""
import pytest

from app.domains.travel_ops.instances.mobility.team import _contract_source_type


def test_contract_types_pass_through_unchanged():
    assert _contract_source_type("db", "근거") == ("db", "근거")


@pytest.mark.parametrize("raw, expected", [("official_web", "db"), ("tour_api", "db"), ("api", "tool_result")])
def test_known_source_types_are_mapped_and_the_original_is_kept_in_the_claim(raw, expected):
    kind, claim = _contract_source_type(raw, "운영시간 10:00~18:00")
    assert kind == expected and claim.endswith(f"(원 출처 종류: {raw})")


def test_an_unknown_source_type_fails_loudly():
    with pytest.raises(ValueError):
        _contract_source_type("rumor", "근거")
