"""`[2026-10-28 전수검사 A13]` 읽기 에이전트가 해 없는 날짜(「10월 30일」)에 해를 골라 붙이면 그 해는 원문 근거가 없다.

전에는 인용에 숫자가 있다는 이유만으로 `date_guessed` 가 거짓이라 모델이 고른 해가 확인 표시 없이 확인 화면으로 갔다.
해가 인용에 적힌 날짜(「2026-10-22」 · 「2027년 1월 3일」 · 「'27년 1월 3일」)는 지금처럼 확인 표시 없이 간다.

`[2026-11-06 병합 — 날짜 형식은 모델 판단(2026-10-26 사용자 확정)]` 모델 답은 `date_quote` · `year_quote` · `date_form` · `date` 를 낸다
(형식 칸 없는 옛 답은 날짜를 버린다 — `agent_read._grounded_date`).
- 연도를 적었다(explicit_year)면서 연도 인용이 원문에 없으면 정책(연도를 적은 과거만 과거)대로 연도 없는 날 → 오늘 이후 처음 오는 그 날로 두고
  확인 표시 + 「연도를 원문에서 확인하지 못해」 메모(`dates.resolve_dates`). 이 경우 A13 의 「값은 그대로」보다 사용자 확정 정책이 앞선다.
- 연도 인용이 원문에 있지만 모델 날짜의 해와 다르면(「1027년」 인데 2027) A13 대로 값은 두고 확인 표시 + 그 해를 밝힌 안내(`pipeline._year_written`).
- 머리줄에 적힌 해(「2027년 겨울 여행」)는 날짜 인용 밖이어도 연도 근거다 — 확인 표시하지 않는다.
"""
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


def _answer(day_line: str, iso: str, *, year_quote, form="explicit_year"):
    return {"items": [{"place_quote": "경복궁", "day": 1, "date_quote": day_line, "year_quote": year_quote, "date_form": form, "date": iso,
                       "start": "10:00", "end": None, "time_quote": "10:00", "kind": "activity"}],
            "moves": [], "conditions": [], "preferences": [], "requests": ["register"], "missing": [],
            "trip": {"party_size": None, "days": None, "nights": None}}


def _date_row(rows):
    return next(r for r in rows if r["field"] == "items[0].date")


@pytest.mark.parametrize("quote", ["10월 30일", "10월 30일 1230 출발", "10월 30일 예약번호 123456"])
@pytest.mark.parametrize("year_quote", [None, "2027"])
def test_model_year_without_a_written_year_is_flagged_for_review(quote, year_quote):
    """해 없는 인용 · 해가 아닌 네 자리 숫자 — 모델이 explicit_year 라 해도 연도 근거가 원문에 없으면 다가오는 그 날 + 확인 표시"""
    text = f"{quote}\n10:00 경복궁"
    rows = read_source(text, today=TODAY, agent=Agent(_answer(quote, "2027-10-30", year_quote=year_quote)), agent_mode="on", position=0)
    row = _date_row(rows)
    assert row["value"] == "2026-10-30"                    # 오늘(10-16) 이후 처음 오는 10월 30일
    assert row["needs_review"] is True
    assert "2026" in (row["note"] or "") and "연도" in row["note"]


def test_model_year_differing_from_the_quoted_year_keeps_the_value_and_is_flagged():
    """연도 인용(「1027년」)은 원문에 있지만 모델 해(2027)와 다르다(Codex 검토 지적) — 값은 두고 확인 표시와 그 해를 밝힌 안내"""
    quote = "1027년 10월 30일"
    rows = read_source(f"{quote}\n10:00 경복궁", today=TODAY, agent=Agent(_answer(quote, "2027-10-30", year_quote="1027년")),
                       agent_mode="on", position=0)
    row = _date_row(rows)
    assert row["value"] == "2027-10-30"                    # 값은 바꾸지 않는다
    assert row["needs_review"] is True
    assert "2027" in (row["note"] or "") and "해" in row["note"]


@pytest.mark.parametrize("quote,year_quote,iso", [("2026-10-22", "2026", "2026-10-22"), ("2027년 1월 3일", "2027년", "2027-01-03"),
                                                  ("'27년 1월 3일", "'27년", "2027-01-03"), ("27년 1월 3일", "27년", "2027-01-03"),
                                                  ("2027.1.3", "2027", "2027-01-03")])
def test_quote_with_a_written_year_is_not_flagged(quote, year_quote, iso):
    text = f"{quote}\n10:00 경복궁"
    rows = read_source(text, today=TODAY, agent=Agent(_answer(quote, iso, year_quote=year_quote)), agent_mode="on", position=0)
    row = _date_row(rows)
    assert row["value"] == iso and row["needs_review"] is False


def test_year_written_in_a_header_line_is_grounded():
    """머리줄의 해 — 날짜 인용(「1월 3일」) 밖에 있어도 모델이 인용한 연도 조각이 원문에 있으면 적힌 해다"""
    text = "2027년 겨울 여행\n1월 3일\n10:00 경복궁"
    rows = read_source(text, today=TODAY, agent=Agent(_answer("1월 3일", "2027-01-03", year_quote="2027년")), agent_mode="on", position=0)
    row = _date_row(rows)
    assert row["value"] == "2027-01-03" and row["needs_review"] is False
