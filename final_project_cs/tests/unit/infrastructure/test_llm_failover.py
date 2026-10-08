# -*- coding: utf-8 -*-
"""모델 서버가 죽거나 늦으면 서버용 OpenAI 키로 자동으로 넘기는 장치. `[2026-10-07 사용자 지시]`

★여기 시험은 전부 **mock 서버**다 — Ollama 자리에는 정해진 응답을 내는 가짜 전송 함수, OpenAI 자리에는 정해진 응답을 내는 가짜 클라이언트를 꽂는다.
  실제 Ollama · 실제 유료 API 는 한 번도 부르지 않는다(키 값도 시험용 글자다).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.infrastructure import llm_failover as lf
from app.infrastructure.ollama_chat import OllamaChat, OllamaError, from_settings

KEY = "sk-test-NOT-A-REAL-KEY-0123456789"
URL = "http://ollama.test:11434"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def settings(**over):
    base = dict(ollama_base_url=URL, ollama_model="gemma4:12b", ollama_timeout_seconds=60.0, ollama_keep_alive="",
                llm_failover_enabled=True, openai_api_key_server=KEY, llm_model="gpt-4o-mini", llm_failover_model="",
                llm_failover_primary_timeout_seconds=6.0, llm_failover_api_timeout_seconds=8.0, llm_failover_total_seconds=15.0,
                llm_failover_failures=3, llm_failover_open_seconds=60.0, llm_failover_daily_cap=2000, llm_failover_monthly_cap=30000,
                llm_failover_vision=False, ollama_fallback_base_urls="")
    base.update(over)
    return SimpleNamespace(**base)


class Server:
    """Ollama 전송 함수 — 호출마다 `script` 의 다음 동작을 한다(예외면 던지고, 응답이면 돌려준다). 다 쓰면 마지막 동작을 되풀이한다."""

    def __init__(self, *script) -> None:
        self.script, self.calls = list(script), 0

    def __call__(self, url, payload):
        step = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if isinstance(step, Exception):
            raise step
        status, body = step
        request = httpx.Request("POST", url)
        return httpx.Response(status, json=body, request=request)


def ok(content='{"action": "answer_fact"}'):
    return (200, {"message": {"content": content}})


CONNECT = httpx.ConnectError("refused")
TIMEOUT = httpx.ReadTimeout("slow")


class Api:
    """OpenAI 클라이언트 흉내 — `chat.completions.create(**kwargs)`. 호출 인자를 모아 둔다."""

    def __init__(self, *script) -> None:
        self.script, self.calls = list(script or ['{"action": "other"}']), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        step = self.script[min(len(self.calls) - 1, len(self.script) - 1)]
        if isinstance(step, Exception):
            raise step
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=step))])


def build(server, api=None, *, clock=None, budget=lambda: True, **over):
    lf.reset_state()
    clock = clock or Clock()
    primary = OllamaChat(base_url=URL, model="gemma4:12b", transport=server)
    chat = lf.wrap_from_settings(primary, settings(**over), budget=budget, api_client=api or Api(), clock=clock, sleep=clock.sleep)
    return chat, clock


def status_error(cls, code):
    request = httpx.Request("POST", "https://api.openai.test/v1/chat/completions")
    return cls(f"boom {KEY}", response=httpx.Response(code, request=request), body=None)


# ───────────── 켜짐 · 꺼짐 ─────────────
def test_switch_off_returns_the_plain_ollama_chat():
    chat = from_settings(settings(llm_failover_enabled=False))
    assert type(chat) is OllamaChat


def test_switch_on_without_the_server_key_returns_the_plain_ollama_chat():
    assert type(from_settings(settings(openai_api_key_server=""))) is OllamaChat
    assert type(from_settings(settings(openai_api_key_server="   "))) is OllamaChat


def test_switch_on_with_the_key_returns_the_failover_chat_with_the_same_surface():
    lf.reset_state()
    chat = from_settings(settings())
    assert type(chat) is lf.FailoverChat
    for name in ("json", "text", "structured", "see", "loaded", "warm"):
        assert callable(getattr(chat, name))
    assert chat.model == "gemma4:12b"


def test_no_ollama_address_means_no_chat_even_with_the_switch_on():
    assert from_settings(settings(ollama_base_url="")) is None


# ───────────── 넘기는 조건 ─────────────
def test_when_ollama_answers_the_api_is_never_called():
    server, api = Server(ok()), Api()
    chat, _ = build(server, api)
    assert chat.json("sys", "hi") == {"action": "answer_fact"}
    assert api.calls == [] and lf.current_path()["path"] == "local"


@pytest.mark.parametrize("step,reason", [(CONNECT, "connect"), (TIMEOUT, "timeout"), (ok(""), "empty")])
def test_connect_failure_timeout_and_empty_answer_go_to_the_api(step, reason):
    server, api = Server(step), Api('{"action": "other"}')
    chat, _ = build(server, api)
    assert chat.json("sys", "hi") == {"action": "other"}
    path = lf.current_path()
    assert path["path"] == "api" and path["backend"] == "openai" and path["reasons"] == [["ollama", reason]] or path["reasons"] == [("ollama", reason)]
    assert len(api.calls) == 1 and api.calls[0]["model"] == "gpt-4o-mini"
    assert lf.snapshot()["counters"][f"fail:ollama:{reason}"] == 1


def test_a_5xx_is_retried_once_after_a_short_wait_and_a_recovery_stays_local():
    server, api = Server((503, {}), ok()), Api()
    chat, clock = build(server, api)
    assert chat.json("sys", "hi") == {"action": "answer_fact"}
    assert server.calls == 2 and clock.slept == [0.4] and api.calls == []


@pytest.mark.parametrize("code", [429, 500, 502, 503])
def test_two_5xx_or_429_in_a_row_go_to_the_api_after_exactly_one_retry(code):
    server, api = Server((code, {})), Api()
    chat, clock = build(server, api)
    chat.json("sys", "hi")
    assert server.calls == 2 and len(api.calls) == 1 and clock.slept == [0.4]


def test_the_retry_is_skipped_when_it_would_not_fit_in_the_total_time():
    server, api = Server((503, {})), Api()
    chat, clock = build(server, api, llm_failover_total_seconds=8.0)           # 0.4 + 6(Ollama) + 8(API) > 8
    chat.json("sys", "hi")
    assert server.calls == 1 and clock.slept == [] and len(api.calls) == 1


def test_a_client_error_that_is_not_429_goes_to_the_api_without_a_retry():
    server, api = Server((404, {})), Api()
    chat, clock = build(server, api)
    chat.json("sys", "hi")
    assert server.calls == 1 and clock.slept == [] and len(api.calls) == 1


def test_a_malformed_answer_goes_to_the_api_for_that_call_only_and_never_opens_the_breaker():
    server, api = Server(ok("not json")), Api()
    chat, _ = build(server, api)
    for _ in range(5):
        assert chat.json("sys", "hi") == {"action": "other"}
    assert server.calls == 5                                    # 서버는 살아 있다 — 매번 먼저 불렀다
    assert lf.snapshot()["breakers"][f"ollama@{URL}"]["state"] == "closed"


# ───────────── 회로 차단기 ─────────────
def test_three_failures_in_a_row_open_the_breaker_and_the_next_call_skips_ollama():
    server, api = Server(CONNECT), Api()
    chat, _ = build(server, api)
    for _ in range(3):
        chat.json("sys", "hi")
    assert server.calls == 3
    chat.json("sys", "hi")
    assert server.calls == 3                                    # 건너뛰었다
    assert lf.current_path()["reasons"] == [("ollama", "circuit_open")]
    assert lf.snapshot()["breakers"][f"ollama@{URL}"]["state"] == "open"
    assert lf.snapshot()["counters"]["skip:ollama:circuit_open"] == 1


def test_a_success_in_between_resets_the_failure_count():
    server, api = Server(CONNECT, CONNECT, ok(), CONNECT, CONNECT, ok()), Api()
    chat, _ = build(server, api)
    for _ in range(6):
        chat.json("sys", "hi")
    assert lf.snapshot()["breakers"][f"ollama@{URL}"]["state"] == "closed"


def test_after_the_open_time_one_probe_goes_to_ollama_and_a_success_closes_the_breaker():
    server, api = Server(CONNECT, CONNECT, CONNECT, ok()), Api()
    chat, clock = build(server, api)
    for _ in range(3):
        chat.json("sys", "hi")
    clock.now += 61
    assert chat.json("sys", "hi") == {"action": "answer_fact"} and lf.current_path()["path"] == "local"
    assert lf.snapshot()["breakers"][f"ollama@{URL}"]["state"] == "closed"


def test_a_failed_probe_reopens_the_breaker_for_another_full_period():
    server, api = Server(CONNECT), Api()
    chat, clock = build(server, api)
    for _ in range(3):
        chat.json("sys", "hi")
    clock.now += 61
    chat.json("sys", "hi")                                      # 시험 호출 — 또 실패
    assert server.calls == 4
    chat.json("sys", "hi")
    assert server.calls == 4                                    # 다시 건너뛴다
    clock.now += 30
    chat.json("sys", "hi")
    assert server.calls == 4                                    # 아직 60초가 안 됐다


def test_while_a_probe_is_in_flight_other_calls_skip_the_server():
    breaker = lf.CircuitBreaker("t", threshold=1, open_seconds=10, clock=lambda: 50.0)
    breaker.failure()
    breaker.opened_at = 0.0
    assert breaker.allow() is True and breaker.state == "half_open"
    assert breaker.allow() is False                             # 시험이 끝나기 전에는 하나만


# ───────────── 모두 안 될 때 · 비밀 · 상한 ─────────────
def test_when_every_path_fails_the_error_names_the_reasons_and_never_the_key():
    server = Server(CONNECT)
    api = Api(status_error(openai.AuthenticationError, 401))
    chat, _ = build(server, api)
    with pytest.raises(OllamaError) as caught:
        chat.json("sys", "hi")
    text = str(caught.value)
    assert "ollama=connect" in text and "openai=auth" in text
    assert KEY not in text and "sk-test" not in text
    assert lf.current_path()["path"] is None


@pytest.mark.parametrize("make,reason", [
    (lambda: openai.APIConnectionError(request=httpx.Request("POST", "https://x.test")), "connect"),
    (lambda: openai.APITimeoutError(request=httpx.Request("POST", "https://x.test")), "timeout"),
    (lambda: status_error(openai.RateLimitError, 429), "429"),
    (lambda: status_error(openai.InternalServerError, 500), "5xx"),
    (lambda: status_error(openai.BadRequestError, 400), "bad_request"),
])
def test_openai_failures_are_named_by_reason_without_the_message_body(make, reason):
    server, api = Server(CONNECT), Api(make())
    chat, _ = build(server, api)
    with pytest.raises(OllamaError) as caught:
        chat.text("sys", "hi")
    assert f"openai={reason}" in str(caught.value) and KEY not in str(caught.value)


def test_the_call_budget_stops_the_api_and_the_failure_is_raised_not_hidden():
    server, api = Server(CONNECT), Api()
    chat, _ = build(server, api, budget=lambda: False)
    with pytest.raises(OllamaError) as caught:
        chat.json("sys", "hi")
    assert "openai=budget_exhausted" in str(caught.value) and api.calls == []
    assert lf.snapshot()["counters"]["skip:openai:budget_exhausted"] == 1


def test_the_budget_is_asked_only_when_the_api_is_actually_about_to_be_used():
    asked = []
    server, api = Server(ok()), Api()
    chat, _ = build(server, api, budget=lambda: asked.append(1) or True)
    chat.json("sys", "hi")
    assert asked == []
    build_server = Server(CONNECT)
    chat2, _ = build(build_server, Api(), budget=lambda: asked.append(1) or True)
    chat2.json("sys", "hi")
    assert asked == [1]


def test_text_sent_to_the_api_is_masked_once_more():
    server, api = Server(CONNECT), Api()
    chat, _ = build(server, api)
    chat.json("sys", "전화 010-1234-5678 메일 kim@example.com 키 " + KEY)
    sent = json.dumps(api.calls[0]["messages"], ensure_ascii=False)
    assert "010-1234-5678" not in sent and "kim@example.com" not in sent and KEY not in sent
    assert "010-****-5678" in sent


def test_the_text_sent_to_ollama_is_left_as_the_caller_made_it():
    seen = []

    def server(url, payload):
        seen.append(payload["messages"][1]["content"])
        return httpx.Response(200, json={"message": {"content": "{}"}}, request=httpx.Request("POST", url))
    chat, _ = build(server)
    chat.json("sys", "원문 그대로 010-1234-5678")
    assert seen == ["원문 그대로 010-1234-5678"]


# ───────────── 이미지 · 스키마 · 여러 서버 ─────────────
def test_images_do_not_go_to_the_api_unless_vision_is_switched_on():
    server, api = Server(CONNECT), Api("받아쓴 글")
    chat, _ = build(server, api)
    with pytest.raises(OllamaError) as caught:
        chat.see("읽어라", b"\x89PNG....")
    assert "openai=vision_off" in str(caught.value) and api.calls == []


def test_with_vision_on_an_image_goes_to_the_api_as_a_data_url():
    server, api = Server(CONNECT), Api("받아쓴 글")
    chat, _ = build(server, api, llm_failover_vision=True)
    assert chat.see("읽어라", b"\xff\xd8\xff\xe0jpeg") == "받아쓴 글"
    part = api.calls[0]["messages"][0]["content"][1]["image_url"]["url"]
    assert part.startswith("data:image/jpeg;base64,")


SCHEMA = {"type": "object", "properties": {"action": {"type": "string", "enum": ["a", "b"]}}, "required": ["action"]}


def test_structured_sends_the_schema_as_the_response_format_and_returns_the_object():
    server, api = Server(CONNECT), Api('{"action": "a"}')
    chat, _ = build(server, api)
    assert chat.structured("sys", "hi", SCHEMA, num_predict=400) == {"action": "a"}
    fmt = api.calls[0]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["schema"] == SCHEMA and fmt["json_schema"]["strict"] is False
    assert api.calls[0]["temperature"] == 0 and api.calls[0]["max_tokens"] >= 400


def test_structured_falls_back_to_json_object_mode_when_the_schema_is_refused():
    server = Server(CONNECT)
    api = Api(status_error(openai.BadRequestError, 400), '{"action": "b"}')
    chat, _ = build(server, api)
    assert chat.structured("sys", "hi", SCHEMA) == {"action": "b"}
    assert api.calls[1]["response_format"] == {"type": "json_object"}
    assert json.dumps(SCHEMA, ensure_ascii=False) in api.calls[1]["messages"][0]["content"]


def test_a_reasoning_model_is_called_without_temperature():
    server, api = Server(CONNECT), Api()
    chat, _ = build(server, api, llm_failover_model="o4-mini")
    chat.json("sys", "hi")
    assert "temperature" not in api.calls[0] and api.calls[0]["model"] == "o4-mini"


def test_the_failover_model_defaults_to_the_projects_llm_model():
    server, api = Server(CONNECT), Api()
    chat, _ = build(server, api)
    chat.text("sys", "hi")
    assert api.calls[0]["model"] == "gpt-4o-mini"


def test_a_second_ollama_server_is_tried_before_the_api():
    lf.reset_state()
    clock = Clock()
    first = OllamaChat(base_url="http://a.test:1", model="m", transport=Server(CONNECT))
    second = OllamaChat(base_url="http://b.test:1", model="m", transport=Server(ok('{"x": 1}')))
    api = Api()
    chat = lf.FailoverChat([
        lf._Backend("ollama", first, lf.breaker_for("a", threshold=3, open_seconds=60, clock=clock), timeout=6),
        lf._Backend("ollama2", second, lf.breaker_for("b", threshold=3, open_seconds=60, clock=clock), timeout=6),
        lf._Backend("openai", lf.OpenAIChat(api_key=KEY, model="gpt-4o-mini", client=api), lf.breaker_for("openai", threshold=3, open_seconds=60, clock=clock),
                    is_api=True, timeout=8)], sleep=clock.sleep, clock=clock)
    assert chat.json("s", "u") == {"x": 1}
    assert lf.current_path()["backend"] == "ollama2" and lf.current_path()["path"] == "local" and api.calls == []


def test_the_api_breaker_opens_too_so_a_broken_key_does_not_cost_eight_seconds_every_call():
    server = Server(CONNECT)
    api = Api(status_error(openai.AuthenticationError, 401))
    chat, _ = build(server, api)
    for _ in range(3):
        with pytest.raises(OllamaError):
            chat.json("sys", "hi")
    assert len(api.calls) == 3
    with pytest.raises(OllamaError):
        chat.json("sys", "hi")
    assert len(api.calls) == 3                                  # 열렸다


# ───────────── 예열 · 기록 ─────────────
def test_warm_and_loaded_go_to_the_first_ollama_only():
    posted = []

    def server(url, payload):
        posted.append(url)
        return httpx.Response(200, json={"message": {"content": "."}}, request=httpx.Request("POST", url))
    chat, _ = build(server)
    chat.warm()
    assert posted == [URL + "/api/chat"]


def test_every_call_leaves_a_path_record_and_counts():
    server, api = Server(ok(), CONNECT), Api()
    chat, _ = build(server, api)
    chat.json("sys", "a")
    assert lf.current_path()["path"] == "local" and lf.current_path()["op"] == "json"
    chat.text("sys", "b")
    assert lf.current_path()["path"] == "api" and lf.current_path()["op"] == "text"
    counters = lf.snapshot()["counters"]
    assert counters["ok:json:ollama"] == 1 and counters["ok:text:openai"] == 1
    assert lf.snapshot()["last_switch"]["to"] == "openai"


# ───────────── 진짜 HTTP 로 — 닫힌 포트 · 느린 서버 · 5xx 서버(mock 서버를 이 PC 안에 잠깐 띄운다) ─────────────
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


class _Handler(BaseHTTPRequestHandler):
    mode = "ok"
    hits = 0

    def do_POST(self):                                           # noqa: N802
        type(self).hits += 1
        self.rfile.read(int(self.headers.get("content-length", 0)))
        if self.mode == "slow":
            time.sleep(1.5)
        if self.mode == "5xx":
            self.send_response(503)
            self.end_headers()
            return
        body = json.dumps({"message": {"content": '{"action": "answer_fact"}'}}).encode()
        try:
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:                                          # 느린 모드에서 클라이언트가 이미 끊었다
            pass

    def log_message(self, *args):                                # noqa: D401 — 조용히
        return


def _serve(mode):
    handler = type("H", (_Handler,), {"mode": mode, "hits": 0})
    server = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, handler


def _real_chat(url, api, **over):
    lf.reset_state()
    cfg = settings(ollama_base_url=url, llm_failover_primary_timeout_seconds=0.5, **over)
    chat = from_settings(cfg)
    assert type(chat) is lf.FailoverChat
    # 실제 OpenAI 대신 가짜 클라이언트를 꽂는다(키 · 상한만 시험용)
    api_backend = chat._backends[-1]
    api_backend.chat._client = api
    api_backend.budget = lambda: True
    return chat


def test_http_a_closed_port_goes_to_the_api_quickly():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]                             # 열었다가 닫으면 아무도 안 듣는 포트가 된다
    api = Api('{"action": "other"}')
    chat = _real_chat(f"http://127.0.0.1:{port}", api)
    started = time.monotonic()
    assert chat.json("sys", "hi") == {"action": "other"}
    assert time.monotonic() - started < 3 and lf.current_path()["reasons"][0][1] == "connect"


def test_http_a_slow_server_times_out_and_goes_to_the_api():
    server, handler = _serve("slow")
    try:
        api = Api('{"action": "other"}')
        chat = _real_chat(f"http://127.0.0.1:{server.server_port}", api)
        started = time.monotonic()
        assert chat.json("sys", "hi") == {"action": "other"}
        assert time.monotonic() - started < 2.0                  # 0.5초에 끊고 넘겼다(서버는 1.5초 걸린다)
        assert lf.current_path()["reasons"][0][1] == "timeout"
    finally:
        server.shutdown()


def test_http_a_503_server_is_retried_once_then_goes_to_the_api():
    server, handler = _serve("5xx")
    try:
        api = Api('{"action": "other"}')
        chat = _real_chat(f"http://127.0.0.1:{server.server_port}", api)
        assert chat.json("sys", "hi") == {"action": "other"}
        assert handler.hits == 2 and lf.current_path()["reasons"][0][1] == "5xx"
    finally:
        server.shutdown()


def test_http_a_healthy_server_answers_locally_and_the_api_is_not_touched():
    server, handler = _serve("ok")
    try:
        api = Api()
        chat = _real_chat(f"http://127.0.0.1:{server.server_port}", api)
        assert chat.json("sys", "hi") == {"action": "answer_fact"}
        assert api.calls == [] and lf.current_path()["path"] == "local"
    finally:
        server.shutdown()


# ───────────── 방어 ─────────────
def test_an_unexpected_exception_during_a_probe_does_not_lock_the_breaker():
    calls = {"n": 0}

    def server(url, payload):
        calls["n"] += 1
        if calls["n"] <= 3:
            raise CONNECT
        if calls["n"] == 4:
            raise ValueError("우리가 모르는 예외")               # 반쪽 시험 호출에서 터진다
        return httpx.Response(200, json={"message": {"content": '{"ok": 1}'}}, request=httpx.Request("POST", url))
    chat, clock = build(server, Api())
    for _ in range(3):
        chat.json("s", "u")
    clock.now += 61
    with pytest.raises(ValueError):
        chat.json("s", "u")
    assert chat.json("s", "u") == {"ok": 1}                      # 자리가 풀려서 바로 다시 시험했고 성공했다
    assert lf.snapshot()["breakers"][f"ollama@{URL}"]["state"] == "closed"


def test_the_openai_client_is_shared_between_requests():
    lf.reset_state()
    first = lf.OpenAIChat(api_key=KEY, model="m", timeout=8.0)._api()
    second = lf.OpenAIChat(api_key=KEY, model="m", timeout=8.0)._api()
    assert first is second
