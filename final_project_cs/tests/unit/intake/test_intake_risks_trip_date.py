# -*- coding: utf-8 -*-
"""계획 확인의 위험 표시가 **여행 날짜**를 따르는지 — 2026-10-18 현장 피드백.

「여행 날짜와 상관없이 현재 재난경보를 기준으로 일정 확인하라고 나온다」: 일주일 뒤 일정에 오늘 발령된 재난문자가 「!」로 붙었다.
지금 발령된 경보(`as_of_now`)는 시작이 가까운 일정에만 문제로 보이고, 먼 일정에서는 빼되 「문제 없음」이라고 말하지 않는다.
예보처럼 그 시각을 본 원인은 날짜가 멀어도 그대로 남는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

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


def test_far_trip_gets_no_risk_alternatives():
    review = {"items": [_item("far", NOW + timedelta(days=7))]}
    out = risks.decorate(_NoDb(), tenant_id="t", review=review, mode="cached", check=_check(), now=NOW)
    item = dict(out["items"][0], kind="activity")
    assert risks.alternatives(_NoDb(), tenant_id="t", review=out, item=item, now=NOW, use_engine=False) is None
