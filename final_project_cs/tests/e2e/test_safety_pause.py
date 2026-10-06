# -*- coding: utf-8 -*-
"""재난 시 **일정 정지 · 피난 안내 · 다시 시작**. `[결정 2026-10-06 사용자]`

계약: `wiki/external/rest-endpoints.md` 「재난 시 일정 정지」 · 설계 `wiki/records/plans/2026-10-06_재난_일정정지와_피난안내_설계.md`
구현: `components/planning/safety.py`(분류) · `components/watch/safety_pause.py`(정지 · 알림 · 해제) · `components/places/shelters.py`(대피 장소) · `TripStore._open_trips`(감시에서 빼기) · `052_safety_pause_and_shelters.sql`

★지키려는 것
 ①재난이 난 시각에 그 지역에 여행객이 있었다면(오늘이 여행 기간 + 일정에 적힌 장소에서 사건이 점검됨) **그날 일정이 정지**된다. 자정이 지나면 풀린다
 ②전쟁 · 화산 폭발 같은 심각한 사건은 **여행 전체**가 정지되고 사용자가 다시 시작할 때까지 간다
 ③정지한 여행은 **감시 · 안내에서 빠진다**(`due` · `active_trip_ids` · 감시 한 틱) — 정지한 일정에 「곧 시작해요」 · 대체 장소 교체가 나가면 안 된다
 ④안전 알림은 **안전을 앞세우고**(공식 안내 · 119) 재난문자 원문과 **표에 있는** 가까운 대피 장소(거리 · 걷는 시간 추정 · 자료 출처)를 싣는다. 표가 비었거나 근처에 없으면 지어내지 않고 그렇게 말한다
 ⑤같은 사건으로 두 번 정지하거나 알리지 않는다 — 사용자가 다시 시작한 뒤에도
 ⑥조회가 실패하면(`fatal`) 정지하지 않는다 · 일정에 장소 좌표가 없으면 정지하지 않고 센다 · 어제 난 사건은 오늘을 멈추지 않는다
 ⑦공식 해제가 오면 「해제됐어요」를 **한 번** 알린다 — 다시 시작은 사용자가 정한다
 ⑧다시 시작(`POST …/safety/resume`)은 본인 여행만 · 남의 것 404 · 일정은 안 바뀐다 · 여행 조회의 `safety` · `items[].paused`

재현:

    python -m pytest tests/e2e/test_safety_pause.py -v
"""
from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.places import shelters
from app.domains.travel_ops.components.planning.safety import SafetyRules, classify
from app.domains.travel_ops.components.watch import safety_pause
from app.domains.travel_ops.components.watch.safety_pause import SafetyPauses, SafetySweep

from .test_guest_and_trip_delete import _make_trip
from .test_trip_api import _at, _body, _iso, api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_cookie_session import WEB, _guest, cookies  # noqa: F401

SOURCE = "시험용 자료(실제 아님)"
#: 서해 한가운데 — 실제 대피 장소 자료를 적재해 둔 개발 DB 에서도 시험의 가까운 곳이 섞이지 않는다
SEA = (34.5, 125.0)
RULES = SafetyRules.from_guardrails()


def _quake(magnitude=5.1, hhmm="10:05"):
    return {"category": "earthquake", "magnitude": magnitude, "distance_km": 12.0, "location": "서해 시험 해역", "at": _iso(hhmm), "kind": f"규모 {magnitude} 지진"}


def _war(hhmm="10:07", text="[행정안전부] 오늘 서울에 공습경보가 발령되었습니다. 가까운 지하 대피시설로 즉시 대피하세요."):
    return {"category": "disaster_msg", "kind": "민방위", "step": "위급재난", "text": text, "created_at": _iso(hhmm)}


def _report(*causes, verdict=None):
    return {"verdict": verdict or ("disrupted" if causes else "clear"), "disruptions": list(causes), "failed_categories": []}


class FakeCheck:
    """점검 흉내 — 부른 장소 · 시각을 남기고, 정해 둔 보고를 준다."""

    def __init__(self, report):
        self.report, self.calls = report, []

    def __call__(self, *, place, starts_at, region="서울"):
        self.calls.append({"place": place, "at": starts_at, "region": region})
        return self.report


def _trip(api, items=2, **override):
    """서해 한가운데 장소 하나에 활동 `items` 개(10:00~, 한 시간씩). 에이전트 입구로 등록한다."""
    places = [{"key": "p1", "name": "시험 장소", "kind": "activity", "lat": SEA[0], "lon": SEA[1], "weather_sensitive": False, "attributes": {}}]
    rows = [{"seq": n + 1, "kind": "activity", "title": f"시험 활동 {n + 1}", "place": "p1", "route": None,
             "starts_at": _iso(f"{10 + n}:00"), "ends_at": _iso(f"{10 + n}:50"), "detail": {}} for n in range(items)]
    body = _body(api["customer"], f"safety-{uuid4().hex[:10]}", places=places, items=rows, routes={}, **override)
    response = api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write"))
    assert response.status_code == 201, response.text
    return UUID(response.json()["trip_id"])


@pytest.fixture()
def near(api):
    """서해 장소 근처의 시험용 대피 장소 — 끝나면 지운다(자료 표는 테넌트 밖이라 시험이 만든 줄만 지운다)."""
    def clean():
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM safety_shelters WHERE source = %s", (SOURCE,))

    clean()
    rows = [("quake_outdoor", "시험 옥외대피장소 가", SEA[0] + 0.0010, SEA[1], None, 3000),      # ≈ 111 m
            ("quake_outdoor", "시험 옥외대피장소 나", SEA[0] + 0.0100, SEA[1], None, 1000),      # ≈ 1.1 km
            ("quake_outdoor", "시험 옥외대피장소 멀리", SEA[0] + 0.2000, SEA[1], None, 1000),    # ≈ 22 km — 반경 밖
            ("civil_defense", "시험 민방위대피소 가", SEA[0], SEA[1] + 0.0020, True, 400),       # ≈ 183 m
            ("civil_defense", "시험 민방위대피소 나", SEA[0], SEA[1] + 0.0300, False, 200)]       # ≈ 2.7 km
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for kind, name, lat, lon, ground, capacity in rows:
            cur.execute("INSERT INTO safety_shelters (shelter_type, name, address, latitude, longitude, underground, capacity, source) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (kind, name, "시험 주소", lat, lon, ground, capacity, SOURCE))
    yield
    clean()


def _sweep(api, check, when="10:30", release=None):
    return SafetySweep(store=api["store"], check=check, release=release, connection_factory=get_connection, clock=lambda: _at(when), rules=RULES)


def _notices(api, kind=None):
    return [(key, payload) for key, payload in api["notices"]() if kind is None or payload.get("kind") == kind]


def _pauses(trip_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT level, resumed_at IS NOT NULL, until_at FROM trip_safety_pauses WHERE trip_id=%s ORDER BY seq", (trip_id,))
        return cur.fetchall()


def _watched(api, trip_id, when):
    """감시 · 안내 반복이 이 여행을 보나 — (`active_trip_ids`, `due` 90분)."""
    with get_connection() as conn:
        ids = api["store"].active_trip_ids(conn, _at(when))
        due = api["store"].due(conn, start=_at(when), end=_at(when) + timedelta(minutes=90))
    return trip_id in ids, any(t == trip_id for t, _ in due)


# ── ① 그날 정지 ───────────────────────────────────────────────────
def test_an_earthquake_stops_the_rest_of_that_day_and_the_watchers_skip_it(api, near):
    trip_id = _trip(api)
    assert _watched(api, trip_id, "10:30") == (True, True)                                    # 정지 전에는 감시 대상(11:00 항목이 곧 시작)
    check = FakeCheck(_report(_quake(5.1)))
    result = _sweep(api, check).tick()
    assert result.counts() == {"trips": 1, "upcoming": 0, "checked": 1, "opened": 1, "already": 0, "no_place": 0, "fatal": 0, "released": 0}
    assert result.opened[0]["level"] == "day" and result.opened[0]["shelter_status"] == "ok"
    assert [c["region"] for c in check.calls] == ["서울"] and check.calls[0]["place"]["name"] == "시험 장소"      # 일정에 적힌 장소에서 점검했다
    [(level, resumed, until)] = _pauses(trip_id)
    assert level == "day" and resumed is False and until == _at("10:30").replace(hour=0, minute=0) + timedelta(days=1)   # 그날 자정(KST)
    assert _watched(api, trip_id, "10:30") == (False, False)                                    # ③감시 · 안내가 이 여행을 건너뛴다
    assert _watched(api, trip_id, "23:59") == (False, False)
    next_morning = _at("09:00") + timedelta(days=1)
    with get_connection() as conn:
        assert trip_id in api["store"].active_trip_ids(conn, next_morning)                      # 자정이 지나면 풀린다(내일 일정은 그대로 이어진다)


def test_the_safety_notice_leads_with_safety_and_lists_nearby_shelters_from_the_table(api, near):
    _trip(api)
    _sweep(api, FakeCheck(_report(_quake(5.1)))).tick()
    [(key, payload)] = _notices(api, "safety_pause_day")
    assert key.endswith(f"safety:{payload['pause_id']}") and payload["type"] == "safety_alert" and payload["safety"] is True
    text = payload["text"]
    lines = text.splitlines()
    assert lines[0] == "⚠️ 안전 알림 — 규모 5.1 지진. 오늘 남은 일정을 정지했어요(일정은 지우지 않았어요)."
    assert "안전이 먼저예요" in lines[1] and "119" in lines[1] and "국민재난안전포털" in lines[1]            # 안전이 앞이다
    guidance = payload["guidance"]
    assert [s["name"] for s in guidance["shelters"]] == ["시험 옥외대피장소 가", "시험 옥외대피장소 나"]      # 가까운 순 · 반경(5 km) 밖은 안 나온다 · 민방위는 지진에 안 나온다
    assert guidance["shelters"][0]["distance_m"] in range(105, 118) and guidance["shelters"][0]["walk_minutes_estimate"] == 2   # 111 m ÷ 4 km/h → 2분(추정)
    assert guidance["shelter_status"] == "ok" and guidance["shelter_source"] == [SOURCE] and guidance["emergency_call"] == "119"
    assert "1) 시험 옥외대피장소 가 — 시험 주소 · 약 1" in text and "걷는 시간은 추정이에요" in text and f"자료: {SOURCE}" in text
    first = guidance["shelters"][0]
    assert first["map_url"].startswith("https://www.google.com/maps/dir/?api=1&origin=34.5%2C125.0&destination=34.501%2C125.0&travelmode=walking")
    assert f"   길찾기(걸어서): {first['map_url']}" in lines                                          # 안전을 위한 이동 — 지도 앱이 길을 안내한다(서버가 길을 계산하지 않는다)
    assert "일정에 적힌 장소 시험 장소 기준" in text and "지금 계신 곳과" in guidance["reference"]["note"]    # 실제 위치가 아니라는 것을 밝힌다
    assert lines[-1].startswith("상황이 정리되면 웹에서 「일정 다시 시작」을") and "내일 일정은 그대로 이어져요" in lines[-1]


def test_the_same_event_does_not_stop_or_notify_twice(api, near):
    _trip(api)
    sweep = _sweep(api, FakeCheck(_report(_quake(5.1))))
    assert sweep.tick().counts()["opened"] == 1
    again = sweep.tick()
    assert again.counts()["opened"] == 0 and again.counts()["checked"] == 1              # 점검은 다시 한다(여행 전체로 올려야 하는 사건이 올 수 있다) — 같은 날 정지는 또 안 건다
    assert len(_notices(api, "safety_pause_day")) == 1


def test_an_event_from_yesterday_does_not_stop_today(api, near):
    trip_id = _trip(api)
    yesterday = {**_quake(5.1), "at": _iso("10:05").replace("09-23", "09-22")}
    assert _sweep(api, FakeCheck(_report(yesterday))).tick().counts()["opened"] == 0
    assert _pauses(trip_id) == []


# ── ② 여행 전체 정지 ──────────────────────────────────────────────
def test_a_war_alert_stops_the_whole_trip_and_guides_to_civil_defense_shelters(api, near):
    trip_id = _trip(api)
    result = _sweep(api, FakeCheck(_report(_war()))).tick()
    assert result.opened[0]["level"] == "trip"
    [(level, resumed, until)] = _pauses(trip_id)
    assert (level, resumed, until) == ("trip", False, None)                              # 다시 시작할 때까지 — 끝나는 시각이 없다
    [(_, payload)] = _notices(api, "safety_pause_trip")
    assert payload["text"].splitlines()[0] == "⚠️ 안전 알림 — 민방위(위급재난). 여행 일정 전체를 정지했어요(일정은 지우지 않았어요)."
    assert [s["name"] for s in payload["guidance"]["shelters"]] == ["시험 민방위대피소 가", "시험 민방위대피소 나"]   # 지진용 옥외대피장소는 안 나온다
    assert payload["guidance"]["shelters"][0]["underground"] is True and "· 지하" in payload["text"]
    assert "재난문자" in payload["text"] and "지하 대피시설로 즉시 대피하세요" in payload["text"]          # 재난문자 원문(공식 안내)을 그대로 싣는다
    for when in ("10:30", "23:59"):
        assert _watched(api, trip_id, when) == (False, False)
    with get_connection() as conn:
        assert trip_id not in api["store"].active_trip_ids(conn, _at("09:00") + timedelta(days=3))   # 며칠 뒤에도 — 사용자가 다시 시작할 때까지


def test_a_big_earthquake_stops_the_whole_trip_and_a_later_severe_event_upgrades_a_day_stop(api, near):
    trip_id = _trip(api)
    assert _sweep(api, FakeCheck(_report(_quake(6.4)))).tick().opened[0]["level"] == "trip"
    other = _trip(api, items=3)
    _sweep(api, FakeCheck(_report(_quake(4.8)))).tick()                                    # 먼저 그날 정지
    upgraded = _sweep(api, FakeCheck(_report(_war()))).tick()                              # 뒤이어 심각한 사건 — 전체로 올린다
    assert [row[0] for row in _pauses(other)] == ["day", "trip"] and trip_id != other
    assert upgraded.counts()["opened"] == 1


# ── 안내가 지어내지 않는다 ────────────────────────────────────────
def test_with_no_shelter_data_the_notice_says_so_and_does_not_invent(api):
    trip_id = _trip(api)                                                                  # 대피 장소 자료를 적재하지 않은 표(`near` 를 안 썼다)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM safety_shelters WHERE shelter_type='quake_outdoor' AND source <> %s", (SOURCE,))
        if cur.fetchone()[0]:
            pytest.skip("이 개발 DB 에는 실제 대피 장소 자료가 적재돼 있다 — 「자료 없음」 경로는 빈 표에서만 본다")
    _sweep(api, FakeCheck(_report(_quake(5.1)))).tick()
    [(_, payload)] = _notices(api, "safety_pause_day")
    assert payload["guidance"]["shelters"] == [] and payload["guidance"]["shelter_status"] == "no_data"
    assert "가까운 대피 장소 자료를 아직 불러오지 못했어요" in payload["text"] and "1)" not in payload["text"]
    assert _pauses(trip_id)[0][0] == "day"                                                 # 대피 장소가 없어도 정지와 공식 안내는 나간다


def test_when_nothing_is_nearby_the_notice_says_nothing_was_found(api, near):
    _trip(api)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE safety_shelters SET latitude = latitude + 1 WHERE source = %s AND shelter_type='quake_outdoor'", (SOURCE,))
    _sweep(api, FakeCheck(_report(_quake(5.1)))).tick()
    [(_, payload)] = _notices(api, "safety_pause_day")
    assert payload["guidance"]["shelter_status"] == "none_nearby" and payload["guidance"]["shelters"] == []
    assert "5km 안에서 대피 장소를 찾지 못했어요" in payload["text"]


def test_a_fire_is_stopped_with_official_guidance_only_no_shelter_list(api, near):
    _trip(api)
    fire = {"category": "disaster_msg", "kind": "화재", "step": "긴급재난", "text": "남산 일대 대형 화재가 발생했습니다.", "created_at": _iso("10:10")}
    _sweep(api, FakeCheck(_report(fire))).tick()
    [(_, payload)] = _notices(api, "safety_pause_day")
    assert payload["guidance"]["shelter_status"] == "not_applicable" and "대피 장소" not in payload["text"] and "남산 일대 대형 화재" in payload["text"]


# ── 정지하지 않는 경우 ────────────────────────────────────────────
def test_a_failed_check_never_stops_anything(api, near):
    trip_id = _trip(api)
    result = _sweep(api, FakeCheck({"verdict": "fatal", "disruptions": [_quake(7.0)], "failed_categories": ["disaster_msg"]})).tick()
    assert result.counts()["opened"] == 0 and len(result.fatal) == 1 and _pauses(trip_id) == []      # 조회 실패를 정지 사유로 쓰지 않는다(결정 15)


def test_ordinary_messages_and_a_clear_check_stop_nothing(api, near):
    trip_id = _trip(api)
    everyday = [{"category": "disaster_msg", "kind": "호우", "step": "긴급재난", "text": "호우경보", "created_at": _iso("10:01")},
                {"category": "disaster_msg", "kind": "기타", "step": "안전안내", "text": "실종자를 찾습니다", "created_at": _iso("10:02")}]
    assert _sweep(api, FakeCheck(_report(*everyday))).tick().counts()["opened"] == 0
    assert _sweep(api, FakeCheck(_report())).tick().counts()["opened"] == 0 and _pauses(trip_id) == []


def test_a_trip_outside_its_dates_is_not_swept(api, near):
    _trip(api)
    outside = _sweep(api, FakeCheck(_report(_quake(5.1))), when="10:30")
    outside.clock = lambda: _at("10:30") + timedelta(days=2)                                 # 여행이 끝난 뒤 — 오늘이 여행 기간이 아니다
    assert outside.tick().counts()["trips"] == 0


# ── 아직 시작하지 않은 여행 ───────────────────────────────────────
def _two_days_before(api, check, release=None):
    sweep = _sweep(api, check, release=release)
    sweep.clock = lambda: _at("10:30") - timedelta(days=2)                                   # 여행은 이틀 뒤에 시작한다
    return sweep


def test_a_trip_that_has_not_started_is_stopped_by_a_severe_event_until_the_user_resumes(api, near):
    """`[결정 2026-10-06 사용자]` 시작 전 여행도 심각한 사건이면 멈춘다 — 가기 전에 현지 상황을 모른다. 대피 장소는 안내하지 않는다(그곳에 있는 사람이 아니다)."""
    trip_id = _trip(api)
    sweep = _two_days_before(api, FakeCheck(_report(_war())))
    result = sweep.tick()
    assert result.counts()["upcoming"] == 1 and result.counts()["opened"] == 1
    assert result.opened[0]["level"] == "trip" and result.opened[0]["phase"] == "upcoming"
    assert _pauses(trip_id) == [("trip", False, None)]                                       # 기한 없음 — 사용자가 다시 시작할 때까지
    [(_, payload)] = _notices(api, "safety_pause_trip")
    guidance = payload["guidance"]
    assert guidance["phase"] == "upcoming" and guidance["shelters"] == [] and guidance["shelter_status"] == "not_applicable"
    assert "아직 시작하지 않은 여행" in payload["text"] and "공식 안내" in payload["text"] and "일정 다시 시작" in payload["text"]
    assert "대피 장소" not in payload["text"] and "길찾기" not in payload["text"]
    # 여행이 시작하는 날이 와도 사용자가 풀지 않았으면 계속 멈춰 있다 — 감시 · 안내가 건너뛴다
    assert _watched(api, trip_id, "10:30") == (False, False)
    with get_connection() as conn, conn.transaction():
        assert SafetyPauses(api["tenant"]).resume(conn, trip_id=trip_id, via="web", by=api["customer"], now=_at("10:30")) == 1
    assert _watched(api, trip_id, "10:30") == (True, True)
    assert sweep.tick().counts()["already"] == 1 and len(_notices(api, "safety_pause_trip")) == 1     # 같은 사건으로 다시 멈추지 않는다


def test_a_day_level_event_does_not_stop_a_trip_that_has_not_started(api, near):
    """「그날 정지」는 오늘 그곳에 있는 사람의 일이다 — 이틀 뒤에 시작하는 여행은 멈추지 않는다. 같은 사건이 시작한 날에는 멈춘다."""
    trip_id = _trip(api)
    before = _two_days_before(api, FakeCheck(_report(_quake(5.1))))
    assert before.tick().counts()["opened"] == 0 and _pauses(trip_id) == []
    assert _sweep(api, FakeCheck(_report(_quake(5.1)))).tick().counts()["opened"] == 1      # 시작한 날(10:30)은 그날 정지
    assert [row[0] for row in _pauses(trip_id)] == ["day"]


def test_an_earthquake_of_magnitude_six_stops_a_trip_that_has_not_started(api, near):
    trip_id = _trip(api)
    assert _two_days_before(api, FakeCheck(_report(_quake(6.3)))).tick().counts()["opened"] == 1
    assert _pauses(trip_id) == [("trip", False, None)]


def test_an_upcoming_trip_with_an_ordinary_message_or_a_failed_check_is_not_stopped(api, near):
    trip_id = _trip(api)
    everyday = {"category": "disaster_msg", "kind": "호우", "step": "긴급재난", "text": "호우경보", "created_at": _iso("10:01")}
    assert _two_days_before(api, FakeCheck(_report(everyday))).tick().counts()["opened"] == 0
    failed = {"verdict": "fatal", "disruptions": [_war()], "failed_categories": ["disaster_msg"]}
    assert _two_days_before(api, FakeCheck(failed)).tick().counts()["opened"] == 0
    assert _pauses(trip_id) == []


def test_the_trip_view_tells_an_upcoming_stop_apart(api, near):
    """여행 조회의 `safety.phase` — 웹이 「시작 전 여행이라 멈춤」과 「지금 여행 중이라 멈춤」을 다르게 보인다."""
    trip_id = _trip(api)
    _two_days_before(api, FakeCheck(_report(_war()))).tick()
    with get_connection() as conn:
        shown = safety_pause.view(conn, tenant_id=api["tenant"], trip_id=trip_id, now=_at("10:30"))
    assert shown["paused"] is True and shown["level"] == "trip" and shown["phase"] == "upcoming"
    assert _sweep(api, FakeCheck(_report(_war())), when="10:31").tick().counts()["checked"] == 0       # 이미 여행 전체가 멈춰 있어 다시 점검하지 않는다


def test_the_reference_place_is_the_ongoing_then_next_then_last_item():
    from app.domains.travel_ops.components.itinerary.itinerary import Item
    from uuid import uuid4

    def item(seq, start, end, name, lat=37.5, lon=127.0):
        return Item(item_id=uuid4(), seq=seq, kind="activity", title=f"항목 {seq}", place_id=uuid4(), starts_at=_at(start), ends_at=_at(end),
                    place={"name": name, "latitude": lat, "longitude": lon})

    items = [item(1, "09:00", "09:50", "지난 곳"), item(2, "10:00", "10:50", "진행 중"), item(3, "11:00", "11:50", "다음 곳")]
    assert safety_pause._reference_place(items, _at("10:30"))["name"] == "진행 중"
    assert safety_pause._reference_place(items, _at("10:55"))["name"] == "다음 곳"
    assert safety_pause._reference_place(items, _at("12:30"))["name"] == "다음 곳"            # 오늘 일정이 다 끝났으면 가장 마지막으로 끝난 곳
    assert safety_pause._reference_place([item(1, "09:00", "09:50", "좌표 없음", lat=None)], _at("10:30")) is None


# ── 해제 · 다시 시작 ──────────────────────────────────────────────
def test_an_official_release_is_told_once_and_the_stop_stays_until_the_user_resumes(api, near):
    trip_id = _trip(api)
    _sweep(api, FakeCheck(_report(_war()))).tick()
    release = lambda *, place, since, at: [{"kind": "민방위", "step": "위급재난", "text": "[행정안전부] 서울 공습경보가 해제되었습니다.", "created_at": _iso("11:20")}]
    sweep = _sweep(api, FakeCheck(_report(_war())), when="11:30", release=release)
    first = sweep.tick()
    assert first.counts()["released"] == 1
    [(_, payload)] = _notices(api, "safety_release")
    assert payload["type"] == "guidance" and "해제됐다는 공식 안내가 나왔어요" in payload["text"] and "일정 다시 시작" in payload["text"]
    assert sweep.tick().counts()["released"] == 0 and len(_notices(api, "safety_release")) == 1       # 한 번만
    assert _pauses(trip_id) == [("trip", False, None)]                                     # 해제가 와도 정지는 사용자가 풀 때까지 그대로다


def test_a_release_of_another_kind_of_event_does_not_count(api, near):
    _trip(api)
    _sweep(api, FakeCheck(_report(_war()))).tick()
    other = lambda *, place, since, at: [{"kind": "호우", "step": "안전안내", "text": "호우 통제가 해제되었습니다.", "created_at": _iso("11:20")}]
    assert _sweep(api, FakeCheck(_report(_war())), when="11:30", release=other).tick().counts()["released"] == 0


def test_resuming_closes_the_stop_and_the_same_event_does_not_stop_it_again(api, near):
    trip_id = _trip(api)
    sweep = _sweep(api, FakeCheck(_report(_quake(5.1))))
    sweep.tick()
    with get_connection() as conn, conn.transaction():
        assert SafetyPauses(api["tenant"]).resume(conn, trip_id=trip_id, via="web", by=api["customer"], now=_at("10:30")) == 1
    assert _watched(api, trip_id, "10:30") == (True, True)                                 # 다시 감시 · 안내 대상이 된다
    again = sweep.tick()
    assert again.counts()["opened"] == 0 and again.counts()["already"] == 1               # ⑤같은 사건으로 다시 멈추지 않는다
    assert len(_notices(api, "safety_pause_day")) == 1
    with get_connection() as conn, conn.transaction():
        assert SafetyPauses(api["tenant"]).resume(conn, trip_id=trip_id, via="web", now=_at("10:30")) == 0   # 닫을 것이 없으면 0 — 오류가 아니다


def test_a_new_different_event_after_resuming_stops_it_again(api, near):
    trip_id = _trip(api)
    _sweep(api, FakeCheck(_report(_quake(5.1, "10:05")))).tick()
    with get_connection() as conn, conn.transaction():
        SafetyPauses(api["tenant"]).resume(conn, trip_id=trip_id, via="web", now=_at("10:30"))
    assert _sweep(api, FakeCheck(_report(_quake(5.4, "10:25")))).tick().counts()["opened"] == 1   # 새 사건(규모 · 시각이 다르다)
    assert [row[0] for row in _pauses(trip_id)] == ["day", "day"]


def test_a_paused_trip_is_not_touched_by_the_watcher_tick(api, near):
    """정지한 여행에는 감시 한 틱이 아무것도 안 한다 — 대체 장소 교체 · 알림이 안 나간다."""
    _trip(api)
    _sweep(api, FakeCheck(_report(_war()))).tick()
    before = len(api["notices"]())
    result = api["tick"]("10:30")
    assert result.checked == 0 and result.adjusted == [] and len(api["notices"]()) == before


# ── 여행 조회 · 다시 시작 입구 ────────────────────────────────────
def test_the_trip_view_shows_the_stop_and_marks_the_paused_items(api, near):
    """★여행 전체 정지로 본다 — 그날 정지는 자정에 풀려 시험의 재생 시계(2026-09-23)와 실제 시계가 어긋난다(조회는 실제 시계)."""
    trip_id = _trip(api)
    assert api["client"].get(f"/v1/trips/{trip_id}", headers=api["auth"]("trip:read")).json()["safety"] == {"paused": False}
    _sweep(api, FakeCheck(_report(_war()))).tick()
    view = api["client"].get(f"/v1/trips/{trip_id}", headers=api["auth"]("trip:read")).json()
    safety = view["safety"]
    assert safety["paused"] is True and safety["level"] == "trip" and safety["label"] == "민방위(위급재난)" and safety["released"] is False
    assert safety["resume"] == {"label": "일정 다시 시작", "path": "/safety/resume"} and safety["day"] is None and safety["until"] is None
    assert [item["paused"] for item in view["items"]] == [True, True]                    # 사건(10:07)에 진행 중이던 10:00 항목도, 아직 안 한 11:00 항목도 정지
    with get_connection() as conn, conn.transaction():
        SafetyPauses(api["tenant"]).resume(conn, trip_id=trip_id, via="web")
    after = api["client"].get(f"/v1/trips/{trip_id}", headers=api["auth"]("trip:read")).json()
    assert after["safety"] == {"paused": False} and [item["paused"] for item in after["items"]] == [False, False]


def test_resume_endpoint_is_for_the_owner_only_and_leaves_the_itinerary_alone(cookies):
    _guest(cookies)
    status, trip = _make_trip(cookies)
    assert status == 201
    trip_id, tenant = UUID(trip["trip_id"]), cookies["tenant"]
    client = cookies["client"]
    csrf = client.get("/v1/web/auth/me").json()["csrf_token"]
    headers = {"Origin": WEB, "X-CSRF-Token": csrf}
    event = classify([_quake(5.1)], RULES)
    from datetime import datetime
    with get_connection() as conn, conn.transaction():
        SafetyPauses(tenant).open(conn, trip_id=trip_id, event=event, day=None, from_at=datetime.now(safety_pause.KST), until_at=None,
                                  guidance={"level": "day", "label": event.label})
    paused = client.get(f"/v1/web/trips/{trip_id}").json()["safety"]
    assert paused["paused"] is True
    version_before = client.get(f"/v1/web/trips/{trip_id}").json()["version"]
    response = client.post(f"/v1/web/trips/{trip_id}/safety/resume", headers=headers)
    assert response.status_code == 200 and response.json() == {"resumed": 1, "safety": {"paused": False}}
    assert client.get(f"/v1/web/trips/{trip_id}").json()["version"] == version_before     # 일정은 안 바뀐다
    assert client.post(f"/v1/web/trips/{trip_id}/safety/resume", headers=headers).json()["resumed"] == 0     # 다시 눌러도 오류가 아니다
    from fastapi.testclient import TestClient
    stranger = TestClient(client.app, follow_redirects=False)
    assert stranger.post(f"/v1/web/trips/{trip_id}/safety/resume").status_code == 401
    other = {**cookies, "client": TestClient(client.app, follow_redirects=False), "ip": "10.9.2.7"}
    _guest(other)
    other_csrf = other["client"].get("/v1/web/auth/me").json()["csrf_token"]
    missing = other["client"].post(f"/v1/web/trips/{trip_id}/safety/resume", headers={"Origin": WEB, "X-CSRF-Token": other_csrf})
    assert missing.status_code == 404                                                      # 남의 여행 = 없는 여행


def test_web_notices_carry_the_safety_guidance(cookies):
    _guest(cookies)
    status, trip = _make_trip(cookies)
    trip_id = UUID(trip["trip_id"])
    event = classify([_war()], RULES)
    guidance = {"level": "trip", "label": event.label, "resume": {"label": "일정 다시 시작", "path": "/safety/resume"}, "shelters": []}
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    with get_connection() as conn, conn.transaction():
        TripStore(cookies["tenant"]).enqueue_message(conn, trip_id=trip_id, key="safety:t", payload=safety_pause.notice_payload(guidance | {
            "official": {"source": "행정안전부 긴급재난문자", "text": "공습경보", "at": None}, "emergency_call": "119", "portal": "국민재난안전포털",
            "shelter_status": "not_applicable", "reference": None}, event, trip_id))
    notices = cookies["client"].get(f"/v1/web/trips/{trip_id}/notices").json()["notices"]
    safety = [n for n in notices if n["safety"] is not None]
    assert len(safety) == 1 and safety[0]["type"] == "safety_alert" and safety[0]["safety"]["resume"]["path"] == "/safety/resume"
    assert all(n["safety"] is None for n in notices if n["type"] != "safety_alert")        # 안전 알림이 아니면 칸은 null


# ── 대피 장소 찾기 · 지우기 ───────────────────────────────────────
def test_nearest_is_sorted_by_distance_and_limited_by_radius(api, near):
    with get_connection() as conn:
        found = shelters.nearest(conn, latitude=SEA[0], longitude=SEA[1], types=("quake_outdoor",), limit=5, radius_km=5, speed_kmh=4.0)
        wide = shelters.nearest(conn, latitude=SEA[0], longitude=SEA[1], types=("quake_outdoor",), limit=5, radius_km=30, speed_kmh=4.0)
        assert shelters.has_data(conn, ("civil_defense",)) and shelters.has_data(conn, ("quake_outdoor", "civil_defense"))
    assert [s["name"] for s in found] == ["시험 옥외대피장소 가", "시험 옥외대피장소 나"]
    assert [s["name"] for s in wide][-1] == "시험 옥외대피장소 멀리" and [s["distance_m"] for s in wide] == sorted(s["distance_m"] for s in wide)
    assert shelters.walk_minutes(111, 4.0) == 2 and shelters.walk_minutes(1, 4.0) == 1
    with pytest.raises(ValueError):
        shelters.walk_minutes(100, 0)                                                      # 속도를 모르면 시간을 지어내지 않는다


def test_the_loader_upserts_without_duplicating_and_replace_clears_the_old_rows(api):
    from scripts import load_safety_shelters as loader

    source = "시험용 적재 자료"
    parsed = loader.parse("시설명,소재지도로명주소,위도,경도,관리번호\n가,서울 1,34.5001,125.0001,A-1\n나,서울 2,34.5002,125.0002,\n")
    try:
        for _ in range(2):                                                                 # 두 번 적재해도 줄이 늘지 않는다
            with get_connection() as conn, conn.transaction():
                counts = loader.load(conn, shelter_type="civil_defense", source=source, source_date=None, rows=parsed.rows, replace=False)
            assert counts == {"deleted": 0, "upserted": 2}
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM safety_shelters WHERE source=%s", (source,))
            assert cur.fetchone()[0] == 2
        with get_connection() as conn, conn.transaction():
            counts = loader.load(conn, shelter_type="civil_defense", source=source, source_date=None, rows=parsed.rows[:1], replace=True)
        assert counts == {"deleted": 2, "upserted": 1}
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM safety_shelters WHERE source=%s", (source,))


def test_deleting_the_trip_deletes_its_stops(api, near):
    trip_id = _trip(api)
    _sweep(api, FakeCheck(_report(_quake(5.1)))).tick()
    assert len(_pauses(trip_id)) == 1
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM trips WHERE trip_id=%s", (trip_id,))
    assert _pauses(trip_id) == []                                                          # `ON DELETE CASCADE`
