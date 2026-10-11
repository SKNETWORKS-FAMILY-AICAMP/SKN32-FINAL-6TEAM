"""HTTP+로컬 개발 DB: 장소 교체 재배치·신규 추가·실패 원판 보존·격리.

관광정보·이동 계산은 mock 응답이다. 실제 공공 API 확인과 구분한다.
"""
from datetime import timedelta
import json

import pytest

from app.domains.travel_ops.components.intake import review
from app.infrastructure.db.session import get_connection

from .test_trip_api import api  # noqa: F401
from .test_intake_review import rv, _client, _key, _send, _field  # noqa: F401


PLAN = "2026-10-15\n09:00 경복궁 관람 1시간\n10:05 광장시장 관람 1시간\n13:00 N서울타워 관람 1시간"
HOTEL = {"name": "시험 호텔", "latitude": 37.57, "longitude": 126.98, "source": "map"}


def walk11(a, b, arrive, not_before=None):
    return {"starts_at": arrive - timedelta(minutes=11), "ends_at": arrive, "eta_min": 11,
            "route": {"planned": "walk", "options": [{"id": "walk", "eta_min": 11, "label": "도보 11분", "walk_m": 880}]}}, None


def request(client, headers, view, edits):
    return client.post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=headers,
                       json={"revision": view["revision"], "edits": edits})


def fetch(client, headers, view):
    return client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json()


@pytest.fixture()
def direct(rv, monkeypatch):
    monkeypatch.setattr(review, "default_engine", lambda party=None, modes=None: walk11)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    return client, headers, view


def test_hotel_change_immediately_updates_next_time_in_same_revision(direct):
    client, headers, before = direct
    a, b, c = before["review"]["items"]
    response = request(client, headers, before, [_field(a, "place", HOTEL)])
    assert response.status_code == 200, response.text
    after = response.json()
    assert after["revision"] == before["revision"] + 1
    assert after["review"]["revision"] == after["revision"]
    assert after["review"]["items"][0]["place"]["name"] == "시험 호텔"
    assert after["review"]["items"][1]["starts_at"] == "10:15"
    assert after["review"]["items"][1]["ends_at"] == "11:15"
    assert after["review"]["items"][2]["starts_at"] == c["starts_at"]
    assert all(m["status"] != "review" for m in after["review"]["moves"])
    assert fetch(client, headers, before)["review"] == after["review"]


def new_fields(view, **overrides):
    source = view["sources"][0]
    index = max((i["index"] for i in source["items"]), default=-1) + 1
    values = {"title": "새 일정", "date": "2026-10-15", "starts_at": "11:30", "ends_at": "12:30",
              "kind": "activity", "place": HOTEL, **overrides}
    return [{"source_id": source["source_id"], "field": f"items[{index}].{name}", "value": value}
            for name, value in values.items()]


def test_add_during_validation_uses_edits_and_get_returns_it(direct):
    client, headers, before = direct
    response = request(client, headers, before, new_fields(before))
    assert response.status_code == 200, response.text
    after = response.json()
    assert len(after["review"]["items"]) == len(before["review"]["items"]) + 1
    added = next(i for i in after["review"]["items"] if i["title"] == "새 일정")
    assert added["starts_at"] == "11:30" and added["place"]["name"] == "시험 호텔"
    assert fetch(client, headers, before)["revision"] == after["revision"]


@pytest.mark.parametrize("values,code", [({"starts_at": "12:30", "ends_at": "11:30"}, "invalid_value"),
                                         ({"date": "2026-10-22"}, "trip_too_long")])
def test_bad_added_item_preserves_previous_revision(direct, values, code):
    client, headers, before = direct
    response = request(client, headers, before, new_fields(before, **values))
    assert response.status_code == 422 and response.json()["error"]["code"] == code, response.text
    assert fetch(client, headers, before)["revision"] == before["revision"]


def test_incomplete_new_item_is_rejected(direct):
    client, headers, before = direct
    response = request(client, headers, before, new_fields(before)[:-1])
    assert response.status_code == 422 and response.json()["error"]["code"] == "unknown_item"


def test_other_customer_cannot_add_or_edit(direct):
    client, headers, before = direct
    other = _key(client)
    response = request(client, other, before, new_fields(before))
    assert response.status_code == 404
    assert fetch(client, headers, before)["revision"] == before["revision"]


def test_other_tenant_cannot_add_even_with_the_same_customer_id(direct, rv):
    from uuid import UUID
    from app.domains.travel_ops.components.intake import pipeline
    from app.domains.travel_ops.modules.web_account.web_session import resolve

    client, headers, before = direct
    with get_connection() as conn:
        customer = resolve(conn, tenant_id=rv["tenant"], raw=headers["X-User-Key"])
        with pytest.raises(LookupError):
            pipeline.edit(conn, tenant_id=rv["tenant"] + "_other", customer_id=customer,
                          intake_id=UUID(before["intake_id"]), revision=before["revision"], edits=new_fields(before))
    assert fetch(client, headers, before)["revision"] == before["revision"]


def test_review_failure_rolls_back_all_new_claims_and_revision(direct, monkeypatch):
    client, headers, before = direct
    def failed(*args, **kwargs):
        raise RuntimeError("mock review failure")
    monkeypatch.setattr(review, "ensure", failed)
    response = request(client, headers, before, [_field(before["review"]["items"][0], "place", HOTEL)])
    assert response.status_code == 409 and response.json()["error"]["code"] == "schedule_check_failed"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT revision FROM trip_intakes WHERE intake_id=%s", (before["intake_id"],))
        assert cur.fetchone()[0] == before["revision"]
        cur.execute("SELECT count(*) FROM intake_claims WHERE intake_id=%s AND revision>%s",
                    (before["intake_id"], before["revision"]))
        assert cur.fetchone()[0] == 0


def test_booked_and_pinned_anchors_preserve_original_on_conflict(direct):
    client, headers, before = direct
    # DB의 읽은 예약 표시를 추가한다. 예약 자체를 새로 만들지는 않는다.
    items = before["review"]["items"]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for item in items[:2]:
            cur.execute("INSERT INTO intake_claims (intake_id,tenant_id,revision,source_id,field,value_json,method,evidence,needs_review,created_at) "
                        "SELECT intake_id,tenant_id,revision,%s,%s,%s,'rule',%s,false,clock_timestamp() "
                        "FROM trip_intakes WHERE intake_id=%s",
                        (item["source_id"], f"items[{item['index']}].booked", json.dumps(True), json.dumps({"source": "test"}), before["intake_id"]))
    response = request(client, headers, before, [_field(items[0], "place", HOTEL)])
    assert response.status_code == 409 and response.json()["error"]["code"] == "schedule_conflict", response.text
    assert fetch(client, headers, before)["revision"] == before["revision"]
