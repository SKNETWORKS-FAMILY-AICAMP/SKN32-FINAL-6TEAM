# -*- coding: utf-8 -*-
"""긴급재난문자 실키 판 — 샘플 판과 **같은 판정**, 모르는 모양은 모름.

★응답 모양의 열 이름은 샘플 CSV(같은 API 에서 받은 것)와 같다. API 번호·날짜/지역 인자는
  `[미확인]` 이라 여기서는 **우리 코드가 보내는 것**만 못 박는다 — 실호출로 확정한 뒤 고친다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.infrastructure.travel.cache import ResponseCache
from app.infrastructure.travel.disaster_msg import DisasterMsgApi

KST = ZoneInfo("Asia/Seoul")


def _row(minutes_ago: int, kind="호우", text="서울 호우경보, 하천변 산책로 이용 자제",
         regions="서울특별시 종로구 청운효자동", step="안전안내"):
    created = datetime.now(KST) - timedelta(minutes=minutes_ago)
    return {"SN": str(minutes_ago), "CRT_DT": created.strftime("%Y/%m/%d %H:%M:%S"),
            "MSG_CN": text, "RCPTN_RGN_NM": regions, "EMRG_STEP_NM": step, "DST_SE_NM": kind}


def _source(body, *, header=None, total=None, cache=None, ttl=None):
    payload = {"header": header or {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
               "body": body}
    if total is not None:
        payload["totalCount"] = total
    calls = []

    def transport(url, params):
        calls.append(dict(params))
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    return DisasterMsgApi(service_key="k", transport=transport, cache=cache,
                          cache_ttl_seconds=ttl), calls


def _now():
    return datetime.now(KST)


def test_a_recent_seoul_message_in_the_district_is_counted():
    source, calls = _source([_row(30)])
    value = source.active(region="서울", at=_now(), district="종로구")
    assert [m["kind"] for m in value["for_region"]] == ["호우"]
    assert value["mode"] == "api" and value["covered"] is True
    assert calls[0]["serviceKey"] == "k" and calls[0]["rgnNm"] == "서울특별시"   # ★K 대문자
    # ★`crtDt` 는 하한(실측) — 창 시작 날짜로 **한 번**만 부른다
    window_start = datetime.fromisoformat(value["window"]["from"])
    assert len(calls) == 1 and calls[0]["crtDt"] == window_start.strftime("%Y%m%d")


def test_a_null_body_with_code_00_is_no_message():
    """★실측 — 건수 0 이면 결과 코드 00 에 `body` 가 null 로 온다."""
    source, _ = _source(None, total=0)
    assert source.active(region="서울", at=_now(), district="종로구")["for_region"] == []


def test_the_same_rules_as_the_sample_apply_missing_person_and_lifted_messages_are_ignored():
    source, _ = _source([_row(10, kind="기타", text="실종자를 찾습니다"),
                         _row(20, kind="교통통제", text="세종대로 통제가 완전 해제되었음")])
    value = source.active(region="서울", at=_now(), district="종로구")
    assert value["for_region"] == [] and value["unclassified"] == []


def test_another_district_does_not_count():
    source, _ = _source([_row(30, regions="서울특별시 강남구 역삼동")])
    assert source.active(region="서울", at=_now(), district="종로구")["for_region"] == []


def test_an_empty_body_is_no_message_not_unknown():
    source, _ = _source([])
    value = source.active(region="서울", at=_now(), district="종로구")
    assert value is not None and value["for_region"] == []


def test_a_no_data_header_is_no_message():
    source, _ = _source(None, header={"resultCode": "03", "resultMsg": "NODATA_ERROR"})
    assert source.active(region="서울", at=_now(), district=None)["for_region"] == []


def test_an_error_header_is_unknown():
    source, _ = _source(None, header={"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED"})
    assert source.active(region="서울", at=_now()) is None


def test_one_unreadable_row_makes_the_list_unknown():
    source, _ = _source([_row(30), {"SN": "x", "CRT_DT": "모름"}])
    assert source.active(region="서울", at=_now()) is None
    assert source.misses["bad_row"] == 1


def test_a_truncated_page_is_unknown():
    """★전체 건수가 받은 것보다 많으면 못 받은 쪽에 그 문자가 있을 수 있다."""
    source, _ = _source([_row(30)], total=5000)
    assert source.active(region="서울", at=_now()) is None
    assert source.misses["truncated"] == 1


def test_a_future_item_only_looks_up_to_now():
    source, _ = _source([_row(30)])
    value = source.active(region="서울", at=_now() + timedelta(days=1), district="종로구")
    assert datetime.fromisoformat(value["window"]["to"]) <= _now() + timedelta(seconds=5)
    assert [m["kind"] for m in value["for_region"]] == ["호우"]


def test_this_source_keeps_its_cache_longer_than_the_default():
    """★하루 한도가 낮다 — 기본 캐시가 꺼져 있어도 이 소스는 자기 유지 시간으로 담는다."""
    source, calls = _source([_row(30)], cache=ResponseCache(ttl_seconds=0), ttl=1200)
    first_calls = None
    for _ in range(3):
        source.active(region="서울", at=_now(), district="종로구")
        first_calls = first_calls or len(calls)
    assert len(calls) == first_calls
