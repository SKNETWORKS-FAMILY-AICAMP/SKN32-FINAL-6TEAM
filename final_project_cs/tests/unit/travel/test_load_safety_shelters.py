# -*- coding: utf-8 -*-
"""대피 장소 적재 스크립트 — 열 이름을 **추측하지 않고**, 나쁜 줄은 **건너뛰고 센다**. `[결정 2026-10-06 사용자 — 재난 시 피난 안내]`

★지키려는 것
 ①열 이름이 자료마다 달라도(공백 · 대소문자 · 도로명/지번 주소) 후보 중 있는 것을 쓴다
 ②필수 열(이름 · 위도 · 경도)이 없으면 **적재하지 않고** 파일의 열을 보여 주며 멈춘다
 ③좌표가 숫자가 아니거나 한국 범위(33~39 / 124~132) 밖이면(TM 같은 다른 좌표계 · 뒤바뀐 열) 그 줄은 건너뛰고 센다 — 고쳐서 쓰지 않는다
 ④`--region` 은 주소로 거른다 · 지하 여부 · 수용 인원 · 관리번호는 있으면 읽는다
 ⑤UTF-8 이 아니면 CP949 로 읽는다

재현:

    python -m pytest tests/unit/travel/test_load_safety_shelters.py -v
"""
from __future__ import annotations

import pytest

from scripts import load_safety_shelters as loader

HEADER = "시설명,시설구분,소재지도로명주소,위도,경도,시설위치(지상지하),최대수용인원,관리번호"


def _csv(*lines: str) -> str:
    return "\n".join([HEADER, *lines])


def test_a_clean_file_loads_every_row_with_the_optional_columns():
    parsed = loader.parse(_csv("가 대피소,공공,서울특별시 중구 세종대로 1,37.5663,126.9779,지하 1층,500,M-1",
                               "나 대피소,민간,서울특별시 종로구 종로 1,37.5700,126.9830,지상,120,M-2"))
    assert parsed.read == 2 and parsed.skipped == {}
    first, second = parsed.rows
    assert first == {"name": "가 대피소", "address": "서울특별시 중구 세종대로 1", "latitude": 37.5663, "longitude": 126.9779,
                     "underground": True, "capacity": 500, "source_ref": "M-1"}
    assert second["underground"] is False and second["capacity"] == 120


def test_header_variants_are_matched_without_guessing():
    text = "대피장소명,주소,위도 ,경도,수용인원\n옥외 가,서울특별시 강남구 1,37.5,127.0,3000\n"
    parsed = loader.parse(text)
    assert parsed.columns == {"name": "대피장소명", "address": "주소", "latitude": "위도 ", "longitude": "경도", "capacity": "수용인원"}
    assert parsed.rows[0]["capacity"] == 3000 and parsed.rows[0]["underground"] is None and parsed.rows[0]["source_ref"] is None


def test_missing_required_columns_stop_the_load_and_show_the_header():
    with pytest.raises(loader.MissingColumns) as stopped:
        loader.parse("시설명,주소,X좌표,Y좌표\n가,서울,200000,450000\n")
    assert stopped.value.missing == ["latitude", "longitude"] and "X좌표" in str(stopped.value)


@pytest.mark.parametrize("line,reason", [
    (",공공,서울특별시 1,37.5,127.0,지상,10,A", "no_name"),
    ("이름,공공,서울특별시 1,,127.0,지상,10,A", "no_coordinates"),
    ("이름,공공,서울특별시 1,abc,127.0,지상,10,A", "no_coordinates"),
    ("이름,공공,서울특별시 1,200000,450000,지상,10,A", "not_wgs84_korea"),      # TM 좌표
    ("이름,공공,서울특별시 1,127.0,37.5,지상,10,A", "not_wgs84_korea"),          # 위도 · 경도가 뒤바뀜
])
def test_bad_rows_are_skipped_and_counted_not_fixed(line, reason):
    parsed = loader.parse(_csv(line))
    assert parsed.rows == [] and parsed.skipped == {reason: 1}


def test_region_filter_uses_the_address():
    parsed = loader.parse(_csv("가,공공,서울특별시 중구 1,37.5,127.0,지상,10,A", "나,공공,부산광역시 중구 1,35.1,129.0,지상,10,B"), region="서울")
    assert [r["name"] for r in parsed.rows] == ["가"] and parsed.skipped == {"other_region": 1}
    with pytest.raises(loader.MissingColumns):
        loader.parse("시설명,위도,경도\n가,37.5,127.0\n", region="서울")             # 주소가 없는데 지역으로 거를 수 없다


def test_cp949_files_are_read(tmp_path):
    path = tmp_path / "shelters.csv"
    path.write_bytes(_csv("가 대피소,공공,서울특별시 중구 1,37.5,127.0,지상,10,A").encode("cp949"))
    assert "가 대피소" in loader.read_text(path)
    utf8 = tmp_path / "u.csv"
    utf8.write_bytes("﻿".encode("utf-8") + _csv("나,공공,서울,37.5,127.0,지상,10,A").encode("utf-8"))
    assert loader.parse(loader.read_text(utf8)).rows[0]["name"] == "나"
