"""Confirmed food requirements survive generated intake drafts and registration."""
from contextlib import nullcontext, contextmanager
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID

import pytest
from starlette.requests import Request

from app.domains.travel_ops.components.intake import assemble, pipeline, reopen, review, social_dining_plan, survey_answers
from app.domains.travel_ops.entry import trip_api
from app.domains.travel_ops.modules.web_account import web_guard
from tests.unit.travel.test_social_dining_plan import BODY, OWNER, setup


CONSTRAINTS = {
    "dietary": ["halal"], "allergies": ["peanut"],
    "survey": {"version": "2026-09-24.v1", "on_disruption": "ask_first",
               "priority_details": {"food": ["vegetarian"]},
               "custom_answers": {"food": "땅콩 알레르기"}},
}


def test_generated_constraints_reach_registration_body_without_aliasing_the_input():
    body = {**deepcopy(BODY), "constraints": deepcopy(CONSTRAINTS)}
    claims = [{**row, "source_id": "generated"} for row in social_dining_plan.build_rows(body)]
    built = assemble.assemble(intake_id="intake", revision=4,
                              sources=[{"source_id": "generated", "position": 0, "transcript": ""}], claims=claims)
    assert built.body.get("constraints") == CONSTRAINTS
    built.body["constraints"]["dietary"].append("vegan")
    assert body["constraints"]["dietary"] == ["halal"]
    assert next(row for row in claims if row["field"] == "trip.constraints")["value"]["dietary"] == ["halal"]


def test_generated_request_conditions_extend_existing_intake_constraints(monkeypatch):
    api, conn = setup(monkeypatch)
    conn.state["claims"].append({"source_id": "original", "field": "trip.constraints",
                                 "value": {"dietary": ["halal"]}, "method": "customer", "evidence": {},
                                 "needs_review": False, "note": None})
    body = {**deepcopy(BODY), "constraints": deepcopy(CONSTRAINTS)}
    api.stage_generated(conn, **OWNER, revision=3, body=body)
    built = assemble.assemble(intake_id="intake", revision=4, sources=conn.state["sources"], claims=conn.state["claims"])
    assert built.body.get("constraints") == CONSTRAINTS


@pytest.mark.parametrize("blocked", [False, True])
@pytest.mark.parametrize("given", [None, {"priority_details": {"food": ["vegan"]}}])
def test_confirmation_keeps_staged_food_and_merges_later_survey_answers(monkeypatch, given, blocked):
    from fastapi import HTTPException
    from app.domains.travel_ops.components.intake import registration
    customer = UUID("00000000-0000-0000-0000-000000000044")
    intake = UUID("00000000-0000-0000-0000-000000000055")
    body = {**deepcopy(BODY), "constraints": deepcopy(CONSTRAINTS)}
    body.pop("customer_id")
    built = SimpleNamespace(body=body, problems=[])
    class Conn:
        active = False
        @contextmanager
        def transaction(self):
            self.active = True
            try: yield
            finally: self.active = False
    conn = Conn()
    monkeypatch.setattr(trip_api, "get_connection", lambda: nullcontext(conn))
    def gate(current, *args):
        assert current is conn and conn.active
        if blocked: raise registration.RegistrationRefused(409, "intake_dining_check_pending", "확인 중")
    monkeypatch.setattr(registration, "require_review", gate)
    monkeypatch.setattr(registration, "confirmed_trip_id", lambda *args: None)
    monkeypatch.setattr(web_guard, "assert_human_check_configured", lambda: None)
    monkeypatch.setattr(web_guard, "count", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "draft", lambda *args, **kwargs: ("review", None, built))
    monkeypatch.setattr(pipeline, "mark_confirmed", lambda *args, **kwargs: None)
    monkeypatch.setattr(reopen, "session", lambda *args, **kwargs: None)
    monkeypatch.setattr(review, "load", lambda *args, **kwargs: None)
    monkeypatch.setattr(survey_answers, "stored", lambda *args, **kwargs: {"preferred_mobility": "public"})
    # `[2026-10-20 develop 병합]` 옛 슬롯 답은 저장 때 해석 이력이 있어야 읽힌다(role-manager 설문 묶음 개편 10-19)
    monkeypatch.setattr(survey_answers, "stored_resolved",
                        lambda *args, **kwargs: {"preferred_mobility": ("public", "preferred_mobility", "public")})
    # Bypass customer DB writes only after the real confirmation endpoint has
    # assembled and validated the final registration request.
    router = trip_api.build_trip_router()
    endpoint = next(route.endpoint for route in router.routes if route.path.endswith("/{intake_id}/confirm"))
    captured = []
    create_cell = next(cell for cell in endpoint.__closure__ if callable(cell.cell_contents)
                       and getattr(cell.cell_contents, "__name__", "") == "_create_trip")

    def capture(tenant, request):
        assert conn.active
        captured.append(request.model_dump(mode="json"))
        return {"trip_id": "00000000-0000-0000-0000-000000000066", "created": True}

    monkeypatch.setattr(create_cell, "cell_contents", capture)
    request = trip_api.IntakeConfirmIn(revision=4, survey=given)
    if blocked:
        with pytest.raises(HTTPException) as caught:
            endpoint(intake_id=intake, request=request, http=Request({"type": "http", "headers": []}),
                     who=("tenant", customer))
        assert caught.value.status_code == 409 and not captured
        return
    endpoint(intake_id=intake, request=request, http=Request({"type": "http", "headers": []}),
             who=("tenant", customer))
    constraints = captured[0]["constraints"]
    assert constraints["dietary"] == ["halal"] and constraints["allergies"] == ["peanut"]
    assert constraints["survey"]["priority_details"] == {
        "food": ["vegan"] if given else ["vegetarian"], "mobility": ["public"]}
    assert constraints["survey"]["custom_answers"]["food"] == "땅콩 알레르기"
