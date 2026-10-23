# -*- coding: utf-8 -*-
"""요식 판정 에이전트(`instances/dining/agent.py`) — 루프 · 상한 · 근거 검증. 모델과 DB 는 가짜다."""
from __future__ import annotations

import json
from contextlib import nullcontext

from app.domains.travel_ops.instances.dining.agent import judge_day, validate_check
from app.domains.travel_ops.instances.dining.agent_tools import DiningTools
from app.infrastructure.llm.tool_chat import ToolTurn

UID = "11111111-1111-1111-1111-111111111111"
PLAN = {"date": "2026-10-25", "customer_notes": "",
        "items": [{"item_id": "i1", "seq": 1, "kind": "dining", "title": "점심", "start": "2026-10-25T12:00",
                   "end": "2026-10-25T13:00", "place": {"name": "시험국밥"}}]}


class FakeTools(DiningTools):
    """DB 대신 정해진 결과."""

    def _find_place(self, name, lat=None, lng=None):
        return {"verdict": "ok", "found": True, "source": "ledger", "place_uid": UID, "name": name, "needs_review": False}

    def _check_open_at(self, place_uid, start, end=None):
        return {"verdict": "bad", "reason": "그날 휴무", "open_at_slot": False}


def _tools(**kw):
    return FakeTools(lambda: nullcontext(None), **kw)


class Script:
    """정해진 턴을 차례로 낸다."""

    def __init__(self, *turns):
        self.turns, self.seen = list(turns), []

    def step(self, messages, tools, final_json=False):
        self.seen.append(messages)
        return self.turns.pop(0)


def _call(i, tool, **args):
    return {"id": f"t{i}", "name": tool, "arguments": args}


def _final(checks, place_uid=UID):
    return ToolTurn(content=json.dumps({"items": [{"item_id": "i1", "place": {"place_uid": place_uid, "call_id": "c1"},
                                                    "checks": checks}], "skipped": []}, ensure_ascii=False))


TOOL_TURN = ToolTurn(content=None, tool_calls=[_call(1, "find_place", name="시험국밥"),
                                               _call(2, "check_open_at", place_uid=UID, start="2026-10-25T12:00",
                                                     end="2026-10-25T13:00")])     # ★식사 끝까지 묻는다(구조 리뷰 P2 — 시작만은 근거가 아니다)


def test_a_grounded_judgment_passes_and_tool_results_go_back_to_the_model():
    chat = Script(TOOL_TURN, _final([{"check": "open_at", "verdict": "bad", "reason": "휴무",
                                      "evidence": [{"call_id": "c2", "path": "verdict", "value": "bad"}]}]))
    result = judge_day(PLAN, tools=_tools(), chat=chat)
    assert result.failure is None and result.stats["validation_failures"] == 0
    assert result.items[0]["checks"][0]["verdict"] == "bad"
    tool_messages = [m for m in chat.seen[1] if m["role"] == "tool"]
    assert [json.loads(m["content"])["call_id"] for m in tool_messages] == ["c1", "c2"]


def test_a_claim_that_contradicts_the_rule_tool_becomes_unknown():
    chat = Script(TOOL_TURN, _final([{"check": "open_at", "verdict": "ok", "reason": "연다",
                                      "evidence": [{"call_id": "c2", "path": "open_at_slot", "value": False},
                                                   {"call_id": "c2", "path": "verdict", "value": "bad"}]}]))
    check = judge_day(PLAN, tools=_tools(), chat=chat).items[0]["checks"][0]
    assert check["verdict"] == "unknown" and check["failure"] == "contradicts_rule_tool" and check["claimed_verdict"] == "ok"


def test_made_up_evidence_is_refused():
    tools = _tools()
    tools.call("check_open_at", {"place_uid": UID, "start": "2026-10-25T12:00"})
    base = {"check": "open_at", "verdict": "bad", "reason": "x"}
    assert validate_check({**base, "evidence": [{"call_id": "c9", "path": "verdict", "value": "bad"}]}, tools) == "evidence_unknown_call"
    assert validate_check({**base, "evidence": [{"call_id": "c1", "path": "hours", "value": "x"}]}, tools) == "evidence_path_missing"
    assert validate_check({**base, "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]}, tools) == "evidence_value_mismatch"
    assert validate_check({**base, "evidence": []}, tools) == "no_evidence"
    assert validate_check({**base, "check": "vibes", "evidence": []}, tools) == "unknown_check"
    assert validate_check({"check": "open_at", "verdict": "unknown", "reason": "모름", "evidence": []}, tools) is None


def test_a_place_not_from_the_tools_is_refused():
    chat = Script(TOOL_TURN, _final([{"check": "open_at", "verdict": "bad", "reason": "휴무",
                                      "evidence": [{"call_id": "c2", "path": "verdict", "value": "bad"}]}],
                                    place_uid="99999999-9999-9999-9999-999999999999"))
    check = judge_day(PLAN, tools=_tools(), chat=chat).items[0]["checks"][0]
    assert check["failure"] == "place_not_from_tools"


def test_turn_limit_and_model_errors_are_failures_not_answers():
    looping = Script(*[ToolTurn(content=None, tool_calls=[_call(i, "find_place", name=f"가게{i}")]) for i in range(5)])
    assert judge_day(PLAN, tools=_tools(), chat=looping, max_turns=3).failure == "turn_limit"

    class Broken:
        def step(self, *a, **k):
            raise TimeoutError("slow")
    result = judge_day(PLAN, tools=_tools(), chat=Broken())
    assert result.failure == "model_error:TimeoutError" and result.items == []
    # 글로 끝내면 한 번 JSON 으로 다시 묻는다 — 그래도 글이면 실패
    assert judge_day(PLAN, tools=_tools(), chat=Script(ToolTurn(content="끝났어요"), ToolTurn(content="정말 끝"))).failure == "final_not_json"


def test_a_text_final_gets_one_json_retry():
    good = _final([{"check": "open_at", "verdict": "unknown", "reason": "모름", "evidence": []}])
    chat = Script(ToolTurn(content="점심은 확인이 필요해요."), good)
    result = judge_day(PLAN, tools=_tools(), chat=chat)
    assert result.failure is None and result.stats["turns"] == 2 and result.items[0]["checks"][0]["verdict"] == "unknown"


# ── `[2026-10-16]` 근거 검증의 구멍 두 가지 — 엉뚱한 도구를 근거로 든 판정 · 빈 답 ──

class ClosedDayTools(FakeTools):
    """그날 휴무 — 휴무 도구는 bad, 영업 도구는 (다른 시각에 물으면) ok."""

    def _check_closed_day(self, place_uid, date):
        return {"verdict": "bad", "reason": "그날은 휴무다", "closed": True}

    def _check_open_at(self, place_uid, start, end=None):
        return {"verdict": "ok", "reason": "그 시각에 영업한다", "open_at_slot": True}


def test_an_open_claim_grounded_only_on_finding_the_place_is_refused():
    """도구가 「휴무」라 했는데 「가게를 찾았다」(find_place 의 ok)를 근거로 「영업 가능」이라 답하면 통과하던 것."""
    tools = ClosedDayTools(lambda: nullcontext(None))
    tools.call("find_place", {"name": "시험국밥"})
    tools.call("check_closed_day", {"place_uid": UID, "date": "2026-10-25"})
    claim = {"check": "open_at", "verdict": "ok", "reason": "찾았으니 연다",
             "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]}
    assert validate_check(claim, tools, place_uid=UID, start="2026-10-25T12:00") == "evidence_wrong_tool"
    assert validate_check(claim, tools) == "evidence_wrong_tool"           # 항목 정보가 없어도 체크에 맞는 도구여야 한다


def test_an_open_claim_is_refused_when_an_uncited_rule_tool_said_closed_that_day():
    """인용한 영업 판정(다른 시각 · ok)과 별개로, 같은 가게 같은 날 휴무 도구가 bad 면 「영업 가능」은 모순이다."""
    tools = ClosedDayTools(lambda: nullcontext(None))
    tools.call("find_place", {"name": "시험국밥"})
    tools.call("check_closed_day", {"place_uid": UID, "date": "2026-10-25"})
    tools.call("check_open_at", {"place_uid": UID, "start": "2026-10-25T12:00"})
    claim = {"check": "open_at", "verdict": "ok", "reason": "연다",
             "evidence": [{"call_id": "c3", "path": "verdict", "value": "ok"}]}
    assert validate_check(claim, tools, place_uid=UID, start="2026-10-25T12:00") == "contradicts_rule_tool"
    # 다른 날의 휴무는 걸지 않는다
    other = ClosedDayTools(lambda: nullcontext(None))
    other.call("check_closed_day", {"place_uid": UID, "date": "2026-10-26"})
    other.call("check_open_at", {"place_uid": UID, "start": "2026-10-25T12:00"})
    ok = {**claim, "evidence": [{"call_id": "c2", "path": "verdict", "value": "ok"}]}
    assert validate_check(ok, other, place_uid=UID, start="2026-10-25T12:00") is None


def test_evidence_about_another_place_is_refused():
    tools = ClosedDayTools(lambda: nullcontext(None))
    tools.call("check_open_at", {"place_uid": "99999999-9999-9999-9999-999999999999", "start": "2026-10-25T12:00"})
    claim = {"check": "open_at", "verdict": "ok", "reason": "연다",
             "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]}
    assert validate_check(claim, tools, place_uid=UID, start="2026-10-25T12:00") == "evidence_other_place"


def test_an_empty_answer_for_a_day_with_a_meal_is_a_failure():
    """식사가 있는데 빈 결과(`items: []`)를 내면 실패 없이 끝나던 것."""
    chat = Script(ToolTurn(content=json.dumps({"items": [], "skipped": []})))
    result = judge_day(PLAN, tools=_tools(), chat=chat)
    assert result.failure == "empty_result"
    assert result.missing == [{"item_id": "i1", "check": "found", "failure": "missing_item"},
                              {"item_id": "i1", "check": "open_at", "failure": "missing_item"}]
    assert result.stats["missing_checks"] == 2


def test_a_required_check_left_out_is_counted_not_silently_passed():
    """시각이 있는 식사의 found · open_at 은 필수다(프롬프트 규칙 2) — 빠지면 센다. 계획에 없는 항목 id 는 버리고 센다."""
    final = ToolTurn(content=json.dumps({"items": [
        {"item_id": "i1", "place": {"place_uid": UID, "call_id": "c1"},
         "checks": [{"check": "found", "verdict": "ok", "reason": "찾음",
                     "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]}]},
        {"item_id": "zz", "place": None, "checks": []}], "skipped": []}, ensure_ascii=False))
    result = judge_day(PLAN, tools=_tools(), chat=Script(TOOL_TURN, final))
    assert result.failure is None
    assert [i["item_id"] for i in result.items] == ["i1"]
    assert result.missing == [{"item_id": "i1", "check": "open_at", "failure": "missing_check"}]
    assert result.stats["missing_checks"] == 1 and result.stats["unknown_items"] == 1


# ── `[2026-10-16]` 근거 검증 2차 — 시각 · 속성 의미 · 검사 없는 항목 · 같은 항목 id 반복 ──

class AttrTools(ClosedDayTools):
    """할랄 no · 채식 limited · 아이 yes."""

    def _check_attributes(self, place_uid, wanted):
        table = {"halal": "no", "vegetarian": "limited", "kids": "yes", "card": "unknown"}
        return {"attributes": {w: {"state": table[w], "source_text": None, "source": None, "verified_at": None} for w in wanted}}


def _attr_tools():
    return AttrTools(lambda: nullcontext(None))


def test_open_evidence_for_another_time_or_day_is_refused():
    """12~13시 식사에 같은 가게의 18시 · 다음 날 조회를 인용하면 통과하던 것."""
    for start in ("2026-10-25T18:00", "2026-10-26T12:00"):
        tools = ClosedDayTools(lambda: nullcontext(None))
        tools.call("check_open_at", {"place_uid": UID, "start": start})
        claim = {"check": "open_at", "verdict": "ok", "reason": "연다",
                 "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]}
        assert validate_check(claim, tools, place_uid=UID, start="2026-10-25T12:00",
                              end="2026-10-25T13:00") == "evidence_other_time", start
    # 종료 시각이 다른 조회도 같은 자리가 아니다
    tools = ClosedDayTools(lambda: nullcontext(None))
    tools.call("check_open_at", {"place_uid": UID, "start": "2026-10-25T12:00", "end": "2026-10-25T12:30"})
    claim = {"check": "open_at", "verdict": "ok", "reason": "연다", "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]}
    assert validate_check(claim, tools, place_uid=UID, start="2026-10-25T12:00", end="2026-10-25T13:00") == "evidence_other_time"
    # 휴무 조회는 날만 본다 — 다른 날이면 거절, 같은 날이면 통과
    tools = ClosedDayTools(lambda: nullcontext(None))
    tools.call("check_closed_day", {"place_uid": UID, "date": "2026-10-26"})
    bad = {"check": "closed_day", "verdict": "bad", "reason": "쉰다", "evidence": [{"call_id": "c1", "path": "verdict", "value": "bad"}]}
    assert validate_check(bad, tools, place_uid=UID, start="2026-10-25T12:00") == "evidence_other_time"
    assert validate_check(bad, tools, place_uid=UID, start="2026-10-26T12:00") is None
    # 같은 시각(초 · 시간대 표기만 다름)은 통과
    tools = ClosedDayTools(lambda: nullcontext(None))
    tools.call("check_open_at", {"place_uid": UID, "start": "2026-10-25T12:00:00+09:00", "end": "2026-10-25T13:00"})
    assert validate_check(claim, tools, place_uid=UID, start="2026-10-25T12:00", end="2026-10-25T13:00") is None


def test_attribute_claims_must_match_the_cited_attribute_and_its_value():
    tools = _attr_tools()
    tools.call("check_attributes", {"place_uid": UID, "wanted": ["halal", "kids", "vegetarian"]})

    def claim(check, verdict, path, value):
        return {"check": check, "verdict": verdict, "reason": "x", "evidence": [{"call_id": "c1", "path": path, "value": value}]}
    # 할랄 no 를 인용하고 식단 ok — 의미가 어긋난다
    assert validate_check(claim("dietary", "ok", "attributes.halal.state", "no"), tools, place_uid=UID) == "contradicts_attribute"
    # 아이 동반만 인용하고 식단 ok — 다른 속성이다
    assert validate_check(claim("dietary", "ok", "attributes.kids.state", "yes"), tools, place_uid=UID) == "evidence_wrong_attribute"
    # 맞는 경우: 할랄 no → bad, 채식 limited(조건부 가능) → ok, 아이 yes → ok
    assert validate_check(claim("dietary", "bad", "attributes.halal.state", "no"), tools, place_uid=UID) is None
    assert validate_check(claim("dietary", "ok", "attributes.vegetarian.state", "limited"), tools, place_uid=UID) is None
    assert validate_check(claim("kids", "ok", "attributes.kids.state", "yes"), tools, place_uid=UID) is None
    # 「yes」인데 bad 라 하는 것도 어긋난다
    assert validate_check(claim("kids", "bad", "attributes.kids.state", "yes"), tools, place_uid=UID) == "contradicts_attribute"


def test_items_without_any_check_are_a_failed_run():
    """`items=[{"item_id": "i1", "checks": []}]` — 누락 2건은 셌지만 실행은 성공으로 남던 것."""
    chat = Script(ToolTurn(content=json.dumps({"items": [{"item_id": "i1", "place": None, "checks": []}], "skipped": []})))
    result = judge_day(PLAN, tools=_tools(), chat=chat)
    assert result.failure == "empty_result"
    assert [m["check"] for m in result.missing] == ["found", "open_at"]


def test_a_repeated_item_id_is_merged_not_overwritten():
    """i1(found) · i1(open_at) 을 나눠 내면 found 가 빠졌다고 세던 것."""
    final = ToolTurn(content=json.dumps({"items": [
        {"item_id": "i1", "place": {"place_uid": UID, "call_id": "c1"},
         "checks": [{"check": "found", "verdict": "ok", "reason": "찾음",
                     "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]}]},
        {"item_id": "i1", "place": {"place_uid": UID, "call_id": "c1"},
         "checks": [{"check": "open_at", "verdict": "bad", "reason": "휴무",
                     "evidence": [{"call_id": "c2", "path": "verdict", "value": "bad"}]}]}], "skipped": []}, ensure_ascii=False))
    result = judge_day(PLAN, tools=_tools(), chat=Script(TOOL_TURN, final))
    assert result.failure is None and result.missing == []
    assert len(result.items) == 1 and [c["check"] for c in result.items[0]["checks"]] == ["found", "open_at"]
