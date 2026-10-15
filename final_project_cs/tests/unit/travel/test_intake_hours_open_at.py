"""접수 확인 운영시간 줄의 「시작 시각에 열려 있나」(`open_at`) · 요식 판정 그림자 비교. `[2026-10-15]`

운영시간 줄의 결과 warn 에는 「시작 때 이미 닫힘」과 「끝나기 전에 닫음 · 마지막 주문 임박」이 함께 담긴다.
그림자가 warn 을 통째로 ok 로 세어 같은 판단(「영업 안 함」)을 어긋남으로 잡았다(로컬 접수 8건 중 3줄 — 정식당 11:30 · 하동관 18:00 · 진진 23:30).
"""
import pytest

from app.domains.travel_ops.components.intake.hours import HoursFacts
from app.domains.travel_ops.components.intake.review import _hours_lines
from app.domains.travel_ops.instances.dining.shadow import rule_verdicts

DAY = "2026-10-28"                                       # 수요일
PLACE = {"name": "가게"}


def _row(start, end=None):
    return {"date": DAY, "start": start, "end": end, "place": PLACE}


def _facts(**attributes):
    return HoursFacts(known=True, attributes=attributes, source="dining_ledger")


@pytest.mark.parametrize("start, end, attributes, expected", [
    ("11:30", "12:30", {"hours": ["12:00", "22:00"]}, "bad"),                 # 열기 전 시작
    ("18:00", "19:00", {"hours": ["07:00", "16:00"]}, "bad"),                 # 닫은 뒤 시작
    ("21:00", "22:30", {"hours": ["11:00", "21:30"]}, "ok"),                  # 시작 때는 열림 — 끝나기 전에 닫을 뿐
    ("15:30", "16:30", {"hours": ["11:00", "21:00"], "break": ["15:00", "17:00"]}, "bad"),   # 브레이크에 시작
    ("12:00", "13:00", {"hours": ["11:00", "21:00"]}, "ok"),
    ("12:00", "13:00", {"hours_week": {"wed": "closed"}}, "bad"),             # 쉬는 날
])
def test_open_at_is_about_the_start_time(start, end, attributes, expected):
    hours, _ = _hours_lines(_row(start, end), _facts(**attributes), [])
    assert hours["open_at"] == expected


def test_the_ledger_slot_verdict_comes_first_and_unknown_hours_carry_nothing():
    facts = _facts(hours=["11:00", "21:00"])
    facts.open_at_slot = False                                                # 원장이 그 시각엔 닫는다고 판정
    assert _hours_lines(_row("12:00", "13:00"), facts, [])[0]["open_at"] == "bad"
    assert "open_at" not in _hours_lines(_row("12:00"), HoursFacts(known=False), [])[0]


def test_the_screen_line_is_unchanged():
    hours, _ = _hours_lines(_row("18:00", "19:00"), _facts(hours=["07:00", "16:00"]), [])
    assert hours["row"] == "hours" and hours["result"] in ("warn", "ok") and hours["text"]


def test_shadow_compares_hours_by_the_start_time_not_by_the_warning():
    closed_at_start = {"rows": [{"row": "hours", "result": "warn", "text": "16:00에 닫아요", "open_at": "bad"}]}
    closes_early = {"rows": [{"row": "hours", "result": "warn", "text": "21:30에 닫아요", "open_at": "ok"}]}
    old_payload = {"rows": [{"row": "hours", "result": "warn", "text": "…"}]}  # 이 칸이 생기기 전에 저장된 검사
    assert rule_verdicts(closed_at_start) == {"open_at": "bad"}
    assert rule_verdicts(closes_early) == {"open_at": "ok"}
    assert rule_verdicts(old_payload) == {"open_at": "ok"}
