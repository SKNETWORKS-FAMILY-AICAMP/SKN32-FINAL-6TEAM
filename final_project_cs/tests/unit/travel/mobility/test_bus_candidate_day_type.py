"""후보 생성이 시간대·휴일 프로파일과 캐시 칸을 구별하는지 확인한다."""
from types import SimpleNamespace

from app.domains.travel_ops.instances.mobility.engine.candidates import ride_estimator


class Bus:
    stops = {'route': [{'seq': 1}, {'seq': 2, 'sect_dist_m': 1000}]}


def test_profile_day_type_and_hour_are_part_of_cache_key():
    calls = []
    class Profile:
        def row(self, route, start, end):
            return 0, False

        def cell(self, index, day, hour, quantile, minimum):
            calls.append((day, hour))
            return {('weekday', 12): 60, ('holiday', 12): 120, ('weekday', 18): 180}[(day, hour)]
    bus = Bus()
    v = SimpleNamespace(bus=bus, bus_prof=Profile(), R={}, rv=lambda *a: 3,
                        bus_speed=lambda r, d: (20, '', '추정', []))
    route = SimpleNamespace(route_id='route')
    start, end = bus.stops['route']
    for day, hour, expected in [('weekday', 12, 1), ('holiday', 12, 2), ('weekday', 18, 3), ('holiday', 12, 2)]:
        assert ride_estimator(v, hour, day)(route, start, end) == expected
    assert calls == [('weekday', 12), ('holiday', 12), ('weekday', 18)]


def test_fallback_speed_uses_requested_day_type():
    bus = Bus()
    v = SimpleNamespace(bus=bus, bus_prof=None, R={},
                        bus_speed=lambda r, d: (60 if d == 'weekday' else 30, '', '추정', []))
    route = SimpleNamespace(route_id='route')
    start, end = bus.stops['route']
    assert ride_estimator(v, day_type='weekday')(route, start, end) == 1
    assert ride_estimator(v, day_type='holiday')(route, start, end) == 2
