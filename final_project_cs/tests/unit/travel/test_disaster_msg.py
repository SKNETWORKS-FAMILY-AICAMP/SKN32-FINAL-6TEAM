# -*- coding: utf-8 -*-
"""긴급재난문자 샘플 판 — 무엇을 이상으로 세고, 무엇을 세지 않는가.

★규칙은 샘플 데이터를 보고 정했다(2026-09-14): 「기타」= 실종자 찾기라 빼고,
  「해제」 문자는 빼고, 샘플 기간 밖은 「없음」이 아니라 「모름」이다.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.infrastructure.travel.base import TravelSources
from app.infrastructure.travel.disaster_msg import DEFAULT_SAMPLE_PATH, KST, DisasterMsgCsv
from app.infrastructure.travel.disruptions import DisruptionCheck

HEADER = "SN,CRT_DT,MSG_CN,RCPTN_RGN_NM,EMRG_STEP_NM,DST_SE_NM,REG_YMD,MDFCN_YMD,RCPTN_RGN_ID,EMRG_STEP_ID,DST_SE_ID\n"
KOREAN = "일련번호,생성일시,메시지내용,수신지역명,긴급단계명,재해구분명,등록일자,수정일자,수신지역ID,긴급단계ID,재해구분ID\n"


def _csv(tmp_path: Path, *rows: str) -> Path:
    path = tmp_path / "sample.csv"
    path.write_text(HEADER + KOREAN + "".join(rows), encoding="utf-8-sig")
    return path


def _row(sn, when, text, region, kind, step="안전안내"):
    return f'{sn},{when},"{text}","{region}",{step},{kind},2023-09-19,2023-09-19,1,1,1\n'


ROWS = (
    _row(1, "2023/09/19 13:30:45", "[서울경찰청] 노원구에서 실종된 ○○○씨를 찾습니다", "서울특별시 노원구 ", "기타"),
    _row(2, "2023/09/19 14:24:55", "[강남구] 언주역 도로 침하로 도로 통제 중",
         "서울특별시 강남구 역삼동,서울특별시 강남구 삼성동", "교통통제"),
    _row(3, "2023/09/19 16:18:39", "[강남구] 봉은사로 차량 통제가 완전 해제되었음을 알려드립니다",
         "서울특별시 강남구 역삼동", "교통통제"),
    _row(4, "2023/09/19 15:00:00", "[서울특별시] 많은 비 예상, 하천변 출입 금지", "서울특별시 전체 ", "호우"),
    _row(5, "2023/09/19 15:10:00", "[부산광역시] 호우경보", "부산광역시 전체 ", "호우"),
    _row(6, "2023/09/19 15:20:00", "[서울특별시] 알 수 없는 구분", "서울특별시 전체 ", "미지정구분"),
)


@pytest.fixture()
def source(tmp_path):
    return DisasterMsgCsv(_csv(tmp_path, *ROWS))


def _at(hour, minute=0):
    return datetime(2023, 9, 19, hour, minute, tzinfo=KST)


# ── 읽기 ────────────────────────────────────────────────────────
def test_the_korean_header_row_is_not_data_and_coverage_is_measured(source):
    assert len(source.rows) == 6
    first, last = source.coverage
    assert first == _at(13, 30).replace(second=45) and last == _at(16, 18).replace(second=39)


def test_a_bad_timestamp_is_counted_not_silently_dropped(tmp_path):
    src = DisasterMsgCsv(_csv(tmp_path, ROWS[1], _row(9, "언젠가", "x", "서울특별시 전체", "호우")))
    assert len(src.rows) == 1 and src.misses["bad_created_at"] == 1


# ── 무엇을 이상으로 세나 ────────────────────────────────────────
def test_missing_person_alerts_are_not_disruptions(source):
    kinds = [m["kind"] for m in source.active(region="서울", at=_at(14, 0))["for_region"]]
    assert "기타" not in kinds


def test_a_road_closure_in_seoul_is_a_disruption_and_its_release_is_not(source):
    result = source.active(region="서울", at=_at(16, 30))
    texts = [m["text"] for m in result["for_region"]]
    assert any("도로 통제 중" in t for t in texts)
    assert not any("해제" in t for t in texts)


def test_other_regions_do_not_leak_into_seoul(source):
    result = source.active(region="서울", at=_at(15, 30))
    assert all(any(r.startswith("서울특별시") for r in m["regions"]) for m in result["for_region"])


def test_a_known_district_narrows_the_match(source):
    """★구를 알면 구로 좁힌다 — 강남 통제로 종로 일정을 바꾸지 않는다. 「전체」는 남는다."""
    result = source.active(region="서울", at=_at(16, 0), district="종로구")
    kinds = [m["kind"] for m in result["for_region"]]
    assert "교통통제" not in kinds and "호우" in kinds


def test_an_unknown_kind_is_kept_visible_not_counted(source):
    result = source.active(region="서울", at=_at(15, 30))
    assert [m["kind"] for m in result["unclassified"]] == ["미지정구분"]
    assert "미지정구분" not in [m["kind"] for m in result["for_region"]]


def test_outside_the_sample_period_is_unknown_not_none(source):
    result = source.active(region="서울", at=datetime(2026, 9, 15, 14, tzinfo=KST))
    assert result["covered"] is False and result["for_region"] == []


# ── 점검에 들어가면 ──────────────────────────────────────────────
def _check(source, *, sensitive, at):
    place = {"place_id": "p", "latitude": None, "longitude": None, "weather_sensitive": sensitive}
    sources = TravelSources(disaster=source)
    return DisruptionCheck(sources, limits=lambda: (60, 30)).check(place=place, starts_at=at)


def _disaster_check(report):
    return next(c for c in report["checks"] if c["category"] == "disaster_msg")


def test_an_indoor_place_ignores_rain_messages_but_not_road_closures(source):
    report = _check(source, sensitive=False, at=_at(16, 0))
    kinds = [d["kind"] for d in report["disruptions"]]
    assert kinds == ["교통통제"] and report["verdict"] == "disrupted"
    assert _disaster_check(report)["mode"] == "sample"


def test_outside_the_sample_period_the_check_says_not_connected(source):
    report = _check(source, sensitive=False, at=datetime(2026, 9, 15, 14, tzinfo=KST))
    check = _disaster_check(report)
    assert check["status"] == "not_connected" and "샘플 기간" in check["reason"]
    assert report["verdict"] == "clear"


def test_without_a_source_the_check_says_why():
    report = DisruptionCheck(TravelSources(unavailable={"disaster": "키 대기"}),
                             limits=lambda: (60, 30)).check(
        place={"weather_sensitive": False}, starts_at=_at(16))
    assert _disaster_check(report) == {"category": "disaster_msg", "status": "not_connected",
                                       "reason": "키 대기"}


# ── 실제 샘플 파일 (있을 때만) ───────────────────────────────────
@pytest.mark.skipif(not DEFAULT_SAMPLE_PATH.exists(), reason="datasets/travel 샘플이 없다")
def test_the_real_sample_file_parses_completely():
    """★2026-09-14 실측: 100건, 2023-09-16 09:45 ~ 09-19 21:08, 읽기 실패 0."""
    src = DisasterMsgCsv(DEFAULT_SAMPLE_PATH)
    assert len(src.rows) == 100 and not src.misses
    assert src.coverage[0].date().isoformat() == "2023-09-16"
    assert src.coverage[1].date().isoformat() == "2023-09-19"
