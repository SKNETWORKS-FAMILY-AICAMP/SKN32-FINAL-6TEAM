# -*- coding: utf-8 -*-
"""채팅 해석의 생성 문법(`decision_unit._schema(message=…)`)은 로컬 모델 전용이다 — 유료 넘김 경로에는 문장 없는 스키마만 간다. `[2026-10-26 L05 이식]`

☆왜: 생성 문법은 고객 문장(인용)을 `enum` 으로 싣는다. 넘김 장치는 유료 경로의 `user` 만 `masked` 로 가리고 스키마는 그대로 보낸다
  (L03 Codex P1 — 스키마 enum 의 원문은 가린 글 밖으로 나간다). 또 OpenAI 엄격 스키마는 최상위 `anyOf` 를 받지 않는다.

★지키려는 것
 ①로컬 경로는 생성 문법(문장 인용 enum)을 그대로 받는다
 ②유료 경로(스트림 · 고정 대기 모두)는 문장 · 일정 이름이 없는 객체 스키마를 받는다
 ③유료 답의 근거 검사(`edit_intent.validate`)는 그대로 — 인용 없는 시각 바꾸기는 유료 답이라도 성공이 아니다
 ④`api_schema` 를 모르는 모델(로컬만 · 시험 대역)에는 아무것도 더하지 않는다
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import decision_unit as du
from app.infrastructure import llm_failover
from app.infrastructure.llm_failover import CircuitBreaker, FailoverChat, _Backend
from app.infrastructure.model_stream import StreamStalled

KST = ZoneInfo("Asia/Seoul")
STREAM = {"first_token_seconds": 8, "stall_seconds": 5, "max_seconds": 12}
MESSAGE = "합성박물관 일정을 한 시간 뒤로 미뤄줘"
#: 이 고정 일정 · 문장으로 만든 로컬 생성 문법의 sha256 — 기준 922d628df 에서 잰 값(유료 갈래 추가 전)은 681483c6…947948a.
#: `[2026-10-27 G]` 읽기 항목 기준 칸 갈래(`decision_unit._shape_generation`)로 바뀐 값. 그 갈래를 빼면(항등) 옛 값 그대로임을 확인했다
#:  (보고서 2026-10-27 G · `ev/pincheck.py`) — 유료 갈래가 로컬 문법에 섞이지 않았다는 이 시험의 뜻은 그대로다.
#: `[2026-10-28 x600 4fee819c]` contract_correction: 한 일정 shift 의 절대 시각 갈래 2개(`edit_intent.generation_variants` — time_edit.time ·
#:  맨 위 anchor_time, 갈래 14개 중 2개)로 바뀐 값. 그 두 갈래를 빼면 옛 값 b36b43ea…259447833 그대로임을 확인했다
#:  (보고서 2026-10-28 timemove · `pincheck.py`) — 유료 갈래가 로컬 문법에 섞이지 않았다는 이 시험의 뜻은 그대로다.
GRAMMAR_SHA256 = "4be6948ec6ace1f9d93208e75063f2141fe244c6957e6ec8adac88d8172fdc89"


@pytest.fixture(autouse=True)
def _clean():
    llm_failover.reset_state()
    yield
    llm_failover.reset_state()


def _stop(alias, hour, title):
    item = SimpleNamespace(item_id=uuid4(), kind="activity", title=title, place={"name": title}, seq=int(alias[1:]),
                           starts_at=datetime(2030, 1, 2, hour, 0, tzinfo=KST), ends_at=None, locked=False, booking_id=None)
    return du.Stop(alias, item)


STOPS = [_stop("i1", 9, "합성박물관"), _stop("i2", 15, "가상공원")]


def _raw(evidence):
    return {"action": "change_time", "target_item": "i1", "target_change": "none", "fact": "none", "minutes": 60,
            "choices": [], "reads": [], "social": "", "general_requests": [], "destination_text": "", "condition_text": "",
            "anchor_kind": "none", "anchor_item": "none", "anchor_time": "", "at_day": "none", "relation": "at", "steps": 0,
            "time_edit": {"boundary": "shift", "scope": "item", "time": "", "duration_minutes": 0, "cascade": False,
                          "continue_previous": False, "evidence": evidence},
            "place_search": {"relation": "none", "anchor_item": "none", "place_text": "", "evidence": ""},
            "place_setting": {"want": "any", "evidence": ""}}


class Path:
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, *, stall=False, answer=None):
        self.stall, self.answer, self.schemas, self.users = stall, answer, [], []

    def loaded(self, *, timeout=5.0):
        return True

    def structured_stream_validated(self, system, user, schema, *, validator, num_predict=160, on_piece=None,
                                    first_wait=15.0, stall=5.0, max_seconds=180.0):
        self.schemas.append(schema)
        self.users.append(user)
        if self.stall:
            raise StreamStalled("모델 답 조각이 끊겼다(stall 5초)", which="stall")
        validator(dict(self.answer))
        return dict(self.answer)

    def structured(self, system, user, schema, *, num_predict=160):
        self.schemas.append(schema)
        self.users.append(user)
        if self.stall:
            raise StreamStalled("모델 답 조각이 끊겼다(stall 5초)", which="stall")
        return dict(self.answer)


def chat_of(local, paid):
    clock = time.monotonic
    backends = [_Backend("ollama", local, CircuitBreaker("ollama", threshold=3, open_seconds=60, clock=clock), timeout=9.0),
                _Backend("openai", paid, CircuitBreaker("openai", threshold=3, open_seconds=60, clock=clock), is_api=True, timeout=8.0)]
    return FailoverChat(backends, total_seconds=15.0, sleep=lambda _s: None, clock=clock)


def _text(schema):
    return json.dumps(schema, ensure_ascii=False)


@pytest.mark.parametrize("stream", [STREAM, None], ids=["stream", "fixed_wait"])
def test_the_paid_path_never_receives_the_message_grammar(stream):
    local, paid = Path(stall=True), Path(answer=_raw(MESSAGE))
    decision = du.decide(chat_of(local, paid), stops=STOPS, changes=[], history=[], selected_item_id=None,
                         message=MESSAGE, stream=stream)
    assert decision.action == "change_time"
    assert MESSAGE in _text(local.schemas[0])                  # ① 로컬 생성 문법은 문장 인용을 싣는다
    sent = paid.schemas[0]
    assert MESSAGE not in _text(sent)                          # ② 유료에는 문장이 없다
    assert all(s.item.title not in _text(sent) for s in STOPS)  # 일정 이름도 없다(별칭만)
    assert sent.get("type") == "object" and "anyOf" not in sent  # 엄격 스키마가 받는 객체 모양


def test_the_paid_schema_is_the_same_fields_without_generation_variants():
    plain = du._schema(STOPS, [], plain=True)
    grammar = du._schema(STOPS, [], message=MESSAGE)
    assert "anyOf" in grammar and "properties" not in grammar
    assert set(plain["required"]) <= set(plain["properties"])
    assert {"time_edit", "place_search", "place_setting", "action", "reads"} <= set(plain["required"])
    # 엄격 변환이 그대로 받는다(최상위 객체 · 모든 키 필수)
    strict = llm_failover.strict_schema(plain)
    assert strict["type"] == "object" and strict["additionalProperties"] is False


def test_a_paid_answer_without_its_quote_is_still_refused():
    local, paid = Path(stall=True), Path(answer=_raw("다른 문장"))
    with pytest.raises(du.DecisionFailed):
        du.decide(chat_of(local, paid), stops=STOPS, changes=[], history=[], selected_item_id=None,
                  message=MESSAGE, stream=STREAM)
    assert paid.schemas and MESSAGE not in _text(paid.schemas[0])


def test_a_model_without_api_schema_gets_the_grammar_only():
    seen = []

    class Only:
        def structured_validated(self, system, user, schema, *, validator, num_predict=160):
            seen.append(schema)
            validator(_raw(MESSAGE))
            return _raw(MESSAGE)

    du.decide(Only(), stops=STOPS, changes=[], history=[], selected_item_id=None, message=MESSAGE)
    assert len(seen) == 1 and MESSAGE in _text(seen[0])


def test_an_api_only_client_sends_the_plain_schema(monkeypatch):
    # ④' 넘김 장치 없이 유료 클라이언트만 꽂힌 조립에서도 생성 문법(문장 인용)은 나가지 않는다(Codex 지적)
    seen = []
    client = object.__new__(llm_failover.OpenAIChat)
    monkeypatch.setattr(client, "structured", lambda system, user, schema, *, num_predict=160: seen.append(schema) or _raw(MESSAGE),
                        raising=False)
    du.decide(client, stops=STOPS, changes=[], history=[], selected_item_id=None, message=MESSAGE)
    assert len(seen) == 1 and MESSAGE not in _text(seen[0]) and "anyOf" not in seen[0]


def test_range_shift_also_refuses_a_stale_goal_first():
    from app.domains.travel_ops.components.conversation import chat_edit, edit_intent

    decision = SimpleNamespace(raw={"stale_edit_goal": True, "time_edit": {"boundary": "shift", "scope": "range"}},
                               minutes=60, query={"day": "d1", "period": "all", "kind": "all", "position": "all"}, item=None)
    with pytest.raises(chat_edit.EditRefused) as refused:
        edit_intent.time_ops(decision, items=[s.item for s in STOPS], now=datetime(2030, 1, 1, 9, 0, tzinfo=KST))
    assert refused.value.code == "need_time_goal"


@pytest.mark.parametrize("message,quoted", [("1월 2일 일정 한 시간 미뤄줘", ["d1"]), ("11월 2일 일정 한 시간 미뤄줘", []),
                                            ("1월 22일 일정 한 시간 미뤄줘", [])])
def test_range_day_quotes_use_digit_boundaries(monkeypatch, message, quoted):
    from app.domains.travel_ops.components.conversation import edit_intent

    seen = {}
    real = edit_intent.generation_variants
    monkeypatch.setattr(edit_intent, "generation_variants",
                        lambda *a, **kw: seen.update(kw) or real(*a, **kw))
    du._schema(STOPS, [], message=message)
    assert [d for d in seen["quoted_days"] if d.startswith("d")] == quoted


# ── `[2026-10-26 x600 40231a56]` 유료 스키마의 시간 수정 조합 ──
#   x600 Case 72e29b8c: 로컬 timeout 뒤 유료 답이 `evidence_validation:inconsistent_temporal_scope` 로 떨어졌다. 로컬 생성 문법은 갈래로
#   경계(boundary)와 범위(scope)의 맞는 조합만 생성하게 하는데, 유료 스키마는 두 칸을 따로 둬 실행할 수 없는 조합(start + following 등)을 낼 수 있었다.
#   최상위가 아닌 `time_edit` 칸 안의 anyOf 는 엄격 모드가 받는다 — 같은 조합 규칙을 유료 스키마에도 싣는다(문장 · 이름 없음).
def _edit(boundary, scope, **over):
    return {"boundary": boundary, "scope": scope, "time": "", "duration_minutes": 0, "cascade": False,
            "continue_previous": False, "evidence": "", **over}


@pytest.mark.parametrize("edit,ok", [
    (_edit("none", "item"), True),
    (_edit("start", "item", time="17:30"), True),
    (_edit("end", "item", time="17:30", cascade=True), True),
    (_edit("duration", "item", duration_minutes=90), True),
    (_edit("shift", "item"), True),
    (_edit("shift", "following"), True),
    (_edit("shift", "range"), True),
    (_edit("reflow", "following"), True),
    (_edit("reflow", "following", continue_previous=True), True),
    (_edit("start", "following", time="17:30"), False),
    (_edit("start", "range", time="17:30"), False),
    (_edit("end", "following", time="17:30"), False),
    (_edit("duration", "range", duration_minutes=60), False),
    (_edit("reflow", "item"), False),
    (_edit("reflow", "range"), False),
    (_edit("shift", "item", continue_previous=True), False),
    (_edit("start", "item", time="17:30", continue_previous=True), False),
    (_edit("shift", "range", time="17:30"), False),
    (_edit("shift", "range", cascade=True), False),
], ids=lambda v: v if isinstance(v, bool) else f"{v['boundary']}-{v['scope']}-{v['continue_previous']}-{v['time'] or '_'}-{v['cascade']}")
def test_the_paid_schema_only_admits_executable_time_edit_combinations(edit, ok):
    from jsonschema import Draft202012Validator

    from app.domains.travel_ops.components.conversation.edit_intent import _inconsistent

    plain = du._schema(STOPS, [], plain=True)
    for shape in (plain, llm_failover.strict_schema(plain)):   # 우리 스키마 · 엄격 변환 모두
        valid = Draft202012Validator(shape["properties"]["time_edit"]).is_valid(edit)
        assert valid is ok, (edit, shape is plain)
    # 받는 조합은 서버 검증(`_inconsistent`)도 받는다 — 유료 스키마가 서버보다 넓지 않다
    if ok:
        assert not _inconsistent(edit)


def test_the_paid_time_edit_variants_stay_free_of_the_message_and_the_root_stays_an_object():
    plain = du._schema(STOPS, [], plain=True)
    strict = llm_failover.strict_schema(plain)
    assert "anyOf" not in plain and "anyOf" not in strict and strict["type"] == "object"
    assert "anyOf" in strict["properties"]["time_edit"]
    for variant in strict["properties"]["time_edit"]["anyOf"]:
        assert variant["additionalProperties"] is False and sorted(variant["required"]) == sorted(variant["properties"])
    assert MESSAGE not in _text(plain) and all(s.item.title not in _text(plain) for s in STOPS)


def test_the_local_grammar_is_unchanged_by_the_paid_variants():
    """로컬 생성 문법(`message=…`)의 바이트는 그대로다 — 유료 갈래는 `plain=True` 에만 붙는다."""
    import hashlib

    grammar = json.dumps(du._schema(STOPS, [], message=MESSAGE), ensure_ascii=False, sort_keys=True)
    plain_edit = du._schema(STOPS, [], plain=True)["properties"]["time_edit"]
    assert json.dumps(plain_edit, ensure_ascii=False) not in grammar
    assert hashlib.sha256(grammar.encode()).hexdigest() == GRAMMAR_SHA256
