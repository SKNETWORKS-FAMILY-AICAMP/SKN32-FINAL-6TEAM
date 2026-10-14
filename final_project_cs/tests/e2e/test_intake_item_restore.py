"""일정별 복원은 다른 일정·여행 값을 유지하며 기존 보호·소유권·원자성을 적용한다."""
import json
from uuid import uuid4

import pytest

from app.infrastructure.db.session import get_connection
from .test_trip_api import api  # noqa: F401
from .test_intake_review import rv, _field, _key  # noqa: F401
from .test_intake_direct_schedule import direct, request, fetch  # noqa: F401
from .test_intake_restore import changed, effective_values


def restore_item(client, headers, view, original, item):
    return client.post(f"/v1/web/trip-intakes/{view['intake_id']}/restore", headers=headers,
                       json={"revision": view["revision"], "restore_revision": original,
                             "item": {"source_id": item["source_id"], "index": item["index"]}})


def test_only_selected_item_restored_other_item_and_trip_claims_exactly_kept(direct):
    client, headers, original, current = changed(direct)
    other = current["review"]["items"][1]
    response = request(client, headers, current, [_field(other, "title", "다른 일정 수정")])
    assert response.status_code == 200, response.text
    current = response.json()
    before = effective_values(current["intake_id"], current["revision"])
    target = original["review"]["items"][0]
    key = (target["source_id"], f"items[{target['index']}].")
    selected = lambda entry: entry[0] == key[0] and entry[1].startswith(key[1])
    response = restore_item(client, headers, current, original["revision"], target)
    assert response.status_code == 200, response.text
    result = response.json()
    after = effective_values(result["intake_id"], result["revision"])
    old = effective_values(original["intake_id"], original["revision"])
    assert {k: v for k, v in after.items() if selected(k)} == {k: v for k, v in old.items() if selected(k)}
    assert {k: v for k, v in after.items() if not selected(k)} == {k: v for k, v in before.items() if not selected(k)}
    assert result["review"]["revision"] == result["revision"] == current["revision"] + 1


@pytest.mark.parametrize("protection,code", [("locked", "item_locked"), ("booked", "item_booked")])
def test_scoped_restore_refuses_protected_item_without_saving(direct, protection, code):
    client, headers, original, current = changed(direct)
    target = current["review"]["items"][0]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO intake_claims (intake_id,tenant_id,revision,source_id,field,value_json,method,evidence,needs_review,created_at) "
                    "SELECT intake_id,tenant_id,revision,%s,%s,%s,'customer','{}',false,clock_timestamp() "
                    "FROM trip_intakes WHERE intake_id=%s", (target["source_id"], f"items[{target['index']}].{protection}", json.dumps(True), current["intake_id"]))
    response = restore_item(client, headers, current, original["revision"], target)
    assert response.status_code == 409 and response.json()["error"]["code"] == code
    assert fetch(client, headers, current)["revision"] == current["revision"]


def test_scoped_restore_rejects_unknown_target_and_other_customer(direct):
    client, headers, original, current = changed(direct)
    target = current["review"]["items"][0]
    response = restore_item(client, headers, current, original["revision"], {**target, "source_id": str(uuid4())})
    assert response.status_code == 409 and response.json()["error"]["code"] == "restore_item_invalid"
    response = restore_item(client, _key(client), current, original["revision"], target)
    assert response.status_code == 404
    assert fetch(client, headers, current)["revision"] == current["revision"]
