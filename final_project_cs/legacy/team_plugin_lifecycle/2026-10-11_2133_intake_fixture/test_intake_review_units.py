# -*- coding: utf-8 -*-
"""확인 화면 검사의 부품 — 이동(수단 · 늦음 · 어림) · 운영시간 사실 모으기 · 소요 시간 읽기 · 체인 지점 · 고른 장소 검사 · 자동 추천의 시각 맞추기.
`[2026-10-02 사용자 지시 — 계획 확인 시나리오 목업]`

DB 없이 도는 시험이다. 이 파일의 이동 계산기·원장은 **테스트용 모방**이다(실제 서버가 아니다).

재현:

    python -m pytest tests/unit/travel/test_intake_review_units.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import autofix, candidates, hours, moves, pipeline, places, review
from app.domains.travel_ops.components.intake.rules import read_plan

KST = ZoneInfo("Asia/Seoul")


def at(hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(2026, 10, 15, int(h), int(m), tzinfo=KST)


A = {"key": "a", "name": "경복궁", "lat": 37.5796, "lon": 126.9770}
B = {"key": "b", "name": "올리브영 광화문점", "lat": 37.5717, "lon": 126.9791}
C = {"key": "c", "name": "광장시장", "lat": 37.5700, "lon": 126.9996}


# ── 이동 ─────────────────────────────────────────────────────────
def option(label, uses, eta, walk_m=500, oid="subway_1"):
    return {"id": oid, "label": label, "eta_min": eta, "walk_m": walk_m, "fare_krw": 1550, "uses": uses}


def got(opt, start, end, eta=None):
    return {"route": {"planned": opt["id"], "options": [opt]}, "starts_at": at(start), "ends_at": at(end),
            "eta_min": eta or opt["eta_min"]}


def test_the_mode_is_read_from_the_lines_the_route_uses():
    assert moves.mode_of(option("도보", [], 12, oid="walk")) == ("walk", "도보")
    assert moves.mode_of(option("x", ["5호선:광화문", "5호선:종로3가", "1호선:종로3가", "1호선:종로5가"], 19)) == ("subway", "지하철 5호선→1호선")
    assert moves.mode_of(option("x", ["버스:103", "버스:103"], 30)) == ("bus", "버스 103")
    assert moves.mode_of(option("x", ["버스:103", "2호선:시청"], 30)) == ("transit", "대중교통")


def test_a_timetable_leg_uses_the_calculators_departure_and_arrival():
    opt = option("5호선 광화문→종로3가 → 1호선 종로3가→종로5가", ["5호선:광화문", "1호선:종로5가"], 19)
    leg = moves.leg_between(lambda a, b, arrive, not_before: (got(opt, "12:01", "12:20"), None), B, C, at("12:00"), at("12:30"))
    assert (leg.basis, leg.mode, leg.minutes) == ("timetable", "subway", 19)
    assert (leg.depart, leg.arrive, leg.slack_min) == (at("12:01"), at("12:20"), 10) and leg.why is None


def test_a_leg_that_cannot_be_made_is_measured_without_the_slow_deep_search_and_reports_how_late():
    calls = []
    opt = option("도보", [], 21, oid="walk", walk_m=1258)

    def engine(a, b, arrive, not_before):
        calls.append(not_before)
        return got(opt, "10:29", "10:50"), None                          # 가장 늦은 출발이 10:29 — 11:30 에 끝나는 일정 뒤로는 못 떠난다

    leg = moves.leg_between(engine, A, B, at("11:30"), at("11:00"))
    assert calls == [None]                                               # ★61분이나 모자라면 깊은 탐색(출발 제한을 건 질문)을 하지 않는다 — 실측 3~11초
    assert (leg.depart, leg.arrive, leg.slack_min, leg.mode, leg.km) == (at("11:30"), at("11:51"), -51, "walk", 1.3)
    assert moves.late_text(leg.slack_min) == "일정보다 51분 늦어요"


def test_a_near_miss_gets_the_deep_search_for_a_route_that_leaves_after_the_previous_item():
    calls = []
    slow = option("버스 103", ["버스:103"], 30, oid="bus_1")
    later = option("지하철", ["1호선:서울역"], 25)

    def engine(a, b, arrive, not_before):
        calls.append(not_before)
        if not_before is None:
            return got(slow, "11:20", "11:50"), None                    # 가장 늦은 출발 11:20 — 11:30 보다 10분 이르다(아슬아슬)
        return got(later, "11:32", "11:57"), None                       # 끝난 뒤 떠나서 닿는 다른 경로가 있다

    leg = moves.leg_between(engine, A, B, at("11:30"), at("11:58"))     # 바로 떠나면(30분) 12:00 — 2분 늦는다
    assert calls == [None, at("11:30")] and (leg.mode, leg.depart, leg.arrive, leg.slack_min) == ("subway", at("11:32"), at("11:57"), 1)
    # 깊은 탐색도 못 찾으면 바로 떠나는 값으로 늦다고 알린다
    leg = moves.leg_between(lambda a, b, ar, nb: (got(slow, "11:20", "11:50"), None) if nb is None else (None, {"code": "arrive_late"}),
                            A, B, at("11:30"), at("11:58"))
    assert (leg.mode, leg.depart, leg.arrive, leg.slack_min) == ("bus", at("11:30"), at("12:00"), -2)
    # 열차 · 버스는 「끝나는 대로 떠나면 닿는다」는 계산만으로 믿지 않는다 — 아슬아슬하면 시간표로 다시 확인한다(여유가 있어도)
    calls.clear()
    ok = moves.leg_between(engine, A, B, at("11:30"), at("12:05"))
    assert calls == [None, at("11:30")] and ok.verified and ok.ok and ok.depart == at("11:32")
    # 시간표로 확인하지 못했는데 이동 시간만 더하면 닿는 경우 — 늦지는 않지만 「빠듯하다」(tight): 열차 · 버스를 기다리는 시간이 빠져 있다
    unsure = moves.leg_between(lambda a, b, ar, nb: (got(slow, "11:20", "11:50"), None) if nb is None else (None, {"code": "arrive_late"}),
                               A, B, at("11:30"), at("12:30"))
    assert (unsure.verified, unsure.tight, unsure.ok, unsure.slack_min) == (False, True, False, 30)
    assert unsure.latest_depart == at("11:20")
    # 도보는 이어지는 이동이라 끝나는 대로 떠나면 되고 빠듯하다고 하지 않는다
    stroll = option("도보", [], 12, oid="walk", walk_m=800)
    walk = moves.leg_between(lambda a, b, ar, nb: (got(stroll, "11:10", "11:22"), None), A, B, at("11:30"), at("12:00"))
    assert (walk.mode, walk.tight, walk.ok, walk.slack_min) == ("walk", False, True, 18)
    # deep=False 면 아슬아슬해도 깊이 찾지 않는다(시각을 맞추려고 여러 번 묻는 쪽)
    calls.clear()
    moves.leg_between(engine, A, B, at("11:30"), at("11:58"), deep=False)
    assert calls == [None]


def test_without_a_calculator_or_when_it_cannot_fill_the_leg_the_leg_is_an_estimate_with_the_reason():
    off = moves.leg_between(None, A, B, at("11:30"), at("11:00"))
    assert (off.basis, off.mode, off.mode_label, off.why) == ("estimate", "estimate", "직선 어림", "이동 계산기가 꺼져 있어요")
    assert (off.minutes, off.slack_min) == (12, -42)                    # 목업의 「11:30에 나서면 11:42 도착 · 42분 늦어요」
    nodata = moves.leg_between(lambda *a: (None, {"code": "no_data", "reason": "도보 상한 안에 지하철역이 없다"}), A, B, at("11:30"), at("12:30"))
    assert nodata.basis == "estimate" and nodata.why == "도보 상한 안에 지하철역이 없다" and nodata.slack_min >= 0

    def boom(*a):
        raise KeyError("자료")

    broke = moves.leg_between(boom, A, B, at("11:30"), at("12:30"))
    assert broke.basis == "estimate" and "KeyError" in broke.why        # 계산기 오류가 확인 화면을 막지 않는다


def test_the_engine_budget_turns_the_rest_into_estimates_and_the_same_question_is_answered_from_memory():
    import time

    calls = []

    def slow(*a):
        calls.append(a)
        time.sleep(0.02)
        return None, {"code": "no_data", "reason": "x"}

    spent = review._Budgeted(slow, 0.01)
    first = spent(A, B, at("11:00"), None)
    assert spent(A, B, at("11:00"), None) == first and len(calls) == 1              # 같은 질문은 기억한 답 — 계산기 시간을 또 쓰지 않는다
    assert spent(A, B, at("12:00"), None) == (None, {"code": "budget", "reason": "이동 계산에 시간이 오래 걸려 어림값으로 냈어요"})


# ── 자동 추천의 시각 맞추기 ─────────────────────────────────────────
def shown(p):
    """검사가 들고 있는 장소 모양(latitude · longitude)."""
    return {"name": p["name"], "latitude": p["lat"], "longitude": p["lon"]}


def test_the_earliest_start_waits_for_the_travel_and_rounds_up_to_five_minutes():
    # 어림 12분 → 11:30 + 12 = 11:42 → 11:45
    assert autofix.earliest_start(None, shown(A), shown(B), at("11:30")) == at("11:45")


def test_the_latest_end_leaves_in_time_for_the_next_item_and_rounds_down():
    # 광화문점 → 광장시장 어림 23분, 다음 일정 13:30 → 13:07 → 13:05
    assert autofix.latest_end(None, shown(B), shown(C), at("13:30")) == at("13:05")


def test_a_calculator_that_says_late_pushes_the_start_until_it_arrives():
    seen = []

    def engine(a, b, arrive, not_before):
        seen.append((arrive, not_before))
        # 이 계산기는 40분이 걸린다 — 도착 목표가 늦을수록 가장 늦은 출발도 늦어진다. 출발 제한이 있으면 그 뒤에 떠나는 경로만 준다
        starts = arrive - timedelta(minutes=40 + 10)
        if not_before is not None and starts < not_before:
            return None, {"code": "arrive_late", "reason": "늦다"}
        return got(option("x", ["1호선:서울역"], 40), starts.strftime("%H:%M"), (arrive - timedelta(minutes=10)).strftime("%H:%M")), None

    start = autofix.earliest_start(engine, shown(A), shown(B), at("11:30"))
    assert start == at("12:20")                                          # 앞 일정 끝 11:30 + 걸리는 40분 + 정책 여유 10분 — 시간표로 확인되는 가장 이른 시작
    assert sum(1 for _, nb in seen if nb is not None) <= 1               # 깊은 탐색(출발 제한을 건 질문)은 아슬아슬할 때 한 번뿐


def test_the_time_fitting_gives_up_instead_of_returning_a_time_that_still_does_not_work():
    def stubborn(a, b, arrive, not_before):
        # 도착 목표를 아무리 늦춰도 계산기는 늘 이른 아침 열차만 준다 — 앞 일정이 끝난 뒤 편이 확인되지 않는다
        return got(option("x", ["1호선:서울역"], 20), "06:00", "06:20"), None

    assert autofix.earliest_start(stubborn, shown(A), shown(B), at("11:30")) is None

    def too_late(a, b, arrive, not_before):
        # 계산기는 늘 밤 열차만 준다 — 다음 일정(13:30)에 어느 끝 시각으로도 닿지 못한다
        return got(option("x", ["1호선:서울역"], 20), "23:00", "23:20"), None

    assert autofix.latest_end(too_late, shown(B), shown(C), at("13:30")) is None


def test_auto_fix_tries_beyond_the_three_shown_candidates_until_one_fits(monkeypatch):
    seen = {}
    names = ["첫째", "둘째", "셋째", "넷째", "다섯째"]

    def fake_alternatives(conn, **kwargs):
        seen["limit"] = kwargs["limit"]
        seen["rank_only"] = kwargs["rank_only"]
        return {"candidates": [{"place": {"name": n, "latitude": 37.57, "longitude": 126.98, "source": "kakao"}, "status": "ok"} for n in names]}

    tried = []

    def fake_fit(conn, tenant_id, item, place, prev, nxt, start, duration, engine, *, require_known=False):
        tried.append(place["name"])
        return (start, start + duration, False) if place["name"] == "넷째" else "travel"       # 앞 셋은 시간표로 안 맞고 넷째가 맞는다

    monkeypatch.setattr(autofix.cand_module, "alternatives", fake_alternatives)
    monkeypatch.setattr(autofix, "_fit_window", fake_fit)
    monkeypatch.setattr(autofix, "default_engine", lambda party=None: None)
    row = {"row": "place", "result": "bad", "text": "x"}
    item = {"id": "0-0", "source_id": "s", "index": 0, "title": "어딘가", "kind": "activity", "date": "2026-10-15", "starts_at": "11:00",
            "ends_at": "12:00", "locked": False, "status": "review", "place": None, "place_state": "unresolved", "rows": [row]}
    got = autofix.plan(None, tenant_id="t", review={"items": [item], "moves": []})
    assert seen["limit"] == autofix.CANDIDATES_TRIED > 3 and seen["rank_only"] is True
    assert tried == ["첫째", "둘째", "셋째", "넷째"] and [c["to"]["place"]["name"] for c in got["changes"]] == ["넷째"]
    assert got["changes"][0]["hours_known"] is False and got["kept"] == []


# ── 운영시간 사실 ─────────────────────────────────────────────────
class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        pass

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _Conn:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def cursor(self):
        return _Cursor(self.rows)

    def transaction(self):
        return _Cursor([])                  # 세이브포인트 자리 — 들어가고 나오기만 한다


def test_nothing_stored_means_unknown_with_a_reason_never_open():
    got_ = hours.facts_for(_Conn(), "t", {"name": "어디", "source": "kakao", "latitude": 37.5, "longitude": 127.0}, "activity",
                           at("11:00"), at("12:00"))
    assert got_.known is False and got_.why_unknown == "카카오 지도 정보에는 운영시간이 없어요"
    tour = hours.facts_for(_Conn(), "t", {"name": "경복궁", "source": "tour_api", "content_id": "1"}, "activity", at("11:00"), at("12:00"))
    assert tour.known is False and "읽지 못했어요" in tour.why_unknown
    assert hours.facts_for(_Conn(), "t", None, "activity", at("11:00"), None).why_unknown == "장소를 정하면 확인해요"
    assert hours.facts_for(_Conn(), "t", {"name": "x"}, "activity", None, None).why_unknown == "방문 시각을 알면 확인해요"


def test_the_dining_ledger_supplies_the_days_hours_break_and_closed_day(monkeypatch):
    from app.domains.travel_ops.instances.dining import ledger

    state = {"linked": True, "available": True, "open_at_slot": True, "order_ok": False, "needs_check": True,
             "attributes": {"hours": ["11:30", "22:30"], "break": ["14:00", "17:30"]}, "holiday_context": "추석 연휴"}
    monkeypatch.setattr(ledger, "dining_state", lambda *a, **k: state)
    # ★`[2026-10-05]` 장소 행(코어 장소)이 있으면 그 행으로 `dining_state` 를 묻는다 — 전에는 원장 가게를 공용 장소로 올려 두고 이름으로 이었다(`ledger_place_for`, 걷어냄)
    place = {"name": "온더무브", "place_id": "core-1", "latitude": 37.56, "longitude": 126.99, "source": "kakao"}
    facts = hours.facts_for(_Conn(), "t", place, "dining", at("12:00"), at("13:00"))
    assert facts.known and facts.source == "dining_ledger" and facts.attributes["hours"] == ["11:30", "22:30"]
    assert facts.attributes["break"] == ["14:00", "17:30"] and facts.order_ok is False and facts.needs_check
    assert facts.conditions == ["추석 연휴"]
    state["attributes"] = {"closed": True}
    closed = hours.facts_for(_Conn(), "t", place, "dining", at("12:00"), at("13:00"))
    assert closed.known and closed.attributes["hours_week"]["thu"] == "closed"      # 2026-10-15 는 목요일
    state["linked"] = False
    assert hours.facts_for(_Conn(), "t", place, "dining", at("12:00"), at("13:00")).known is False   # 원장에 못 이은 식당은 모른다
    # 장소 행이 아직 없고(확인 화면 단계) 이름으로도 원장에서 하나로 정해지지 않으면 모른다 — 고르지 않는다
    monkeypatch.setattr(ledger, "find_place_by_name", lambda *a, **k: None)
    unplaced = {"name": "온더무브", "latitude": 37.56, "longitude": 126.99, "source": "kakao"}
    assert hours.facts_for(_Conn(), "t", unplaced, "dining", at("12:00"), at("13:00")).known is False
    # 활동은 원장을 묻지 않는다
    monkeypatch.setattr(ledger, "dining_state", lambda *a, **k: pytest.fail("활동인데 원장을 물었다"))
    hours.facts_for(_Conn(), "t", place, "activity", at("12:00"), at("13:00"))


def test_closed_weekday_helpers():
    week = {d: {"open": "09:00", "close": "18:00"} for d in ("mon", "wed", "thu", "fri", "sat", "sun")} | {"tue": "closed"}
    assert hours.closed_weekdays({"hours_week": week}) == ["화"] and hours.week_known_all({"hours_week": week})
    assert not hours.week_known_all({"hours_week": {"mon": "closed"}}) and hours.closed_weekdays({}) == []


# ── 소요 시간 · 체인 지점 ─────────────────────────────────────────
@pytest.mark.parametrize("line,end,title", [
    ("10시 경복궁 관람 1시간 반", "11:30", "경복궁 관람"), ("10시 카페 40분", "10:40", "카페"),
    ("12시 점심 1시간 30분 토속촌", "13:30", "점심"), ("9시 북촌 2시간", "11:00", "북촌"),
])
def test_a_duration_in_the_line_becomes_the_end_time(line, end, title):
    read = read_plan(line)
    fields = {c.field: c for c in read.claims}
    assert fields["items[0].ends_at"].value == end and fields["items[0].title"].value == title
    assert fields["items[0].ends_at"].span.text in line                 # 근거는 원문 조각이다
    assert len(read.items) == 1                                          # ★「1시간」이 시각 「1시」로 읽혀 가짜 항목이 생기던 결함


def test_a_duration_never_overrides_an_explicit_end_and_a_clock_hour_is_still_a_time():
    explicit = read_plan("10:00~11:00 경복궁 2시간")
    assert {c.field: c.value for c in explicit.claims}["items[0].ends_at"] == "11:00"
    two = read_plan("10시 경복궁\n1시 반 광장시장")
    assert [c.value for c in two.claims if c.field.endswith("starts_at")] == ["10:00", "01:30"]
    assert read_plan("23시 야식 2시간").items[0].end is None            # 자정을 넘는 끝은 만들지 않는다


@pytest.mark.parametrize("line", ["10시 카페 10분 거리", "10시 경복궁 30분 걸려서 도착", "10시 경복궁 1시간 전에 도착", "10시 경복궁 도착 20분 후에 출발",
                                  "9시 정각 경복궁", "10시 북촌 30분 이내"])
def test_phrases_that_are_not_a_stay_do_not_become_an_end_time(line):
    read = read_plan(line)
    assert read.items and read.items[0].end is None and not [c for c in read.claims if c.field.endswith("ends_at")]


def test_item_field_names_are_made_canonical_so_a_lock_cannot_be_dodged_by_spelling():
    assert pipeline._canonical("items[ 01 ].place") == "items[1].place" and pipeline._canonical("items[1].locked") == "items[1].locked"
    assert pipeline._canonical("items[x].place") == "items[x].place" and pipeline._canonical("trip.title") == "trip.title"


def hit(name, lat=37.5, lon=127.0, group=""):
    return {"id": name, "name": name, "category": "", "category_group": group, "address": "서울", "latitude": lat, "longitude": lon}


def test_one_branch_among_siblings_is_not_picked_blindly_but_a_typed_branch_name_is():
    siblings = [hit("올리브영 종각역점"), hit("올리브영 명동 플래그십"), hit("올리브영 강남타운")]
    assert places._kakao_match("올리브영", siblings) is None             # ★관련도 첫 결과를 고르지 않는다
    assert places._kakao_match("올리브영", [hit("올리브영 종각역점"), hit("올리브영 광화문점")]) is None   # 모두 「…점」인 체인
    assert places._kakao_match("올리브영 광화문점", [hit("올리브영 종각역점"), hit("올리브영 광화문점")])["name"] == "올리브영 광화문점"
    assert places._kakao_match("올리브영 광화문점", [hit("올리브영 광화문점"), hit("올리브영 광화문점")]) is None   # 같은 이름이 둘이면 모른다
    assert places._kakao_match("경복궁", [hit("경복궁"), hit("경복궁 앞 식당")])["name"] == "경복궁"             # 이름이 같으면 그것
    assert places._kakao_match("토속촌", [hit("토속촌삼계탕")])["name"] == "토속촌삼계탕"                      # 하나뿐이면 그것(확인은 부르는 쪽)
    assert places._kakao_match("순희네", [hit("다른 곳")]) is None


# ── 편집 값 검사 ──────────────────────────────────────────────────
def checked(field, value):
    return pipeline._checked(field, value)[0]


def test_the_edit_values_for_lock_removal_and_picked_places_are_checked():
    assert checked("items[0].locked", True) is True and checked("items[0].locked", False) is False
    assert checked("items[0].removed", False) is False and checked("items[0].removed", True) is True
    for field, bad in (("items[0].locked", "yes"), ("items[0].locked", 1), ("items[0].removed", None)):
        with pytest.raises(pipeline.IntakeRejected):
            pipeline._checked(field, bad)
    pick = {"name": "올리브영 명동 플래그십", "latitude": 37.5637, "longitude": 126.9851, "source": "kakao", "kind": "dining",
            "content_id": "123", "place_id": "남의-장소"}
    got_ = checked("items[2].place", pick)
    assert got_["source"] == "customer_pick" and got_["origin"] == "kakao" and got_["place_id"] is None   # place_id 는 받지 않는다
    assert got_["kind"] == "dining" and got_["content_id"] == "123" and got_["latitude"] == 37.5637
    assert checked("items[2].place", {**pick, "kind": "x"})["kind"] is None
    assert checked("items[2].place", {**pick, "source": "customer_pick", "origin": "map"})["origin"] == "map"
    assert checked("items[2].place", {**pick, "source": "customer_pick", "origin": "ssh"})["origin"] == "search"
    for bad, code in (({**pick, "latitude": 37.0}, "place_out_of_seoul"), ({**pick, "longitude": 128.0}, "place_out_of_seoul"),
                      ({**pick, "latitude": True}, "invalid_value"), ({**pick, "latitude": float("nan")}, "invalid_value"),
                      ({**pick, "name": "x" * 81}, "invalid_value"), ({**pick, "content_id": "1; DROP"}, "invalid_value"),
                      ({"latitude": 37.5, "name": "a"}, "invalid_value"), ({**pick, "source": "google"}, "invalid_value")):
        with pytest.raises(pipeline.IntakeRejected) as caught:
            pipeline._checked("items[2].place", bad)
        assert caught.value.code == code, bad
    assert pipeline._checked("items[1].place", {"none": True})[0] is None          # 기존 모양은 그대로


def test_a_branch_with_the_same_name_far_away_is_not_taken_but_the_same_site_is():
    here = [("올리브영광화문점", 37.5717, 126.9791)]
    same = {"name": "올리브영 광화문점", "latitude": 37.5718, "longitude": 126.9792}
    far = {"name": "올리브영 광화문점", "latitude": 37.5010, "longitude": 127.0265}          # 이름만 같고 8km 밖의 다른 지점
    other = {"name": "올리브영 종각점", "latitude": 37.5702, "longitude": 126.9838}
    assert candidates._is_taken(same, here) and not candidates._is_taken(far, here) and not candidates._is_taken(other, here)
    assert [p["name"] for p in candidates._dedupe([same, far, other, dict(other)], here)] == ["올리브영 광화문점", "올리브영 종각점"]
    assert candidates._is_taken({"name": "올리브영 광화문점", "latitude": None, "longitude": None}, [("올리브영광화문점", None, None)])


def test_the_public_copy_hides_the_internal_keys_but_the_stored_review_keeps_them():
    stored = {"revision": 2, "items": [{"id": "0-0", "place": {"name": "경복궁", "place_id": "p-1", "content_id": "126508"}},
                                       {"id": "0-1", "place": None}],
              "moves": [{"from": "0-0", "to": "0-1", "sig": "내부 키", "status": "keep"}], "needs": {"total": 0}}
    out = review.public(stored)
    assert out["items"][0]["place"] == {"name": "경복궁", "content_id": "126508"} and out["items"][1]["place"] is None
    assert "sig" not in out["moves"][0] and stored["items"][0]["place"]["place_id"] == "p-1" and stored["moves"][0]["sig"] == "내부 키"
    assert review.public(None) is None


class _Reply:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload
        self.text = "{}"

    def json(self):
        return self._payload


def test_tour_photos_are_fetched_once_cached_only_in_memory_and_unsafe_links_are_dropped():
    from app.domains.travel_ops.ports.data_sources.cache import ResponseCache
    from app.domains.travel_ops.ports.data_sources.tour_api import TourApiPlace

    asked = []

    def transport(url, params):
        asked.append((url, params))
        return _Reply({"response": {"header": {"resultCode": "0000"}, "body": {"items": {"item": [
            {"originimgurl": "https://tong.visitkorea.or.kr/a.jpg", "smallimageurl": "https://tong.visitkorea.or.kr/a_s.jpg", "imgname": "정문"},
            {"originimgurl": "https://tong.visitkorea.or.kr/c.jpg", "smallimageurl": "javascript:alert(1)", "imgname": "썸네일만 나쁨"},
            {"originimgurl": "javascript:alert(1)", "imgname": "나쁜 주소"},
            {"originimgurl": "ftp://x/b.jpg"}, {"originimgurl": ""}]}}}})

    source = TourApiPlace(service_key="test-key", transport=transport, cache=ResponseCache(ttl_seconds=60))
    first = source.images("126508")
    assert first == [{"url": "https://tong.visitkorea.or.kr/a.jpg", "thumb": "https://tong.visitkorea.or.kr/a_s.jpg", "name": "정문"},
                     {"url": "https://tong.visitkorea.or.kr/c.jpg", "thumb": None, "name": "썸네일만 나쁨"}]       # 나쁜 썸네일 주소는 비운다
    assert source.images("126508") == first and len(asked) == 1                     # ★되풀이해 불러도 관광공사에 다시 가지 않는다(프로세스 메모리)
    assert source.images("12; DROP") is None and source.images("") is None and len(asked) == 1       # 숫자가 아니면 부르지도 않는다
    assert "detailImage2" in asked[0][0] and asked[0][1]["contentId"] == "126508"


# ── 말 다듬기 ─────────────────────────────────────────────────────
def test_korean_particles_follow_the_final_sound():
    assert (review.eul("경복궁"), review.eul("광장시장"), review.eul("올리브영")) == ("경복궁을", "광장시장을", "올리브영을")
    assert (review.eul("N서울타워"), review.gwa("경복궁"), review.gwa("사무소")) == ("N서울타워를", "경복궁과", "사무소와")
    assert (review.ro("광장시장"), review.ro("서울숲"), review.ro("서울역"), review.ro("N서울타워"), review.ro("북악산 길")) == (
        "광장시장으로", "서울숲으로", "서울역으로", "N서울타워로", "북악산 길로")


def test_places_carry_their_branch_state_and_text():
    row = {"claims": {"place": {"value": {"name": "올리브영 광화문점", "source": "kakao"}, "method": "lookup", "needs_review": True,
                                "evidence": {"method": "kakao_nearest", "chosen_from": ["a", "b", "c"]}}},
           "place": {"latitude": 1.0}, "title": "올리브영", "kind": "activity"}
    state, value = review.place_state(row)
    assert state == "picked_nearest" and value["name"] == "올리브영 광화문점"
    line = review._place_line(row, state, value)
    assert line["result"] == "warn" and "임시로" in line["text"] and "올리브영 광화문점" in line["text"]
    row["claims"]["place"] = {"value": None, "method": "customer", "needs_review": False, "evidence": {"none": True}}
    assert review.place_state(row) == ("none", None)
    row["claims"]["place"] = {"value": None, "method": "lookup", "needs_review": True, "evidence": {"blocked": ["kakao:timeout"]}}
    row["place"] = None
    assert review._place_line(row, *review.place_state(row))["text"].endswith("못 찾은 것일 수 있어요")


def test_time_notes_are_said_politely_and_worst_result_wins():
    row = {"date": "2026-10-15", "start": "11:00", "end": "12:30", "where": "items[1]", "source_id": "s"}
    notes = {("s", "items[1].ends_at"): "끝 시각이 없어 90분으로 두었다"}
    line = review._time_line(row, notes, "경복궁과 30분 겹쳐요 · 등록 때 막힐 수 있어요", False)
    assert line == {"row": "time", "result": "warn", "text": "끝 시각이 없어 90분으로 두었어요 · 경복궁과 30분 겹쳐요 · 등록 때 막힐 수 있어요"}
    assert review._time_line(row, {}, None, False) is None
    assert review._time_line({**row, "date": None}, {}, None, False)["result"] == "bad"
    assert review._time_line(row, {}, None, True)["text"] == "끝나는 시각(12:30)이 시작(11:00)보다 빨라요"
