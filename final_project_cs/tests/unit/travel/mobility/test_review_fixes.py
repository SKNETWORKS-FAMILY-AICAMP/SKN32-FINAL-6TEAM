# -*- coding: utf-8 -*-
"""이동 계산기 점검(2026-09-29) 수정 회귀 — 문제 번호별로 한 시험 이상.

문제 목록: wiki/records/reports/2026-09-29_0210_이동계산기_점검_문제목록.md
시간표 데이터(DATA_DIR) 없이 도는 시험만 둔다 — 데이터 축은 기존 시험 파일이 맡는다.
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from app.modules.travel_ops.mobility.engine.paths import RULES_DIR
from app.modules.travel_ops.mobility.engine.timeutil import (
    CalendarOutOfRange, HolidayCalendar, day_type_of, to_min, to_min_ceil, to_service_min)

RULES = json.loads((RULES_DIR / "rules_v0.3.json").read_text(encoding="utf-8"))


def _verifier(**kw):
    """데이터 없이 만드는 작은 판정기 — 빈 시간표 · 노선 순서 없음."""
    from app.modules.travel_ops.mobility.engine.verify_time import Timetable, Verifier
    return Verifier(Timetable(), None, RULES, kw.pop("holidays", set()), **kw)


# ── #12 요청 시각의 초 — 출발은 올린다 ─────────────────────────────
def test_12_depart_seconds_round_up():
    assert to_min("10:00:59") == 600, "시간표 쪽은 종전대로 내림"
    assert to_min_ceil("10:00:59") == 601, "10:00:59 에 떠나는 사람은 10:00 열차를 못 탄다"
    assert to_min_ceil("10:00:00") == 600 and to_min_ceil("10:00") == 600, "초가 0 이면 그대로"
    assert to_service_min("00:30:10", ceil_seconds=True) == 24 * 60 + 31, "운행일 축으로 올린 뒤에도 초 올림"
    assert to_service_min("00:30:10") == 24 * 60 + 30, "기본값(도착 기한)은 내림"


# ── #17 시각이 아닌 값 ────────────────────────────────────────────
@pytest.mark.parametrize("bad", [-1, -0.5, "10:00:99", "10:61", "106199", "31:00"])
def test_17_invalid_times_are_none(bad):
    assert to_min(bad) is None
    assert to_min_ceil(bad) is None


# ── #5 공휴일 표 밖의 날짜 ────────────────────────────────────────
def test_5_calendar_refuses_uncovered_year():
    cal = HolidayCalendar.from_doc({"years": [2026, 2027], "holidays": {"2026-10-03": "개천절"}})
    assert day_type_of(date(2026, 10, 3), cal) == "holiday"
    assert day_type_of(date(2026, 10, 5), cal) == "weekday"
    with pytest.raises(CalendarOutOfRange):
        day_type_of(date(2028, 3, 1), cal)          # 앞 판은 삼일절을 평일로 판정했다
    with pytest.raises(CalendarOutOfRange):
        day_type_of(date(2028, 3, 4), cal)          # 주말도 같이 거절 — 옆 날짜만 되는 모양을 안 만든다


def test_5_plain_set_keeps_old_behaviour():
    assert day_type_of(date(2028, 3, 1), {"2026-10-03"}) == "weekday", "덮는 해를 모르는 옛 집합은 종전대로"


def test_5_real_holiday_file_declares_years():
    cal = HolidayCalendar.from_doc(json.loads((RULES_DIR / "holidays_2026_2027.json").read_text(encoding="utf-8")))
    assert cal.years == {2026, 2027}
    assert "2026-10-03" in cal


# ── #66 · #30 판정기가 SystemExit 로 프로세스를 끝내지 않는다 ──────────
def test_66_unknown_disruption_kind_is_input_error_not_exit():
    from app.modules.travel_ops.mobility.engine.errors import CaseInputError
    with pytest.raises(CaseInputError):
        _verifier().verify_case({"id": "t", "date": "2026-10-05", "depart_at": "10:00",
                                 "disruptions": [{"kind": "bogus"}], "legs": []})
    assert not issubclass(CaseInputError, SystemExit), "일반 오류 처리(except Exception)로 잡혀야 한다"


def test_30_missing_depart_is_input_error():
    from app.modules.travel_ops.mobility.engine.errors import CaseInputError
    with pytest.raises(CaseInputError):
        _verifier().verify_case({"id": "t", "date": "2026-10-05", "arrive_by": "11:00", "legs": []})


def test_30_adapter_refuses_arrive_only_input():
    from app.modules.travel_ops.mobility.engine.adapter import map_task_to_case
    task = {"task_id": "t1", "case_id": "c1",
            "context": {"current_state": {"mobility": {
                "date": "2026-10-05", "arrive_by": "11:00",
                "legs": [{"line": "02호선", "from": "강남", "to": "잠실"}]}}}}
    case, note = map_task_to_case(task)
    assert case is None and note.startswith("mobility_input_incomplete:depart_at")


# ── #10 · #28 · #50 자전거 조회 ──────────────────────────────────────
class _Router:
    def __init__(self, doc=None, exc=None):
        self.doc, self.exc = doc, exc

    def route(self, *a, **k):
        if self.exc:
            raise self.exc
        return self.doc


def test_10_missing_distance_or_time_is_not_zero():
    from app.modules.travel_ops.mobility.engine.bike import BikeRouter
    br = BikeRouter(_Router({"paths": [{}]}))
    assert br.route("bike", 37.5, 127.0, 37.51, 127.01) is None, "빈 경로를 0 m·0 초로 만들지 않는다"
    assert br.last_error["kind"] == "bad_response"
    ok = BikeRouter(_Router({"paths": [{"distance": 1234.5, "time": 300000}]}))
    assert ok.route("bike", 37.5, 127.0, 37.51, 127.01)["time_s"] == 300


def test_28_router_failures_are_classified_and_bugs_not_swallowed():
    from app.modules.travel_ops.mobility.engine.bike import BikeRouter
    from app.modules.travel_ops.mobility.engine.car import RouterDown
    down = BikeRouter(_Router(exc=RouterDown("down")))
    assert down.route("bike", 37.5, 127.0, 37.51, 127.01) is None and down.last_error["kind"] == "router_down"
    net = BikeRouter(_Router(exc=OSError("reset")))
    assert net.route("bike", 37.5, 127.0, 37.51, 127.01) is None and net.last_error["kind"] == "router_error"
    with pytest.raises(TypeError):                   # 코드 결함은 삼키지 않는다
        BikeRouter(_Router(exc=TypeError("bug"))).route("bike", 37.5, 127.0, 37.51, 127.01)
    assert BikeRouter(None).route("bike", 1, 1, 1, 1) is None


def test_28_bike_live_no_key_reason():
    from app.modules.travel_ops.mobility.engine.bike import BikeLive
    live = BikeLive(key=None)
    assert live.get("ST-1") is None and live.last_error == {"kind": "no_key"}


def test_50_bike_live_error_never_carries_key(monkeypatch):
    import urllib.request

    from app.modules.travel_ops.mobility.engine.bike import BikeLive

    def boom(url, timeout):
        raise OSError(f"failed {url}")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    live = BikeLive(key="SECRETKEY123")
    assert live.get("ST-1") is None
    assert "SECRETKEY123" not in json.dumps(live.last_error), "키가 든 주소를 오류에 싣지 않는다"


# ── #9 자전거 대수는 일행 인원만큼 · 설문 값 옮기기 ────────────────────
def test_9_bike_needs_one_per_person():
    from app.modules.travel_ops.mobility.engine.bike import BikeStations
    st = {"stationId": "ST-1", "name": "대여소1", "lat": 37.5000, "lon": 127.0000, "mode": "QR", "rack": 10}
    st2 = {"stationId": "ST-2", "name": "대여소2", "lat": 37.5100, "lon": 127.0100, "mode": "QR", "rack": 10}
    v = _verifier(bk=BikeStations([st, st2]))
    leg = {"mode": "bike", "from": {"lat": 37.5001, "lng": 127.0001, "name": "출발"},
           "to": {"lat": 37.5101, "lng": 127.0101, "name": "도착"}}
    live = {"checked_at": "2026-09-29T10:00", "counts": {"ST-1": 2, "ST-2": 9}}
    one = v.verify_leg_bike(1, leg, 600, "weekday", party={"size": 1}, live_fixture=live)
    four = v.verify_leg_bike(1, leg, 600, "weekday", party={"size": 4}, live_fixture=live)
    assert one.verdict == "feasible"
    assert four.verdict == "infeasible" and "4명" in four.reason, "4인 일행에 2대면 빌릴 수 없다"


def test_9_party_of_reads_survey_domestic():
    from app.modules.travel_ops.mobility.engine.plan import party_of
    assert party_of(4, {"survey": {"domestic": True}}) == {"size": 4, "foreign": False}
    assert party_of(2, {"survey": {"domestic": False}})["foreign"] is True
    assert "foreign" not in party_of(2, {"survey": {"party": "아이 둘"}}), "자유 문장에서 짐작하지 않는다"


# ── #16 버스 소요 48시간 경계 ─────────────────────────────────────────
def test_16_bus_profile_checks_end_of_last_segment():
    from app.modules.travel_ops.mobility.engine.bus_profile import BusSegProfile
    prof = BusSegProfile.__new__(BusSegProfile)
    prof.row = lambda route_id, s, nxt: (None, False)
    stops = [{"seq": 1}, {"seq": 2, "sect_dist_m": 500}]
    late = BusSegProfile.walk(prof, "R", stops, 1, 2, 2 * 1440 - 1, lambda t: ("weekday",), "q50", 1,
                              fallback=lambda m: 2.0)
    assert late.out_of_range, "47:59 에 들어가 48:01 에 끝나면 범위 밖"
    ok = BusSegProfile.walk(prof, "R", stops, 1, 2, 600, lambda t: ("weekday",), "q50", 1, fallback=lambda m: 2.0)
    assert not ok.out_of_range and ok.minutes == 2.0


# ── #51 판정 기록 가리기 ──────────────────────────────────────────────
@pytest.mark.parametrize("raw,hidden", [("문의 a@b.com", "a@b.com"), ("010-1234-5678", "1234"),
                                        ("lat=37.5, lon=127.0", "37.5"), ("37.5,127.0", "127.0")])
def test_51_scrub_hides_pii_and_single_coords(raw, hidden):
    from app.modules.travel_ops.mobility.devtools.judgment_log import scan_blocked, scrub_text
    assert hidden not in scrub_text(raw)
    assert scan_blocked(raw), "검사도 잡는다"


@pytest.mark.parametrize("plain", ["2호선 강남 10:00 출발", "버스 7022 23:10", "요금 1,400원", "tago_subway@2026-09-09",
                                   # 실행 번호 — 새벽 2시대 + 무작위 뒷자리가 숫자 넷이면 서울 번호 모양이 됐다(시험이 흔들린 원인)
                                   "20260929T024107-1234ab", "20260929T031500-5678cd"])
def test_51_scrub_leaves_ordinary_text(plain):
    from app.modules.travel_ops.mobility.devtools.judgment_log import scan_blocked, scrub_text
    assert scrub_text(plain) == plain and not scan_blocked(plain)


# ── #18 결과 접기 ────────────────────────────────────────────────────
_BASIS = {"timetable_built_at": "built:t", "rules_version": "v", "service_date": "2026-10-05", "decided_at": "t"}


def test_18_answer_has_no_english_verdict_words():
    from app.modules.travel_ops.mobility.engine.fold import fold_case
    out = fold_case({"id": "c", "verdict": "feasible", "grade": "확정", "reason": "성립",
                     "legs": [{"label": "02호선 강남→잠실", "verdict": "feasible", "grade": "확정", "arrive_min": 620}]},
                    task_id="t", basis=_BASIS)
    assert out["outcome"] == "completed"
    assert " ok" not in out["answer"] and "가능" in out["answer"]


def test_18_unknown_verdict_is_not_packaged_as_completed():
    from app.modules.travel_ops.mobility.engine.fold import fold_case
    out = fold_case({"id": "c", "verdict": "unknown", "grade": "근거없음", "reason": "시간표 없음",
                     "legs": [{"label": "02호선 강남→잠실", "verdict": "unknown", "grade": "근거없음"}]},
                    task_id="t", basis=_BASIS)
    assert out["outcome"] == "escalated" and out["failure_code"] == "mobility_no_data"
    assert out["evidence"], "근거는 그대로 싣는다"
