# -*- coding: utf-8 -*-
"""재난 뒤 **다시 시작** — 상황 꾸러미 · 선택 기록 · 대체 후보 제안. `[결정 2026-10-06 사용자]`

구현: `components/watch/safety_recovery.py` · 입구 `GET|POST /v1/web/trips/{id}/safety/recovery`(+ 다시 시작 응답의 `recovery`) · MCP `tripilot_get_recovery_brief`
기록: `user_activity_events`(마이그레이션 054 · `components/itinerary/activity_log.py`)

★지키려는 것
 ①재난문자가 **구를 지정**하면 그 구 안 = 확정 · 밖 = 없음 · 구를 모르면 불명. 문자에 구가 없거나 지진이면 **전부 불명**(범위를 지어내지 않는다)
 ②다른 도시의 같은 이름 구(부산 강서구)를 서울로 읽지 않는다
 ③다시 시작해야 꾸러미가 생긴다 — 정지가 없거나 아직 풀리지 않았으면 `null`. 사용자가 고른 것은 **기록**되고 꾸러미에 다시 보인다
 ④고르는 것만 기록한다 — 「영향받은 것만 바꾸기」는 **제안만** 만들고 일정은 안 바뀐다(제안을 고르기 전까지 그대로)
 ⑤밀도는 우리가 임의로 낮추지 않는다 — 「오늘은 가볍게」는 기록과 제약 전달뿐이다
 ⑥대체 후보에서 피해 구의 곳은 빠지고, 구를 모르는 후보는 「구를 확인하지 못했어요」가 붙은 채 남는다
 ⑦남의 여행 · 다시 시작한 적 없는 정지는 404 · 여행을 지우면 활동 기록도 지워진다

재현:

    python -m pytest tests/e2e/test_safety_recovery.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.planning.safety import SafetyRules, classify as classify_event
from app.domains.travel_ops.components.watch import safety_pause, safety_recovery
from app.domains.travel_ops.components.watch.safety_pause import SafetyPauses
from app.infrastructure.db.session import get_connection

from .test_guest_and_trip_delete import _count, _delete, _make_trip
from .test_safety_pause import _quake, _war
from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다(`cookies` 가 이것을 쓴다)
from .test_web_cookie_session import WEB, _guest, cookies  # noqa: F401

RULES = SafetyRules.from_guardrails()
TEXT = "[행정안전부] 서울 강남구 · 송파구 지역에 공습경보가 발령되었습니다. 가까운 지하 대피시설로 즉시 대피하세요."
#: 지금부터 30일 뒤 오전 10시(한국) — 비로그인 여행은 오늘부터 365일 안이어야 하고, 지금 시각 기준으로 아직 안 끝난 항목이어야 한다
FUTURE = (datetime.now(timezone(timedelta(hours=9))) + timedelta(days=30)).replace(hour=10, minute=0, second=0, microsecond=0)


# ── ① ② 구 읽기 · 영향 판정 (DB 없이) ─────────────────────────────
def test_districts_are_read_in_order_without_duplicates():
    assert safety_recovery.districts_in(TEXT) == ["강남구", "송파구"]
    assert safety_recovery.districts_in("서울 마포구 호우, 마포구와 서대문구 통제") == ["마포구", "서대문구"]
    assert safety_recovery.districts_in("호우 안전 안내") == [] and safety_recovery.districts_in(None) == []


def test_a_district_name_of_another_city_is_not_read_as_seoul():
    assert safety_recovery.districts_in("부산 강서구 호우 대피") == []                    # 서울에도 강서구가 있다 — 서울이 안 적혔으면 읽지 않는다
    assert safety_recovery.districts_in("서울과 부산 모두 경보, 강서구") == ["강서구"]         # 서울이 적혔으면 읽는다


def _item(title, district, *, hours_ahead=3, kind="activity", with_place=True, now=FUTURE):
    place = {"place_id": str(uuid4()), "name": title, "attributes": ({"district": district} if district else {})} if with_place else None
    start = now + timedelta(hours=hours_ahead)
    return Item(item_id=uuid4(), seq=1, kind=kind, title=title, place_id=None, starts_at=start, ends_at=start + timedelta(hours=1), place=place)


def test_items_are_sorted_into_affected_unknown_and_unaffected_by_the_named_districts():
    event = {"category": "disaster_msg", "text": TEXT, "label": "공습경보"}
    items = [_item("강남 전시", "강남구"), _item("마포 식당", "마포구", kind="dining"), _item("구를 모르는 곳", None),
             _item("이미 끝난 일정", "강남구", hours_ahead=-5), _item("이동", None, kind="mobility", with_place=False)]
    districts, rows = safety_recovery.classify(event, items, now=FUTURE)
    assert districts == ["강남구", "송파구"]
    by_title = {r["title"]: r for r in rows}
    assert set(by_title) == {"강남 전시", "마포 식당", "구를 모르는 곳"}                       # 끝난 일정 · 이동 항목은 판정하지 않는다
    assert by_title["강남 전시"]["status"] == "affected" and "강남구" in by_title["강남 전시"]["reason"]
    assert by_title["마포 식당"]["status"] == "unaffected" and "강남구, 송파구" in by_title["마포 식당"]["reason"]
    assert by_title["구를 모르는 곳"]["status"] == "unknown"                                    # 모르면 불명 — 없음으로 처리하지 않는다


def test_an_earthquake_or_a_text_without_districts_leaves_everything_unknown():
    items = [_item("강남 전시", "강남구"), _item("마포 식당", "마포구")]
    for event in ({"category": "earthquake", "text": "서울 강남구 인근 규모 5.1", "label": "규모 5.1 지진"},
                  {"category": "disaster_msg", "text": "[행정안전부] 호우 안전 안내", "label": "호우"}):
        _, rows = safety_recovery.classify(event, items, now=FUTURE)
        assert {r["status"] for r in rows} == {"unknown"}, event
    assert "점검 공지" in safety_recovery.classify({"category": "earthquake", "text": None, "label": "지진"}, items, now=FUTURE)[1][0]["reason"]


# ── ⑥ 대체 후보 거르기 ────────────────────────────────────────────
def test_the_filter_drops_candidates_in_the_affected_area_and_marks_the_unknown_ones():
    keep = safety_recovery.make_district_filter(get_connection, "t", ["강남구"])
    options = [{"key": "a", "name": "강남 후보", "place_id": None, "catalog_place": {"attributes": {"district": "강남구"}}},
               {"key": "b", "name": "마포 후보", "place_id": None, "catalog_place": {"attributes": {"district": "마포구"}}},
               {"key": "c", "name": "구를 모르는 후보", "place_id": None}]
    kept = {o["name"]: o for o in keep(options)}
    assert set(kept) == {"마포 후보", "구를 모르는 후보"}
    assert kept["마포 후보"]["note"] is None and kept["구를 모르는 후보"]["note"] == "이 곳의 구를 확인하지 못했어요"


# ── ③ ④ ⑤ ⑦ 웹 입구 ───────────────────────────────────────────────
def _web(cookies):
    _guest(cookies)
    client = cookies["client"]
    csrf = client.get("/v1/web/auth/me").json()["csrf_token"]
    return client, {"Origin": WEB, "X-CSRF-Token": csrf}


def _future_trip(cookies):
    """30일 뒤 장소 셋(강남구 · 마포구 · 구를 모름) — 지금 시각 기준으로 아직 안 끝난 항목이다."""
    spots = [("강남 전시", 37.4979, 127.0276, "강남구"), ("마포 식당", 37.5563, 126.9236, "마포구"), ("구를 모르는 곳", 37.55, 126.98, None)]
    places = [{"key": f"p{n}", "name": name, "kind": "activity", "lat": lat, "lon": lon, "weather_sensitive": False,
               "attributes": ({"district": district} if district else {})} for n, (name, lat, lon, district) in enumerate(spots)]
    items = [{"seq": n + 1, "kind": "activity", "title": name, "place": f"p{n}", "route": None,
              "starts_at": (FUTURE + timedelta(hours=3 * n)).isoformat(), "ends_at": (FUTURE + timedelta(hours=3 * n, minutes=50)).isoformat(),
              "detail": {}} for n, (name, *_rest) in enumerate(spots)]
    status, trip = _make_trip(cookies, places=places, items=items, routes={})
    assert status == 201, trip
    return UUID(trip["trip_id"])


def _stop(cookies, trip_id, text=TEXT):
    event = classify_event([_war(text=text)], RULES)
    with get_connection() as conn, conn.transaction():
        pause_id = SafetyPauses(cookies["tenant"]).open(conn, trip_id=trip_id, event=event, day=None, from_at=datetime.now(safety_pause.KST), until_at=None,
                                                         guidance={"level": "trip", "label": event.label, "phase": "in_progress"})
    assert pause_id is not None
    return pause_id


def test_resuming_returns_the_brief_and_it_is_empty_before_resuming(cookies):
    client, headers = _web(cookies)
    trip_id = _future_trip(cookies)
    assert client.get(f"/v1/web/trips/{trip_id}/safety/recovery").json() == {"recovery": None}        # 정지가 없다
    pause_id = _stop(cookies, trip_id)
    assert client.get(f"/v1/web/trips/{trip_id}/safety/recovery").json() == {"recovery": None}        # 아직 멈춰 있다 — 다시 시작해야 생긴다
    answer = client.post(f"/v1/web/trips/{trip_id}/safety/resume", headers=headers).json()
    brief = answer["recovery"]
    assert answer["resumed"] == 1 and brief["pause_id"] == str(pause_id) and brief["phase"] == "in_progress"
    assert brief["affected_districts"] == ["강남구", "송파구"] and brief["counts"] == {"affected": 1, "unknown": 1, "unaffected": 1}
    assert [o["key"] for o in brief["options"]] == ["keep", "replace_affected", "replan_all"]
    assert [o["key"] for o in brief["options"] if o.get("recommended")] == ["replace_affected"]
    assert any("긴급재난문자" in fact for fact in brief["facts"]) and any("범위" in u or "상태는 우리가 알 수 없어요" in u for u in brief["unknowns"])
    assert brief["constraints"]["avoid_districts"] == ["강남구", "송파구"] and brief["constraints"]["lighter_day"] is False
    assert brief["chosen"] is None and "업체 예약" in brief["scope_note"]
    assert client.get(f"/v1/web/trips/{trip_id}/safety/recovery").json()["recovery"]["pause_id"] == str(pause_id)


def test_a_choice_is_recorded_shown_again_and_never_changes_the_density(cookies):
    client, headers = _web(cookies)
    trip_id = _future_trip(cookies)
    pause_id = _stop(cookies, trip_id)
    client.post(f"/v1/web/trips/{trip_id}/safety/resume", headers=headers)
    version = client.get(f"/v1/web/trips/{trip_id}").json()["version"]
    before = _count("SELECT count(*) FROM user_activity_events WHERE trip_id=%s AND kind='safety_recovery_choice'", trip_id)
    sent = client.post(f"/v1/web/trips/{trip_id}/safety/recovery", headers=headers,
                       json={"pause_id": str(pause_id), "choice": "keep", "lighter_day": True, "answers": {"lodging": "yes", "companions": "no"}})
    assert sent.status_code == 200 and sent.json() == {"recorded": True, "choice": "keep", "lighter_day": True, "proposals": []}
    assert _count("SELECT count(*) FROM user_activity_events WHERE trip_id=%s AND kind='safety_recovery_choice'", trip_id) == before + 1
    shown = client.get(f"/v1/web/trips/{trip_id}/safety/recovery").json()["recovery"]
    assert shown["chosen"]["choice"] == "keep" and shown["chosen"]["answers"] == {"lodging": "yes", "companions": "no"}
    assert shown["constraints"]["lighter_day"] is True                                              # 사용자가 고른 것만 제약이 된다
    assert client.get(f"/v1/web/trips/{trip_id}").json()["version"] == version                       # 일정은 안 바뀐다


def test_replacing_the_affected_only_proposes_and_leaves_the_itinerary_alone(cookies):
    client, headers = _web(cookies)
    trip_id = _future_trip(cookies)
    pause_id = _stop(cookies, trip_id)
    client.post(f"/v1/web/trips/{trip_id}/safety/resume", headers=headers)
    version = client.get(f"/v1/web/trips/{trip_id}").json()["version"]
    answer = client.post(f"/v1/web/trips/{trip_id}/safety/recovery", headers=headers, json={"pause_id": str(pause_id), "choice": "replace_affected"})
    assert answer.status_code == 200 and answer.json()["recorded"] is True
    proposals = answer.json()["proposals"]
    assert [p["title"] for p in proposals] == ["강남 전시"]                                           # 영향 확정 항목만 — 불명 · 없음은 건드리지 않는다
    # 후보가 실제로 있는지는 개발 DB 의 장소 목록에 달려 있다 — 여기서는 「영향 확정 항목에만 요청했고 일정은 그대로」만 고정하고, 요청 방식은 아래 시험이 가짜 창구로 본다
    assert proposals[0]["status"] in {"asked", "no_alternate", "no_option_outside_area"}
    assert (proposals[0]["proposal_id"] is not None) == (proposals[0]["status"] == "asked")
    assert client.get(f"/v1/web/trips/{trip_id}").json()["version"] == version                       # 제안만 만들었다 — 고르기 전까지 그대로다


def test_an_unknown_pause_or_someone_elses_trip_is_not_found(cookies):
    client, headers = _web(cookies)
    trip_id = _future_trip(cookies)
    pause_id = _stop(cookies, trip_id)
    body = {"pause_id": str(pause_id), "choice": "keep"}
    assert client.post(f"/v1/web/trips/{trip_id}/safety/recovery", headers=headers, json=body).status_code == 404     # 아직 안 풀었다
    client.post(f"/v1/web/trips/{trip_id}/safety/resume", headers=headers)
    assert client.post(f"/v1/web/trips/{trip_id}/safety/recovery", headers=headers, json={**body, "pause_id": str(uuid4())}).status_code == 404
    assert client.post(f"/v1/web/trips/{trip_id}/safety/recovery", headers=headers, json={**body, "choice": "delete_all"}).status_code == 422
    assert TestClient(client.app, follow_redirects=False).get(f"/v1/web/trips/{trip_id}/safety/recovery").status_code == 401
    other = {**cookies, "client": TestClient(client.app, follow_redirects=False), "ip": "10.9.2.8"}
    _guest(other)
    csrf = other["client"].get("/v1/web/auth/me").json()["csrf_token"]
    assert other["client"].get(f"/v1/web/trips/{trip_id}/safety/recovery").status_code == 404                                     # 남의 여행 = 없는 여행
    assert other["client"].post(f"/v1/web/trips/{trip_id}/safety/recovery", json=body, headers={"Origin": WEB, "X-CSRF-Token": csrf}).status_code == 404


def test_an_earthquake_brief_has_no_confirmed_item_and_the_event_text_is_shown(cookies):
    client, headers = _web(cookies)
    trip_id = _future_trip(cookies)
    event = classify_event([_quake(5.4)], RULES)
    with get_connection() as conn, conn.transaction():
        SafetyPauses(cookies["tenant"]).open(conn, trip_id=trip_id, event=event, day=datetime.now(safety_pause.KST).date(), from_at=datetime.now(safety_pause.KST), until_at=None,
                       guidance={"level": "day", "label": event.label, "phase": "in_progress"})
    brief = client.post(f"/v1/web/trips/{trip_id}/safety/resume", headers=headers).json()["recovery"]
    assert brief["counts"] == {"affected": 0, "unknown": 3, "unaffected": 0} and brief["affected_districts"] == []
    assert any("기상청 지진정보" in fact for fact in brief["facts"])
    assert "영향이 확정된 곳이 없어요" in [o for o in brief["options"] if o["key"] == "replace_affected"][0]["detail"]


def test_deleting_the_trip_deletes_its_activity_records(cookies):
    client, headers = _web(cookies)
    trip_id = _future_trip(cookies)
    pause_id = _stop(cookies, trip_id)
    client.post(f"/v1/web/trips/{trip_id}/safety/resume", headers=headers)
    client.post(f"/v1/web/trips/{trip_id}/safety/recovery", headers=headers, json={"pause_id": str(pause_id), "choice": "keep"})
    assert _count("SELECT count(*) FROM user_activity_events WHERE trip_id=%s", trip_id) == 1
    assert _delete(cookies, trip_id).status_code == 200
    assert _count("SELECT count(*) FROM user_activity_events WHERE trip_id=%s", trip_id) == 0


def test_suggestions_are_requested_only_for_confirmed_items_with_the_area_filter():
    """가짜 창구로 요청 방식을 본다 — 영향 **확정** 항목에만 · 같은 요청 번호는 같은 값 · 피해 구를 거르는 함수를 같이 넘긴다."""
    class Desk:
        def __init__(self):
            self.calls = []

        def propose_alternatives(self, **kwargs):
            self.calls.append(kwargs)
            return {"status": "asked", "proposal_id": "p-1", "options": [{"name": "마포 후보"}, {"name": "서대문 후보"}]}

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class Store:
        def latest(self, conn, trip_id):
            return {"version": 7}, []

    brief = {"pause_id": "pause-1", "affected_districts": ["강남구"],
             "items": [{"item_id": str(uuid4()), "title": "강남 전시", "status": "affected"},
                       {"item_id": str(uuid4()), "title": "구를 모르는 곳", "status": "unknown"},
                       {"item_id": str(uuid4()), "title": "마포 식당", "status": "unaffected"}]}
    desk, trip_id = Desk(), uuid4()
    out = safety_recovery.suggest_replacements(desk, Store(), tenant_id="t", trip_id=trip_id, brief=brief, conn_factory=Connection)
    assert len(desk.calls) == 1 and str(desk.calls[0]["item_id"]) == brief["items"][0]["item_id"]            # 확정 항목 하나에만
    call = desk.calls[0]
    assert call["base_version"] == 7 and call["request_id"] == f"recovery:pause-1:{brief['items'][0]['item_id']}" and callable(call["keep"])
    assert out == [{"item_id": brief["items"][0]["item_id"], "title": "강남 전시", "status": "asked", "proposal_id": "p-1",
                    "options": ["마포 후보", "서대문 후보"]}]
