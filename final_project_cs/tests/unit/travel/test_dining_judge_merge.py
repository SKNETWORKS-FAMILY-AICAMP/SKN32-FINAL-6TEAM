# -*- coding: utf-8 -*-
"""요식 판정을 접수 확인 줄에 합치기(`instances/dining/judge.merge` · `run`). `[2026-10-16]`

★①규칙이 모름(unknown)인 영업 · 휴무 줄을 도구 근거로 정하고 ②새 조건을 더한다.
  ③실제 실행에서 근거 검증한 필수 bad는 기존 ok도 내린다. 검증 표시 없는 주장은 기존 확정 줄을 바꾸지 않는다.
★화면 문장은 코드가 만든다 — 에이전트 문장(reason)은 내보내지 않는다.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager

import pytest

from app.domains.travel_ops.instances.dining import judge
from app.domains.travel_ops.instances.dining.agent import AgentResult

RULE_HOURS_TEXT = "운영시간을 확인하지 못했어요"


def _row(row, result, text="규칙 문장"):
    return {"row": row, "result": result, "text": text}


def _review(hours="unknown", closed="unknown", status="keep", ready=True):
    meal = {"id": "0-1", "kind": "dining", "title": "하동관 점심", "date": "2026-10-19", "starts_at": "12:00",
            "ends_at": "13:00", "status": status, "can_lock": status != "review",
            "place": {"name": "하동관", "latitude": 37.56, "longitude": 126.98},
            "rows": [_row("place", "ok"), _row("hours", hours, RULE_HOURS_TEXT), _row("closed", closed)]}
    sight = {"id": "0-0", "kind": "activity", "title": "경복궁", "date": "2026-10-19", "status": "keep", "can_lock": True,
             "rows": [_row("place", "ok"), _row("hours", "unknown")]}
    return {"items": [sight, meal], "moves": [], "needs": {"items": 0, "moves": 0, "total": 0}, "ready": ready}


def _check(code, verdict, tool="check_open_at"):
    return {"check": code, "verdict": verdict,
            "evidence": [{"tool": tool, "call_id": "c1", "path": "verdict", "value": verdict}]}


def _meal(review):
    return next(i for i in review["items"] if i["id"] == "0-1")


def _rows(review):
    return {r["row"]: r for r in _meal(review)["rows"]}


def test_unknown_hours_become_the_agent_verdict_with_code_text():
    merged, changed = judge.merge(_review(), {"0-1": [_check("open_at", "ok")]})
    hours = _rows(merged)["hours"]
    assert changed == 1
    assert hours["result"] == "ok" and hours["text"] == "그 시각에 영업해요" and hours["by"] == "agent"
    assert hours["open_at"] == "ok" and hours["agent"]["verdict"] == "ok" and hours["agent"]["agree"] is False


def test_google_evidence_says_so_in_the_text():
    merged, _ = judge.merge(_review(), {"0-1": [_check("open_at", "bad", tool="live_open_check")]})
    assert _rows(merged)["hours"]["text"] == "구글 정보로는 그 시각에는 영업하지 않아요"


def test_a_rule_verdict_is_kept_and_the_agent_is_only_attached():
    merged, changed = judge.merge(_review(hours="ok"), {"0-1": [_check("open_at", "bad")]})
    hours = _rows(merged)["hours"]
    assert changed == 0
    assert hours["result"] == "ok" and hours["text"] == RULE_HOURS_TEXT and "by" not in hours
    assert hours["agent"] == {"verdict": "bad", "agree": False, "evidence": _check("open_at", "bad")["evidence"]}
    assert _meal(merged)["status"] == "keep" and merged["ready"] is True


def test_agent_unknown_does_not_touch_an_unknown_row():
    merged, changed = judge.merge(_review(), {"0-1": [_check("closed_day", "unknown", tool="check_closed_day")]})
    closed = _rows(merged)["closed"]
    assert changed == 0 and closed["result"] == "unknown" and closed["text"] == "규칙 문장"


def test_a_bad_verdict_makes_the_item_need_review_and_recounts():
    merged, changed = judge.merge(_review(), {"0-1": [_check("closed_day", "bad", tool="check_closed_day")]})
    assert changed == 1 and _rows(merged)["closed"]["text"] == "그날은 쉬는 날이에요"
    meal = _meal(merged)
    assert meal["status"] == "review" and meal["can_lock"] is False
    assert merged["needs"] == {"items": 1, "moves": 0, "total": 1} and merged["ready"] is False


def test_customer_conditions_are_added_as_rows():
    decided = {"0-1": [_check("dietary", "bad", tool="check_attributes"), _check("kids", "unknown", tool="check_attributes"),
                       _check("payment", "ok", tool="check_attributes")]}
    merged, changed = judge.merge(_review(), decided)
    rows = _rows(merged)
    assert changed == 3
    # 근거에 확인한 속성(attributes.<속성>)이 없으면 조건 이름을 적지 않는다(`[2026-10-18]` 전에는 「(할랄 · 채식)」 고정)
    assert rows["dietary"]["text"] == "요청하신 식사 조건에 맞지 않는 곳이에요" and rows["dietary"]["by"] == "agent"
    assert rows["kids"]["text"] == "아이 동반 가능 여부는 확인하지 못했어요"
    assert rows["payment"]["result"] == "ok"
    # required 를 적지 않은 식이 조건은 선호다 — 안 맞아도 주의(warn)로만 두고 확인 필요로 올리지 않는다
    assert rows["dietary"]["result"] == "warn" and _meal(merged)["status"] == "keep"


@pytest.mark.parametrize("required", [True, False])
def test_a_validated_dietary_bad_blocks_registration_only_when_required(required):
    """필수 식이 bad 만 확인 필요(review)로 올려 등록 가능(ready)을 끄고, 선호는 주의로 둔다.
    ☆화면의 「여행 등록」은 `ready` 를 보지만 등록 API(`confirm`)는 아직 이 판정을 다시 보지 않는다 — 그 관문은 이 판에 없다(2026-10-19 기준)."""
    check = {**_check("dietary", "bad", tool="check_attributes"), "validated": True, "required": required}
    merged, changed = judge.merge(_review(), {"0-1": [check]})
    dietary = _rows(merged)["dietary"]
    assert changed == 1 and dietary["by"] == "agent"
    assert dietary["requirement"] == ("required" if required else "preference")
    assert dietary["result"] == ("bad" if required else "warn") and dietary["blocks_registration"] is required
    assert _meal(merged)["status"] == ("review" if required else "keep") and merged["ready"] is not required


def test_business_is_added_only_when_closed_down():
    merged, changed = judge.merge(_review(), {"0-1": [_check("business", "ok", tool="check_business")]})
    assert changed == 0 and "business" not in _rows(merged)                       # 「폐업 기록 없음」은 고객에게 뜻이 없다
    merged, changed = judge.merge(_review(), {"0-1": [_check("business", "bad", tool="check_business")]})
    assert changed == 1 and _rows(merged)["business"]["text"] == "폐업했거나 옮긴 곳으로 나와요"


def test_agent_text_never_reaches_the_screen():
    check = {**_check("open_at", "ok"), "reason": "에이전트가 지어낸 말"}
    merged, _ = judge.merge(_review(), {"0-1": [check]})
    assert "에이전트가 지어낸 말" not in str(merged)


def test_merging_twice_does_not_add_rows_twice():
    decided = {"0-1": [_check("payment", "ok", tool="check_attributes")]}
    once, _ = judge.merge(_review(), decided)
    twice, changed = judge.merge(copy.deepcopy(once), decided)
    assert [r["row"] for r in _meal(twice)["rows"]].count("payment") == 1 and changed == 0


def test_non_dining_items_and_unknown_ids_are_untouched():
    review = _review()
    before = copy.deepcopy(review["items"][0])
    merged, changed = judge.merge(review, {"0-0": [_check("open_at", "ok")], "9-9": [_check("open_at", "ok")]})
    assert changed == 0 and merged["items"][0] == before


def test_a_not_ready_review_never_becomes_ready():
    """규칙 문제(problems)는 다시 보지 않는다 — 에이전트는 등록 가능을 더 나쁘게만 만든다."""
    merged, _ = judge.merge(_review(ready=False), {"0-1": [_check("open_at", "ok")]})
    assert merged["ready"] is False


# -- run: 실패 · 검증 실패인 체크는 줄에 쓰지 않는다 --

class FakeCursor:
    def __init__(self, sink):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.sink.append(params)


class FakeConn:
    def __init__(self, sink):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @contextmanager
    def transaction(self):
        yield

    def cursor(self):
        return FakeCursor(self.sink)


def _run(monkeypatch, result, stored):
    from app.domains.travel_ops.components.intake import review as review_module

    inserted, saved = [], []
    monkeypatch.setattr(judge, "judge_day", lambda plan, **kw: result)
    monkeypatch.setattr(review_module, "load", lambda conn, t, i, r: copy.deepcopy(stored))
    monkeypatch.setattr(review_module, "store", lambda conn, t, i, r, payload: saved.append(payload))
    monkeypatch.setattr(review_module, "intake_state", lambda conn, t, i: ("review", 1))   # 지금 판 그대로(늦은 판정은 `test_dining_judge_stale.py`)
    got = judge.run(lambda: FakeConn(inserted), tenant_id="t", intake_id="i", revision=1, review=_review(), notes="",
                    chat=None, model="fake", tools_factory=lambda connect: None)
    return got, inserted, saved


def _result(checks, failure=None):
    return AgentResult(items=[{"item_id": "0-1", "place": None, "checks": checks}], skipped=[], stats={}, failure=failure,
                       raw_final=None, tool_calls=[{"id": "c1", "tool": "check_open_at", "args": {}}], missing=[])


def test_run_merges_only_checks_that_passed_validation(monkeypatch):
    good = {"check": "open_at", "verdict": "ok", "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]}
    bad = {"check": "closed_day", "verdict": "unknown", "failure": "evidence_path_missing", "claimed_verdict": "bad",
           "evidence": [{"call_id": "c9", "path": "verdict", "value": "bad"}]}
    got, inserted, saved = _run(monkeypatch, _result([good, bad]), _review())
    assert got["used"] == 1 and got["changed"] == 1 and len(inserted) == 3        # 요약 줄 + 체크 둘 모두 기록한다
    rows = _rows(saved[0])
    assert rows["hours"]["result"] == "ok" and rows["hours"]["agent"]["evidence"][0]["tool"] == "check_open_at"
    assert rows["closed"]["result"] == "unknown" and "agent" not in rows["closed"]  # 검증 실패 — 규칙 그대로
    assert saved[0]["agent_judged"]["changed_rows"] == 1


def test_run_leaves_the_review_alone_when_the_day_fails(monkeypatch):
    got, inserted, saved = _run(monkeypatch, _result([], failure="turn_limit"), _review())
    assert got["failures"] == 1 and saved == [] and len(inserted) == 1            # 실패도 요약 줄로 남는다


def test_run_downgrades_the_current_rule_ok_with_fresh_validated_bad_and_keeps_the_rule_for_audit(monkeypatch):
    """현재 저장본에 합치며, 필수 불가를 확인했으면 화면도 bad로 보여 등록 이유와 맞춘다."""
    stored = _review(hours="ok")
    good = {"check": "open_at", "verdict": "bad", "evidence": [{"call_id": "c1", "path": "verdict", "value": "bad"}]}
    got, _, saved = _run(monkeypatch, _result([good]), stored)
    row = _rows(saved[0])["hours"]
    assert got["changed"] == 1 and row["result"] == "bad"
    assert row["rule_result"] == "ok" and row["rule_text"] == RULE_HOURS_TEXT
    assert row["blocks_registration"] is True and row["agent"]["validated"] is True
