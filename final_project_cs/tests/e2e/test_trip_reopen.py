# -*- coding: utf-8 -*-
"""등록한 여행 고치기(수정 모드) — `POST /v1/web/trips/{trip_id}/reopen` · 수정 접수의 `/confirm`. `[2026-10-13 사용자 결정]`

★계약 `wiki/external/rest-endpoints.md` 「등록한 여행 고치기」. 확인 화면의 고치기는 기존 접수 경로 그대로이고,
  여기서는 다시 열기 · 「완료」가 같은 여행의 새 판을 쓰는 것(안 바뀐 일정은 같은 id · 바뀐 일정은 새 id 가 원래를 가리킴 ·
  지난 일정은 그대로 · 판 하나 · 알림 하나)과 거절(낡은 판 · 지난 일정 · 여행 칸 · 일정 짜기)을 본다.

재현:

    python -m pytest tests/e2e/test_trip_reopen.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary import TripStore

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_api import _h, _member, _session

KST = ZoneInfo("Asia/Seoul")
NOW = datetime.now(KST)
#: 어제는 다 끝났고 내일은 아직 안 왔다 — 실제 시계로 「지난 일정」과 「앞으로의 일정」을 가른다
YESTERDAY, TOMORROW = (NOW - timedelta(days=1)).date().isoformat(), (NOW + timedelta(days=1)).date().isoformat()


def _at(day: str, hhmm: str) -> str:
    return f"{day}T{hhmm}:00+09:00"


def _place(key, name, lat, lon):
    return {"key": key, "name": name, "kind": "activity", "lat": lat, "lon": lon, "weather_sensitive": None, "attributes": {}}


def _item(seq, kind, title, place, day, start, end):
    return {"seq": seq, "kind": kind, "title": title, "place": place, "starts_at": _at(day, start), "ends_at": _at(day, end),
            "detail": {}}


def _trip(api, key: str) -> dict:
    """어제 경복궁(끝남) · 내일 북촌 → 인사동 → N서울타워(이동 항목 둘). 덕수궁은 등록만 한 공용 장소(바꿀 곳)."""
    body = {"request_id": "reopen-trip", "title": "서울 이틀", "locale": "ko", "party_size": 2, "constraints": {},
            "places": [_place("gb", "경복궁", 37.5796, 126.9770), _place("bc", "북촌한옥마을", 37.5826, 126.9836),
                       _place("is", "인사동", 37.5740, 126.9850), _place("ns", "N서울타워", 37.5512, 126.9882),
                       _place("ds", "덕수궁", 37.5658, 126.9751)],
            "items": [_item(1, "activity", "경복궁", "gb", YESTERDAY, "10:00", "12:00"),
                      _item(2, "activity", "북촌한옥마을", "bc", TOMORROW, "10:00", "11:30"),
                      _item(3, "mobility", "북촌한옥마을 → 인사동 · 걸음", None, TOMORROW, "11:30", "11:50"),
                      _item(4, "activity", "인사동", "is", TOMORROW, "12:00", "13:30"),
                      _item(5, "mobility", "인사동 → N서울타워 · 버스", None, TOMORROW, "13:30", "14:10"),
                      _item(6, "activity", "N서울타워", "ns", TOMORROW, "15:00", "16:30")]}
    response = api["client"].post("/v1/web/trips", json=body, headers=_h(key))
    assert response.status_code == 201, response.text
    return response.json()


def _user(api) -> str:
    key = _session(api)["user_key"]
    _member(api, key)                     # 게스트 제한(여행 1개 · 기간)과 섞지 않는다
    return key


def _reopen(api, key, trip_id, version, status=200):
    response = api["client"].post(f"/v1/web/trips/{trip_id}/reopen", json={"version": version}, headers=_h(key))
    assert response.status_code == status, response.text
    return response.json()


def _edit(api, key, view, *edits, status=200):
    response = api["client"].post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=_h(key),
                                  json={"revision": view["revision"], "edits": list(edits)})
    assert response.status_code == status, response.text
    return response.json()


def _confirm(api, key, view, status=200, **extra):
    response = api["client"].post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=_h(key),
                                  json={"revision": view["revision"], **extra})
    assert response.status_code == status, response.text
    return response.json()


def _stored(api, trip_id):
    with get_connection() as conn:
        return TripStore(api["tenant"]).latest(conn, UUID(str(trip_id)))


def _index(view, title):
    return next(i["index"] for i in view["sources"][0]["items"] if i["fields"]["title"]["value"] == title)


def test_reopen_puts_only_the_stops_still_ahead_into_a_check_screen_intake(api):
    key = _user(api)
    trip = _trip(api, key)
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    _, items = _stored(api, trip["trip_id"])
    by_title = {i.title: str(i.item_id) for i in items}
    assert view["status"] == "review" and view["trip_id"] is None
    assert view["reopen"] == {"trip_id": trip["trip_id"], "version": trip["version"],
                              "frozen_item_ids": [by_title["경복궁"]]}          # ★끝난 일정은 접수에 넣지 않는다
    source = view["sources"][0]
    assert source["kind"] == "trip"
    assert [i["fields"]["title"]["value"] for i in source["items"]] == ["북촌한옥마을", "인사동", "N서울타워"]
    first = source["items"][0]["fields"]
    assert {f["method"] for f in first.values()} == {"trip"}                      # 등록한 여행에서 가져온 값 — 고객이 고친 값과 다르다
    assert first["title"]["evidence"]["item_id"] == by_title["북촌한옥마을"]
    assert (first["date"]["value"], first["starts_at"]["value"], first["ends_at"]["value"]) == (TOMORROW, "10:00", "11:30")
    assert view["check"]["ready"] is True, view["check"]["problems"]
    assert {i["status"] for i in view["review"]["items"]} >= {"keep"} and not any(i["edited"] for i in view["review"]["items"])
    # 다시 열면 같은 접수 — 고치던 값이 남는다
    assert _reopen(api, key, trip["trip_id"], trip["version"])["intake_id"] == view["intake_id"]


def test_done_without_changes_writes_no_new_version(api):
    key = _user(api)
    trip = _trip(api, key)
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    done = _confirm(api, key, view)
    assert (done["status"], done["changed"], done["version"]) == ("confirmed", False, trip["version"])
    assert len(done["trip"]["history"]) == 1                                      # 처음 등록 판 하나 그대로
    assert _confirm(api, key, view) == done                                        # 다시 눌러도 같다


def test_a_changed_and_a_removed_stop_become_one_new_version_of_the_same_trip(api):
    key = _user(api)
    trip = _trip(api, key)
    _, before = _stored(api, trip["trip_id"])
    old = {i.title: i for i in before}
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    source = view["sources"][0]["source_id"]
    insa = _index(view, "인사동")
    view = _edit(api, key, view, {"source_id": source, "field": f"items[{insa}].starts_at", "value": "12:30"},
                 {"source_id": source, "field": f"items[{insa}].ends_at", "value": "14:00"})
    view = _edit(api, key, view, {"source_id": source, "field": f"items[{_index(view, 'N서울타워')}].removed", "value": True})
    done = _confirm(api, key, view)
    assert (done["changed"], done["version"]) == (True, trip["version"] + 1)
    assert done["trip"]["trip_id"] == trip["trip_id"]                              # ★새 여행이 아니라 같은 여행
    meta, after = _stored(api, trip["trip_id"])
    assert meta["version"] == trip["version"] + 1
    assert [i.kind for i in after] == ["activity", "activity", "mobility", "activity"]
    assert [i.title for i in after if i.kind != "mobility"] == ["경복궁", "북촌한옥마을", "인사동"]
    # ★`[2026-10-14]` 바뀐 일정 옆 옛 이동은 빠지고, 확인 화면이 검증한 이동이 새 항목으로 들어간다 — 그 구간 출발 알림이 이 항목으로 나간다
    move = after[2]
    assert move.item_id not in {i.item_id for i in before} and move.detail.get("route_def")
    assert move.starts_at >= datetime.fromisoformat(_at(TOMORROW, "11:30")) and move.ends_at <= datetime.fromisoformat(_at(TOMORROW, "12:30"))
    now = {i.title: i for i in after}
    assert now["경복궁"].item_id == old["경복궁"].item_id                          # 지난 일정 — 그대로
    assert now["북촌한옥마을"].item_id == old["북촌한옥마을"].item_id              # 안 바뀐 일정 — 같은 id
    assert now["인사동"].item_id != old["인사동"].item_id and now["인사동"].replaces_item_id == old["인사동"].item_id
    assert now["인사동"].place_id == old["인사동"].place_id                         # 같은 곳 — 장소 행을 새로 만들지 않는다
    assert now["인사동"].starts_at == datetime.fromisoformat(_at(TOMORROW, "12:30"))
    last = done["trip"]["history"][-1]
    assert last["reason"] == "customer_request" and last["causes"][0]["type"] == "edit"
    assert "바꾼 일정 인사동" in last["causes"][0]["summary"] and "뺀 일정 N서울타워" in last["causes"][0]["summary"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT payload_json->>'text' FROM outbox WHERE tenant_id=%s AND topic='trip.notice' AND dedupe_key=%s",
                    (api["tenant"], f"{trip['trip_id']}:v{trip['version'] + 1}"))
        [(text,)] = cur.fetchall()                                                 # ★알림 하나
    assert text.startswith("일정을 직접 고쳤어요")
    again = _confirm(api, key, view)                                               # 같은 「완료」를 다시 — 판은 하나
    assert (again["version"], again["changed"]) == (trip["version"] + 1, True)
    assert _stored(api, trip["trip_id"])[0]["version"] == trip["version"] + 1


def test_a_move_between_two_untouched_stops_stays(api):
    key = _user(api)
    trip = _trip(api, key)
    _, before = _stored(api, trip["trip_id"])
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    source = view["sources"][0]["source_id"]
    tower = _index(view, "N서울타워")
    view = _edit(api, key, view, {"source_id": source, "field": f"items[{tower}].starts_at", "value": "15:30"},
                 {"source_id": source, "field": f"items[{tower}].ends_at", "value": "17:00"})
    _confirm(api, key, view)
    _, after = _stored(api, trip["trip_id"])
    kept = next(i for i in before if i.title.startswith("북촌한옥마을 →"))
    assert kept.item_id in {i.item_id for i in after}                              # 북촌 · 인사동이 그대로라 그 사이 이동도 그대로
    old_move = next(i for i in before if i.title.startswith("인사동 →"))
    assert old_move.item_id not in {i.item_id for i in after}                      # N서울타워가 바뀌어 그 앞 옛 이동은 빠지고
    kinds = [i.kind for i in after]
    assert kinds[-2:] == ["mobility", "activity"]                                  # ★`[2026-10-14]` 그 자리에 검증한 이동이 들어간다
    assert [i.seq for i in after] == list(range(1, len(after) + 1))


def test_a_new_place_from_our_places_reuses_that_row(api):
    key = _user(api)
    trip = _trip(api, key)
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    source = view["sources"][0]["source_id"]
    view = _edit(api, key, view, {"source_id": source, "field": f"items[{_index(view, '인사동')}].place", "value": {"name": "덕수궁"}})
    done = _confirm(api, key, view)
    _, after = _stored(api, trip["trip_id"])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT place_id FROM places WHERE tenant_id=%s AND name='덕수궁' AND trip_scope IS NULL", (api["tenant"],))
        [(shared,)] = cur.fetchall()
    moved = next(i for i in after if i.place_id == shared)
    # ★확인 화면 카드가 보인 이름(고른 곳)으로 — 원문 「인사동」은 근거에 남는다
    assert moved.title == "덕수궁" and moved.replaces_item_id is not None and moved.place["name"] == "덕수궁"
    assert moved.detail["provenance"]["title"]["method"] == "trip"
    assert "바꾼 일정 인사동 → 덕수궁" in done["trip"]["history"][-1]["causes"][0]["summary"]


def test_a_stale_trip_version_is_refused_on_open_and_on_done(api):
    key = _user(api)
    trip = _trip(api, key)
    refused = _reopen(api, key, trip["trip_id"], trip["version"] + 1, status=409)
    assert refused["error"]["code"] == "stale_itinerary" and refused["error"]["version"] == trip["version"]
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    source = view["sources"][0]["source_id"]
    view = _edit(api, key, view, {"source_id": source, "field": f"items[{_index(view, 'N서울타워')}].removed", "value": True})
    store = TripStore(api["tenant"])
    with get_connection() as conn, conn.transaction():                            # 그 사이 감시 · 채팅이 일정을 바꿨다
        meta, items = store.latest(conn, UUID(trip["trip_id"]))
        store.append_version(conn, trip_id=meta["trip_id"], base_version=meta["version"], items=items,
                             reason="auto_adjusted", causes=[])
    _confirm(api, key, view, status=409)
    assert _stored(api, trip["trip_id"])[0]["version"] == trip["version"] + 1     # 아무것도 쓰지 않았다
    fresh = _reopen(api, key, trip["trip_id"], trip["version"] + 1)
    assert fresh["intake_id"] != view["intake_id"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM trip_intakes WHERE intake_id=%s", (view["intake_id"],))
        assert cur.fetchone()[0] == "closed"                                       # 옛 수정 접수는 닫았다(값은 남는다)


def test_touching_a_stop_that_is_already_over_is_refused(api):
    key = _user(api)
    trip = _trip(api, key)
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    source = view["sources"][0]["source_id"]
    added = len(view["sources"][0]["items"])
    view = _edit(api, key, view, *[{"source_id": source, "field": f"items[{added}].{name}", "value": value} for name, value in (
        ("title", "덕수궁"), ("date", YESTERDAY), ("starts_at", "14:00"), ("ends_at", "15:00"), ("kind", "activity"),
        ("place", {"name": "덕수궁"}))])
    refused = _confirm(api, key, view, status=422)
    assert refused["error"]["code"] == "item_in_past" and refused["error"]["items"] == ["덕수궁"]
    assert _stored(api, trip["trip_id"])[0]["version"] == trip["version"]


def test_trip_fields_and_planning_are_not_open_in_an_edit_intake(api):
    key = _user(api)
    trip = _trip(api, key)
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    refused = _edit(api, key, view, {"field": "trip.title", "value": "다른 이름"}, status=422)
    assert refused["error"]["code"] == "trip_field_locked"
    planned = api["client"].post(f"/v1/web/trip-intakes/{view['intake_id']}/plan", headers=_h(key),
                                 json={"revision": view["revision"], "start_date": TOMORROW, "days": 1, "party_size": 2})
    assert planned.status_code == 409 and planned.json()["error"]["code"] == "intake_reopened"


def test_cancel_drops_the_changes_and_the_next_edit_starts_fresh(api):
    """`[2026-10-13 사용자 지시]` 수정 모드의 「취소」 — 고친 값은 여행에 쓰지 않고, 다시 열면 새 접수(고치던 값이 되살아나지 않는다)."""
    key = _user(api)
    trip = _trip(api, key)
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    source = view["sources"][0]["source_id"]
    _edit(api, key, view, {"source_id": source, "field": f"items[{_index(view, 'N서울타워')}].removed", "value": True})
    cancelled = api["client"].post(f"/v1/web/trip-intakes/{view['intake_id']}/cancel", headers=_h(key))
    assert cancelled.status_code == 200 and cancelled.json() == {"intake_id": view["intake_id"], "status": "closed"}
    assert api["client"].post(f"/v1/web/trip-intakes/{view['intake_id']}/cancel", headers=_h(key)).status_code == 200   # 두 번 눌러도 같다
    assert _stored(api, trip["trip_id"])[0]["version"] == trip["version"]                                                 # 여행은 그대로
    fresh = _reopen(api, key, trip["trip_id"], trip["version"])
    assert fresh["intake_id"] != view["intake_id"] and fresh["revision"] == 1
    assert "N서울타워" in [i["fields"]["title"]["value"] for i in fresh["sources"][0]["items"]]
    # 닫힌 접수로는 「완료」 못 한다 · 보통 접수는 취소 대상이 아니다 · 남의 것은 404
    assert api["client"].post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=_h(key), json={"revision": 2}).status_code == 409
    other = _user(api)
    assert api["client"].post(f"/v1/web/trip-intakes/{fresh['intake_id']}/cancel", headers=_h(other)).status_code == 404
    plain = api["client"].post("/v1/web/trip-intakes", headers=_h(key), data={"text": ""})
    refused = api["client"].post(f"/v1/web/trip-intakes/{plain.json()['intake_id']}/cancel", headers=_h(key))
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "intake_not_reopened"


def test_someone_elses_trip_does_not_open_and_deleting_the_trip_removes_its_edit_intakes(api):
    key = _user(api)
    trip = _trip(api, key)
    other = _user(api)
    _reopen(api, other, trip["trip_id"], trip["version"], status=404)
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    deleted = api["client"].post(f"/v1/web/trips/{trip['trip_id']}/delete", headers=_h(key), json={})
    assert deleted.status_code == 200, deleted.text
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM trip_intakes WHERE intake_id=%s", (view["intake_id"],))
        assert cur.fetchone()[0] == 0


def test_a_mode_picked_in_edit_mode_replaces_the_old_move_and_is_a_change_by_itself(api, monkeypatch):
    """`[2026-10-14 매니저 합침]` 수정 모드에서 고른 이동 수단은 「완료」 때 여행에 남는다 — 옛 이동을 갈음하고(`replaces_item_id`),
    수단만 바꿔도 새 판이다. ☆처음 판은 고른 수단을 버려 출발 알림이 옛 수단으로 나갔다."""
    from app.domains.travel_ops.components.intake import review as review_module

    from .test_intake_move_mode import FakeCalc

    monkeypatch.setattr(review_module, "default_engine", FakeCalc().factory)     # 시험용 이동 계산기(mock) — 계약 모양만 본다
    key = _user(api)
    trip = _trip(api, key)
    _, before = _stored(api, trip["trip_id"])
    old_move = next(i for i in before if i.title.startswith("북촌한옥마을 →"))
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    a, b = (next(i["id"] for i in view["review"]["items"] if i["title"] == t) for t in ("북촌한옥마을", "인사동"))
    picked = api["client"].post(f"/v1/web/trip-intakes/{view['intake_id']}/moves/{a}~{b}/mode", headers=_h(key),
                                json={"revision": view["revision"], "mode": "taxi"})
    assert picked.status_code == 200, picked.text
    done = _confirm(api, key, {"intake_id": view["intake_id"], "revision": picked.json()["revision"]})
    assert (done["changed"], done["version"]) == (True, trip["version"] + 1)
    _, after = _stored(api, trip["trip_id"])
    new_move = next(i for i in after if i.replaces_item_id == old_move.item_id)
    assert new_move.kind == "mobility" and new_move.detail["route_def"]["planned"] == "taxi"
    assert old_move.item_id not in {i.item_id for i in after}
    assert "이동(" in done["trip"]["history"][-1]["causes"][0]["summary"]


def test_reopening_shows_the_mode_saved_on_the_trip_and_done_without_touching_it_changes_nothing(api, monkeypatch):
    """`[2026-10-14 x600 실서버 확인]` 다시 연 수정 화면은 여행에 저장된 수단을 보인다(추천으로 되돌아가지 않는다).
    여행에서 가져온 수단(`method: trip`)은 고친 것이 아니라 그대로 「완료」하면 판을 쓰지 않는다."""
    from app.domains.travel_ops.components.intake import review as review_module

    from .test_intake_move_mode import FakeCalc

    monkeypatch.setattr(review_module, "default_engine", FakeCalc().factory)     # 시험용 이동 계산기(mock) — 계약 모양만 본다
    key = _user(api)
    trip = _trip(api, key)
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    a, b = (next(i["id"] for i in view["review"]["items"] if i["title"] == t) for t in ("북촌한옥마을", "인사동"))
    picked = api["client"].post(f"/v1/web/trip-intakes/{view['intake_id']}/moves/{a}~{b}/mode", headers=_h(key),
                                json={"revision": view["revision"], "mode": "taxi"})
    assert picked.status_code == 200, picked.text
    done = _confirm(api, key, {"intake_id": view["intake_id"], "revision": picked.json()["revision"]})
    assert done["version"] == trip["version"] + 1
    again = _reopen(api, key, trip["trip_id"], done["version"])
    a, b = (next(i["id"] for i in again["review"]["items"] if i["title"] == t) for t in ("북촌한옥마을", "인사동"))
    move = next(m for m in again["review"]["moves"] if m["from"] == a and m["to"] == b)
    assert move["mode"] == "taxi"                                                  # ★저장된 수단 — 추천(지하철)이 아니다
    untouched = _confirm(api, key, again)
    assert (untouched["changed"], untouched["version"]) == (False, done["version"])  # 가져온 수단은 고친 것이 아니다


def _small_trip(api, key: str, *items) -> dict:
    body = {"request_id": "reopen-hotfix", "title": "서울 하루", "locale": "ko", "party_size": 2, "constraints": {},
            "places": [_place("bc", "북촌한옥마을", 37.5826, 126.9836), _place("is", "인사동", 37.5740, 126.9850)],
            "items": list(items)}
    response = api["client"].post("/v1/web/trips", json=body, headers=_h(key))
    assert response.status_code == 201, response.text
    return response.json()


def test_a_booking_without_a_number_is_kept_when_reopened_and_after_a_time_change(api):
    """`[2026-10-14 ST4F-491]` 「예약 완료」라고만 적어 등록한 일정(예약번호 없음)을 다시 열면 예약 표시가 빠졌다."""
    key = _user(api)
    booked = {**_item(1, "activity", "북촌한옥마을", "bc", TOMORROW, "10:00", "11:30"), "detail": {"booking": {"declared_by": "customer_plan"}}}
    trip = _small_trip(api, key, booked, _item(2, "activity", "인사동", "is", TOMORROW, "14:00", "15:30"))
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    by_title = {i["title"]: i for i in view["review"]["items"]}
    assert by_title["북촌한옥마을"]["booked"] is True and by_title["인사동"]["booked"] is None      # 예약 줄 · 자동 추천 제외가 다시 선다
    source = view["sources"][0]["source_id"]
    view = _edit(api, key, view, {"source_id": source, "field": f"items[{_index(view, '북촌한옥마을')}].starts_at", "value": "10:30"})
    done = _confirm(api, key, view)
    assert done["changed"] is True
    after = {i.title: i for i in _stored(api, trip["trip_id"])[1] if i.kind != "mobility"}
    assert after["북촌한옥마을"].starts_at == datetime.fromisoformat(_at(TOMORROW, "10:30"))
    assert after["북촌한옥마을"].detail["booking"] == {"declared_by": "customer_plan"}          # 시각만 고쳐도 예약 표시가 남는다
    assert "booking" not in after["인사동"].detail


def test_an_item_past_midnight_is_frozen_so_done_is_not_refused(api):
    """`[2026-10-14 ST4F-491]` 23:00 → 다음 날 01:00 일정이 있으면 「완료」가 항상 422(time_order)였다 — 고정 일정으로 둔다."""
    key = _user(api)
    next_day = (NOW + timedelta(days=2)).date().isoformat()
    overnight = {**_item(2, "activity", "인사동", "is", TOMORROW, "23:00", "23:30"), "ends_at": _at(next_day, "01:00")}
    trip = _small_trip(api, key, _item(1, "activity", "북촌한옥마을", "bc", TOMORROW, "10:00", "11:30"), overnight)
    view = _reopen(api, key, trip["trip_id"], trip["version"])
    _, items = _stored(api, trip["trip_id"])
    by_title = {i.title: str(i.item_id) for i in items}
    assert view["reopen"]["frozen_item_ids"] == [by_title["인사동"]]
    assert [i["fields"]["title"]["value"] for i in view["sources"][0]["items"]] == ["북촌한옥마을"]
    source = view["sources"][0]["source_id"]
    view = _edit(api, key, view, {"source_id": source, "field": f"items[{_index(view, '북촌한옥마을')}].starts_at", "value": "10:30"})
    assert view["check"]["ready"] is True, view["check"]["problems"]
    done = _confirm(api, key, view)
    assert done["changed"] is True and done["version"] == trip["version"] + 1
    kept = next(i for i in _stored(api, trip["trip_id"])[1] if i.title == "인사동")
    assert str(kept.item_id) == by_title["인사동"]                                          # 고정 일정은 같은 id 그대로
