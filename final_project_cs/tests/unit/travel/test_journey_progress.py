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
