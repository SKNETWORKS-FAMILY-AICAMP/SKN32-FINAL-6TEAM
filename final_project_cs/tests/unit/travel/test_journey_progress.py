"""Customer progress must change the itinerary and suppress obsolete departures."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.domains.travel_ops.components.conversation.journey_progress import plan
from app.domains.travel_ops.components.conversation.chat_edit import ops_for
from app.domains.travel_ops.components.itinerary.itinerary import Item


def at(hm, day="2026-10-17"):
    return datetime.fromisoformat(f"{day}T{hm}:00+09:00")


def visit(seq, title, start, end, lat=37.485, lon=127.016):
    uid = uuid4()
    return Item(uuid4(), seq, "activity", title, uid, at(start), at(end),
                place={"place_id": str(uid), "name": title, "latitude": lat, "longitude": lon})


def walk(origin, destination, deadline, earliest):
    return {"starts_at": deadline - timedelta(minutes=5), "ends_at": deadline - timedelta(minutes=2),
            "eta_min": 3, "route": {"planned": "walk", "options": [{"id": "walk", "eta_min": 3}]},
            "departure_context": {"schema_version": 1, "from_place": origin, "to_place": destination}}, None


def test_leave_daiso_finishes_visit_and_departs_now_instead_of_answering_old_time():
    daiso = visit(1, "다이소", "21:00", "21:43")
    karaoke = visit(3, "노래방", "22:10", "23:40", lon=127.017)
    old_move = Item(uuid4(), 2, "mobility", "옛 이동", None, at("21:57"), at("21:58"))
    after, outcome = plan(trip={}, items=[daiso, old_move, karaoke], action="advance_trip", target=daiso,
                          now=at("21:02"), engine=walk)
    current = next(i for i in after if i.item_id == daiso.item_id)
    next_stop = next(i for i in after if i.item_id == karaoke.item_id)
    move = next(i for i in after if i.kind == "mobility")
    assert current.ends_at == at("21:02")
    assert current.detail["execution"]["state"] == "completed"
    assert move.starts_at == at("21:02")
    assert next_stop.starts_at == at("21:07")
    assert outcome["arrival_at"] == at("21:05").isoformat()
    assert old_move.item_id not in {i.item_id for i in after}
    assert outcome["state"] == "departing"


def test_now_at_2057_is_not_rounded_to_2100():
    daiso = visit(1, "다이소", "21:25", "22:08")
    decision = SimpleNamespace(action="change_time", item=daiso, raw={"anchor_kind": "now"}, minutes=None, query=None)
    ops, _ = ops_for(decision, items=[daiso], now=at("20:57"))
    assert ops[0].starts_at == "20:57"


def test_arrival_keeps_meal_history_and_records_current_visit_without_retravelling():
    meal = visit(1, "식사", "20:20", "20:58")
    daiso = visit(2, "다이소", "21:25", "22:08")
    after, outcome = plan(trip={}, items=[meal, daiso], action="arrive_item", target=daiso, now=at("20:54"))
    assert after[0].ends_at == at("20:54")
    assert after[0].detail["execution"]["state"] == "completed"
    assert after[1].starts_at == at("20:54")
    assert after[1].detail["execution"]["state"] == "arrived"
    assert outcome["state"] == "arrived"


def test_home_report_ends_today_and_preserves_tomorrow():
    daiso = visit(1, "다이소", "21:00", "21:43")
    karaoke = visit(3, "노래방", "22:10", "23:40")
    move = Item(uuid4(), 2, "mobility", "출발", None, at("21:57"), at("21:58"))
    tomorrow = visit(4, "내일 방문", "10:00", "11:00")
    tomorrow.starts_at = at("10:00", "2026-10-18")
    tomorrow.ends_at = at("11:00", "2026-10-18")
    after, _ = plan(trip={}, items=[daiso, move, karaoke, tomorrow], action="finish_day", target=None, now=at("21:09"))
    assert [i.detail.get("execution", {}).get("state") for i in after] == ["completed", "skipped", "skipped", None]
    from app.domains.travel_ops.components.watch.trip_reminders import plan_reminders, ReminderRules
    # This assertion uses the real reminder selector, not a duplicate selector.
    assert not plan_reminders(after, now=at("21:58"), rules=ReminderRules())


def test_missing_route_keeps_completed_fact_without_claiming_navigation_succeeded():
    first = visit(1, "다이소", "21:00", "21:43")
    second = visit(2, "노래방", "22:10", "23:40")
    after, outcome = plan(trip={}, items=[first, second], action="advance_trip", target=first, now=at("21:02"),
                          engine=lambda *args: (None, {"code": "source_failed"}))
    assert after[0].detail["execution"]["state"] == "completed"
    assert after[1].starts_at == at("22:10")
    assert outcome["navigation"] == "unverifiable"


def test_completion_then_a_separate_next_command_still_starts_navigation():
    daiso = visit(1, "다이소", "21:00", "21:43")
    karaoke = visit(2, "노래방", "22:10", "23:40", lon=127.017)
    done, _ = plan(trip={},items=[daiso,karaoke],action="complete_item",target=daiso,now=at("21:01"))
    after,outcome = plan(trip={},items=done,action="advance_trip",target=done[0],now=at("21:02"),engine=walk)
    assert after[0].ends_at == at("21:01")
    assert outcome["departure_at"] == at("21:02").isoformat()
    repeated,again = plan(trip={},items=after,action="advance_trip",target=after[0],now=at("21:03"),engine=walk)
    assert repeated == after and again["status"] == "already_applied"


def test_repeating_the_same_arrival_does_not_move_its_actual_start_later():
    daiso=visit(1,"다이소","21:25","22:08")
    arrived,_=plan(trip={},items=[daiso],action="arrive_item",target=daiso,now=at("20:54"))
    after,outcome=plan(trip={},items=arrived,action="arrive_item",target=arrived[0],now=at("20:57"))
    assert after[0].starts_at==at("20:54")
    assert outcome["status"]=="already_applied"


def test_finishing_a_day_preserves_a_multi_day_hotel_stay():
    hotel=visit(1,"숙박","15:00","11:00")
    hotel.kind="lodging"
    hotel.ends_at=at("11:00","2026-10-19")
    shop=visit(2,"다이소","21:00","21:43")
    after,_=plan(trip={},items=[hotel,shop],action="finish_day",target=None,now=at("21:09"))
    assert after[0]==hotel and not after[0].detail.get("execution")
    assert after[1].detail["execution"]["state"]=="completed"


def test_booking_clocks_are_preserved_while_actual_arrival_is_recorded():
    booked=visit(1,"예약 방문","20:20","21:20")
    booked.booking_id=uuid4()
    after,_=plan(trip={},items=[booked],action="arrive_item",target=booked,now=at("20:25"))
    assert (after[0].starts_at,after[0].ends_at)==(booked.starts_at,booked.ends_at)
    assert after[0].detail["execution"]["actual_start"]==at("20:25").isoformat()


def test_home_after_last_reported_visit_completes_it_even_if_old_plan_was_later():
    market=visit(1,"이마트 슈퍼","22:10","23:40")
    after,_=plan(trip={},items=[market],action="finish_day",target=market,now=at("21:09"))
    assert after[0].detail["execution"]["state"]=="completed"
    assert after[0].detail["execution"]["start_unknown"] is True
    assert after[0].starts_at==after[0].ends_at==at("21:09")


def test_arriving_at_a_different_visit_rebuilds_its_outbound_route():
    meal=visit(1,"식사","20:20","20:58")
    shop=visit(3,"다이소","21:25","22:08")
    old=Item(uuid4(),2,"mobility","옛 식당 이동",None,at("21:02"),at("21:13"))
    after,outcome=plan(trip={},items=[meal,old,shop],action="arrive_item",target=meal,now=at("20:22"),engine=walk)
    move=next(i for i in after if i.kind=="mobility")
    assert old.item_id!=move.item_id and move.detail.get("departure_context")
    assert outcome["state"]=="arrived"


def test_starting_the_next_visit_now_advances_from_the_reported_current_visit():
    from app.domains.travel_ops.components.conversation.decision_unit import decide, Stop
    current=visit(1,"식사","20:22","21:00")
    current.detail={"execution":{"state":"arrived"}}
    target=visit(2,"다이소","21:25","22:08")
    class Model:
        def structured(self,*args,**kwargs):
            return {"action":"change_time","target_item":"i2","target_change":"none",
                    "fact":"none","anchor_kind":"now","minutes":0,"choices":[]}
    decision=decide(Model(),stops=[Stop("i1",current),Stop("i2",target)],changes=[],history=[],
        selected_item_id=None,message="다이소 일정을 지금으로 옮겨줘",now=at("20:50"))
    assert decision.action=="advance_trip" and decision.item.item_id==current.item_id


def test_missing_notification_question_reads_the_unique_next_route_without_editing():
    from app.domains.travel_ops.components.conversation.decision_unit import decide, Stop
    origin=visit(1,"출발점","20:00","20:10")
    meal=visit(2,"식당","20:25","21:03")
    class Model:
        def structured(self,*args,**kwargs):
            return {"action":"other","target_item":"none","target_change":"none","fact":"none","minutes":0,"choices":[]}
    decision=decide(Model(),stops=[Stop("i1",origin),Stop("i2",meal)],changes=[],history=[],
        selected_item_id=None,message="알림 준다며 왜 안 줘",now=at("20:12"))
    assert decision.action=="answer_fact" and decision.fact=="move" and decision.item.item_id==meal.item_id
    from app.domains.travel_ops.components.conversation.read_requests import reply
    meal.seq=3
    move=Item(uuid4(),2,"mobility","이동",None,at("20:18"),at("20:23"),
        detail={"route_def":{"planned":"walk","options":[{"id":"walk","label":"도보","eta_min":5}]}})
    result,_,_=reply(decision,items=[origin,move,meal],message="알림 준다며 왜 안 줘",selected=None,
        turns=[],version=1,now=at("20:12"),context_now=at("20:12"),ttl_seconds=1800,place_source=None)
    assert "출발" in result["text"] and "식당" in result["text"] and "확인하지 못" not in result["text"]


def test_arrival_search_uses_previous_known_stop_instead_of_unvisited_new_meal():
    from app.domains.travel_ops.components.conversation.journey_progress import arrival_anchor
    station=visit(1,"출발점","20:00","20:10",lat=37.4849,lon=127.0162)
    unvisited=visit(2,"아직 가지 않은 대체 식당","20:25","21:03",lat=37.478,lon=126.99)
    assert arrival_anchor([station,unvisited],unvisited,None,at("20:22"))==(37.4849,127.0162)

# ── `[2026-10-22 사용자 결정 — ST4F-716]` 웹 「끝났어요 → 바로 진행」: 앞당기기 전 운영시간 확인 · 계산은 트랜잭션 밖 ──

def hours_of(attributes):
    from app.domains.travel_ops.components.intake.hours import HoursFacts

    def read(item, start, end):
        return HoursFacts(True, dict(attributes))
    return read


def test_st4f716_next_visit_starts_at_its_opening_time_not_before_it():
    bukchon = visit(1, "북촌한옥마을", "10:00", "11:30")
    insadong = visit(2, "인사동", "12:00", "13:00", lon=127.02)
    after, outcome = plan(trip={}, items=[bukchon, insadong], action="advance_trip", target=bukchon,
                          now=at("10:50"), engine=walk, hours=hours_of({"hours": ["11:30", "21:00"]}))
    moved = next(i for i in after if i.item_id == insadong.item_id)
    assert (moved.starts_at, moved.ends_at) == (at("11:30"), at("12:30"))      # 도착 10:53 + 여유 → 10:55 는 여는 시각 전이다
    assert outcome["next_start_at"] == at("11:30").isoformat()
    assert outcome["hours_check"] == "checked" and outcome["state"] == "departing"
    assert "11:30에 문을 열어 11:30 시작으로 앞당겼어요" in outcome["text"]


def test_st4f716_opening_after_the_planned_start_keeps_the_next_visit_and_records_the_end():
    bukchon = visit(1, "북촌한옥마을", "10:00", "11:30")
    insadong = visit(2, "인사동", "12:00", "13:00", lon=127.02)
    after, outcome = plan(trip={}, items=[bukchon, insadong], action="advance_trip", target=bukchon,
                          now=at("10:50"), engine=walk, hours=hours_of({"hours": ["12:30", "21:00"]}))
    assert outcome["navigation"] == "opens_later" and "12:30" in outcome["text"]
    kept = next(i for i in after if i.item_id == insadong.item_id)
    assert (kept.starts_at, kept.ends_at) == (insadong.starts_at, insadong.ends_at)
    done = next(i for i in after if i.item_id == bukchon.item_id)
    assert done.ends_at == at("10:50") and done.detail["execution"]["state"] == "completed"


def test_st4f716_new_break_time_conflict_keeps_times_and_says_why():
    bukchon = visit(1, "북촌한옥마을", "10:00", "11:30")
    insadong = visit(2, "인사동", "12:00", "13:00", lon=127.02)
    after, outcome = plan(trip={}, items=[bukchon, insadong], action="advance_trip", target=bukchon, now=at("10:50"),
                          engine=walk, hours=hours_of({"hours": ["09:00", "21:00"], "break": ["10:30", "11:30"]}))
    assert outcome["navigation"] == "hours_conflict" and "브레이크 타임" in outcome["text"]
    kept = next(i for i in after if i.item_id == insadong.item_id)
    assert kept.starts_at == at("12:00")
    assert not any(i.kind == "mobility" for i in after)                        # 새 이동을 만들지 않았다


def test_st4f716_violation_already_in_the_plan_does_not_block_the_move():
    bukchon = visit(1, "북촌한옥마을", "10:00", "11:30")
    insadong = visit(2, "인사동", "12:00", "13:00", lon=127.02)
    # 원래 12:00~13:00 도 13:00 마감에 걸려 있다(원래부터 있던 위반 — 이 변경의 탓이 아니다)
    after, outcome = plan(trip={}, items=[bukchon, insadong], action="advance_trip", target=bukchon,
                          now=at("10:50"), engine=walk, hours=hours_of({"hours": ["09:00", "12:30"]}))
    assert "navigation" not in outcome
    assert next(i for i in after if i.item_id == insadong.item_id).starts_at == at("10:55")


def test_st4f716_unreadable_hours_moves_without_claiming_a_check():
    bukchon = visit(1, "북촌한옥마을", "10:00", "11:30")
    insadong = visit(2, "인사동", "12:00", "13:00", lon=127.02)

    def broken(item, start, end):
        raise RuntimeError("db down")
    after, outcome = plan(trip={}, items=[bukchon, insadong], action="advance_trip", target=bukchon,
                          now=at("10:50"), engine=walk, hours=broken)
    assert outcome["hours_check"] == "unavailable" and outcome["state"] == "departing"
    assert next(i for i in after if i.item_id == insadong.item_id).starts_at == at("10:55")


def test_st4f716_apply_routes_and_checks_hours_outside_the_save_transaction(monkeypatch):
    from contextlib import contextmanager
    from app.domains.travel_ops.components.conversation import journey_progress
    from app.domains.travel_ops.components.conversation.decision_unit import Decision

    bukchon = visit(1, "북촌한옥마을", "10:00", "11:30")
    insadong = visit(2, "인사동", "12:00", "13:00", lon=127.02)
    state = {"open": False, "saved": None, "calls": []}

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        @contextmanager
        def transaction(self):
            state["open"] = True
            try:
                yield
            finally:
                state["open"] = False

    class Store:
        tenant_id = "t"

        def version_for_request(self, conn, trip_id, key):
            return None

        def latest(self, conn, trip_id):
            return {"version": 2}, [bukchon, insadong]

        def append_version(self, conn, *, trip_id, base_version, items, reason, causes):
            assert state["open"] and base_version == 2
            state["saved"] = items
            return 3

        def enqueue_notice(self, conn, *, trip_id, version, payload):
            assert state["open"]

    def engine(*args):
        state["calls"].append(("route", state["open"]))
        return walk(*args)

    def hours(item, start, end):
        state["calls"].append(("hours", state["open"]))
        return hours_of({"hours": ["09:00", "21:00"]})(item, start, end)

    monkeypatch.setattr(journey_progress, "_planner", lambda trip, supplied=None: engine)
    decision = Decision(action="advance_trip", item=bukchon, change=None, fact="", minutes=None, question="")
    out = journey_progress.apply(store=Store(), connect=Conn, trip_id=uuid4(), base_version=2, decision=decision,
                                 now=at("10:50"), request_id="r1", message="웹 「끝났어요」 · advance_trip", hours=hours)
    assert out["version"] == 3 and out["state"] == "departing"
    assert state["calls"] and all(open_ is False for _, open_ in state["calls"])   # 계산 · 조회 중엔 트랜잭션이 없다
    assert next(i for i in state["saved"] if i.item_id == insadong.item_id).starts_at == at("10:55")


def test_st4f716_a_tight_goal_is_loosened_instead_of_failing_the_move():
    """`[2026-10-22 실서버 확인]` 계산기가 「지금 출발」 목표를 3분 빠듯하게 받아 후보 없음(`arrive_late`)을 내면 목표를 늦춰 다시 묻는다(전에는 바로 실패)."""
    gyeongbok = visit(1, "경복궁", "15:10", "16:40")
    insadong = visit(2, "인사동", "17:20", "18:20", lon=127.02)

    def rush(origin, destination, goal, earliest):
        depart = goal - timedelta(minutes=25 if goal >= at("17:00") else 28)     # 늦은 시각엔 덜 붐빈다 — 목표를 거꾸로 맞추면 3분 넘친다
        if depart < earliest:
            return None, {"code": "arrive_late"}
        return {"starts_at": depart, "ends_at": goal - timedelta(minutes=10), "eta_min": 15,
                "route": {"planned": "walk", "options": [{"id": "walk", "eta_min": 15}]}}, None
    after, outcome = plan(trip={}, items=[gyeongbok, insadong], action="advance_trip", target=gyeongbok,
                          now=at("15:52"), engine=rush)
    assert outcome["state"] == "departing", outcome
    assert outcome["departure_at"] == at("15:54").isoformat()                  # 지금부터 2분 안 — 「지금 출발」로 받는다
    assert next(i for i in after if i.item_id == insadong.item_id).starts_at == at("16:22")


def test_st4f716_particles_follow_the_final_consonant():
    """`[2026-10-22 사용자 결정 — A]` 「을(를)」 · 「은(는)」 · 「이(가)」 · 「(으)로」 대신 이름 받침에 맞는 조사(채팅 · 알림 · 웹 토스트가 같은 문장)."""
    store = visit(1, "다이소", "21:00", "21:43")                                     # 받침 없음 → 를 · 는
    lane = visit(2, "쌈지길", "22:10", "23:40", lon=127.017)                         # ㄹ 받침 → 로 · 이
    _, moved = plan(trip={}, items=[store, lane], action="advance_trip", target=store, now=at("21:02"), engine=walk)
    assert moved["text"].startswith("다이소를 21:02에 마쳤고, 지금 쌈지길로 이동해요."), moved["text"]
    _, kept = plan(trip={}, items=[store, lane], action="complete_item", target=store, now=at("21:02"))
    assert kept["text"] == "다이소를 21:02에 완료한 것으로 반영했어요."
    bukchon = visit(1, "북촌한옥마을", "10:00", "11:30")                               # ㄹ 받침 → 은
    ssamzie = visit(2, "쌈지길", "12:00", "13:00", lon=127.02)
    _, refused = plan(trip={}, items=[bukchon, ssamzie], action="advance_trip", target=bukchon, now=at("10:50"),
                      engine=walk, hours=hours_of({"hours": ["09:00", "21:00"], "break": ["10:30", "11:30"]}))
    assert refused["text"] == "북촌한옥마을은 완료했어요. 지금 가면 쌈지길이 브레이크 타임에 걸려 이동 시각은 바꾸지 않았어요."
    _, opened = plan(trip={}, items=[bukchon, visit(2, "인사동", "12:00", "13:00", lon=127.02)], action="advance_trip", target=bukchon,
                     now=at("10:50"), engine=walk, hours=hours_of({"hours": ["11:30", "21:00"]}))
    assert opened["text"] == "북촌한옥마을을 10:50에 마쳤어요. 인사동은 11:30에 문을 열어 11:30 시작으로 앞당겼어요."
    for said in (moved, kept, refused, opened):
        assert not any(mark in said["text"] for mark in ("(를)", "(는)", "(가)", "(으)"))
