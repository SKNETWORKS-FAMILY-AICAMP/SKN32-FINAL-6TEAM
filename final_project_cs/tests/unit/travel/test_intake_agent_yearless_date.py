"""`[2026-10-28 전수검사 A13]` 읽기 에이전트가 해 없는 날짜(「10월 30일」)에 해를 골라 붙이면 그 해는 원문 근거가 없다.

전에는 인용에 숫자가 있다는 이유만으로 `date_guessed` 가 거짓이라 모델이 고른 해가 확인 표시 없이 확인 화면으로 갔다.
값은 그대로 두고(머리줄 등 다른 곳의 해를 모델이 읽었을 수 있다) 확인 표시와 그 해를 밝힌 안내만 붙인다.
해가 인용에 적힌 날짜(「2026-10-22」 · 「2027년 1월 3일」 · 「'27년 1월 3일」)는 지금처럼 확인 표시 없이 간다."""
from datetime import date

import pytest

from app.domains.travel_ops.components.intake.pipeline import read_source

TODAY = date(2026, 10, 16)


class Agent:
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, answer):
        self.answer = answer

    def structured(self, system, user, schema, *, num_predict=160):
        return self.answer


def _answer(day_line: str, iso: str):
    return {"items": [{"place_quote": "경복궁", "day": 1, "date": iso, "date_quote": day_line, "start": "10:00", "end": None,
                       "time_quote": "10:00", "kind": "activity"}],
            "moves": [], "conditions": [], "preferences": [], "requests": ["register"], "missing": [],
            "trip": {"party_size": None, "days": None, "nights": None}}


def _date_row(rows):
    return next(r for r in rows if r["field"] == "items[0].date")


@pytest.mark.parametrize("quote", ["10월 30일", "10월 30일 1230 출발", "10월 30일 예약번호 123456", "1027년 10월 30일"])
def test_model_picked_year_for_a_yearless_quote_is_flagged_for_review(quote):
    """해 없는 인용 · 해가 아닌 네 자리 숫자 · 모델 값과 다른 해(Codex 검토 지적)는 모두 확인 표시"""
    text = f"{quote}\n10:00 경복궁"
    rows = read_source(text, today=TODAY, agent=Agent(_answer(quote, "2027-10-30")), agent_mode="on", position=0)
    row = _date_row(rows)
    assert row["value"] == "2027-10-30"                    # 값은 바꾸지 않는다
    assert row["needs_review"] is True
    assert "2027" in (row["note"] or "") and "해" in row["note"]


@pytest.mark.parametrize("quote,iso", [("2026-10-22", "2026-10-22"), ("2027년 1월 3일", "2027-01-03"), ("'27년 1월 3일", "2027-01-03"),
                                       ("27년 1월 3일", "2027-01-03"), ("2027.1.3", "2027-01-03")])
def test_quote_with_a_written_year_is_not_flagged(quote, iso):
    text = f"{quote}\n10:00 경복궁"
    rows = read_source(text, today=TODAY, agent=Agent(_answer(quote, iso)), agent_mode="on", position=0)
    row = _date_row(rows)
    assert row["value"] == iso and row["needs_review"] is False
