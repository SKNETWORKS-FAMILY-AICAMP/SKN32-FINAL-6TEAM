# -*- coding: utf-8 -*-
"""직선 어림값으로 떨어지는 길을 줄인다 — 2026-10-22(사용자 지적 「길찾기가 다 대충 직선거리 예상 시각으로 나온다」).

· 어림이 된 이유를 갈래(`why_code`)로 남긴다 — 일시적 오류와 몇 번을 해도 같은 「답 없음」을 가른다.
· 확인 화면 한 판의 이동 한도(25초 한 통)를 앞 구간의 깊은 탐색이 다 쓰고 뒷날짜가 어림이 되지 않게, 남은 구간마다 몫이 있을 때만 깊이 찾는다.
· 수정 저장은 계산기가 답을 못 낸 구간을 거절하지 않고 어림 + 「확인 필요」로 간다. 오류만 한 번 더 부르고, 그래도 오류면 「다시 제출」이라고 안내한다.

DB 없이 도는 시험이다. 이 파일의 이동 계산기는 **테스트용 모방**이다(실제 서버가 아니다).

재현:

    python -m pytest tests/unit/intake/test_intake_leg_estimates_v1.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import direct_schedule as schedule
from app.domains.travel_ops.components.intake import hours, moves, review
from app.domains.travel_ops.components.intake.hours import HoursFacts

KST = ZoneInfo("Asia/Seoul")
A = {"key": "a", "name": "경복궁", "lat": 37.5796, "lon": 126.9770}
B = {"key": "b", "name": "광장시장", "lat": 37.5700, "lon": 126.9996}


def at(hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(2026, 10, 18, int(h), int(m), tzinfo=KST)


# ── 이유 갈래 ─────────────────────────────────────────────────────
def test_every_way_to_an_estimate_names_its_reason_code():
    assert moves.leg_between(None, A, B, at("11:30"), at("12:30")).why_code == "engine_off"
    nodata = moves.leg_between(lambda *a: (None, {"code": "no_data", "reason": "도보 상한 안에 지하철역이 없다"}), A, B, at("11:30"), at("12:30"))
    assert nodata.why_code == "no_data"
    assert moves.leg_between(lambda *a: (None, {"reason": "x"}), A, B, at("11:30"), at("12:30")).why_code == "unfilled"

    def boom(*a):
        raise TimeoutError("x")
    assert moves.leg_between(boom, A, B, at("11:30"), at("12:30")).why_code == "engine_error"
    spent = review._Budgeted(lambda *a: (None, {"code": "no_data"}), 0.0)
    assert moves.leg_between(spent, A, B, at("11:30"), at("12:30")).why_code == "budget"


def test_a_timetable_leg_has_no_reason_code():
    opt = {"id": "walk", "label": "도보", "eta_min": 10, "walk_m": 800, "uses": []}
    got = {"route": {"planned": "walk", "options": [opt]}, "starts_at": at("11:00"), "ends_at": at("11:10"), "eta_min": 10}
    assert moves.leg_between(lambda *a: (got, None), A, B, at("10:50"), at("11:30")).why_code is None


# ── 남은 한도 ─────────────────────────────────────────────────────
def test_the_remaining_limit_is_the_smaller_of_the_leg_share_and_the_whole_request():
    whole = review._Budgeted(lambda *a: (None, None), 10)
    leg = review._Budgeted(lambda *a: (None, None), 25, within=whole)
    assert leg.left == 10 and whole.left == 10
    assert review._Budgeted(lambda *a: (None, None), 7).left == 7


# ── 확인 화면: 깊은 탐색이 한 통을 다 쓰지 않는다 ─────────────────────
def four_stops():
    sources = [{"source_id": "s", "position": 0, "kind": "text", "filename": None, "transcript": "a\nb\nc\nd"}]
    claims = []
    stops = [("경복궁", "09:00", "10:00", 37.5796, 126.9770), ("광장시장", "10:30", "11:30", 37.5700, 126.9996),
             ("남대문시장", "12:00", "13:00", 37.5592, 126.9773), ("국립중앙박물관", "13:30", "14:30", 37.5240, 126.9803)]
    for i, (title, start, end, lat, lon) in enumerate(stops):
        values = {"title": title, "date": "2026-10-18", "starts_at": start, "ends_at": end, "kind": "activity",
                  "place": {"name": title, "latitude": lat, "longitude": lon, "source": "customer_pick"}}
        claims.extend({"source_id": "s", "field": f"items[{i}].{field}", "value": value, "method": "customer",
                       "evidence": {"line": i + 1}, "needs_review": False, "note": None} for field, value in values.items())
    return sources, claims


def near_miss_engine(calls):
    """처음 묻는 답(그전엔 안 됨 없음)이 앞 일정 끝보다 10분 이르다(아슬아슬) — 깊이 찾으면 끝난 뒤 떠나는 경로가 있다."""
    def run(a, b, arrive, not_before=None):
        calls.append(not_before)
        option = {"id": "bus_1", "label": "버스 103", "eta_min": 25, "walk_m": 300, "uses": ["버스:103"], "fare_krw": 1500}
        start = not_before if not_before is not None else arrive - timedelta(minutes=40)
        return {"route": {"planned": "bus_1", "options": [option]}, "starts_at": start,
                "ends_at": start + timedelta(minutes=25), "eta_min": 25, "left_out": []}, None
    return run


def build_with(monkeypatch, budget_s, calls):
    clock = [0.0]
    engine = near_miss_engine(calls)

    def timed(a, b, arrive, not_before=None):
        clock[0] += 1.0                                            # 한 번 묻는 데 1초 — 깊은 탐색도 한 번
        return engine(a, b, arrive, not_before)

    monkeypatch.setattr(review, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(review, "facts_for", lambda *args: HoursFacts(True, {"hours": ["00:00", "23:59"]}))
    monkeypatch.setattr(review, "ENGINE_BUDGET_S", budget_s)
    sources, claims = four_stops()
    return review.build(None, tenant_id="t", intake_id="x", revision=1, sources=sources, claims=claims, engine=timed,
                        use_engine=False)


def test_with_enough_limit_every_near_miss_still_gets_the_deep_search(monkeypatch):
    calls = []
    built = build_with(monkeypatch, 100.0, calls)
    assert len(built["moves"]) == 3 and calls.count(None) == 3
    assert len([c for c in calls if c is not None]) == 3           # 구간마다 깊은 탐색 한 번
    assert {m["basis"] for m in built["moves"]} == {"timetable"}


def test_when_the_limit_cannot_cover_every_remaining_leg_the_deep_search_is_skipped_so_no_leg_is_left_to_an_estimate(monkeypatch):
    calls = []
    built = build_with(monkeypatch, 3.0, calls)                    # 구간 셋 × 1초가 전부인 3초 — 남은 구간 몫이 1.5초에 못 미친다
    assert [c for c in calls if c is not None] == []               # 깊은 탐색을 하나도 안 했다
    assert len(built["moves"]) == 3
    assert {m["basis"] for m in built["moves"]} == {"timetable"}   # 셋 다 시간표로 채웠다(빠듯하다고 알릴 뿐 어림값이 아니다)


def test_without_the_share_rule_the_same_limit_runs_out_and_the_last_leg_becomes_an_estimate(monkeypatch):
    # 대조 — 앞 판처럼 몫을 안 보면(0) 첫 구간의 깊은 탐색이 한 통을 써서 뒤 구간이 어림이 된다
    monkeypatch.setattr(review, "DEEP_MIN_SHARE_S", 0.0)
    built = build_with(monkeypatch, 3.0, [])
    assert "estimate" in {m["basis"] for m in built["moves"]}


def test_estimate_reasons_are_logged_with_the_count(monkeypatch, caplog):
    clock = [0.0]
    monkeypatch.setattr(review, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(review, "facts_for", lambda *args: HoursFacts(True, {"hours": ["00:00", "23:59"]}))
    sources, claims = four_stops()
    with caplog.at_level("INFO", logger=review.__name__):
        review.build(None, tenant_id="t", intake_id="x", revision=1, sources=sources, claims=claims,
                     engine=lambda *a: (None, {"code": "no_data", "reason": "후보 없음"}), use_engine=False)
    assert any("어림 3/3" in r.getMessage() and "no_data" in r.getMessage() for r in caplog.records)


# ── 수정 저장: 답 없음은 거절하지 않는다 ────────────────────────────────
def row(index, start, end, **kw):
    return {"source_id": "source", "index": index, "date": "2026-10-15", "start": start, "end": end,
            "title": "호텔" if index == 0 else "다음 일정", "kind": "activity", "locked": False, "booked": None,
            "booking_no": None, "place": {"name": f"장소{index}", "latitude": 37.57, "longitude": 126.98 + index * .001}, **kw}


@pytest.fixture()
def no_hours(monkeypatch):
    monkeypatch.setattr(hours, "facts_for", lambda *a: hours.HoursFacts(False, why_unknown="시험에는 운영시간 없음"))


def fit(rows, engine, touched={("source", 0)}):
    return schedule.fit(None, tenant_id="test", rows=rows, touched=touched, engine=engine, use_engine=False)


def test_a_calculator_with_no_answer_is_saved_as_an_estimate_instead_of_refusing(no_hours):
    far = {"name": "먼 곳", "latitude": 37.60, "longitude": 127.05}
    got = fit([row(0, "09:00", "10:00"), row(1, "10:00", "11:00", place=far)],
              lambda *a: (None, {"code": "no_data", "reason": "도보 상한 안에 지하철역이 없다"}))
    assert got and all(c["basis"] == "estimate" for c in got)      # 거절하지 않고 어림 근거로 맞춘다 — 같은 판의 검사가 「확인 필요」로 센다


def test_an_engine_error_is_asked_once_more_and_a_second_try_can_succeed(no_hours):
    attempts = []

    def flaky(a, b, arrive, not_before=None):
        attempts.append(1)
        if len(attempts) == 1:
            raise TimeoutError("일시적")
        depart = arrive - timedelta(minutes=11)
        return {"starts_at": depart, "ends_at": arrive, "eta_min": 11,
                "route": {"planned": "walk", "options": [{"id": "walk", "eta_min": 11, "walk_m": 880, "label": "도보 11분"}]}}, None

    assert fit([row(0, "09:00", "10:00"), row(1, "11:00", "12:00")], flaky) == []
    assert len(attempts) == 2


def test_an_engine_error_that_repeats_is_refused_with_a_resubmit_message_not_a_wait_message(no_hours):
    def failed(*args):
        raise TimeoutError("일시적")
    with pytest.raises(schedule.ScheduleConflict) as raised:
        fit([row(0, "09:00", "10:00"), row(1, "10:05", "11:05")], failed)
    assert raised.value.code == "schedule_check_failed"
    assert "다시 제출" in str(raised.value) and "잠시 뒤" not in str(raised.value)
