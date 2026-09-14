# -*- coding: utf-8 -*-
"""확정 시나리오 재생 — `team_branch/jh/확정_시나리오_액티비티_수정_버전.md`(2026-09-14).

대만인 친구 2명의 서울 하루를 **재생 입력**으로 흘려 제품 경로가 시나리오대로 움직이는지
본다. 사건은 사후에 정한 것이므로 결과에 `replay` 표시가 붙어야 한다(v11 §8-A).

장면 여섯:
    액-02   09:00  시스템 — 1시간 전 미세먼지 경보 → 같은 건물 아쿠아리움으로 자동 변경
    이동-B1 10:45  시스템 — 성수역 화재 무정차 → 건대입구 하차+버스, 다른 안 뚝섬
    요식-P3 13:00  고객   — 70분 늦음 → 라스트오더 촉박 → 도보 6분 브레이크타임 없는 식당
    이동-A6 17:10  시스템 — 세종대로 행사 통제 → 지하철로, 택시는 「확인 불가」로 빼고 도보 우회
    요식-P7 18:00  고객   — 임시휴무 → 도보 8분 카드 결제 식당, 롯데마트 일정 영향 없음
    액-08   19:40  고객   — 품절 → 귀가 동선 위 매장 추천, 재고는 [미확인]

★결정 15(하나를 고른다)를 따른다. 시나리오 문장의 「대안 둘」은 **최선 하나를 적용하고
  나머지를 「다른 안」으로** 보인다 — 선택지를 나열해 고르게 하지 않는다.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.infrastructure.db.session import get_connection
from app.infrastructure.travel.base import TravelSources
from app.infrastructure.travel.disruptions import DisruptionCheck
from app.infrastructure.travel.replay import (ReplayAir, ReplayRouteEvents, ReplayTimeline,
                                              ReplayWarning, ReplayWeather)
from app.modules.travel_ops.itinerary import Item, TripStore
from app.modules.travel_ops.trip_desk import TripDesk
from app.modules.travel_ops.trip_watch import TripWatcher

KST = ZoneInfo("Asia/Seoul")
SCENARIO = json.loads((Path(__file__).resolve().parents[2] / "app" / "modules" / "travel_ops"
                       / "scenarios" / "seoul_day_taiwan_friends.json").read_text(encoding="utf-8"))
DAY = SCENARIO["trip"]["date"]
REPORTS = {report["type"]: report for report in SCENARIO["customer_reports"]}


def _at(hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{DAY}T{hhmm}:00").replace(tzinfo=KST)


class Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture()
def world():
    """테넌트·고객·장소·일정(버전 1)을 만든다. 끝나면 지운다."""
    tenant = "scenario_" + uuid4().hex[:12]
    clock = Clock(_at("08:00"))
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "scenario"))
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) "
                        "RETURNING customer_id", (tenant, "taiwan-friends"))
            customer = cur.fetchone()[0]
            place_ids = {}
            for place in SCENARIO["places"]:
                cur.execute(
                    "INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,"
                    "attributes) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING place_id",
                    (tenant, place["name"], place["kind"], place["lat"], place["lon"],
                     place["weather_sensitive"], json.dumps(place["attributes"], ensure_ascii=False)))
                place_ids[place["key"]] = cur.fetchone()[0]
        store = TripStore(tenant)
        items = [Item(item_id=uuid4(), seq=it["seq"], kind=it["kind"], title=it["title"],
                      place_id=place_ids.get(it.get("place")), starts_at=_at(it["start"]),
                      ends_at=_at(it["end"]),
                      detail={**it.get("detail", {}), **({"route": it["route"]} if "route" in it else {})})
                 for it in SCENARIO["items"]]
        with conn.transaction():
            trip_id, _ = store.create_trip(conn, customer_id=customer, title=SCENARIO["trip"]["title"],
                                           locale=SCENARIO["trip"]["locale"],
                                           party_size=SCENARIO["trip"]["party_size"], items=items,
                                           constraints=SCENARIO["trip"]["constraints"])
    timeline = ReplayTimeline(SCENARIO["timeline"], clock)
    sources = TravelSources(weather=ReplayWeather(timeline), warning=ReplayWarning(timeline),
                            air=ReplayAir(timeline))
    check = DisruptionCheck(sources, limits=lambda: (60, 30)).check
    watcher = TripWatcher(store=store, check=check, connection_factory=get_connection, clock=clock,
                          routes=SCENARIO["routes"], route_events=ReplayRouteEvents(timeline))
    desk = TripDesk(store=store, connection_factory=get_connection)
    yield {"tenant": tenant, "store": store, "trip_id": trip_id, "clock": clock,
           "watcher": watcher, "desk": desk}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM trips WHERE tenant_id=%s", (tenant,))      # versions·items cascade
        cur.execute("DELETE FROM places WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM customers WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))


def _latest(world):
    with get_connection() as conn:
        return world["store"].latest(conn, world["trip_id"])


def _notices(world):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT dedupe_key, payload_json FROM outbox WHERE tenant_id=%s "
                    "AND topic='trip.notice' ORDER BY available_at, dedupe_key", (world["tenant"],))
        return cur.fetchall()


def _slot(items, seq):
    return next(i for i in items if i.seq == seq)


def _tick(world, hhmm):
    world["clock"].now = _at(hhmm)
    return world["watcher"].tick()


# ── 액-02 ──────────────────────────────────────────────────────
def test_before_the_warning_nothing_changes(world):
    result = _tick(world, "08:40")
    trip, _ = _latest(world)
    assert trip["version"] == 1 and result.adjusted == [] and _notices(world) == []


def test_act02_air_alert_one_hour_ahead_moves_the_sky_deck_to_the_aquarium(world):
    result = _tick(world, "09:00")
    assert len(result.adjusted) == 1, (result.fatal, result.unresolved, result.unhandled)
    assert (result.adjusted[0]["from"], result.adjusted[0]["to"]) == ("잠실 스카이타워", "아쿠아리움")

    trip, items = _latest(world)
    assert trip["version"] == 2
    sky = _slot(items, 2)
    assert sky.place["name"] == "아쿠아리움" and sky.replaces_item_id is not None
    assert sky.starts_at == _at("10:00")                    # ★시각은 그대로
    assert [i.place["name"] for i in items if i.kind == "activity" and i.seq != 2] == [
        "성수동 팝업·향수 쇼룸 거리", "경복궁", "롯데마트 서울역점"]

    [(key, payload)] = _notices(world)
    assert key.endswith(":v2")
    assert payload["text"] == ("오늘 오전 잠실 스카이타워 야외 전망 데크는 시야 확보가 어려울 것으로 "
                               "예상되어, 같은 건물 지하 1층 아쿠아리움으로 변경됩니다.")
    assert payload["replay"] is True
    assert "기준 초과" in payload["causes"][0]["kind"]
    assert payload["other_options"] == ["롯데월드 어드벤처"]


def test_act02_does_not_adjust_twice(world):
    _tick(world, "09:00")
    second = _tick(world, "09:10")
    trip, _ = _latest(world)
    assert trip["version"] == 2 and second.adjusted == [] and len(_notices(world)) == 1


# ── 이동-B1 ────────────────────────────────────────────────────
def test_move_b1_station_fire_reroutes_via_konkuk_university_by_bus(world):
    """성수역 무정차 — 직통이 끊긴다. 건대입구 하차+버스를 적용하고 뚝섬을 다른 안으로 둔다."""
    result = _tick(world, "10:45")
    [change] = [a for a in result.adjusted if "성수" in (a.get("from") or "")]
    assert change["to"] == "건대입구역에서 내려 버스로 가는 길"

    _, items = _latest(world)
    move = _slot(items, 3)
    assert move.detail["option"] == "konkuk_bus" and move.replaces_item_id is not None
    assert move.ends_at <= _slot(items, 4).starts_at        # ★성수동 일정에 늦지 않는다

    text = change["notice"]["text"]
    assert "성수역 화재로 열차가 성수역을 무정차 통과합니다" in text
    assert "도보 350m, 예상 23분" in text
    assert "다른 안: 뚝섬역에서 내려 버스로 되돌아가는 길(도보 420m, 예상 25분)" in text
    assert "도착이 조금 늦어지지만" in text
    assert change["notice"]["replay"] is True


# ── 요식-P3 ────────────────────────────────────────────────────
def test_dining_p3_seventy_minute_delay_moves_lunch_to_a_no_break_restaurant(world):
    report = REPORTS["delay"]
    result = world["desk"].report_delay(trip_id=world["trip_id"], at=_at(report["at"]),
                                        minutes=report["minutes"], message=report["message"])
    assert result["status"] == "adjusted", result
    assert result["to"] == "성수 브런치 식당(시나리오)"

    _, items = _latest(world)
    lunch = _slot(items, 5)
    assert lunch.starts_at == _at("14:10") and lunch.ends_at <= _slot(items, 6).starts_at
    text = result["notice"]["text"]
    assert "주문 가능한 시간이 촉박" in text
    assert "도보 6분 거리, 브레이크타임 없는 성수 브런치 식당(시나리오)" in text
    assert "다른 안: 성수 국수 식당(시나리오)(도보 6분)" in text


# ── 이동-A6 ────────────────────────────────────────────────────
def test_move_a6_road_control_switches_to_subway_and_excludes_taxi(world):
    result = _tick(world, "17:10")
    [change] = [a for a in result.adjusted if a.get("from") == "세종대로 직통 버스"]
    assert change["to"] == "지하철(3호선 → 4호선 환승 1회)"
    text = change["notice"]["text"]
    assert "세종대로가 행사로 통제" in text
    assert "택시는 통제 구간의 실제 소요를 확인할 수 없어 권하지 않습니다" in text
    assert "통제 구역에 걸린 도보 구간은 우회로로 안내합니다" in text
    excluded = change["notice"]["excluded"]
    assert any("다음 일정" in reason for reason in excluded["세종대로 직통 버스"])  # 버스는 늦는다
    _, items = _latest(world)
    assert _slot(items, 8).ends_at <= _slot(items, 9).starts_at


# ── 요식-P7 ────────────────────────────────────────────────────
def test_dining_p7_closed_today_moves_dinner_to_a_card_restaurant(world):
    report = REPORTS["closed"]
    result = world["desk"].report_closed(trip_id=world["trip_id"], at=_at(report["at"]),
                                         message=report["message"])
    assert result["status"] == "adjusted", result
    assert result["to"] == "서울역 한식당(시나리오)"      # ★현금만 받는 가까운 곳은 탈락
    _, items = _latest(world)
    dinner = _slot(items, 9)
    assert dinner.starts_at == _at("18:20")
    text = result["notice"]["text"]
    assert "도보 8분 거리, 카드 결제가 가능한 서울역 한식당(시나리오)" in text
    assert "이후 롯데마트 서울역점 일정에는 영향이 없습니다" in text


# ── 액-08 ──────────────────────────────────────────────────────
def test_act08_stock_out_recommends_a_store_on_the_way_back_without_claiming_stock(world):
    report = REPORTS["stock_out"]
    answer = world["desk"].ask_nearby_store(trip_id=world["trip_id"], at=_at(report["at"]),
                                            products=report["products"], message=report["message"])
    assert answer["status"] == "answered", answer
    assert answer["recommendation"] == "명동 대형마트(시나리오 지점)"
    assert "호텔로 돌아가는 동선 위" in answer["text"]
    assert "[미확인]" in answer["text"] and answer["stock"] == "unverified"
    assert any("벗어난다" in r for r in answer["rejected"]["용산 대형마트(시나리오 지점)"])
    trip, _ = _latest(world)
    assert trip["version"] == 1                            # ★추천만 — 일정은 안 바꾼다


# ── 하루 전체 ──────────────────────────────────────────────────
def test_the_whole_day_in_order(world):
    """시각 순서대로 흘린다. 일정 버전 1 → 6, 통지 다섯(액-08 은 답변이라 통지 없음)."""
    desk, trip_id = world["desk"], world["trip_id"]
    assert len(_tick(world, "09:00").adjusted) == 1                               # 액-02
    assert len(_tick(world, "10:45").adjusted) == 1                               # 이동-B1
    p3 = REPORTS["delay"]
    assert desk.report_delay(trip_id=trip_id, at=_at(p3["at"]), minutes=p3["minutes"],
                             message=p3["message"])["status"] == "adjusted"        # 요식-P3
    assert _tick(world, "14:50").adjusted == []                                   # 성수→경복궁 정상
    assert len(_tick(world, "17:10").adjusted) == 1                               # 이동-A6
    p7 = REPORTS["closed"]
    assert desk.report_closed(trip_id=trip_id, at=_at(p7["at"]),
                              message=p7["message"])["status"] == "adjusted"       # 요식-P7
    a8 = REPORTS["stock_out"]
    assert desk.ask_nearby_store(trip_id=trip_id, at=_at(a8["at"]), products=a8["products"],
                                 message=a8["message"])["status"] == "answered"    # 액-08

    trip, items = _latest(world)
    assert trip["version"] == 6
    assert len(_notices(world)) == 5
    ordered = sorted(items, key=lambda i: i.seq)
    for before, after in zip(ordered, ordered[1:]):
        assert (before.ends_at or before.starts_at) <= after.starts_at, (before.title, after.title)
