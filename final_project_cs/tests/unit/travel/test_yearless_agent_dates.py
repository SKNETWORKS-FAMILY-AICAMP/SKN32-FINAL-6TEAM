"""연도 없는 날짜는 오늘 이후 처음 오는 그 날(오늘 포함) — 모델(E4B)이 낸 구조화 날짜 + 원문 인용으로 판정한다. `[2026-10-26 사용자 확정]`

모델이 연도 없는 「10월 5일」에 올해 연도를 붙여 이미 지난 날로 내도, 연도가 원문에 없으면 명시 과거로 보지 않는다.
연도를 원문에 적은 과거만 과거다(전부 과거 가드 `all_dates_before_today` 대상)."""
from datetime import date, datetime

from app.domains.travel_ops.components.intake import agent_read
from app.domains.travel_ops.components.intake.pipeline import read_source
from app.domains.travel_ops.components.itinerary import itinerary_checks as checks

TODAY = date(2026, 10, 26)


class Agent:
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, answer):
        self.answer = answer

    def structured(self, system, user, schema, *, num_predict=160):
        return self.answer


def _answer(items):
    return {"items": items, "moves": [], "conditions": [], "preferences": [], "requests": ["register"], "missing": [],
            "trip": {"party_size": None, "days": None, "nights": None}}


def _item(quote, when, date_quote, start, form="yearless", year_quote=None):
    # `[2026-10-26]` 날짜 형식 · 연도 인용은 모델이 낸다(`date_form` · `year_quote`) — 이 대역은 그 계약의 답이다
    return {"place_quote": quote, "day": 1, "date": when, "date_quote": date_quote, "year_quote": year_quote, "date_form": form,
            "start": start, "end": None,
            "time_quote": start, "kind": "activity"}


def _dates(rows):
    return {int(r["field"][6:r["field"].index("]")]): r for r in rows if r["field"].startswith("items[") and r["field"].endswith(".date")}


def test_ground_keeps_month_day_but_drops_a_year_the_quote_does_not_state():
    lines = ["10월 5일 10:00 경복궁"]
    out = agent_read.ground(_answer([_item("경복궁", "2026-10-05", "10월 5일", "10:00")]), lines)
    assert out.items[0].date == "--10-05"           # 연도는 원문에 없다 — 날짜 해석(`dates.resolve_dates`)이 다가오는 날로 채운다
    assert out.items[0].date_guessed is False


def test_ground_keeps_a_year_written_in_the_quote_or_text():
    out = agent_read.ground(_answer([_item("경복궁", "2026-10-05", "2026년 10월 5일", "10:00", "explicit_year", "2026년")]), ["2026년 10월 5일 10:00 경복궁"])
    assert out.items[0].date == "2026-10-05"
    header = ["2026년 여행", "10월 5일 10:00 경복궁"]
    out = agent_read.ground(_answer([_item("경복궁", "2026-10-05", "10월 5일", "10:00", "explicit_year", "2026년")]), header)
    assert out.items[0].date == "2026-10-05"         # 연도를 원문 어딘가(머리줄)에 적었다 — 명시한 연도다


def test_relative_dates_without_digits_stay_agent_relative():
    out = agent_read.ground(_answer([_item("경복궁", "2026-10-28", "모레", "10:00", "relative")]), ["모레 10:00 경복궁"])
    assert out.items[0].date == "2026-10-28" and out.items[0].date_guessed is True


def test_yearless_past_month_day_from_the_model_becomes_the_next_such_date():
    text = "10월 5일 10:00 경복궁"
    rows = read_source(text, today=TODAY, agent=Agent(_answer([_item("경복궁", "2026-10-05", "10월 5일", "10:00")])),
                       agent_mode="on", position=0)
    row = _dates(rows)[0]
    assert row["value"] == "2027-10-05" and row["evidence"]["how"] == "year_filled" and row["needs_review"] is True
    start = datetime.fromisoformat(f"{row['value']}T10:00").replace(tzinfo=checks.KST)
    assert not checks.all_dates_before_today([(start, start)], now=datetime(2026, 10, 26, 12, tzinfo=checks.KST))


def test_yearless_today_stays_today():
    text = "10월 26일 18:00 경복궁"
    rows = read_source(text, today=TODAY, agent=Agent(_answer([_item("경복궁", "2026-10-26", "10월 26일", "18:00")])),
                       agent_mode="on", position=0)
    assert _dates(rows)[0]["value"] == "2026-10-26"


def test_explicit_past_year_stays_past_for_the_all_past_guard():
    text = "2026년 10월 5일 10:00 경복궁"
    rows = read_source(text, today=TODAY, agent=Agent(_answer([_item("경복궁", "2026-10-05", "2026년 10월 5일", "10:00", "explicit_year", "2026년")])),
                       agent_mode="on", position=0)
    row = _dates(rows)[0]
    assert row["value"] == "2026-10-05" and row["evidence"]["how"] == "written"
    start = datetime.fromisoformat(f"{row['value']}T10:00").replace(tzinfo=checks.KST)
    assert checks.all_dates_before_today([(start, start)], now=datetime(2026, 10, 26, 12, tzinfo=checks.KST))
