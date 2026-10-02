# -*- coding: utf-8 -*-
"""밀도를 **실제 판단에** 쓴다 — 자동 변경이 하루 밀도를 나쁘게 만들면 순위에서 뒤로 밀린다. `[2026-10-03 사용자 지시 · D-019 개정]`

☆전에는 밀도가 **관측만** 했다(`D-019 — 거절·재조정 없음`) — 등록·조회 응답에 숫자를 줄 뿐, 감시가 일정을 바꿀 때는 아무도 안 봤다. 하루가 원하신 여유보다 빡빡해지든 말든 그대로 적용됐다.

★지키려는 것
 ①잴 수 있던 날이 목표 안 → 밖이 되면 `new_exceed` ②이미 밖이던 날은 **허용 오차**(`travel.density.gate.worsen_tolerance`)보다 더 나빠질 때만 `worse` — 잡음에 걸리지 않는다
 ③잴 수 있던 날을 못 재게 되면 `unmeasurable`(결정 15) ④바꾸기 전에 못 쟀던 날 · 밀도 목표가 없는 여행은 아무것도 안 건다
 ⑤`soft`(기본): 밀도를 나쁘게 만드는 안은 **뒤로 밀고**, 구조 위반 없고 밀도도 안 나쁜 안이 있으면 그것을 쓴다 — 없으면 **가장 덜 나쁜 안**을 쓰되 알림에 무엇이 어떻게 빡빡해졌는지 적는다(고장 난 항목을 그대로 두는 것이 더 나쁘다)
 ⑥`hard`: 구조 위반처럼 막는다 ⑦구조 위반은 밀도 설정과 상관없이 늘 막는다

재현:

    python -m pytest tests/unit/travel/test_density_gate.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.settings import get_guardrails
from app.modules.travel_ops import itinerary_fit
from app.modules.travel_ops.density import density_regressions
from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.itinerary_changes import ItineraryChange, _with_fallbacks
from app.modules.travel_ops.itinerary_checks import parts_from_items
from app.modules.travel_ops.itinerary_fit import fit_change

KST = ZoneInfo("Asia/Seoul")
DAY = datetime(2026, 10, 6, 10, 0, tzinfo=KST)
DENSITY = {"level": "normal", "days": {"2026-10-06": {"starts_at": "2026-10-06T10:00:00+09:00",
                                                       "ends_at": "2026-10-06T22:00:00+09:00", "buffer_minutes": 0}}}
TRIP = {"constraints": {"density": DENSITY}, "party_size": 2}       # 하루 720분 · 목표 0.55 → 점유 396분을 넘으면 「목표 밖」


def _place(name):
    return {"place_id": str(uuid4()), "name": name, "kind": "activity", "latitude": 37.5, "longitude": 127.0,
            "attributes": {"hours": ["09:00", "22:00"]}}


def _day(first_minutes=180, second_minutes=180, transfer=10):
    """A(10:00~) — 60분 쉼 — B. B 앞 이동 `transfer` 분을 명시해 하루를 **잴 수 있게** 둔다(분자 = 두 항목 + 이동)."""
    a = Item(item_id=uuid4(), seq=1, kind="activity", title="A", place_id=uuid4(), starts_at=DAY,
             ends_at=DAY + timedelta(minutes=first_minutes), place=_place("A"))
    b_start = DAY + timedelta(minutes=first_minutes + 60)
    b = Item(item_id=uuid4(), seq=2, kind="activity", title="B", place_id=uuid4(), starts_at=b_start,
             ends_at=b_start + timedelta(minutes=second_minutes), place=_place("B"),
             detail={"transfer_minutes_before": transfer} if transfer is not None else {})
    return a, b


def _swap(item: Item, name: str, minutes: int) -> ItineraryChange:
    """`item` 을 같은 시작에 `minutes` 분짜리 다른 곳으로 — 하루 점유가 그만큼 달라진다."""
    repl = item.replaced_by(place=_place(name), title=name, ends_at=item.starts_at + timedelta(minutes=minutes), detail=dict(item.detail))
    return ItineraryChange(reason="auto_adjusted", causes=[], notice={"text": f"{name}(으)로 바꿨어요"},
                           replacements={item.item_id: repl}, summary={"to": name})


def _ranked(*changes):
    return _with_fallbacks(lambda c, _others: c, list(changes))


def _ratio(items):
    from app.modules.travel_ops.density import measure_density

    return measure_density(parts_from_items(items), TRIP["constraints"])["density"][0]


# ── 판정 규칙 ────────────────────────────────────────────────

def test_the_baseline_day_is_measurable_and_inside_the_target():
    a, b = _day()
    row = _ratio([a, b])
    assert row["status"] == "ok" and round(row["actual_density"], 3) == round(370 / 720, 3)


def test_a_change_that_pushes_the_day_over_the_target_is_a_new_exceed():
    a, b = _day()
    after = [_swap(a, "A2", 210).replacements[a.item_id], b]                     # 210 + 180 + 10 = 400분 > 396
    [shift] = density_regressions(TRIP["constraints"], parts_from_items([a, b]), parts_from_items(after))
    assert shift.kind == "new_exceed" and shift.date == "2026-10-06"
    assert shift.target == 0.55 and round(shift.after, 3) == round(400 / 720, 3)
    assert "10월 6일" in shift.sentence() and "밀도" not in shift.sentence() and "51%" in shift.sentence() and "56%" in shift.sentence()


def test_a_day_already_over_the_target_is_only_blamed_when_it_gets_worse_than_the_tolerance():
    a, b = _day(first_minutes=200, second_minutes=200)                           # 410분 > 396 — 이미 목표 밖
    parts = parts_from_items([a, b])
    jitter = parts_from_items([_swap(a, "A2", 210).replacements[a.item_id], b])      # +10분 = 1.4%p < 2%p
    assert density_regressions(TRIP["constraints"], parts, jitter) == []
    worse = parts_from_items([_swap(a, "A3", 240).replacements[a.item_id], b])       # +40분 = 5.6%p
    [shift] = density_regressions(TRIP["constraints"], parts, worse)
    assert shift.kind == "worse" and "이미" in shift.sentence()
    better = parts_from_items([_swap(a, "A4", 150).replacements[a.item_id], b])
    assert density_regressions(TRIP["constraints"], parts, better) == []


def test_a_change_that_makes_a_measurable_day_unmeasurable_counts():
    a, b = _day()
    broken = b.replaced_by(place=_place("B2"), title="B2", detail={})                # 이동 시간을 모르는 곳 — 하루를 못 잰다
    [shift] = density_regressions(TRIP["constraints"], parts_from_items([a, b]), parts_from_items([a, broken]))
    assert shift.kind == "unmeasurable" and shift.after is None and "확인하지 못했어요" in shift.sentence()


def test_a_day_that_was_not_measurable_before_is_not_blamed_and_no_target_means_no_check():
    a, b = _day(transfer=None)                                                       # 이동 시간 누락 → 바꾸기 전부터 못 잰다
    assert _ratio([a, b])["status"] == "unmeasurable"
    after = [_swap(a, "A2", 400).replacements[a.item_id], b]
    assert density_regressions(TRIP["constraints"], parts_from_items([a, b]), parts_from_items(after)) == []
    a2, b2 = _day()
    big = [_swap(a2, "A9", 600).replacements[a2.item_id], b2]
    assert density_regressions({}, parts_from_items([a2, b2]), parts_from_items(big)) == []       # 밀도 목표 없음


# ── 고르기 ──────────────────────────────────────────────────

def test_soft_mode_demotes_the_option_that_shakes_the_density_and_says_why():
    a, b = _day()
    over, calm = _swap(a, "빡빡한 곳", 210), _swap(a, "여유 있는 곳", 180)
    fit = fit_change(_ranked(over, calm), trip=TRIP, items=[a, b])
    assert fit.rank == 2 and fit.change.summary["to"] == "여유 있는 곳" and fit.accepted == []
    assert [(s.rank, s.name, s.why) for s in fit.skipped] == [(1, "빡빡한 곳", "density")]
    assert "1순위(빡빡한 곳)은(는) 그날 일정이 원하신 여유보다 빡빡해져 2순위로 골랐어요" in fit.change.notice["text"]
    assert "밀도" not in fit.change.notice["text"]


def test_the_best_that_keeps_the_density_is_used_without_a_note():
    a, b = _day()
    fit = fit_change(_ranked(_swap(a, "그대로", 180), _swap(a, "빡빡", 240)), trip=TRIP, items=[a, b])
    assert fit.rank == 1 and fit.skipped == [] and "※" not in fit.change.notice["text"]


def test_when_every_option_shakes_the_density_the_least_bad_one_is_applied_and_the_notice_tells_the_cost():
    """고장 난 항목을 그대로 두는 것보다 낫다 — 가장 덜 나쁜 안(목표를 덜 넘는 쪽)을 쓰고 무엇이 빡빡해졌는지 적는다."""
    a, b = _day()
    worst, mild, mid = _swap(a, "가장 빡빡", 238), _swap(a, "조금 빡빡", 215), _swap(a, "중간", 225)
    fit = fit_change(_ranked(worst, mid, mild), trip=TRIP, items=[a, b])
    assert fit.change.summary["to"] == "조금 빡빡" and fit.rank == 3
    assert [s.kind for s in fit.accepted] == ["new_exceed"]
    text = fit.change.notice["text"]
    assert "더 나은 안이 없어 이 안을 적용했지만 10월 6일 일정이 원하신 여유보다 빡빡해졌어요" in text
    assert "1·2순위(1순위 가장 빡빡, 2순위 중간)은(는) 그날 일정이 원하신 여유보다 빡빡해져 3순위로 골랐어요" in text


def test_a_candidate_that_loses_the_measurement_ranks_behind_one_with_a_known_excess():
    a, b = _day()
    unknown = ItineraryChange(reason="auto_adjusted", causes=[], notice={"text": "모르는 곳으로"},
                              replacements={b.item_id: b.replaced_by(place=_place("B2"), title="B2", detail={})}, summary={"to": "B2"})
    known = _swap(a, "알려진 초과", 215)
    fit = fit_change(_ranked(unknown, known), trip=TRIP, items=[a, b])
    assert fit.change.summary["to"] == "알려진 초과" and fit.rank == 2


def test_the_structural_violation_is_still_a_wall_whatever_the_density_says():
    """겹침은 밀도와 상관없이 막는다 — 밀도가 좋아도(점유가 줄어도) 안 된다."""
    a, b = _day()
    overlapping = _swap(a, "겹치는 곳", 250)                                          # B(10:00+240 시작)와 겹친다
    fit = fit_change(_ranked(overlapping), trip=TRIP, items=[a, b])
    assert fit.change is None and fit.skipped[0].why == "schedule" and "겹친다" in fit.skipped[0].reasons[0]


def test_hard_mode_blocks_a_density_regression_like_a_structural_violation(monkeypatch):
    class _Hard:
        def get(self, key):
            return "hard" if key == "travel.density.gate.mode" else get_guardrails().get(key)

    monkeypatch.setattr(itinerary_fit, "get_guardrails", lambda: _Hard())
    a, b = _day()
    only_over = fit_change(_ranked(_swap(a, "빡빡", 215)), trip=TRIP, items=[a, b])
    assert only_over.change is None and only_over.skipped[0].why == "density"
    assert fit_change(_ranked(_swap(a, "빡빡", 215), _swap(a, "여유", 180)), trip=TRIP, items=[a, b]).rank == 2


def test_the_default_mode_is_soft_and_the_tolerance_is_in_the_config():
    guardrails = get_guardrails()
    assert guardrails.get("travel.density.gate.mode") == "soft"
    assert guardrails.get("travel.density.gate.worsen_tolerance") == pytest.approx(0.02)
