# -*- coding: utf-8 -*-
"""enrich_place_catalog_from_csv — 사람이 채운 영업시간(`field_sources`)을 관광공사 값으로 적지 않는다. DB 없이 본다.

`[2026-10-12 사용자]` `wiki/teams/db_column.md` 30번 `field_sources` 를 DB 적재에 반영.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import pytest

from app.domains.travel_ops.instances.activity.hours_text import read_week
from scripts import enrich_place_catalog_from_csv as e

SRC = {"by": "human", "url": "https://www.example.go.kr/info", "checked": "2026-10-12"}
NOW = datetime(2026, 10, 12, 3, 0, tzinfo=timezone.utc)


def _row(cid, title="경복궁", business_hours="", closed_days="", sources=None, **cols):
    return {"contentid": cid, "contenttypeid": "12", "title": title, "mapx": "126.97", "mapy": "37.57",
            "brand": "", "business_hours": business_hours, "closed_days": closed_days,
            "field_sources": json.dumps(sources, ensure_ascii=False) if sources else "", **cols}


def test_only_the_two_hours_columns_travel_with_the_hours():
    row = _row("1", closed_days="매주 화요일", tel="02-000-0000", sources={"closed_days": SRC, "tel": SRC})
    assert e.hours_sources(row) == {"closed_days": SRC}
    assert e.hours_sources(_row("2", closed_days="매주 화요일")) == {}


def test_plan_carries_sources_only_for_rows_a_person_filled():
    rows = [_row("1", business_hours="09:00~18:00", closed_days="매주 화요일", sources={"closed_days": SRC}),
            _row("2", business_hours="09:00~18:00", closed_days="매주 월요일")]
    built = e.build_plan(rows, [("1", "경복궁", 37.57, 126.97), ("2", "창덕궁", 37.58, 126.99)])
    assert built["plan"]["1"]["hours_sources"] == {"closed_days": SRC}
    assert "hours_sources" not in built["plan"]["2"]
    assert built["stats"]["hours_from_official_web"] == 1


def test_hours_record_names_the_official_page_instead_of_tourapi():
    read = read_week("09:00~18:00", "매주 화요일")
    assert read is not None
    human = e.hours_record(read, NOW, {"closed_days": SRC})
    assert human["source"] == "official_web" and human["field_sources"] == {"closed_days": SRC}
    tour = e.hours_record(read, NOW, {})
    assert tour["source"] == "activity_csv" and "field_sources" not in tour


def test_main_stops_before_touching_the_db_when_sources_are_broken(tmp_path, monkeypatch):
    path = tmp_path / "bad.csv"
    row = _row("1", sources={"fee": SRC})                    # 빈 칸에 출처만 있다
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    class _NoDb:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def cursor(self):
            return self

        def execute(self, *a):
            pass

        def fetchall(self):
            return []

    monkeypatch.setattr(e, "get_connection", lambda: _NoDb())
    monkeypatch.setattr(e, "apply", lambda *a: pytest.fail("DB 에 쓰면 안 된다"))
    with pytest.raises(SystemExit, match="field_sources 형식 오류"):
        e.main([str(path), "--tenant", "t", "--apply"])


def test_not_applicable_markers_are_not_loaded_as_sources():
    na = {"by": "human", "na": True, "checked": "2026-10-12"}
    row = _row("1", business_hours="09:00~18:00", sources={"closed_days": na})
    assert e.hours_sources(row) == {}
