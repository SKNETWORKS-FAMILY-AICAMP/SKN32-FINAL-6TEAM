"""서울시 환승 창은 다음 승차 시각 기준이다. 현재 제품 미연결 계산식 시험."""
import pytest

from app.domains.travel_ops.instances.mobility.engine.options import transfer_fare
from .test_plan_v1 import _rules


def parts(alight, board):
    return [dict(kind="간선", base=1500, m=3000, board=alight-10, alight=alight),
            dict(kind="subway", base=1550, m=3000, board=board, alight=board+10)]


@pytest.mark.parametrize("alight,board,expected", [
    (20*60+40, 21*60+20, 1550),
    (20*60+30, 21*60+30, 1550),
    (20*60+45, 21*60+46, None),
    (6*60+40, 7*60+20, None),
    (6*60+20, 7*60+1, None),
    (6*60+30, 7*60, 1550),
    (23*60+40, 24*60+30, 1550),
    (12*60, 12*60+30, 1550),
    (12*60, 12*60+31, None),
])
def test_following_board_controls_day_or_night_window(alight, board, expected):
    assert transfer_fare(_rules()["fare"], parts(alight, board)) == expected


def test_overlapping_rides_cannot_receive_transfer_discount():
    assert transfer_fare(_rules()["fare"], parts(720, 719)) is None


@pytest.mark.parametrize("field,value", [
    ("m", float("nan")), ("m", float("inf")), ("m", -1), ("m", True),
    ("base", -1), ("board", float("nan")), ("alight", None),
])
def test_invalid_distance_fare_or_clock_does_not_produce_money(field, value):
    data = parts(720, 725)
    data[0][field] = value
    assert transfer_fare(_rules()["fare"], data) is None
