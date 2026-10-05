# -*- coding: utf-8 -*-
"""텔레그램 봇 클라이언트(`infrastructure/notify/telegram.py`) — `sendMessage` 한 건의 결과가 바깥함 일꾼이 읽는 예외로 정확히 바뀌는가.
`[2026-10-05 사용자 지시 「텔레그램만 붙여 · 알림만」]`

지키려는 것
 ①성공(2xx)만 반환 — 평문(`parse_mode` 없음) · 토큰은 주소에만
 ②429 → `RetryAfter`(헤더 `Retry-After` → 본문 `parameters.retry_after` 순) · 칸이 없거나 15분을 넘거나 음수면 None(우리 기본 간격)
 ③403 · 400 「chat not found」 → `ChatUnavailable`(재시도해도 소용없다) · 그 밖의 400 · 401 · 5xx 는 막힘이 **아니다**(`RuntimeError` — 일꾼이 재시도)
 ④시간 초과 → `TimeoutError` · 연결 오류 → `ConnectionError`(일꾼이 `unknown`)
 ⑤4,096자 넘으면 자르되 잘렸다는 표시 · 빈 본문은 거절
 ⑥예외 문구 · 로그 어디에도 토큰 · 대화 번호 · 본문이 없다(`httpx` 가 주소를 INFO 로 찍는 기록은 걸러낸다)

★텔레그램은 **mock 서버**(`httpx.MockTransport`)다 — 실제 봇으로 확인한 것이 아니다.

재현:

    python -m pytest tests/unit/travel/test_telegram_client.py -v
"""
from __future__ import annotations

import json
import logging
import traceback

import httpx
import pytest

from app.infrastructure.notify import telegram as client
from app.infrastructure.notify.discord import RetryAfter

TOKEN = "123456789:AAExampleBotTokenForTestsOnly_abcdefghijk"
CHAT = 555000111
BODY = "PRIVATE-BODY 일정이 바뀌었어요"


def _transport(status=200, *, json_body=None, headers=None, raise_exc=None, seen=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if raise_exc is not None:
            raise raise_exc
        return httpx.Response(status, json=json_body if json_body is not None else {"ok": status < 300}, headers=headers or {})
    return httpx.MockTransport(handler)


def _send(transport, text=BODY, chat=CHAT, token=TOKEN):
    return client.send_message(token, chat, text, transport=transport)


def _whole(exc: BaseException) -> str:
    """예외가 어디에 어떻게 보이든(문구 · repr · 꼬리표 · 연쇄) 한 덩어리 글로."""
    return "\n".join([str(exc), repr(exc), "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))])


# ── ① 성공 ──────────────────────────────────────────────────────
def test_success_posts_one_plain_text_message_and_keeps_the_token_only_in_the_path():
    seen = []
    assert _send(_transport(200, seen=seen)) is None
    [request] = seen
    assert request.method == "POST" and request.url.host == "api.telegram.org" and request.url.path == f"/bot{TOKEN}/sendMessage"
    body = json.loads(request.content)
    assert body == {"chat_id": CHAT, "text": BODY}                       # parse_mode 없음 = 평문 · 다른 칸 없음
    assert TOKEN not in request.content.decode() and request.headers.get("authorization") is None


@pytest.mark.parametrize("status", [200, 201, 204])
def test_any_2xx_counts_as_delivered(status):
    assert _send(_transport(status)) is None


# ── ② 429 ───────────────────────────────────────────────────────
def _retry(transport) -> RetryAfter:
    with pytest.raises(RetryAfter) as caught:
        _send(transport)
    return caught.value


def test_429_reads_the_retry_after_header():
    assert _retry(_transport(429, headers={"Retry-After": "5"})).seconds == 5.0


def test_429_reads_the_body_parameters_retry_after_when_the_header_is_missing():
    assert _retry(_transport(429, json_body={"ok": False, "error_code": 429, "parameters": {"retry_after": 7}})).seconds == 7.0


def test_429_prefers_the_header_over_the_body():
    assert _retry(_transport(429, headers={"Retry-After": "3"}, json_body={"ok": False, "parameters": {"retry_after": 99}})).seconds == 3.0


def test_429_without_any_wait_time_gives_none_so_the_worker_uses_its_own_interval():
    assert _retry(_transport(429, json_body={"ok": False})).seconds is None
    assert _retry(_transport(429, json_body={"ok": False, "parameters": {}})).seconds is None
    assert _retry(_transport(429, json_body={"ok": False, "parameters": {"retry_after": "soon"}})).seconds is None


def test_429_with_a_wait_over_fifteen_minutes_or_negative_is_not_trusted():
    assert _retry(_transport(429, headers={"Retry-After": "900.5"})).seconds is None
    assert _retry(_transport(429, json_body={"parameters": {"retry_after": 86400}})).seconds is None
    assert _retry(_transport(429, headers={"Retry-After": "-1"})).seconds is None
    assert _retry(_transport(429, headers={"Retry-After": "900"})).seconds == 900.0         # 경계값은 받아들인다


def test_429_with_an_unreadable_body_still_raises_retry_after():
    transport = httpx.MockTransport(lambda request: httpx.Response(429, content=b"<html>too many</html>"))
    assert _retry(transport).seconds is None


# ── ③ 막힘 · 그 밖의 실패 ───────────────────────────────────────
@pytest.mark.parametrize("status,body", [
    (403, {"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked by the user"}),
    (403, {"ok": False, "error_code": 403, "description": "Forbidden: user is deactivated"}),
    (403, {"ok": False}),
    (400, {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}),
    (400, {"ok": False, "error_code": 400, "description": "BAD REQUEST: CHAT NOT FOUND"}),
])
def test_a_blocked_or_missing_chat_is_chat_unavailable(status, body):
    with pytest.raises(client.ChatUnavailable):
        _send(_transport(status, json_body=body))


@pytest.mark.parametrize("status,body", [
    (400, {"ok": False, "error_code": 400, "description": "Bad Request: message is too long"}),
    (400, {"ok": False}),
    (401, {"ok": False, "error_code": 401, "description": "Unauthorized"}),
    (404, {"ok": False, "error_code": 404, "description": "Not Found"}),
    (500, {"ok": False}),
    (502, {"ok": False}),
])
def test_every_other_failure_is_a_plain_runtime_error_not_a_blocked_chat(status, body):
    """★400 의 다른 이유 · 401(토큰 틀림)을 「고객이 막았다」로 읽으면 멀쩡한 연결이 막힘으로 표시된다 — 일꾼이 재시도해야 한다."""
    with pytest.raises(RuntimeError) as caught:
        _send(_transport(status, json_body=body))
    assert not isinstance(caught.value, (client.ChatUnavailable, RetryAfter))
    assert str(status) in str(caught.value)


def test_a_400_with_a_non_json_body_is_not_treated_as_blocked():
    transport = httpx.MockTransport(lambda request: httpx.Response(400, content=b"<html>bad</html>"))
    with pytest.raises(RuntimeError) as caught:
        _send(transport)
    assert not isinstance(caught.value, client.ChatUnavailable)


def test_redirects_are_not_followed():
    seen = []
    with pytest.raises(RuntimeError):
        _send(_transport(302, headers={"Location": "https://evil.example/steal"}, seen=seen))
    assert len(seen) == 1


# ── ④ 시간 초과 · 연결 오류 ─────────────────────────────────────
@pytest.mark.parametrize("exc", [httpx.ReadTimeout("slow"), httpx.ConnectTimeout("slow"), httpx.PoolTimeout("slow")])
def test_a_timeout_becomes_timeout_error(exc):
    with pytest.raises(TimeoutError):
        _send(_transport(raise_exc=exc))


@pytest.mark.parametrize("exc", [httpx.ConnectError("refused"), httpx.ReadError("reset"), httpx.RemoteProtocolError("closed")])
def test_a_transport_failure_becomes_connection_error(exc):
    with pytest.raises(ConnectionError):
        _send(_transport(raise_exc=exc))


# ── ⑤ 길이 · 빈 본문 ────────────────────────────────────────────
def test_exactly_the_limit_is_sent_whole():
    seen = []
    text = "가" * client.MAX_TEXT
    _send(_transport(200, seen=seen), text=text)
    assert json.loads(seen[0].content)["text"] == text


def test_over_the_limit_is_cut_with_a_marker_and_never_exceeds_the_limit():
    seen = []
    _send(_transport(200, seen=seen), text="나" * (client.MAX_TEXT + 500))
    sent = json.loads(seen[0].content)["text"]
    assert len(sent) <= client.MAX_TEXT and sent.endswith("(잘림)") and sent.startswith("나" * 100)


def test_cut_leaves_short_text_alone():
    assert client.cut("안녕") == "안녕" and client.cut("x" * client.MAX_TEXT) == "x" * client.MAX_TEXT


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_an_empty_body_is_refused_before_anything_is_sent(text):
    seen = []
    with pytest.raises(ValueError):
        _send(_transport(200, seen=seen), text=text)
    assert seen == []


def test_a_missing_token_fails_instead_of_pretending_to_send():
    seen = []
    with pytest.raises(RuntimeError, match="not configured"):
        _send(_transport(200, seen=seen), token="")
    assert seen == []


# ── ⑥ 비밀은 어디에도 없다 ──────────────────────────────────────
@pytest.mark.parametrize("make", [
    lambda: _transport(403, json_body={"ok": False, "description": "Forbidden: bot was blocked by the user"}),
    lambda: _transport(400, json_body={"ok": False, "description": "Bad Request: chat not found"}),
    lambda: _transport(401, json_body={"ok": False}),
    lambda: _transport(500),
    lambda: _transport(429, headers={"Retry-After": "5"}),
    lambda: _transport(raise_exc=httpx.ReadTimeout(f"timeout at https://api.telegram.org/bot{TOKEN}/sendMessage")),
    lambda: _transport(raise_exc=httpx.ConnectError(f"cannot reach https://api.telegram.org/bot{TOKEN}/sendMessage")),
])
def test_no_exception_carries_the_token_the_chat_number_or_the_body(make):
    with pytest.raises(Exception) as caught:
        _send(make())
    whole = _whole(caught.value)
    assert TOKEN not in whole and str(CHAT) not in whole and "PRIVATE-BODY" not in whole and "api.telegram.org/bot" not in whole


def test_the_original_exception_is_not_chained_so_its_text_cannot_leak_the_token():
    with pytest.raises(TimeoutError) as caught:
        _send(_transport(raise_exc=httpx.ReadTimeout(f"timeout at /bot{TOKEN}/sendMessage")))
    assert caught.value.__cause__ is None and caught.value.__suppress_context__ is True


def test_a_full_send_writes_nothing_with_the_token_or_body_to_the_logs(caplog):
    caplog.set_level(logging.DEBUG)
    _send(_transport(200))
    for status in (403, 429, 500):
        with pytest.raises(Exception):
            _send(_transport(status))
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert TOKEN not in logged and str(CHAT) not in logged and "PRIVATE-BODY" not in logged and "api.telegram.org/bot" not in logged


def test_the_httpx_log_filter_drops_records_that_carry_the_token_and_keeps_the_rest(caplog):
    caplog.set_level(logging.DEBUG)
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.info('HTTP Request: POST https://api.telegram.org/bot%s/sendMessage "HTTP/1.1 200 OK"', TOKEN)
    httpx_logger.info('HTTP Request: GET https://example.org/health "HTTP/1.1 200 OK"')
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert TOKEN not in logged and "api.telegram.org/bot" not in logged
    assert "example.org/health" in logged                                     # 토큰이 없는 기록은 그대로 둔다


def test_the_filter_is_installed_once_on_both_http_loggers():
    for name in ("httpx", "httpcore"):
        assert sum(isinstance(f, client._DropTokenRecords) for f in logging.getLogger(name).filters) == 1
