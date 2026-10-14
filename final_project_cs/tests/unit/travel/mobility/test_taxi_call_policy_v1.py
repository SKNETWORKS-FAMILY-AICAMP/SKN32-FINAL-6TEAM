"""서울 호출료의 공식 시간 경계와 관측 전 앱 견적의 유효성을 검증합니다."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.instances.mobility.engine.errors import CaseInputError
from app.domains.travel_ops.instances.mobility.engine import taxi_call_policy
from app.domains.travel_ops.instances.mobility.engine.taxi_call_policy import (
    resolve_call_fee, validate_quoted_fee,
)

KST = timezone(timedelta(hours=9))
DEPART = datetime(2026, 10, 11, 22, tzinfo=KST)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(taxi_call_policy, "_now_kst", lambda: DEPART+timedelta(days=1))


def quote(**changes):
    return {**{
        "from": "public_a", "to": "public_b", "fee_won": 2500,
        "source": "호출 전 앱 화면",
        "quoted_at": (DEPART-timedelta(minutes=10)).isoformat(),
        "valid_from": (DEPART-timedelta(minutes=5)).isoformat(),
        "valid_until": (DEPART+timedelta(minutes=5)).isoformat(),
    }, **changes}


@pytest.mark.parametrize("product", ["km_blue_immediate", "turu_blue_immediate", "capsi_immediate", "mycap_immediate"])
@pytest.mark.parametrize("hour,minute,maximum", [(0,0,5000),(2,59,5000),(3,0,3000),(21,59,3000),(22,0,5000),(23,59,5000)])
def test_official_seoul_immediate_call_boundaries(product,hour,minute,maximum):
    result = resolve_call_fee(product, DEPART.replace(hour=hour,minute=minute))
    assert result["minimum_won"] == 0
    assert result["maximum_won"] == maximum
    assert result["actual_fee_known"] is False
    assert "서울" in result["basis"] and "사전 범위" in result["basis"]
    assert result["source_url"].startswith("https://")


def test_general_call_zero_does_not_guarantee_meter_or_availability():
    result = resolve_call_fee("kakao_general", DEPART)
    assert result["minimum_won"] == result["maximum_won"] == 0
    assert result["actual_fee_known"] is False
    assert "플랫폼 이용료" in result["basis"]


def test_aware_departure_uses_seoul_time_and_naive_means_kst():
    utc = datetime(2026,10,11,13,tzinfo=timezone.utc)
    aware = resolve_call_fee("km_blue_immediate", utc)
    naive = resolve_call_fee("km_blue_immediate", DEPART.replace(tzinfo=None))
    assert aware["maximum_won"] == naive["maximum_won"] == 5000


@pytest.mark.parametrize("product", ["mycab", "cabsy", "km_blue_reservation", "unknown", "", None, True])
def test_unknown_or_reservation_needs_a_product_specific_quote(product):
    with pytest.raises(CaseInputError, match="견적"):
        resolve_call_fee(product, DEPART)


@pytest.mark.parametrize("depart", [None,True,"2026-10-11T22:00:00+09:00",0])
def test_departure_must_be_datetime(depart):
    with pytest.raises(CaseInputError):
        resolve_call_fee("km_blue_immediate", depart)


def test_valid_quote_is_single_fee_with_caller_validity_not_provider_ttl():
    value = quote()
    snapshot = deepcopy(value)
    result = resolve_call_fee("km_blue_immediate",DEPART,quoted_fee=value)
    assert result["minimum_won"] == result["maximum_won"] == 2500
    assert result["actual_fee_known"] is True
    assert "호출자" in result["basis"] and "공식 TTL" in result["basis"]
    assert value == snapshot
    normalized = validate_quoted_fee(value,DEPART)
    normalized["fee_won"] = 0
    assert value == snapshot


@pytest.mark.parametrize("fee", [True,-1,1.5,"2500",float("nan"),float("inf")])
def test_bad_quote_fee_rejected(fee):
    with pytest.raises(CaseInputError):
        resolve_call_fee("km_blue_immediate",DEPART,quoted_fee=quote(fee_won=fee))


@pytest.mark.parametrize("changes", [
    {"quoted_at": (DEPART+timedelta(seconds=1)).isoformat()},
    {"quoted_at": (DEPART-timedelta(minutes=1)).isoformat()},
    {"quoted_at": "2026-10-11T21:50:00"},
    {"quoted_at": "bad"},
    {"valid_until": DEPART.isoformat()},
    {"valid_from": (DEPART+timedelta(seconds=1)).isoformat()},
    {"source": ""}, {"from": ""}, {"to": ""}, {"unexpected": 1},
])
def test_late_expired_or_incomplete_quote_rejected(changes):
    with pytest.raises(CaseInputError):
        resolve_call_fee("km_blue_immediate",DEPART,quoted_fee=quote(**changes))


def test_quote_time_can_equal_valid_from_and_departure_can_equal_period_start():
    value = quote(quoted_at=(DEPART-timedelta(minutes=5)).isoformat())
    assert resolve_call_fee("km_blue_immediate",DEPART,quoted_fee=value)["actual_fee_known"]
    value = quote(valid_from=DEPART.isoformat())
    assert resolve_call_fee("km_blue_immediate",DEPART,quoted_fee=value)["minimum_won"] == 2500


def test_missing_quote_timestamp_cannot_be_backfilled():
    value = quote()
    del value["quoted_at"]
    with pytest.raises(CaseInputError):
        validate_quoted_fee(value,DEPART)


def test_zero_quote_is_valid_and_does_not_turn_missing_into_zero():
    assert resolve_call_fee("km_blue_immediate",DEPART,quoted_fee=quote(fee_won=0))["actual_fee_known"]
    assert resolve_call_fee("km_blue_immediate",DEPART)["maximum_won"] == 5000


def test_utc_quote_timestamps_compare_as_instants():
    value = quote()
    for field in ("quoted_at","valid_from","valid_until"):
        value[field] = datetime.fromisoformat(value[field]).astimezone(timezone.utc).isoformat()
    assert resolve_call_fee("km_blue_immediate",DEPART,quoted_fee=value)["minimum_won"] == 2500


@pytest.mark.parametrize("product", ["blue_partners_immediate"])
def test_quote_only_brand_needs_explicit_pretrip_quote(product):
    with pytest.raises(CaseInputError, match="견적"):
        resolve_call_fee(product,DEPART)
    result = resolve_call_fee(product,DEPART,quoted_fee=quote())
    assert result["actual_fee_known"] and result["maximum_won"] == 2500
    assert result["source_url"] is None  # 입력 출처를 공식 웹 보증으로 꾸미지 않습니다.


@pytest.mark.parametrize("product", ["km_blue_reservation", "mycap_reservation", "cabsy", "anything"])
def test_reservation_and_unknown_brand_rejected_even_with_quote(product):
    with pytest.raises(CaseInputError, match="견적"):
        resolve_call_fee(product,DEPART,quoted_fee=quote())


def test_quote_after_actual_now_is_rejected_even_before_future_departure(monkeypatch):
    monkeypatch.setattr(taxi_call_policy,"_now_kst",lambda: DEPART-timedelta(minutes=20))
    with pytest.raises(CaseInputError, match="미래"):
        resolve_call_fee("km_blue_immediate",DEPART,quoted_fee=quote())


def test_zero_elapsed_pretrip_quote_is_allowed_at_validity_start():
    value = quote(quoted_at=DEPART.isoformat(),valid_from=DEPART.isoformat())
    assert resolve_call_fee("km_blue_immediate",DEPART,quoted_fee=value)["actual_fee_known"]


def test_general_call_cannot_accept_nonzero_platform_fee():
    with pytest.raises(CaseInputError,match="일반호출"):
        resolve_call_fee("kakao_general",DEPART,quoted_fee=quote())


@pytest.mark.parametrize("field", ["quoted_at","valid_from","valid_until"])
def test_quote_timestamps_cannot_be_datetime_objects(field):
    with pytest.raises(CaseInputError):
        validate_quoted_fee(quote(**{field: DEPART}),DEPART)


def test_quote_fee_above_catalog_cap_is_rejected_instead_of_clamped():
    with pytest.raises(CaseInputError,match='범위'):
        resolve_call_fee("km_blue_immediate",DEPART,quoted_fee=quote(fee_won=7000))
