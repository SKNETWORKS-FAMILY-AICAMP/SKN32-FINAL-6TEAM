# -*- coding: utf-8 -*-
"""판정 에이전트 — 식사가 아닌 일정 항목의 장소는 도구가 찾지 않는다 · 속성 확인은 고객이 말한 조건만. `[2026-10-20]`

☆`[2026-10-19 실측]` gpt-4o-mini 3판(개발용 18/240판 · 검증용 3/120판)에서 활동 장소(경복궁)를 `find_place` 로 찾고
  영업 · 휴무 · 폐업 도구까지 불렀다 — 판정은 안 틀렸지만 호출 낭비이고, 인자 오류의 대부분이 이것이었다.
★지시문만 믿지 않는다 — 판정마다 일정에서 「식사가 아닌 항목의 장소 이름」을 도구 묶음에 넘기고, 그 이름으로 찾으면 거절한다.
  식사 항목도 같은 이름이면(시장 안 식당 등) 막지 않는다.
"""
from __future__ import annotations

import json
from contextlib import nullcontext

from app.domains.travel_ops.instances.dining.agent import judge_day, off_scope_names
from app.domains.travel_ops.instances.dining.agent_tools import SPECS, DiningTools
from app.infrastructure.llm.tool_chat import ToolTurn

UID = "22222222-2222-2222-2222-222222222222"


class Ledger(DiningTools):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.finds: list[str] = []

    def _find_place(self, name, lat=None, lng=None):
        self.finds.append(name)
        return {"found": True, "verdict": "ok", "source": "ledger", "place_uid": UID, "name": name}

    def _map_search(self, query, lat=None, lng=None):
        self.finds.append(query)
        return {"results": []}


def _plan(*items):
    return {"date": "2026-11-10", "customer_notes": "", "items": list(items)}


ACTIVITY = {"item_id": "a1", "seq": 1, "kind": "activity", "title": "오전 관광", "start": "2026-11-10T10:00",
            "end": "2026-11-10T11:00", "place": {"name": "경복궁"}}
MEAL = {"item_id": "m1", "seq": 2, "kind": "dining", "title": "미진 식사", "start": "2026-11-10T12:00",
        "end": "2026-11-10T13:00", "place": {"name": "미진"}}


def test_off_scope_names_are_the_places_of_items_that_are_not_meals():
    market_meal = {**MEAL, "item_id": "m2", "place": {"name": "광장시장"}}
    market_walk = {**ACTIVITY, "item_id": "a2", "place": {"name": "광장 시장"}}
    assert off_scope_names(_plan(ACTIVITY, MEAL)) == frozenset({"경복궁"})
    assert off_scope_names(_plan(market_walk, market_meal)) == frozenset()       # 식사도 그 장소면 막지 않는다(띄어쓰기 무시)


def test_finding_an_activity_place_is_refused_without_calling_the_tool():
    tools = Ledger(lambda: nullcontext(None), off_scope=frozenset({"경복궁"}))
    got = tools.call("find_place", {"name": " 경복 궁 "})
    assert "refused" in got and "식사" in got["refused"]
    assert tools.finds == [] and tools.calls == [] and tools.refused[0]["tool"] == "find_place"
    assert "refused" in tools.call("map_search", {"query": "경복궁"})
    assert tools.call("find_place", {"name": "미진"})["call_id"] == "c1"


def test_judge_day_hands_the_plan_scope_to_the_tools():
    tools = Ledger(lambda: nullcontext(None))
    final = {"items": [{"item_id": "m1", "place": {"place_uid": UID, "call_id": "c1"}, "checks": [
        {"check": "found", "verdict": "ok", "reason": "찾음", "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]}]}],
        "skipped": [], "requests": []}

    class Script:
        def __init__(self):
            self.turns = [ToolTurn(content=None, tool_calls=[{"id": "t1", "name": "find_place", "arguments": {"name": "미진"}},
                                                             {"id": "t2", "name": "find_place", "arguments": {"name": "경복궁"}}]),
                          ToolTurn(content=json.dumps(final, ensure_ascii=False))]

        def step(self, messages, specs, final_json=False):
            return self.turns.pop(0)

    judge_day(_plan(ACTIVITY, MEAL), tools=tools, chat=Script())
    assert tools.finds == ["미진"]
    assert [r["tool"] for r in tools.refused] == ["find_place"]


def test_the_attribute_tool_says_to_check_only_what_the_customer_asked():
    text = SPECS["check_attributes"].description
    assert "요청한 조건" in text and "반드시" in text and "말하지 않은 조건만" in text      # `[2026-10-20]` 요청한 조건까지 덜 부르던 문구를 고쳤다
