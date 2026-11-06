"""날짜 형식은 모델(E4B)이 판단한다 — `date_form`(explicit_year · relative · yearless) + 연도 근거 `year_quote`. `[2026-10-26 사용자 지시]`

★코드는 고객 원문을 숫자 · 낱말로 다시 읽지 않는다. 인용(`date_quote` · `year_quote`)이 원문에 실제로 있는지와 필드끼리 맞는지만 본다.
  전에는 모델 연도 숫자가 본문 **아무 줄**에 있으면(「입장료 2026원」) 연도 명시로 봐서 연도 없는 「3/5」를 과거로 오판했다.
정책: 연도 없는 날짜 = 오늘 이후 처음 오는 그 날(오늘 포함) · 연도를 적은 과거만 과거 · 상대 표현은 오늘 기준(지난 날이어도 그대로)."""
from datetime import date, datetime

from app.domains.travel_ops.components.intake import agent_read, dates
from app.domains.travel_ops.components.intake.pipeline import read_source
from app.domains.travel_ops.components.itinerary import itinerary_checks as checks

TODAY = date(2026, 10, 26)
NOW = datetime(2026, 10, 26, 12, tzinfo=checks.KST)


class Agent:
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, answer):
        self.answer = answer

    def structured(self, system, user, schema, *, num_predict=160):
        return self.answer


def _answer(items):
    return {"items": items, "moves": [], "conditions": [], "preferences": [], "requests": ["register"], "missing": [],
            "trip": {"party_size": None, "days": None, "nights": None}}


def _item(place, when, date_quote, form, *, year_quote=None, start="10:00"):
    return {"place_quote": place, "day": 1, "date_quote": date_quote, "year_quote": year_quote, "date_form": form, "date": when,
            "start": start, "end": None, "time_quote": start, "kind": "activity"}


def _date_row(text, item):
    rows = read_source(text, today=TODAY, agent=Agent(_answer([item])), agent_mode="on", position=0)
    return next(r for r in rows if r["field"] == "items[0].date")


def _all_past(value):
    start = datetime.fromisoformat(f"{value}T10:00").replace(tzinfo=checks.KST)
    return checks.all_dates_before_today([(start, start)], now=NOW)


def test_schema_asks_the_model_for_the_date_form_and_the_year_quote():
    # `[2026-11-06 병합]` 항목 스키마는 I05 의 두 갈래(날짜 없음 · 날짜+인용, `agent_read._dated_items`)다 — 두 갈래 모두 같은 칸 순서를 지킨다
    branches = agent_read.SCHEMA["properties"]["items"]["items"]["anyOf"]
    assert len(branches) == 2
    for item in branches:
        assert {"date_form", "year_quote"} <= set(item["required"])
        assert item["properties"]["date_form"]["enum"] == ["explicit_year", "relative", "yearless", None]
        order = list(item["properties"])
        # 인용을 먼저 적고 → 판단 → 값(작은 모델이 근거를 보고 고르게)
        assert order.index("date_quote") < order.index("year_quote") < order.index("date_form") < order.index("date")


def test_a_number_elsewhere_in_the_text_is_not_a_written_year():
    text = "3/5 10시 경복궁, 입장료 2026원"
    item = _item("경복궁", "2026-03-05", "3/5", "yearless")
    assert agent_read.ground(_answer([item]), text.splitlines()).items[0].date == "--03-05"
    row = _date_row(text, item)
    assert row["value"] == "2027-03-05" and row["evidence"]["how"] == "year_filled" and row["needs_review"] is True
    assert not _all_past(row["value"])


def test_a_two_digit_year_the_model_quotes_keeps_the_past_date():
    text = "'26.3.5 10시 경복궁"
    row = _date_row(text, _item("경복궁", "2026-03-05", "'26.3.5", "explicit_year", year_quote="'26"))
    assert row["value"] == "2026-03-05" and row["evidence"]["how"] == "written"
    assert _all_past(row["value"])


def test_a_year_written_in_a_header_line_is_quoted_separately():
    text = "2026년 여행\n3월 5일 10시 경복궁"
    out = agent_read.ground(_answer([_item("경복궁", "2026-03-05", "3월 5일", "explicit_year", year_quote="2026년")]), text.splitlines())
    assert out.items[0].date == "2026-03-05" and out.items[0].date_guessed is False


def test_an_explicit_year_without_a_source_quote_is_not_trusted_as_written():
    # 모델이 「연도를 적었다」고 했지만 연도 인용이 원문에 없다 — 연도를 명시한 과거로 보지 않고(정책: 적은 연도만) 연도 없는 날로 둔다 · 버린 수를 센다
    text = "3월 5일 10시 경복궁"
    out = agent_read.ground(_answer([_item("경복궁", "2026-03-05", "3월 5일", "explicit_year", year_quote="2026년")]), text.splitlines())
    assert out.items[0].date == "--03-05" and out.report["dropped"]["date_year"] == 1
    out = agent_read.ground(_answer([_item("경복궁", "2026-03-05", "3월 5일", "explicit_year", year_quote=None)]), text.splitlines())
    assert out.items[0].date == "--03-05" and out.report["dropped"]["date_year"] == 1


def test_relative_dates_with_digits_are_the_models_date_counted_from_today():
    text = "다음 달 5일 10시 경복궁"
    out = agent_read.ground(_answer([_item("경복궁", "2026-11-05", "다음 달 5일", "relative")]), text.splitlines())
    assert out.items[0].date == "2026-11-05" and out.items[0].date_guessed is True
    row = _date_row(text, _item("경복궁", "2026-11-05", "다음 달 5일", "relative"))
    assert row["value"] == "2026-11-05" and row["evidence"]["how"] == "agent_relative"


def test_a_relative_past_date_stays_past():
    text = "작년 크리스마스 저녁 7시 명동성당"
    row = _date_row(text, _item("명동성당", "2025-12-25", "작년 크리스마스", "relative", start="19:00"))
    assert row["value"] == "2025-12-25" and _all_past(row["value"])


def test_a_missing_date_form_is_a_contract_error_not_a_trusted_year():
    # 옛 형식 답(판단 칸 없음) — 연도를 믿지도, 연도 없는 날로 바꾸지도 않는다. 날짜를 버리고 센다(날짜는 묻는 길로)
    text = "3월 5일 10시 경복궁"
    item = _item("경복궁", "2026-03-05", "3월 5일", None)
    del item["date_form"]
    out = agent_read.ground(_answer([item]), text.splitlines())
    assert out.items[0].date is None and out.items[0].date_quote is None
    assert out.report["dropped"]["date_form"] == 1


def test_system_prompt_examples_follow_today():
    system = agent_read.system_for(TODAY)
    assert "2026-10-26" in system
    # 예시의 「연도 없는 날」 값은 오늘에서 계산한다(고정 날짜가 시간이 지나 과거가 되지 않게)
    assert dates.next_month_day(8, 15, TODAY).isoformat() in system


def test_a_yearless_february_29_waits_for_the_next_leap_year():
    assert dates._fill_year("--02-29", TODAY) == date(2028, 2, 29)


def test_chat_add_with_number_noise_uses_the_next_such_date():
    from app.domains.travel_ops.components.conversation import chat_edit

    message = "3/5 10:00 경복궁 넣어줘, 입장료 2026원"
    answer = _answer([_item("경복궁", "2026-03-05", "3/5", "yearless")])
    ops = chat_edit._read_adds(message, lambda text, today: agent_read.ground(answer, text.splitlines()), stops=[], now=NOW, day=None)
    assert [(o.date, o.starts_at) for o in ops] == [("2027-03-05", "10:00")]


def test_an_impossible_month_day_is_unknown_not_moved_to_the_28th():
    got, ask = dates.resolve_dates([{"day": 1, "date": "--02-30", "line": 1}], today=TODAY, lines=["2/30 10시 경복궁"])
    assert got[0].value is None and got[0].how == "unknown" and got[0].needs_review is True and ask is True
    out = agent_read.ground(_answer([_item("경복궁", "2027-02-30", "2/30", "yearless")]), ["2/30 10시 경복궁"])
    assert out.items[0].date is None and out.report["dropped"]["date"] == 1


def test_an_unverified_explicit_year_is_shown_as_an_assumed_year_with_its_own_note():
    # 연도 없는 「10월 25일」(어제의 월 · 일)을 모델이 explicit_year · 연도 인용 없이 냈다(실측) — 그대로 믿으면 지난 날이라 전부 과거로 거절된다
    text = "10월 25일 10시 경복궁"
    row = _date_row(text, _item("경복궁", "2026-10-25", "10월 25일", "explicit_year", year_quote=None))
    assert row["value"] == "2027-10-25" and row["evidence"]["how"] == "year_filled" and row["needs_review"] is True
    assert "연도를 원문에서 확인하지 못해" in row["note"]
    plain = _date_row(text, _item("경복궁", "2026-10-25", "10월 25일", "yearless"))
    assert "해가 적혀 있지 않아" in plain["note"]


def test_contract_counters_cover_missing_form_with_no_date_and_mismatched_year_quotes():
    text = "2027년 맞이 12/31 23시 보신각"
    no_date = _item("보신각", None, None, None)
    del no_date["date_form"]
    out = agent_read.ground(_answer([no_date]), [text])
    assert out.report["dropped"]["date_form"] == 1
    # 연도 인용은 원문에 있는데 형식은 yearless — 모델 형식을 따르되(다가오는 12월 31일) 어긋남을 센다
    out = agent_read.ground(_answer([_item("보신각", "2026-12-31", "12/31", "yearless", year_quote="2027년", start="23:00")]), [text])
    assert out.items[0].date == "--12-31" and out.report["dropped"]["date_mismatch"] == 1
