"""0초 도착과 소스 관측시각을 보존한다. 소스 나이를 임의의 실시간 보장으로 바꾸지 않는다."""
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival


def test_zero_and_provider_clock_are_preserved():
    rows = [{"barvlDt": value, "recptnDt": time} for value, time in (
        (0, "2026-10-08 14:00:00"), ("0", "2026-10-08 14:06:00"),
        (None, "bad time"), (-1, None))]
    def transport(url, params):
        return httpx.Response(200, json={"realtimeArrivalList": rows}, request=httpx.Request("GET", url))
    src = SeoulSubwayArrival(service_key="test-key", transport=transport,
                            now=lambda: datetime(2026, 10, 8, 14, 5, tzinfo=ZoneInfo("Asia/Seoul")))
    trains = src.arrivals("서울")['trains']
    assert [t['eta_seconds'] for t in trains] == [0, 0, None, None]
    assert [t['received_age_seconds'] for t in trains] == [300, -60, None, None]
    assert [t['source_clock_ahead'] for t in trains] == [False, True, None, None]
