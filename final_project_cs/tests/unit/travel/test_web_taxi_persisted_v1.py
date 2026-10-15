"""손상된 저장 조건을 일반호출 기본값으로 낮추지 않는 경계."""
import pytest

from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.components.intake import assemble, review, taxi_pricing


@pytest.fixture(autouse=True)
def _taxi_call_product_on():
    """이 파일은 택시 호출 상품 고르기가 **켜진** 때의 동작을 본다 — 꺼짐은 test_taxi_call_product_switch.py."""
    settings_hook.register(lambda tenant, name: True if name == settings_hook.TAXI_CALL_PRODUCT else None)
    yield
    settings_hook.clear()


@pytest.mark.parametrize("value", [None, {}, [], "km_blue_immediate", {"product": "km_blue_immediate"},
    {"product": "blue_partners_immediate", "quotes": []}, {"product": True, "quotes": []},
    {"product": "km_blue_immediate", "quotes": None}, {"product": "km_blue_immediate", "quotes": [{}]}])
def test_corrupt_persisted_claim_is_rejected_in_read_review_and_confirmation(value):
    claims = [{"source_id": None, "field": "trip.taxi_pricing", "value": value, "method": "customer",
               "evidence": {}, "needs_review": False, "note": None}]
    collected = assemble.collect(sources=[], claims=claims)
    with pytest.raises(ValueError):
        taxi_pricing.from_trip(collected.trip)
    with pytest.raises(ValueError):
        review.build(None, tenant_id="t", intake_id="i", revision=1, sources=[], claims=claims, use_engine=False)
    with pytest.raises(ValueError):
        assemble.assemble(intake_id="i", revision=1, sources=[], claims=claims)


def test_only_absent_claim_preserves_the_explicit_general_default():
    assert taxi_pricing.from_trip({}) is None
    result = review.build(None, tenant_id="t", intake_id="i", revision=1, sources=[], claims=[], use_engine=False)
    assert result["taxi_pricing"] == {"product": "kakao_general", "quotes": []}
