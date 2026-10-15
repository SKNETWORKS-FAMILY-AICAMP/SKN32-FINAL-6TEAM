# -*- coding: utf-8 -*-
"""원문 추출 → 날짜·장소 해석 → 조립에서 장소별 의미가 보존되는지 검증한다.

모델과 관광공사 조회 응답만 고정한다. 파서·날짜 해석·claim·조립은 실제 코드다.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake.assemble import collect
from app.domains.travel_ops.components.intake.pipeline import read_source

TODAY = date(2026, 10, 14)
SOURCE_ID = "s1"
LATER_PLACE_LINE = "오후엔 서촌 골목 좀 걷다가 저녁 무렵 남산타워 올라가 볼까 해요"


class FakeChat:
    def __init__(self, spans):
        self.spans = spans

    def json(self, system, user):
        return {"spans": self.spans}


class FakeTour:
    """식당으로 바꾸지 않고 원문과 같은 관광지·시장만 확인한다."""

    def find(self, name, area_code=None, **kwargs):
        kinds = {"서촌": "12", "남산타워": "12", "경복궁": "12", "통인시장": "38", "광장시장": "38"}
        if name not in kinds:
            return None
        return {"matched_title": name, "content_id": "c-" + name, "content_type_id": kinds[name],
                "latitude": 37.57, "longitude": 126.98, "address": "서울특별시 종로구"}


def _read(text, names, *, line=1, extra_spans=(), now=None):
    spans = [{"line": line, "quote": name, "role": "place"} for name in names]
    spans += [{"line": line, "quote": quote, "role": role} for quote, role in extra_spans]
    rows = read_source(text, chat=FakeChat(spans), tour=FakeTour(), our_places=[],
                       today=TODAY, now=now)
    source = {"source_id": SOURCE_ID, "position": 0, "transcript": text}
    return source, [{**row, "source_id": SOURCE_ID} for row in rows]


def _collect(source, claims):
    return collect(sources=[source], claims=claims)


def _dated(text, names, *, extra_spans=()):
    return _read("1일차 2026-10-15\n" + text, names, line=2, extra_spans=extra_spans)


def _by_title(collected):
    return {row["title"]: row for row in collected.rows}


def test_later_evening_does_not_set_the_earlier_places_time():
    source, claims = _dated(LATER_PLACE_LINE, ["서촌", "남산타워"])
    got = _by_title(_collect(source, claims))
    assert set(got) == {"서촌", "남산타워"}
    assert got["서촌"]["start"] < "18:00"
    assert got["남산타워"]["start"] == "18:00"
    assert got["서촌"]["kind"] == got["남산타워"]["kind"] == "activity"


def test_next_places_lunch_does_not_make_a_walk_into_dining():
    source, claims = _dated("서촌 걷다가 점심은 통인시장 근처에서 해결하고 싶어요", ["서촌", "통인시장"])
    got = _by_title(_collect(source, claims))
    assert set(got) == {"서촌", "통인시장"}
    assert got["서촌"]["kind"] == "activity"
    assert got["통인시장"]["kind"] == "dining"
    assert got["통인시장"]["start"] == "12:00"


def test_meal_at_the_first_place_survives_following_travel():
    source, claims = _dated("광장시장에서 점심 먹고 경복궁 가자", ["광장시장", "경복궁"])
    got = _by_title(_collect(source, claims))
    assert set(got) == {"광장시장", "경복궁"}
    assert got["광장시장"]["kind"] == "dining"
    assert got["광장시장"]["start"] == "12:00"
    assert got["경복궁"]["kind"] == "activity"
    assert got["경복궁"]["start"] > got["광장시장"]["start"]


def test_two_relative_dates_on_a_line_stay_with_their_places():
    source, claims = _read("내일은 경복궁 구경하고 모레는 남산타워 올라가자", ["경복궁", "남산타워"],
                           extra_spans=[("내일", "date"), ("모레", "date")])
    got = _by_title(_collect(source, claims))
    assert {title: row["date"] for title, row in got.items()} == {
        "경복궁": "2026-10-15", "남산타워": "2026-10-16"}


def test_postfix_now_belongs_to_the_current_place_and_evening_to_the_next():
    anchor = datetime(2026, 10, 14, 11, 7, tzinfo=ZoneInfo("Asia/Seoul"))
    source, claims = _read("서촌은 지금 당장 가고 저녁 무렵 남산타워 올라갈까 해요", ["서촌", "남산타워"],
                           extra_spans=[("지금 당장", "time"), ("저녁 무렵", "time")], now=anchor)
    got = _by_title(_collect(source, claims))
    assert set(got) == {"서촌", "남산타워"}
    assert got["서촌"]["start"] == "11:07"
    assert got["서촌"]["date"] == anchor.date().isoformat()
    assert got["남산타워"]["start"] == "18:00"


@pytest.mark.parametrize("legacy", [False, True], ids=["stored-segment", "legacy-without-segment"])
def test_removing_a_later_place_keeps_the_original_items_time(legacy):
    source, original = _dated(LATER_PLACE_LINE, ["서촌", "남산타워"])
    claims = deepcopy(original)
    titles = [claim for claim in claims if claim["field"].endswith(".title")]
    if legacy:
        for claim in titles:
            claim["evidence"].pop("segment", None)
    else:
        assert all("segment" in claim["evidence"] for claim in titles)
    before = _by_title(_collect(source, claims))
    assert before["서촌"]["start"] < "18:00"
    removed = next(claim for claim in titles if claim["value"] == "남산타워")
    claims.append({"source_id": SOURCE_ID, "field": removed["field"].replace(".title", ".removed"),
                   "value": True, "method": "customer", "evidence": {}, "needs_review": False, "note": None})
    after = _by_title(_collect(source, claims))
    assert set(after) == {"서촌"}
    assert after["서촌"]["start"] == before["서촌"]["start"]
    assert after["서촌"]["kind"] == before["서촌"]["kind"]
