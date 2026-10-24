"""한 번의 이동을 모델이 전체 이동·성향으로 읽어도 다른 구간에 퍼지지 않는다."""
from datetime import date

import pytest

from app.domains.travel_ops.components.intake import reading_prefs, survey_answers
from app.domains.travel_ops.components.intake.pipeline import read_source
from app.domains.travel_ops.components.intake.review import picked_modes

DAY = date(2026, 10, 23)
HEADER = "1일차 2026-10-23"
STOPS = [("경복궁", "10:00"), ("광장시장", "12:30"), ("국립중앙박물관", "15:00"), ("N서울타워", "19:00")]


class Reader:
    model = "transport-scope-fixture"

    def __init__(self, quote, scope, *, day=1, preferences=()):
        self.answer = {"items": [{"place_quote": title, "day": 1, "date": DAY.isoformat(), "date_quote": HEADER,
                                  "start": start, "end": None, "time_quote": start, "kind": "activity"}
                                 for title, start in STOPS],
                       "moves": [{"mode": "taxi", "scope": scope, "day": day, "from_quote": None,
                                  "to_quote": None, "quote": quote}],
                       "preferences": list(preferences), "conditions": [], "missing": [], "trip": {}}

    def structured(self, system, user, schema, *, num_predict=160):
        return self.answer


def source(quote, *, middle=True):
    lines = [HEADER, *(f"{start} {title}" for title, start in STOPS)]
    lines.insert(4 if middle else 1, quote)
    return "\n".join(lines)


@pytest.mark.parametrize("scope", ["all", "day", "segment"])
@pytest.mark.parametrize("quote", ["우리 지금 택시로 이동", "택시로 이동"])
def test_a_single_ride_misread_as_global_or_preference_only_changes_its_neighbours(scope, quote):
    reader = Reader(quote, scope, preferences=[{"code": "prefer_taxi", "quote": quote}])
    rows = read_source(source(quote), today=DAY, agent=reader, agent_mode="on")
    assert picked_modes(rows) == {"0-2~0-3": "taxi"}
    assert reading_prefs.carry(rows) == []
    report = next(row["value"] for row in rows if row["field"] == "reading.agent")
    assert report["moves"][0]["scope"] == "segment"
    assert report["preferences"] == []


def test_an_unlocated_ride_does_not_change_any_segment_or_skip_the_mobility_question():
    quote = "우리 지금 택시로 이동"
    rows = read_source(source(quote, middle=False), today=DAY, agent=Reader(quote, "all"), agent_mode="on")
    assert picked_modes(rows) == {}
    found = reading_prefs.carry(rows)
    plan = survey_answers.second_plan(survey_answers.first_plan([]), [], found)
    assert not [skip for skip in plan["skipped_by_reading"] if skip.get("part") == "mobility"]


@pytest.mark.parametrize("day", [None, 99])
def test_an_unknown_day_never_defaults_to_the_whole_trip(day):
    quote = "오늘은 전부 택시로 이동"
    rows = read_source(source(quote), today=DAY, agent=Reader(quote, "day", day=day), agent_mode="on")
    assert picked_modes(rows) == {}


def test_explicit_whole_trip_transport_still_applies_to_all_segments():
    quote = "여행 내내 다 택시로 이동"
    rows = read_source(source(quote, middle=False), today=DAY, agent=Reader(quote, "all"), agent_mode="on")
    assert picked_modes(rows) == {"0-0~0-1": "taxi", "0-1~0-2": "taxi", "0-2~0-3": "taxi"}
    assert reading_prefs.carry(rows)[0]["value"] == ["taxi"]


@pytest.mark.parametrize("quote", ["우리 지금 택시로 이동", "택시로 이동", "지금은 모두 택시로", "오늘은 전부 택시로"])
def test_local_transport_is_not_a_global_mobility_preference(quote):
    assert reading_prefs.proposals([{"preferences": [{"code": "prefer_taxi", "quote": quote}]}]) == []
    assert not reading_prefs.whole_trip_said(quote)



def test_repeated_transport_words_without_endpoints_are_not_assigned_to_the_first_pair():
    quote = "우리 지금 택시로 이동"
    text = source(quote).replace("12:30 광장시장", quote + "\n12:30 광장시장")
    rows = read_source(text, today=DAY, agent=Reader(quote, "all"), agent_mode="on")
    assert picked_modes(rows) == {}


def test_a_stated_day_changes_that_day_and_leaves_the_next_day_alone():
    quote = "오늘은 전부 택시로 이동"
    reader = Reader(quote, "day", day=1)
    text = source(quote, middle=False) + "\n2일차 2026-10-24\n10:00 덕수궁\n13:00 서울시립미술관"
    rows = read_source(text, today=DAY, agent=reader, agent_mode="on")
    assert picked_modes(rows) == {"0-0~0-1": "taxi", "0-1~0-2": "taxi", "0-2~0-3": "taxi"}
    assert reading_prefs.carry(rows) == []


@pytest.mark.parametrize("quote", ["웬만하면 택시", "택시 위주", "택시로 다닐래요", "택시를 선호해요"])
def test_an_explicit_general_preference_is_still_handed_over(quote):
    [proposal] = reading_prefs.proposals([{"preferences": [{"code": "prefer_taxi", "quote": quote}]}])
    assert proposal["value"] == ["taxi"]


@pytest.mark.parametrize("quote", ["이번 여행 내내 택시로", "이동은 주로 택시로"])
def test_an_explicit_whole_trip_phrase_keeps_its_scope(quote):
    assert reading_prefs.transport_scope("all", quote) == "all"


@pytest.mark.parametrize("quote", ["오늘 택시로 이동", "지금은 모두 택시로", "광장시장까지 택시가 좋아요"])
def test_limited_or_unclear_scope_never_becomes_a_general_preference(quote):
    assert reading_prefs.transport_scope("day", quote) == "segment"
    assert not reading_prefs.mobility_preference_said(quote)
