# -*- coding: utf-8 -*-
"""일일 정기점검 — 03시 시작 · 가능하면 03:30 까지 · 안 끝나면 관리자 웹앱 보고 · 08:00 에 모두 멈춤. `[2026-10-14 사용자 지시]` DB 없이 본다.

사용자 말: 「관광공사에서 장소 자체가 잘 바뀌지 않아 그래서 하루 1회 일일 정기점검 때 하기로 했어」 · 「전체 받는 게 아니라 사용자가 등록한 장소에 대한 부분들만」 ·
「3시 시작 가능하면 3시 30분까지 마감하게 하고 안 끝나고 있으면 관리자 웹앱에 보고 들어가게 만들어놔. 그리고 8시에는 모두 멈추게 해 지금처럼」.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.domains.travel_ops.components.places import catalog_hours as ch
from app.domains.travel_ops.components.places import place_info
from app.domains.travel_ops.components.watch import daily_check as dc

KST = timezone(timedelta(hours=9))


def _at(hour, minute=0, day=2):
    return datetime(2030, 1, day, hour, minute, tzinfo=KST)


def _win(now):
    return dc.window(now, start="03:00", finish_by="03:30", stop="08:00")


# ── 시각 ──────────────────────────────────────────────────────────
def test_the_window_opens_at_three_aims_at_half_past_and_stops_at_eight():
    assert not _win(_at(2, 59)).open and _win(_at(2, 59)).day == "2030-01-01"
    assert _win(_at(3, 0)).open and not _win(_at(3, 0)).past_finish_by
    assert _win(_at(3, 30)).past_finish_by and _win(_at(7, 59)).open
    assert not _win(_at(8, 0)).open and not _win(_at(8, 0)).past_finish_by      # 8시에는 모두 멈춘다


def test_pacing_spreads_the_rest_over_the_minutes_left_to_half_past_three():
    assert dc.paced(600, base=10, cap=25, win=_win(_at(3, 0))) == 20           # 600곳 ÷ 30분
    assert dc.paced(30, base=10, cap=25, win=_win(_at(3, 0))) == 10            # 적으면 최소 양
    assert dc.paced(600, base=10, cap=25, win=_win(_at(3, 20))) == 25          # 많아야 상한(관광공사 몰림 허용 안)
    assert dc.paced(5, base=10, cap=25, win=_win(_at(3, 40))) == 25            # 지났으면 상한으로 마저 한다


def test_unfinished_jobs_are_told_apart_from_finished_and_unknown_ones():
    late, unknown = dc.unfinished({
        "place_facts": {"asked": 25, "remaining": 40},
        "catalog_hours": {"skipped": "오늘 밤 몫을 다 썼다"},
        "trip_dawn": {"outside_window": False, "disabled": None, "checked": 0, "fatal": 0},
        "team:activity_live_status": {"checked": 3},
        "team:dining_refresh": {"remaining": 0},
        "team:broken": {"fatal": 1},
        "web_guard": {"fatal": 1},                                           # 정기점검 작업이 아니다
    })
    assert late == ["place_facts", "team:broken"] and unknown == ["team:activity_live_status"]
    assert dc.code_of("team:activity_live_status") == "TEAM_ACTIVITY_LIVE_STATUS"


# ── 운영시간 읽기(대체 후보용): 03:30 까지 양을 맞추고 08:00 에 멈춘다 ──
class _Conn:
    def __init__(self, done=0, due=0):
        self.answers, self.params = [(done,), (due,)], []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        self.params.append(params)

    def fetchone(self):
        return self.answers.pop(0)

    def fetchall(self):
        return []


class _Tour:
    def operating(self, content_id, type_id):
        raise AssertionError("읽을 곳이 없으면 부르지 않는다")


def _prefill(conn, now, **kw):
    return ch.prefill(conn, tenant_id="t", source=_Tour(), chat=None, now=now, start="03:00", until="08:00",
                      per_night=600, per_tick=10, retry_days=7, **kw)


def test_the_hours_job_stops_at_eight():
    assert _prefill(_Conn(), _at(8, 0))["skipped"] == "창 밖"


def test_the_hours_job_reads_more_per_tick_to_finish_by_half_past_three():
    conn = _Conn(due=600)
    got = _prefill(conn, _at(3, 0), pace=lambda left: dc.paced(left, base=10, cap=25, win=_win(_at(3, 0))))
    assert conn.params[-1][-1] == 20 and got["remaining"] == 600                # 이번에 20곳(흉내 연결이 0곳을 돌려줘 남은 수는 그대로)
    assert conn.params[0][1] == _at(3, 0)                                       # 하루 몫은 그날 03시부터 센다


def test_the_day_budget_still_stops_it():
    assert _prefill(_Conn(done=600), _at(5, 0))["skipped"] == "오늘 밤 몫을 다 썼다"


# ── 일정에 넣은 장소: 창 안에서 하루 한 번 다시 읽기 ───────────────
class _FactsConn:
    def __init__(self, rows, counts=(0, 0)):
        self.rows, self.counts, self.selects, self.updates = rows, counts, [], []

    def cursor(self):
        return self

    def transaction(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        if sql.startswith("SELECT"):
            self.selects.append((sql, params))
        else:
            self.updates.append(params)

    def fetchone(self):
        return self.counts

    def fetchall(self):
        return self.rows


class _Intro:
    def __init__(self, intro=None, fail=False):
        self.intro, self.fail = intro, fail

    def operating(self, content_id, type_id):
        if self.fail:
            raise LookupError("관광공사 응답 없음")
        return self.intro


NOW = _at(3, 5)
DAY = _win(NOW).started_at.isoformat()
READ_BEFORE = {"source_content_id": "1", "source_content_type_id": "12", "hours_week": {"1": ["09:00-18:00"]},
               "hours_read": {"source": "tour_api", "method": "rule", "read_at": "2030-01-01T10:00:00+09:00"}}


def _row(attributes):
    return [("p1", "경복궁", "activity", 37.5, 126.9, attributes)]


def test_only_places_in_trips_are_asked_paced_and_counted():
    conn = _FactsConn([], counts=(300, 280))
    got = place_info.fill_missing_facts(conn, "t", source=_Intro(), chat=None, now=NOW, refresh_from=DAY,
                                        pace=lambda left: dc.paced(left, base=10, cap=25, win=_win(NOW)))
    _, rows_sql = conn.selects
    assert "FROM trips t JOIN itinerary_items i" in rows_sql[0]              # 일정에 넣은 장소만 — 관광공사 전체 목록이 아니다
    assert "hours_refresh" in rows_sql[0] and rows_sql[1][-1] == 12          # 300곳 ÷ 25분 → 12곳
    assert got["remaining"] == 280


def test_outside_the_window_only_new_places_are_asked_and_nothing_is_counted():
    conn = _FactsConn([])
    got = place_info.fill_missing_facts(conn, "t", source=_Intro(), chat=None, now=_at(9, 0))
    assert len(conn.selects) == 1 and "hours_refresh" not in conn.selects[0][0] and "remaining" not in got


def test_a_failed_reread_keeps_the_hours_read_yesterday():
    conn = _FactsConn(_row(dict(READ_BEFORE)), counts=(1, 1))
    got = place_info.fill_missing_facts(conn, "t", source=_Intro(fail=True), chat=None, now=NOW, refresh_from=DAY)
    patch, drop = json.loads(conn.updates[0][0]), conn.updates[0][1]
    assert set(patch) == {"hours_refresh"} and drop == [] and got["unknown"] == 1 and got["remaining"] == 0


def test_a_reread_that_cannot_make_a_week_drops_the_old_week(monkeypatch):
    from app.domains.travel_ops.components.places import place_hours

    class _Read:
        week = None

        def as_record(self, **kw):
            return {"source": "tour_api", "method": "none_week", **kw}

    monkeypatch.setattr(place_hours, "read_hours", lambda usetime, restdate, chat: _Read())
    conn = _FactsConn(_row(dict(READ_BEFORE)), counts=(1, 1))
    place_info.fill_missing_facts(conn, "t", source=_Intro({"usetime_text": "문의", "restdate_text": ""}), chat=None,
                                  now=NOW, refresh_from=DAY)
    assert conn.updates[0][1] == ["hours_week"]


# ── 03:30 이 지나면 안 끝난 작업을 관리자 웹앱에 보고 ─────────────────
def _deadline(monkeypatch, now, result, *, claimed=True):
    from contextlib import contextmanager

    import scripts.run_sweepers as rs
    from app.application import job_gate, operations_diagnostics

    events = []

    class _C:
        def transaction(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    @contextmanager
    def connect():
        yield _C()

    monkeypatch.setattr(rs, "get_connection", connect)
    monkeypatch.setattr(job_gate, "claim", lambda conn, **kw: claimed)
    monkeypatch.setattr(operations_diagnostics, "record",
                        lambda event, **kw: events.append(event) or {"status": "stored", "event_id": str(event.event_id)})
    return rs._daily_check_deadline("tenant_a", result, now=now), events


def test_after_half_past_three_unfinished_work_is_reported_with_its_codes(monkeypatch):
    out, events = _deadline(monkeypatch, _at(3, 31), {"place_facts": {"remaining": 40}, "catalog_hours": {"remaining": 0}})
    assert out["late"] == ["place_facts"] and out["report"] == "stored"
    assert events[0].code == "DAILY_CHECK_OVERDUE" and events[0].conditions == ["PLACE_FACTS"]
    _, again = _deadline(monkeypatch, _at(5, 0), {"place_facts": {"remaining": 40}})
    assert again[0].event_id == events[0].event_id                           # 같은 날은 같은 사건 번호 — 운영 진단에 두 번 세지 않는다


def test_nothing_is_reported_before_half_past_three_after_eight_or_when_all_is_done(monkeypatch):
    assert _deadline(monkeypatch, _at(3, 20), {"place_facts": {"remaining": 40}})[0] is None
    assert _deadline(monkeypatch, _at(8, 5), {"place_facts": {"remaining": 40}})[0] is None
    out, events = _deadline(monkeypatch, _at(3, 31), {"place_facts": {"remaining": 0}})
    assert out["late"] == [] and events == []
    assert _deadline(monkeypatch, _at(4, 0), {"place_facts": {"remaining": 9}}, claimed=False)[0] is None   # 오늘 이미 판정했다


# ── 운영정보 칸이 없는 곳에서 멈추지 않는다 `[2026-10-15 x600 서버 실측]` ─────────────────────
class _DueConn:
    """읽을 곳 둘을 돌려주는 흉내 연결 — 첫째가 운영정보 없는 곳(동상), 둘째가 정상."""

    def __init__(self):
        self.writes, self._rows, self._answers = [], [("1603296", "12", "서빙고동 부군당", "20250924", None, None),
                                                      ("1604580", "12", "정상 장소", "20250711", None, None)], [(0,), (2,)]

    def cursor(self):
        return self

    def transaction(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        if sql.startswith("INSERT"):
            self.writes.append(params)

    def fetchone(self):
        return self._answers.pop(0)

    def fetchall(self):
        return self._rows


class _NoInfoThenOk:
    def __init__(self, reason):
        from collections import Counter

        self.misses, self.reason, self.calls = Counter(), reason, []

    def operating(self, content_id, type_id):
        self.calls.append(content_id)
        if content_id == "1603296":
            self.misses[self.reason] += 1
            return None
        return {"usetime_text": "09:00~18:00", "restdate_text": "", "info_phone": None}


def test_a_place_the_provider_answered_without_hours_is_recorded_as_unknown_and_the_job_moves_on():
    """전에는 첫 곳(운영정보 칸 없음)에서 멈춰 다음 틱도 같은 곳만 불렀다 — 09-30 이후 읽은 곳 0 · 하룻밤 300번 호출."""
    conn, tour = _DueConn(), _NoInfoThenOk("no_operating_fields")
    got = ch.prefill(conn, tenant_id="t", source=tour, chat=None, now=_at(3, 0), start="03:00", until="08:00",
                     per_night=600, per_tick=10, retry_days=7)
    assert tour.calls == ["1603296", "1604580"] and got["stopped"] is None, got            # 첫 곳 뒤로 나아갔다
    assert got["no_operating_info"] == 1 and got["read"] == 1 and len(conn.writes) == 2, got
    assert conn.writes[0][0:3] == ("t", "1603296", "12")                                    # 첫 곳은 「모름」 행으로 적었다


def test_a_real_call_failure_still_stops_the_tick_and_writes_nothing():
    conn, tour = _DueConn(), _NoInfoThenOk("rate_limited")
    got = ch.prefill(conn, tenant_id="t", source=tour, chat=None, now=_at(3, 0), start="03:00", until="08:00",
                     per_night=600, per_tick=10, retry_days=7)
    assert tour.calls == ["1603296"] and "운영정보를 받지 못했다" in got["stopped"] and conn.writes == [], got
