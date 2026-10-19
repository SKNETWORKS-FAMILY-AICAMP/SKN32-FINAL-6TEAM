"""계획 확인에서도 6종 위험을 숨기지 않고 안전 대안만 고객이 고른다."""
from copy import deepcopy
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import candidates, review, risks
from app.domains.travel_ops.components.places import catalog_pool
from app.domains.travel_ops.components.planning.planner import Cand
from app.domains.travel_ops.components.team_hooks import legs
from app.domains.travel_ops.components.watch import risk_report

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 1, 14, tzinfo=KST)
STAMP = NOW.isoformat()


def row(**extra):
    return {"id": "1-0", "source_id": str(uuid4()), "index": 0, "title": "야외 축제", "kind": "activity",
            "day": 1, "date": "2030-01-01", "starts_at": "13:00", "ends_at": "16:00", "locked": False,
            "place_state": "found", "place": {"name": "야외 축제", "latitude": 37.5, "longitude": 127.0,
                "weather_sensitive": True, "source": "tour_api"}, "rows": [], **extra}


def report(*problems, failed=()):
    return {"verdict": "fatal" if failed else "disrupted" if problems else "clear", "checked_at": STAMP,
            "checks": [{"category": category, "status": "failed" if category in failed else "ok",
                        "source": "test_source", "confirmed_at": STAMP} for category in risk_report.CATEGORIES],
            "disruptions": list(problems), "failed_categories": list(failed)}


WIND = {"category": "weather_warning", "kind": "강풍주의보", "source": "kma", "confirmed_at": STAMP}
ROAD = {"category": "traffic_control", "kind": "road_closed", "road": "시험로",
        "message": "시험로 양방향 전면통제", "ends_at": "2030-01-01T23:00:00+09:00", "source": "utic"}


def decorated(item=None, check=None):
    return risks.decorate(None, tenant_id="unit", review={"items": [item or row()], "ready": True,
        "needs": {"total": 0}}, check=check or (lambda **kw: report(WIND, ROAD)), now=NOW, mode="fresh")


def test_weather_and_road_facts_both_appear_without_changing_registration_policy():
    source = row()
    before = deepcopy(source)
    output = decorated(source)
    risk = output["items"][0]["risk"]
    assert risk["status"] == "problem" and len(risk["problems"]) == 2
    assert "강풍" in risk["problems"][0]["summary"]
    assert "시험로 양방향 전면통제" in risk["problems"][1]["summary"]
    assert "23:00" in risk["problems"][1]["summary"]
    assert risk["data_confirmed_at"] == STAMP and output["ready"] is True
    assert output["needs"] == {"total": 0} and source == before


def test_missing_source_is_unknown_instead_of_clear():
    result = decorated(check=lambda **kw: report(failed=["traffic_control"]))["items"][0]["risk"]
    assert result["status"] == "unknown"
    assert result["unknown_categories"][0]["category"] == "traffic_control"


def test_partial_sources_preserve_the_confirmed_problem_and_unknown_coverage():
    def check(**kw):
        value = report(WIND, ROAD)
        value["checks"][3]["partial_from"] = ["secondary_source"]
        return value
    value = decorated(check=check)["items"][0]["risk"]
    assert value["status"] == "problem" and len(value["problems"]) == 2
    assert value["unknown_categories"][0]["code"] == "partial"


def test_an_ongoing_visit_checks_the_current_time():
    calls = []
    decorated(check=lambda **kw: calls.append(kw) or report())
    assert calls[0]["starts_at"] == NOW


def test_a_future_snapshot_is_not_called_the_future_weather_warning():
    # 2026-10-19: 재난경보 날짜 수정(risks._for_trip_date) 뒤에는 시작이 24시간보다 먼 일정에 「지금 상태」 원인을
    # 문제로 붙이지 않는다 — 문제 0개 · 「아직 확인 전」(unknown · too_early)이고, 뺀 개수는 deferred_current 로 남는다.
    value = decorated(row(date="2030-01-03"))["items"][0]["risk"]
    assert value["status"] == "unknown" and value["code"] == "too_early"
    assert value["problems"] == [] and value["deferred_current"] >= 1
    assert any(c["code"] == "too_early" for c in value["unknown_categories"])


def test_missing_visit_time_and_source_errors_are_visible_unknown(monkeypatch):
    result = decorated(row(starts_at=None))["items"][0]["risk"]
    assert result["status"] == "unknown" and result["code"] == "no_time"
    monkeypatch.setattr(risks, "check_for", lambda mode: (_ for _ in ()).throw(RuntimeError("sensitive config")))
    result = risks.decorate(None, tenant_id="unit", review={"items": [row()]}, now=NOW, mode="fresh")
    assert result["items"][0]["risk"]["status"] == "unknown"
    assert "sensitive config" not in str(result)


def test_ended_visits_are_not_rechecked():
    calls = []
    value = decorated(row(ends_at="14:00"), lambda **kw: calls.append(kw) or report())["items"][0]["risk"]
    assert value["status"] == "not_applicable" and calls == []


def test_first_review_refreshes_normally_then_polling_is_cache_only(monkeypatch):
    cache = {"items": [row()], "ready": True}
    modes, writes = [], []
    monkeypatch.setattr(review, "load", lambda *a: dict(cache))
    def decorate(conn, **kw):
        modes.append(kw["mode"])
        return {**kw["review"], "risk_schema_version": risks.SCHEMA_VERSION}
    def save(conn, tenant, intake, revision, payload):
        writes.append(payload)
        cache.update(payload)
    monkeypatch.setattr(risks, "decorate", decorate)
    monkeypatch.setattr(review, "store", save)
    for _ in range(2):
        review.ensure(None, tenant_id="unit", intake_id=uuid4(), revision=1, sources=[], claims=[])
    assert modes == ["fresh", "cached"] and len(writes) == 1


def test_the_existing_candidates_api_dispatches_to_safety_validation(monkeypatch):
    result = {"candidates": [], "notes": ["verification_unavailable"]}
    monkeypatch.setattr(risks, "alternatives", lambda *a, **k: result)
    assert candidates.alternatives(None, tenant_id="unit", review={}, item={}) is result


@pytest.mark.parametrize("protected", [{"locked": True}, {"booked": True}, {"vendor_booking": True}])
def test_fixed_or_booked_visits_keep_their_existing_protection(protected):
    item = row(risk={"status": "problem", "problems": [WIND]}, **protected)
    output = risks.alternatives(None, tenant_id="unit", review={"items": [item]}, item=item, now=NOW)
    assert output["candidates"] == [] and "protected_schedule" in output["notes"]


def test_safe_indoor_candidates_use_normal_assessment_and_keep_the_proposed_time(monkeypatch):
    item = row(risk={"status": "problem", "problems": [WIND]})
    cand = Cand(key="tour_123", name="공식 실내 전시관", kind="activity", lat=37.51, lon=127.0,
                attributes={"source_content_id": "123", "source_content_type_id": "14",
                            "hours": ["09:00", "22:00"]}, origin="place_catalog", weather_sensitive=False)
    calls = []
    monkeypatch.setattr(catalog_pool, "nearby_activities", lambda *a, **kw: calls.append(kw) or [cand])
    monkeypatch.setattr(catalog_pool, "reuse_hours", lambda *a: {})
    monkeypatch.setattr(legs, "leg_planner", lambda *a: lambda *args: ({"eta_min": 20}, None))
    monkeypatch.setattr(candidates, "assess", lambda *a: {"rows": [], "fits": True, "status": "ok", "slack": {}, "estimated": False})
    output = risks.alternatives(None, tenant_id="unit", review={"items": [item]}, item=item, now=NOW,
                                check=lambda **kw: report(), use_engine=False)
    assert output["candidates"] and calls[0]["indoor_only"] is True and calls[0]["require_hours"] is True
    option = output["candidates"][0]
    assert option["place"]["name"] == cand.name and option["risk"]["status"] == "clear"
    assert option["date"] == "2030-01-01" and option["starts_at"] >= "14:20"
    starts = datetime.fromisoformat(option["date"] + "T" + option["starts_at"])
    ends = datetime.fromisoformat(option["date"] + "T" + option["ends_at"])
    assert (ends - starts).total_seconds() == 120 * 60


def test_unknown_candidate_risk_never_appears_as_a_safe_option(monkeypatch):
    item = row(risk={"status": "problem", "problems": [WIND]})
    cand = Cand(key="tour_123", name="공식 실내 전시관", kind="activity", lat=37.51, lon=127.0,
                attributes={"source_content_id": "123", "hours": ["09:00", "22:00"]}, origin="place_catalog", weather_sensitive=False)
    monkeypatch.setattr(catalog_pool, "nearby_activities", lambda *a, **kw: [cand])
    monkeypatch.setattr(catalog_pool, "reuse_hours", lambda *a: {})
    monkeypatch.setattr(legs, "leg_planner", lambda *a: None)
    output = risks.alternatives(None, tenant_id="unit", review={"items": [item]}, item=item, now=NOW,
                                check=lambda **kw: report(failed=["traffic_control"]), use_engine=False)
    assert output["candidates"] == [] and "verification_unavailable" in output["notes"]


def test_partial_traffic_coverage_keeps_a_customer_choice_with_explicit_warning(monkeypatch):
    item = row(risk={"status": "problem", "problems": [WIND]})
    cand = Cand(key="tour_123", name="공식 실내 전시관", kind="activity", lat=37.51, lon=127.0,
                attributes={"source_content_id": "123", "hours": ["09:00", "22:00"]}, origin="place_catalog", weather_sensitive=False)
    monkeypatch.setattr(catalog_pool, "nearby_activities", lambda *a, **kw: [cand])
    monkeypatch.setattr(catalog_pool, "reuse_hours", lambda *a: {})
    monkeypatch.setattr(legs, "leg_planner", lambda *a: None)
    monkeypatch.setattr(candidates, "assess", lambda *a: {"rows": [], "fits": True, "status": "ok", "slack": {}, "estimated": False})
    def partial(**kwargs):
        value = report()
        value["checks"][3]["partial_from"] = ["secondary_traffic_source"]
        return value
    output = risks.alternatives(None, tenant_id="unit", review={"items": [item]}, item=item, now=NOW,
                                check=partial, use_engine=False)
    assert output["candidates"] and "indoor_with_coverage_warning" in output["notes"]
    option = output["candidates"][0]
    assert option["fits"] is True and option["status"] == "warn" and option["risk"]["status"] == "unknown"
    assert option["risk"]["unknown_categories"][0]["code"] == "partial"
    assert any(r["row"] == "risk" and r["result"] == "unknown" for r in option["rows"])
    assert "교통자료 일부 미확인" in option["reason"]
