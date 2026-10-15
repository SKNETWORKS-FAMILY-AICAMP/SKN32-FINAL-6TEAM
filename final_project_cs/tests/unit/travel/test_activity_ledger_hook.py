# -*- coding: utf-8 -*-
"""활동 판정 끼움 자리(`team_hooks/activity_ledger`) — 확인 화면 · 등록 판정 · 감시가 활동 팀 판정을 쓴다. `[2026-10-13]`

활동 코어 전달 사항 3번. 재현: 화요일 휴무인 경복궁을 화요일 일정에 넣으면, 관광공사 운영시간 표가 없는 DB 에서도
확인 화면이 「쉬는 날」을 알려야 한다(전에는 경고 없이 통과). DB 없이(가짜 연결 · 가짜 판정).
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import hours as intake_hours
from app.domains.travel_ops.components.intake.review import _hours_lines
from app.domains.travel_ops.components.itinerary.itinerary_checks import Part, check_itinerary
from app.domains.travel_ops.components.team_hooks import activity_ledger
from app.domains.travel_ops.components.watch.activity_disasters import rejudge

KST = ZoneInfo("Asia/Seoul")
TUESDAY_10 = datetime(2026, 10, 20, 10, 0, tzinfo=KST)        # 2026-10-20 은 화요일
TUESDAY_12 = datetime(2026, 10, 20, 12, 0, tzinfo=KST)


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return None                                           # 관광공사 운영시간 표 · 장소 행 모두 없다


class _Conn:
    def cursor(self):
        return _Cursor()

    @contextmanager
    def transaction(self):
        yield


def _register(state=None, by_content=None, disaster=None):
    activity_ledger.register(state=state or (lambda *a, **k: None),
                             state_by_content=by_content,
                             indoor=lambda *a, **k: None,
                             disaster=disaster or (lambda messages, **k: None))


CLOSED = {"known": True, "empty": False, "closed": True, "within_hours": None, "cut_short": None,
          "closes_at": None, "usable_minutes": None, "quote": "매주 화요일", "closure_reason": "weekly",
          "needs_caveat": True, "restdate_text": "매주 화요일", "content_id": "126508", "name": "경복궁"}
CUT_SHORT = {"known": True, "empty": False, "closed": False, "within_hours": False, "cut_short": True,
             "closes_at": "19:00", "usable_minutes": 60, "quote": None, "needs_caveat": False}


def _row(start: datetime, end: datetime) -> dict:
    return {"date": start.date().isoformat(), "start": start.strftime("%H:%M"), "end": end.strftime("%H:%M"),
            "place": {"name": "경복궁", "content_id": "126508"}, "title": "경복궁"}


def test_unregistered_hook_answers_unknown():
    activity_ledger.clear()
    assert activity_ledger.state(_Conn(), "t", "p", TUESDAY_10) is None
    assert activity_ledger.state_by_content(_Conn(), "126508", TUESDAY_10) is None
    assert activity_ledger.disaster([{"kind": "호우"}], outdoor=False) is None


def test_closed_tuesday_is_flagged_on_review_without_catalog_hours():
    calls = []
    _register(by_content=lambda conn, content_id, at, until, **k: calls.append(content_id) or dict(CLOSED))
    facts = intake_hours.facts_for(_Conn(), "t", {"name": "경복궁", "content_id": "126508"}, "activity",
                                   TUESDAY_10, TUESDAY_12)
    assert calls == ["126508"]
    assert facts.known and facts.source == "activity_ledger"
    assert facts.attributes["hours_week"]["tue"] == "closed"

    part = Part(seq=1, kind="activity", title="경복궁", starts_at=TUESDAY_10, ends_at=TUESDAY_12,
                place={"name": "경복궁", "attributes": facts.attributes, "activity": facts.activity})
    violations = check_itinerary([part])
    assert [v.code for v in violations] == ["closed_day"]

    _hours, closed = _hours_lines(_row(TUESDAY_10, TUESDAY_12), facts, violations)
    assert closed["result"] == "bad"
    assert "화요일은 쉬는 날이에요" in closed["text"] and "매주 화요일" in closed["text"]


def test_cut_short_says_how_long_you_can_stay():
    start, end = datetime(2026, 10, 21, 18, 0, tzinfo=KST), datetime(2026, 10, 21, 20, 0, tzinfo=KST)
    _register(by_content=lambda *a, **k: dict(CUT_SHORT))
    facts = intake_hours.facts_for(_Conn(), "t", {"name": "경복궁", "content_id": "126508"}, "activity", start, end)

    part = Part(seq=1, kind="activity", title="경복궁", starts_at=start, ends_at=end,
                place={"name": "경복궁", "attributes": facts.attributes, "activity": facts.activity})
    violations = check_itinerary([part])
    assert [v.code for v in violations] == ["after_closing"]
    assert "19:00 에 닫아 60분만 머물 수 있다" in violations[0].reason

    hours_line, closed = _hours_lines(_row(start, end), facts, violations)
    assert hours_line["result"] == "warn" and hours_line["text"] == "19:00에 닫아 60분만 머물 수 있어요"
    assert closed["result"] == "ok"


def test_core_place_row_is_tried_before_content_id():
    seen = []
    _register(state=lambda conn, tenant, place_id, at, until, **k: seen.append(("place", place_id)) or dict(CLOSED),
              by_content=lambda *a, **k: seen.append(("content",)) or None)
    intake_hours.facts_for(_Conn(), "t", {"name": "경복궁", "place_id": "p-1", "content_id": "126508"}, "activity",
                           TUESDAY_10, TUESDAY_12)
    assert seen == [("place", "p-1")]


def test_fact_tool_path_does_not_mix_in_the_activity_verdict():
    _register(by_content=lambda *a, **k: pytest.fail("사실 도구는 활동 판정을 섞지 않는다"))
    facts = intake_hours.facts_for(_Conn(), "t", {"content_id": "126508"}, "activity", TUESDAY_10, None,
                                   activity_verdict=False)
    assert facts.activity is None and not facts.known


def test_other_kinds_never_ask_the_activity_ledger():
    _register(by_content=lambda *a, **k: pytest.fail("관광지만 활동 원장에 묻는다"))
    intake_hours.facts_for(_Conn(), "t", {"content_id": "999"}, "lodging", TUESDAY_10, None)


# ── 감시 — 재난문자 다시 가르기 ────────────────────────────────────
def _item(sensitive):
    return SimpleNamespace(kind="activity", starts_at=TUESDAY_10,
                           place={"name": "국립중앙박물관", "weather_sensitive": sensitive})


def _report(disruptions, held=()):
    return {"verdict": "disrupted" if disruptions else "clear", "disruptions": list(disruptions),
            "checks": [{"category": "disaster_msg", "status": "ok", "weather_held_back": list(held)}]}


def _judge(messages, *, outdoor, at=None, place_name=None):
    text = messages[0].get("text") or ""
    if "복구" in text:
        return {"blocks": False, "no_effect": 1, "ask": [], "unclassified": []}
    if messages[0].get("kind") in ("호우", "산사태"):
        return {"blocks": True, "no_effect": 0, "ask": [], "unclassified": []}
    return {"blocks": False, "no_effect": 0, "ask": [], "unclassified": [{"kind": messages[0].get("kind")}]}


def test_watch_drops_released_message_and_adds_indoor_region_hazard():
    _register(disaster=_judge)
    released = {"category": "disaster_msg", "kind": "정전", "text": "잠실동 일대 정전 복구가 완료되었습니다"}
    rain = {"category": "disaster_msg", "kind": "호우", "text": "호우경보 — 외출 자제"}
    out = rejudge(_report([released], held=[rain]), _item(False))
    assert out["verdict"] == "disrupted"
    assert [d["kind"] for d in out["disruptions"]] == ["호우"]
    assert out["activity_rejudged"] == {"dropped": 1, "added": 1}


def test_watch_keeps_unknown_messages_and_leaves_report_when_unregistered():
    other = {"category": "disaster_msg", "kind": "미확인", "text": "알 수 없는 문자"}
    _register(disaster=_judge)
    report = _report([other])
    assert rejudge(report, _item(True)) is report               # 분류되지 않은 문자는 지우지 않는다

    activity_ledger.clear()
    report = _report([], held=[{"category": "disaster_msg", "kind": "호우", "text": "호우"}])
    assert rejudge(report, _item(False)) is report              # 미등록 — 공유 점검 그대로


def test_watch_ignores_non_activity_items():
    _register(disaster=lambda *a, **k: pytest.fail("관광지만 다시 가른다"))
    report = _report([{"category": "disaster_msg", "kind": "호우"}])
    assert rejudge(report, SimpleNamespace(kind="dining", starts_at=TUESDAY_10, place={})) is report
