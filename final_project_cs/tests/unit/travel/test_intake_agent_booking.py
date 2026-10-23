"""예약 표시는 모델이 고른 장소 조각에 대응하는 원문에서 보존한다."""
from datetime import date

import pytest

from app.domains.travel_ops.components.intake.pipeline import read_source


class PlanReader:
    model = "booking-regression"

    def __init__(self, items, *, correction=False):
        self.items = items
        self.correction = correction

    def structured(self, system, user, schema, *, num_predict=160):
        return {"items": self.items, "requests": ["correction"] if self.correction else ["register"],
                "pieces": [{"kind": "correction", "quote": "N서울타워 말고 롯데타워로"}] if self.correction else [],
                "moves": [], "conditions": [], "preferences": [], "gaps": [], "missing": [], "trip": {}}


def stop(name, clock):
    return {"place_quote": name, "day": 1, "date": "2026-10-24", "date_quote": None,
            "start": clock, "end": None, "time_quote": clock, "kind": "activity"}


def read(text, items, *, correction=False):
    rows = read_source(text, today=date(2026, 10, 17), agent=PlanReader(items, correction=correction), agent_mode="on")
    values = {}
    for row in rows:
        if not row["field"].startswith("items["):
            continue
        index, field = row["field"][6:].split("].", 1)
        values.setdefault(int(index), {})[field] = row["value"]
    return rows, list(values.values())


@pytest.mark.parametrize("marker, expected", [("예약 있음", True), ("예약 완료", True), ("booked", True),
                                              ("예약 없음", False), ("not booked", False)])
def test_explicit_booking_status_survives_the_agent_reading(marker, expected):
    text = f"19:00 N서울타워 · {marker}"
    rows, items = read(text, [stop("N서울타워", "19:00")])
    assert items[0]["booked"] is expected
    claim = next(r for r in rows if r["field"] == "items[0].booked")
    evidence = claim["evidence"]
    assert text[evidence["start"]:evidence["end"]] == evidence["text"]
    assert claim["method"] == "rule"


def test_booking_number_remains_verbatim_with_its_original_evidence():
    text = "19:00 명동난타극장 예약번호 KY-20931"
    rows, items = read(text, [stop("명동난타극장", "19:00")])
    assert items[0]["booking_no"] == "KY-20931"
    claim = next(r for r in rows if r["field"] == "items[0].booking_no")
    evidence = claim["evidence"]
    assert text[evidence["start"]:evidence["end"]] == "KY-20931"


def test_booking_belongs_to_the_overlapping_place_when_the_agent_reorders_one_line():
    text = "10:00 경복궁 예약 있음 12:00 광장시장 예약 없음"
    _, items = read(text, [stop("광장시장", "12:00"), stop("경복궁", "10:00")])
    assert [(x["title"], x["booked"]) for x in items] == [("광장시장", False), ("경복궁", True)]


def test_booking_is_not_copied_to_a_different_place_on_the_same_line():
    text = "10:00 경복궁 예약 있음 12:00 광장시장"
    _, items = read(text, [stop("경복궁", "10:00"), stop("광장시장", "12:00")])
    assert items[0]["booked"] is True
    assert "booked" not in items[1]


def test_booking_number_is_reindexed_for_the_matching_place_not_the_original_position():
    text = "10:00 경복궁 예약번호 KY-20931 12:00 광장시장"
    _, items = read(text, [stop("광장시장", "12:00"), stop("경복궁", "10:00")])
    assert "booking_no" not in items[0]
    assert items[1]["booking_no"] == "KY-20931"


def test_absent_booking_information_stays_unknown():
    _, items = read("19:00 N서울타워", [stop("N서울타워", "19:00")])
    assert "booked" not in items[0]
    assert "booking_no" not in items[0]


def test_correction_does_not_transfer_the_replaced_places_booking():
    text = "19:00 N서울타워 예약 있음\n아 N서울타워 말고 롯데타워로 바꿀게요"
    _, items = read(text, [stop("롯데타워", "19:00")], correction=True)
    assert [x["title"] for x in items] == ["롯데타워"]
    assert "booked" not in items[0]


def test_a_quote_spanning_two_places_does_not_assign_one_places_booking():
    title = "경복궁 예약 있음 12:00 광장시장"
    _, items = read("10:00 " + title, [stop(title, "10:00")])
    assert "booked" not in items[0]
