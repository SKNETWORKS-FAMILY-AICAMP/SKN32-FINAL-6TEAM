"""로컬 DB·실제 접수 API를 사용한다. 장소 조회는 mock 서버 역할의 시험 제공자다."""
import pytest

from app.domains.travel_ops.components.intake import test_plans as plans
from app.infrastructure.db.session import get_connection
from .test_intake_review import _client, _key, _send, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401


def test_code_expands_before_reading_and_remains_scoped_through_recheck(rv):
    client, _, _ = _client()
    headers = _key(client)
    listing = client.get("/v1/web/test-scenarios")
    assert listing.status_code == 200
    assert len(listing.json()["scenarios"]) == 12
    view = _send(client, headers, " TEST1 ")
    assert view["status"] == "review"
    assert sum(len(s["items"]) for s in view["sources"]) == 6
    assert view["test_scenario"]["code"] == "test1"
    assert view["review"]["test_scenario"] == view["test_scenario"]
    assert "경복궁" in "\n".join(line["text"] for source in view["sources"] for line in source["lines"])
    own_url = f"/v1/web/trip-intakes/{view['intake_id']}"
    assert client.get(own_url, headers=_key(client)).status_code == 404
    response = client.post(own_url + "/edits", headers=headers, json={"revision": view["revision"], "edits": [{
        "source_id": view["sources"][0]["source_id"], "field": "items[0].title", "value": "경복궁 관람 수정"}]})
    assert response.status_code == 200, response.text
    assert response.json()["test_scenario"]["code"] == "test1"
    stream = client.get(own_url + "/events", headers=headers)
    assert stream.status_code == 200
    assert "event: result" in stream.text
    ordinary = _send(client, headers, "10/18 09:00 경복궁 관람 · test1을 기억해요")
    assert ordinary["test_scenario"] is None


@pytest.mark.parametrize("text,code", (("test13", "unknown_test_scenario"), ("test1rt", "live_test_not_ready")))
def test_rejected_code_does_not_create_empty_intake(rv, text, code):
    client, _, _ = _client()
    headers = _key(client)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM trip_intakes WHERE tenant_id=%s", (rv["tenant"],))
        before = cur.fetchone()[0]
    response = client.post("/v1/web/trip-intakes", headers=headers, data={"text": text})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM trip_intakes WHERE tenant_id=%s", (rv["tenant"],))
        assert cur.fetchone()[0] == before


def test_disabled_codes_and_file_mix_are_refused(rv, monkeypatch):
    client, _, _ = _client()
    headers = _key(client)
    mixed = client.post("/v1/web/trip-intakes", headers=headers, data={"text": "test1"}, files={"files": ("memo.txt", b"plan")})
    assert mixed.status_code == 422
    assert mixed.json()["error"]["code"] == "test_scenario_with_files"
    monkeypatch.setattr(plans, "operator_setting", lambda *_: False)
    assert client.get("/v1/web/test-scenarios").json()["scenarios"] == []
    disabled = client.post("/v1/web/trip-intakes", headers=headers, data={"text": "test1"})
    assert disabled.status_code == 422
    assert disabled.json()["error"]["code"] == "test_scenarios_disabled"
