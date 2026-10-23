# -*- coding: utf-8 -*-
"""항로 지킴이 운영 스위치 — 끄면 화면에서 숨기고 서버의 자동 일정 변경도 멈춘다. `[2026-10-19 사용자 결정 — ST4F-613]`

끈 동안은 켠 여행도 꺼진 여행과 같이 판정한다(일반 사건은 먼저 묻고, 날씨만 걸리면 「바꿀까요?」, 안전 사건은 안전 알림).
켠 기록(`constraints.survey.on_disruption` · `survey_answered`)은 바꾸지 않아 다시 켜면 원래대로 돌아온다.
계약: `wiki/external/rest-endpoints/web-trips.md` 「항로 지킴이 운영 스위치」.
"""
from __future__ import annotations

import copy
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core import settings as core_settings
from app.core.settings import ConfigError
from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.planning import guardian, pending, survey
from app.domains.travel_ops.modules.web_account import web_guard

KST = ZoneInfo("Asia/Seoul")
ON = {"survey": {"on_disruption": "replace"}, "survey_answered": ["on_disruption"]}
OFF = {"survey": {"on_disruption": "ask_first"}, "survey_answered": ["on_disruption"]}


@pytest.fixture(autouse=True)
def _no_reader():
    settings_hook.clear()
    yield
    settings_hook.clear()


@pytest.fixture()
def service_tenant(monkeypatch):
    """판정 함수는 서비스 테넌트(`settings.tenant_id`)로 읽는다 — 시험에서는 가짜 설정 하나로 바꾼다."""
    class Settings:
        tenant_id = "t1"
        web_origin = ""

    monkeypatch.setattr(core_settings, "get_settings", lambda: Settings())
    return "t1"


def _console(value, seen=None):
    def reader(tenant, name):
        if seen is not None:
            seen.append((tenant, name))
        return value if name == settings_hook.GUARDIAN else None

    settings_hook.register(reader)


def _item():
    return Item(item_id=uuid4(), seq=1, kind="activity", title="서울 관람", place_id=uuid4(),
                starts_at=datetime(2026, 10, 25, 10, 0, tzinfo=KST), ends_at=datetime(2026, 10, 25, 12, 0, tzinfo=KST))


# ── 관리 콘솔 목록 · 값 ────────────────────────────────────────────────────────────────────────────

def test_switch_is_listed_for_the_admin_console_off_by_default_with_help():
    spec = web_guard.specs()[settings_hook.GUARDIAN]
    assert spec.type == "bool" and spec.default is False
    assert spec.check(False) is None and spec.check("off") == "wrong_type"
    assert "끄면" in spec.help and "켠 기록" in spec.help


def test_without_console_value_the_guardrail_decides_and_it_is_off():
    assert settings_hook.guardian_enabled("t1") is False
    assert core_settings.guardian_enabled() is False


@pytest.mark.parametrize("stored, expected", [(True, True), (False, False)])
def test_console_value_wins(stored, expected):
    _console(stored)
    assert settings_hook.guardian_enabled("t1") is expected


@pytest.mark.parametrize("stored", ["off", 0, None])
def test_non_boolean_value_is_not_treated_as_a_change(stored):
    _console(stored)
    assert settings_hook.guardian_enabled("t1") is False


def test_unreadable_table_falls_back_to_the_guardrail_off():
    def broken(tenant, name):
        raise RuntimeError("db down")

    settings_hook.register(broken)
    assert settings_hook.guardian_enabled("t1") is False


def test_unreadable_guardrail_keeps_the_decided_default_off(monkeypatch):
    class Broken:
        def get(self, key):
            raise ConfigError(f"guardrails 키 없음: '{key}'")

    monkeypatch.setattr(core_settings, "get_guardrails", lambda: Broken())
    assert core_settings.guardian_enabled() is False


# ── 판정 — 끄면 켠 여행도 꺼진 여행과 같다 ─────────────────────────────────────────────────────────

def test_switch_off_reads_a_turned_on_trip_as_ask_first(service_tenant):
    _console(False)
    assert survey.on_disruption(ON) == "ask_first"
    assert survey.auto_on_disruption(ON) is False
    assert guardian.is_on(ON) is False


def test_switch_on_keeps_the_customers_choice(service_tenant):
    _console(True)
    assert survey.on_disruption(ON) == "replace" and survey.auto_on_disruption(ON) is True
    assert survey.on_disruption(OFF) == "ask_first" and survey.auto_on_disruption(OFF) is False


def test_switch_is_read_with_the_service_tenant_only_for_trips_that_chose_replace(service_tenant):
    seen: list[tuple[str, str]] = []
    _console(False, seen)
    assert survey.on_disruption(OFF) == "ask_first"
    assert survey.on_disruption({}) == "ask_first"
    assert seen == []                                    # 꺼진 여행 · 답 없는 여행은 스위치를 읽을 필요가 없다
    survey.on_disruption(ON)
    assert seen == [("t1", settings_hook.GUARDIAN)]


def test_without_a_registered_reader_the_switch_is_off_and_settings_are_not_needed(monkeypatch):
    def no_settings():
        raise ConfigError("필수 환경변수가 없다")

    monkeypatch.setattr(core_settings, "get_settings", no_settings)
    assert survey.on_disruption(ON) == "ask_first"       # 도구 · 시험 — 읽을 운영자 값이 없으면 기본(꺼짐)


def test_switch_off_makes_decide_ask_first_and_safety_stays_a_safety_alert(service_tenant):
    item = _item()
    _console(True)
    assert pending.decide(constraints=ON, item=item).action == "apply"
    _console(False)
    decision = pending.decide(constraints=ON, item=item)
    assert (decision.action, decision.reason) == ("ask", "ask_first")
    safety = pending.decide(constraints=ON, item=item, report={"disruptions": [{"category": "earthquake"}]})
    assert (safety.action, safety.reason) == ("safety_alert", "safety_alert")


def test_switch_off_asks_before_weather_changes_on_a_turned_on_trip(service_tenant):
    rain = {"disruptions": [{"category": "forecast"}]}
    _console(True)
    assert pending.needs_consent(rain, ON) is False
    _console(False)
    assert pending.needs_consent(rain, ON) is True


def test_switch_off_keeps_protected_items_protected(service_tenant):
    item = _item()
    item.detail["customer_pinned"] = True
    _console(False)
    assert pending.decide(constraints=ON, item=item).reason == "protected"


def test_turning_it_back_on_restores_the_trip_because_nothing_was_rewritten(service_tenant):
    stored = copy.deepcopy(ON)
    _console(False)
    survey.on_disruption(stored)
    pending.decide(constraints=stored, item=_item())
    guardian.is_on(stored)
    assert stored == ON                                  # 판정은 저장값을 바꾸지 않는다
    _console(True)
    assert guardian.is_on(stored) is True


# ── 알림의 항로 지킴이 몫 ──────────────────────────────────────────────────────────────────────────

def _changed():
    return {"type": "change_notice", "text": "바꿨어요", "rollback": pending.rollback_offer(version=3, previous=2)}


def _asked():
    return {"type": "proposal_request", "reason": "ask_first", "text": "고를까요?", "options": [{"key": "a"}]}


def test_switch_on_annotates_as_before(service_tenant):
    _console(True)
    trip_id = uuid4()
    assert guardian.annotate(_changed(), constraints=ON, trip_id=trip_id)["guardian"] == {"changed": True}
    offer = guardian.annotate(_asked(), constraints=OFF, trip_id=trip_id)["guardian"]["offer"]
    assert offer["label"] == guardian.OFFER_LABEL and offer["path"] == f"/trips/{trip_id}?guardian=on"


def test_switch_off_adds_no_guardian_part_to_notices(service_tenant):
    _console(False)
    trip_id = uuid4()
    assert "guardian" not in guardian.annotate(_changed(), constraints=ON, trip_id=trip_id)
    assert "guardian" not in guardian.annotate(_asked(), constraints=OFF, trip_id=trip_id)
    assert "guardian" not in guardian.annotate(_asked(), constraints={}, trip_id=trip_id)
