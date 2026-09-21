# -*- coding: utf-8 -*-
"""Case 버전만으로 확정 시나리오 하루가 돈다 — 시나리오용 여행 버전과 **같은 결과**인가.

★`[결정 2026-09-17]` 합격선: 같은 재생 입력을 두 테넌트에 흘린다.

    A  시나리오용 여행 버전   TripWatcher · TripDesk 가 직접 쓴다
    B  Case 버전             감시 Case · 고객 Case → Controller → Team → 코어가 `itinerary.apply` 적용

  비교: 일정 버전 수 · 마지막 항목(순서·제목·시각) · 버전별 통지 문구.
  그리고 B 에만 있어야 하는 것: 버전마다 Case 가 붙어 있다(`itinerary_versions.case_id`),
  적용 기록(`action_requests` succeeded), 담당 Team.

★LLM 만 흉내 낸다(분류기 · 신고 추출). 감시 · Controller · Team · 적용 · 통지는 실제 코드다.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.subjects import SubjectNotFound
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.infrastructure.travel.base import TravelSources
from app.infrastructure.travel.disruptions import DisruptionCheck
from app.infrastructure.travel.replay import (ReplayAir, ReplayRouteEvents, ReplayTimeline,
                                              ReplayWarning, ReplayWeather)
from app.modules.travel_ops.case_engine import CaseEngine, cleanup_tenant
from app.modules.travel_ops.itinerary import Item, TripStore
from app.modules.travel_ops.subjects import resolve_subject
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


def _classifier(message: str) -> dict[str, str]:
    if any(word in message for word in ("바꿔", "되돌", "다른 안")):
        return {"intent": "adjust_reject", "issue_code": "other", "sentiment": "neutral"}
    if "품절" in message:
        return {"intent": "incident_report", "issue_code": "activity_other", "sentiment": "negative"}
    return {"intent": "incident_report", "issue_code": "dining_hours", "sentiment": "negative"}


def _extractor(message: str) -> dict:
    if "되돌려" in message:
        import re
        return {"type": "rollback", "to_version": int(re.findall(r"\d+", message)[0])}
    if "바꿔" in message:
        return {"type": "change"}
    for report in REPORTS.values():
        if report["message"] == message:
            return {"type": report["type"], "minutes": report.get("minutes"),
                    "products": report.get("products", [])}
    return {"type": "other"}


def _seed(tenant: str):
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "case version day"))
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                        (tenant, "taiwan-friends"))
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
        # ★이동 항목은 경로 정의를 들고 다닌다 — 등록 API 와 시나리오 모드가 넣는 모양 그대로.
        items = [Item(item_id=uuid4(), seq=it["seq"], kind=it["kind"], title=it["title"],
                      place_id=place_ids.get(it.get("place")), starts_at=_at(it["start"]),
                      ends_at=_at(it["end"]),
                      detail={**it.get("detail", {}),
                              **({"route": it["route"], "route_def": SCENARIO["routes"][it["route"]]}
                                 if "route" in it else {})})
                 for it in SCENARIO["items"]]
        with conn.transaction():
            trip_id, _ = store.create_trip(conn, customer_id=customer, title=SCENARIO["trip"]["title"],
                                           locale=SCENARIO["trip"]["locale"],
                                           party_size=SCENARIO["trip"]["party_size"], items=items,
                                           constraints=SCENARIO["trip"]["constraints"])
    return store, customer, trip_id


def _sources(clock):
    timeline = ReplayTimeline(SCENARIO["timeline"], clock)
    sources = TravelSources(weather=ReplayWeather(timeline), warning=ReplayWarning(timeline),
                            air=ReplayAir(timeline))
    return DisruptionCheck(sources, limits=lambda: (60, 30)).check, ReplayRouteEvents(timeline)


@pytest.fixture()
def trip_world():
    tenant = "tripver_" + uuid4().hex[:10]
    store, customer, trip_id = _seed(tenant)
    clock = Clock(_at("08:00"))
    check, route_events = _sources(clock)
    yield {"tenant": tenant, "store": store, "trip_id": trip_id, "customer": customer, "clock": clock,
           "watcher": TripWatcher(store=store, check=check, connection_factory=get_connection, clock=clock,
                                  route_events=route_events),
           "desk": TripDesk(store=store, connection_factory=get_connection)}
    cleanup_tenant(tenant)


@pytest.fixture()
def case_world():
    tenant = "casever_" + uuid4().hex[:10]
    store, customer, trip_id = _seed(tenant)
    clock = Clock(_at("08:00"))
    check, route_events = _sources(clock)
    engine = CaseEngine(tenant_id=tenant, check=check, route_events=route_events, classifier=_classifier,
                        report_extractor=_extractor, clock=clock)
    yield {"tenant": tenant, "store": store, "trip_id": trip_id, "customer": customer, "clock": clock,
           "engine": engine}
    cleanup_tenant(tenant)


# ── 도우미 ─────────────────────────────────────────────────────
def _latest(world):
    with get_connection() as conn:
        return world["store"].latest(conn, world["trip_id"])


def _notices(world) -> list[tuple[str, str]]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT dedupe_key, payload_json FROM outbox WHERE tenant_id=%s AND topic='trip.notice'",
                    (world["tenant"],))
        rows = cur.fetchall()
    version = lambda key: int(key.rsplit(":v", 1)[1])  # noqa: E731
    return [(key.rsplit(":", 1)[1], payload["text"]) for key, payload in sorted(rows, key=lambda r: version(r[0]))]


def _shape(items):
    return [(i.seq, i.kind, i.title, i.starts_at.isoformat(), i.ends_at.isoformat() if i.ends_at else None)
            for i in sorted(items, key=lambda i: i.seq)]


def _versions(world):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT version, reason, case_id FROM itinerary_versions WHERE tenant_id=%s "
                    "AND trip_id=%s ORDER BY version", (world["tenant"], world["trip_id"]))
        return cur.fetchall()


def _run_trip_day(world):
    desk, trip_id, clock = world["desk"], world["trip_id"], world["clock"]

    def tick(hhmm):
        clock.now = _at(hhmm)
        return world["watcher"].tick()

    assert len(tick("09:00").adjusted) == 1
    assert len(tick("10:45").adjusted) == 1
    p3 = REPORTS["delay"]
    clock.now = _at(p3["at"])
    assert desk.report_delay(trip_id=trip_id, at=_at(p3["at"]), minutes=p3["minutes"],
                             message=p3["message"])["status"] == "adjusted"
    assert tick("14:50").adjusted == []
    assert len(tick("17:10").adjusted) == 1
    p7 = REPORTS["closed"]
    assert desk.report_closed(trip_id=trip_id, at=_at(p7["at"]), message=p7["message"])["status"] == "adjusted"
    a8 = REPORTS["stock_out"]
    assert desk.ask_nearby_store(trip_id=trip_id, at=_at(a8["at"]), products=a8["products"],
                                 message=a8["message"])["status"] == "answered"


def _say(world, kind, **kwargs):
    report = REPORTS[kind]
    world["clock"].now = _at(report["at"])
    return world["engine"].message(customer_id=world["customer"], trip_id=world["trip_id"],
                                   text=report["message"], request_id=f"say-{kind}", **kwargs)


def _run_case_day(world):
    engine, clock = world["engine"], world["clock"]
    outcomes = {}

    def tick(hhmm):
        clock.now = _at(hhmm)
        return engine.tick()

    outcomes["act02"] = tick("09:00")
    outcomes["b1"] = tick("10:45")
    outcomes["p3"] = _say(world, "delay")
    outcomes["quiet"] = tick("14:50")
    outcomes["a6"] = tick("17:10")
    outcomes["p7"] = _say(world, "closed")
    outcomes["a8"] = _say(world, "stock_out")
    return outcomes


# ── 하루 전체 — 두 버전이 같다 ──────────────────────────────────
def test_the_case_version_runs_the_whole_day_like_the_trip_version(trip_world, case_world):
    _run_trip_day(trip_world)
    outcomes = _run_case_day(case_world)

    # 감시가 연 Case 셋 — 담당 Team 이 끝까지 처리했다
    for key, team in (("act02", "activity"), ("b1", "mobility"), ("a6", "mobility")):
        tick = outcomes[key]
        assert len(tick.opened) == 1 and tick.fatal == [], (key, tick)
        assert tick.ran == [{"case_id": tick.opened[0]["case_id"], "status": "resolved"}], (key, tick.ran)
        view = case_world["engine"].view(tick.opened[0]["case_id"])
        assert view["owner_team_id"] == team, (key, view)
        assert view["events"] == ["created", "classified", "routed", "completed"], (key, view)
    assert outcomes["quiet"].opened == []

    # 고객 Case 셋
    for key, team in (("p3", "dining"), ("p7", "dining"), ("a8", "activity")):
        view = outcomes[key]
        assert view["case_status"] == "resolved" and view["owner_team_id"] == team, (key, view)
    assert "[미확인]" in outcomes["a8"]["answer"] and outcomes["a8"]["applied_actions"] == []

    # ★같은 결과 — 버전 수 · 마지막 항목 · 통지 문구
    trip_a, items_a = _latest(trip_world)
    trip_b, items_b = _latest(case_world)
    assert trip_a["version"] == trip_b["version"] == 6
    assert _shape(items_a) == _shape(items_b)
    assert [text for _, text in _notices(trip_world)] == [text for _, text in _notices(case_world)]
    assert len(_notices(case_world)) == 5

    # ★Case 버전에만 있어야 하는 것 — 버전마다 Case 가 붙고, 적용 기록이 남는다
    versions = _versions(case_world)
    assert [v for v, _, _ in versions] == [1, 2, 3, 4, 5, 6]
    assert all(case_id is not None for v, _, case_id in versions if v > 1)
    assert all(case_id is None for _, _, case_id in _versions(trip_world))
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s AND action_type='itinerary.apply' "
                    "AND status='succeeded'", (case_world["tenant"],))
        assert cur.fetchone()[0] == 5


# ── 재요청 — 다른 안 · 자유 문장 · 되돌리기 ─────────────────────
def test_re_requests_run_through_cases(case_world):
    _run_case_day(case_world)
    engine, trip_id, customer = case_world["engine"], case_world["trip_id"], case_world["customer"]
    trip, items = _latest(case_world)
    lunch = next(i for i in items if i.seq == 5)
    choice = lunch.detail["alternates"][0]["key"]

    swapped = engine.message(customer_id=customer, trip_id=trip_id, text="화면에서 다른 안 선택",
                             request_id="swap-1", part_id=lunch.item_id, base_version=trip["version"],
                             request={"type": "change", "choice": choice})
    assert swapped["case_status"] == "resolved" and swapped["owner_team_id"] == "dining", swapped
    assert _latest(case_world)[0]["version"] == 7

    # ★「다른 안으로 바꿔줘」 — 문장에 대상이 없다. 방금 바꾼 항목(점심)이 대상이다
    free = engine.message(customer_id=customer, trip_id=trip_id, text="다른 안으로 바꿔줘", request_id="swap-2")
    assert free["classification"]["issue_code"] == "other"
    assert free["case_status"] == "resolved" and free["owner_team_id"] == "dining", free
    assert _latest(case_world)[0]["version"] == 8

    rolled = engine.message(customer_id=customer, trip_id=trip_id, text="6번 일정으로 되돌려 주세요",
                            request_id="rollback-1", base_version=8,
                            request={"type": "rollback", "to_version": 6})
    assert rolled["case_status"] == "resolved", rolled
    trip, items = _latest(case_world)
    assert trip["version"] == 9 and _shape(items) == _shape(_items_at(case_world, 6))

    # 같은 요청 id 는 Case 를 새로 열지 않고 일정도 안 민다
    again = engine.message(customer_id=customer, trip_id=trip_id, text="6번 일정으로 되돌려 주세요",
                           request_id="rollback-1", base_version=8,
                           request={"type": "rollback", "to_version": 6})
    assert again["case_id"] == rolled["case_id"] and _latest(case_world)[0]["version"] == 9


def _items_at(world, version):
    with get_connection() as conn:
        return world["store"].items(conn, world["trip_id"], version)


# ── 막는 것 ────────────────────────────────────────────────────
def test_a_stale_base_version_is_escalated_not_applied(case_world):
    _run_case_day(case_world)
    trip, items = _latest(case_world)
    lunch = next(i for i in items if i.seq == 5)
    view = case_world["engine"].message(customer_id=case_world["customer"], trip_id=case_world["trip_id"],
                                        text="화면에서 다른 안 선택", request_id="stale-1", part_id=lunch.item_id,
                                        base_version=trip["version"] - 1, request={"type": "change"})
    assert view["case_status"] == "escalated" and view["escalation"]["guardrail"] == "itinerary_stale", view
    assert _latest(case_world)[0]["version"] == trip["version"]


def test_another_customers_trip_is_not_found(case_world):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                    (case_world["tenant"], "someone-else"))
        stranger = cur.fetchone()[0]
        conn.commit()
    with get_connection() as conn, pytest.raises(SubjectNotFound):
        resolve_subject(conn, tenant_id=case_world["tenant"], customer_id=stranger,
                        subject_ref={"kind": "trip", "id": str(case_world["trip_id"])})


def test_the_same_disruption_opens_one_case(case_world):
    case_world["clock"].now = _at("09:00")
    first = case_world["engine"].tick()
    assert len(first.opened) == 1
    # 고친 뒤에는 항목이 바뀌어 같은 사건이 다시 안 걸린다. 고치기 전 같은 항목이면 같은 Case 로 모인다
    with get_connection() as conn:
        assert repository.get_case(conn, tenant_id=case_world["tenant"],
                                   case_id=first.opened[0]["case_id"])["status"] == "resolved"
    second = case_world["engine"].tick()
    assert second.opened == [] and _latest(case_world)[0]["version"] == 2


# ── 실제 Gemma 처럼 틀리게 분류해도 담당이 맞는가 ─────────────────
def _gemma_like_classifier(message: str) -> dict[str, str]:
    """★2026-09-17 실제 gemma4:12b 실측(문장마다 3회 같은 결과)을 흉내 낸다 — 접두가 자주 빗나간다."""
    if "늦" in message:
        return {"intent": "incident_report", "issue_code": "activity_time_conflict", "sentiment": "negative"}
    if "휴무" in message:
        return {"intent": "incident_report", "issue_code": "dining_other", "sentiment": "negative"}
    if any(word in message for word in ("바꿔", "되돌려")):
        return {"intent": "adjust_reject", "issue_code": "booking_change_request", "sentiment": "neutral"}
    return {"intent": "other", "issue_code": "other", "sentiment": "neutral"}


def test_the_interpretation_routes_correctly_even_when_the_classifier_prefix_is_wrong(case_world):
    world = dict(case_world)
    check, route_events = _sources(world["clock"])
    world["engine"] = CaseEngine(tenant_id=world["tenant"], check=check, route_events=route_events,
                                 classifier=_gemma_like_classifier, report_extractor=_extractor,
                                 clock=world["clock"])
    outcomes = _run_case_day(world)
    for key, team in (("p3", "dining"), ("p7", "dining"), ("a8", "activity")):
        view = outcomes[key]
        assert view["case_status"] == "resolved" and view["owner_team_id"] == team, (key, view)
    assert outcomes["p3"]["classification"]["issue_code"] == "activity_time_conflict"   # 분류는 그대로 남는다
    assert _latest(world)[0]["version"] == 6

    engine, customer, trip_id = world["engine"], world["customer"], world["trip_id"]
    free = engine.message(customer_id=customer, trip_id=trip_id, text="다른 안으로 바꿔줘", request_id="g-swap")
    assert free["case_status"] == "resolved" and free["owner_team_id"] == "dining", free
    back = engine.message(customer_id=customer, trip_id=trip_id, text="6번 일정으로 되돌려 주세요",
                          request_id="g-back")
    assert back["case_status"] == "resolved", back
    trip, items = _latest(world)
    assert trip["version"] == 8 and _shape(items) == _shape(_items_at(world, 6))


def test_a_failing_interpreter_is_recorded_and_the_case_still_routes_by_classification(case_world):
    def broken(message: str) -> dict:
        raise TimeoutError("ollama down")

    world = dict(case_world)
    check, route_events = _sources(world["clock"])
    world["engine"] = CaseEngine(tenant_id=world["tenant"], check=check, route_events=route_events,
                                 classifier=_classifier, report_extractor=broken, clock=world["clock"])
    view = _say(world, "closed")
    assert view["owner_team_id"] == "dining", view          # 분류 접두(dining_hours)로 갔다
    assert view["case_status"] != "resolved", view           # 추출이 죽었는데 확답하지 않는다
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT state_json FROM customer_cases WHERE tenant_id=%s AND case_id=%s",
                    (world["tenant"], view["case_id"]))
        state = cur.fetchone()[0]
    assert state["interpretation"]["error"].startswith("TimeoutError"), state
    assert state.get("routing_hint_verified") is not True, state


def test_every_notice_carries_the_plan_link_whichever_path_made_it(case_world):
    """★`[2026-09-22]` Case 버전의 변경 통지에 링크가 빠져 있었다 — 화면에서 통지를 열어 보고 찾았다.

    시나리오용 여행 버전은 `TripStore.enqueue_notice` 가 붙여 주는데, Case 버전은 코어가 바깥함에
    **직접** 써서 그 자리를 지나지 않았다. 통지를 만드는 길이 여럿이라 **길마다** 본다.
    """
    from app.modules.travel_ops.plan_link import plan_url

    _run_case_day(case_world)
    link = plan_url(case_world["tenant"], case_world["trip_id"])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT dedupe_key, payload_json FROM outbox WHERE tenant_id=%s AND topic='trip.notice'",
                    (case_world["tenant"],))
        rows = cur.fetchall()
    assert rows, "통지가 하나도 없다"
    missing = [key for key, payload in rows if payload.get("plan_url") != link]
    assert missing == [], missing
