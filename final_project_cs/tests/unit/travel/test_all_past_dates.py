"""Calendar-only admission guard; frozen product clock, no providers or database."""
from datetime import datetime, timedelta

from app.domains.travel_ops.components.itinerary import itinerary_checks as checks


def test_yesterday_is_rejected():
    now = datetime(2032, 5, 8, 12, tzinfo=checks.KST)
    yesterday = now - timedelta(days=1)
    assert checks.all_dates_before_today([(yesterday, yesterday)], now=now)


def test_calendar_matrix_and_product_midnight():
    from datetime import timezone
    now = datetime(2032, 5, 8, 0, 1, tzinfo=checks.KST)
    yesterday, tomorrow = now - timedelta(days=1), now + timedelta(days=1)
    cases = [([(yesterday, yesterday), (yesterday - timedelta(days=1), None)], True),
             ([(yesterday, None), (now, None)], False),
             ([(yesterday, None), (tomorrow, None)], False),
             ([(now, None)], False), ([(tomorrow, None)], False),
             ([], False), ([(None, None)], False),
             ([(yesterday, None), (None, None)], False),
             ([(yesterday, now)], False), ([(yesterday, tomorrow)], False)]
    for spans, expected in cases:
        assert checks.all_dates_before_today(spans, now=now) is expected
        assert checks.all_dates_before_today(spans, now=now.astimezone(timezone.utc)) is expected
    before_midnight = now - timedelta(minutes=2)
    assert not checks.all_dates_before_today([(yesterday, None)], now=before_midnight)


def test_review_has_visible_block_and_preserves_source_dates(monkeypatch):
    from app.domains.travel_ops.components.intake import review
    from app.domains.travel_ops.components.intake.hours import HoursFacts
    now = datetime(2032, 5, 8, 12, tzinfo=checks.KST)
    yesterday = (now - timedelta(days=1)).date().isoformat()
    sources = [{"source_id": "s", "position": 0, "kind": "text", "filename": None,
                "transcript": "10:00 자유시간"}]
    values = {"title": "자유시간", "date": yesterday, "starts_at": "10:00", "ends_at": "11:00",
              "kind": "activity", "place": None}
    claims = [{"source_id": "s", "field": f"items[0].{field}", "value": value, "method": "customer",
               "evidence": {"line": 1, "none": field == "place"}, "needs_review": False, "note": None}
              for field, value in values.items()]
    monkeypatch.setattr(review.settings_hook, "taxi_call_product_enabled", lambda _: False)
    monkeypatch.setattr(review, "facts_for", lambda *a: HoursFacts(False, {}))
    result = review.build(None, tenant_id="t", intake_id="i", revision=1, sources=sources,
                          claims=claims, now=now, use_engine=False)
    public = review.public(result)
    assert public["ready"] is False
    assert any(row["text"] == "모든 일정이 오늘 이전이에요. 여행 날짜를 확인해주세요"
               for item in public["items"] for row in item["rows"])
    assert public["items"][0]["date"] == yesterday


def test_normal_create_api_rejects_before_new_trip_write(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from uuid import UUID
    import pytest
    from fastapi import HTTPException
    from app.domains.travel_ops.entry import trip_api
    from app.core.service_bindings import standalone_services

    now = datetime(2032, 5, 8, 12, tzinfo=checks.KST)
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)
    monkeypatch.setattr(checks, "datetime", Frozen)
    class Conn:
        def cursor(self): return nullcontext(self)
        def transaction(self): return nullcontext(self)
        def execute(self, *a): pass
    class Store:
        def __init__(self, tenant): pass
        def by_request_key(self, *a): return None
    monkeypatch.setattr(trip_api, "get_connection", lambda: nullcontext(Conn()))
    monkeypatch.setattr(trip_api, "TripStore", Store)
    def no_write(*a, **kw):
        raise AssertionError("all-past plan reached new-trip write boundary")
    monkeypatch.setattr(trip_api.guest_policy, "check_new_trip", no_write)
    with standalone_services():
        router = trip_api.build_trip_router()
        endpoint = next(r.endpoint for r in router.routes if r.path == "/v1/trips" and "POST" in r.methods)
        yesterday = now - timedelta(days=1)
        body = trip_api.CreateTrip(request_id="allpast-unit", customer_id=UUID(int=7), title="합성 일정",
                                  items=[trip_api.ItemIn(seq=1, kind="activity", title="자유시간",
                                         starts_at=yesterday, ends_at=yesterday + timedelta(hours=1))])
        with pytest.raises(HTTPException) as error:
            endpoint(body, SimpleNamespace(tenant_id="unit"))
    assert error.value.status_code == 422
    assert error.value.detail["error"]["code"] == "itinerary_infeasible"
    assert "모든 일정이 오늘 이전이에요" in error.value.detail["error"]["message"]
    # Same public endpoint: mixed dates reach other checks, not this guard.
    tomorrow = now + timedelta(days=1)
    mixed = body.model_copy(update={"items": [*body.items, trip_api.ItemIn(
        seq=2, kind="activity", title="내일 일정", starts_at=tomorrow, ends_at=tomorrow + timedelta(hours=1))]})
    with standalone_services(), pytest.raises(AssertionError, match="write boundary"):
        endpoint(mixed, SimpleNamespace(tenant_id="unit"))
    # An already registered exact request remains idempotent even after midnight.
    import hashlib
    monkeypatch.setattr(Store, "by_request_key", lambda *a: (UUID(int=9), hashlib.sha256(body.model_dump_json().encode()).hexdigest()))
    monkeypatch.setattr(trip_api, "_trip_view", lambda *a: {"trip_id": str(UUID(int=9)), "version": 1})
    with standalone_services():
        assert endpoint(body, SimpleNamespace(tenant_id="unit"))["created"] is False


def test_cached_review_guard_exempts_confirmed_and_reopened(monkeypatch):
    from contextlib import nullcontext
    from copy import deepcopy
    from app.domains.travel_ops.components.intake import review, risks
    now = datetime(2032, 5, 8, 12, tzinfo=checks.KST)
    cached = {"items": [{"date": (now - timedelta(days=1)).date().isoformat(), "end_date": None,
                         "status": "keep", "can_lock": True, "rows": []}], "moves": [],
              "ready": True, "needs": {"items": 0, "moves": 0, "total": 0},
              "risk_schema_version": risks.SCHEMA_VERSION}
    monkeypatch.setattr(review, "load", lambda *a: deepcopy(cached))
    monkeypatch.setattr(risks, "decorate", lambda *a, **kw: kw["review"])
    class Conn:
        state = ("review", None)
        def cursor(self): return nullcontext(self)
        def execute(self, *a): pass
        def fetchone(self): return self.state
    conn = Conn()
    for state, ready in [(("review", None), False), (("confirmed", None), True), (("review", "existing-trip"), True)]:
        conn.state = state
        result = review.ensure(conn, tenant_id="unit", intake_id="i", revision=1,
                               sources=[], claims=[], now=now)
        assert result["ready"] is ready
    assert cached["ready"] is True and cached["items"][0]["rows"] == []
    once = review.admission_dates(cached, now=now)
    assert review.admission_dates(once, now=now) == once
