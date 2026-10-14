"""활동 장소 적재(`scripts/activity/load_places.py`) — CSV 한 행이 표 한 행으로 어떻게 바뀌나. DB 없이."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
_spec = importlib.util.spec_from_file_location("activity_load_places", ROOT / "scripts" / "activity" / "load_places.py")
load_places = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(load_places)

HEADER = ("contentid,contenttypeid,title,addr1,addr2,lDongSignguCd,mapx,mapy,lclsSystm1,lclsSystm2,lclsSystm3,"
          "overview,business_hours,closed_days,fee,brand\n")


def _write(tmp_path: Path, *lines: str) -> str:
    path = tmp_path / "places.csv"
    path.write_text(HEADER + "".join(line + "\n" for line in lines), encoding="utf-8")
    return str(path)


def test_row_maps_hours_and_extras_and_builds_name_key(tmp_path):
    path = _write(tmp_path, '1,12,"경복궁 (서울)",서울 종로구,,23,126.97,37.57,HS,HS01,HS010100,소개,09:00~18:00,매주 화요일,3000원,')
    [row] = load_places.rows(path)
    assert row["content_id"] == "1" and row["name_ko"] == "경복궁 (서울)"
    assert row["name_key"] == "경복궁"
    assert (row["usetime_text"], row["restdate_text"]) == ("09:00~18:00", "매주 화요일")
    assert (row["overview"], row["fee_text"]) == ("소개", "3000원")
    assert (row["lat"], row["lng"]) == (37.57, 126.97)
    assert row["brand"] is None and row["capacity_text"] is None          # CSV 에 없는 칸은 비운다


def test_missing_or_zero_coordinate_clears_both(tmp_path):
    path = _write(tmp_path, "1,12,가,,,,0,37.5,,,,,,,,", "2,12,나,,,,,37.5,,,,,,,,")
    assert [(r["lat"], r["lng"]) for r in load_places.rows(path)] == [(None, None), (None, None)]


def test_blank_id_or_name_skipped_and_first_duplicate_wins(tmp_path):
    path = _write(tmp_path, ",12,가,,,,,,,,,,,,,", "3,12,,,,,,,,,,,,,,", "4,12,먼저,,,,,,,,,,,,,", "4,12,나중,,,,,,,,,,,,,")
    assert [(r["content_id"], r["name_ko"]) for r in load_places.rows(path)] == [("4", "먼저")]


def test_real_csv_loads_every_row():
    data = load_places.rows(load_places.CSV_PATH)
    assert len(data) == 6334   # [2026-10-11] 4행 정리 — 리포트 2026-10-11_1554_Activity_CSV_컬럼정리 §반영
    assert len({r["content_id"] for r in data}) == len(data)


def test_every_mapped_column_exists_in_the_real_csv():
    """★`[2026-10-12]` CSV 컬럼 이름이 바뀌어도 적재는 오류 없이 NULL 을 넣는다 — 머지 뒤 네 칸이 그렇게 비었다."""
    import csv

    with open(load_places.CSV_PATH, encoding="utf-8-sig", newline="") as fh:
        header = set(next(csv.reader(fh)))
    assert [src for src, _ in load_places.COLUMNS if src not in header] == []
