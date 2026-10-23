"""A later meal's time cue must not be saved as the preceding stop's context."""
from datetime import date

import pytest

from app.domains.travel_ops.components.intake.assemble import collect
from app.domains.travel_ops.components.intake.pipeline import read_source


class Reader:
    def __init__(self, clocks):
        self.clocks = clocks

    def structured(self, system, user, schema, *, num_predict=160):
        return {"items": [
            {"place_quote": name, "day": 1, "date": "2026-10-23", "date_quote": "10/23",
             "start": clock, "end": None, "time_quote": clock, "kind": kind}
            for name, kind, clock in zip(("홍대", "돈가스", "라멘"),
                                         ("activity", "dining", "dining"), self.clocks)
        ], "moves": [], "conditions": [], "preferences": [], "requests": ["register"],
            "missing": [], "trip": {}}


@pytest.mark.parametrize("text", [
    "10/23일 홍대가서 쇼핑 후에 근처에서 돈가스 먹고 그 다음엔 저녁으로 라멘",
    "10/23 홍대 쇼핑하고 돈가스 먹고 저녁은 라멘",
    "10/23 홍대 쇼핑, 점심은 돈가스, 저녁은 라멘",
])
def test_later_dinner_does_not_turn_the_preceding_meal_into_dinner(text):
    claims = read_source(text, today=date(2026, 10, 22), agent=Reader((None, None, None)), agent_mode="on")
    titles = [c for c in claims if c["field"].endswith(".title")]
    segments = {c["value"]: c["evidence"]["segment"] for c in titles}
    assert "저녁" not in segments["돈가스"]["text"]
    assert "저녁" in segments["라멘"]["text"]
    for title in titles:
        segment = title["evidence"]["segment"]
        assert segment["text"] == text[segment["start"]:segment["end"]]
        assert title["value"] in segment["text"]
    got = collect(sources=[{"source_id": "s1", "position": 0, "transcript": text}],
                  claims=[{**c, "source_id": "s1"} for c in claims])
    meals = {r["title"]: r for r in got.rows}
    assert meals["돈가스"]["end"] <= meals["라멘"]["start"]
    assert meals["돈가스"]["start"] < meals["라멘"]["start"]
    assert meals["라멘"]["start"] == "18:00"


def test_explicit_clocks_are_kept_when_the_stop_context_is_split():
    text = "10/23 11:00 홍대 쇼핑하고 13:00 돈가스 먹고 저녁 19:00 라멘"
    claims = read_source(text, today=date(2026, 10, 22), agent=Reader(("11:00", "13:00", "19:00")), agent_mode="on")
    got = collect(sources=[{"source_id": "s1", "position": 0, "transcript": text}],
                  claims=[{**c, "source_id": "s1"} for c in claims])
    assert [(r["title"], r["start"]) for r in got.rows] == [("홍대", "11:00"), ("돈가스", "13:00"), ("라멘", "19:00")]
