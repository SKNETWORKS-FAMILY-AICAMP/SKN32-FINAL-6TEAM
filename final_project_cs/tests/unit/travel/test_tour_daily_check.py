# -*- coding: utf-8 -*-
"""관광공사 일일 정기점검 — 03시 시작 · 마감 없음 · 고객이 일정에 넣은 장소만 하루 한 번 다시 읽는다. `[2026-10-14 사용자 지시]` DB 없이 본다.

사용자 말: 「관광공사에서 장소 자체가 잘 바뀌지 않아 그래서 하루 1회 일일 정기점검 때 하기로 했어. 일일 정기점검은 마감시간 8시 아니고 그냥 3시 시작」.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.domains.travel_ops.components.places import catalog_hours as ch
from app.domains.travel_ops.components.places import place_info

KST = timezone(timedelta(hours=9))


# ── 하루 몫의 시작 ────────────────────────────────────────────────
def test_the_day_starts_at_three_and_before_three_belongs_to_yesterday():
    assert ch.day_start(datetime(2030, 1, 2, 10, 0, tzinfo=KST), "03:00") == datetime(2030, 1, 2, 3, 0, tzinfo=KST)
    assert ch.day_start(datetime(2030, 1, 2, 3, 0, tzinfo=KST), "03:00") == datetime(2030, 1, 2, 3, 0, tzinfo=KST)
    assert ch.day_start(datetime(2030, 1, 2, 2, 59, tzinfo=KST), "03:00") == datetime(2030, 1, 1, 3, 0, tzinfo=KST)


# ── 운영시간 읽기: 08시 마감이 없다 ───────────────────────────────
class _Conn:
    def __init__(self, done=0):
        self.done, self.params = done, []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        self.params.append(params)

    def fetchone(self):
        return (self.done,)

    def fetchall(self):
        return []


class _Tour:
    def operating(self, content_id, type_id):
        raise AssertionError("읽을 곳이 없으면 부르지 않는다")


def test_without_an_end_time_the_hours_job_still_runs_after_eight():
    conn = _Conn()
    got = ch.prefill(conn, tenant_id="t", source=_Tour(), chat=None, now=datetime(2030, 1, 2, 9, 30, tzinfo=KST),
                     start="03:00", until=None, per_night=600, per_tick=10, retry_days=7)
    assert "skipped" not in got
    assert conn.params[0][1] == datetime(2030, 1, 2, 3, 0, tzinfo=KST)        # 하루 몫은 그날 03시부터 센다


def test_the_day_budget_still_stops_it():
    got = ch.prefill(_Conn(done=600), tenant_id="t", source=_Tour(), chat=None,
                     now=datetime(2030, 1, 2, 23, 0, tzinfo=KST), start="03:00", until=None,
                     per_night=600, per_tick=10, retry_days=7)
    assert got["skipped"] == "오늘 밤 몫을 다 썼다"


def test_an_explicit_end_time_still_works_for_rollback():
    got = ch.prefill(_Conn(), tenant_id="t", source=_Tour(), chat=None, now=datetime(2030, 1, 2, 9, 0, tzinfo=KST),
                     start="03:00", until="08:00", per_night=600, per_tick=10, retry_days=7)
    assert got["skipped"] == "창 밖"


# ── 일정에 넣은 장소: 하루 한 번 다시 읽기 ─────────────────────────
class _FactsConn:
    def __init__(self, rows):
        self.rows, self.select, self.updates = rows, None, []

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
            self.select = (sql, params)
        else:
            self.updates.append(params)

    def fetchall(self):
        return self.rows


class _Intro:
    def __init__(self, intro=None, fail=False):
        self.intro, self.fail = intro, fail

    def operating(self, content_id, type_id):
        if self.fail:
            raise LookupError("관광공사 응답 없음")
        return self.intro


NOW = datetime(2030, 1, 2, 3, 5, tzinfo=KST)
DAY = ch.day_start(NOW, "03:00").isoformat()
READ_BEFORE = {"source_content_id": "1", "source_content_type_id": "12", "hours_week": {"1": ["09:00-18:00"]},
               "hours_read": {"source": "tour_api", "method": "rule", "read_at": "2030-01-01T10:00:00+09:00"}}


def _row(attributes):
    return [("p1", "경복궁", "activity", 37.5, 126.9, attributes)]


def test_only_places_in_trips_are_asked_and_the_daily_refresh_is_in_the_query():
    conn = _FactsConn([])
    place_info.fill_missing_facts(conn, "t", source=_Intro(), chat=None, now=NOW, refresh_from=DAY)
    sql, params = conn.select
    assert "FROM trips t JOIN itinerary_items i" in sql                    # 일정에 넣은 장소만 — 관광공사 전체 목록이 아니다
    assert "hours_refresh" in sql and params.count(DAY) == 2


def test_without_the_daily_refresh_only_new_places_are_asked():
    conn = _FactsConn([])
    place_info.fill_missing_facts(conn, "t", source=_Intro(), chat=None, now=NOW)
    assert "hours_refresh" not in conn.select[0]


def test_a_failed_reread_keeps_the_hours_read_yesterday():
    conn = _FactsConn(_row(dict(READ_BEFORE)))
    got = place_info.fill_missing_facts(conn, "t", source=_Intro(fail=True), chat=None, now=NOW, refresh_from=DAY)
    patch, drop = json.loads(conn.updates[0][0]), conn.updates[0][1]
    assert set(patch) == {"hours_refresh"} and drop == [] and got["unknown"] == 1   # 어제 읽은 요일표는 그대로


def test_a_reread_that_cannot_make_a_week_drops_the_old_week(monkeypatch):
    from app.domains.travel_ops.components.places import place_hours

    class _Read:
        week = None

        def as_record(self, **kw):
            return {"source": "tour_api", "method": "none_week", **kw}

    monkeypatch.setattr(place_hours, "read_hours", lambda usetime, restdate, chat: _Read())
    conn = _FactsConn(_row(dict(READ_BEFORE)))
    place_info.fill_missing_facts(conn, "t", source=_Intro({"usetime_text": "문의", "restdate_text": ""}), chat=None,
                                  now=NOW, refresh_from=DAY)
    assert conn.updates[0][1] == ["hours_week"]
