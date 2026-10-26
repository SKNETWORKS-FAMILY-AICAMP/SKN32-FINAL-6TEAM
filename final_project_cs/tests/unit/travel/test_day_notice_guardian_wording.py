# -*- coding: utf-8 -*-
"""하루 시작 안내 끝 문장이 항로 지킴이 상태(D-020)를 따른다.

D-020 「현재 변경 규칙」 — 켜짐: 재계획·저장 뒤 변경 통지 / 꺼짐·미응답: 먼저 확인.
wiki `architecture/notifications.md` 「하루 시작 끝 문장」. 판정과 같은 함수(`survey.auto_on_disruption`)를 읽는다.
DB·네트워크를 쓰지 않는다 — `_changed_since` 만 시험 대역으로 바꾼다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.planning import survey
from app.domains.travel_ops.components.watch.trip_reminders import (
    Reminder, ReminderRules, ReminderTickResult, TripReminders, day_phrase)

KST = ZoneInfo("Asia/Seoul")
AUTO = "일정에 영향을 주는 변동이 확인되면 먼저 조정하고 알려드릴게요."
ASK = "일정에 영향을 주는 변동이 확인되면 바꾸기 전에 먼저 여쭤볼게요."
ON = {"survey": {"on_disruption": "replace"}, "survey_answered": ["on_disruption"]}


def _items():
    day = (datetime.now(KST) + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0)
    return [Item(item_id=uuid4(), seq=1, kind="activity", title="경복궁", place_id=None,
                 starts_at=day, ends_at=day + timedelta(hours=2))]


def _payload(constraints):
    items = _items()
    reminders = TripReminders(store=SimpleNamespace(tenant_id="unit"),
                              connection_factory=lambda: pytest.fail("DB 를 쓰면 안 된다"),
                              clock=lambda: items[0].starts_at - timedelta(hours=2), rules=ReminderRules())
    reminders._changed_since = lambda trip_id, due_at: 0
    day = items[0].starts_at.astimezone(KST).date()
    reminder = Reminder("day_start", f"day_start:{day}", items[0].starts_at - timedelta(hours=1),
                        items[0].starts_at, day)
    trip = {"version": 3, "constraints": constraints}
    return reminders._payload(uuid4(), trip, items, reminder, reminder.due_at, ReminderTickResult())


def test_day_phrase_promises_auto_adjust_only_when_asked():
    items = _items()
    day = items[0].starts_at.astimezone(KST).date()
    assert day_phrase(items, day, auto_adjust=True).render().endswith(AUTO)
    off = day_phrase(items, day, auto_adjust=False).render()
    assert off.endswith(ASK) and AUTO not in off


def test_day_phrase_defaults_to_ask_first():
    """설정·설문 미응답은 꺼짐, 먼저 확인이 기본값(D-020) — 부르는 쪽이 값을 안 줘도 자동 조정을 약속하지 않는다."""
    items = _items()
    text = day_phrase(items, items[0].starts_at.astimezone(KST).date()).render()
    assert text.endswith(ASK) and AUTO not in text


def test_day_start_notice_for_guardian_on_says_adjust_then_notify(monkeypatch):
    monkeypatch.setattr(survey, "guardian_switch_on", lambda: True)
    payload = _payload(ON)
    assert payload["text"].endswith(AUTO)
    assert set(payload) >= {"type", "kind", "version", "text", "template", "values"}


@pytest.mark.parametrize("constraints", [
    None,                                                                         # 설문 없음(옛 여행)
    {"survey": {"on_disruption": "replace"}},                                     # 미응답 — 기본값만 저장
    {"survey": {"on_disruption": "ask_first"}, "survey_answered": ["on_disruption"]},  # 꺼짐(먼저 물어봐줘)
], ids=["no_survey", "unanswered_default_replace", "ask_first"])
def test_day_start_notice_for_guardian_off_or_unanswered_asks_first(monkeypatch, constraints):
    monkeypatch.setattr(survey, "guardian_switch_on", lambda: True)
    payload = _payload(constraints)
    assert payload["text"].endswith(ASK) and AUTO not in payload["text"]


def test_operator_switch_off_makes_even_an_on_trip_ask_first(monkeypatch):
    """운영자가 `travel.guardian.enabled` 를 끄면 켠 여행도 꺼짐과 같다(D-020 ST4F-613)."""
    monkeypatch.setattr(survey, "guardian_switch_on", lambda: False)
    payload = _payload(ON)
    assert payload["text"].endswith(ASK) and AUTO not in payload["text"]
