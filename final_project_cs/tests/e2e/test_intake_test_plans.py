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
    assert len(listing.json()["scenarios"]) == plans.TOTAL == 51
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


# ★`[2026-10-20]` 「없는 코드」 예는 시험 계획 수(`TOTAL`)보다 한참 큰 번호로 — test51 이 실제로 생겨 202 로 받아졌다
@pytest.mark.parametrize("text,code", (("test99", "unknown_test_scenario"), ("test1rt", "live_test_not_ready")))
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


@pytest.mark.parametrize("code", ("test13", "test14", "test15"))
def test_normal_codes_expand_and_keep_category_in_intake(rv, code):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, code)
    assert view["status"] == "review"
    assert sum(len(source["items"]) for source in view["sources"]) == 2
    assert view["test_scenario"]["code"] == code
    assert view["test_scenario"]["category"] == "normal"
    assert view["review"]["test_scenario"] == view["test_scenario"]


def test_lodging_code_expands_to_a_named_hotel_check_in(rv):
    """test16 — 이름 있는 호텔 체크인이 든 일정이 접수에서 숙소 줄(체크인)로 읽힌다."""
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "test16")
    assert view["status"] == "review"
    assert view["test_scenario"]["code"] == "test16"
    assert view["test_scenario"]["category"] == "general"
    lines = "\n".join(line["text"] for source in view["sources"] for line in source["lines"])
    assert "더 플라자 호텔 서울" in lines
    assert sum(len(source["items"]) for source in view["sources"]) == 3


@pytest.mark.parametrize("number", range(17, 51))
def test_every_input_form_code_reads_through_to_the_review_screen(rv, number):
    """test17~50 — 입력 형식별 예시가 접수 → 읽기 → 확인 화면까지 실패 없이 간다(규칙만 — 이 시험에는 모델이 없다).
    무엇을 읽는지는 재지 않는다: 지금 구조가 못 읽는 형식을 보여 주는 예시라 읽은 항목 수는 재설계 뒤 달라진다."""
    client, _, _ = _client()
    headers = _key(client)
    code = f"test{number}"
    view = _send(client, headers, code)
    assert view["status"] == "review", view.get("error")
    assert view["test_scenario"]["code"] == code
    assert view["test_scenario"]["category"] in plans.FORM_CATEGORIES
    assert view["review"]["test_scenario"] == view["test_scenario"]
    expected = plans.prepared(number)["text"].splitlines()[0]
    assert expected in "\n".join(line["text"] for source in view["sources"] for line in source["lines"])
