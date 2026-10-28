"""로컬 개발 DB에서 등록 이동 보존·기존 여행 경로 복구·본인 여행 권한을 확인한다."""
from uuid import UUID
from zoneinfo import ZoneInfo

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.instances.mobility import route_shape
from .test_trip_api import api  # noqa: F401
from .test_trip_intake_api import CHAT_PLAN, _confirm, _full_client, _key, _send, _stored
from tests.helpers import relative_dates as reldate

# ★`[2026-10-28]` 박아 둔 날짜는 실행 날 기준으로 옮긴다 — 전부-과거 가드(`all_dates_before_today`)가 실제 시계를 읽는다.
#   요일 · 순서 · 간격은 원래 자료와 같다(`tests/helpers/relative_dates.py`).
D_2026_10_18 = reldate.day("2026-10-18")


class Router:
    def route(self, start, end, **kwargs):
        return {"paths": [{"points": {"coordinates": [list(start), list(end)]}}]}


def registered(monkeypatch):
    monkeypatch.setattr(route_shape, "_engine", lambda: (Router(), None))
    monkeypatch.setattr(route_shape, "_line_order", lambda: None)
    client, _, _ = _full_client()
    headers = _key(client)
    view = _send(client, headers, text=CHAT_PLAN)
    trip = _confirm(client, headers, view["intake_id"], view["revision"])["trip"]
    return client, headers, view, trip


def test_registered_moves_keep_checked_times_and_route_shapes_and_repeated_confirm_does_not_duplicate(api, monkeypatch):
    client, headers, view, trip = registered(monkeypatch)
    moves = [item for item in _stored(api, trip) if item.kind == "mobility"]
    assert len(moves) == len(view["review"]["moves"]) == 2
    for item, checked in zip(moves, view["review"]["moves"]):
        assert item.starts_at.astimezone(ZoneInfo("Asia/Seoul")).strftime("%H:%M") == checked["depart"]
        assert item.ends_at.astimezone(ZoneInfo("Asia/Seoul")).strftime("%H:%M") == checked["arrive"]
        assert item.detail["route_def"]["options"][0]["uses"] == checked.get("uses", [])
    response = client.get(f"/v1/web/trips/{trip['trip_id']}/route-shapes", headers=headers)
    assert response.status_code == 200, response.text
    assert {shape["item_id"] for shape in response.json()["shapes"]} == {str(move.item_id) for move in moves}
    again = _confirm(client, headers, view["intake_id"], view["revision"])["trip"]
    assert again["trip_id"] == trip["trip_id"] and again["created"] is False
    assert len([item for item in _stored(api, trip) if item.kind == "mobility"]) == 2


def test_legacy_routes_use_only_linked_customer_review_without_rewriting_trip_items(api, monkeypatch):
    client, headers, view, trip = registered(monkeypatch)
    trip_id = UUID(trip["trip_id"])
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM itinerary_items WHERE tenant_id=%s AND trip_id=%s AND kind='mobility'", (api["tenant"], trip_id))
        cur.execute("UPDATE itinerary_items SET detail=detail #- '{intake,source_id}' #- '{intake,index}' "
                    "WHERE tenant_id=%s AND trip_id=%s", (api["tenant"], trip_id))
    for suffix in ("", "?detail=true"):
        response = client.get(f"/v1/web/trips/{trip_id}/route-shapes{suffix}", headers=headers)
        assert response.status_code == 200, response.text
        shapes = response.json()["shapes"]
        assert len(shapes) == 2 and all(len(shape["line"]["coordinates"]) >= 2 for shape in shapes)
        assert response.json()["detail"] == bool(suffix)
    shown = client.get(f"/v1/web/trips/{trip_id}", headers=headers)
    assert shown.status_code == 200, shown.text
    assert len([item for item in shown.json()["items"] if item["kind"] == "mobility"]) == 2
    again = _confirm(client, headers, view["intake_id"], view["revision"])
    assert again["trip"]["created"] is False and again["trip"]["trip_id"] == str(trip_id)
    assert len(_stored(api, trip)) == 3 and all(item.kind != "mobility" for item in _stored(api, trip))
    stranger = _key(client)
    assert client.get(f"/v1/web/trips/{trip_id}/route-shapes", headers=stranger).status_code == 404
    # A changed coordinate invalidates both old adjacent routes.
    middle = _stored(api, trip)[1]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE places SET latitude=latitude+0.01 WHERE tenant_id=%s AND place_id=%s", (api["tenant"], middle.place_id))
    assert client.get(f"/v1/web/trips/{trip_id}/route-shapes", headers=headers).json()["shapes"] == []


def test_booking_declared_without_a_number_stays_booked_after_registration(api):
    from app.domains.travel_ops.components.planning.pending import protected_reason

    client, _, _ = _full_client()
    headers = _key(client)
    view = _send(client, headers, text=f"1일차 {D_2026_10_18}\n09:00 경복궁 · 예약 있음")
    trip = _confirm(client, headers, view["intake_id"], view["revision"])["trip"]
    assert trip["items"][0]["booked"] is True
    saved = _stored(api, trip)[0]
    assert saved.detail["booking"] == {"declared_by": "customer_plan"}
    assert protected_reason(saved) is None  # D-020: 예약 사실과 고객이 고정한 항목을 구분한다.
    from dataclasses import replace
    assert protected_reason(replace(saved, detail={**saved.detail, "customer_pinned": True})) == "customer_pinned"
