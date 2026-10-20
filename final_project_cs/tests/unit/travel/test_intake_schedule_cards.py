"""Copied clock/place cards survive a model omission without inventing stops."""
from datetime import date

import pytest

from app.domains.travel_ops.components.intake import schedule_cards
from app.domains.travel_ops.components.intake.assemble import collect, effective
from app.domains.travel_ops.components.intake.pipeline import read_source
from app.domains.travel_ops.components.intake.rules import read_plan

DAY = date(2026, 10, 24)
TEXT = ("1일차 · 2026-10-24\n11:00–12:00\n솔빛공원\n12:34–12:50\n도보 16분 · 0.9km\n"
        "15:02–16:30\n별빛문화축제 변경됨\n17:18–18:41\n지하철 8호선→5호선→4호선 83분 · 12.6km\n"
        "19:00–20:30\n한강전망대")


def stop(name, start, end, *, quote=None):
    return {"place_quote": name, "day": 1, "date": DAY.isoformat(), "date_quote": DAY.isoformat(),
            "start": start, "end": end, "time_quote": quote or f"{start}–{end}", "kind": "activity"}


class Reader:
    model = "schedule-card-regression"

    def __init__(self, items=None, *, correction="별빛문화축제 변경됨"):
        self.items = items or [stop("솔빛공원", "11:00", "12:00"), stop("한강전망대", "19:00", "20:30")]
        self.correction = correction
        self.calls = 0

    def structured(self, system, user, schema, *, num_predict):
        self.calls += 1
        return {"items": self.items, "pieces": [{"kind": "correction", "quote": self.correction}] if self.correction else [],
                "moves": [], "conditions": [], "preferences": [], "gaps": [], "missing": [], "trip": {}}


def source(text=TEXT):
    return {"source_id": "s", "position": 0, "transcript": text}


def claims(text=TEXT, reader=None):
    return [{**c, "source_id": "s"} for c in read_source(text, today=DAY, agent=reader or Reader(), agent_mode="on")]


def grouped(rows):
    out = {}
    for row in rows:
        if row["field"].startswith("items["):
            index, field = row["field"][6:].split("].", 1)
            out.setdefault(int(index), {})[field] = row
    return list(out.values())


def test_copied_status_card_is_recovered_even_when_model_marks_it_as_correction():
    reader = Reader()
    rows = claims(reader=reader)
    items = grouped(rows)
    assert [i["title"]["value"] for i in items] == ["솔빛공원", "한강전망대", "별빛문화축제"]
    festival = items[2]
    assert festival["starts_at"]["value"] == "15:02"
    assert festival["ends_at"]["value"] == "16:30"
    assert festival["title"]["evidence"] == {"source": "text", "line": 7, "start": 0, "end": 6, "text": "별빛문화축제"}
    assert festival["starts_at"]["evidence"]["line"] == 6
    assert reader.calls == 1
    assert schedule_cards.omissions([source()], rows) == []


def test_card_clocks_override_a_models_nearby_clock_and_strip_only_the_status_badge():
    reader = Reader([stop("별빛문화축제 변경됨", "11:00", "12:00"), stop("한강전망대", "19:00", "20:30")])
    festival = grouped(claims(reader=reader))[0]
    assert festival["title"]["value"] == "별빛문화축제"
    assert (festival["starts_at"]["value"], festival["ends_at"]["value"]) == ("15:02", "16:30")
    assert all(festival[k]["method"] == "rule" for k in ["starts_at", "ends_at"])
    assert festival["ends_at"]["evidence"]["text"] == "16:30"


@pytest.mark.parametrize("separator", ["–", "—", "~", "-", "부터"])
def test_standalone_clock_ranges_keep_original_title_and_clock_spans(separator):
    text = f"2026-10-24\n  15:02{separator}16:30  \n  별빛문화축제 변경됨"
    found = schedule_cards.cards(read_plan(text))
    assert len(found) == 1
    card = found[0]
    assert card.title.text == "별빛문화축제" and card.title.start == 2
    assert card.start.span.line == 2 and card.end.span.line == 2
    assert card.start.value == "15:02" and card.end.value == "16:30"


@pytest.mark.parametrize("line", ["도보 16분 · 0.9km", "지하철 8호선→5호선 42분", "비 오면 실내로 가요",
                                 "어디 갈까요?", "강풍주의보 알림", "별빛문화축제 말고 박물관", "활동", "2일차"])
def test_transport_conditions_questions_and_change_commands_are_not_place_cards(line):
    assert schedule_cards.cards(read_plan(f"15:02–16:30\n{line}")) == []


def test_actual_replacement_command_does_not_resurrect_the_original_card():
    text = TEXT + "\n별빛문화축제 말고 달빛미술관으로 바꿔 주세요"
    reader = Reader([stop("솔빛공원", "11:00", "12:00"), stop("한강전망대", "19:00", "20:30"),
                     stop("달빛미술관", "15:02", "16:30")], correction="별빛문화축제 말고 달빛미술관으로 바꿔 주세요")
    rows = claims(text, reader)
    assert "별빛문화축제" not in [i["title"]["value"] for i in grouped(rows)]
    assert schedule_cards.omissions([source(text)], rows) == []


def test_unrecovered_explicit_card_is_a_registration_problem():
    rows = claims()
    missing = [c for c in rows if not (c["field"].startswith("items[2]."))]
    got = collect(sources=[source()], claims=missing)
    assert [(p.code, p.field) for p in got.problems if p.code == "source_item_missing"] == [
        ("source_item_missing", "reading.source_items")]
    assert "별빛문화축제" in next(p.message for p in got.problems if p.code == "source_item_missing")


def test_customer_title_edits_and_explicit_removal_do_not_trigger_recreation():
    rows = claims()
    previous = next(c for c in rows if c["field"] == "items[2].title")
    evidence = schedule_cards.edited_title_evidence({"source": "customer"}, previous)
    assert evidence["source_item_line"] == 7
    rows.extend([{"source_id": "s", "field": "items[2].title", "value": "달빛미술관", "method": "customer", "evidence": evidence},
                 {"source_id": "s", "field": "items[2].removed", "value": True, "method": "customer", "evidence": {}}])
    got = collect(sources=[source()], claims=effective(rows))
    assert not any(p.code == "source_item_missing" for p in got.problems)
    assert "별빛문화축제" not in [row["title"] for row in got.rows]


def test_customer_title_association_survives_all_clock_edits_and_another_title_edit():
    rows = claims()
    previous = next(c for c in rows if c["field"] == "items[2].title")
    evidence = schedule_cards.edited_title_evidence({"source": "customer"}, previous)
    twice = schedule_cards.edited_title_evidence({"source": "customer"}, {"evidence": evidence})
    rows.extend({"source_id": "s", "field": f"items[2].{field}", "value": value, "method": "customer", "evidence": twice if field == "title" else {}}
                for field, value in [("title", "달빛미술관"), ("starts_at", "16:00"), ("ends_at", "17:00")])
    assert schedule_cards.omissions([source()], effective(rows)) == []


def test_untimed_free_text_is_not_promoted_to_an_explicit_card():
    assert schedule_cards.cards(read_plan("언젠가 별빛문화축제에 가 보고 싶어요")) == []


def test_genuine_unresolved_correction_cannot_silently_hide_an_unrelated_card():
    text = TEXT + "\n오늘 순서는 바꿀래요"
    rows = claims(text, Reader(correction="오늘 순서는 바꿀래요"))
    assert any(card["title"] == "별빛문화축제" for card in schedule_cards.omissions([source(text)], rows))
