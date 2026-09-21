# -*- coding: utf-8 -*-
"""행정안전부 긴급재난문자 어댑터 — DisasterMsgSource 자체 단위 검증.

★실 API 키로 검증되지 않았다(disaster_msg.py 모듈 docstring 참고).
  이 파일은 가짜 HTTP 전송으로 파싱·오류 처리·필터링 로직을 검증한다 —
  네트워크·API 키·DB가 전혀 필요 없다.

★기상청(test_kma_weather.py)·OpenMeteo(test_travel_sources.py)와 같은 패턴:
  "실패는 전부 「모름」이고 전부 세어진다"는 규율을 재난문자 어댑터도
  동일하게 지키는지 확인한다.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.infrastructure.travel.disaster_msg import DisasterMsgSource


def _resp(status: int, payload=None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://x")
    if text is not None:
        return httpx.Response(status, text=text, request=request)
    return httpx.Response(status, json=payload, request=request)


def _source(handler, key: str = "test-key") -> DisasterMsgSource:
    return DisasterMsgSource(
        service_key=key,
        transport=lambda url, params: handler(url, params),
    )


def _body(rows: list) -> dict:
    """재난문자 API 정상 응답 봉투 — 최상위 `body` 아래 배열."""
    return {"body": rows}


def _row(sn: str = "1", step: str = "안전안내", dst: str = "산불",
         crt_dt: str = "2026/10/03 08:00:00") -> dict:
    return {"SN": sn, "CRT_DT": crt_dt, "MSG_CN": f"[{dst} {step}] 상세",
            "RCPTN_RGN_NM": "서울특별시", "DST_SE_NM": dst, "EMRG_STEP_NM": step}


# ── _parse_crt_dt ──────────────────────────────────────────────
def test_parse_crt_dt_slash_format():
    """실호출 확인 포맷 "YYYY/MM/DD HH:MM:SS" 가 UTC datetime 으로 파싱된다."""
    result = DisasterMsgSource._parse_crt_dt("2026/10/03 08:00:00")
    assert result == datetime(2026, 10, 3, 8, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize("bad", [None, "", "20261003080000", "not-a-date", "2026-10-03T08:00:00"])
def test_parse_crt_dt_unreadable_value_returns_none(bad):
    """포맷이 맞지 않거나 빈 값이면 None — 모름으로 둔다."""
    assert DisasterMsgSource._parse_crt_dt(bad) is None


# ── _recent_only ───────────────────────────────────────────────
def test_recent_only_keeps_fresh_messages():
    """cutoff 이후(1시간 전) 메시지는 포함된다."""
    fresh_dt = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y/%m/%d %H:%M:%S")
    messages = [{"SN": "1", "CRT_DT": fresh_dt}]
    assert DisasterMsgSource._recent_only(messages, since_hours=6.0) == messages


def test_recent_only_drops_old_messages():
    """cutoff 이전(8시간 전) 메시지는 제거된다."""
    old_dt = (datetime.now(UTC) - timedelta(hours=8)).strftime("%Y/%m/%d %H:%M:%S")
    messages = [{"SN": "1", "CRT_DT": old_dt}]
    assert DisasterMsgSource._recent_only(messages, since_hours=6.0) == []


def test_recent_only_keeps_unreadable_crt_dt():
    """★CRT_DT 를 못 읽으면 제거하지 않는다.

    모르는 것을 「오래됐다」로 단정하면 실제 최근 발령을 놓칠 수 있다.
    """
    messages = [{"SN": "1", "CRT_DT": "모르는포맷"}]
    assert DisasterMsgSource._recent_only(messages, since_hours=6.0) == messages


def test_recent_only_mixes_fresh_old_unreadable():
    """최근·오래됨·모름이 섞이면 최근 + 모름만 남는다."""
    now = datetime.now(UTC)
    fmt = "%Y/%m/%d %H:%M:%S"
    messages = [
        {"SN": "fresh", "CRT_DT": (now - timedelta(hours=1)).strftime(fmt)},
        {"SN": "old",   "CRT_DT": (now - timedelta(hours=10)).strftime(fmt)},
        {"SN": "unk",   "CRT_DT": "?"},
    ]
    kept_sns = {m["SN"] for m in DisasterMsgSource._recent_only(messages, since_hours=6.0)}
    assert "fresh" in kept_sns and "unk" in kept_sns and "old" not in kept_sns


# ── _body_error override ────────────────────────────────────────
def test_body_error_detects_header_result_code_non_00():
    """header.resultCode 가 "00" 이 아니면 오류 문구를 반환한다."""
    payload = {"header": {"resultCode": "12", "resultMsg": "SERVICE_KEY_ERROR"}, "body": []}
    error = DisasterMsgSource._body_error(payload)
    assert error is not None and "12" in error


def test_body_error_detects_header_error_code():
    """header.errorCode 도 잡는다(resultCode 가 없는 변형)."""
    payload = {"header": {"errorCode": "99", "errorMsg": "UNKNOWN"}}
    assert DisasterMsgSource._body_error(payload) is not None


def test_body_error_passes_healthy_payload():
    """★오탐 방지 — 정상 응답을 오류로 읽으면 모든 조회가 실패한다."""
    assert DisasterMsgSource._body_error(_body([_row()])) is None


def test_body_error_passes_header_00():
    """resultCode "00" 은 성공이다."""
    payload = {"header": {"resultCode": "00", "resultMsg": "OK"}, "body": [_row()]}
    assert DisasterMsgSource._body_error(payload) is None


# ── recent() 성공 ──────────────────────────────────────────────
def test_success_returns_messages_source_confirmed_at():
    """정상 응답이면 messages·source·confirmed_at 을 포함한다."""
    result = _source(lambda u, p: _resp(200, _body([_row()]))).recent()
    assert result is not None
    assert len(result["messages"]) == 1
    assert result["source"] == "disaster_msg"
    assert result["confirmed_at"]


def test_six_fields_are_extracted_and_stringified():
    """SN·CRT_DT·MSG_CN·RCPTN_RGN_NM·DST_SE_NM·EMRG_STEP_NM 6개 필드가 추출된다."""
    result = _source(lambda u, p: _resp(200, _body([_row(sn="99", step="위급재난", dst="산불")]))).recent()
    msg = result["messages"][0]
    assert msg["SN"] == "99"
    assert msg["EMRG_STEP_NM"] == "위급재난"
    assert msg["DST_SE_NM"] == "산불"
    assert msg["RCPTN_RGN_NM"] == "서울특별시"
    assert msg["CRT_DT"] == "2026/10/03 08:00:00"


def test_region_name_is_forwarded_as_rgnNm():
    """★`region_name` 을 주면 확인된 파라미터 `rgnNm` 으로 서버에 전달된다."""
    seen: dict = {}

    def handler(url, params):
        seen.update(params)
        return _resp(200, _body([]))

    _source(handler).recent(region_name="서울특별시")
    assert seen.get("rgnNm") == "서울특별시"


def test_no_region_name_does_not_send_rgnNm():
    """region_name 을 안 주면 rgnNm 을 보내지 않는다(전국 조회)."""
    seen: dict = {}

    def handler(url, params):
        seen.update(params)
        return _resp(200, _body([]))

    _source(handler).recent()
    assert "rgnNm" not in seen


def test_empty_body_array_is_valid_with_empty_messages():
    """body 가 빈 배열이면 messages 가 [] 인 정상 결과다."""
    result = _source(lambda u, p: _resp(200, _body([]))).recent()
    assert result is not None and result["messages"] == []


def test_service_key_is_included_in_request():
    """serviceKey 파라미터가 요청에 포함된다."""
    seen: dict = {}

    def handler(url, params):
        seen.update(params)
        return _resp(200, _body([]))

    _source(handler, key="my-real-key").recent()
    assert seen.get("serviceKey") == "my-real-key"


def test_return_type_json_and_page_params_are_always_sent():
    """returnType=json·pageNo·numOfRows 는 항상 포함된다."""
    seen: dict = {}

    def handler(url, params):
        seen.update(params)
        return _resp(200, _body([]))

    _source(handler).recent()
    assert seen.get("returnType") == "json"
    assert "pageNo" in seen and "numOfRows" in seen


# ── 실패 갈래 — 전부 None 이고 전부 세어진다 ──────────────────
def test_no_service_key_returns_none_and_is_counted():
    """키가 없으면 바깥으로 나가지 않고 no_service_key 를 센다."""
    calls = []
    source = DisasterMsgSource(
        service_key="",
        transport=lambda u, p: calls.append(1) or _resp(200, _body([])),
    )
    assert source.recent() is None
    assert source.misses["no_service_key"] == 1
    assert calls == [], "키 없는데 HTTP 요청을 보냈다"


@pytest.mark.parametrize("handler,reason", [
    (lambda u, p: (_ for _ in ()).throw(httpx.ConnectTimeout("slow")), "timeout"),
    (lambda u, p: (_ for _ in ()).throw(httpx.ConnectError("down")), "transport_error"),
    (lambda u, p: _resp(500, text="oops"), "http_500"),
    (lambda u, p: _resp(200, text="<html>error</html>"), "not_json"),
    (lambda u, p: _resp(200, {"header": {"resultCode": "12", "resultMsg": "BAD_KEY"}, "body": []}),
     "body_error"),
])
def test_every_failure_is_none_and_is_counted(handler, reason):
    source = _source(handler)
    assert source.recent() is None
    assert source.misses[reason] == 1, dict(source.misses)


def test_body_not_a_list_is_unexpected_envelope():
    """body 가 배열이 아니면(dict 등) unexpected_envelope 로 센다."""
    source = _source(lambda u, p: _resp(200, {"body": {"SN": "1"}}))
    assert source.recent() is None
    assert source.misses["unexpected_envelope"] == 1


def test_timeout_is_not_retried():
    """★타임아웃에 자동 재시도를 걸면 공급자 장애 때 우리가 부하를 보탠다."""
    calls = []

    def handler(url, params):
        calls.append(url)
        raise httpx.ReadTimeout("slow")

    assert _source(handler).recent() is None
    assert len(calls) == 1, f"재시도했다: {len(calls)}회"


# ── near() ─────────────────────────────────────────────────────
def test_near_delegates_to_recent_ignoring_coordinates():
    """★near() 는 좌표를 실제로 쓰지 않는다.

    이 API 는 좌표가 아니라 지역명(rgnNm) 으로 거른다 — places 에는
    지역명이 없어서 지금은 전국을 그대로 받는다. 좌표가 있든 없든
    recent() 에 위임하고 같은 결과를 돌려준다.
    """
    result = _source(lambda u, p: _resp(200, _body([_row()]))).near(37.5796, 126.9770)
    assert result is not None and result["source"] == "disaster_msg"


def test_near_and_recent_give_same_result_for_same_data():
    """near() 와 recent() 가 동일한 데이터를 돌려준다."""
    payload = _body([_row(sn="42", step="긴급재난")])
    source = _source(lambda u, p: _resp(200, payload))

    # near() 는 recent() 에 위임하므로 두 번 호출하면 두 번 나간다
    # — 각각 독립된 소스로 검증한다
    r1 = _source(lambda u, p: _resp(200, payload)).recent()
    r2 = _source(lambda u, p: _resp(200, payload)).near(0.0, 0.0)
    assert r1 is not None and r2 is not None
    assert r1["messages"][0]["SN"] == r2["messages"][0]["SN"] == "42"