# -*- coding: utf-8 -*-
"""숙소 팀이 꽂는 「다른 숙소 후보」 자리(`team_hooks.lodging_alternatives`)와 숙소 팀 어댑터(`instances.lodging.review_alternatives`).
`[2026-10-16 사용자 결정]` 후보 공급은 팀이 — 미등록 · 답하지 못함은 `None`(부르는 쪽이 자체 고르기로 간다). 바깥 소스는 mock 서버 대신 메모리 객체."""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.team_hooks import lodging_alternatives as hook
from app.domains.travel_ops.instances.lodging import review_alternatives

QUERY = {"keyword": "명동", "check_in": "2026-10-22", "check_out": "2026-10-23", "adults": 2}


@pytest.fixture(autouse=True)
def clean():
    hook.clear()
    yield
    hook.clear()


def test_without_a_registered_team_the_answer_is_unknown():
    assert hook.is_registered() is False
    assert hook.ranked(**QUERY) is None


def test_missing_keyword_dates_or_party_is_unknown_not_an_empty_answer():
    hook.register(rank=lambda **k: {"alternatives": []})
    for broken in ({"keyword": None}, {"check_in": None}, {"check_out": ""}, {"adults": None}, {"adults": 0}):
        assert hook.ranked(**{**QUERY, **broken}) is None


def test_a_registered_team_answer_passes_through():
    seen = {}

    def rank(**query):
        seen.update(query)
        return {"alternatives": []}

    hook.register(rank=rank)
    assert hook.ranked(**QUERY, anchor=(37.56, 126.98), exclude_names=["호텔 A"]) == {"alternatives": []}
    assert seen["anchor"] == (37.56, 126.98) and seen["exclude_names"] == ("호텔 A",) and seen["adults"] == 2


class _Source:
    def __init__(self, stays):
        self.stays = stays
        self.asked = 0

    def stay_search(self, **_):
        self.asked += 1
        return {"stays": self.stays}


class _Travel:
    def __init__(self, myrealtrip=(), google=()):
        self.travel_search = _Source(list(myrealtrip))
        self.stay_google = _Source(list(google))


def _google(name, lat, lon, price=150000):
    return {"name": name, "latitude": lat, "longitude": lon, "price_per_night": price, "link": f"https://example.test/{name}",
            "rating": 4.5}


def test_adapter_uses_the_team_picker_nearest_first_and_skips_the_current_stay():
    travel = _Travel(myrealtrip=[{"gid": 1, "name": "좌표 없는 숙소", "price_per_night": 100000}],
                     google=[_google("먼 호텔", 37.60, 127.05), _google("가까운 호텔", 37.5605, 126.9805),
                             _google("지금 숙소", 37.5601, 126.9801), _google("중간 호텔", 37.565, 126.985)])
    got = review_alternatives.rank(travel=travel, **QUERY, anchor=(37.56, 126.98), exclude_names=("지금 숙소",))
    names = [alt["name"] for alt in got["alternatives"]]
    assert "지금 숙소" not in names
    assert names[:2] == ["가까운 호텔", "중간 호텔"]
    assert "좌표 없는 숙소" not in names and len(names) == 3   # 마이리얼트립(목록에 좌표 없음)은 부르지 않는다 — 지도 후보 셋이 다 좌표가 있다
    assert travel.travel_search.asked == 0
    assert all(isinstance(alt["latitude"], float) for alt in got["alternatives"])


def test_adapter_without_sources_or_coordinates_is_unknown():
    assert review_alternatives.rank(travel=None, **QUERY) is None
    assert review_alternatives.rank(travel=_Travel(), **QUERY) is None
    no_google = _Travel(myrealtrip=[{"gid": 1, "name": "좌표 없는 숙소", "price_per_night": 100000}])
    no_google.stay_google = None                            # SerpApi 키 없음 — 바깥에 나가지 않는다
    assert review_alternatives.rank(travel=no_google, **QUERY) is None
    assert no_google.travel_search.asked == 0
