# -*- coding: utf-8 -*-
"""tourapi_client — 네트워크 오류만 기다렸다 다시 부르고, 응답을 받은 오류는 바로 멈춘다. 네트워크 없이 본다.

`[2026-10-12]` 하루에 세 번 WinError 10060 · read timeout 으로 멈춘 뒤 넣은 규칙.
"""
from __future__ import annotations

import io
import urllib.error
import urllib.request

import pytest

from app.domains.travel_ops.instances.activity.data_processing import tourapi_client as c

OK_BODY = '{"response": {"header": {"resultCode": "0000"}, "body": {"items": {"item": [{"contentid": "1"}]}}}}'


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def waits(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(c.time, "sleep", slept.append)
    return slept


def _urlopen(monkeypatch, outcomes):
    """outcomes 를 차례로 — 예외면 던지고, 문자열이면 그 본문을 돌려준다."""
    calls = []

    def fake(url, timeout):
        calls.append(url)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return _Response(outcome.encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return calls


def test_network_error_is_retried_after_waiting_then_succeeds(monkeypatch, waits):
    calls = _urlopen(monkeypatch, [urllib.error.URLError(TimeoutError("10060")), TimeoutError("read"), OK_BODY])
    assert c.call_tourapi("detailIntro2", {"contentId": "1"}, "KEY") == {"contentid": "1"}
    assert len(calls) == 3 and waits == [10, 30]


def test_network_error_stops_after_all_retries_without_printing_the_key(monkeypatch, waits, capsys):
    calls = _urlopen(monkeypatch, [ConnectionResetError("reset")] * 4)
    with pytest.raises(c.StopFetching) as stop:
        c.call_tourapi("detailIntro2", {"contentId": "1"}, "SECRETKEY")
    assert len(calls) == 4 and waits == list(c.RETRY_WAITS_SECONDS)
    assert "SECRETKEY" not in str(stop.value) + capsys.readouterr().out


def test_http_error_and_error_response_stop_at_once(monkeypatch, waits):
    calls = _urlopen(monkeypatch, [urllib.error.HTTPError("u", 500, "err", {}, None)])
    with pytest.raises(c.StopFetching, match="HTTP 오류: 500"):
        c.call_tourapi("detailIntro2", {"contentId": "1"}, "KEY")
    assert len(calls) == 1 and waits == []

    calls = _urlopen(monkeypatch, ["<OpenAPI_ServiceResponse>LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"])
    with pytest.raises(c.StopFetching, match="JSON 이 아닌 응답"):
        c.call_tourapi("detailIntro2", {"contentId": "1"}, "KEY")
    assert len(calls) == 1 and waits == []
