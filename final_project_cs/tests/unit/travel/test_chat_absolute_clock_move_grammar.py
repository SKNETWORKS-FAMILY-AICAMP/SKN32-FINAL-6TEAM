# -*- coding: utf-8 -*-
"""채팅 「오후 5시 30분으로 옮겨줘」 — 로컬 생성 문법이 절대 시각을 낼 칸을 남기는가. `[2026-10-28 x600 4fee819c]`

☆x600 로컬 E4B 원출력(Case 10108fc5 · 14dd1f31 · 5a96697a, `customer_cases.state_json->decision->raw`)은 3/3 이 같은 모양이었다:
  action=change_time · time_edit.boundary=shift · scope=item · time="" · anchor_time="" · minutes=30.
  모델은 「옮겨줘」를 상대 이동(shift)으로 골랐고, L05 생성 문법(`edit_intent.generation_variants`, 53a116f0)이 shift 갈래의
  time · anchor_time 을 빈 문자열로 묶어 둬 시각을 어디에도 낼 수 없었다. 서버는 시각 안의 「30분」을 이동 크기로 세지 않으므로
  (`spoken_minutes`, c286b906) minutes=None → `chat_edit` need_time 되묻기였다.
  c286b906 은 「shift · scope=item · 검증된 time」을 새 시작으로 실행하는 계약(`time_ops`)을 이미 갖고 있다 — 문법이 그 답을 막았을 뿐이다.

★고친 뒤 지키는 것(생성 문법만 — 문장을 읽지 않고 답을 고쳐 쓰지 않는다)
 ①shift · item 갈래는 시각 없이(time="", minutes≠0), 인용된 절대 시각(time=HH:MM, minutes=0), 또는 맨 위 시작 시각 칸
   (anchor_kind=time · relation=at · anchor_time=HH:MM, minutes=0)으로 낼 수 있다. ☆로컬 실 E4B 는 time 갈래만 열었을 때 2/2 가 여전히
   time="" · minutes=30 이었고, 맨 위 칸을 연 뒤 1/1 이 anchor_time=17:30 을 냈다(보고서 2026-10-28 timemove, `e4b/live-c2-1.json`)
 ②상대 이동 크기와 절대 시각을 함께 낼 수 없다(기존 v7 계약 `test_generation_cannot_combine_relative_delta_and_absolute_boundary`)
 ③range 갈래에는 시각을 낼 수 없다(following 갈래는 L05 부터 원래 모양 그대로 — 이번 변경 밖)
 ④시각 값은 `edit_intent.validate` 가 인용으로 재계산해 확인한다(인용과 다르면 해석 실패) — 맨 위 칸의 시각도 같은 검사
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import jsonschema
import pytest

from app.domains.travel_ops.components.conversation import decision_unit as du
from app.domains.travel_ops.components.conversation import edit_intent
from app.domains.travel_ops.components.conversation.chat_edit import EditRefused, ops_for
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 1, 9, tzinfo=KST)
ALIASES = {"none", "i1", "i2", "i3"}


def _items():
    rows = [("북촌한옥마을", 10, 0, 11, 30), ("광장시장", 12, 30, 13, 30), ("N서울타워", 19, 0, 20, 0)]
    return [Item(item_id=uuid4(), place_id=None, seq=n + 1, kind="activity", title=title,
                 starts_at=datetime(2030, 1, 2, sh, sm, tzinfo=KST), ends_at=datetime(2030, 1, 2, eh, em, tzinfo=KST))
            for n, (title, sh, sm, eh, em) in enumerate(rows)]


def _raw(message, *, boundary="shift", scope="item", time="", minutes=0, relation="at", target="i1", anchor_kind="none",
         anchor_time=""):
    """x600 원출력과 같은 칸 모양(서버 기록 `decision.raw`)."""
    return {"fact": "none", "reads": [], "steps": 1, "action": "change_time", "at_day": "none", "social": "", "choices": [],
            "minutes": minutes, "relation": relation,
            "time_edit": {"time": time, "scope": scope, "cascade": False, "boundary": boundary, "evidence": message,
                          "duration_minutes": 0, "continue_previous": False},
            "anchor_item": "none", "anchor_kind": anchor_kind, "anchor_time": anchor_time, "target_item": target,
            "place_search": {"evidence": "", "relation": "none", "place_text": "", "anchor_item": "i1"},
            "place_setting": {"want": "any", "evidence": ""}, "target_change": "none", "condition_text": "",
            "destination_text": "", "general_requests": []}


def _schema(items, message):
    return du._schema(du.stops_of(items), [], message=message)


class _GrammarBoundModel:
    """받은 생성 문법을 지키는 답만 내는 가짜 모델 — 문법이 막는 답은 낼 수 없다(ValidationError)."""

    def __init__(self, raw):
        self.raw = raw
        self.schemas = []

    def structured(self, system, user, schema, **_options):
        self.schemas.append(schema)
        jsonschema.validate(self.raw, schema)
        return dict(self.raw)


X600 = [  # (문장, x600 Case, 원출력 relation) — 3건 모두 shift · item · time="" · minutes=30
    ("오후 5시 30분으로 옮겨줘", "10108fc5", "before"),
    ("오후 5시 30분으로 옮겨줘", "14dd1f31", "before"),
    ("17:30으로 옮겨줘", "5a96697a", "at"),
]


@pytest.mark.parametrize("message,case,relation", X600)
def test_recorded_x600_raw_has_no_clock_and_asks_need_time(message, case, relation):
    """원인 기록: 그 원출력은 문법 안의 답이고, 시각 칸이 비어 서버는 need_time 으로 되묻는다(서버가 칸을 못 읽은 것이 아니다)."""
    items = _items()
    raw = _raw(message, minutes=30, relation=relation)
    model = _GrammarBoundModel(raw)
    got = du.decide(model, stops=du.stops_of(items), changes=[], history=[], selected_item_id=items[0].item_id, message=message, now=NOW)
    assert got.action == "change_time" and got.item.item_id == items[0].item_id and got.minutes is None
    with pytest.raises(EditRefused) as refused:
        ops_for(got, items=items, now=NOW, message=message)
    assert refused.value.code == "need_time"


@pytest.mark.parametrize("message", ["오후 5시 30분으로 옮겨줘", "17:30으로 옮겨줘"])
def test_shift_item_branch_can_carry_the_quoted_absolute_clock(message):
    """RED(4fee819c): shift · item 갈래가 time 을 빈 문자열로 묶어 「17:30」을 낼 수 없었다."""
    items = _items()
    raw = _raw(message, time="17:30", minutes=0)
    jsonschema.validate(raw, _schema(items, message))


@pytest.mark.parametrize("message", ["오후 5시 30분으로 옮겨줘", "17:30으로 옮겨줘"])
def test_absolute_clock_move_runs_end_to_end_keeping_the_stay(message):
    items = _items()
    model = _GrammarBoundModel(_raw(message, time="17:30", minutes=0))
    got = du.decide(model, stops=du.stops_of(items), changes=[], history=[], selected_item_id=items[0].item_id, message=message, now=NOW)
    assert got.action == "change_time" and got.item.item_id == items[0].item_id and got.minutes is None
    ops, _ = ops_for(got, items=items, now=NOW, message=message)
    assert [(o.item_id, o.date, o.starts_at, o.ends_at) for o in ops] == [(items[0].item_id, "2030-01-02", "17:30", "19:00")]


def test_relative_delta_and_absolute_clock_still_cannot_combine():
    items = _items()
    message = "오후 5시 30분으로 옮겨줘"
    assert not jsonschema.Draft202012Validator(_schema(items, message)).is_valid(_raw(message, time="17:30", minutes=30))


def test_relative_shift_without_clock_is_still_generated_and_moves_by_the_spoken_size():
    items = _items()
    message = "30분 늦춰줘"
    model = _GrammarBoundModel(_raw(message, time="", minutes=30))
    got = du.decide(model, stops=du.stops_of(items), changes=[], history=[], selected_item_id=items[0].item_id, message=message, now=NOW)
    assert got.minutes == 30
    ops, _ = ops_for(got, items=items, now=NOW, message=message)
    assert [(o.starts_at, o.ends_at) for o in ops] == [("10:30", "12:00")]


@pytest.mark.parametrize("scope", ["range"])
def test_clock_stays_impossible_on_range_shifts(scope):
    items = _items()
    message = "17:30으로 옮겨줘"
    raw = _raw(message, scope=scope, time="17:30", minutes=0, target="none" if scope == "range" else "i1")
    if scope == "following":
        raw["anchor_item"] = "i1"
    else:
        raw["query"] = {"day": "all", "period": "all", "kind": "all", "position": "all"}
    assert not jsonschema.Draft202012Validator(_schema(items, message)).is_valid(raw)


def test_clock_must_still_match_the_quote():
    """문법은 HH:MM 모양만 묶는다 — 인용과 다른 시각은 `validate` 가 거절한다(해석 실패, 저장 없음)."""
    message = "17:30으로 옮겨줘"
    with pytest.raises(ValueError):
        edit_intent.validate(_raw(message, time="17:00", minutes=0), message, ALIASES)
    edit_intent.validate(_raw(message, time="17:30", minutes=0), message, ALIASES)


#: 로컬 실 E4B 원출력(후보 트리, `e4b/live-c2-1.json`) — shift · item · time="" 에 맨 위 시작 시각 칸 17:30
def _live_c2(message="오후 5시 30분으로 옮겨줘"):
    return _raw(message, minutes=0, relation="at", anchor_kind="time", anchor_time="17:30")


@pytest.mark.parametrize("message", ["오후 5시 30분으로 옮겨줘", "17:30으로 옮겨줘"])
def test_shift_item_branch_can_carry_the_clock_in_the_top_start_field(message):
    """RED(4fee819c): shift · item 갈래가 anchor_kind=none · anchor_time="" 로 묶여 있었다."""
    jsonschema.validate(_live_c2(message), _schema(_items(), message))


def test_recorded_live_top_field_answer_moves_to_that_clock_keeping_the_stay():
    items = _items()
    message = "오후 5시 30분으로 옮겨줘"
    model = _GrammarBoundModel(_live_c2(message))
    got = du.decide(model, stops=du.stops_of(items), changes=[], history=[], selected_item_id=items[0].item_id,
                    message=message, now=NOW)
    assert got.action == "change_time" and got.item.item_id == items[0].item_id and got.minutes is None
    ops, _ = ops_for(got, items=items, now=NOW, message=message)
    assert [(o.item_id, o.date, o.starts_at, o.ends_at) for o in ops] == [(items[0].item_id, "2030-01-02", "17:30", "19:00")]


def test_top_field_clock_cannot_be_a_range_boundary_or_carry_a_delta():
    items = _items()
    message = "오후 5시 30분으로 옮겨줘"
    schema = jsonschema.Draft202012Validator(_schema(items, message))
    assert not schema.is_valid(_raw(message, minutes=0, relation="before", anchor_kind="time", anchor_time="17:30"))
    assert not schema.is_valid(_raw(message, minutes=30, relation="at", anchor_kind="time", anchor_time="17:30"))


@pytest.mark.parametrize("message,clock", [("오후 5시 30분으로 옮겨줘", "05:30"), ("오후 5시 30분으로 옮겨줘", "17:00"),
                                           ("17:30으로 옮겨줘", "17:00")])
def test_top_field_clock_must_match_the_quote(message, clock):
    """맨 위 칸 시각도 `validate` 의 인용 재계산을 받는다 — 다르면 해석 실패(DecisionFailed), 일정은 그대로."""
    raw = _raw(message, minutes=0, relation="at", anchor_kind="time", anchor_time=clock)
    with pytest.raises(ValueError):
        edit_intent.validate(raw, message, ALIASES)
    items = _items()
    with pytest.raises(du.DecisionFailed):
        du.decide(_GrammarBoundModel(raw), stops=du.stops_of(items), changes=[], history=[],
                  selected_item_id=items[0].item_id, message=message, now=NOW)


def test_top_field_clock_without_any_quoted_clock_is_refused():
    message = "조금 늦게 옮겨줘"
    with pytest.raises(ValueError):
        edit_intent.validate(_raw(message, minutes=0, relation="at", anchor_kind="time", anchor_time="17:30"), message, ALIASES)


# ── Codex 검토 조건(2026-10-28): 유료 plain 경로 · 모순 입력 · 기존 start+anchor_time ──
def test_paid_plain_schema_admits_the_top_field_answer_and_the_same_validation_applies():
    """유료 넘김 스키마(`_schema(plain=True)`)는 바뀌지 않았고 같은 답을 받는다 — 검증(`validate`)은 두 경로가 같다."""
    items = _items()
    message = "오후 5시 30분으로 옮겨줘"
    plain = du._schema(du.stops_of(items), [], plain=True)
    jsonschema.validate(_live_c2(message), plain)
    edit_intent.validate(_live_c2(message), message, ALIASES)
    wrong = _raw(message, minutes=0, relation="at", anchor_kind="time", anchor_time="17:00")
    jsonschema.validate(wrong, plain)
    with pytest.raises(ValueError):
        edit_intent.validate(wrong, message, ALIASES)


def test_top_field_clock_with_a_relative_delta_is_rejected_not_silently_moved():
    """문법 없는 답(유료)이 새 시작 시각과 이동 크기를 함께 내면 어느 쪽으로도 실행하지 않는다(해석 실패)."""
    message = "17:30으로 30분 늦춰줘"
    with pytest.raises(ValueError, match="inconsistent temporal scope"):
        edit_intent.validate(_raw(message, minutes=30, relation="at", anchor_kind="time", anchor_time="17:30"), message, ALIASES)


def test_existing_start_with_legacy_anchor_clock_is_not_newly_checked():
    """기존 start · time="" · 맨 위 anchor_time 답(실 E4B D02)의 검증은 그대로다 — 새 검사는 shift 에만 붙는다."""
    message = "1월 3일 오후 1시로 옮겨줘"
    raw = _raw(message, boundary="start", minutes=0, relation="at", anchor_kind="time", anchor_time="13:00")
    edit_intent.validate(raw, message, ALIASES)
    raw = _raw("다음 날로 옮겨줘", boundary="start", minutes=0, relation="at", anchor_kind="time", anchor_time="13:00")
    edit_intent.validate(raw, "다음 날로 옮겨줘", ALIASES)


def test_place_action_shift_with_top_clock_is_not_checked_as_a_time_move():
    """장소 행동의 time_edit 은 실행되지 않는다(`_executes_time_edit`) — 새 검사도 걸지 않는다(기존과 같다)."""
    message = "다른 데로 바꿔줘"
    raw = {**_raw(message, minutes=0, relation="at", anchor_kind="time", anchor_time="17:30"), "action": "apply_change"}
    edit_intent.validate(raw, message, ALIASES)
