# -*- coding: utf-8 -*-
"""계획 확인의 위험 표시가 **여행 날짜**를 따르는지 — 2026-10-18 현장 피드백.

「여행 날짜와 상관없이 현재 재난경보를 기준으로 일정 확인하라고 나온다」: 일주일 뒤 일정에 오늘 발령된 재난문자가 「!」로 붙었다.
지금 발령된 경보(`as_of_now`)는 시작이 가까운 일정에만 문제로 보이고, 먼 일정에서는 빼되 「문제 없음」이라고 말하지 않는다.
예보처럼 그 시각을 본 원인은 날짜가 멀어도 그대로 남는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.domains.travel_ops.components.intake import risks

NOW = datetime(2026, 10, 18, 19, 0, tzinfo=risks.KST)


class _NoDb:
    def transaction(self):
        raise RuntimeError("no db in this test")


def _item(item_id: str, when: datetime) -> dict:
    return {"id": item_id, "kind": "dining", "title": "광장시장", "date": when.date().isoformat(),
            "starts_at": when.strftime("%H:%M"), "ends_at": (when + timedelta(hours=1)).strftime("%H:%M"),
            "place": {"name": "광장시장", "latitude": 37.57, "longitude": 126.99, "weather_sensitive": True}}


def _check(*, extra=()):
    rows = [{"category": c, "status": "ok", "source": "test", "confirmed_at": NOW.isoformat()}
            for c in ("forecast", "weather_warning", "disaster_msg", "traffic_control", "air_quality", "earthquake")]

    def check(*, place, starts_at):
        return {"checks": rows, "advisories": [],
                "disruptions": [{"category": "disaster_msg", "text": "현재 서울지역에 강한 바람이 불고 있습니다"}, *extra]}
    return check


def _risk(review: dict, item_id: str) -> dict:
    return next(i for i in review["items"] if i["id"] == item_id)["risk"]


def test_far_trip_drops_current_disaster_message():
    review = {"items": [_item("far", NOW + timedelta(days=7))]}
    out = risks.decorate(_NoDb(), tenant_id="t", review=review, mode="cached", check=_check(), now=NOW)
    risk = _risk(out, "far")
    assert risk["status"] == "unknown"
    assert risk["code"] == "too_early"
    assert risk["problems"] == []
    assert risk["deferred_current"] == 1
    assert "반영하지 않았어요" in risk["reason"]


def test_far_trip_defers_only_timing_unknowns():
    review = {"items": [_item("far", NOW + timedelta(days=7))]}
    value = _risk(risks.decorate(_NoDb(), tenant_id="t", review=review,
                  mode="fresh", check=_check(), now=NOW), "far")
    assert value.get("deferred") is True
    assert value["unknown_categories"] == []
    assert value["status"] == "unknown"


def test_soon_item_still_shows_current_disaster_message():
    review = {"items": [_item("soon", NOW + timedelta(hours=5))]}
    out = risks.decorate(_NoDb(), tenant_id="t", review=review, mode="cached", check=_check(), now=NOW)
    risk = _risk(out, "soon")
    assert risk["status"] == "problem"
    assert len(risk["problems"]) == 1
    assert "deferred_current" not in risk


def test_far_trip_keeps_forecast_problem():
    rain = {"category": "forecast", "text": "그 시각 강수 확률 80%"}
    review = {"items": [_item("far", NOW + timedelta(days=3))]}
    out = risks.decorate(_NoDb(), tenant_id="t", review=review, mode="cached", check=_check(extra=[rain]), now=NOW)
    risk = _risk(out, "far")
    assert risk["status"] == "problem"
    assert [p["category"] for p in risk["problems"]] == ["forecast"]
    assert risk["deferred_current"] == 1


def test_far_trip_keeps_overlapping_control_period():
    visit = NOW + timedelta(days=7)
    control = {"category": "traffic_control", "starts_at": (visit - timedelta(hours=1)).isoformat(),
               "ends_at": (visit + timedelta(hours=1)).isoformat(), "message": "방문 기간 통제"}
    out = risks.decorate(_NoDb(), tenant_id="t", review={"items": [_item("far", visit)]},
                         mode="fresh", check=_check(extra=[control]), now=NOW)
    value = _risk(out, "far")
    assert value["status"] == "problem"
    assert [p["category"] for p in value["problems"]] == ["traffic_control"]
    assert not value.get("deferred")


def test_far_trip_without_as_of_now_marker_defers_current_warning(monkeypatch):
    monkeypatch.setattr(risks.risk_report, "judge_item", lambda *a, **k: {
        "status": "problem", "problems": [{"category": "disaster_msg", "text": "현재 경보"}],
        "unknown_categories": [], "categories": []})
    out = risks.decorate(_NoDb(), tenant_id="t", review={"items": [_item("far", NOW + timedelta(days=7))]},
                         mode="fresh", check=_check(), now=NOW)
    assert _risk(out, "far").get("deferred") is True
    assert _risk(out, "far")["problems"] == []


def test_reuse_rechecks_when_crossing_the_current_alert_boundary():
    item = _item("edge", NOW + timedelta(hours=24, minutes=5))
    previous = risks.decorate(_NoDb(), tenant_id="t", review={"items": [item]},
                              mode="fresh", check=_check(), now=NOW)
    calls = []
    def check(**kw):
        calls.append(kw)
        return _check()(**kw)
    out = risks.decorate(_NoDb(), tenant_id="t", review={"items": [item]}, mode="fresh",
                         check=check, now=NOW + timedelta(minutes=5), reuse=previous)
    assert len(calls) == 1
    assert _risk(out, "edge")["status"] == "problem"


def test_reuse_does_not_extend_original_result_lifetime():
    item = _item("far", NOW + timedelta(days=7))
    first = risks.decorate(_NoDb(), tenant_id="t", review={"items": [item]}, mode="fresh", check=_check(), now=NOW)
    second = risks.decorate(_NoDb(), tenant_id="t", review={"items": [item]}, mode="fresh", check=_check(),
                            now=NOW + timedelta(seconds=600), reuse=first)
    assert _risk(second, "far")["checked_at"] == _risk(first, "far")["checked_at"]
    calls = []
    def check(**kw):
        calls.append(kw)
        return _check()(**kw)
    risks.decorate(_NoDb(), tenant_id="t", review={"items": [item]}, mode="fresh", check=check,
                   now=NOW + timedelta(seconds=601), reuse=second)
    assert len(calls) == 1


def test_reuse_does_not_keep_a_problem_after_visit_ends():
    item = _item("ending", NOW - timedelta(minutes=55))
    first = risks.decorate(_NoDb(), tenant_id="t", review={"items": [item]}, mode="fresh", check=_check(), now=NOW)
    out = risks.decorate(_NoDb(), tenant_id="t", review={"items": [item]}, mode="fresh", check=_check(),
                         now=NOW + timedelta(minutes=5), reuse=first)
    assert _risk(out, "ending")["status"] == "not_applicable"


def test_reuse_normalizes_previous_date_semantics_without_mutating_cache():
    from copy import deepcopy
    item = _item("far", NOW + timedelta(days=7))
    previous = risks.decorate(_NoDb(), tenant_id="t", review={"items": [item]}, mode="fresh", check=_check(), now=NOW)
    legacy = _risk(previous, "far")
    legacy.pop("deferred")
    legacy["unknown_categories"] = [{"category": "disaster_msg", "code": "too_early"}]
    before = deepcopy(previous)
    def no_check(**kw):
        raise AssertionError("unchanged fresh result must be reused")
    out = risks.decorate(_NoDb(), tenant_id="t", review={"items": [item]}, mode="fresh", check=no_check,
                         now=NOW + timedelta(minutes=1), reuse=previous)
    assert _risk(out, "far").get("deferred") is True
    assert _risk(out, "far")["unknown_categories"] == []
    assert previous == before


@pytest.mark.parametrize("hours, deferred", [(24, False), (24 + 1 / 60, True)])
def test_current_alert_boundary_is_strict(hours, deferred):
    item = _item("edge", NOW + timedelta(hours=hours))
    out = risks.decorate(_NoDb(), tenant_id="t", review={"items": [item]}, mode="fresh", check=_check(), now=NOW)
    assert bool(_risk(out, "edge").get("deferred")) is deferred


@pytest.mark.parametrize("code", ["source_failed", "partial", "not_connected", "missing"])
def test_far_trip_preserves_real_unknowns(monkeypatch, code):
    unknown = {"category": "traffic_control", "code": code}
    monkeypatch.setattr(risks.risk_report, "judge_item", lambda *a, **k: {
        "status": "problem", "problems": [{"category": "disaster_msg"}],
        "unknown_categories": [unknown, {"category": "air_quality", "code": "too_early"}]})
    out = risks.decorate(_NoDb(), tenant_id="t", review={"items": [_item("far", NOW + timedelta(days=7))]},
                         mode="fresh", check=_check(), now=NOW)
    value = _risk(out, "far")
    assert value["unknown_categories"] == [unknown]
    assert value["status"] == "unknown" and not value.get("deferred")


@pytest.mark.parametrize("bounds, kept", [
    ({"starts_at": "2026-10-25T20:00:00+09:00"}, True),
    ({"ends_at": "2026-10-25T19:00:00+09:00"}, True),
    ({"starts_at": "2026-10-25T20:00:01+09:00"}, False),
    ({"ends_at": "2026-10-25T18:59:59+09:00"}, False),
    ({"starts_at": "2026-10-25T10:00:00Z", "ends_at": "2026-10-25T11:00:00Z"}, True),
    ({"starts_at": "invalid", "ends_at": "invalid"}, False),
    ({"starts_at": "2026-10-25T19:00:00"}, False),
    ({"starts_at": "2026-10-25T19:45:00+09:00", "ends_at": "2026-10-25T19:15:00+09:00"}, False),
])
def test_control_period_boundaries(bounds, kept):
    control = {"category": "traffic_control", **bounds}
    out = risks.decorate(_NoDb(), tenant_id="t", review={"items": [_item("far", NOW + timedelta(days=7))]},
                         mode="fresh", check=_check(extra=[control]), now=NOW)
    assert (_risk(out, "far")["status"] == "problem") is kept


@pytest.mark.parametrize("seconds, calls_expected", [(599, 0), (600, 0), (601, 1), (-1, 1)])
def test_reuse_freshness_endpoints(seconds, calls_expected):
    item = _item("far", NOW + timedelta(days=7))
    first = risks.decorate(_NoDb(), tenant_id="t", review={"items": [item]}, mode="fresh", check=_check(), now=NOW)
    calls = []
    def check(**kw):
        calls.append(kw)
        return _check()(**kw)
    risks.decorate(_NoDb(), tenant_id="t", review={"items": [item]}, mode="fresh", check=check,
                   now=NOW + timedelta(seconds=seconds), reuse=first)
    assert len(calls) == calls_expected


def test_far_trip_gets_no_risk_alternatives():
    review = {"items": [_item("far", NOW + timedelta(days=7))]}
    out = risks.decorate(_NoDb(), tenant_id="t", review=review, mode="cached", check=_check(), now=NOW)
    item = dict(out["items"][0], kind="activity")
    assert risks.alternatives(_NoDb(), tenant_id="t", review=out, item=item, now=NOW, use_engine=False) is None
