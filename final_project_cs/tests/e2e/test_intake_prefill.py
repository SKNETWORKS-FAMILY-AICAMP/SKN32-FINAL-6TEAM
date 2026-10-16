# -*- coding: utf-8 -*-
"""비서처럼 먼저 채우기(`intake/prefill.py`) — 읽은 직후 **빈칸만** 담당에게 맡겨 채우고, 「우리가 채움」 + 이유를 확인 화면에 싣는다. `[2026-10-16 D-025]`

★지키려는 것
 ①이름 없는 자리(「성수 식당」)는 같은 지역 · 같은 종류의 곳으로 **먼저 채운다** — 확인 화면을 열면 이미 채워져 있고, 왜 채웠는지가 같이 온다
 ②고객이 이름을 적은 곳(「경복궁」)과 그 시각은 건드리지 않는다
 ③예약했다는데 이름이 없는 자리(「성수 예약 식당 · 예약 있음」)는 우리가 고르지 않고 **묻는다**
 ④채운 것은 고객이 고친 것과 같은 길(새 판 · 되돌리기 가능)이고, 채우기를 꺼도 읽기 · 확인 화면은 그대로다

재현:

    python -m pytest tests/e2e/test_intake_prefill.py -v
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.intake import areas as areas_module
from app.domains.travel_ops.components.intake import pipeline
from app.domains.travel_ops.components.intake.areas import AreaIndex

from .test_intake_nameless_lines import FAR_DONGDAEMUN, LEDGER_SEONGSU, PLAN, ROWS, SEONGSU_ADDRESS, SHOPS_SEONGSU
from .test_intake_review import OPEN_ALL, _catalog, _client, _hours, _item, _key, _row, _send, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401


@pytest.fixture()
def filled(rv, monkeypatch):  # noqa: F811
    """`test_intake_nameless_lines` 와 같은 성수 장소들 — 단 먼저 채우기를 켠 채로(가드레일 기본값)."""
    from app.infrastructure.db.session import get_connection

    monkeypatch.setattr(pipeline, "areas_for", lambda conn, tenant_id, terms=None: AreaIndex.from_rows(ROWS))
    areas_module.reset()
    for cid, title, lat, lon in SHOPS_SEONGSU:
        _catalog(rv, cid, "38", title, lat, lon, SEONGSU_ADDRESS)
    _hours(rv, "126508", OPEN_ALL)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for name, lat, lon in [*LEDGER_SEONGSU, FAR_DONGDAEMUN]:
            cur.execute("INSERT INTO places (tenant_id, name, kind, latitude, longitude, source_name, attributes) "
                        "VALUES (%s,%s,'dining',%s,%s,'dining_ledger','{\"source\": \"dining_ledger\"}')", (rv["tenant"], name, lat, lon))
    yield rv
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM places WHERE tenant_id=%s AND source_name='dining_ledger'", (rv["tenant"],))
    areas_module.reset()


def test_blanks_are_filled_first_with_a_reason_and_named_or_booked_stops_are_left_alone(filled):
    assert pipeline.agent_reader_config("t")["prefill"] == "on"                     # 가드레일 기본값
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    assert view["status"] == "review" and view["revision"] > 1                      # 채운 것이 새 판이다(고객이 고친 것과 같은 길)
    prefill = view["prefill"]
    assert prefill is not None
    by_item = {f["item"]: f for f in prefill["filled"]}
    plain = _item(view, "성수 식당")
    assert plain["place"] is not None and plain["place"]["name"] in {n for n, _, _ in LEDGER_SEONGSU}   # ①같은 지역의 식당으로
    assert plain["id"] in by_item and "가게 이름이 없는 자리" in by_item[plain["id"]]["reason"]
    assert by_item[plain["id"]]["owner"] == "dining_team" and by_item[plain["id"]]["owner_label"] == "식당 팀"
    palace = _item(view, "경복궁")
    assert palace["place_state"] == "found" and palace["id"] not in by_item and palace["starts_at"] == "16:30"   # ②그대로
    booked = _item(view, "성수 예약 식당")
    assert booked["place"] is None and booked["id"] not in by_item                                       # ③고르지 않는다
    assert any("예약하신 곳의 이름" in q["question"] for q in prefill["questions"])
    assert _row(booked, "booking")["result"] == "warn"


def test_with_prefill_off_the_reading_and_check_are_what_they_were(filled, monkeypatch):
    real = pipeline.agent_reader_config
    monkeypatch.setattr(pipeline, "agent_reader_config", lambda tenant_id: {**real(tenant_id), "prefill": "off"})
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    assert view["revision"] == 1 and view["prefill"] is None                                             # ④끄면 옛 동작 그대로
    assert _item(view, "성수 식당")["place_state"] == "needs_choice"


def test_a_filled_blank_keeps_the_time_the_customer_wrote(filled):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    plain = _item(view, "성수 식당")
    assert plain["place"] is not None and plain["starts_at"] == "15:00"            # 장소만 채우고 고객이 적은 시각은 그대로
