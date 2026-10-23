"""출발 하한과 도착 목표는 표현 시간대가 달라도 같은 서울 운행일 축이다."""
from datetime import date, datetime, timedelta, timezone, tzinfo

import pytest

from app.domains.travel_ops.instances.mobility.engine import plan as P
from app.domains.travel_ops.instances.mobility.engine.timeutil import day_type_of
from .test_review_fixes_plan import _rt


UTC = timezone.utc
KST = timezone(timedelta(hours=9))
WEST = timezone(timedelta(hours=-5))


@pytest.mark.parametrize('utc,expected', [
    ('2026-10-18T10:00:00+00:00', (date(2026, 10, 18), 1140)),
    ('2026-10-18T15:00:00+00:00', (date(2026, 10, 18), 1440)),
    ('2026-10-18T15:30:00+00:00', (date(2026, 10, 18), 1470)),
    ('2026-10-18T18:59:59+00:00', (date(2026, 10, 18), 1679)),
    ('2026-10-18T19:00:00+00:00', (date(2026, 10, 19), 240)),
    ('2026-10-18T23:30:00+00:00', (date(2026, 10, 19), 510)),
])
def test_same_instant_has_same_service_day_in_every_timezone(utc, expected):
    instant = datetime.fromisoformat(utc)
    assert {P.service_day(instant.astimezone(zone)) for zone in (UTC, KST, WEST)} == {expected}
    wall = datetime.fromisoformat(P.iso_of(*expected))
    assert wall == instant.replace(second=0).astimezone(KST)


@pytest.mark.parametrize('wall,expected', [
    ('2026-10-18T19:00:00', (date(2026, 10, 18), 1140)),
    ('2026-10-19T00:30:00', (date(2026, 10, 18), 1470)),
    ('2026-10-19T03:59:59', (date(2026, 10, 18), 1679)),
    ('2026-10-19T04:00:00', (date(2026, 10, 19), 240)),
])
def test_naive_input_keeps_seoul_wall_clock_meaning(wall, expected):
    local = datetime.fromisoformat(wall)
    assert P.service_day(local) == P.service_day(local.replace(tzinfo=KST)) == expected


def test_tzinfo_without_offset_keeps_naive_meaning():
    class NoOffset(tzinfo):
        def utcoffset(self, dt):
            return None

    assert P.service_day(datetime(2026, 10, 18, 19, tzinfo=NoOffset())) == (date(2026, 10, 18), 1140)


def test_kst_cutoff_selects_monday_after_sunday_utc_evening():
    before = datetime.fromisoformat('2026-10-18T18:59:59+00:00')
    after = before + timedelta(seconds=1)
    assert day_type_of(P.service_day(before)[0], set()) == 'holiday'
    assert day_type_of(P.service_day(after)[0], set()) == 'weekday'


@pytest.mark.parametrize('utc,expected', [
    ('2026-10-18T08:19:52+00:00', (date(2026, 10, 18), 1040)),
    ('2026-10-18T14:59:01+00:00', (date(2026, 10, 18), 1440)),
    ('2026-10-18T18:59:01+00:00', (date(2026, 10, 19), 240)),
])
def test_departure_floor_rounds_up_on_the_same_kst_axis(utc, expected):
    instant = datetime.fromisoformat(utc)
    assert P.Planner._floor_min(instant) == P.Planner._floor_min(instant.astimezone(KST)) == expected


def _walk_planner(monkeypatch):
    planner = P.Planner(_rt(), modes={'walk'})
    # 합성 장소·보행망 응답만 사용한다. 고객 장소·실제 길·외부 조회와 무관하다.
    monkeypatch.setattr(planner, '_walk_path', lambda *args, **kwargs: (300, 71, False))
    origin = {'key': 'A', 'name': '출발 장소', 'lat': 0.0, 'lon': 0.0}
    destination = {'key': 'B', 'name': '도착 장소', 'lat': 0.0, 'lon': 0.001}
    return planner, origin, destination


@pytest.mark.parametrize('arrival_zone', [UTC, KST])
@pytest.mark.parametrize('floor_zone', [UTC, KST])
def test_leg_keeps_a_71_minute_route_when_100_minutes_remain(monkeypatch, arrival_zone, floor_zone):
    planner, origin, destination = _walk_planner(monkeypatch)
    arrival = datetime(2026, 10, 18, 19, tzinfo=KST).astimezone(arrival_zone)
    floor = datetime(2026, 10, 18, 17, 19, 52, tzinfo=KST).astimezone(floor_zone)
    got, reason = planner.leg(origin, destination, arrival, {}, False, 'synthetic', not_before_dt=floor)
    assert got is not None, reason
    route, start, end, service_date, _left = got
    assert route['planned'] == 'walk' and route['options'][0]['eta_min'] == 71
    assert service_date == date(2026, 10, 18)
    assert 1040 <= start < end <= 1140
    assert end - start == 71
    assert datetime.fromisoformat(P.iso_of(service_date, start)) >= floor
    assert datetime.fromisoformat(P.iso_of(service_date, end)) <= arrival


@pytest.mark.parametrize('zone', [UTC, KST])
def test_leg_still_rejects_a_route_when_its_real_duration_exceeds_remaining_time(monkeypatch, zone):
    planner, origin, destination = _walk_planner(monkeypatch)
    arrival = datetime(2026, 10, 18, 19, tzinfo=KST).astimezone(zone)
    floor = datetime(2026, 10, 18, 18, 30, tzinfo=KST).astimezone(zone)
    got, reason = planner.leg(origin, destination, arrival, {}, False, 'too-late', not_before_dt=floor)
    assert got is None and reason['code'] == 'arrive_late'


def test_leg_preserves_route_across_kst_midnight(monkeypatch):
    planner, origin, destination = _walk_planner(monkeypatch)
    arrival = datetime(2026, 10, 19, 0, 30, tzinfo=KST).astimezone(UTC)
    floor = datetime(2026, 10, 18, 22, 50, tzinfo=KST).astimezone(UTC)
    got, reason = planner.leg(origin, destination, arrival, {}, False, 'midnight', not_before_dt=floor)
    assert got is not None, reason
    _route, start, end, service_date, _left = got
    assert service_date == date(2026, 10, 18)
    assert 1370 <= start < end <= 1470
