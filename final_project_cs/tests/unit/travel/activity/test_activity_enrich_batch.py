# -*- coding: utf-8 -*-
"""장소 정보 채우기 배치(`enrich_batch`) — 대상 모으기 · 하나씩 채우며 세기 · 예산이 차면 멈추기. `[2026-10-19]` 가짜만 쓴다."""
from __future__ import annotations

from datetime import datetime, timezone

from app.domains.travel_ops.instances.activity import enrich_batch as eb
from app.domains.travel_ops.instances.activity import place_enrichment as pe

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


class _Cur:
    def __init__(self, rows):
        self.rows, self.params = rows, None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params):
        self.params = params

    def fetchall(self):
        return self.rows


class _Conn:
    def __init__(self, rows):
        self.cur = _Cur(rows)

    def cursor(self):
        return self.cur


def _cands(*names):
    return [eb.Candidate(n, None, NOW) for n in names]


def test_find_names_dedupes_the_same_name_and_number_and_passes_the_window():
    rows = [("경복궁", "126508", NOW), ("경복궁", "126508", NOW), ("OO 카페", None, NOW), ("  OO 카페 ", None, NOW), ("OO 카페", "999", NOW)]
    conn = _Conn(rows)
    found = eb.find_names(conn, NOW, 168, tenant_id="t1")
    assert [(c.name, c.content_id) for c in found] == [("경복궁", "126508"), ("OO 카페", None), ("OO 카페", "999")]
    assert conn.cur.params == (NOW, NOW, "168", "t1", "t1")
    assert "latest_version" in eb._NAMES_SQL and "i.kind = 'activity'" in eb._NAMES_SQL


def test_run_counts_every_status_and_continues_after_a_failure():
    answers = {"a": pe.ENRICHED, "b": pe.COMPLETE, "c": pe.WEB_ERROR, "d": pe.NO_INFO, "e": pe.NOT_FOUND}
    out = eb.run(_cands("a", "b", "c", "d", "e"), lambda name: {"status": answers[name]})
    assert out["targets"] == 5 and out["left"] == 0
    assert out["by_status"] == {pe.ENRICHED: 1, pe.COMPLETE: 1, pe.WEB_ERROR: 1, pe.NO_INFO: 1, pe.NOT_FOUND: 1}
    assert out["asked"] == 3                                      # 실제로 웹 검색을 부른 곳 — 채움 · 못 찾음 · 웹 실패


def test_run_stops_at_the_budget_and_reports_how_many_are_left():
    seen = []

    def enrich(name):
        seen.append(name)
        return {"status": pe.BUDGET if name == "b" else pe.ENRICHED}

    out = eb.run(_cands("a", "b", "c", "d"), enrich)
    assert seen == ["a", "b"] and out["left"] == 2 and out["by_status"][pe.BUDGET] == 1


def test_run_stops_when_there_is_no_table_to_save_into():
    out = eb.run(_cands("a", "b", "c"), lambda name: {"status": pe.TABLE_MISSING})
    assert out["left"] == 2 and out["asked"] == 1


def test_limit_caps_the_number_of_web_searches_not_the_skipped_ones():
    answers = iter([pe.COMPLETE, pe.COMPLETE, pe.ENRICHED, pe.ENRICHED, pe.ENRICHED])
    out = eb.run(_cands("a", "b", "c", "d", "e"), lambda name: {"status": next(answers)}, limit=2)
    assert out["asked"] == 2 and out["left"] == 1 and out["by_status"][pe.COMPLETE] == 2    # 이미 채운 곳은 한도에 세지 않는다
