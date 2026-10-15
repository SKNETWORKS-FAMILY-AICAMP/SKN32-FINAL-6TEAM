# -*- coding: utf-8 -*-
"""확인 화면의 「택시 호출 상품」 고르기 스위치 — 기본 꺼짐, 관리 콘솔 값이 먼저. `[2026-10-14 사용자 지시 · 핫픽스]`

꺼짐이면: ① 검사 응답에 `taxi_pricing` 이 없다(화면 칸이 사라진다) ② 앞서 저장된 고른 값도 계산에 쓰지 않는다
③ 고르기 요청은 거절한다(칸을 감춘 뒤에도 직접 보내는 요청이 먹지 않게).
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.components.intake import pipeline, review
from app.domains.travel_ops.components.intake.hours import HoursFacts
from app.domains.travel_ops.modules.web_account import web_guard

from tests.unit.travel.test_web_taxi_pricing_v1 import RecordingConnection, engine, inputs, pricing


@pytest.fixture(autouse=True)
def _no_reader():
    settings_hook.clear()
    yield
    settings_hook.clear()


def _console(value):
    settings_hook.register(lambda tenant, name: value if name == settings_hook.TAXI_CALL_PRODUCT else None)


def test_switch_is_listed_for_the_admin_console_and_off_by_default():
    spec = web_guard.specs()[settings_hook.TAXI_CALL_PRODUCT]
    assert spec.type == "bool" and spec.default is False
    assert spec.check(True) is None and spec.check("on") == "wrong_type"


def test_without_console_value_the_guardrail_decides_and_it_is_off():
    assert settings_hook.taxi_call_product_enabled("t1") is False


@pytest.mark.parametrize("stored, expected", [(True, True), (False, False)])
def test_console_value_wins(stored, expected):
    _console(stored)
    assert settings_hook.taxi_call_product_enabled("t1") is expected


@pytest.mark.parametrize("stored", ["on", 1, None])
def test_non_boolean_value_is_not_treated_as_on(stored):
    _console(stored)
    assert settings_hook.taxi_call_product_enabled("t1") is False


def test_unreadable_table_falls_back_to_off():
    def broken(tenant, name):
        raise RuntimeError("db down")

    settings_hook.register(broken)
    assert settings_hook.taxi_call_product_enabled("t1") is False


def _build(monkeypatch, product):
    monkeypatch.setattr(review, "facts_for", lambda *args: HoursFacts(True, {"hours": ["00:00", "23:59"]}))
    seen = []

    def factory(party, modes=None, *, constraints=None):
        seen.append(dict(constraints or {}))
        return engine()

    monkeypatch.setattr(review, "default_engine", factory)
    sources, claims = inputs(product)
    return review.build(None, tenant_id="t", intake_id="i", revision=1, sources=sources, claims=claims), seen


def test_off_hides_the_choice_and_ignores_a_value_saved_earlier(monkeypatch):
    built, seen = _build(monkeypatch, "capsi_immediate")
    assert built["taxi_pricing"] is None
    assert seen and all("taxi_call_product" not in c for c in seen)


def test_on_still_returns_the_choice_and_uses_it(monkeypatch):
    _console(True)
    built, seen = _build(monkeypatch, "capsi_immediate")
    assert built["taxi_pricing"] == pricing("capsi_immediate")
    assert any(c.get("taxi_call_product") == "capsi_immediate" for c in seen)


def test_public_view_drops_the_choice_of_a_review_stored_while_it_was_on():
    stored = {"items": [], "moves": [], "taxi_pricing": pricing()}
    assert review.public(stored, tenant_id="t")["taxi_pricing"] is None       # 꺼짐
    assert stored["taxi_pricing"] == pricing()                                # 저장본은 그대로
    assert review.public(stored)["taxi_pricing"] == pricing()                 # tenant 를 안 주면 이전과 같다
    _console(True)
    assert review.public(stored, tenant_id="t")["taxi_pricing"] == pricing()


def test_choosing_a_product_is_rejected_while_off_and_writes_nothing(monkeypatch):
    monkeypatch.setattr(pipeline, "_sources", lambda *args: [])
    monkeypatch.setattr(pipeline, "_claims", lambda *args: [])
    conn = RecordingConnection()
    with pytest.raises(pipeline.IntakeRejected) as error:
        pipeline.edit(conn, tenant_id="t", customer_id="c", intake_id="i", revision=3,
                      edits=[{"field": "trip.taxi_pricing", "value": pricing()}])
    assert error.value.code == "taxi_pricing_disabled"
    assert not any(sql.startswith(("INSERT", "UPDATE")) for sql, _ in conn.calls)
