"""전부 과거 접수 관문(`review.wholly_past`, 원격 c023140b5)과 연도 없는 · 연도 미확인 · 없는 날짜 해석(`dates.resolve_dates`, 과거 날짜 가드레일 확장)이 맞물리는지.

`[2026-10-26 병합 877e6723b]` 두 구현이 한 접수 경로에서 만난다 — 읽기가 날짜를 정한 뒤(`resolve_dates`) 첫 검사 저장본을 관문이 본다.
- 연도 없는 날 · 모델이 연도를 적었다고 했지만 원문에 연도가 없던 날(`year_unverified`)은 오늘 이후 처음 오는 그 날 → 과거가 아니다.
- 어느 해에도 없는 월 · 일(「2/30」)은 날짜 모름 → 관문은 모르는 날을 과거로 추정하지 않는다.
- 확정된 지난 날(연도를 적은 날 · 오늘에서 센 「어제」 같은 날)로만 이뤄진 계획이 전부 과거로 거절된다.
- 읽기 에이전트 경로(`agent_read.ground` → `pipeline._agent_rows`)에서 달력에 없는 날로 버린 날짜도 「모름」이어야 한다 — 다른 일정의 첫날로
  채우면(`day_offset`) 지어낸 날짜가 관문을 연다(Codex 병합 검토 2차 지적).
제품 시계(`itinerary_checks.datetime`)만 고정한다. DB · 모델 호출 없음(모델은 고정 답 대역).
"""
from datetime import date, datetime

import pytest

from app.domains.travel_ops.components.intake import review as review_module
from app.domains.travel_ops.components.intake.dates import resolve_dates
from app.domains.travel_ops.components.intake.pipeline import read_source
from app.domains.travel_ops.components.itinerary import itinerary_checks as checks

NOW = datetime(2032, 5, 8, 12, tzinfo=checks.KST)
TODAY = NOW.date()


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)
    monkeypatch.setattr(checks, "datetime", Frozen)


def _payload(items):
    dated, _ask = resolve_dates(items, today=TODAY, lines=[])
    return dated, {"items": [{"date": d.value, "end_date": None} for d in dated]}


@pytest.mark.parametrize("item", [
    {"date": "--05-01"},                                   # 연도 없는 지난 월 · 일 → 다음 해
    {"date": "--05-01", "year_unverified": True},          # 연도 인용이 원문에 없던 explicit_year → 연도 없는 날로
])
def test_yearless_past_month_day_is_not_wholly_past(item):
    dated, payload = _payload([item])
    assert dated[0].value == "2033-05-01" and dated[0].how == "year_filled" and dated[0].needs_review
    assert review_module.wholly_past(payload) is False


def test_impossible_month_day_is_unknown_not_past():
    dated, payload = _payload([{"date": "--02-30"}, {"date": "2031-01-01"}])
    assert dated[0].value is None and dated[0].how == "unknown"
    # 하나라도 날짜를 모르면 전부 과거라고 하지 않는다 — 지난 날과 섞여도
    assert review_module.wholly_past(payload) is False


def test_written_past_year_alone_is_wholly_past():
    dated, payload = _payload([{"date": "2031-01-01"}, {"date": "2031-01-02"}])
    assert [d.how for d in dated] == ["written", "written"]
    assert review_module.wholly_past(payload) is True


def test_leap_day_yearless_goes_to_next_leap_year_not_past():
    dated, payload = _payload([{"date": "--02-29"}])
    assert dated[0].value == date(2036, 2, 29).isoformat()
    assert review_module.wholly_past(payload) is False


class Agent:
    """읽기 에이전트 고정 답 대역 — 실제 `structured(system, user, schema, *, num_predict)` 서명."""
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, answer):
        self.answer = answer

    def structured(self, system, user, schema, *, num_predict=160):
        return self.answer


def _agent_item(quote, when, date_quote, start, form, year_quote=None):
    return {"place_quote": quote, "day": 1, "date": when, "date_quote": date_quote, "year_quote": year_quote, "date_form": form,
            "start": start, "end": None, "time_quote": start, "kind": "activity"}


def _agent_dates(text, items, today):
    answer = {"items": items, "moves": [], "conditions": [], "preferences": [], "requests": ["register"], "missing": [],
              "trip": {"party_size": None, "days": None, "nights": None}}
    rows = read_source(text, today=today, agent=Agent(answer), agent_mode="on", position=0)
    return {int(r["field"][6:r["field"].index("]")]): r for r in rows if r["field"].startswith("items[") and r["field"].endswith(".date")}


def test_agent_impossible_date_next_to_a_written_past_date_is_unknown_not_first_day():
    today = date(2026, 10, 26)
    text = "2026년 10월 5일 10:00 경복궁\n2월 30일 14:00 창덕궁"
    dates = _agent_dates(text, [_agent_item("경복궁", "2026-10-05", "2026년 10월 5일", "10:00", "explicit_year", "2026년"),
                                _agent_item("창덕궁", "2026-02-30", "2월 30일", "14:00", "yearless")], today)
    assert dates[0]["value"] == "2026-10-05" and dates[0]["evidence"]["how"] == "written"
    # 달력에 없는 날 — 첫날(10월 5일)로 지어내지 않는다
    assert dates[1]["value"] is None and dates[1]["evidence"]["how"] == "unknown" and dates[1]["needs_review"] is True
    assert "2월 30일" in (dates[1]["note"] or "")
    payload = {"items": [{"date": dates[i]["value"], "end_date": None} for i in (0, 1)]}
    assert review_module.wholly_past(payload, now=datetime(2026, 10, 26, 12, tzinfo=checks.KST)) is False


def test_agent_impossible_explicit_year_date_is_unknown_too():
    today = date(2026, 10, 26)
    text = "2025년 10월 5일 10:00 경복궁\n2025년 2월 29일 14:00 창덕궁"
    dates = _agent_dates(text, [_agent_item("경복궁", "2025-10-05", "2025년 10월 5일", "10:00", "explicit_year", "2025년"),
                                _agent_item("창덕궁", "2025-02-29", "2025년 2월 29일", "14:00", "explicit_year", "2025년")], today)
    assert dates[1]["value"] is None and dates[1]["evidence"]["how"] == "unknown"
    assert "2025년 2월 29일" in (dates[1]["note"] or "")
