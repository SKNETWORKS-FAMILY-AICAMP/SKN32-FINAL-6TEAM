# -*- coding: utf-8 -*-
"""수정 모드 열기가 등록 때 잰 이동을 다시 쓴다 — 2026-10-21 ST4F-705(사용자 지시 「이미 있는 일정을 다시 검사할 필요가 있나」).

「일정 수정」(`POST /v1/web/trips/{id}/reopen`)은 새 수정 접수의 첫 판을 검사한다. 앞 판이 없어 모든 구간을 계산기로 다시 쟀고, 등록한 수단을 구간마다
고른 수단으로 싣기 때문에(`reopen._trip_modes`) 구간마다 두 번(추천 · 고른 수단) 쟀다 — 로컬 실측 16.4초. 이제 첫 판은 같은 여행을 앞서 검사한 가장 최근 판을
앞 판으로 쓰고(`review._reopened_from`), 고른 수단이 앞 판의 추천과 같으면 그 구간 계산을 그대로 쓴다.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from app.domains.travel_ops.components.intake import review, risks
from app.domains.travel_ops.components.intake.hours import HoursFacts
from tests.unit.travel.test_web_taxi_pricing_v1 import inputs


@pytest.fixture()
def ensured(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_build(conn, **kwargs):
        calls.append(kwargs)
        return {"revision": kwargs["revision"], "items": [], "moves": [], "needs": {"total": 0}, "ready": True}

    monkeypatch.setattr(review, "build", fake_build)
    monkeypatch.setattr(review, "load", lambda *a, **k: None)
    monkeypatch.setattr(review, "store", lambda *a, **k: None)

    def fake_decorate(conn, *, tenant_id, review, mode, reuse=None):
        calls.append({"risk_mode": mode, "reuse": reuse})
        return review

    monkeypatch.setattr(risks, "decorate", fake_decorate)
    return calls


def test_a_reopened_first_check_starts_from_the_trip_s_latest_check(ensured, monkeypatch) -> None:
    prior = {"revision": 3, "items": [], "moves": []}
    asked: list[Any] = []
    monkeypatch.setattr(review, "_reopened_from", lambda conn, tenant_id, intake_id: asked.append(intake_id) or prior)
    review.ensure(object(), tenant_id="t", intake_id="edit", revision=1, sources=[], claims=[], force=True)
    assert asked == ["edit"]
    assert ensured[-2]["previous"] is prior                       # 이동 — 같은 구간은 앞 판 값
    assert ensured[-1] == {"risk_mode": "fresh", "reuse": prior}  # 위험 — 방금 본 일정만 다시 쓴다(그 밖은 지금처럼 새로)


def test_later_revisions_keep_their_own_previous_and_ask_no_trip_check(ensured, monkeypatch) -> None:
    monkeypatch.setattr(review, "_reopened_from", lambda *a, **k: pytest.fail("둘째 판부터는 그 접수의 앞 판을 쓴다"))
    review.ensure(object(), tenant_id="t", intake_id="edit", revision=2, sources=[], claims=[], force=True, previous_revision=1)
    review.ensure(object(), tenant_id="t", intake_id="edit", revision=4, sources=[], claims=[], force=True)
    assert ensured[-2]["previous"] is None


def _counting_engine(calls: list[Any]):
    def factory(party, modes=None, *, constraints=None):
        def run(a, b, arrive, not_before=None):
            calls.append(modes)
            start = not_before or arrive - timedelta(minutes=20)
            option = {"id": "taxi", "label": "택시", "eta_min": 20, "uses": [], "fare_krw": 10000}
            return {"route": {"options": [option], "planned": "taxi"}, "starts_at": start,
                    "ends_at": start + timedelta(minutes=20), "eta_min": 20, "left_out": []}, None
        return run
    return factory


def _with_mode(claims: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    """수정 접수가 싣는 등록한 수단 — `reopen._trip_modes` 의 값 줄(`method: trip`)."""
    return claims + [{"source_id": "s", "field": "moves[0-0~0-1].mode", "value": mode, "method": "trip",
                      "evidence": {}, "needs_review": False, "note": None}]


def test_a_reopened_mode_the_registration_check_recommended_is_not_measured_again(monkeypatch) -> None:
    monkeypatch.setattr(review, "facts_for", lambda *args: HoursFacts(True, {"hours": ["00:00", "23:59"]}))
    calls: list[Any] = []
    monkeypatch.setattr(review, "default_engine", _counting_engine(calls))
    sources, claims = inputs()
    registered = review.build(None, tenant_id="t", intake_id="reg", revision=1, sources=sources, claims=claims)
    assert registered["moves"][0]["mode"] == "taxi" and not registered["moves"][0]["mode_choice"] and calls

    calls.clear()
    reopened = review.build(None, tenant_id="t", intake_id="edit", revision=1, sources=sources, claims=_with_mode(claims, "taxi"),
                            previous=registered)
    assert calls == []                                             # 계산기를 부르지 않았다(전에는 추천 · 고른 수단 두 번)
    move, before = reopened["moves"][0], registered["moves"][0]
    assert move["mode_choice"] == {"mode": "taxi", "state": "kept"} and move["recommended_mode"] == "taxi"
    assert (move["minutes"], move["fare_krw"], move["rows"]) == (before["minutes"], before["fare_krw"], before["rows"])
    assert move["sig"] != before["sig"] and "#m=taxi" in move["sig"]   # 다음 판은 고른 수단이 든 키로 다시 쓴다

    calls.clear()
    again = review.build(None, tenant_id="t", intake_id="edit", revision=2, sources=sources, claims=_with_mode(claims, "taxi"),
                         previous=reopened)
    assert calls == [] and again["moves"][0]["sig"] == move["sig"]


def test_a_place_picked_at_registration_is_the_same_segment_once_reopened(monkeypatch) -> None:
    """등록 때 고객이 고른 장소(`customer`)를 수정 접수는 등록한 값(`method: trip` → `found`)으로 싣는다 — 같은 구간이다(로컬 실측: 8구간 중 4구간이 이 차이로 다시 재졌다)."""
    monkeypatch.setattr(review, "facts_for", lambda *args: HoursFacts(True, {"hours": ["00:00", "23:59"]}))
    calls: list[Any] = []
    monkeypatch.setattr(review, "default_engine", _counting_engine(calls))
    sources, claims = inputs()                                     # 장소 값 줄이 고객 값(`customer`)
    registered = review.build(None, tenant_id="t", intake_id="reg", revision=1, sources=sources, claims=claims)
    assert registered["items"][0]["place_state"] == "customer"

    calls.clear()
    trip_claims = [{**c, "method": "trip"} for c in claims]
    reopened = review.build(None, tenant_id="t", intake_id="edit", revision=1, sources=sources, claims=_with_mode(trip_claims, "taxi"),
                            previous=registered)
    assert reopened["items"][0]["place_state"] == "found" and calls == []
    assert reopened["moves"][0]["mode_choice"] == {"mode": "taxi", "state": "kept"}


def test_a_different_mode_or_a_moved_stop_is_measured_as_before(monkeypatch) -> None:
    monkeypatch.setattr(review, "facts_for", lambda *args: HoursFacts(True, {"hours": ["00:00", "23:59"]}))
    calls: list[Any] = []
    monkeypatch.setattr(review, "default_engine", _counting_engine(calls))
    sources, claims = inputs()
    registered = review.build(None, tenant_id="t", intake_id="reg", revision=1, sources=sources, claims=claims)

    calls.clear()
    review.build(None, tenant_id="t", intake_id="edit", revision=1, sources=sources, claims=_with_mode(claims, "walk"), previous=registered)
    assert calls                                                   # 앞 판의 추천(택시)과 다른 수단 — 지금처럼 잰다

    calls.clear()
    moved = [{**c, "value": "11:30"} if c["field"] == "items[1].starts_at" else c for c in claims]
    review.build(None, tenant_id="t", intake_id="edit", revision=1, sources=sources, claims=_with_mode(moved, "taxi"), previous=registered)
    assert calls                                                   # 뒤 일정 시각이 바뀌면 같은 구간이 아니다
