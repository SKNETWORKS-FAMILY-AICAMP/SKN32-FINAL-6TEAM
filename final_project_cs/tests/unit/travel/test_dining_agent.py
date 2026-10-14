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
                                               _call(2, "check_open_at", place_uid=UID, start="2026-10-25T12:00")])


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
