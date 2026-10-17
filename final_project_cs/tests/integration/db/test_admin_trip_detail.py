"""격리 PostgreSQL 엔진으로 여행 소유·대화 페이지·계획 판을 검증한다."""
import os
import json
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domains.travel_ops.entry import admin_trip_api as api
from app.presentation import admin_api
from app.presentation.ui import auth
from tests.integration.db.test_unattended_operations import PG


@pytest.fixture(scope="module")
def pg():
    if not os.environ.get("OPS_PGLITE_MODULE"):
        pytest.skip("OPS_PGLITE_MODULE 필요: 실제 고객 DB에는 연결하지 않는다")
    process = subprocess.Popen(["node", str(Path(__file__).with_name("operations_pglite.mjs"))],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf8")
    assert process.stdout.readline().strip() == "ready"
    database = PG(process)
    root = Path(__file__).resolve().parents[3]
    database.request({"script": True, "sql": "CREATE TABLE customers(customer_id uuid PRIMARY KEY);"
                      "CREATE TABLE places(place_id uuid PRIMARY KEY,tenant_id text,name text);"
                      "CREATE TABLE bookings(booking_id uuid PRIMARY KEY);"})
    database.request({"script": True, "sql": (root / "app/infrastructure/db/migrations/014_itinerary.sql").read_text(encoding="utf8")})
    migration = (root / "app/infrastructure/db/migrations/034_trip_chat_turns.sql").read_text(encoding="utf8")
    database.request({"script": True, "sql": migration.split("DO $$")[0]})
    yield database
    process.stdin.close()
    process.wait(timeout=15)


@pytest.fixture
def case(pg, monkeypatch):
    tenant, customer, other, trip = "admin_" + uuid4().hex, uuid4(), uuid4(), uuid4()
    pg.execute("INSERT INTO customers VALUES(%s),(%s)", (customer, other))
    pg.execute("INSERT INTO trips(trip_id,tenant_id,customer_id,title,latest_version,party_size) VALUES(%s,%s,%s,%s,2,4)",
               (trip, tenant, customer, "서울 여행"))
    for version, title in ((1, "경복궁"), (2, "국립중앙박물관")):
        pg.execute("INSERT INTO itinerary_versions(trip_id,version,tenant_id,reason) VALUES(%s,%s,%s,%s)",
                   (trip, version, tenant, "created" if version == 1 else "customer_request"))
        pg.execute("INSERT INTO itinerary_items(item_id,trip_id,version,tenant_id,seq,kind,title,starts_at) "
                   "VALUES(%s,%s,%s,%s,1,'activity',%s,%s)",
                   (uuid4(), trip, version, tenant, title, datetime(2026, 10, 20, 1, tzinfo=UTC)))
    @contextmanager
    def connection():
        yield pg
    monkeypatch.setattr(api, "get_connection", connection)
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(tenant_id=tenant))
    monkeypatch.setattr(auth, "operators", lambda: {"qa": ("unused", frozenset({"ops:introspect"})), "limited": ("unused", frozenset())})
    app = FastAPI()
    app.include_router(api.build_router(operator_dependency=admin_api.operator, require_permission=admin_api.require))
    client = TestClient(app)
    client.cookies.set(auth.COOKIE, auth.issue(auth.Operator("qa", frozenset({"ops:introspect"}))))
    return SimpleNamespace(pg=pg, tenant=tenant, customer=customer, other=other, trip=trip, client=client,
                           path=f"/admin/api/users/{customer}/trips/{trip}")


def test_summary_and_two_plan_versions_use_stored_data(case):
    response = case.client.get(case.path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["trip"]["title"] == "서울 여행"
    assert response.json()["trip"]["latest_version"] == 2
    initial = case.client.get(case.path + "/plans/initial").json()["plan"]
    current = case.client.get(case.path + "/plans/current").json()["plan"]
    assert (initial["version"], initial["items"][0]["title"]) == (1, "경복궁")
    assert (current["version"], current["items"][0]["title"]) == (2, "국립중앙박물관")
    assert current["items"][0]["starts_at"] == "2026-10-20T01:00:00+00:00"
    assert case.pg.execute("SELECT latest_version FROM trips WHERE trip_id=%s", (case.trip,)).fetchone()[0] == 2


def test_chat_cursor_preserves_long_text_and_excludes_other_trips(case):
    expected = []
    for index in range(5):
        text = f"대화 {index}: " + "긴 내용 " * 300
        expected.append(text)
        case.pg.execute("INSERT INTO trip_chat_turns(tenant_id,trip_id,role,text) VALUES(%s,%s,%s,%s)",
                        (case.tenant, case.trip, "customer" if index % 2 == 0 else "assistant", text))
    case.pg.execute("INSERT INTO trip_chat_turns(tenant_id,trip_id,role,text) VALUES(%s,%s,'customer','다른 여행 비공개')",
                    (case.tenant, uuid4()))
    seen, cursor = [], "0"
    while cursor is not None:
        response = case.client.get(case.path + f"/chat?after={cursor}&limit=2")
        assert response.status_code == 200
        page = response.json()
        seen.extend(page["turns"])
        cursor = page["next_after"]
    assert [turn["text"] for turn in seen] == expected
    assert len({turn["turn_id"] for turn in seen}) == 5
    assert [turn["role"] for turn in seen] == ["customer", "assistant", "customer", "assistant", "customer"]


@pytest.mark.parametrize("suffix", ["", "/chat", "/plans/initial", "/plans/current"])
def test_customer_and_tenant_isolation(case, monkeypatch, suffix):
    wrong_owner = case.path.replace(str(case.customer), str(case.other))
    assert case.client.get(wrong_owner + suffix).status_code == 404
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(tenant_id="different-tenant"))
    assert case.client.get(case.path + suffix).status_code == 404


@pytest.mark.parametrize("suffix", ["", "/chat", "/plans/initial", "/plans/current"])
def test_customer_credentials_and_missing_scope_cannot_read(case, suffix):
    case.client.cookies.clear()
    assert case.client.get(case.path + suffix, headers={"X-User-Key": "customer-key"}).status_code == 401
    case.client.cookies.set(auth.COOKIE, auth.issue(auth.Operator("limited", frozenset())))
    assert case.client.get(case.path + suffix).status_code == 403


def test_missing_initial_plan_is_not_replaced_with_later_version(case):
    trip = uuid4()
    case.pg.execute("INSERT INTO trips(trip_id,tenant_id,customer_id,title,latest_version) VALUES(%s,%s,%s,'이전 여행',2)",
                    (trip, case.tenant, case.customer))
    case.pg.execute("INSERT INTO itinerary_versions(trip_id,version,tenant_id,reason) VALUES(%s,2,%s,'customer_request')", (trip, case.tenant))
    path = case.path.replace(str(case.trip), str(trip))
    assert case.client.get(path + "/plans/initial").json()["plan"] is None
    assert case.client.get(path + "/plans/current").json()["plan"]["version"] == 2
    assert case.client.get(path + "/chat").json() == {"turns": [], "next_after": None}


@pytest.mark.parametrize("query", ["after=-1", "after=abc", "after=9223372036854775808", "limit=0", "limit=201"])
def test_invalid_chat_cursor_and_limit(case, query):
    assert case.client.get(case.path + "/chat?" + query).status_code == 422


def test_text_is_redacted_and_html_remains_plain_text(case):
    case.pg.execute("INSERT INTO trip_chat_turns(tenant_id,trip_id,role,text) VALUES(%s,%s,'assistant',%s)",
                    (case.tenant, case.trip, "연락 010-1234-5678 <script>alert(1)</script>"))
    text = case.client.get(case.path + "/chat").json()["turns"][0]["text"]
    assert "010-****-5678" in text
    assert "<script>alert(1)</script>" in text


@pytest.mark.parametrize("chosen", [None, "walk"])
def test_plan_keeps_selected_transport_and_filters_internal_details(case, chosen):
    detail = {"option": chosen, "route_def": {"planned": "metro", "options": [
        {"id": "metro", "label": "지하철 2호선", "eta_min": 18},
        {"id": "walk", "label": "도보", "eta_min": 35}]}, "internal_token": "private"}
    case.pg.execute("UPDATE itinerary_items SET detail=%s::jsonb WHERE trip_id=%s AND version=2", (json.dumps(detail), case.trip))
    item = case.client.get(case.path + "/plans/current").json()["plan"]["items"][0]
    assert item["detail"] == {"mode": "도보" if chosen else "지하철 2호선", "travel_minutes": 35 if chosen else 18}
