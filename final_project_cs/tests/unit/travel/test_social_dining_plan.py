"""Generated first plans stay in the owned intake until explicit confirmation."""
from contextlib import contextmanager
from copy import deepcopy

import hashlib
import importlib
import json

import pytest


OWNER = {"tenant_id": "tenant", "customer_id": "customer", "intake_id": "intake"}
BODY = {
    "request_id": "generated-request", "customer_id": "customer", "title": "서울 맛집 여행",
    "locale": "ko", "party_size": 2, "constraints": {"survey": {"on_disruption": "ask_first"}},
    "places": [
        {"key": "meal", "name": "토속촌", "kind": "dining", "lat": 37.57, "lon": 126.97,
         "weather_sensitive": None,
         "attributes": {"source": "dining_ledger", "dining_place_uid": "ledger-real-id",
                        "source_content_id": "12345", "source_content_type_id": "39",
                        "address": "서울 종로구", "hours": ["10:00", "22:00"], "halal": False}},
        {"key": "activity", "name": "경복궁", "kind": "activity", "lat": 37.58, "lon": 126.98,
         "weather_sensitive": True,
         "attributes": {"source": "tour_api", "source_content_id": "24680", "source_content_type_id": "12"}},
    ],
    "items": [
        {"seq": 1, "kind": "dining", "title": "점심 토속촌", "place": "meal",
         "starts_at": "2026-10-16T03:00:00+00:00", "ends_at": "2026-10-16T04:00:00+00:00", "detail": {}},
        {"seq": 2, "kind": "mobility", "title": "이동", "place": None,
         "starts_at": "2026-10-16T13:00:00+09:00", "ends_at": "2026-10-16T13:10:00+09:00", "detail": {}},
        {"seq": 3, "kind": "activity", "title": "경복궁 관람", "place": "activity",
         "starts_at": "2026-10-16T13:30:00+09:00", "ends_at": "2026-10-16T15:00:00+09:00", "detail": {}},
    ],
}


def component():
    return importlib.import_module("app.domains.travel_ops.components.intake.social_dining_plan")


def fields(rows):
    return {row["field"]: row["value"] for row in rows}


def test_structured_rows_keep_seoul_dates_times_real_source_ids_and_attributes():
    before = deepcopy(BODY)
    rows = component().build_rows(BODY)
    got = fields(rows)
    assert got["items[0].date"] == "2026-10-16"
    assert got["items[0].starts_at"] == "12:00"
    assert got["items[0].ends_at"] == "13:00"
    assert got["items[0].end_date"] == "2026-10-16"
    assert got["items[1].kind"] == "activity"
    assert "items[2].kind" not in got
    place = got["items[0].place"]
    assert place["source"] == "dining_ledger"
    assert place["dining_place_uid"] == "ledger-real-id"
    assert place["content_id"] == "12345"
    assert place["content_type_id"] == "39"
    assert place["attributes"]["halal"] is False
    assert place["_hours"]["hours"] == ["10:00", "22:00"]
    assert "place_id" not in place
    assert BODY == before


def test_generated_claims_cite_structured_paths_and_a_body_digest():
    rows = component().build_rows(BODY)
    expected_hash = hashlib.sha256(json.dumps(BODY, ensure_ascii=False, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()
    title = next(row for row in rows if row["field"] == "items[1].title")
    assert title["method"] == "rule"
    assert title["evidence"]["source"] == "planner_generated"
    assert title["evidence"]["body_hash"] == expected_hash
    assert title["evidence"]["path"] == "/items/2/title"
    assert title["evidence"]["line"] == 2


def test_unsupported_cross_day_item_is_rejected_without_losing_its_end_date():
    body = deepcopy(BODY)
    body["items"][0]["ends_at"] = "2026-10-17T01:00:00+09:00"
    api = component()
    with pytest.raises(api.pipeline.IntakeRejected) as caught:
        api.build_rows(body)
    assert caught.value.code == "generated_cross_day_unsupported"


def test_missing_real_place_reference_is_never_replaced_by_an_invented_id():
    body = deepcopy(BODY)
    body["items"][0]["place"] = "unknown-place"
    api = component()
    with pytest.raises(api.pipeline.IntakeRejected) as caught:
        api.build_rows(body)
    assert caught.value.code == "generated_place_missing"


class MemoryConnection:
    def __init__(self):
        self.state = {"status": "review", "revision": 3, "reopen_trip_id": None, "trip_id": None,
                      "sources": [{"source_id": "original", "position": 0, "kind": "text", "transcript": "일정 짜 줘"}],
                      "claims": [{"source_id": "original", "field": "trip.title", "value": "우리 여행",
                                  "method": "customer", "evidence": {"source": "customer"},
                                  "needs_review": False, "note": None}],
                      "wishlist": [{"key": "wish-a", "priority": "must"}],
                      "survey": {"on_disruption": "ask_first"}, "review": None}

    @contextmanager
    def transaction(self):
        before = deepcopy(self.state)
        try:
            yield
        except BaseException:
            self.state = before
            raise

    @contextmanager
    def cursor(self):
        yield MemoryCursor(self)


class MemoryCursor:
    def __init__(self, connection):
        self.conn = connection
        self.result = None
        self.rowcount = 0

    def execute(self, sql, params=()):
        state = self.conn.state
        sql = " ".join(sql.split())
        if sql.startswith("SELECT status, revision, reopen_trip_id, trip_id FROM trip_intakes"):
            tenant, intake, customer = params
            owned = (tenant, customer, intake) == ("tenant", "customer", "intake")
            self.result = (state["status"], state["revision"], state["reopen_trip_id"], state["trip_id"]) if owned else None
            assert "FOR UPDATE" in sql
        elif sql.startswith("INSERT INTO intake_sources"):
            intake, tenant, position, digest, size, transcript = params
            state["sources"].append({"source_id": "generated", "position": position, "kind": "chat",
                                     "sha256": digest, "size_bytes": size, "transcript": transcript})
            self.result = ("generated",)
        elif sql.startswith("INSERT INTO intake_claims") and " SELECT " in sql:
            # The complete previous revision survives; only new structured rows are appended.
            assert params == (4, "tenant", "intake", 3)
        elif sql.startswith("INSERT INTO intake_claims"):
            intake, tenant, revision, source_id, name, value, method, evidence = params
            state["claims"].append({"source_id": source_id, "field": name, "value": json.loads(value),
                                    "method": method, "evidence": json.loads(evidence),
                                    "needs_review": False, "note": None})
        elif sql.startswith("UPDATE trip_intakes SET revision="):
            revision, tenant, intake, customer, previous = params
            assert (tenant, customer, intake, previous) == ("tenant", "customer", "intake", state["revision"])
            state["revision"] = revision
            self.rowcount = 1
        else:
            pytest.fail(f"Unexpected persistence operation: {sql}")

    def fetchone(self):
        return self.result


def setup(monkeypatch, *, fail_review=False):
    api = component()
    conn = MemoryConnection()
    monkeypatch.setattr(api.pipeline, "_sources", lambda conn, *args: deepcopy(conn.state["sources"]))
    monkeypatch.setattr(api.pipeline, "_claims", lambda conn, *args: deepcopy(conn.state["claims"]))

    def review(conn, tenant, intake, revision, sources, claims, **kwargs):
        if fail_review:
            return None, "test_review_failure"
        from app.domains.travel_ops.components.intake.assemble import collect
        rows = collect(sources=sources, claims=claims).rows
        conn.state["review"] = {"items": [{"title": row["title"], "kind": row["kind"], "date": row["date"],
                                           "starts_at": row["start"]} for row in rows], "revision": revision}
        return conn.state["review"], None

    monkeypatch.setattr(api.pipeline, "_review_of", review)
    monkeypatch.setattr(api.pipeline, "view", lambda conn, **kwargs: {
        "intake_id": "intake", "revision": conn.state["revision"], "trip_id": conn.state["trip_id"],
        "review": deepcopy(conn.state["review"]), "status": conn.state["status"]})
    return api, conn


def test_generated_plan_stays_in_the_existing_intake_and_preserves_wishes_and_survey(monkeypatch):
    api, conn = setup(monkeypatch)
    result = api.stage_generated(conn, **OWNER, revision=3, body=BODY)
    assert result["intake_id"] == "intake"
    assert result["revision"] == 4 and result["trip_id"] is None
    assert [item["title"] for item in result["review"]["items"]] == ["점심 토속촌", "경복궁 관람"]
    assert conn.state["wishlist"] == [{"key": "wish-a", "priority": "must"}]
    assert conn.state["survey"] == {"on_disruption": "ask_first"}
    assert fields(conn.state["claims"])["trip.title"] == "우리 여행"
    assert conn.state["sources"][-1]["kind"] == "chat"
    assert conn.state["sources"][-1]["position"] == 1


@pytest.mark.parametrize("wrong", [{"tenant_id": "other"}, {"customer_id": "other"}, {"intake_id": "other"}])
def test_other_customers_or_tenants_cannot_stage_a_plan(monkeypatch, wrong):
    api, conn = setup(monkeypatch)
    before = deepcopy(conn.state)
    with pytest.raises(LookupError):
        api.stage_generated(conn, **{**OWNER, **wrong}, revision=3, body=BODY)
    assert conn.state == before


def test_stale_revision_cannot_append_generated_sources(monkeypatch):
    api, conn = setup(monkeypatch)
    before = deepcopy(conn.state)
    with pytest.raises(api.pipeline.IntakeConflict) as caught:
        api.stage_generated(conn, **OWNER, revision=2, body=BODY)
    assert caught.value.code == "stale_revision"
    assert conn.state == before


@pytest.mark.parametrize("change", [{"status": "confirmed"}, {"reopen_trip_id": "trip"}, {"trip_id": "trip"}])
def test_noninitial_or_noneditable_intakes_are_not_overwritten(monkeypatch, change):
    api, conn = setup(monkeypatch)
    conn.state.update(change)
    before = deepcopy(conn.state)
    with pytest.raises(api.pipeline.IntakeConflict):
        api.stage_generated(conn, **OWNER, revision=3, body=BODY)
    assert conn.state == before


def test_existing_even_incomplete_read_items_are_not_replaced(monkeypatch):
    api, conn = setup(monkeypatch)
    conn.state["claims"].append({"source_id": "original", "field": "items[0].title", "value": "내가 정한 식당",
                                 "method": "rule", "evidence": {}, "needs_review": True, "note": None})
    before = deepcopy(conn.state)
    with pytest.raises(api.pipeline.IntakeConflict) as caught:
        api.stage_generated(conn, **OWNER, revision=3, body=BODY)
    assert caught.value.code == "intake_has_items"
    assert conn.state == before


def test_failed_full_review_rolls_back_generated_source_claims_and_revision(monkeypatch):
    api, conn = setup(monkeypatch, fail_review=True)
    before = deepcopy(conn.state)
    with pytest.raises(api.pipeline.IntakeConflict) as caught:
        api.stage_generated(conn, **OWNER, revision=3, body=BODY)
    assert caught.value.code == "schedule_check_failed"
    assert conn.state == before
