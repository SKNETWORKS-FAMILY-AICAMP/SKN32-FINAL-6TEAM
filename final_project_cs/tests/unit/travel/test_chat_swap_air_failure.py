# -*- coding: utf-8 -*-
"""채팅 「다른 곳으로 바꿔 줘」가 **대기질 자료 하나를 못 읽어** 교체 전체를 거절하던 결함 — 재현과 고친 동작. `[2026-10-20]`

☆x600 실서버 확인(2026-10-20 04:27, role-manager 50d6cdf0): 등록된 여행(10-27 화요일)의 「경복궁 다른 곳으로 바꿔 줘」가
  등록 때 남긴 대안(황학정 · 독립관 · 창덕궁 낙선재)으로 바뀌지 않고 「요청을 완료하지 못했어요」(`escalated`)로 끝났다.
  같은 순간 api 로그에 `air chain exhausted — every source failed: ['airkorea', …]`.

경로: 활동 팀 `_change` → `plan_swap(check=recheck)` → 교체 직전 다시 점검(`DisruptionCheck.check`) → 대기질 실패 → 판정 `fatal`
  → (전) `clear` 가 아니면 모두 `alternate_invalid` · 문장 없음 → 팀 `settle` 이 `_escalate` → 「요청을 완료하지 못했어요」.

왜 **늘** 났나: ①접수로 등록한 장소에 구(district)가 없어 에어코리아(구 측정소)가 곧바로 실패 ②대체 Open-Meteo 는 72시간 앞까지만 값을 준다.

고친 것(사용자 결정 2026-10-20 — 둘 다):
  1. 고객이 고른 교체는 **사건이 없고 안전과 무관한 자료만 못 읽었으면 바꾸고** 못 확인한 것을 알린다(D-018). 안전 자료(재난문자 · 지진 · 특보)를
     못 읽었거나 실제 사건이 있으면 바꾸지 않고 **이유를 답한다**(`alternate_invalid` + `text` → 처리 불가가 아니라 답).
  2. 접수 등록 장소에 서울 자치구를 채우고(`assemble._seoul_district`), 72시간 밖 시각의 대기질은 실패가 아니라 「아직 볼 때가 아님」으로 둔다.

모든 바깥 서비스는 메모리 대역이다(mock 서버 시험 — 실서버 확인은 따로 적는다).

재현:

    python -m pytest tests/unit/travel/test_chat_swap_air_failure.py -v
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx

from app.domains.travel_ops.components.intake.assemble import _place_in
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary.itinerary_changes import NoChange, plan_swap
from app.domains.travel_ops.instances._shared.itinerary_team import ItineraryWork
from app.domains.travel_ops.ports.data_sources.air_quality import AirKoreaRealtime, FallbackAir, OpenMeteoAir
from app.domains.travel_ops.ports.data_sources.base import TravelSources
from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck

KST = ZoneInfo("Asia/Seoul")
NOW = datetime.now(UTC).astimezone(KST).replace(minute=0, second=0, microsecond=0)
WEEK_LATER = NOW + timedelta(days=7)                     # x600 확인 때와 같은 거리(10-20 → 10-27)
TOMORROW = NOW + timedelta(days=1)


# ── 바깥 서비스 대역 ─────────────────────────────────────────────
def _airkorea(status=200):
    """에어코리아 — 서울 측정소(구 이름) 값. 시각과 상관없이 「지금 값」만 준다."""
    body = {"response": {"header": {"resultCode": "00", "resultMsg": "NORMAL_CODE"},
                         "body": {"items": [{"stationName": "종로구", "dataTime": NOW.strftime("%Y-%m-%d %H:00"),
                                             "pm10Value": "21", "pm25Value": "9", "pm10Grade": "1", "pm25Grade": "1"}]}}}
    return AirKoreaRealtime(service_key="test", transport=lambda url, params: httpx.Response(
        status, json=body, request=httpx.Request("GET", url)))


def _open_meteo(status=200):
    """Open-Meteo 대기질 — 지금 앞뒤로 과거 6시간 + 예보 72시간."""
    hours = [(NOW + timedelta(hours=h)).strftime("%Y-%m-%dT%H:00") for h in range(-6, 72)]
    body = {"latitude": 37.6, "longitude": 127.0,
            "hourly": {"time": hours, "pm10": [20.0] * len(hours), "pm2_5": [9.0] * len(hours)}}
    return OpenMeteoAir(transport=lambda url, params: httpx.Response(status, json=body, request=httpx.Request("GET", url)))


class _Weather:
    name = "weather_stub"

    def forecast(self, *, latitude, longitude, at):
        return {"source": "weather_stub", "precipitation_probability": 10, "wind_speed_kmh": 5}


def _check(status=200):
    air = FallbackAir([_airkorea(status), _open_meteo(status)])
    checker = DisruptionCheck(TravelSources(weather=_Weather(), air=air), limits=lambda: (60, 30),
                              quake_rules=lambda: (4.0, 100.0, 24.0))
    return (lambda *, place, starts_at: checker.check(place=place, starts_at=starts_at)), air


# ── 등록된 여행 모양 ─────────────────────────────────────────────
def _registered_place(name, lat, lon, **extra):
    """옛 등록 장소 행의 모양 — 구(district)가 없다(고치기 전에 등록된 여행)."""
    place_id = str(uuid4())
    attributes = {"source": "tour_api", "source_content_id": "1"}
    return {**attributes, "place_id": place_id, "name": name, "kind": "activity", "latitude": lat, "longitude": lon,
            "weather_sensitive": None, "attributes": attributes, **extra}


def _trip(visit, **extra):
    current = _registered_place("경희궁 숭정전", 37.5713, 126.9681, **extra)
    alternates = [_registered_place("황학정", 37.5781, 126.9657, **extra),
                  _registered_place("독립관", 37.5744, 126.9580, **extra)]
    item = Item(item_id=uuid4(), seq=1, kind="activity", title="경복궁", place_id=None, starts_at=visit,
                ends_at=visit + timedelta(hours=2), place=current,
                detail={"alternates": [{"name": p["name"], "place_id": p["place_id"], "key": p["place_id"],
                                        "starts_at": visit.isoformat(), "ends_at": (visit + timedelta(hours=2)).isoformat(),
                                        "walk_min": None, "option": None, "option_label": None} for p in alternates],
                        "other_options": [p["name"] for p in alternates], "alternates_from": "intake"})
    return item, {p["place_id"]: p for p in [current, *alternates]}


def _swap(item, places, check, customer_pick=True):
    return plan_swap(trip_version=3, base_version=3, items=[item], places_by_id=places, item_id=item.item_id,
                     choice=None, message="경복궁 다른 곳으로 바꿔 줘", request_id="live-test", check=check,
                     customer_pick=customer_pick)


# ── x600 의 경우: 일주일 뒤 · 구 없음 ─────────────────────────────
def test_a_week_ahead_swap_is_not_blocked_by_the_air_quality_check_any_more():
    """고침 2 — 72시간 밖 시각의 대기질은 「아직 볼 때가 아님」이다. 그래서 x600 과 같은 여행(구 없음 · 일주일 뒤)도 바로 바뀐다."""
    check, air = _check()
    item, places = _trip(WEEK_LATER)
    plan = _swap(item, places, check)
    assert not isinstance(plan, NoChange), plan
    assert plan.notice["text"].startswith("요청하신 대로 경희궁 숭정전 대신 황학정")
    assert "unchecked" not in plan.summary and not plan.notice.get("warnings")
    assert air.misses["all_failed"] == 0                                         # 바깥에 묻지도 않았다


def test_registered_places_carry_their_seoul_district():
    """고침 2 — 접수 등록 장소에 구를 채운다(주소가 먼저, 없으면 좌표가 한 구만 가리킬 때). 에어코리아가 측정소를 고른다."""
    by_address = _place_in("alt-1", {"name": "황학정", "latitude": 37.5781, "longitude": 126.9657, "source": "tour_api",
                                     "address": "서울특별시 종로구 사직로9길 15-32"}, "activity")
    assert by_address["attributes"]["district"] == "종로구"
    nowhere = _place_in("alt-2", {"name": "먼 곳", "latitude": 35.1, "longitude": 129.0, "source": "tour_api"}, "activity")
    assert "district" not in nowhere["attributes"]                               # 서울 밖 · 모르면 비운다(지어내지 않는다)


def test_with_a_district_the_air_check_reads_the_station_value_for_tomorrow():
    """대조 — 72시간 안 · 구가 있으면 에어코리아 값으로 점검을 통과한다."""
    check, air = _check()
    item, places = _trip(TOMORROW, district="종로구")
    plan = _swap(item, places, check)
    assert not isinstance(plan, NoChange), plan
    assert "unchecked" not in plan.summary
    assert air.sources[0].misses["no_district"] == 0


# ── 고침 1: 조회만 실패했으면 바꾸고 알린다 ──────────────────────
def test_when_only_the_air_sources_fail_the_customers_swap_still_happens_with_a_note():
    """72시간 안인데 대기질 소스가 둘 다 실패(장애) — 사건은 없다. 고객이 고른 교체는 하고 「대기질은 확인하지 못했어요」를 싣는다."""
    check, air = _check(status=504)
    item, places = _trip(TOMORROW, district="종로구")
    plan = _swap(item, places, check)
    assert not isinstance(plan, NoChange), plan
    assert plan.summary["unchecked"] == ["air_quality"] and plan.summary["rechecked"] == "fatal"
    assert any("대기질 정보는 지금 확인하지 못했어요" in w for w in plan.notice["warnings"])
    assert "대기질" in plan.notice["text"]
    assert air.misses["all_failed"] == 1


def test_a_prefilter_still_drops_an_option_whose_checks_could_not_be_read():
    """같은 「대기질만 못 읽음」이라도 고객에게 **보이기 전에** 미리 거르는 쪽(`customer_pick=False` — 항로 지킴이 묻는 안 · 확인 화면 위험 대안)은
    교체를 받지 않는다 — 확인 못 한 후보를 안전한 대안처럼 내밀지 않는다(`test_intake_risks` 의 「확인 못 한 후보는 안전한 안으로 안 보인다」).
    ☆`[2026-10-20 commit 세션 발견]` 고친 첫 판은 이 구분이 없어 미리 거르기까지 느슨해졌다."""
    item, places = _trip(TOMORROW)
    plan = _swap(item, places, lambda **_: _report(failed_categories=["air_quality"]), customer_pick=False)
    assert isinstance(plan, NoChange) and plan.status == "alternate_invalid"
    assert plan.detail["report"]["failed_categories"] == ["air_quality"]


def _report(**extra):
    return {"verdict": "fatal", "disruptions": [], "failed_categories": [], **extra}


def test_an_unread_safety_source_keeps_the_plan_and_says_why():
    """재난문자를 못 읽었으면 바꾸지 않는다 — 처리 불가가 아니라 이유를 답한다."""
    item, places = _trip(TOMORROW)
    plan = _swap(item, places, lambda **_: _report(failed_categories=["disaster_msg", "air_quality"]))
    assert isinstance(plan, NoChange) and plan.status == "alternate_invalid"
    assert "재난문자를 지금 확인하지 못해 바꾸지 않았어요" in plan.detail["text"] and plan.detail["unchecked"] == ["disaster_msg"]


def test_a_real_disruption_keeps_the_plan_and_names_it():
    item, places = _trip(TOMORROW)
    plan = _swap(item, places, lambda **_: _report(verdict="disrupted", disruptions=[
        {"category": "traffic_control", "kind": "도로 통제"}]))
    assert isinstance(plan, NoChange) and plan.status == "alternate_invalid"
    assert "황학정은(는)" in plan.detail["text"] and "도로 통제 소식이 있어 바꾸지 않았어요" in plan.detail["text"]
    closed = _swap(item, places, lambda **_: _report(verdict="disrupted", disruptions=[
        {"category": "place_status", "kind": "closed", "source": "dining_ledger"}]))
    assert "휴무 소식이 있어 바꾸지 않았어요" in closed.detail["text"]                # 영업 상태 확인의 영어 값을 그대로 싣지 않는다


def test_a_check_that_could_not_run_keeps_the_plan_and_says_so():
    """도구 없음 · 한도(실패 항목 목록이 없는 `fatal` · `not_checked`)는 확인 못 한 것이라 바꾸지 않고 답한다."""
    item, places = _trip(TOMORROW)
    for report in ({"verdict": "fatal", "unknown": True}, {"verdict": "not_checked", "reason": "ToolBudgetExceeded"}):
        plan = _swap(item, places, lambda report=report, **_: report)
        assert isinstance(plan, NoChange) and plan.status == "alternate_invalid"
        assert "안전 정보를 지금 확인하지 못해 바꾸지 않았어요" in plan.detail["text"]


def test_the_team_answers_a_refused_swap_instead_of_escalating():
    """Case 버전(채팅) — 팀 `settle` 이 `alternate_invalid` 를 처리 불가(`escalated`)가 아니라 그 이유 문장으로 답한다."""
    item, places = _trip(TOMORROW)
    plan = _swap(item, places, lambda **_: _report(failed_categories=["earthquake"]))
    seen = {}

    def result(task, **kwargs):
        seen.update(kwargs)
        return "answered"

    def escalate(*args, **kwargs):
        raise AssertionError("처리 불가로 넘기면 안 된다")

    work = SimpleNamespace(_result=result, _escalate=escalate, _plain=ItineraryWork._plain)
    assert ItineraryWork.settle(work, object(), {"evidence": []}, plan) == "answered"
    assert "지진 정보를 지금 확인하지 못해 바꾸지 않았어요" in seen["answer"]
    assert seen["decisions"][0]["itinerary"] == "alternate_invalid"


# ── 같은 문장의 두 번째 갈래: 「근처」로 읽혀 식당 전용 길로 감 ────────
def test_a_near_reading_of_an_activity_swap_stays_on_the_alternate_path():
    """☆x600 2026-10-20 09:47 — 같은 「경복궁 다른 곳으로 바꿔 줘」(경복궁 줄을 골라 보냄)를 해석 모델이 「경복궁 근처」로 읽어
    식당 전용 근처 계산으로 넘겼고 「어느 식사 일정을 바꿀지 알려 주세요」(`clarify`)로 끝났다. 대상이 활동이면 그 길로 보내지 않는다."""
    from app.domains.travel_ops.components.conversation.trip_messages import near_dining_change

    activity, _ = _trip(TOMORROW)
    meal = Item(item_id=uuid4(), seq=2, kind="dining", title="점심", place_id=None, starts_at=TOMORROW, ends_at=None)
    near = {"place_search": {"relation": "near", "anchor_item": "s1"}}

    def decision(action, item):
        return SimpleNamespace(action=action, item=item, raw=near)

    items = [activity, meal]
    assert not near_dining_change(decision("apply_change", activity), items=items, selected=None)
    assert not near_dining_change(decision("apply_change", None), items=items, selected=activity.item_id)   # 화면에서 고른 항목
    assert not near_dining_change(decision("propose_alternatives", activity), items=items, selected=None)
    assert near_dining_change(decision("apply_change", meal), items=items, selected=None)                   # 식사는 지금처럼
    assert near_dining_change(decision("apply_change", None), items=items, selected=None)                   # 대상 모름 — 지금처럼 되묻는다
    assert near_dining_change(decision("replace_named", activity), items=items, selected=None)              # 이름 댄 바꾸기는 그대로
    assert not near_dining_change(SimpleNamespace(action="apply_change", item=activity, raw={}), items=items, selected=None)
