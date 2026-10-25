"""모형 저장소를 사용한 답변 API와 소유권·현재 작업 경계 시험."""
from contextlib import nullcontext
from copy import deepcopy
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domains.travel_ops.components.intake import dining_review, pipeline
from app.domains.travel_ops.components.intake import review as review_module
from app.domains.travel_ops.components.team_hooks import dining_ledger
from app.domains.travel_ops.entry import trip_api
from tests.unit.travel.test_dining_clarifications import QUOTE, questioned


INTAKE = UUID("11111111-1111-1111-1111-111111111111")
CUSTOMER = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def api(monkeypatch):
    saved = {"payload": questioned(), "owner": True, "status": "review", "revision": 2, "queued": [], "stores": 0}
    class Conn:
        locked = False
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def transaction(self):
            return nullcontext(self)
        def cursor(self):
            return self
        def execute(self, sql, params):
            assert "customer_id=%s FOR UPDATE" in sql and params == ("tenant", INTAKE, CUSTOMER)
            self.locked = True
        def fetchone(self):
            return (saved["status"], saved["revision"]) if saved["owner"] else None
    conn = Conn()
    saved["conn"] = conn
    def load(*args):
        assert conn.locked
        return deepcopy(saved["payload"])
    def store(*args):
        assert conn.locked
        saved["payload"] = deepcopy(args[-1])
        saved["stores"] += 1
    def lock(*args):
        assert conn.locked
        return saved["status"], saved["revision"]
    monkeypatch.setattr(review_module, "load", load)
    monkeypatch.setattr(review_module, "store", store)
    monkeypatch.setattr(review_module, "intake_state", lock)
    monkeypatch.setattr(pipeline, "_sources", lambda *a: [{"transcript": QUOTE}])
    monkeypatch.setattr(pipeline, "view", lambda *a, **kw: {"intake_id": str(INTAKE), "status": "review", "revision": 2,
                                                         "review": deepcopy(saved["payload"])})
    monkeypatch.setattr(pipeline, "rejudge", lambda *a: saved["queued"].append(a))
    monkeypatch.setattr(trip_api, "get_connection", lambda: conn)
    monkeypatch.setattr(dining_ledger, "agent_judge_runner", lambda: object())
    router = trip_api.build_trip_router()
    endpoint = next(r for r in router.routes if r.path.endswith("/dining-answers"))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[endpoint.dependant.dependencies[0].call] = lambda: ("tenant", CUSTOMER)
    return TestClient(app), saved


def body(saved):
    return {"revision": 2, "run_id": "run-1", "question_id": saved["payload"]["dining_questions"][0]["id"],
            "item_ids": ["dinner"], "excluded": False}


def test_answer_api_saves_the_quote_and_scope_then_queues_the_current_revision(api):
    client, saved = api
    response = client.post(f"/v1/web/trip-intakes/{INTAKE}/dining-answers", json=body(saved))
    assert response.status_code == 200, response.text
    payload = response.json()["review"]
    q = payload["dining_questions"][0]
    assert q["quote"] == QUOTE and q["answer"]["item_ids"] == ["dinner"]
    assert payload["dining_judge"]["status"] == "pending" and payload["dining_judge"]["run_id"] != "run-1"
    assert payload["dining_judge"]["input_fingerprint"] == dining_review.fingerprint(payload, QUOTE)
    assert len(saved["queued"]) == 1 and saved["queued"][0][1:] == ("tenant", INTAKE, 2)
    again = client.post(f"/v1/web/trip-intakes/{INTAKE}/dining-answers", json=body(saved))
    assert again.status_code == 409 and len(saved["queued"]) == 1


@pytest.mark.parametrize("change,status", [({"owner": False}, 404), ({"status": "confirmed"}, 409), ({"revision": 3}, 409)])
def test_foreign_closed_or_old_intakes_never_store_answers(api, change, status):
    client, saved = api
    saved.update(change)
    response = client.post(f"/v1/web/trip-intakes/{INTAKE}/dining-answers", json=body(saved))
    assert response.status_code == status and saved["stores"] == 0 and saved["queued"] == []


@pytest.mark.parametrize("patch", [{"item_ids": ["museum"]}, {"question_id": "foreign-question"}, {"quote": "forged"}])
def test_invalid_scope_or_client_owned_source_fields_are_rejected(api, patch):
    client, saved = api
    response = client.post(f"/v1/web/trip-intakes/{INTAKE}/dining-answers", json={**body(saved), **patch})
    assert response.status_code == 422 and saved["stores"] == 0 and saved["queued"] == []


def test_unavailable_judge_does_not_silently_save_an_unchecked_answer(api, monkeypatch):
    client, saved = api
    monkeypatch.setattr(dining_ledger, "agent_judge_runner", lambda: None)
    response = client.post(f"/v1/web/trip-intakes/{INTAKE}/dining-answers", json=body(saved))
    assert response.status_code == 503 and saved["stores"] == 0


def test_answered_scope_reaches_the_actual_agent_and_finishes_without_a_scope_gap(api, monkeypatch):
    import json
    from app.domains.travel_ops.instances.dining import judge
    from app.domains.travel_ops.instances.dining.agent_tools import DiningTools
    from app.infrastructure.llm.tool_chat import ToolTurn
    from tests.unit.travel.test_dining_agent import UID

    client, saved = api
    response = client.post(f"/v1/web/trip-intakes/{INTAKE}/dining-answers", json=body(saved))
    assert response.status_code == 200
    pending = response.json()["review"]
    # 모형 SQL 연결은 판정 감사 기록도 받아 실제 run의 저장 경계를 실행한다.
    conn = saved["conn"]
    conn.execute = lambda sql, params=(): None
    class Tools(DiningTools):
        def _find_place(self, name, lat=None, lng=None):
            return {"found": True, "verdict": "ok", "place_uid": UID, "name": name}
        def _check_open_at(self, **kw):
            return {"verdict": "ok"}
        def _check_attributes(self, **kw):
            return {"attributes": {"halal": {"state": "yes"}}}
    calls = []
    items = []
    for n, (item_id, hour) in enumerate([("lunch", "12:00"), ("dinner", "18:00")]):
        base = n * 2 + 1
        calls += [{"id": f"t{base}", "name": "find_place", "arguments": {"name": item_id}},
                  {"id": f"t{base+1}", "name": "check_open_at", "arguments": {"place_uid": UID, "start": f"2026-10-25T{hour}"}}]
        items.append({"item_id": item_id, "place": {"place_uid": UID, "call_id": f"c{base}"}, "checks": [
            {"check": "found", "verdict": "ok", "evidence": [{"call_id": f"c{base}", "path": "verdict", "value": "ok"}]},
            {"check": "open_at", "verdict": "ok", "evidence": [{"call_id": f"c{base+1}", "path": "verdict", "value": "ok"}]}]})
    calls.append({"id": "t5", "name": "check_attributes", "arguments": {"place_uid": UID, "wanted": ["halal"]}})
    items[1]["checks"].append({"check": "dietary", "required": True, "request_id": "r1", "verdict": "ok",
                                "evidence": [{"call_id": "c5", "path": "attributes.halal.state", "value": "yes"}]})
    final = {"items": items, "requests": [{"request_id": "r1", "quote": QUOTE, "attribute": "halal",
                                           "required": True, "state": "unclear", "item_ids": []}]}
    class Chat:
        turns = 0
        def step(self, messages, tools, **kw):
            self.turns += 1
            assert "customer_clarifications" in messages[1]["content"]
            return ToolTurn(content=None, tool_calls=calls) if self.turns == 1 else ToolTurn(content=json.dumps(final, ensure_ascii=False))
    got = judge.run(lambda: conn, tenant_id="tenant", intake_id=INTAKE, revision=2, review=pending,
                    notes=QUOTE, chat=Chat(), model="fake", tools_factory=lambda c: Tools(c))
    assert got["missing"] == 0 and saved["payload"]["dining_judge"]["status"] == "completed"
    dinner = next(i for i in saved["payload"]["items"] if i["id"] == "dinner")
    dietary = next(r for r in dinner["rows"] if r["row"] == "dietary")
    assert dietary["result"] == "ok" and dietary["agent"]["customer_request"]["item_ids"] == ["dinner"]
