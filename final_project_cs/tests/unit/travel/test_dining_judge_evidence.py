# -*- coding: utf-8 -*-
"""요식 판정 — **판정을 받치는 근거**가 있어야 ok · bad 가 되고 화면 줄이 바뀐다. `[2026-10-16 설계 대조 P1]`

☆규칙 도구의 「모름(unknown)」만 인용한 「영업함(ok)」이 검증을 통과했고(`agent.validate_check`), 판정 합치기(`judge.merge`)는
  바로 그 규칙 unknown 줄만 바꾸므로 「그 시각에 영업해요」로 화면이 바뀌었다(`wiki/records/reports/2026-10-16_dining-design-assessment-e19e1ea3.md` §2).
"""
from __future__ import annotations

from types import SimpleNamespace

from app.domains.travel_ops.instances.dining.agent import validate_check
from app.domains.travel_ops.instances.dining.judge import merge

UID = "p1"
START, END = "2026-10-25T12:00", "2026-10-25T13:00"


def _call(i, tool, result, **args):
    return {"id": f"c{i}", "tool": tool, "args": {"place_uid": UID, **args}, "result": result}


def _check(code, verdict, *evidence):
    return {"check": code, "verdict": verdict, "evidence": [{"call_id": c, "path": p, "value": v} for c, p, v in evidence]}


def _validate(check, *calls):
    return validate_check(check, SimpleNamespace(calls=list(calls)), place_uid=UID, start=START, end=END)


OPEN_UNKNOWN = _call(1, "check_open_at", {"verdict": "unknown", "reason": "원장에 그날 규칙이 없다"}, start=START, end=END)
DETAIL = _call(2, "place_detail", {"hours_text": "매일 11:00-21:00", "closure_text": []})
LIVE_OPEN = _call(3, "live_open_check", {"verdict": "open"}, start=START, end=END)


def test_an_ok_citing_only_an_unknown_rule_verdict_is_refused():
    check = _check("open_at", "ok", ("c1", "verdict", "unknown"))
    assert _validate(check, OPEN_UNKNOWN) == "evidence_not_decisive"


def test_an_ok_citing_another_path_of_an_unknown_rule_call_is_refused():
    check = _check("open_at", "ok", ("c1", "reason", "원장에 그날 규칙이 없다"))
    assert _validate(check, OPEN_UNKNOWN) == "evidence_not_decisive"


def test_a_closed_day_or_business_claim_needs_its_rule_tool_to_say_so():
    closed_unknown = _call(4, "check_closed_day", {"verdict": "unknown"}, date="2026-10-25")
    assert _validate(_check("closed_day", "bad", ("c4", "verdict", "unknown")), closed_unknown) == "evidence_not_decisive"
    closed_ok = _call(4, "check_closed_day", {"verdict": "ok"}, date="2026-10-25")
    assert _validate(_check("closed_day", "ok", ("c4", "verdict", "ok")), closed_ok) is None


def test_reading_the_raw_text_still_passes_validation_and_google_backs_an_open():
    """원문 읽기는 지시문 규칙 4가 허용하는 길이다 — 검증은 통과하고, 화면 줄을 바꿀지는 합치기가 정한다."""
    check = _check("open_at", "ok", ("c1", "verdict", "unknown"), ("c2", "hours_text", "매일 11:00-21:00"))
    assert _validate(check, OPEN_UNKNOWN, DETAIL) is None
    assert _validate(_check("open_at", "ok", ("c3", "verdict", "open")), LIVE_OPEN) is None


def _review(rule_result="unknown"):
    return {"ready": True, "items": [{"id": "0-1", "kind": "dining", "status": "ok",
                                      "rows": [{"row": "place", "result": "ok"}, {"row": "hours", "result": rule_result},
                                               {"row": "closed", "result": "unknown"}]}]}


def _decided(code, verdict, *evidence):
    return {"0-1": [{"check": code, "verdict": verdict,
                     "evidence": [{"tool": t, "call_id": c, "path": p, "value": v} for t, c, p, v in evidence]}]}


def test_merge_keeps_an_unknown_row_when_the_evidence_does_not_show_the_verdict():
    review, changed = merge(_review(), _decided("open_at", "ok", ("check_open_at", "c1", "verdict", "unknown")))
    hours = review["items"][0]["rows"][1]
    assert changed == 0 and hours["result"] == "unknown" and "by" not in hours
    assert hours["agent"]["verdict"] == "ok"                                 # 에이전트 판정은 근거로 남는다


def test_merge_does_not_change_the_screen_on_raw_text_alone():
    review, changed = merge(_review(), _decided("open_at", "bad", ("check_open_at", "c1", "verdict", "unknown"),
                                                ("place_detail", "c2", "hours_text", "매일 11:00-14:00")))
    assert changed == 0 and review["items"][0]["rows"][1]["result"] == "unknown"
    review, changed = merge(_review(), _decided("business", "bad", ("place_detail", "c2", "hours_text", "폐업")))
    assert changed == 0 and not any(r["row"] == "business" for r in review["items"][0]["rows"])


def test_merge_changes_an_unknown_row_on_a_rule_or_google_verdict():
    review, changed = merge(_review(), _decided("open_at", "ok", ("live_open_check", "c3", "verdict", "open")))
    hours = review["items"][0]["rows"][1]
    assert changed == 1 and hours["result"] == "ok" and hours["text"].startswith("구글 정보로는") and hours["by"] == "agent"
    review, changed = merge(_review(), _decided("closed_day", "bad", ("check_closed_day", "c4", "verdict", "bad")))
    closed = review["items"][0]["rows"][2]
    assert changed == 1 and closed["result"] == "bad" and review["ready"] is False
