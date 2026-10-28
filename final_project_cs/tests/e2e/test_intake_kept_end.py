# -*- coding: utf-8 -*-
"""뒤 일정을 늦출 때 앞 일정의 **추정 끝**은 보이던 그대로 — `POST …/edits`. `[2026-10-25 사용자 결정]`

☆왜: 원문에 끝이 없는 일정은 끝을 「시작 + 기본 시간(활동 90 · 식사 60분), 다음 일정 시작은 넘지 않게」로 판마다 새로 계산해, 다음 일정을 늦추면 끊겨 있던
끝이 같이 늘어 출발이 늦어졌다(2026-10-25 로컬 접수 37a94e6d — 호텔 끝 10:00 → 경복궁을 10:50 으로 늦추자 10:30, 같은 「도착」 질문이 다시 떴다).
계약 `wiki/external/rest-endpoints/web-intakes.md` 「앞 일정의 추정 끝 고정」.

★지키려는 것: ①늦추면 앞 일정 끝이 그대로(저장만 · 검사 포함 · keep_times 모두) ②앞당기면 지금처럼 다음 일정 시작에서 끊긴다 ③앞서 고정한 끝도
앞당긴 시작보다 늦으면 그 시작으로 줄어 겹치지 않는다 ④고객이 적은 끝은 건드리지 않는다.

재현:

    python -m pytest tests/e2e/test_intake_kept_end.py -v
"""
from __future__ import annotations

import pytest

from .test_intake_review import _client, _item, _key, _send, rv  # noqa: F401 — 같은 환경 · 모방을 그대로 쓴다
from .test_trip_api import api  # noqa: F401 — `rv` 가 쓰는 픽스처
from tests.helpers import relative_dates as reldate

# ★`[2026-10-28]` 박아 둔 날짜는 실행 날 기준으로 옮긴다 — 전부-과거 가드(`all_dates_before_today`)가 실제 시계를 읽는다.
#   요일 · 순서 · 간격은 원래 자료와 같다(`tests/helpers/relative_dates.py`).
D_2026_10_15 = reldate.day("2026-10-15")

#: 경복궁에 끝이 없다 — 끝은 10:00 + 90분인데 10:30 광장시장에 끊겨 10:30
NO_END = (f"{D_2026_10_15}\n"
          "10:00 경복궁 관람\n"
          "10:30 광장시장 빈대떡")
#: 경복궁 끝을 고객이 적었다
WITH_END = (f"{D_2026_10_15}\n"
            "10:00~10:20 경복궁 관람\n"
            "10:30 광장시장 빈대떡")


def _times(client, headers, view, start, *, check=None):
    market = _item(view, "광장시장 빈대떡")
    body = {"revision": view["revision"],
            "edits": [{"source_id": market["source_id"], "field": f"items[{market['index']}].starts_at", "value": start}]}
    if check is not None:
        body["check"] = check
    r = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _palace(view):
    item = _item(view, "경복궁 관람")
    return item["starts_at"], item["ends_at"]


@pytest.mark.parametrize("check", [None, False])
def test_making_the_next_stop_later_keeps_the_end_that_was_shown(rv, check):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, NO_END)
    assert _palace(view) == ("10:00", "10:30")                          # 끝 = 10:30 광장시장에 끊긴 추정 끝
    later = _times(client, headers, view, "11:00", check=check)
    assert _palace(later) == ("10:00", "10:30")                         # ★전에는 11:00(끊는 기준을 따라 늘었다)
    further = _times(client, headers, later, "12:30", check=check)
    assert _palace(further) == ("10:00", "10:30")                       # 기본 90분(11:30)까지도 늘지 않는다


def test_making_the_next_stop_earlier_still_cuts_the_end_at_its_start(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, NO_END)
    earlier = _times(client, headers, view, "10:15")
    assert _palace(earlier) == ("10:00", "10:15")                       # 지금처럼 다음 일정 시작에서 끊긴다


def test_an_end_kept_before_is_cut_back_when_the_next_stop_comes_earlier_than_it(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, NO_END)
    later = _times(client, headers, view, "11:00")
    assert _palace(later) == ("10:00", "10:30")
    back = _times(client, headers, later, "10:20")
    assert _palace(back) == ("10:00", "10:20")                          # 고정한 10:30 이 10:20 시작과 겹치지 않게 줄었다
    again = _times(client, headers, back, "11:30")
    assert _palace(again) == ("10:00", "10:20")                         # 다시 늦추면 그때 보이던 10:20 그대로


def test_an_end_the_customer_wrote_is_left_as_it_is(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, WITH_END)
    assert _palace(view) == ("10:00", "10:20")
    later = _times(client, headers, view, "11:00")
    assert _palace(later) == ("10:00", "10:20")
    earlier = _times(client, headers, later, "10:15")
    assert _palace(earlier) == ("10:00", "10:20")                       # 고객이 적은 끝은 이 규칙이 줄이지 않는다(겹침은 검사가 말한다)
