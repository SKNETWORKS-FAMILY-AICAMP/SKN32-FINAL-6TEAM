"""택시 후보의 출발·소요·요금은 같은 조회 시각에 묶는다. 실주행 시험 아님."""
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine import plan as P
from app.domains.travel_ops.instances.mobility.engine.car import RouterDown

A = {'name': '서울 출발', 'lat': 37.57, 'lon': 126.98}
B = {'name': '서울 도착', 'lat': 37.54, 'lon': 127.05}
DAY = date(2026, 10, 11)


class ClockCar:
    def __init__(self, duration):
        self.duration = duration
        self.calls = []

    def leg(self, start, end, depart, **kwargs):
        self.calls.append(depart)
        seconds = self.duration(depart)
        return {'distance_m': 9800.0, 'topis_time_s': seconds,
                'fare_won': 10000 + depart.hour * 60 + depart.minute, 'grade': '추정'}


def option(car, by=580, buffer=10):
    planner = object.__new__(P.Planner)
    planner.v = SimpleNamespace(car=car)
    planner.modes = {'taxi'}
    left = []
    result = planner._taxi_option(A, B, DAY, by, buffer, left)
    return result, left


def assert_consistent(car, result, by, buffer):
    departure = datetime.fromisoformat(P.iso_of(DAY, result['_start']))
    queried = [dt for dt in car.calls if dt == departure]
    assert queried, '안내할 출발 시각 자체에서 소요를 조회해야 한다'
    import math
    actual_minutes = max(1, math.ceil(car.duration(departure) / 60))
    assert result['eta_min'] == actual_minutes
    assert result['_fare'] == 10000 + departure.hour * 60 + departure.minute
    assert result['_start'] + actual_minutes + buffer <= by
    assert result['_start'] + actual_minutes + buffer + result['_slack'] == by


def test_hour_boundary_never_uses_previous_query_time_for_departure():
    # 09:10에서 40분→08:50, 08:50에서 29분→09:01로 진동한다.
    # 수정 전에는 조회하지 않은09:01에29분을 붙여 여유 포함 목표를11분 넘긴다.
    car = ClockCar(lambda dt: (40 if dt.hour >= 9 else 29) * 60)
    result, left = option(car)
    assert result is not None and not left
    assert_consistent(car, result, 580, 10)


@pytest.mark.parametrize('seconds', [30 * 60, 30 * 60 + 1, 10 * 60, 41 * 60])
def test_constant_profile_preserves_exact_departure_fare_and_ceiling(seconds):
    car = ClockCar(lambda dt: seconds)
    result, left = option(car, by=720)
    assert not left
    assert_consistent(car, result, 720, 10)
    assert len(car.calls) == 2


@pytest.mark.parametrize('by', [1450, 1490])
def test_midnight_candidate_uses_the_actual_calendar_date(by):
    car = ClockCar(lambda dt: (30 if dt.day == DAY.day else 45) * 60)
    result, left = option(car, by=by)
    assert result is not None and not left
    assert_consistent(car, result, by, 10)


def test_unbounded_duration_growth_does_not_publish_unverified_candidate():
    # 매번 그 출발부터 목표까지 남은 시간보다 오래 걸리는 자료다.
    car = ClockCar(lambda dt: (580 - (dt.hour * 60 + dt.minute) + 60) * 60)
    result, left = option(car)
    assert result is None
    assert left[-1]['code'] == 'taxi_no_feasible_departure'
    assert len(car.calls) <= P.TAXI_REFIT_MAX_QUERIES


def test_query_failure_during_refit_is_explicit():
    car = ClockCar(lambda dt: 30 * 60)
    original = car.leg

    def fail_second(*args, **kwargs):
        if car.calls:
            raise RouterDown('재조회 경로 없음')
        return original(*args, **kwargs)

    car.leg = fail_second
    result, left = option(car)
    assert result is None and left[-1]['code'] == 'taxi_no_route'
