"""확인 화면이 활동 원장 판정의 `live_status` 칸을 읽는다 — `[2026-10-15]` 활동 → 코어 전달 4번 (TeamFlow ST4F-536). DB 없이.

칸: `value`(open · closed · unknown · unchecked) · `mode`(shadow · llm) · `applied` · `checked_at` · `citations` · `visit_date`.
  - `shadow` 의 「닫힘」은 판정에 안 들어간다 → 줄의 결과는 그대로이고 휴무일 줄 끝에 「참고」만 붙는다.
  - `llm` 이고 `applied` 인 「닫힘」은 판정에 들어온다(원장이 `closed` + `closure_reason: live_status` 로 싣는다) → 휴무일 줄이 정기 휴무와 다른 말로 나온다.
  - 열었다 · 모름 · 아직 안 봄 → 아무것도 덧붙이지 않는다(「열었다」로 풀어 주지 않는다).
활동 팀의 실제 원장이 이 칸을 싣는 것은 활동 팀 변경이 합쳐진 뒤 확인한다 — 여기서는 칸을 받았을 때 코어가 어떻게 읽는지만 본다.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import hours as hours_module
from app.domains.travel_ops.components.intake.hours import HoursFacts
from app.domains.travel_ops.components.intake.review import _hours_lines, _live_reference
from app.domains.travel_ops.components.itinerary.itinerary_checks import Part, check_itinerary
from app.domains.travel_ops.components.team_hooks import activity_ledger

KST = ZoneInfo("Asia/Seoul")
OPEN_WEEK = {d: {"open": "09:00", "close": "18:00"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
ROW = {"date": "2026-11-10", "start": "10:00", "end": "12:00", "place": {"name": "시험 전시관"}}   # 2026-11-10 은 화요일


def _live(value="closed", mode="shadow", applied=None):
    applied = (mode == "llm") if applied is None else applied
    return {"value": value, "mode": mode, "applied": applied, "visit_date": "2026-11-10",
            "checked_at": "2026-11-10T03:10:00+09:00", "citations": [{"url": "https://example.test/n", "quote": "임시 휴관"}]}


def _facts(activity, *, week=None, known=True):
    return HoursFacts(known, {"hours_week": week or OPEN_WEEK} if known else {}, "activity_ledger", activity=activity)


def test_shadow_closed_is_a_reference_and_does_not_change_the_result():
    facts = _facts({"closed": False, "within_hours": True, "live_status": _live("closed", "shadow")})
    hours_line, closed_line = _hours_lines(ROW, facts, [])
    plain_hours, plain_closed = _hours_lines(ROW, _facts({"closed": False, "within_hours": True}), [])
    assert closed_line["result"] == plain_closed["result"] == "ok"                  # 결과(색)는 그대로
    assert hours_line == plain_hours                                                # 운영시간 줄도 그대로
    assert closed_line["text"].startswith(plain_closed["text"])
    assert "참고" in closed_line["text"] and "웹 공지" in closed_line["text"] and "판단에는 반영하지 않았어요" in closed_line["text"]


def test_shadow_closed_reference_survives_when_hours_are_unknown():
    """운영시간을 모르는 곳도 — 웹 공지에서 닫힘이 나왔다는 참고는 가린다고 좋을 것이 없다."""
    facts = _facts({"live_status": _live("closed", "shadow")}, known=False)
    facts.why_unknown = "관광공사 운영시간을 아직 읽지 못했어요"
    hours_line, closed_line = _hours_lines(ROW, facts, [])
    assert hours_line["result"] == "unknown" and closed_line["result"] == "unknown"
    assert "참고" in closed_line["text"]


def test_applied_llm_closure_is_told_as_a_web_notice_not_a_weekly_rest_day():
    week = {**OPEN_WEEK, "tue": "closed"}              # 원장이 닫음으로 판정하면 hours.facts_for 가 그 요일을 closed 로 싣는다
    activity = {"closed": True, "closure_reason": "live_status", "quote": "임시 휴관", "live_status": _live("closed", "llm")}
    hours_line, closed_line = _hours_lines(ROW, _facts(activity, week=week), [])
    assert closed_line["result"] == "bad" and "웹 공지에 임시 휴무로 나와요" in closed_line["text"] and "(임시 휴관)" in closed_line["text"]
    assert "쉬는 날이에요" not in closed_line["text"] and "참고" not in closed_line["text"]        # 판정에 반영됐으니 「참고」가 아니다
    assert hours_line["result"] == "unknown" and "웹 공지상 임시 휴무" in hours_line["text"]


def test_a_regular_rest_day_keeps_its_old_wording():
    week = {**OPEN_WEEK, "tue": "closed"}
    activity = {"closed": True, "closure_reason": "regular_rest", "quote": "매주 화요일 휴관"}
    hours_line, closed_line = _hours_lines(ROW, _facts(activity, week=week), [])
    assert "화요일은 쉬는 날이에요" in closed_line["text"] and "웹 공지" not in closed_line["text"]
    assert hours_line["text"] == "쉬는 날이라 운영하지 않아요"


@pytest.mark.parametrize("live", [None, _live("open", "shadow"), _live("open", "llm"), _live("unknown", "llm"), _live("unchecked", "llm"),
                                  _live("unchecked", "shadow"), _live("closed", "llm"), "closed"], ids=repr)
def test_nothing_is_added_for_values_that_are_not_an_unapplied_closure(live):
    activity = {"closed": False, "within_hours": True, **({"live_status": live} if live is not None else {})}
    assert _live_reference(activity) is None
    assert _hours_lines(ROW, _facts(activity), [])[1]["text"] == _hours_lines(ROW, _facts({"closed": False, "within_hours": True}), [])[1]["text"]


def test_llm_closed_but_not_applied_still_reads_as_a_reference():
    """`llm` 인데 `applied` 가 거짓(인용이 없어 반영 안 됨)이면 판정에 안 들어간 것이다 — 참고로 보인다."""
    assert _live_reference({"live_status": _live("closed", "llm", applied=False)}) is not None


class _Conn:
    @contextmanager
    def transaction(self):
        yield


def _facts_through_hours_module(monkeypatch, state):
    monkeypatch.setattr(activity_ledger, "state", lambda *a, **k: state)
    out = HoursFacts(True, {"hours_week": dict(OPEN_WEEK)}, "tour_api")
    start = datetime(2026, 11, 10, 10, tzinfo=KST)
    hours_module._apply_activity_ledger(_Conn(), "demo", "core-1", None, start, datetime(2026, 11, 10, 12, tzinfo=KST), out)
    return out, start


def test_shadow_state_reaches_the_screen_but_the_check_still_passes(monkeypatch):
    """원장 답(섀도 닫힘, `closed: False`) → 사실 → 등록 판정(`check_itinerary`)까지: 위반이 없고, 칸은 화면에 도착한다."""
    out, start = _facts_through_hours_module(monkeypatch, {"closed": False, "within_hours": True, "live_status": _live("closed", "shadow")})
    assert out.attributes["hours_week"]["tue"] != "closed" and out.activity["live_status"]["mode"] == "shadow"
    part = Part(seq=1, kind="activity", title="시험 전시관", starts_at=start, ends_at=datetime(2026, 11, 10, 12, tzinfo=KST),
                place={"name": "시험 전시관", "attributes": dict(out.attributes), "activity": out.activity})
    assert check_itinerary([part]) == []
    assert "참고" in _hours_lines(ROW, out, [])[1]["text"]


def test_applied_state_makes_the_day_closed_and_the_check_flags_it(monkeypatch):
    state = {"closed": True, "closure_reason": "live_status", "quote": "임시 휴관", "live_status": _live("closed", "llm")}
    out, start = _facts_through_hours_module(monkeypatch, state)
    assert out.attributes["hours_week"]["tue"] == "closed"
    part = Part(seq=1, kind="activity", title="시험 전시관", starts_at=start, ends_at=datetime(2026, 11, 10, 12, tzinfo=KST),
                place={"name": "시험 전시관", "attributes": dict(out.attributes), "activity": out.activity})
    assert [v.code for v in check_itinerary([part])] == ["closed_day"]
