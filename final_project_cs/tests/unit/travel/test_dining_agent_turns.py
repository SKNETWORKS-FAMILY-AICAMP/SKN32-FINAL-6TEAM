# -*- coding: utf-8 -*-
"""판정 에이전트 — 「찾았지만 확인 필요」는 찾은 것이다 · 턴 상한은 식당 수에 맞춘다. `[2026-10-16 실제 접수 그림자]`

☆장면 1 접수(식당 4곳, gpt-6-luna)에서 판정은 다 맞았는데 **기록이 0건**이었다 — 찾기가 「찾았지만 다르면 고쳐 주세요(unknown)」로 답하자
  「하동관 명동 본점 명동9길」 · 「미진 광화문 본점 종로19」처럼 이름을 바꿔 다시 찾기만 7번, 마지막 답을 내기 전에 10턴 상한(`turn_limit`).
★코드가 막는다(지시문만 믿지 않는다): 같은 자리(좌표)에서 이미 찾은(found) 가게를 다시 찾으면 도구를 부르지 않고 앞 결과를 돌려준다.
★턴 상한 = max(10, 4 + 2 × 식사 수) — 식사 하나에 「찾기 · 영업 · 휴무」를 한두 턴에 묶어 부른다(실측). 시간 상한(120초)은 그대로다.
"""
from __future__ import annotations

from contextlib import nullcontext
import json

from app.domains.travel_ops.instances.dining.agent import SYSTEM, judge_day, turn_limit_for
from app.domains.travel_ops.instances.dining.agent_tools import DiningTools
from app.infrastructure.llm.tool_chat import ToolTurn

UID = "22222222-2222-2222-2222-222222222222"
LAT, LNG = 37.56439, 126.98501


def _meal(n, name="하동관 명동본점"):
    return {"item_id": f"i{n}", "seq": n, "kind": "dining", "title": name, "start": f"2026-10-27T{11 + n:02d}:00",
            "end": f"2026-10-27T{12 + n:02d}:00", "place": {"name": name, "lat": LAT + n * 0.001, "lng": LNG}}


class NeedsReview(DiningTools):
    """찾았지만 확인이 필요한 가게(카카오 「하동관 명동본점」 → 원장 「하동관」)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.finds = []

    def _find_place(self, name, lat=None, lng=None):
        self.finds.append(name)
        return {"found": True, "source": "ledger", "place_uid": UID, "name": "하동관", "needs_review": True,
                "note": "원장의 「하동관」로 찾았어요 — 다르면 고쳐 주세요"}

    def _check_open_at(self, place_uid, start, end=None):
        return {"verdict": "bad", "reason": "16:00 에 닫는다", "open_at_slot": False}


class Script:
    def __init__(self, *turns):
        self.turns, self.seen = list(turns), []

    def step(self, messages, tools, final_json=False):
        self.seen.append(messages)
        return self.turns.pop(0)


def _call(i, tool, **args):
    return {"id": f"t{i}", "name": tool, "arguments": args}


def _final(item_ids):
    return ToolTurn(content=json.dumps({"items": [{"item_id": i, "place": {"place_uid": UID, "call_id": "c1"}, "checks": [
        {"check": "found", "verdict": "unknown", "reason": "확인 필요", "evidence": [{"call_id": "c1", "path": "verdict", "value": "unknown"}]}]}
        for i in item_ids], "skipped": []}, ensure_ascii=False))


def test_a_found_but_needs_review_place_is_not_searched_again_at_the_same_spot():
    plan = {"date": "2026-10-27", "customer_notes": "", "items": [_meal(6)]}
    tools = NeedsReview(lambda: nullcontext(None))
    meal = plan["items"][0]["place"]
    chat = Script(ToolTurn(content=None, tool_calls=[_call(1, "find_place", name="하동관 명동본점", lat=meal["lat"], lng=meal["lng"])]),
                  ToolTurn(content=None, tool_calls=[_call(2, "find_place", name="하동관 명동 본점 명동9길",
                                                           lat=meal["lat"], lng=meal["lng"])]),
                  _final(["i6"]))
    result = judge_day(plan, tools=tools, chat=chat)
    assert tools.finds == ["하동관 명동본점"], tools.finds                     # 두 번째 찾기는 도구를 부르지 않았다
    again = [json.loads(m["content"]) for m in chat.seen[2] if m["role"] == "tool"][-1]
    assert again["place_uid"] == UID and "이미 찾았다" in again["repeat"], again
    assert result.failure is None


def test_a_place_that_was_not_found_may_be_searched_once_more():
    class NotFound(NeedsReview):
        def _find_place(self, name, lat=None, lng=None):
            self.finds.append(name)
            return {"found": False, "source": None, "reason": "원장 · 지도 모두 없다"}

    plan = {"date": "2026-10-27", "customer_notes": "", "items": [_meal(6)]}
    tools = NotFound(lambda: nullcontext(None))
    meal = plan["items"][0]["place"]
    chat = Script(ToolTurn(content=None, tool_calls=[_call(1, "find_place", name="하동관 명동본점", lat=meal["lat"], lng=meal["lng"])]),
                  ToolTurn(content=None, tool_calls=[_call(2, "find_place", name="하동관", lat=meal["lat"], lng=meal["lng"])]),
                  ToolTurn(content=json.dumps({"items": [{"item_id": "i6", "place": {"place_uid": None, "call_id": None},
                                                          "checks": [{"check": "found", "verdict": "bad", "reason": "못 찾음",
                                                                      "evidence": [{"call_id": "c2", "path": "found", "value": False}]}]}],
                                               "skipped": []}, ensure_ascii=False)))
    judge_day(plan, tools=tools, chat=chat)
    assert tools.finds == ["하동관 명동본점", "하동관"]                         # 못 찾았으면 다른 말로 다시 찾을 수 있다


def test_the_turn_limit_grows_with_the_number_of_meals():
    assert turn_limit_for({"items": [_meal(1)]}) == 10                       # 최소는 그대로
    four = {"items": [_meal(n, f"가게{n}") for n in range(1, 5)]}
    assert turn_limit_for(four) == 12
    six = {"items": [_meal(n, f"가게{n}") for n in range(1, 7)] + [{"item_id": "a", "kind": "activity"}]}
    assert turn_limit_for(six) == 16                                         # 식사만 센다


def test_a_four_meal_day_gets_past_ten_turns():
    plan = {"date": "2026-10-27", "customer_notes": "", "items": [_meal(n, f"가게{n}") for n in range(1, 5)]}
    tools = NeedsReview(lambda: nullcontext(None))
    turns = [ToolTurn(content=None, tool_calls=[_call(i, "check_open_at", place_uid=UID, start="2026-10-27T12:00")])
             for i in range(11)]
    result = judge_day(plan, tools=tools, chat=Script(*turns, _final([f"i{n}" for n in range(1, 5)])))
    assert result.failure != "turn_limit", result.failure                     # ☆전에는 10턴에서 그날이 통째로 실패


def test_the_instructions_say_a_found_place_is_settled():
    assert "found=true" in SYSTEM and "다시 찾지 않는다" in SYSTEM



class Recording(Script):
    """턴마다 도구 목록 · 형식 강제 여부도 남긴다."""

    def __init__(self, *turns):
        super().__init__(*turns)
        self.asks = []

    def step(self, messages, tools, final_json=False):
        self.asks.append((len(tools), final_json))
        return super().step(messages, tools, final_json)


def test_the_last_turn_is_an_answer_turn_so_a_long_day_is_not_lost():
    """☆2차 실측: 다시 찾기는 사라졌지만 묻지 않은 확인(폐업 · 카드 · 할랄)을 한두 개씩 부르다 12턴에 또 `turn_limit` — 그날 기록 0건.
    마지막 한 턴은 도구 없이 「지금까지로 답하라」로 묻는다. 빠진 필수 확인은 따로 센다(`missing`)."""
    plan = {"date": "2026-10-27", "customer_notes": "", "items": [_meal(6)]}
    tools = NeedsReview(lambda: nullcontext(None))
    chat = Recording(ToolTurn(content=None, tool_calls=[_call(1, "find_place", name="하동관", lat=LAT + 0.006, lng=LNG)]),
                     ToolTurn(content=None, tool_calls=[_call(2, "check_open_at", place_uid=UID, start="2026-10-27T17:00")]),
                     _final(["i6"]))
    result = judge_day(plan, tools=tools, chat=chat, max_turns=3)
    assert result.failure is None and result.items, result.failure
    assert chat.asks[-1] == (0, True), chat.asks                              # 마지막 턴: 도구 0개 · JSON 강제
    assert "지금까지" in chat.seen[-1][-1]["content"]


def test_a_model_that_still_calls_tools_on_the_answer_turn_is_a_turn_limit():
    plan = {"date": "2026-10-27", "customer_notes": "", "items": [_meal(6)]}
    looping = Recording(*[ToolTurn(content=None, tool_calls=[_call(i, "check_open_at", place_uid=UID, start="2026-10-27T17:00")])
                          for i in range(3)])
    assert judge_day(plan, tools=NeedsReview(lambda: nullcontext(None)), chat=looping, max_turns=3).failure == "turn_limit"



# ── 다른 세션 구조 리뷰(2026-10-16 · dining-agent-architecture-review) P2 두 건 ─────────────────────────
class ByName(DiningTools):
    """이름마다 다른 가게 — 시장처럼 같은 좌표를 쓰는 서로 다른 식당."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.finds = []

    def _find_place(self, name, lat=None, lng=None):
        self.finds.append(name)
        uid = {"시장김밥": "33333333-3333-3333-3333-333333333333"}.get(name, "44444444-4444-4444-4444-444444444444")
        return {"found": True, "source": "ledger", "place_uid": uid, "name": name, "needs_review": True}


def test_a_different_restaurant_at_the_same_spot_is_still_searched():
    """[P2] 다시 찾기 막기가 좌표만 봐서, 같은 좌표의 다른 식당(시장김밥 → 시장칼국수)이 첫 가게 결과로 바뀌었다.
    이미 찾은 이름과 이어지는 다시 찾기(한 이름이 다른 이름을 통째로 품음)만 막는다."""
    spot = {"lat": 37.5704, "lng": 127.0011}
    plan = {"date": "2026-10-27", "customer_notes": "",
            "items": [{"item_id": "k", "seq": 1, "kind": "dining", "title": "시장김밥", "start": "2026-10-27T12:00",
                       "end": "2026-10-27T13:00", "place": {"name": "시장김밥", **spot}},
                      {"item_id": "n", "seq": 2, "kind": "dining", "title": "시장칼국수", "start": "2026-10-27T15:00",
                       "end": "2026-10-27T16:00", "place": {"name": "시장칼국수", **spot}}]}
    tools = ByName(lambda: nullcontext(None))
    chat = Script(ToolTurn(content=None, tool_calls=[_call(1, "find_place", name="시장김밥", **spot)]),
                  ToolTurn(content=None, tool_calls=[_call(2, "find_place", name="시장칼국수", **spot),
                                                     _call(3, "find_place", name="광장시장 시장김밥", **spot)]),
                  ToolTurn(content=json.dumps({"items": [], "skipped": []})))
    judge_day(plan, tools=tools, chat=chat)
    assert tools.finds == ["시장김밥", "시장칼국수"], tools.finds              # 칼국수는 찾고, 김밥 다시 찾기는 막는다
    second = [json.loads(m["content"]) for m in chat.seen[2] if m["role"] == "tool"]
    assert second[-2]["name"] == "시장칼국수" and "repeat" not in second[-2]
    assert second[-1]["name"] == "시장김밥" and "이미 찾았다" in second[-1]["repeat"]


class OpenAtStart(DiningTools):
    """11:00~12:30 영업 — 시작 시각만 물으면 ok, 끝까지 물으면 bad(다른 세션 리뷰의 실제 SQL 재현과 같은 모양)."""

    def _check_open_at(self, place_uid, start, end=None):
        return ({"verdict": "bad", "reason": "12:30 에 닫는다"} if end else {"verdict": "ok", "reason": "12:00 에 연다"})


def test_an_open_at_answer_for_a_meal_with_an_end_needs_a_call_that_asked_the_end():
    """[P2] 시작 시각만 물은 영업 조회(ok)가 12:00~13:00 식사 전체의 근거로 통과했다 — 끝 시각까지 물은 호출만 근거로 받는다."""
    from app.domains.travel_ops.instances.dining.agent import validate_check

    tools = OpenAtStart(lambda: nullcontext(None))
    tools.call("check_open_at", {"place_uid": UID, "start": "2026-10-27T12:00"})                          # c1 — 시작만
    tools.call("check_open_at", {"place_uid": UID, "start": "2026-10-27T12:00", "end": "2026-10-27T13:00"})  # c2 — 끝까지
    only_start = {"check": "open_at", "verdict": "ok", "reason": "연다", "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]}
    whole = {"check": "open_at", "verdict": "bad", "reason": "12:30 에 닫는다", "evidence": [{"call_id": "c2", "path": "verdict", "value": "bad"}]}
    slot = {"place_uid": UID, "start": "2026-10-27T12:00", "end": "2026-10-27T13:00"}
    assert validate_check(only_start, tools, **slot) is not None               # 거절
    assert validate_check(whole, tools, **slot) is None
    alone = OpenAtStart(lambda: nullcontext(None))                            # 끝 시각이 없는 식사면 시작만 물은 것으로 된다
    alone.call("check_open_at", {"place_uid": UID, "start": "2026-10-27T12:00"})
    assert validate_check(only_start, alone, place_uid=UID, start="2026-10-27T12:00") is None
