# -*- coding: utf-8 -*-
"""브이월드 지오코더(`activity/geocode.py`) — 가짜 네트워크로 본다(실제 호출 없음). `[2026-10-19]`

★핵심: ① 「없음」과 「못 물어봄」을 가른다 ② 키가 결과 · 오류에 실리지 않는다 ③ 서울 밖은 받지 않는다.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.instances.activity import geocode as g

KEY = "SECRET-KEY-123"
OK_BODY = {"response": {"status": "OK", "result": {"point": {"x": "126.9769930325", "y": "37.5758772123"}}}}
NOT_FOUND_BODY = {"response": {"status": "NOT_FOUND"}}


class Fake:
    """`type` 별로 준비한 답(dict 또는 예외)을 돌려주고 받은 요청을 적는다."""

    def __init__(self, road=None, parcel=None):
        self.answers = {"road": road, "parcel": parcel}
        self.requests: list[dict[str, str]] = []

    def __call__(self, url, params, timeout):
        self.requests.append({**params})
        answer = self.answers[params["type"]]
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_road_address_found_first_and_parcel_is_not_asked():
    fake = Fake(road=OK_BODY)
    result = g.VWorldGeocoder(KEY, fetch=fake).geocode("서울특별시 종로구 사직로 161")
    assert result.ok and result.kind == "road"
    assert (result.latitude, result.longitude) == (37.5758772123, 126.9769930325)
    assert [r["type"] for r in fake.requests] == ["road"]


def test_falls_back_to_the_parcel_address_when_the_road_address_is_not_found():
    fake = Fake(road=NOT_FOUND_BODY, parcel=OK_BODY)
    geocoder = g.VWorldGeocoder(KEY, fetch=fake)
    result = geocoder.geocode("서울특별시 종로구 세종로 1-1")
    assert result.ok and result.kind == "parcel" and geocoder.calls == 2


def test_not_found_in_both_kinds_is_not_found_not_unavailable():
    result = g.VWorldGeocoder(KEY, fetch=Fake(NOT_FOUND_BODY, NOT_FOUND_BODY)).geocode("서울특별시 없는구 없는로 1")
    assert result.status == g.NOT_FOUND and not result.ok and result.latitude is None


def test_a_network_error_is_unavailable_never_not_found():
    """★못 물어본 것을 「주소가 틀렸다」로 읽지 않는다."""
    result = g.VWorldGeocoder(KEY, fetch=Fake(TimeoutError("boom"), TimeoutError("boom"))).geocode("서울특별시 종로구 사직로 161")
    assert result.status == g.UNAVAILABLE and result.reason == "TimeoutError"


def test_unavailable_once_and_not_found_otherwise_is_still_unavailable():
    result = g.VWorldGeocoder(KEY, fetch=Fake(TimeoutError("x"), NOT_FOUND_BODY)).geocode("서울특별시 종로구 사직로 161")
    assert result.status == g.UNAVAILABLE                     # 도로명을 못 물어봤으니 「없다」고 단정하지 않는다


@pytest.mark.parametrize("status", ["ERROR", "INCORRECT_KEY", ""])
def test_service_errors_are_unavailable(status):
    body = {"response": {"status": status}}
    result = g.VWorldGeocoder(KEY, fetch=Fake(body, body)).geocode("서울특별시 종로구 사직로 161")
    assert result.status == g.UNAVAILABLE


def test_a_malformed_response_is_unavailable():
    result = g.VWorldGeocoder(KEY, fetch=Fake({"nope": 1}, {"response": {"status": "OK", "result": {}}})).geocode("서울특별시 종로구 사직로 161")
    assert result.status == g.UNAVAILABLE


def test_outside_seoul_is_not_accepted():
    busan = {"response": {"status": "OK", "result": {"point": {"x": "129.0756", "y": "35.1796"}}}}
    result = g.VWorldGeocoder(KEY, fetch=Fake(busan, busan)).geocode("서울특별시 종로구 사직로 161")
    assert result.status == g.NOT_FOUND and result.reason == "OUT_OF_SEOUL"


def test_no_key_never_calls_the_network():
    fake = Fake(OK_BODY, OK_BODY)
    for key in (None, "", "   "):
        result = g.VWorldGeocoder(key, fetch=fake).geocode("서울특별시 종로구 사직로 161")
        assert result.status == g.UNAVAILABLE and result.reason == "no_key"
    assert fake.requests == []


def test_empty_address_asks_nothing():
    fake = Fake(OK_BODY, OK_BODY)
    assert g.VWorldGeocoder(KEY, fetch=fake).geocode("  (괄호만)  ").status == g.NO_ADDRESS
    assert g.VWorldGeocoder(KEY, fetch=fake).geocode(None).status == g.NO_ADDRESS
    assert fake.requests == []


def test_the_key_never_appears_in_the_result_or_the_error_reason():
    """예외 메시지에 요청 주소(키)가 실려도 결과에는 종류 이름만 남는다."""
    leaky = RuntimeError(f"GET https://api.vworld.kr/req/address?key={KEY}")
    result = g.VWorldGeocoder(KEY, fetch=Fake(leaky, leaky)).geocode("서울특별시 종로구 사직로 161")
    assert KEY not in repr(result) and result.reason == "RuntimeError"


def test_address_is_cleaned_before_asking():
    assert g.clean_address("서울특별시 서울특별시  종로구   사직로 161 (세종로)") == "서울특별시 종로구 사직로 161"
    fake = Fake(road=OK_BODY)
    g.VWorldGeocoder(KEY, fetch=fake).geocode("서울특별시 서울특별시 종로구 사직로 161 (세종로)")
    assert fake.requests[0]["address"] == "서울특별시 종로구 사직로 161"
    assert fake.requests[0]["crs"] == "epsg:4326" and fake.requests[0]["key"] == KEY


def test_from_settings_reads_the_core_key(monkeypatch):
    from app.core import settings as core_settings

    class _S:
        vworld_api_key = "FROM-SETTINGS"

    monkeypatch.setattr(core_settings, "get_settings", lambda: _S())
    assert g.VWorldGeocoder.from_settings(fetch=Fake(OK_BODY)).geocode("서울특별시 종로구 사직로 161").ok
