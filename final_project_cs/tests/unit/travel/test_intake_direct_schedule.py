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
