"""Real HTTP confirm + draft/assemble/registration/create, SQL-recording fake UOW.

Authentication is an explicit FastAPI dependency seam, never a forged cookie.
External databases, providers and notification dispatch are not used.
"""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.domains.travel_ops.components.intake import prepared, survey_answers
from app.domains.travel_ops.components.itinerary import itinerary_checks as checks
from app.domains.travel_ops.entry import trip_api
from app.domains.travel_ops.modules.web_account import web_guard


@pytest.fixture
def confirm_api(monkeypatch):
    now = datetime(2032, 5, 8, 12, tzinfo=checks.KST)
    customer, intake, source, saved = (UUID(int=n) for n in (44, 55, 66, 77))

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    monkeypatch.setattr(checks, "datetime", Frozen)

    class UOW:
        status = "review"
        owner = customer
        offsets = [-1]
        queries = None
        writes = None
        boundary = 0

        def __init__(self):
            self.queries, self.writes = [], []

        def cursor(self):
            return nullcontext(self)

        def transaction(self):
            return nullcontext(self)

        def execute(self, sql, params):
            self.queries.append((sql, params))
            if not sql.startswith("SELECT"):
                self.writes.append(sql)
                raise AssertionError("unexpected persistent mutation")
            if "customer_id=%s" in sql:
                assert params[:2] == ("confirm-proof", intake)
                self.rows = [(self.status, 1, saved if self.status == "confirmed" else None)] if params[2] == self.owner else []
            elif "FROM intake_claims" in sql:
                fields = {"trip.title": "합성 자유시간", "trip.party_size": 1}
                for i, offset in enumerate(self.offsets):
                    fields.update({f"items[{i}].{key}": value for key, value in {
                        "title": "자유시간", "date": (now + timedelta(days=offset)).date().isoformat(),
                        "starts_at": "10:00", "ends_at": "11:00", "kind": "activity", "place": None,
                    }.items()})
                self.rows = [(source, field, value, "customer", {"none": field.endswith(".place"), "line": 1}, False, None)
                             for field, value in fields.items()]
            elif "FROM intake_sources" in sql:
                self.rows = [(source, 0, "text", None, "10:00 자유시간", False, {}, 0, [])]
            elif "FROM intake_reviews" in sql:
                self.rows = [(deepcopy(self.cached),)]
            elif "SELECT reopen_trip_id" in sql:
                self.rows = [(None, None, None)]
            elif "SELECT status, revision FROM trip_intakes" in sql:
                self.rows = [(self.status, 1)]
            elif "SELECT trip_id FROM trip_intakes" in sql:
                self.rows = []
            elif "pg_advisory_xact_lock" in sql:
                self.rows = []
            else:
                raise AssertionError(f"uncontracted SQL: {sql}")

        def fetchone(self):
            return self.rows[0] if self.rows else None

        def fetchall(self):
            return self.rows

    db = UOW()
    db.cached = {"revision": 1, "ready": True, "checked": True, "items": [], "moves": [],
                 "needs": {"items": 0, "moves": 0, "total": 0}}
    monkeypatch.setattr(trip_api, "get_connection", lambda: nullcontext(db))
    class Store:
        def __init__(self, tenant):
            assert tenant == "confirm-proof"
        def by_request_key(self, *args):
            return None
        def latest(self, *args):
            return {"customer_id": customer}, []
    monkeypatch.setattr(trip_api, "TripStore", Store)
    monkeypatch.setattr(trip_api, "_trip_view", lambda *args: {"trip_id": str(saved), "version": 1})
    monkeypatch.setattr(web_guard, "assert_human_check_configured", lambda: None)
    monkeypatch.setattr(web_guard, "count", lambda *args, **kwargs: None)
    monkeypatch.setattr(survey_answers, "stored", lambda *args, **kwargs: {})
    monkeypatch.setattr(survey_answers, "stored_resolved", lambda *args, **kwargs: {})
    monkeypatch.setattr(prepared, "with_alternates", lambda *args, **kwargs: kwargs["body"])
    def boundary(*args, **kwargs):
        db.boundary += 1
        raise HTTPException(418, {"proof": "passed-calendar-guard-before-write"})
    monkeypatch.setattr(trip_api.guest_policy, "check_new_trip", boundary)
    router = trip_api.build_trip_router()
    route = next(r for r in router.routes if r.path.endswith("/{intake_id}/confirm"))
    auth = route.dependant.dependencies[0].call
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth] = lambda: ("confirm-proof", customer)
    client = TestClient(app)
    return db, client, app, auth, f"/v1/web/trip-intakes/{intake}/confirm"


def test_confirm_stale_ready_cache_rejected_without_writes(confirm_api):
    db, client, _, _, url = confirm_api
    before = deepcopy(db.cached)
    response = client.post(url, json={"revision": 1})
    assert response.status_code == 422, response.text
    error = response.json()["detail"]["error"]
    assert error["code"] == "itinerary_infeasible"
    assert error["violations"][0]["code"] == "all_dates_in_past"
    assert "여행 날짜를 확인" in error["message"]
    assert db.boundary == 0 and db.writes == []
    assert db.cached == before and db.cached["ready"] is True


@pytest.mark.parametrize("offsets", [[-1, 0], [-1, 1], [0], [1]])
def test_confirm_nonpast_reaches_next_boundary(confirm_api, offsets):
    db, client, _, _, url = confirm_api
    db.offsets = offsets
    response = client.post(url, json={"revision": 1})
    assert response.status_code == 418, response.text
    assert db.boundary == 1 and db.writes == []


def test_confirm_existing_confirmed_is_idempotent(confirm_api):
    db, client, _, _, url = confirm_api
    db.status = "confirmed"
    response = client.post(url, json={"revision": 1})
    assert response.status_code == 200, response.text
    assert response.json()["trip"]["created"] is False
    assert db.boundary == 0 and db.writes == []


def test_confirm_other_owner_is_404_before_review(confirm_api):
    db, client, _, _, url = confirm_api
    db.owner = UUID(int=999)
    response = client.post(url, json={"revision": 1})
    assert response.status_code == 404, response.text
    assert len(db.queries) == 1 and db.writes == [] and db.boundary == 0


def test_confirm_no_auth_does_not_reach_draft(confirm_api, monkeypatch):
    from app.domains.travel_ops.modules.web_account import web_cookie
    monkeypatch.setattr(web_cookie, "get_connection", lambda: nullcontext(confirm_api[0]))
    db, client, app, auth, url = confirm_api
    del app.dependency_overrides[auth]
    response = client.post(url, json={"revision": 1})
    assert response.status_code == 401, response.text
    assert db.queries == [] and db.writes == [] and db.boundary == 0
