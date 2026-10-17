"""공통 숙소는 여행 전체를 보고 고르며 날짜별 조식·보호·되돌리기 경계를 지킨다."""
from copy import deepcopy

import pytest

from app.domains.travel_ops.components.intake import autofix, candidates, lodging_context as context, pipeline
from .test_intake_lodging_candidates import HOTEL, review, sources  # noqa: F401


def trip():
    view = review(meal=True)
    breakfast, visit = view["items"]
    second = {**deepcopy(breakfast), "id": "0-2", "index": 2, "date": "2030-01-06"}
    far = {**deepcopy(visit), "id": "0-3", "index": 3, "date": second["date"], "title": "다음 날 방문지",
           "place": {**visit["place"], "name": "다음 날 방문지", "latitude": 37.572, "longitude": 126.985}}
    view["items"] += [second, far]
    return view


def test_both_dates_search_from_the_whole_trip_center(sources):
    calls, kakao = sources
    view = trip()
    hotels = view["items"][::2]
    orders = []
    for hotel in hotels:
        got = candidates.alternatives(None, tenant_id="travel", review=view, item=hotel, kakao=kakao, use_engine=False)
        orders.append([x["place"]["name"] for x in got["candidates"]])
        assert all(x["reference"] == "여행 전체 방문지(평균 직선거리)" for x in got["candidates"])
    assert orders[0] == orders[1]
    assert all(ref == pytest.approx((37.5758, 126.981)) for ref, _, _ in calls)


def test_scoped_recommendation_fills_both_breakfasts_and_preserves_other_stops(sources):
    _, kakao = sources
    view = trip()
    original = deepcopy(view)
    got = autofix.plan(None, tenant_id="travel", review=view, kakao=kakao, use_engine=False, item_id="0-2")
    assert {x["id"] for x in got["changes"]} == {"0-0", "0-2"}, got
    assert {x["to"]["place"]["name"] for x in got["changes"]} == {HOTEL["name"]}
    assert all(x["to"]["place"]["kind"] == "dining" and x["to"]["ends_at"] < "10:00" for x in got["changes"])
    assert view == original


def test_joint_fit_rejects_candidate_that_only_fits_one_date(sources, monkeypatch):
    _, kakao = sources
    fit = autofix._fit_window
    monkeypatch.setattr(autofix, "_fit_window", lambda conn, tenant, item, *args, **kw:
                        "stay" if item["date"] == "2030-01-06" else fit(conn, tenant, item, *args, **kw))
    got = autofix.plan(None, tenant_id="travel", review=trip(), kakao=kakao, use_engine=False, item_id="0-0")
    assert got["changes"] == [] and len(got["kept"]) == 2


def test_fourth_hotel_can_win_when_the_first_three_do_not_fit_both_dates(sources, monkeypatch):
    _, kakao = sources
    hotels = [{**HOTEL, "name": f"숙소 {n}", "content_type_id": "32"} for n in range(6)]
    monkeypatch.setattr(candidates, "_catalog_places", lambda *a, **kw: hotels)
    fit = autofix._fit_window
    monkeypatch.setattr(autofix, "_fit_window", lambda conn, tenant, item, place, *args, **kw:
                        "stay" if place["name"] != "숙소 3" else fit(conn, tenant, item, place, *args, **kw))
    got = autofix.plan(None, tenant_id="travel", review=trip(), use_engine=False, item_id="0-0")
    assert {x["to"]["place"]["name"] for x in got["changes"]} == {"숙소 3"}, got
    assert {x["id"] for x in got["changes"]} == {"0-0", "0-2"}


def test_cold_route_calculation_budget_is_shared_by_day_not_exhausted_across_all_dates(sources, monkeypatch):
    from app.domains.travel_ops.components.intake import review as review_module
    from datetime import datetime, timedelta

    clock = [0.0]
    monkeypatch.setattr(review_module.time, "monotonic", lambda: clock[0])
    hotels = [{**HOTEL, "name": f"숙소 {n}", "latitude": HOTEL["latitude"] + n * 0.0001, "content_type_id": "32"} for n in range(3)]
    monkeypatch.setattr(candidates, "_catalog_places", lambda *a, **kw: hotels)
    monkeypatch.setattr(context, "score", lambda place, points: int(place["name"].split()[-1]))

    def engine(a, b, arrive, not_before=None):
        clock[0] += 6.0
        return {"ok": True}, None

    def fit(conn, tenant, item, place, prev, nxt, start, duration, budget, **kwargs):
        route = kwargs["engine_next"]
        point = {"lat": place["latitude"], "lon": place["longitude"]}
        target = {"lat": nxt["place"]["latitude"], "lon": nxt["place"]["longitude"]}
        got, _ = route(point, target, datetime.fromisoformat(item["date"] + "T10:00:00"))
        if got is None:
            return "travel"
        if place["name"] != "숙소 2" and item["date"] == "2030-01-06":
            return "stay"
        return start, start + timedelta(minutes=30), False

    monkeypatch.setattr(autofix, "_fit_window", fit)
    got = autofix.plan(None, tenant_id="travel", review=trip(), engine=engine, item_id="0-0")
    assert {c["to"]["place"]["name"] for c in got["changes"]} == {"숙소 2"}, got
    assert {c["id"] for c in got["changes"]} == {"0-0", "0-2"}
    assert clock[0] == 36.0


def test_named_stay_is_reused_instead_of_searching_another_hotel(sources):
    calls, kakao = sources
    view = trip()
    stay = {**deepcopy(view["items"][0]), "id": "1-0", "index": 0, "source_id": "other", "title": "이미 정한 숙소",
            "kind": "lodging", "date": "2030-01-04", "end_date": "2030-01-07", "starts_at": "15:00", "ends_at": "11:00",
            "parts": None, "place": dict(HOTEL), "status": "keep", "rows": []}
    view["items"].insert(0, stay)
    got = autofix.plan(None, tenant_id="travel", review=view, kakao=kakao, use_engine=False, item_id="0-0")
    assert {x["id"] for x in got["changes"]} == {"0-0", "0-2"}
    assert all(x["to"]["place"]["name"] == HOTEL["name"] for x in got["changes"])
    assert not calls and not kakao.asked


def test_two_explicit_stay_periods_are_kept_separate():
    view = trip()
    stays = [{**deepcopy(view["items"][0]), "id": f"1-{i}", "title": f"정한 숙소 {i}", "kind": "lodging",
              "date": f"2030-01-0{4+i}", "end_date": f"2030-01-0{5+i}", "starts_at": "15:00", "ends_at": "11:00",
              "parts": None, "place": {**HOTEL, "name": f"숙소 {i}"}} for i in range(2)]
    view["items"] += stays
    assert {x["id"] for x in context.group_for(view["items"], view["items"][0])} == {"1-0", "0-0"}
    assert {x["id"] for x in context.group_for(view["items"], view["items"][2])} == {"1-1", "0-2"}


@pytest.mark.parametrize("protection", ["locked", "booked", "vendor_booking"])
def test_protected_common_stay_blocks_conflicting_direct_pick(protection):
    view = trip()
    view["items"][2].update(place=dict(HOTEL), **{protection: True})
    pick = {**HOTEL, "name": "다른 숙소", "source": "customer_pick"}
    with pytest.raises(pipeline.IntakeConflict):
        pipeline._link_stay_places(view, [("source", "items[0].place", pick, {}, None)])


def test_direct_pick_links_place_with_meal_kind():
    out = pipeline._link_stay_places(trip(), [("source", "items[0].place", dict(HOTEL), {}, None)])
    assert len(out) == 2
    assert out[1][1] == "items[2].place" and out[1][2]["name"] == HOTEL["name"]
    assert out[1][2]["kind"] == "dining" and out[1][2]["category"] == "숙소 안 식사"


def test_existing_daily_mismatch_is_reported_and_repaired(sources):
    _, kakao = sources
    view = trip()
    for n, hotel in enumerate(view["items"][::2]):
        hotel.update(parts=None, place={**HOTEL, "name": f"기존 숙소 {n}"}, place_state="customer", status="keep")
    context.annotate(view["items"])
    assert all(x["status"] == "review" and x["lodging_group"]["place"] is None for x in view["items"][::2])
    got = autofix.plan(None, tenant_id="travel", review=view, kakao=kakao, use_engine=False, item_id="0-0")
    assert {x["to"]["place"]["name"] for x in got["changes"]} == {HOTEL["name"]}


def test_conflicting_protected_stays_are_never_silently_chosen(sources):
    _, kakao = sources
    view = trip()
    for n, hotel in enumerate(view["items"][::2]):
        hotel.update(place={**HOTEL, "name": f"고정 숙소 {n}"}, locked=True)
    got = autofix.plan(None, tenant_id="travel", review=view, kakao=kakao, use_engine=False, item_id="0-0")
    assert got["changes"] == [] and {x["reason"] for x in got["kept"]} == {"conflicting_stays"}
