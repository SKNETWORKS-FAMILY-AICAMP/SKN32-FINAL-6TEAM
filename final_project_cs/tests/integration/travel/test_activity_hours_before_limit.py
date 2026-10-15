"""가까운 미확인 장소가 채워도 뒤쪽의 시간 보유 활동을 추천한다."""
from uuid import uuid4

from tests.integration.travel.test_activity_catalog_pool import _setup, _night, _Tour, _desk, _drop


def test_known_hours_beyond_first_ten_is_still_recommended():
    tenant = "hours_limit_" + uuid4().hex[:8]
    catalog = [(str(9800 + i), f"시간 미확인 여행 활동 {i}", 0.0001 * (i + 1), 0.0) for i in range(10)]
    catalog.append(("9899", "시간 확인된 여행 미술관", 0.004, 0.0))
    try:
        store, trip_id, items = _setup(tenant, catalog)
        tour = _Tour({**{str(9800 + i): "운영시간 안내 없음" for i in range(10)}, "9899": "09:00~18:00"})
        assert _night(tenant, tour, per_tick=30)["read"] == 1
        asked = list(tour.asked)
        done = _desk(store).fresh_alternate(
            trip_id=trip_id, item_id=items[0].item_id, base_version=1,
            message="활동 다른 데로 바꿔", request_id="hours-beyond-limit")
        assert done["status"] == "adjusted", done
        assert done["notice"]["changed"]["to"] == "시간 확인된 여행 미술관"
        assert tour.asked == asked  # 고객 요청에서는 새 외부 호출을 하지 않는다.
    finally:
        _drop(tenant)
