"""선택된 이용권의 반납 한도에서 기존 여유시간만큼 앞서 경고한다."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine.bike import BikeStations
from app.domains.travel_ops.instances.mobility.engine.verify_time import Timetable, Verifier
from .test_review_fixes import RULES


@pytest.mark.parametrize('ride,base,warned,threshold', [
    (60, 60, True, 50), (100, 120, False, 110), (110, 120, False, 110),
    (111, 120, True, 110), (160, 180, False, 170), (171, 180, True, 170),
])
def test_warning_follows_selected_pass_and_keeps_existing_margin(monkeypatch, ride, base, warned, threshold):
    from app.domains.travel_ops.instances.mobility.engine import verify_time
    monkeypatch.setattr(verify_time, 'bike_fare', lambda *args: {
        'pass': f'{base//60}h', 'pass_won': 2000, 'base_ride_min': base,
        'overtime_min': 0, 'overtime_won': 0})
    a = {'stationId': 'ST-1', 'name': '출발 대여소', 'lat': 37.5, 'lon': 127.0, 'mode': 'QR', 'rack': 10}
    b = dict(a, stationId='ST-2', name='도착 대여소', lat=37.51, lon=127.01)
    router = SimpleNamespace(available=lambda: True, route=lambda *args: {
        'time_s': ride*60, 'distance_m': 1000, 'source_id': 'controlled/bike', 'basis': '통제 소요'})
    verifier = Verifier(Timetable(), None, deepcopy(RULES), set(), bk=BikeStations([a, b]), bike_router=router)
    got = verifier.verify_leg_bike(0, {'mode': 'bike', 'from': dict(a, lng=a['lon']),
                                      'to': dict(b, lng=b['lon'])}, 600, 'weekday',
                                    live_fixture={'checked_at': 'controlled', 'counts': {'ST-1': 2, 'ST-2': 2}})
    warnings = [w for w in got.warnings if w['code'] == 'MOB_W_BIKE_OVERTIME']
    assert bool(warnings) is warned
    if warned:
        assert str(threshold) in str(warnings[0])
