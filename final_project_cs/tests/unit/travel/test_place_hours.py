# -*- coding: utf-8 -*-
"""장소 영업시간 — 관광공사 원문 → 요일별 시각. `[2026-09-28]` 사용자 결정 「원문을 구조화한다」.

★원문은 실제 관광공사 응답에서 가져왔다(과학책방 갈다 4114555 · 경복궁 126508 · 황생가칼국수 837020 ·
  자하손만두 834669, 2026-09-28 조회). 모델은 흉내다 — 실제 모델 확인은 라이브 실행에서 봤다.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.modules.travel_ops.itinerary_checks import Part, check_itinerary
from app.modules.travel_ops.place_hours import days_in, fits, hours_on, read_by_model, read_by_rule, read_hours

KST = ZoneInfo("Asia/Seoul")
MONDAY, FRIDAY, TUESDAY = date(2026, 9, 28), date(2026, 10, 2), date(2026, 9, 29)
GYEONGBOKGUNG = ("[1월~2월/11월~12월]09:00~17:00 (입장마감 16:00)[3월~5월/9월~10월]09:00~18:00 (입장마감 17:00)"
                 "[6월~8월] 09:00~18:30 (입장마감 17:30)",
                 "매주 화요일 ※ 단, 정기휴일이 공휴일 및 대체공휴일과 겹칠 경우에는 개방하며, 그 다음의 첫 번째 비공휴일이 정기휴일임")


def _at(day: date, hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{day.isoformat()}T{hhmm}:00").replace(tzinfo=KST)


def test_a_simple_text_is_read_by_rule_with_its_closed_days():
    read = read_by_rule("13:00~17:00", "매주 일요일~목요일")
    assert read is not None and read.method == "rule"
    attributes = {"hours_week": read.week}
    assert hours_on(attributes, MONDAY) == "closed"               # ☆실제로 월요일 09:00 에 들어갔던 곳
    assert fits(attributes, _at(FRIDAY, "13:30"), _at(FRIDAY, "15:00")) is True
    assert fits(attributes, _at(FRIDAY, "09:00"), _at(FRIDAY, "10:30")) is False


def test_rule_reads_last_entry_and_no_rest_day_and_leaves_the_rest_to_the_model():
    read = read_by_rule("10:00~18:00 (입장마감 17:00)", "연중무휴")
    assert read.week["sun"] == {"open": "10:00", "close": "18:00", "last_entry": "17:00"}
    assert fits({"hours_week": read.week}, _at(MONDAY, "17:10"), _at(MONDAY, "17:50")) is False   # 입장 마감 뒤
    for use, rest in (GYEONGBOKGUNG, ("11:00~21:30 (마지막 주문 20:30)", "설·추석 당일"),
                      ("평일 10:00~19:00 / 주말 11:00~18:00", "")):
        assert read_by_rule(use, rest) is None, use                # 규칙 밖 — 모델로 간다


def test_day_words_are_days_and_months_or_words_ending_in_il_are_not():
    assert days_in("매주 일요일~목요일") == {"sun", "mon", "tue", "wed", "thu"}
    assert days_in("[1월~2월/11월~12월]09:00~17:00") == set()                 # ☆달을 월요일로 읽었다
    assert days_in("매주 월요일 / 설·추석 당일") == {"mon"}                   # ☆「당일」을 일요일로 읽었다
    assert days_in("평일 10:00~18:00") == set() and days_in("공휴일 휴무") == set()
    assert days_in("금요일~월요일") == {"fri", "sat", "sun", "mon"}
    assert days_in("토,일 휴무") == {"sat", "sun"}


class _Model:
    def __init__(self, answer):
        self.answer, self.calls = answer, 0

    def json(self, system, user):
        self.calls += 1
        return self.answer


def test_seasons_become_the_shortest_window_and_holiday_rules_stay_as_text():
    model = _Model({
        "open": [{"days": [], "open": "09:00", "close": "17:00", "last_entry": "16:00",
                  "quote": "[1월~2월/11월~12월]09:00~17:00 (입장마감 16:00)"},
                 {"days": [], "open": "09:00", "close": "18:30", "last_entry": "17:30",
                  "quote": "[6월~8월] 09:00~18:30 (입장마감 17:30)"}],
        "closed": [{"days": ["tue"], "quote": "매주 화요일"}],
        "conditions": ["※ 단, 정기휴일이 공휴일 및 대체공휴일과 겹칠 경우에는 개방하며"]})
    read = read_hours(*GYEONGBOKGUNG, chat=model)
    assert read.method == "llm" and model.calls == 1
    assert read.week["tue"] == "closed"
    assert read.week["mon"] == {"open": "09:00", "close": "17:00", "last_entry": "16:00"}   # 가장 짧은 쪽
    assert read.conditions and read.dropped == []


def test_what_is_not_in_the_text_is_dropped_not_believed():
    model = _Model({
        "open": [{"days": [], "open": "08:00", "close": "22:00", "quote": "08:00~22:00"},         # 원문에 없는 인용
                 {"days": [], "open": "10:00", "close": "21:30",
                  "quote": "11:00~21:30 (마지막 주문 20:30)"},                                   # 인용에 없는 시각
                 {"days": [], "open": "11:00", "close": "21:30", "last_entry": "20:30",
                  "quote": "11:00~21:30 (마지막 주문 20:30)"}],
        "closed": [{"days": ["mon"], "quote": "설·추석 당일"}],                                   # 인용에 없는 요일
        "conditions": ["설·추석 당일", "매주 수요일 휴무"]})                                       # 원문에 없는 조건
    read = read_hours("11:00~21:30 (마지막 주문 20:30)", "설·추석 당일", chat=model)
    assert len(read.dropped) == 3, read.dropped
    assert read.week["mon"] == {"open": "11:00", "close": "21:30", "last_entry": "20:30"}      # 월요일은 쉬지 않는다
    assert read.conditions == ["설·추석 당일"]


def test_without_a_model_or_with_a_broken_one_the_hours_stay_unknown():
    assert read_by_model(*GYEONGBOKGUNG, chat=None).week == {}

    class Broken:
        def json(self, system, user):
            raise TimeoutError("모델 시간 초과")

    read = read_hours(*GYEONGBOKGUNG, chat=Broken())
    assert read.week == {} and read.method == "none" and "TimeoutError" in read.dropped[0]


def test_the_check_sees_a_closed_day_and_a_late_entry():
    week = read_by_rule("10:00~18:00 (입장마감 17:00)", "매주 월요일").week
    place = {"name": "미술관", "attributes": {"hours_week": week}}

    def part(day, start, end):
        return Part(seq=1, kind="activity", title="미술관", starts_at=_at(day, start), ends_at=_at(day, end),
                    place=place, route=None, detail={})

    assert [v.code for v in check_itinerary([part(MONDAY, "11:00", "12:30")])] == ["closed_day"]
    assert [v.code for v in check_itinerary([part(TUESDAY, "17:10", "17:50")])] == ["after_last_entry"]
    assert check_itinerary([part(TUESDAY, "11:00", "12:30")]) == []
    # 하루 한 칸짜리 옛 모양은 그대로 읽는다
    old = {"name": "옛", "attributes": {"hours": ["09:00", "18:00"]}}
    assert hours_on(old["attributes"], MONDAY).opens.hour == 9
