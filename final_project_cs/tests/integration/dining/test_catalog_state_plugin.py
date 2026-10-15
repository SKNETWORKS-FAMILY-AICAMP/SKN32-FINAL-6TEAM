"""The pre-registration hook delegates real SQL judgment without bypassing Dining."""
from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.registry import TeamRegistry
from app.core.service_bindings import BindingTable, bind_services
from app.domains.travel_ops.components.intake.hours import facts_for
from app.domains.travel_ops.instances.dining.ledger import catalog_state
from tests.integration.dining.test_dining_judgment import add_hours, at
from tests.unit.core.test_plugin_availability import Team


@pytest.mark.parametrize("identify_by", ["uid", "exact_name"])
def test_pre_registration_ledger_hours_use_real_sql(conn, place, identify_by):
    uid = place("플러그인식당")
    name = f"원장검증{uuid4().hex}"
    conn.execute("UPDATE dining.dn_place SET name_ko=%s, is_synthetic=false, "
                 "road_address='서울특별시 종로구 시험로 1' WHERE place_uid=%s", (name, uid))
    add_hours(conn, uid, 1, [(660, 1320, 1260)])
    found = {"name": name, "_hours": {"hours": ["00:00", "23:59"]}}
    if identify_by == "uid":
        found["dining_place_uid"] = uid
    table = BindingTable({("dining_ledger", "catalog_state"): catalog_state},
                         TeamRegistry([Team(team_id="dining")]), "sql-test")
    with bind_services(table):
        actual = facts_for(conn, "test", found, "dining", at(0, "12:00"), at(0, "13:00"))
        late = facts_for(conn, "test", found, "dining", at(0, "21:10"), at(0, "21:40"))
    assert actual.source == "dining_ledger" and actual.open_at_slot is True
    assert actual.order_ok is True and actual.attributes["hours"] == ["11:00", "22:00"]
    assert late.open_at_slot is False


def test_ambiguous_name_does_not_borrow_another_shops_hours(conn, place):
    name = f"중복원장{uuid4().hex}"
    for _ in range(2):
        uid = place(name)
        conn.execute("UPDATE dining.dn_place SET name_ko=%s, is_synthetic=false, "
                     "road_address='서울특별시 종로구 시험로 1' WHERE place_uid=%s", (name, uid))
        add_hours(conn, uid, 1, [(660, 1320, None)])
    assert catalog_state(conn, None, {"name": name}, at(0, "12:00"), at(0, "12:00") + timedelta(hours=1)) is None
