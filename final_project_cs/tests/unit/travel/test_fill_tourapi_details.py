# -*- coding: utf-8 -*-
"""fill_tourapi_details — `wiki/teams/db_column.md`(30개 컬럼)대로 빈 칸을 채우는 규칙. 네트워크 없이 본다.

`[2026-10-11]` 옛 판(EXTRA_FIELDS · info_center · reservation · spend_time)에서 문서 판으로 바꿨다.
"""
from __future__ import annotations

import json

import pytest

from app.domains.travel_ops.instances.activity.data_processing import fill_tourapi_details as f


def _row(cid="1", ctype="12", addr1="서울특별시 양천구 목동", **cols):
    base = {c: "" for c in f.COLUMNS}
    return {**base, "contentid": cid, "contenttypeid": ctype, "addr1": addr1, **cols}


def test_columns_are_the_30_of_db_column_md_and_every_mapped_column_exists():
    assert len(f.COLUMNS) == 30 == len(set(f.COLUMNS))
    mapped = {c for fields in f.INTRO_FIELDS.values() for c in fields} | set(f.COMMON_COLUMNS) | {"tel"}
    assert mapped <= set(f.COLUMNS)
    assert set(f.TEL_FALLBACK) == set(f.INTRO_FIELDS) == set(f.PRIORITY)
    assert not {"indoor_outdoor", "indoor_outdoor_source"} & mapped          # 실내외는 이 스크립트가 안 채운다


def test_each_type_maps_its_own_field_names():
    assert f.INTRO_FIELDS["12"] == {"business_hours": "usetime", "closed_days": "restdate", "capacity": "accomcount",
                                    "pet": "chkpet", "age_limit": "expagerange", "experience_guide": "expguide"}
    assert f.INTRO_FIELDS["14"] == {"business_hours": "usetimeculture", "closed_days": "restdateculture",
                                    "fee": "usefee", "capacity": "accomcountculture", "spendtime": "spendtime",
                                    "pet": "chkpetculture"}
    assert f.INTRO_FIELDS["15"] == {"business_hours": "playtime", "fee": "usetimefestival",
                                    "reservation_info": ("bookingplace", "eventhomepage"),
                                    "spendtime": "spendtimefestival", "eventstartdate": "eventstartdate",
                                    "eventenddate": "eventenddate", "age_limit": "agelimit"}
    assert f.INTRO_FIELDS["28"] == {"business_hours": "usetimeleports", "closed_days": "restdateleports",
                                    "fee": "usefeeleports", "capacity": "accomcountleports",
                                    "reservation_info": "reservation", "pet": "chkpetleports",
                                    "age_limit": "expagerangeleports"}
    assert f.INTRO_FIELDS["38"] == {"business_hours": "opentime", "closed_days": "restdateshopping",
                                    "pet": "chkpetshopping"}


def test_several_fields_with_one_meaning_are_joined_without_blanks_or_duplicates():
    assert f._joined({"sponsor1tel": "02-1", "sponsor2tel": "02-2"}, ("sponsor1tel", "sponsor2tel")) == "02-1 / 02-2"
    assert f._joined({"sponsor1tel": "02-1", "sponsor2tel": ""}, ("sponsor1tel", "sponsor2tel")) == "02-1"
    assert f._joined({"sponsor1tel": "02-1", "sponsor2tel": "02-1"}, ("sponsor1tel", "sponsor2tel")) == "02-1"
    assert f._joined({}, ("sponsor1tel", "sponsor2tel")) == ""


def test_migrate_renames_old_columns_drops_sigungucode_and_keeps_existing_values():
    rows = [{"contentid": "1", "info_center": "02-1", "reservation": "전화", "spend_time": "1시간",
             "sigungucode": "19", "tel": ""}]
    stats = f.migrate(rows, ["contentid", "info_center", "reservation", "spend_time", "sigungucode", "tel"])
    assert set(rows[0]) == set(f.COLUMNS)
    assert (rows[0]["tel"], rows[0]["reservation_info"], rows[0]["spendtime"]) == ("02-1", "전화", "1시간")
    assert rows[0]["lDongSignguCd"] == ""                                     # 옛 코드는 체계가 달라 옮기지 않는다
    assert stats["sigungucode 지움"] == 1


def test_migrate_stops_on_an_unknown_column_instead_of_dropping_it():
    with pytest.raises(SystemExit):
        f.migrate([{"contentid": "1", "mystery": "x"}], ["contentid", "mystery"])


def test_every_tourapi_row_needs_both_calls_and_brand_or_unknown_rows_none():
    assert f.operations_for(_row()) == f.BOTH_OPERATIONS
    assert f.operations_for(_row(overview="개요", tel="02-1")) == f.BOTH_OPERATIONS   # 캐시에 있으면 fetch 가 건너뛴다
    assert f.operations_for(_row(cid="OY1", ctype="38")) == ()                         # 브랜드 행은 안 부른다
    assert f.operations_for(_row(ctype="99")) == ()                                    # 모르는 타입


def test_apply_cache_fills_blanks_from_both_responses_without_overwriting():
    rows = [_row("1", "28", overview="이미 있음"), _row("2", "15")]
    cache = {("1", "detailCommon2"): {"overview": "새 개요", "tel": "", "lDongSignguCd": "470"},
             ("1", "detailIntro2"): {"infocenterleports": "02-111", "reservation": "전화 예약",
                                     "accomcountleports": "30명", "expagerangeleports": "만 7세 이상",
                                     "usetimeleports": "09~18"},
             ("2", "detailCommon2"): {"overview": "행사 개요", "tel": "02-9", "homepage": "<a href=x>",
                                      "modifiedtime": "20261001"},
             ("2", "detailIntro2"): {"bookingplace": "현장", "eventhomepage": "https://ex.kr",
                                     "spendtimefestival": "1시간", "agelimit": "전체", "usetimefestival": "무료",
                                     "eventstartdate": "20261010", "eventenddate": "20261012",
                                     "sponsor1tel": "02-1", "sponsor2tel": "02-2"}}
    stats = f.apply_cache(rows, cache)
    assert rows[0]["overview"] == "이미 있음"                                           # 있던 칸은 그대로
    assert rows[0]["tel"] == "02-111"                                                   # common 이 비어 문의처로
    assert (rows[0]["reservation_info"], rows[0]["capacity"], rows[0]["lDongSignguCd"]) == ("전화 예약", "30명", "470")
    assert rows[1]["tel"] == "02-9"                                                     # common 이 있으면 문의처는 안 쓴다
    assert (rows[1]["reservation_info"], rows[1]["spendtime"], rows[1]["fee"]) == ("현장 / https://ex.kr", "1시간", "무료")
    assert (rows[1]["eventstartdate"], rows[1]["eventenddate"], rows[1]["homepage"]) == ("20261010", "20261012", "<a href=x>")
    assert rows[1]["capacity"] == "" and rows[1]["closed_days"] == ""                 # 그 타입에 없는 칸은 비운다
    assert stats["reservation_info"] == 2 and "overview" in stats


def test_experience_guide_comes_only_from_sightseeing_expguide():
    rows = [_row("1", "12", overview="개요"), _row("2", "14", overview="개요")]
    f.apply_cache(rows, {("1", "detailIntro2"): {"expguide": "체험 예약은 전화로"},
                         ("2", "detailIntro2"): {"expguide": "무시되어야 함"}})
    assert rows[0]["experience_guide"] == "체험 예약은 전화로" and rows[1]["experience_guide"] == ""


def test_addr2_comes_from_detail_common_only_into_blank_cells():
    rows = [_row("1", "14"), _row("2", "14", addr2="기존 상세주소")]
    f.apply_cache(rows, {("1", "detailCommon2"): {"addr2": "스타필드 코엑스몰 B1"},
                         ("2", "detailCommon2"): {"addr2": "덮어쓰면 안 됨"}})
    assert rows[0]["addr2"] == "스타필드 코엑스몰 B1" and rows[1]["addr2"] == "기존 상세주소"


def test_apply_cache_never_touches_indoor_outdoor():
    rows = [_row("1", "12", indoor_outdoor="indoor", indoor_outdoor_source="human:2026-10-11")]
    f.apply_cache(rows, {("1", "detailCommon2"): {"indoor_outdoor": "outdoor"}})
    assert (rows[0]["indoor_outdoor"], rows[0]["indoor_outdoor_source"]) == ("indoor", "human:2026-10-11")


def test_brand_rows_take_the_code_of_their_gu_only_when_one_code_dominates():
    tour = [_row(str(i), addr1="서울특별시 중구 a", lDongSignguCd="140") for i in range(1, 20)]       # 중구 140 ×19
    tour += [_row("20", addr1="서울특별시 중구 한강대로 405", lDongSignguCd="170"),                      # 경계 1곳 → 95%
             _row("21", addr1="서울 마포구 b", lDongSignguCd="440"), _row("22", addr1="서울 마포구 c", lDongSignguCd="999")]
    rows = tour + [_row("OY1", "38", addr1="서울특별시 중구 명동길 53"),
                   _row("OY2", "38", addr1="서울특별시 마포구 양화로"),
                   _row("OY3", "38", addr1="서울특별시 강서구 공항대로"),
                   _row("OY4", "38", addr1="서울특별시 중구 x", lDongSignguCd="111")]
    stats = f.fill_brand_signgu(rows)
    assert [r["lDongSignguCd"] for r in rows[-4:]] == ["140", "", "", "111"]           # 마포 50:50 은 비움 · 있던 값 그대로
    assert stats == {"브랜드 lDongSignguCd": 1, "브랜드 lDongSignguCd(다수 규칙)": 1,
                     "브랜드 구 코드 여럿(안 채움)": 1, "브랜드 구 코드 모름": 1}


# ── field_sources (`[2026-10-12 사용자]`) ────────────────────────
SRC = {"by": "human", "url": "https://www.example.go.kr/info", "checked": "2026-10-12"}


def _sources(**cols):
    return json.dumps(cols, ensure_ascii=False)


def test_human_filled_cells_are_listed_and_only_fillable_columns_allowed():
    assert f.SOURCES_COLUMN == f.COLUMNS[-1]
    assert set(f.HUMAN_FILLABLE) <= set(f.COLUMNS)
    assert not {"contentid", "title", "mapx", "mapy", "overview", "experience_guide", "indoor_outdoor"} & set(f.HUMAN_FILLABLE)


def test_valid_sources_pass_and_each_kind_of_mistake_is_reported():
    good = _row("1", "12", closed_days="매주 월요일", field_sources=_sources(closed_days=SRC))
    claude = _row("b", "12", tel="02-000-0000",
                  field_sources=_sources(tel={**SRC, "by": "claude", "quote": "문의 02-000-0000"}))
    assert f.source_errors([good, claude, _row("2", "12")]) == []
    bad = [
        _row("3", "12", field_sources="{not json"),
        _row("4", "12", overview="개요", field_sources=_sources(overview=SRC)),              # 허용 밖
        _row("5", "12", field_sources=_sources(fee=SRC)),                                     # 빈 칸의 출처
        _row("6", "12", fee="무료", field_sources=_sources(fee={**SRC, "by": "kakao"})),
        _row("a", "12", fee="무료", field_sources=_sources(fee={**SRC, "by": "claude"})),          # 근거 문구 없음
        _row("7", "12", fee="무료", field_sources=_sources(fee={**SRC, "url": "블로그"})),
        _row("8", "12", fee="무료", field_sources=_sources(fee={**SRC, "checked": "10/12"})),
        _row("9", "12", fee="무료", field_sources=_sources(fee={"by": "human"})),
    ]
    errors = f.source_errors(bad)
    for cid in "3456789a":
        assert any(e.startswith(cid + " ") for e in errors), cid


def test_tourapi_value_replaces_a_human_value_and_drops_its_source():
    rows = [_row("1", "12", closed_days="매주 월요일", tel="02-000-0000",
                 field_sources=_sources(closed_days=SRC, tel=SRC))]
    stats = f.apply_cache(rows, {("1", "detailIntro2"): {"restdate": "연중무휴"}})
    assert rows[0]["closed_days"] == "연중무휴" and rows[0]["tel"] == "02-000-0000"
    assert json.loads(rows[0]["field_sources"]) == {"tel": SRC}
    assert stats["closed_days(사람 값→TourAPI)"] == 1


def test_human_value_stays_when_tourapi_is_empty_and_tourapi_values_are_never_replaced_otherwise():
    rows = [_row("1", "12", closed_days="매주 월요일", field_sources=_sources(closed_days=SRC)),
            _row("2", "12", closed_days="기존 TourAPI 값")]
    f.apply_cache(rows, {("1", "detailIntro2"): {"restdate": ""}, ("2", "detailIntro2"): {"restdate": "새 값"}})
    assert rows[0]["closed_days"] == "매주 월요일" and json.loads(rows[0]["field_sources"]) == {"closed_days": SRC}
    assert rows[1]["closed_days"] == "기존 TourAPI 값" and rows[1]["field_sources"] == ""


def test_main_stops_before_calling_or_writing_when_sources_are_broken(monkeypatch):
    rows = [_row("1", "12", field_sources=_sources(fee=SRC))]
    monkeypatch.setattr(f, "read_csv", lambda: rows)
    monkeypatch.setattr(f, "fetch", lambda *a: pytest.fail("호출하면 안 된다"))
    monkeypatch.setattr(f, "write_csv", lambda *a: pytest.fail("쓰면 안 된다"))
    with pytest.raises(SystemExit, match="field_sources 형식 오류"):
        f.main(["--max-calls", "0"])


# ── 「해당 없음」 (`[2026-10-12 사용자]`) ───────────────────────────
NA = {"by": "human", "na": True, "checked": "2026-10-12", "note": "거리 — 대표 전화가 원래 없다"}


def test_not_applicable_sits_on_a_blank_cell_without_a_url():
    assert f.source_errors([_row("1", "12", field_sources=_sources(tel=NA))]) == []
    errors = f.source_errors([_row("2", "12", tel="02-000-0000", field_sources=_sources(tel=NA)),     # 값이 있다
                              _row("3", "12", field_sources=_sources(tel={**NA, "url": "https://x"})),  # 모르는 키
                              _row("4", "12", field_sources=_sources(tel={**NA, "checked": "어제"}))])
    for cid in "234":
        assert any(e.startswith(cid + " ") for e in errors), cid


def test_a_tourapi_value_replaces_the_not_applicable_marker():
    rows = [_row("1", "12", field_sources=_sources(closed_days=NA, tel=NA))]
    stats = f.apply_cache(rows, {("1", "detailIntro2"): {"restdate": "연중무휴"}})
    assert rows[0]["closed_days"] == "연중무휴" and json.loads(rows[0]["field_sources"]) == {"tel": NA}
    assert stats["closed_days(해당 없음→TourAPI)"] == 1



def test_a_person_may_give_a_value_without_a_url_but_must_say_how():
    told = {"by": "human", "checked": "2026-10-12", "note": "사용자 확인"}
    assert f.source_errors([_row("1", "12", tel="02-000-0000", field_sources=_sources(tel=told))]) == []
    bare = {"by": "human", "checked": "2026-10-12"}
    claude = {"by": "claude", "checked": "2026-10-12", "quote": "문의 02-000-0000"}
    errors = f.source_errors([_row("2", "12", tel="02-000-0000", field_sources=_sources(tel=bare)),
                              _row("3", "12", tel="02-000-0000", field_sources=_sources(tel=claude))])
    assert any(e.startswith("2 ") and "note" in e for e in errors)
    assert any(e.startswith("3 ") and "url" in e for e in errors)
