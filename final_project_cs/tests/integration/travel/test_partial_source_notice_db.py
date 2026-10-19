"""실제 격리 Postgres에서 사실 안내·중복 방지·일정 불변을 검증한다."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

from app.composition import wire_trip_scope
from app.infrastructure.db.session import database_dsn, get_connection
from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.components.watch.trip_watch_cases import TripWatchCaseOpener
from app.infrastructure.notify.discord import render
from tests.unit.travel.test_partial_source_notice import NOW, make_report

pytestmark = pytest.mark.skipif(not os.environ.get("PARTIAL_NOTICE_SYNTHETIC_DATABASE_URL"),
                               reason="requires explicit isolated synthetic database")


@pytest.fixture(autouse=True)
def isolated_db_guard():
    expected = os.environ.get("PARTIAL_NOTICE_SYNTHETIC_DATABASE_URL")
    assert expected and database_dsn() == expected
    parsed = urlsplit(expected)
    assert (parsed.hostname, parsed.port, parsed.path, parsed.username) == (
        "127.0.0.1", 15544, "/semantic_synthetic", "semantic_test")
    with get_connection() as conn:
        assert conn.execute("SELECT current_database(),current_user").fetchone() == ("semantic_synthetic", "semantic_test")
        assert conn.execute("SELECT owner FROM semantic_test_isolation_guard").fetchone() == ("semantic-contract-repair",)
    wire_trip_scope()


def make_trip(*, protection=None, guest=False, kind="activity"):
    from datetime import timedelta

    tenant = "partial_notice_" + uuid4().hex[:12]
    customer = uuid4()
    store = TripStore(tenant)
    with get_connection() as conn, conn.transaction():
        conn.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,%s)", (tenant, "synthetic notice verification"))
        conn.execute("INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,%s)",
                     (customer, tenant, "web:synthetic-guest" if guest else "synthetic-notice-agent"))
        place = conn.execute("INSERT INTO places(tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes) "
                             "VALUES(%s,%s,%s,37.57,127.1,true,%s) RETURNING place_id",
                             (tenant, "합성 여행지", kind, json.dumps({"hours": ["08:00", "22:00"]}))).fetchone()[0]
        stop = Item(item_id=uuid4(), seq=1, kind=kind, title="합성 여행지", place_id=place,
                    starts_at=NOW-timedelta(hours=1), ends_at=NOW+timedelta(hours=1),
                    locked=protection == "locked", detail={"customer_pinned": protection == "pinned"})
        trip_id, _ = store.create_trip(conn, customer_id=customer, title="synthetic notice only", locale="ko", party_size=2,
                                      items=[stop], constraints={"survey": {"on_disruption": "replace"},
                                                                "survey_answered": ["on_disruption"]})
    report = make_report()
    calls = []
    opener = TripWatchCaseOpener(store=store, check=lambda **kw: deepcopy(report), connection_factory=get_connection,
                                clock=lambda: NOW, repository=None, run_case=lambda **kw: calls.append(kw))
    return SimpleNamespace(tenant=tenant, store=store, trip_id=trip_id, report=report, opener=opener, calls=calls)


def snapshot(case):
    with get_connection() as conn:
        trip = conn.execute("SELECT latest_version,constraints FROM trips WHERE tenant_id=%s AND trip_id=%s",
                            (case.tenant, case.trip_id)).fetchall()
        items = conn.execute("SELECT version,item_id,seq,kind,title,place_id,starts_at,ends_at,locked,booking_id,detail "
                             "FROM itinerary_items WHERE tenant_id=%s AND trip_id=%s ORDER BY version,seq",
                             (case.tenant, case.trip_id)).fetchall()
        versions = conn.execute("SELECT version,reason,cause_json FROM itinerary_versions WHERE tenant_id=%s AND trip_id=%s ORDER BY version",
                                (case.tenant, case.trip_id)).fetchall()
        cases = conn.execute("SELECT case_id FROM customer_cases WHERE tenant_id=%s", (case.tenant,)).fetchall()
    return trip, items, versions, cases


def notices(case):
    with get_connection() as conn:
        return conn.execute("SELECT dedupe_key,payload_json FROM outbox WHERE tenant_id=%s AND dedupe_key LIKE %s ORDER BY dedupe_key",
                            (case.tenant, str(case.trip_id) + ":watch-deferred:%")).fetchall()


@pytest.mark.parametrize("protection", [None, "pinned", "locked"])
def test_real_watch_saves_facts_once_with_zero_trip_or_case_changes(protection):
    case = make_trip(protection=protection)
    before = snapshot(case)
    first = case.opener.tick()
    assert len(first.notified) == 1 and first.opened == [] and not case.calls
    assert snapshot(case) == before
    [(key, payload)] = notices(case)
    assert "문화 행사로 전면 통제" in render(payload) and "자동 변경을 보류" in render(payload)
    assert payload["changed"] is None and payload["causes"][0]["incident_id"] == "synthetic-road-1"
    case.report["disruptions"][0].update(distance_m=999, confirmed_at="2030-01-01T11:33:00+09:00")
    assert case.opener.tick().notified == [] and len(notices(case)) == 1
    case.report["disruptions"][0]["incident_id"] = "synthetic-road-2"
    assert len(case.opener.tick().notified) == 1 and len(notices(case)) == 2
    assert snapshot(case) == before


def test_concurrent_polls_use_real_outbox_unique_without_mutating_itinerary():
    from app.core.service_bindings import standalone_services

    case = make_trip()
    before = snapshot(case)
    def tick(_):
        # 실제 합성 부품 조립의 ContextVar는 새 스레드로 자동 전파되지 않는다.
        with standalone_services():
            return case.opener.tick()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(tick, range(2)))
    assert sum(len(r.notified) for r in results) == 1 and len(notices(case)) == 1
    assert snapshot(case) == before and not case.calls


def test_real_guest_filter_still_prevents_automatic_watch_or_notice():
    case = make_trip(guest=True)
    before = snapshot(case)
    result = case.opener.tick()
    assert result.checked == 0 and not result.notified and not notices(case)
    assert snapshot(case) == before and not case.calls


def test_dining_lookup_exception_preserves_confirmed_report_in_real_saved_notice():
    case = make_trip(kind="dining")
    before = snapshot(case)
    def lookup(**kwargs):
        raise RuntimeError("PRIVATE_SYNTHETIC_ENRICHMENT_ERROR")
    case.opener.place_status = SimpleNamespace(lookup=lookup)
    result = case.opener.tick()
    [fatal] = result.fatal
    assert fatal["report"]["disruptions"] == case.report["disruptions"]
    assert set(fatal["report"]["failed_categories"]) == {"forecast", "place_check"}
    [(_, payload)] = notices(case)
    assert "문화 행사로 전면 통제" in render(payload) and "PRIVATE_SYNTHETIC_ENRICHMENT_ERROR" not in repr(payload)
    assert snapshot(case) == before and not case.calls
