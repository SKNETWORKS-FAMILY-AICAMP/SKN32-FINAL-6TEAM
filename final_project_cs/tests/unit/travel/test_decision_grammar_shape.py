# -*- coding: utf-8 -*-
"""채팅 해석 생성 문법의 모양 — 쓸모없는 칸을 모델이 아무 값으로 채우지 못하게 한다. `[2026-10-27 G 모델 품질]`

☆왜(실 E4B 관측):
 - 수용 F02 「N서울타워의 운영시간을 알려줘」와 개발 문장 「남산공원 주소 알려줘」(다른 여행)에서 같은 모양 — reads[0] 이
   anchor_kind=none 인데 anchor_item=대상 별칭 · relation=before · reference=previous 를 냈다. 지시문(SYSTEM)은
   「anchor_item 은 item 일 때만, 그 밖에는 none」「미술관 몇 시야? = 기준 없음」이라 했지만, 스키마가 이 칸을 서로 독립한 enum 으로
   늘 요구해 모델이 빈칸 대신 아무 값을 골랐다. 서버(`time_anchor.clean`)는 none+anchor_item 을 기준 일정으로 읽어 이웃 일정을
   계산했다 → 엉뚱한 일정 답 또는 「어느 일정을 기준으로…」 되묻기.

★지키려는 것(생성 문법만 좁힌다 — 모델 답을 서버가 고쳐 쓰지 않는다. `_schema` C02 · `generation_variants` 와 같은 원칙)
 ①읽기 항목의 기준 칸은 anchor_kind 로 갈린다: none → anchor_item=none · anchor_time="" · relation=at · steps=1,
   item → anchor_item 은 일정 별칭(none 아님) · anchor_time="", time → anchor_item=none · anchor_time HH:MM,
   now · previous → anchor_item=none · anchor_time="". 지시문이 이미 말한 계약 그대로다(새 뜻 없음)
 ②「점심 먹고 나서」(item+after) · 「다음 일정」(now+after) · 「오후 3시에」(time+at) 는 여전히 낼 수 있다
 ③유료 넘김(plain) 스키마는 바뀌지 않는다
 ④`decide` 가 모델에 주는 문법이 바로 이 문법이다(가짜 모델 — 받은 문법을 지키는 답만 낸다): 기준 없는 답은 그대로 실행되고,
   F02 모양 답은 생성될 수 없어 해석 실패(DecisionFailed)다 — 서버가 고쳐 쓰지 않는다
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import jsonschema
import pytest

from app.domains.travel_ops.components.conversation import decision_unit as du

KST = ZoneInfo("Asia/Seoul")


def _stop(alias, hour, title, kind="activity", day=4):
    item = SimpleNamespace(item_id=uuid4(), kind=kind, title=title, place={"name": title}, seq=int(alias[1:]), detail={},
                           starts_at=datetime(2031, 3, day, hour, 0, tzinfo=KST), ends_at=None, locked=False, booking_id=None)
    return du.Stop(alias, item)


STOPS = [_stop("i1", 10, "합성궁"), _stop("i2", 12, "가상시장", kind="dining"), _stop("i3", 15, "모형공원"),
         _stop("i4", 10, "시험랜드", day=5)]
ALIASES = {s.alias for s in STOPS} | {"none"}


def _admits(schema, raw) -> bool:
    try:
        jsonschema.validate(raw, schema)
    except jsonschema.ValidationError:
        return False
    return True


def _admits_anchor(schema, read) -> bool:
    return _admits(schema, _fact_raw(read))


def _read(**anchor):
    base = {"fact": "address", "target_item": "i3", "origin_item": "i3", "origin_text": "", "transport_mode": "any",
            "reference": "explicit", "query": None, "text": "모형공원 주소 알려줘", "advice": "", "anchor_kind": "none",
            "anchor_item": "none", "anchor_time": "", "at_day": "none", "relation": "at", "steps": 1}
    return {**base, **anchor}


def _fact_raw(read):
    return {"action": "answer_fact", "time_edit": dict(INACTIVE_TIME),
            "place_search": {"relation": "none", "anchor_item": "none", "place_text": "", "evidence": ""},
            "place_setting": {"want": "any", "evidence": ""}, "target_item": "i3", "target_change": "none", "fact": "address",
            "change_scope": "none", "destination_text": "", "condition_text": "", "anchor_kind": "none", "anchor_item": "none",
            "anchor_time": "", "at_day": "none", "relation": "at", "steps": 1, "minutes": 0, "place_text": "",
            "query": {"day": "all", "period": "all", "kind": "all", "position": "all"}, "reads": [read], "social": "",
            "general_requests": [], "choices": []}


INACTIVE_TIME = {"boundary": "none", "scope": "item", "time": "", "duration_minutes": 0, "cascade": False,
                 "continue_previous": False, "evidence": ""}


FACT_MESSAGE = "모형공원 주소 알려줘"


def test_a_named_fact_read_cannot_carry_a_neighbour_anchor_without_an_anchor_kind():
    """① F02 모양(기준 없음 + 대상 별칭 + before)은 생성될 수 없다. 기준 없는 같은 질문은 낼 수 있다."""
    grammar = du._schema(STOPS, [], message=FACT_MESSAGE)
    f02_shape = _read(anchor_kind="none", anchor_item="i3", relation="before", reference="previous")
    assert not _admits_anchor(grammar, f02_shape)
    assert _admits_anchor(grammar, _read())


@pytest.mark.parametrize("anchor", [
    {"anchor_kind": "item", "anchor_item": "i2", "relation": "after"},          # 「점심 먹고 나서 뭐 해?」
    {"anchor_kind": "item", "anchor_item": "i3", "relation": "before"},         # 「모형공원 가기 전에」
    {"anchor_kind": "now", "relation": "after"},                                # 「다음 일정 뭐야?」
    {"anchor_kind": "now", "relation": "after", "steps": 2},                    # 「다다음 일정은?」
    {"anchor_kind": "time", "anchor_time": "15:00", "relation": "at"},          # 「오후 3시에 뭐 해?」
    {"anchor_kind": "previous", "relation": "before"},                          # 「그럼 그 전에는?」
])
def test_every_anchor_the_prompt_describes_is_still_expressible(anchor):
    """② 지시문의 예(item · now · time · previous)는 그대로 생성할 수 있다."""
    grammar = du._schema(STOPS, [], message=FACT_MESSAGE)
    assert _admits_anchor(grammar, _read(target_item="none", **anchor))


@pytest.mark.parametrize("anchor", [
    {"anchor_kind": "none", "anchor_item": "i2"},                               # 기준 없음인데 기준 일정
    {"anchor_kind": "none", "relation": "after"},                               # 기준 없음인데 앞뒤 — 「다음」은 now 로
    {"anchor_kind": "item", "anchor_item": "none"},                             # 기준 일정인데 일정 없음
    {"anchor_kind": "time", "anchor_time": ""},                                 # 시각 기준인데 시각 없음
    {"anchor_kind": "now", "anchor_item": "i1", "relation": "after"},           # 지금 기준인데 일정 별칭
    {"anchor_kind": "item", "anchor_item": "i1", "anchor_time": "15:00"},       # 일정 기준인데 시각
])
def test_contradictory_anchor_fields_are_not_generated(anchor):
    grammar = du._schema(STOPS, [], message=FACT_MESSAGE)
    assert not _admits_anchor(grammar, _read(target_item="none", **anchor))


def test_the_paid_schema_keeps_full_objects():
    """③ 유료 넘김(plain) 스키마의 읽기 항목은 갈래 없이 그대로다."""
    plain = du._schema(STOPS, [], plain=True)
    assert "anyOf" not in plain["properties"]["reads"]["items"]
    assert plain["properties"]["reads"]["items"]["properties"]["anchor_kind"]["enum"] == ["none", "item", "time", "now", "previous"]


class _GrammarBoundModel:
    """가짜 모델 — 받은 생성 문법을 지키는 답만 낸다(문법이 거절하면 시험이 실패한다)."""

    def __init__(self, raw):
        self.raw, self.calls = raw, []

    def structured(self, system, user, schema, *, num_predict=160):
        jsonschema.validate(self.raw, schema)
        self.calls.append(schema)
        return self.raw


def test_decide_gives_the_model_this_grammar_and_runs_an_anchorless_fact_read():
    """④ 기준 없는 사실 질문은 그대로 실행된다 — 대상 일정의 사실(이웃 아님)."""
    model = _GrammarBoundModel(_fact_raw(_read()))
    decision = du.decide(model, stops=STOPS, changes=[], history=[], selected_item_id=None, message=FACT_MESSAGE)
    assert decision.action == "answer_fact" and decision.item is STOPS[2].item and decision.fact == "address"
    assert decision.reads and decision.reads[0]["anchor_item"] == "none" and decision.reads[0]["relation"] == "at"


def test_decide_cannot_receive_the_f02_shape_and_does_not_repair_it():
    """④ F02 모양 답은 문법 밖이라 모델이 낼 수 없다 — 가짜 모델이 내려 하면 해석 실패이고, 서버가 칸을 고쳐 쓰지 않는다."""
    f02_shape = _read(anchor_kind="none", anchor_item="i3", relation="before", reference="previous")
    model = _GrammarBoundModel(_fact_raw(f02_shape))
    with pytest.raises(du.DecisionFailed):
        du.decide(model, stops=STOPS, changes=[], history=[], selected_item_id=None, message=FACT_MESSAGE)
