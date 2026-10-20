"""직접 장소 교체: 이동시간, 잠금·예약, 같은 날 경계, 계산 실패."""
from datetime import timedelta

import pytest

from app.domains.travel_ops.components.intake import direct_schedule as schedule
from app.domains.travel_ops.components.intake import hours


def row(index, start, end, **kw):
    return {"source_id": "source", "index": index, "date": "2026-10-15", "start": start, "end": end,
            "title": "호텔" if index == 0 else "다음 일정", "kind": "activity", "locked": False, "booked": None,
            "booking_no": None, "place": {"name": f"장소{index}", "latitude": 37.57, "longitude": 126.98 + index * .001}, **kw}


def walk11(a, b, arrive, not_before=None):
    depart = arrive - timedelta(minutes=11)
    return {"starts_at": depart, "ends_at": arrive, "eta_min": 11,
            "route": {"planned": "walk", "options": [{"id": "walk", "eta_min": 11, "walk_m": 880, "label": "도보 11분"}]}}, None


@pytest.fixture(autouse=True)
def no_hours(monkeypatch):
    monkeypatch.setattr(hours, "facts_for", lambda *a: hours.HoursFacts(False, why_unknown="시험에는 운영시간 없음"))


def fit(rows, touched={('source', 0)}, engine=walk11):
    return schedule.fit(None, tenant_id="test", rows=rows, touched=touched, engine=engine, use_engine=False)


def values(changes):
    return {c["field"]: c["value"] for c in changes}


def test_hotel_pick_pushes_next_and_preserves_stay():
    got = fit([row(0, "09:00", "10:00"), row(1, "10:05", "11:05"), row(2, "11:40", "12:40")])
    assert values(got) == {"items[1].starts_at": "10:15", "items[1].ends_at": "11:15"}
    assert all(c["basis"] == "timetable" for c in got)


def test_delaying_next_stop_preserves_preceding_inferred_end_for_reassembly():
    rows = [row(0, "09:00", "10:00", provenance={"ends_at": {"rule": "intake.default_duration"}}),
            row(1, "10:00", "11:00")]
    got = fit(rows, touched={('source', 1)})
    assert values(got) == {"items[0].ends_at": "10:00", "items[1].starts_at": "10:15", "items[1].ends_at": "11:15"}
    assert rows[0]["end"] == "10:00"  # 원본을 늘려 이동시간을 지우지 않는다.


def test_cascades_through_following_unlocked_items():
    got = fit([row(0, "09:00", "10:00"), row(1, "10:05", "11:05"), row(2, "11:10", "12:10")])
    assert values(got)["items[2].starts_at"] == "11:30"
    assert values(got)["items[2].ends_at"] == "12:30"


@pytest.mark.parametrize("protection", [{"locked": True}, {"booked": True}, {"booking_no": "RES-1"}])
def test_fixed_next_pulls_flexible_previous_back(protection):
    got = fit([row(0, "09:00", "10:00"), row(1, "10:05", "11:05", **protection)])
    assert values(got) == {"items[0].starts_at": "08:50", "items[0].ends_at": "09:50"}


def test_two_fixed_anchors_cannot_fit_and_input_is_unchanged():
    rows = [row(0, "09:00", "10:00", locked=True), row(1, "10:05", "11:05", booked=True)]
    with pytest.raises(schedule.ScheduleConflict, match="잠금·예약"):
        fit(rows)
    assert rows[0]["start"] == "09:00" and rows[1]["start"] == "10:05"


def test_no_pushing_into_next_day():
    got = fit([row(0, "22:00", "23:00"), row(1, "23:05", "23:59")])
    assert values(got) == {"items[0].starts_at": "21:50", "items[0].ends_at": "22:50"}


def test_no_room_before_day_start_keeps_original():
    with pytest.raises(schedule.ScheduleConflict, match="하루"):
        fit([row(0, "00:00", "01:00"), row(1, "01:05", "02:05", locked=True)])


def test_unrelated_next_day_stays_untouched():
    got = fit([row(0, "09:00", "10:00"), row(1, "10:05", "11:05"),
               row(2, "09:00", "10:00", date="2026-10-16")])
    assert not any(c["field"].startswith("items[2]") for c in got)


def test_engine_error_is_not_an_automatic_success():
    def failed(*args):
        raise TimeoutError("test")
    with pytest.raises(schedule.ScheduleConflict) as raised:
        fit([row(0, "09:00", "10:00"), row(1, "10:05", "11:05")], engine=failed)
    assert raised.value.code == "schedule_check_failed"


def test_disabled_engine_keeps_estimate_provenance():
    got = fit([row(0, "09:00", "10:00"), row(1, "10:00", "11:00")], engine=None)
    assert got and all(c["basis"] == "estimate" for c in got)


def test_shift_cannot_break_known_closing_time(monkeypatch):
    monkeypatch.setattr(hours, "facts_for", lambda *a: hours.HoursFacts(True, {"hours": ["09:00", "11:10"]}))
    with pytest.raises(schedule.ScheduleConflict, match="운영시간"):
        fit([row(0, "09:00", "10:00"), row(1, "10:05", "11:05")])


def test_closing_time_uses_free_time_before_the_changed_hotel(monkeypatch):
    def facts(conn, tenant, place, *args):
        return hours.HoursFacts(True, {"hours": ["00:00", "23:59"] if place["name"] == "장소0" else ["09:00", "11:10"]})
    monkeypatch.setattr(hours, "facts_for", facts)
    got = fit([row(0, "09:00", "10:00"), row(1, "10:05", "11:05")])
    assert values(got) == {"items[0].starts_at": "08:50", "items[0].ends_at": "09:50"}


def test_chosen_mode_is_used_for_reflow(monkeypatch):
    from app.domains.travel_ops.components.intake import review
    asked = []
    def factory(party=None, modes=None):
        asked.append(modes)
        if modes is None:
            return walk11
        def taxi(a, b, arrive, not_before=None):
            return {"starts_at": arrive - timedelta(minutes=3), "ends_at": arrive, "eta_min": 3,
                    "route": {"planned": "taxi", "options": [{"id": "taxi", "eta_min": 3, "label": "택시 3분"}]}}, None
        return taxi
    monkeypatch.setattr(review, "default_engine", factory)
    got = schedule.fit(None, tenant_id="test", rows=[row(0, "09:00", "10:00"), row(1, "10:02", "11:02")],
                       touched={("source", 0)}, mode_picks={"0-0~0-1": "taxi"})
    # 도보 외 수단은 기존 시간표 맞춤의 5분 탐색·올림 여유까지 포함한다.
    assert values(got) == {"items[1].starts_at": "10:10", "items[1].ends_at": "11:10"}
    assert ["taxi"] in asked


def test_a_chosen_mode_that_cannot_reach_falls_back_to_the_recommended_engine(monkeypatch):
    """★x600 실서버 확인(2026-10-15): 저장된 도보 구간이 바뀐 장소 사이에서 닿지 않으면 「고른 수단 안의 후보가 없다」로 저장을 막았다 — 추천 수단으로 돌아가 계산한다."""
    from app.domains.travel_ops.components.intake import review

    def factory(party=None, modes=None):
        if modes is None:
            return walk11
        def unreachable(a, b, arrive, not_before=None):
            return None, {"code": "no_candidate", "reason": "고른 수단(walk) 안의 후보가 없다"}
        return unreachable
    monkeypatch.setattr(review, "default_engine", factory)
    got = schedule.fit(None, tenant_id="test", rows=[row(0, "09:00", "10:00"), row(1, "10:05", "11:05")],
                       touched={("source", 0)}, mode_picks={"0-0~0-1": "walk"})
    assert values(got) == {"items[1].starts_at": "10:15", "items[1].ends_at": "11:15"}


def slow_clock_engine(monkeypatch, seconds):
    """실제 대기 없이 계산기가 쓴 시간만 증가시킨다."""
    from types import SimpleNamespace
    from app.domains.travel_ops.components.intake import review

    clock, calls = [0.0], []
    monkeypatch.setattr(review, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    def engine(a, b, arrive, not_before=None):
        calls.append((a["name"], b["name"], arrive, not_before))
        clock[0] += seconds
        return walk11(a, b, arrive, not_before)
    return engine, calls


@pytest.mark.parametrize("mode", [None, "walk"])
def test_shared_hotel_gives_each_day_its_own_existing_budget(monkeypatch, mode):
    from app.domains.travel_ops.components.intake import review

    engine, calls = slow_clock_engine(monkeypatch, 12)
    monkeypatch.setattr(review, "default_engine", lambda *args: engine)
    rows = [row(0, "09:00", "10:00"), row(1, "11:00", "12:00"),
            row(2, "09:00", "10:00", date="2026-10-16"), row(3, "11:00", "12:00", date="2026-10-16")]
    picks = {"0-0~0-1": mode, "0-2~0-3": mode} if mode else None
    assert schedule.fit(None, tenant_id="test", rows=rows, touched={("source",0),("source",2)}, mode_picks=picks) == []
    assert len(calls) == 2


def test_completed_timetable_is_kept_when_its_call_uses_the_remaining_budget(monkeypatch):
    engine, calls = slow_clock_engine(monkeypatch, 21)
    assert fit([row(0, "09:00", "10:00"), row(1, "11:00", "12:00")], engine=engine) == []
    assert len(calls) == 1


def test_spent_budget_still_refuses_the_next_uncalculated_leg(monkeypatch):
    engine, calls = slow_clock_engine(monkeypatch, 11)
    rows = [row(0,"09:00","10:00"),row(1,"11:00","12:00"),row(2,"13:00","14:00"),row(3,"15:00","16:00")]
    with pytest.raises(schedule.ScheduleConflict) as refused:
        fit(rows, touched={("source",0),("source",1),("source",2)}, engine=engine)
    assert refused.value.code == "schedule_check_failed"
    assert len(calls) == 2


def breakfast_claims(end_evidence):
    return {"place": {"evidence": {"lodging_parts": {"lodging_meal": True}}},
            "ends_at": {"value": "10:00", "method": "customer", "evidence": end_evidence}}


def test_derived_hotel_breakfast_end_shrinks_without_moving_the_next_visit():
    rows = [row(0, "09:00", "10:00", kind="dining", claims=breakfast_claims({"via": "autofix"})),
            row(1, "10:05", "11:05")]
    changes = fit(rows)
    assert values(changes) == {"items[0].ends_at": "09:50"}
    assert changes[0]["derived_stay_end"] is True


@pytest.mark.parametrize("evidence", [{"source": "customer"}, {"text": "10:00", "source": "text"}])
def test_explicit_breakfast_end_is_not_shortened(evidence):
    changes = fit([row(0,"09:00","10:00",kind="dining",claims=breakfast_claims(evidence)),
                   row(1,"10:05","11:05")])
    assert values(changes) == {"items[1].starts_at": "10:15", "items[1].ends_at": "11:15"}


@pytest.mark.parametrize("protection", [{"booked":True}, {"locked":True}, {"booking_no":"RES-1"}])
def test_protected_breakfast_is_not_shortened(protection):
    changes = fit([row(0,"09:00","10:00",kind="dining",claims=breakfast_claims({"via":"autofix"}),**protection),
                   row(1,"10:05","11:05")])
    assert values(changes) == {"items[1].starts_at": "10:15", "items[1].ends_at": "11:15"}


def test_a_previous_derived_stay_end_remains_adjustable():
    changes = fit([row(0,"09:00","09:50",kind="dining",claims=breakfast_claims({"via":"direct_schedule","derived_stay_end":True})),
                   row(1,"10:00","11:00")])
    assert values(changes) == {"items[0].ends_at":"09:45"}


def test_derived_breakfast_is_not_shortened_below_the_existing_minimum():
    changes = fit([row(0,"09:00","09:30",kind="dining",claims=breakfast_claims({"via":"autofix"})),
                   row(1,"09:35","10:35")])
    assert values(changes) == {"items[1].starts_at":"09:45", "items[1].ends_at":"10:45"}


def test_single_hotel_breakfast_without_linked_place_parts_uses_the_original_title():
    changes = fit([row(0,"09:00","10:00",kind="dining",provenance={"ends_at":{"rule":"intake.default_duration"}}),
                   row(1,"10:05","11:05")])
    assert values(changes) == {"items[0].ends_at":"09:50"}


def test_ordinary_restaurant_does_not_use_the_hotel_breakfast_rule():
    changes = fit([row(0,"09:00","10:00",title="점심",kind="dining",provenance={"ends_at":{"rule":"intake.default_duration"}}),
                   row(1,"10:05","11:05")])
    assert values(changes) == {"items[0].ends_at":"10:00", "items[1].starts_at":"10:15", "items[1].ends_at":"11:15"}
    assert not any(c.get("derived_stay_end") for c in changes)


def test_engine_place_keys_match_the_review_item_ids():
    # `[2026-10-20 「대안 적용 13.9초」]` 이동 계산기의 요청 사이 재사용 칸은 장소 키까지 본다 — 시각 맞추기가 검사(`review.build`)와 같은 키
    #   (`원본 위치-번호`)로 물어야 바로 뒤 검사가 같은 구간을 다시 세지 않는다
    seen = []

    def engine(a, b, arrive, not_before=None):
        seen.append((a["key"], b["key"]))
        return walk11(a, b, arrive, not_before)
    fit([row(0, "09:00", "10:00", order=(2, 5, 0)), row(1, "10:05", "11:05", order=(2, 6, 1))], engine=engine)
    assert ("2-0", "2-1") in seen                                     # 시각을 고르는 탐색(`autofix` 의 prev · cand)은 도착 목표가 달라 따로 센다
    assert not any(":" in k for pair in seen for k in pair)          # 옛 키(`원본:번호`)는 쓰지 않는다
