"""기상청 서울 권역의 포함·제외를 실제 방문 구에 적용한다."""
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.ports.data_sources.base import TravelSources
from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck, SEOUL_WARNING_ZONES
from app.domains.travel_ops.ports.data_sources.disaster_msg import SEOUL_GU_NAMES

NOW = datetime(2030, 1, 1, 14, tzinfo=ZoneInfo("Asia/Seoul"))


def warning(*rows):
    return {"source": "kma_warning", "confirmed_at": NOW.isoformat(), "for_region": list(rows)}


def row(area, kind="호우경보"):
    return {"kind": kind, "areas": [area]}


def checked(areas, *, district=None, latitude=None, longitude=None, address=None):
    value = warning(*(row(area) for area in areas))
    checker = DisruptionCheck(TravelSources(warning=SimpleNamespace(active=lambda **kw: value)))
    place = {"district": district, "latitude": latitude, "longitude": longitude, "attributes": {"address": address}}
    return checker._warning("서울", True, place)


@pytest.mark.parametrize("district", sorted(SEOUL_WARNING_ZONES["서울동남권"]))
def test_southeastern_districts_do_not_get_a_warning_explicitly_excluding_them(district):
    result = checked(["서울(서울동남권 제외)"], district=district)
    assert result["status"] == "ok" and result["_disruptions"] == []


@pytest.mark.parametrize("district", ["종로구", "마포구", "강서구", "광진구"])
def test_the_same_exclusion_keeps_warnings_for_other_seoul_districts(district):
    result = checked(["서울(서울동남권 제외)"], district=district)
    assert result["status"] == "ok" and result["_disruptions"][0]["kind"] == "호우경보"


def test_the_actual_festival_coordinates_are_in_the_excluded_zone():
    result = checked(["서울(서울동남권 제외)"], latitude=37.5590614348, longitude=127.1306006547)
    assert result["value"]["district"] == "강동구" and result["value"]["district_basis"] == "box"
    assert result["status"] == "ok" and not result["_disruptions"]


@pytest.mark.parametrize("zone,districts", SEOUL_WARNING_ZONES.items())
def test_a_specific_zone_only_applies_to_the_districts_in_that_zone(zone, districts):
    district = sorted(districts)[0]
    assert checked([zone], district=district)["_disruptions"]
    elsewhere = next(name for name in SEOUL_GU_NAMES if name not in districts)
    assert not checked([zone], district=elsewhere)["_disruptions"]


@pytest.mark.parametrize("area", ["서울", "서울특별시", "서울(동남권)", "서울(강동구, 송파구)"])
def test_citywide_and_included_zones_are_kept(area):
    assert checked([area], district="강동구")["_disruptions"]


def test_an_explicit_address_has_priority_over_a_coarse_coordinate_box():
    result = checked(["서울(서울동남권 제외)"], latitude=37.58, longitude=126.98,
                     address="서울특별시 강동구 올림픽로 1")
    assert result["value"]["district_basis"] == "address" and not result["_disruptions"]


@pytest.mark.parametrize("area", ["서울(서부권 제외)", "서울동부", "서울(동남권 제외, 강동구)"])
def test_an_unknown_zone_expression_stays_unassessed_instead_of_becoming_citywide(area):
    result = checked([area], district="강동구")
    assert result["status"] == "failed" and result["unassessed_areas"] == [[area]]
    assert not result["_disruptions"]


def test_a_place_without_district_evidence_cannot_be_assigned_to_a_subzone():
    result = checked(["서울동남권"])
    assert result["status"] == "failed" and not result["_disruptions"]
    assert checked(["서울"])["status"] == "ok"


def test_an_ambiguous_coordinate_box_crossing_zones_is_explicitly_unknown():
    result = checked(["서울(서울동남권 제외)"], district=["광진구", "강동구"])
    assert result["status"] == "failed" and not result["_disruptions"]


def test_explicit_exclusion_does_not_remove_other_confirmed_weather_or_traffic():
    value = warning(row("서울(서울동남권 제외)"), row("서울", "강풍주의보"))
    sources = TravelSources(
        weather=SimpleNamespace(forecast=lambda **kw: {"source": "weather", "confirmed_at": NOW.isoformat()}),
        warning=SimpleNamespace(active=lambda **kw: value),
        traffic=SimpleNamespace(near=lambda **kw: {"source": "utic", "confirmed_at": NOW.isoformat(),
            "for_place": [{"reason": "road_closed", "message": "합성 도로 전면통제", "road": "합성로"}]}))
    result = DisruptionCheck(sources).check(place={"latitude": 37.559, "longitude": 127.1306,
                "weather_sensitive": True}, starts_at=NOW)
    assert result["verdict"] == "disrupted"
    assert {x["kind"] for x in result["disruptions"] if x["category"] == "weather_warning"} == {"강풍주의보"}
    assert any(x["category"] == "traffic_control" for x in result["disruptions"])


def test_city_source_and_legacy_warning_call_keep_their_original_contract():
    seen = []
    value = warning(row("서울동남권"))
    source = SimpleNamespace(active=lambda **kw: seen.append(kw) or value)
    result = DisruptionCheck(TravelSources(warning=source))._warning("서울", True)
    assert result["_disruptions"] and seen == [{"region": "서울"}]
