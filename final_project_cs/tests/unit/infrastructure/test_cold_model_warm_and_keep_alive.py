# -*- coding: utf-8 -*-
"""로컬 모델이 식어 있을 때(`not_loaded`)와 같은 모델의 붙잡아 둘 시간(`keep_alive`). `[2026-10-26 x600 채팅 해석 유료 넘김 원인 F · E]`

☆왜: x600 채팅 해석 17건 중 2건이 `not_loaded` 로 유료로 넘어갔다. 스트림 경로(`FailoverChat._streaming`)는 `/api/ps` 에 모델이 없으면
  로컬을 건너뛰기만 하고 모델을 올리지 않아, runner 가 내려가 있으면 다음 요청도 계속 유료였다. 또 일정 짚기(`OllamaItemPointer`)가
  해석과 **같은 모델**인데 `keep_alive=30m` 를 보내 서버 기본(`OLLAMA_KEEP_ALIVE=-1`)을 덮어 30분 뒤 모델이 내려갔다.

★지키려는 것
 ①식어 있으면 이번 요청은 곧바로 다음 경로(유료) — 고객 요청 안에서 적재를 기다리지 않는다 — 그리고 **뒤에서 예열 1회**를 시작한다
 ②예열은 기존 장치(`model_warmup.warmup` 의 중복 억제 · `OllamaChat.warm`)를 그대로 쓴다 — 조립 루트가 꽂는다(인프라는 도메인을 모른다)
 ③예열 실패 · 꽂히지 않음은 요청을 깨지 않는다(유료 답은 그대로)
 ④넘김이 꺼진 로컬 서빙(`OllamaChat` 그대로)은 다음 경로가 없다 — 식어 있으면 적재를 기다리는 고정 대기 호출로 답한다(10-26 이전 동작)
 ⑤같은 모델이면 일정 짚기도 해석과 같은 `keep_alive` — 다른 모델이면 일정 짚기 설정 그대로
"""
from __future__ import annotations

import json
import logging
import threading
import time
from types import SimpleNamespace

import pytest

from app.infrastructure import llm_failover
from app.infrastructure.llm_failover import CircuitBreaker, FailoverChat, _Backend
from app.infrastructure.ollama_chat import OllamaChat, OllamaError

SCHEMA = {"type": "object", "properties": {"action": {"type": "string", "enum": ["a", "b"]}}, "required": ["action"]}


@pytest.fixture(autouse=True)
def _clean():
    from app.domains.travel_ops.modules.live_progress import model_warmup

    saved = getattr(llm_failover, "_warm_starter", None)
    llm_failover.reset_state()
    model_warmup.reset()
    yield
    for _ in range(500):                                     # 앞 시험의 예열 스레드가 끝나야 다음 시험의 「한 번」이 맞다
        if not getattr(llm_failover, "_warm_running", False):
            break
        time.sleep(0.01)
    assert not getattr(llm_failover, "_warm_running", False)
    if hasattr(llm_failover, "register_warm_starter"):
        llm_failover.register_warm_starter(saved)
    llm_failover.reset_state()
    model_warmup.reset()


class Local:
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, *, up: bool):
        self.up, self.asked = up, 0

    def loaded(self, *, timeout=5.0):
        return self.up

    def structured_stream_validated(self, system, user, schema, *, validator, **kw):
        self.asked += 1
        return {"action": "a"}


class Paid:
    model = "paid"

    def __init__(self):
        self.asked = 0

    def loaded(self, *, timeout=5.0):
        return True

    def structured_stream_validated(self, system, user, schema, *, validator, **kw):
        self.asked += 1
        return {"action": "b"}


def chat_of(local, paid):
    clock = time.monotonic
    return FailoverChat([_Backend("ollama", local, CircuitBreaker("ollama", threshold=3, open_seconds=60, clock=clock), timeout=9.0),
                         _Backend("openai", paid, CircuitBreaker("openai", threshold=3, open_seconds=60, clock=clock), is_api=True,
                                  timeout=8.0)], total_seconds=15.0, sleep=lambda _s: None, clock=clock)


def _ask(chat):
    return chat.structured_stream_validated("sys", "고객 문장", SCHEMA, validator=lambda v: None, num_predict=400,
                                            first_wait=8.0, stall=5.0, max_seconds=15.0)


# ── ① · ③ 넘김 장치 ─────────────────────────────────────────────
def test_a_cold_local_model_goes_to_paid_and_starts_one_background_warm():
    started, seen = threading.Event(), []
    llm_failover.register_warm_starter(lambda chat: (seen.append(chat), started.set()))
    local, paid = Local(up=False), Paid()
    chat = chat_of(local, paid)
    assert _ask(chat) == {"action": "b"}
    assert started.wait(2.0) and seen == [chat]              # 화면 예열과 같은 대상 — `warm` 은 첫 Ollama 를 긴 제한시간으로 데운다
    assert local.asked == 0 and paid.asked == 1
    assert llm_failover.current_path()["reasons"] == [("ollama", "not_loaded")]


def test_the_request_does_not_wait_for_the_warm_to_finish():
    release, entered = threading.Event(), threading.Event()

    def slow(chat):
        entered.set()
        release.wait(5.0)                                    # 적재는 30초 넘게 걸린다 — 고객 요청은 기다리지 않는다

    llm_failover.register_warm_starter(slow)
    started = time.monotonic()
    try:
        assert _ask(chat_of(Local(up=False), Paid())) == {"action": "b"}
        assert time.monotonic() - started < 2.0
        assert entered.wait(2.0)
    finally:
        release.set()


def test_concurrent_cold_requests_start_only_one_warm_thread():
    release, calls = threading.Event(), []

    def slow(chat):
        calls.append(chat)
        release.wait(5.0)

    llm_failover.register_warm_starter(slow)
    chat = chat_of(Local(up=False), Paid())
    try:
        for _ in range(5):                                   # 예열이 도는 동안 온 식은 요청들은 스레드를 더 만들지 않는다
            assert _ask(chat) == {"action": "b"}
        time.sleep(0.05)
        assert len(calls) == 1
    finally:
        release.set()


def test_a_cold_secondary_ollama_does_not_warm():
    seen = []
    llm_failover.register_warm_starter(seen.append)
    clock = time.monotonic
    first, second, paid = Local(up=True), Local(up=False), Paid()
    first.structured_stream_validated = lambda *a, **k: (_ for _ in ()).throw(OllamaError("Ollama 호출 실패: ConnectError"))
    chat = FailoverChat([_Backend("ollama", first, CircuitBreaker("o1", threshold=3, open_seconds=60, clock=clock), timeout=9.0),
                         _Backend("ollama2", second, CircuitBreaker("o2", threshold=3, open_seconds=60, clock=clock), timeout=9.0),
                         _Backend("openai", paid, CircuitBreaker("p", threshold=3, open_seconds=60, clock=clock), is_api=True,
                                  timeout=8.0)], total_seconds=15.0, sleep=lambda _s: None, clock=clock)
    assert _ask(chat) == {"action": "b"}
    time.sleep(0.05)
    assert seen == []                                        # 예열은 첫 Ollama 만(`FailoverChat.warm` 과 같다)


def test_a_loaded_local_model_answers_without_any_warm():
    seen = []
    llm_failover.register_warm_starter(seen.append)
    local, paid = Local(up=True), Paid()
    assert _ask(chat_of(local, paid)) == {"action": "a"}
    time.sleep(0.05)
    assert seen == [] and paid.asked == 0


def test_a_failing_warm_starter_is_logged_and_never_breaks_the_answer(caplog):
    done = threading.Event()

    def broken(chat):
        done.set()
        raise RuntimeError("warm exploded")

    llm_failover.register_warm_starter(broken)
    with caplog.at_level(logging.WARNING, logger="app.llm_failover"):
        assert _ask(chat_of(Local(up=False), Paid())) == {"action": "b"}
        assert done.wait(2.0)
        for _ in range(100):
            if any("warm" in r.getMessage() for r in caplog.records):
                break
            time.sleep(0.01)
    assert any("warm" in r.getMessage() and "RuntimeError" in r.getMessage() for r in caplog.records)


def test_without_a_registered_starter_a_cold_model_still_goes_to_paid():
    llm_failover.register_warm_starter(None)
    assert _ask(chat_of(Local(up=False), Paid())) == {"action": "b"}


# ── ② 조립 루트가 꽂는 예열 = 기존 `model_warmup` 의 중복 억제 ────────────────
class Cold:
    model = "tripilot-pointer:e4b-ft"

    def __init__(self):
        self.warmed = 0

    def loaded(self, *, timeout=5.0):
        return False

    def warm(self):
        self.warmed += 1


def test_the_composition_root_plugs_the_existing_warmup_with_its_dedupe():
    import app.composition as composition

    llm_failover.register_warm_starter(None)
    composition._register_llm_failover()
    assert llm_failover._warm_starter is composition._llm_failover_warm
    chat = Cold()
    composition._llm_failover_warm(chat)
    composition._llm_failover_warm(chat)                     # 가드레일 `web_guard.warmup.dedupe_seconds` 안의 되풀이는 한 번으로
    assert chat.warmed == 1


def test_the_composition_warm_shares_the_web_warmup_dedupe_window(monkeypatch):
    import app.composition as composition
    from app.core import settings as settings_module
    from app.domains.travel_ops.modules.live_progress import model_warmup

    guard = settings_module.get_guardrails()
    assert float(guard.get("web_guard.warmup.dedupe_seconds")) > 0
    chat = Cold()
    model_warmup.warmup(chat, count=lambda: None, defer=lambda job: job(),
                        dedupe_seconds=float(guard.get("web_guard.warmup.dedupe_seconds")))      # 화면 예열이 막 시작했다
    composition._llm_failover_warm(chat)
    assert chat.warmed == 1


# ── ④ 넘김이 꺼진 로컬 서빙 ─────────────────────────────────────
def _bare(monkeypatch, *, loaded):
    chat = OllamaChat(base_url="http://ollama.test:11434", model="tripilot-pointer:e4b-ft", timeout=150.0)
    sent, streamed = [], []

    def post(url, payload):
        sent.append(payload)
        return SimpleNamespace(status_code=200, json=lambda: {"message": {"content": json.dumps({"action": "a"})}}, text="")

    chat._post = post
    if isinstance(loaded, BaseException):
        def probe(*, timeout=5.0):
            raise loaded
    else:
        def probe(*, timeout=5.0):
            return loaded
    monkeypatch.setattr(chat, "loaded", probe)
    monkeypatch.setattr(chat, "structured_stream",
                        lambda *a, **k: streamed.append(k) or {"action": "a"})
    return chat, sent, streamed


def test_without_failover_a_cold_model_is_awaited_with_the_fixed_wait_call(monkeypatch):
    chat, sent, streamed = _bare(monkeypatch, loaded=False)
    pieces, checked = [], []
    value = chat.structured_stream_validated("sys", "고객 문장", SCHEMA, validator=checked.append, num_predict=400,
                                             on_piece=pieces.append, first_wait=8.0, stall=5.0, max_seconds=15.0)
    assert value == {"action": "a"} and checked == [{"action": "a"}]
    assert streamed == [] and len(sent) == 1 and sent[0]["format"] == SCHEMA       # 같은 구조화 답 — 적재를 기다리는 한 번의 호출
    assert [json.loads(p) for p in pieces] == [{"action": "a"}]


def test_without_failover_a_loaded_model_keeps_streaming(monkeypatch):
    chat, sent, streamed = _bare(monkeypatch, loaded=True)
    chat.structured_stream_validated("sys", "고객 문장", SCHEMA, validator=lambda v: None, num_predict=400,
                                     first_wait=8.0, stall=5.0, max_seconds=15.0)
    assert sent == [] and streamed and streamed[0]["first_wait"] == 8.0


def test_failover_paths_never_take_the_cold_fixed_wait_branch(monkeypatch):
    settings = SimpleNamespace(llm_failover_enabled=True, openai_api_key_server="unit-key", llm_failover_failures=3,
                               llm_failover_open_seconds=60, ollama_timeout_seconds=150.0, llm_failover_primary_timeout_seconds=9.0,
                               ollama_fallback_base_urls="http://ollama2.test:11434", llm_failover_api_timeout_seconds=8.0,
                               llm_failover_model="paid", llm_model="paid", llm_failover_total_seconds=15.0,
                               llm_failover_vision=False)
    primary = OllamaChat(base_url="http://ollama.test:11434", model="tripilot-pointer:e4b-ft", timeout=150.0)
    chat = llm_failover.wrap_from_settings(primary, settings, budget=lambda: True, api_client=object())
    locals_ = [b.chat for b in chat._backends if not b.is_api]
    assert len(locals_) == 2 and all(c.wait_when_cold is False for c in locals_)   # 넘김 장치가 이미 `loaded` 를 본다 — 두 번 묻지 않는다
    assert primary.wait_when_cold is True                                           # 예열 · 넘김 꺼짐에서 쓰는 원래 클라이언트는 그대로


def test_a_failover_path_client_streams_without_asking_the_status_again(monkeypatch):
    chat, sent, streamed = _bare(monkeypatch, loaded=AssertionError("넘김 장치의 경로는 상태를 다시 묻지 않는다"))
    chat.wait_when_cold = False
    chat.structured_stream_validated("sys", "고객 문장", SCHEMA, validator=lambda v: None, num_predict=400,
                                     first_wait=8.0, stall=5.0, max_seconds=15.0)
    assert sent == [] and len(streamed) == 1


def test_without_failover_an_unanswerable_status_probe_keeps_streaming(monkeypatch):
    chat, sent, streamed = _bare(monkeypatch, loaded=OllamaError("Ollama 상태 조회 실패"))
    chat.structured_stream_validated("sys", "고객 문장", SCHEMA, validator=lambda v: None, num_predict=400,
                                     first_wait=8.0, stall=5.0, max_seconds=15.0)
    assert sent == [] and len(streamed) == 1


# ── ⑤ 같은 모델의 keep_alive ───────────────────────────────────
def _pointer_settings(**over):
    base = dict(ollama_pointer_model="tripilot-pointer:e4b-ft", ollama_base_url="http://ollama.test:11434",
                ollama_pointer_timeout_seconds=30.0, ollama_pointer_keep_alive="30m", ollama_pointer_background_warm=False,
                ollama_pointer_warm_timeout_seconds=180.0, ollama_num_ctx=8192, ollama_model="tripilot-pointer:e4b-ft",
                ollama_keep_alive="")
    base.update(over)
    return SimpleNamespace(**base)


@pytest.mark.parametrize("chat_keep_alive", ["", "-1", "2h"])
def test_a_pointer_sharing_the_interpreter_model_sends_the_interpreter_keep_alive(chat_keep_alive):
    from app.domains.travel_ops.components.conversation import item_pointer
    from app.domains.travel_ops.instances._shared import itinerary_team

    try:
        pointer = item_pointer.register_from_settings(_pointer_settings(ollama_keep_alive=chat_keep_alive))
        sent = []

        def post(url, payload, timeout):
            sent.append(payload.get("keep_alive"))
            return SimpleNamespace(status_code=200, json=lambda: {"message": {"content": '{"item": null}'}}, text="")

        pointer._post = post
        pointer._ask("prompt")
        assert pointer.keep_alive == chat_keep_alive and sent == [chat_keep_alive or None]
    finally:
        itinerary_team.set_item_pointer(None)


def test_a_separate_pointer_model_keeps_its_own_keep_alive():
    from app.domains.travel_ops.components.conversation import item_pointer
    from app.domains.travel_ops.instances._shared import itinerary_team

    try:
        pointer = item_pointer.register_from_settings(_pointer_settings(ollama_model="gemma4:12b", ollama_keep_alive="-1"))
        assert pointer.keep_alive == "30m"
    finally:
        itinerary_team.set_item_pointer(None)
