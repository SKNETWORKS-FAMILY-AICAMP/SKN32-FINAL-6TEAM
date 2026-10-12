"""두 번째 버스는 여정 전체 구간 대신 실제 환승 승차 무렵을 검사한다."""
from types import SimpleNamespace

from tests.unit.travel.mobility.test_bus_service_direction import _window


def test_late_transfer_cannot_use_a_night_bus_that_only_overlaps_departure():
    planner, candidate = _window(first=1420, last=1690)
    planner._ride_est = lambda r, *_: 235 if r.route_id == '2' else 0
    # 전날 마지막 운행의 정류장 통과 추정은 08:05, 허용 창 끝은 09:05.
    # 여정 시작 09:00은 창에 닿지만 환승 승차 09:20은 창 밖이다.
    candidate.est_min = 90
    candidate.bus_board_offsets = [5, 20]
    assert not planner._in_service(candidate, 540, 630)


def test_a_later_boarding_offset_preserves_a_valid_transfer():
    planner, candidate = _window(first=240, last=1380)
    candidate.est_min = 90
    candidate.bus_board_offsets = [5, 20]
    assert planner._in_service(candidate, 540, 630)


def test_offsets_are_not_assumed_for_old_or_unknown_candidates():
    planner, candidate = _window(first=1420, last=1690)
    planner._ride_est = lambda r, *_: 235 if r.route_id == '2' else 0
    assert planner._in_service(candidate, 540, 630)
