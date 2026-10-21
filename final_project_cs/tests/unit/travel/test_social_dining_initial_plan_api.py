"""새 SNS 진입의 최초 생성은 여행 등록 전에 같은 접수의 초안으로 돌아온다."""
from contextlib import nullcontext
from types import ModuleType, SimpleNamespace
import sys
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domains.travel_ops.entry import trip_api
from app.domains.travel_ops.components.intake import pipeline, reopen, survey_answers
from app.domains.travel_ops.components.planning import planner
from app.domains.travel_ops.components.team_hooks import dining_ledger
from app.domains.travel_ops.modules.web_account import web_guard


def test_generate_for_saved_links_returns_draft_without_registering(monkeypatch):
    customer = UUID("00000000-0000-0000-0000-000000000044")
    intake = UUID("00000000-0000-0000-0000-000000000055")
    monkeypatch.setattr(trip_api, "get_connection", lambda: nullcontext(object()))
    monkeypatch.setattr(web_guard, "assert_human_check_configured", lambda: None)
    monkeypatch.setattr(web_guard, "count", lambda *args, **kwargs: None)
    built = SimpleNamespace(body={"items": [], "places": [], "title": "맛집 후보 여행"},
                            plan={"preferences": ""})
    monkeypatch.setattr(pipeline, "draft", lambda *args, **kwargs: ("review", 1, built))
    monkeypatch.setattr(reopen, "session", lambda *args, **kwargs: None)
    monkeypatch.setattr(survey_answers, "stored", lambda *args, **kwargs: {})
    monkeypatch.setattr(survey_answers, "stored_resolved", lambda *args, **kwargs: {})
    monkeypatch.setattr(dining_ledger, "require_planner_factory", lambda: None)
    monkeypatch.setattr(dining_ledger, "planner_factory", lambda *args, **kwargs: None)

    class Store:
        def __init__(self, tenant):
            pass

        def by_request_key(self, *args, **kwargs):
            return None

        def create(self, *args, **kwargs):
            raise AssertionError("review_only must not register a trip or enqueue a notice")

    monkeypatch.setattr(trip_api, "TripStore", Store)
    draft_body = {"title": "검증한 초안", "items": [], "places": [], "routes": []}
    draft = SimpleNamespace(as_create_body=lambda **kwargs: draft_body)
    monkeypatch.setattr(planner, "plan_trip", lambda **kwargs: SimpleNamespace(draft=draft, coverage={}, checks=[]))
    module = ModuleType("app.domains.travel_ops.components.intake.social_dining_plan")

    def stage(conn, **kwargs):
        assert kwargs["customer_id"] == customer and kwargs["intake_id"] == intake
        assert kwargs["body"] is draft_body
        return {"intake_id": str(intake), "status": "review", "revision": 2,
                "review": {"items": []}, "check": {"ready": False}}

    module.stage_generated = stage
    monkeypatch.setitem(sys.modules, module.__name__, module)
    router = trip_api.build_trip_router()
    app = FastAPI()
    route = next(route for route in router.routes if route.path.endswith("/{intake_id}/plan"))
    for dependency in route.dependant.dependencies:
        app.dependency_overrides[dependency.call] = lambda: ("travel-test", customer)
    app.include_router(router)
    response = TestClient(app).post(f"/v1/web/trip-intakes/{intake}/plan", json={
        "revision": 1, "start_date": "2040-10-15", "days": 1, "party_size": 2, "review_only": True})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["intake_id"] == str(intake) and result["status"] == "review" and result["revision"] == 2
    assert "trip" not in result
