# -*- coding: utf-8 -*-
"""계획 읽기 — 남은 줄을 **한 번에** 보내고 답을 **조금씩 받으며** 멈춤을 본다. `[2026-10-16 2회차 합의 · 사용자 승인]`

☆왜: 고정 한도(로컬 9초 · 유료 8초)로는 긴 계획의 정상 답(12~27초)도 끊겼고, 유료 답은 600토큰에 잘렸다. 앞 판(8줄 묶음 · 실패한 묶음만 유료 ·
  상한을 넘으면 남은 줄)은 한 계획을 두 모델이 섞어 읽고 줄을 버려 사용자가 반대했다. 실측 근거 `wiki/records/reports/2026-10-16_계획읽기_묶음나누기.md`.

★지키려는 것
 ①조각 감시(`model_stream.collect`) — 첫 조각 · 조각 사이 · 맨 위 상한을 따로 보고, 넘으면 연결을 닫고 「시간 초과」로 올린다
 ②한 답은 한 경로가 끝까지 — 로컬이 멈추거나 모델이 안 올라와 있으면 **유료가 처음부터** 읽는다(받다 만 로컬 답은 쓰지 않는다)
 ③유료 답 상한은 부르는 쪽이 정한다(줄 수로) · 상한에 걸려 잘리면 모양 오류
 ④보내는 줄 번호는 목록 안 순서(1부터) · 답은 원래 줄로 되돌린다 · 원문에 글자 그대로 없는 인용은 버린다
 ⑤진행 알림은 원문 검사를 통과한 서로 다른 줄 수 / 보낸 줄 수 — 경로가 바뀌면 `reading_api` 로 0 부터
 ⑥끝내 못 읽으면 숨기지 않는다 — `ReadingFailed` → 접수 「읽기 실패」(`reading_model_failed`)
"""
from __future__ import annotations

from datetime import date, datetime
import json
import threading
import time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import pipeline
from app.domains.travel_ops.components.intake.llm_spans import ReadingFailed, label_lines, output_budget
from app.infrastructure import llm_failover
from app.infrastructure.llm_failover import CircuitBreaker, FailoverChat, ModelNotLoaded, OpenAIChat, _Backend, classify
from app.infrastructure.model_stream import StreamStalled, collect
from app.infrastructure.ollama_chat import OllamaChat, OllamaContentError, OllamaError

PLACES = ["경복궁", "광장시장", "북촌한옥마을", "남산타워", "망원시장", "서울숲"]
LINES = ["1일차 10월 20일", *[f"오후엔 {p} 가 보고 싶어" for p in PLACES[:3]], "2일차 10월 21일", *[f"오후엔 {p} 가 보고 싶어" for p in PLACES[3:]]]
UNREAD = [2, 3, 4, 6, 7, 8]
STREAM = {"first_token_seconds": 15, "stall_seconds": 5, "max_seconds": 120, "progress_seconds": 0,
          "output_tokens_base": 1024, "output_tokens_per_line": 30, "output_tokens_per_char": 2}


@pytest.fixture(autouse=True)
def _clean():
    llm_failover.reset_state()
    yield
    llm_failover.reset_state()


def answer_for(user: str) -> dict:
    rows = [row.split(": ", 1) for row in user.splitlines()]
    return {"spans": [{"line": int(n), "quote": next(p for p in PLACES if p in text), "role": "place"} for n, text in rows]}


# ── ① 조각 감시 ─────────────────────────────────────────────
def test_collect_gathers_pieces_and_reports_the_text_so_far():
    seen = []
    out = collect(lambda: iter(["{\"a\"", ": 1", "}"]), first_wait=1, stall=1, max_seconds=5, on_piece=seen.append)
    assert out == '{"a": 1}' and seen == ['{"a"', '{"a": 1', '{"a": 1}']


def _slow(first: float, then: list[float]):
    def pieces():
        time.sleep(first)
        yield "a"
        for gap in then:
            time.sleep(gap)
            yield "b"
    return pieces


@pytest.mark.parametrize(("pieces", "which"), [
    (_slow(0.6, []), "first"),            # 첫 조각이 안 온다
    (_slow(0.0, [0.05, 0.6]), "stall"),   # 오다가 끊긴다
    (_slow(0.0, [0.1] * 30), "max"),      # 조각은 오지만 끝이 없다(되풀이)
])
def test_collect_stops_on_each_clock_and_closes_the_connection(pieces, which):
    closed = threading.Event()
    with pytest.raises(StreamStalled) as caught:
        collect(pieces, first_wait=0.3, stall=0.3, max_seconds=1.0, close=closed.set)
    assert caught.value.which == which and closed.is_set()
    assert classify(caught.value).reason == "timeout"                    # 넘김 장치가 「시간 초과」로 센다


def test_collect_raises_the_producer_error_and_a_broken_listener_does_not_stop_it():
    def boom():
        yield "x"
        raise OllamaError("HTTP 503")

    with pytest.raises(OllamaError, match="503"):
        collect(boom, first_wait=1, stall=1, max_seconds=2, on_piece=lambda _t: 1 / 0)


# ── ② 넘김: 한 답은 한 경로가 끝까지 ─────────────────────────────
class Local:
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, *, up=True, stall=False):
        self.up, self.stall, self.asked = up, stall, []

    def loaded(self, *, timeout=5.0):
        return self.up

    def json_stream(self, system, user, *, on_piece=None, **kw):
        self.asked.append(user)
        text = json.dumps(answer_for(user), ensure_ascii=False)
        on_piece(text[:30])
        if self.stall:
            raise StreamStalled("모델 답 조각이 끊겼다(stall 5초)", which="stall")
        on_piece(text)
        return answer_for(user)


class Paid(Local):
    def loaded(self, *, timeout=5.0):
        return True


def chat_of(local, paid, *, clock=time.monotonic):
    backends = [_Backend("ollama", local, CircuitBreaker("ollama", threshold=3, open_seconds=60, clock=clock), timeout=9.0),
                _Backend("openai", paid, CircuitBreaker("openai", threshold=3, open_seconds=60, clock=clock), is_api=True, timeout=8.0,
                         reader_budget=lambda: True)]
    return FailoverChat(backends, total_seconds=15.0, sleep=lambda _s: None, clock=clock)


def test_a_local_stall_restarts_the_whole_answer_on_the_paid_model():
    local, paid = Local(stall=True), Paid()
    pieces = []
    out = chat_of(local, paid).json_stream("sys", "1: 오후엔 경복궁 가 보고 싶어", on_piece=lambda t, path: pieces.append(path))
    assert out == answer_for("1: 오후엔 경복궁 가 보고 싶어")
    assert pieces[0] == "local" and pieces[-1] == "api" and pieces.count("local") == 1   # 로컬 조각 하나 받다 멈춤 → 유료가 처음부터
    assert local.asked and paid.asked                                                   # 둘 다 같은 글 전체를 받았다
    assert llm_failover.current_path()["path"] == "api" and llm_failover.current_path()["reasons"] == [("ollama", "timeout")]


def test_a_cold_local_model_goes_straight_to_paid_without_tripping_the_breaker():
    local, paid = Local(up=False), Paid()
    chat = chat_of(local, paid)
    chat.json_stream("sys", "1: 오후엔 경복궁 가 보고 싶어", on_piece=lambda t, p: None)
    assert local.asked == [] and paid.asked
    assert llm_failover.current_path()["reasons"] == [("ollama", "not_loaded")]
    assert chat._backends[0].breaker.snapshot()["failures"] == 0
    assert classify(ModelNotLoaded("x")).counts is False


def test_reader_paid_restart_stays_blocked_when_explicitly_disabled():
    """`[2026-10-26 L03]` 계획 읽기 입구(`reader_json_stream`)는 유료 대체를 끈 설정이면 로컬이 멈춰도 유료로 다시 읽지 않는다(유료 0회)."""
    from app.infrastructure.ollama_chat import OllamaError
    local, paid = Local(stall=True), Paid()
    with pytest.raises(OllamaError, match="reader_external_disabled"):
        chat_of(local, paid).reader_json_stream("sys", "1: 오후엔 경복궁 가 보고 싶어", on_piece=lambda t, path: None,
                                                external_fallback_enabled=False)
    assert local.asked and paid.asked == []
    assert ("openai", "reader_external_disabled") in llm_failover.current_path()["reasons"]


def test_reader_external_fallback_is_on_by_default_in_guardrails(monkeypatch):
    """`[2026-10-26 08:20 사용자 결정]` 계획 읽기 유료 대체는 끄지 않는다 — D-025 원래 계약(로컬이 조각 감시 5초로 멈추면 유료가 처음부터 읽는다).
    가드레일 기본은 켜짐이고, 관리 콘솔 값(false)이 있으면 그것이 먼저다."""
    from app.domains.travel_ops.components import settings_hook
    from app.domains.travel_ops.components.intake import pipeline
    monkeypatch.setattr(settings_hook, "operator_setting", lambda tenant_id, name: None)
    assert pipeline.agent_reader_config("t")["external_fallback_enabled"] is True
    monkeypatch.setattr(settings_hook, "operator_setting",
                        lambda tenant_id, name: False if name == "travel.intake_reader.external_fallback_enabled" else None)
    assert pipeline.agent_reader_config("t")["external_fallback_enabled"] is False


def test_reader_paid_restart_runs_only_when_explicitly_enabled():
    local, paid = Local(stall=True), Paid()
    pieces = []
    out = chat_of(local, paid).reader_json_stream("sys", "1: 오후엔 경복궁 가 보고 싶어", on_piece=lambda t, path: pieces.append(path),
                                                  external_fallback_enabled=True)
    assert out == answer_for("1: 오후엔 경복궁 가 보고 싶어")
    assert pieces[0] == "local" and pieces[-1] == "api" and local.asked and paid.asked


# ── ③ 유료 답 상한 ─────────────────────────────────────────
class FakeStream:
    def __init__(self, pieces, finish):
        self.pieces, self.finish, self.closed = pieces, finish, False

    def __iter__(self):
        for index, piece in enumerate(self.pieces):
            last = index == len(self.pieces) - 1
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=piece), finish_reason=self.finish if last else None)])

    def close(self):
        self.closed = True


def paid_with(pieces, finish="stop"):
    sent = {}

    class Completions:
        def create(self, **kwargs):
            sent.update(kwargs)
            return FakeStream(pieces, finish)

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    return OpenAIChat(api_key="sk-test", model="gpt-6-luna", client=client), sent


def test_paid_stream_uses_the_callers_output_budget_and_rejects_a_cut_answer():
    chat, sent = paid_with(['{"spans": [', "]}"])
    assert chat.json_stream("sys", "1: x", max_tokens=2160) == {"spans": []}
    assert sent["stream"] is True and sent["max_completion_tokens"] == 2160 and sent["reasoning_effort"] == "none"
    cut, _ = paid_with(['{"spans": [{"line": 1'], finish="length")
    with pytest.raises(OllamaContentError, match="잘렸다"):
        cut.json_stream("sys", "1: x", max_tokens=600)


def test_an_injected_local_transport_falls_back_to_one_answer():
    body = {"message": {"content": '{"spans": []}'}}
    chat = OllamaChat(base_url="http://x", model="m", transport=lambda url, payload: SimpleNamespace(status_code=200, json=lambda: body, text=""))
    seen = []
    assert chat.json_stream("sys", "1: x", on_piece=seen.append) == {"spans": []} and seen == ['{"spans": []}']


def test_output_budget_grows_with_the_lines_and_characters_sent():
    assert output_budget(6, 84, STREAM) == 1024                      # 짧은 글은 바닥
    assert output_budget(54, 971, STREAM) == 3562 and output_budget(22, 550, STREAM) == 1760   # 시험지 L4 · L6(실측 답 1,509 · 1,107토큰)
    assert output_budget(54, 971, None) == 0


# ── ④⑤ 줄 읽기 · 진행 ───────────────────────────────────────
class Streamer:
    """조금씩 주는 모델(시험용) — 로컬로 반쯤 주다가 유료로 처음부터 다시 줄 수 있다."""

    def __init__(self, *, switch=False, extra=()):
        self.switch, self.extra, self.users, self.kw = switch, list(extra), [], {}

    def json_stream(self, system, user, *, on_piece=None, **kw):
        self.users.append(user)
        self.kw = kw
        answer = answer_for(user)
        answer["spans"] += self.extra
        text = json.dumps(answer, ensure_ascii=False)
        if self.switch:
            on_piece(text[: len(text) // 2], "local")
        for cut in range(20, len(text) + 20, 20):
            on_piece(text[:cut], "api" if self.switch else "local")
        return answer


def test_lines_go_out_numbered_from_one_and_answers_land_on_their_original_lines():
    chat = Streamer()
    _, items, report = label_lines(LINES, UNREAD, chat, stream=STREAM)
    assert [row.split(":")[0] for row in chat.users[0].splitlines()] == ["1", "2", "3", "4", "5", "6"]
    assert [(i.line, i.title.text) for i in items] == list(zip(UNREAD, PLACES))
    assert chat.kw == {"first_wait": 15.0, "stall": 5.0, "max_seconds": 120.0, "max_tokens": 1024}
    assert report["accepted"] == 6 and report["rejected"] == [] and report["output_tokens"] == 1024


def test_progress_counts_lines_whose_quote_is_in_the_original_and_restarts_on_the_paid_model():
    events = []
    label_lines(LINES, UNREAD, Streamer(switch=True, extra=[{"line": 1, "quote": "광잔시장", "role": "place"}]), stream=STREAM,
                on_progress=events.append)
    assert events[0] == {"phase": "reading", "done": 0, "total": 6}
    phases = [e["phase"] for e in events]
    assert "reading" in phases and phases[-1] == "reading_api" and phases.index("reading_api") > 0
    api = [e["done"] for e in events if e["phase"] == "reading_api"]
    assert api[0] < api[-1] == 6 and api == sorted(api)                                  # 유료로 바뀌면 처음부터 다시 센다
    assert events[-1] == {"phase": "reading_api", "done": 6, "total": 6, "final": True}  # 「광잔시장」(원문에 없음)은 세지 않는다


def test_progress_is_throttled_to_the_configured_interval():
    events, now = [], [0.0]
    label_lines(LINES, UNREAD, Streamer(), stream={**STREAM, "progress_seconds": 5}, on_progress=events.append, clock=lambda: now[0])
    assert [e.get("final") for e in events] == [None, True]                            # 시계가 안 가면 시작 · 끝만


def test_an_answer_in_original_numbers_still_lands_on_its_line():
    class Old:
        def json(self, system, user):
            return {"spans": [{"line": 2, "quote": "경복궁", "role": "place"}, {"line": 3, "quote": "광장시장", "role": "place"}]}

    _, items, report = label_lines(LINES, [2, 3], Old())
    assert [(i.line, i.title.text) for i in items] == [(2, "경복궁"), (3, "광장시장")] and report["rejected"] == []


# ── ⑥ 끝내 못 읽으면 드러낸다 ────────────────────────────────
class Down:
    def json_stream(self, *a, **kw):
        raise OllamaError("모든 모델 경로가 실패했다: ollama=timeout, openai=timeout")

    def json(self, *a, **kw):
        raise OllamaError("down")


def test_a_failed_model_raises_instead_of_leaving_lines_quietly_unread():
    with pytest.raises(ReadingFailed, match="모든 모델 경로가 실패했다"):
        label_lines(LINES, UNREAD, Down(), stream=STREAM)


def test_read_source_turns_a_failed_model_into_a_reading_failure_the_customer_sees():
    with pytest.raises(pipeline.IntakeRejected) as caught:
        pipeline.read_source("\n".join(LINES), chat=Down(), today=date(2026, 10, 16),
                             now=datetime(2026, 10, 16, 9, tzinfo=ZoneInfo("Asia/Seoul")), reading_stream=STREAM)
    assert caught.value.code == "reading_model_failed" and caught.value.message == pipeline.READING_FAILED_TEXT


def test_read_source_reads_the_stream_settings_from_the_guardrails():
    assert pipeline._reading_stream(None) == {"first_token_seconds": 15, "stall_seconds": 5, "max_seconds": 120, "progress_seconds": 5,
                                              "output_tokens_base": 1024, "output_tokens_per_line": 30, "output_tokens_per_char": 2,
                                              "api_reserve_seconds": 30}   # [2026-10-26 x600 74b2b232] 유료 대체 몫 추가
    assert pipeline._reading_stream(STREAM) is STREAM


# ── 읽기 에이전트(D-025)도 같은 장치 — 묶음이 여럿이어도 한 계획은 한 모델 ────────────────
from app.domains.travel_ops.components.intake import agent_read  # noqa: E402

AGENT_LINES = [f"{h:02d}:00 장소{h}" for h in range(8, 20)]
AGENT_TEXT = "\n".join(AGENT_LINES)


class AgentStream:
    """조금씩 주는 에이전트 모델(시험용) — `api_from` 번째 호출부터 유료로 답한 것처럼 경로를 남긴다. 받은 `api_only` 를 기록한다."""

    model = "tripilot-pointer:e4b-ft"

    def __init__(self, api_from=None):
        self.api_from, self.calls = api_from, []

    def structured_stream(self, system, user, schema, *, num_predict, on_piece, first_wait, stall, max_seconds, api_only=False):
        self.calls.append(api_only)
        path = "api" if api_only or (self.api_from is not None and len(self.calls) >= self.api_from) else "local"
        llm_failover._path_var.set({"path": path, "backend": None, "op": "structured_stream", "reasons": [], "seconds": 0.1})
        got = [line.split(" ", 1) for line in user.splitlines() if " " in line]
        answer = {"items": [{"place_quote": place, "day": 1, "date": None, "date_quote": None, "start": clock, "end": None,
                             "time_quote": clock, "kind": "activity"} for clock, place in got]}
        text = json.dumps(answer, ensure_ascii=False)
        for cut in range(30, len(text) + 30, 30):
            on_piece(text[:cut], path)
        return answer


def test_the_agent_streams_with_the_reading_settings_and_reports_lines_read():
    events = []
    chat = AgentStream()
    out = agent_read.read(AGENT_TEXT, AGENT_LINES, chat, today=date(2026, 10, 16), stream=STREAM, on_progress=events.append)
    assert chat.calls == [False] and [i.title.text for i in out.items] == [f"장소{h}" for h in range(8, 20)]
    assert events[0] == {"phase": "reading", "done": 0, "total": 12}
    assert events[-1] == {"phase": "reading", "done": 12, "total": 12, "final": True}
    dones = [e["done"] for e in events]
    assert dones == sorted(dones) and len(set(dones)) > 2


def test_when_a_later_chunk_falls_back_to_paid_the_whole_plan_is_read_again_by_paid():
    events = []
    chat = AgentStream(api_from=2)                     # 첫 묶음은 로컬, 둘째 묶음에서 유료로 넘어갔다
    out = agent_read.read(AGENT_TEXT, AGENT_LINES, chat, today=date(2026, 10, 16), chunk_chars=60, stream=STREAM,
                          on_progress=events.append)
    chunks = out.report["chunks"]
    assert chunks > 2 and chat.calls == [False, False] + [True] * chunks           # 첫 묶음부터 유료만으로 다시
    assert out.report["restarted_on_api"] is True and all(p["path"] == "api" for p in out.report["paths"])
    assert [i.title.text for i in out.items] == [f"장소{h}" for h in range(8, 20)]   # 다시 읽어도 두 번 세지 않는다
    assert events[-1] == {"phase": "reading_api", "done": 12, "total": 12, "final": True}
    assert "reading_api" in [e["phase"] for e in events] and events[0]["phase"] == "reading"


def test_when_the_first_chunk_is_paid_the_rest_stay_paid_without_restarting():
    chat = AgentStream(api_from=1)
    out = agent_read.read(AGENT_TEXT, AGENT_LINES, chat, today=date(2026, 10, 16), chunk_chars=60, stream=STREAM)
    assert chat.calls == [False] + [True] * (out.report["chunks"] - 1) and "restarted_on_api" not in out.report


def test_without_stream_settings_the_agent_keeps_the_old_one_shot_call():
    class Plain:
        model = "m"

        def __init__(self):
            self.calls = 0

        def structured(self, system, user, schema, *, num_predict=160):
            self.calls += 1
            return {"items": []}

    chat = Plain()
    agent_read.read(AGENT_TEXT, AGENT_LINES, chat, today=date(2026, 10, 16))
    assert chat.calls == 1


def test_failover_structured_stream_skips_local_when_asked_for_paid_only():
    class LocalS(Local):
        def structured_stream(self, system, user, schema, **kw):
            self.asked.append(user)
            return {"items": []}

    local, paid = LocalS(), LocalS()
    paid.loaded = lambda timeout=5.0: True
    chat = chat_of(local, paid)
    assert chat.structured_stream("sys", "x", {"type": "object"}, api_only=True) == {"items": []}
    assert local.asked == [] and paid.asked == ["x"]
    assert llm_failover.current_path()["reasons"] == [("ollama", "skipped")] and chat._backends[0].breaker.snapshot()["failures"] == 0
