"""HTTP·로컬 개발 DB에서 전체 복원의 원자성·보호·소유권을 확인한다. 외부 조회는 mock 응답이다."""
import json
from uuid import UUID

import pytest

from app.domains.travel_ops.components.intake import pipeline, review, direct_schedule
from app.infrastructure.db.session import get_connection
from .test_trip_api import api  # noqa: F401
from .test_intake_review import rv, _field, _key  # noqa: F401
from .test_intake_direct_schedule import direct, request, new_fields, fetch, HOTEL  # noqa: F401


def restore(client, headers, view, original):
    return client.post(f"/v1/web/trip-intakes/{view['intake_id']}/restore", headers=headers,
                       json={"revision": view["revision"], "restore_revision": original})


def effective_values(intake_id, revision):
    with get_connection() as conn:
        return {(str(c["source_id"]), c["field"]): (c["value"], c["method"], c["evidence"], c["needs_review"], c["note"])
                for c in pipeline.effective(pipeline._claims(conn, _tenant(conn, intake_id), UUID(intake_id), revision))}


def _tenant(conn, intake_id):
    with conn.cursor() as cur:
        cur.execute("SELECT tenant_id FROM trip_intakes WHERE intake_id=%s", (intake_id,))
        return cur.fetchone()[0]


def changed(direct):
    client, headers, original = direct
    item = original["review"]["items"][0]
    response = request(client, headers, original, [_field(item, "place", HOTEL), _field(item, "title", "숙소")])
    assert response.status_code == 200, response.text
    return client, headers, original, response.json()


def test_restore_place_retiming_add_delete_and_title_as_one_exact_historical_revision(direct, monkeypatch):
    client, headers, original, current = changed(direct)
    assert current["review"]["items"][1]["starts_at"] != original["review"]["items"][1]["starts_at"]
    response = request(client, headers, current, new_fields(current))
    assert response.status_code == 200, response.text
    current = response.json()
    response = request(client, headers, current, [_field(current["review"]["items"][2], "removed", True)])
    assert response.status_code == 200, response.text
    current = response.json()
    def no_rearrangement(*args, **kwargs):
        raise AssertionError("history restore must not rearrange times")
    monkeypatch.setattr(direct_schedule, "fit", no_rearrangement)
    response = restore(client, headers, current, original["revision"])
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["revision"] == current["revision"] + 1
    assert result["review"]["revision"] == result["revision"]
    assert effective_values(result["intake_id"], result["revision"]) == effective_values(original["intake_id"], original["revision"])
    fields = ("id", "title", "place", "starts_at", "ends_at", "date", "locked")
    assert [{f: i[f] for f in fields} for i in result["review"]["items"]] == [
        {f: i[f] for f in fields} for i in original["review"]["items"]]
    assert fetch(client, headers, current)["revision"] == result["revision"]


@pytest.mark.parametrize("target", [0, 2, 999])
def test_invalid_or_nonpast_original_keeps_current_revision(direct, target):
    client, headers, original, current = changed(direct)
    response = restore(client, headers, current, target)
    assert response.status_code == (422 if target == 0 else 409), response.text
    assert fetch(client, headers, current)["revision"] == current["revision"]


def test_stale_restore_preserves_all_current_values(direct):
    client, headers, original, current = changed(direct)
    response = restore(client, headers, original, original["revision"])
    assert response.status_code == 409 and response.json()["error"]["code"] == "stale_revision"
    assert fetch(client, headers, current)["revision"] == current["revision"]


@pytest.mark.parametrize("protection,code", [("locked", "item_locked"), ("booked", "item_booked"), ("booking_no", "item_booked")])
def test_protected_current_item_prevents_any_partial_restore(direct, protection, code):
    client, headers, original, current = changed(direct)
    item = current["review"]["items"][0]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO intake_claims (intake_id,tenant_id,revision,source_id,field,value_json,method,evidence,needs_review,created_at) "
                    "SELECT intake_id,tenant_id,revision,%s,%s,%s,'customer','{}',false,clock_timestamp() "
                    "FROM trip_intakes WHERE intake_id=%s", (item["source_id"], f"items[{item['index']}].{protection}",
                    json.dumps("booking-test" if protection == "booking_no" else True), current["intake_id"]))
    before = effective_values(current["intake_id"], current["revision"])
    response = restore(client, headers, current, original["revision"])
    assert response.status_code == 409 and response.json()["error"]["code"] == code, response.text
    assert effective_values(current["intake_id"], current["revision"]) == before
    assert fetch(client, headers, current)["revision"] == current["revision"]


def test_missing_completed_history_and_failed_new_check_leave_no_new_revision(direct, monkeypatch):
    client, headers, original, current = changed(direct)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM intake_reviews WHERE intake_id=%s AND revision=%s", (original["intake_id"], original["revision"]))
    response = restore(client, headers, current, original["revision"])
    assert response.status_code == 409 and response.json()["error"]["code"] == "restore_revision_invalid"
    with get_connection() as conn:
        review.ensure(conn, tenant_id=_tenant(conn, original["intake_id"]), intake_id=UUID(original["intake_id"]),
                      revision=original["revision"], sources=pipeline._sources(conn, _tenant(conn, original["intake_id"]), UUID(original["intake_id"])),
                      claims=pipeline._claims(conn, _tenant(conn, original["intake_id"]), UUID(original["intake_id"]), original["revision"]), force=True)
    def failed(*args, **kwargs):
        raise RuntimeError("mock check failure")
    monkeypatch.setattr(review, "ensure", failed)
    response = restore(client, headers, current, original["revision"])
    assert response.status_code == 409 and response.json()["error"]["code"] == "schedule_check_failed"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT revision FROM trip_intakes WHERE intake_id=%s", (current["intake_id"],))
        assert cur.fetchone()[0] == current["revision"]
        for table in ("intake_claims", "intake_reviews"):
            cur.execute(f"SELECT count(*) FROM {table} WHERE intake_id=%s AND revision>%s", (current["intake_id"], current["revision"]))
            assert cur.fetchone()[0] == 0


def test_other_customer_and_tenant_cannot_restore(direct, rv):
    from app.domains.travel_ops.modules.web_account.web_session import resolve
    client, headers, original, current = changed(direct)
    response = restore(client, _key(client), current, original["revision"])
    assert response.status_code == 404
    with get_connection() as conn:
        customer = resolve(conn, tenant_id=rv["tenant"], raw=headers["X-User-Key"])
        with pytest.raises(LookupError):
            pipeline.restore(conn, tenant_id=rv["tenant"] + "_other", customer_id=customer,
                             intake_id=UUID(current["intake_id"]), revision=current["revision"], restore_revision=original["revision"])
    assert fetch(client, headers, current)["revision"] == current["revision"]


def test_unchanged_protected_anchor_does_not_block_restoring_other_items(direct):
    client, headers, original = direct
    response = request(client, headers, original, [_field(original["review"]["items"][0], "locked", True)])
    assert response.status_code == 200, response.text
    original = response.json()
    response = request(client, headers, original, [_field(original["review"]["items"][2], "title", "이름 변경")])
    assert response.status_code == 200, response.text
    current = response.json()
    response = restore(client, headers, current, original["revision"])
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["review"]["items"][0]["locked"] is True
    assert effective_values(result["intake_id"], result["revision"]) == effective_values(original["intake_id"], original["revision"])
