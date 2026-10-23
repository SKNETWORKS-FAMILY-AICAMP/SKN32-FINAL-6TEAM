# -*- coding: utf-8 -*-
"""sibling_hours — 쇼핑 지점끼리 운영시간 · 휴무 옮겨 적기와 호출 순서. 네트워크 없이 본다(`[2026-10-16 사용자]`)."""
from __future__ import annotations

import json

from app.domains.travel_ops.components.places.place_info import official_web_note
from app.domains.travel_ops.instances.activity.data_processing import fill_tourapi_details as f
from app.domains.travel_ops.instances.activity.data_processing import sibling_hours as s


def _row(cid, title, hours="", closed="", brand="", ctype="38", sources=None):
    base = {c: "" for c in f.COLUMNS}
    return {**base, "contentid": cid, "contenttypeid": ctype, "title": title, "addr1": "서울특별시 송파구",
            "business_hours": hours, "closed_days": closed, "brand": brand,
            "field_sources": json.dumps(sources, ensure_ascii=False) if sources else ""}


def _propagate(rows, checked="2026-10-16"):
    return s.propagate(rows, checked, f.read_sources, f.write_sources)


def test_venue_comes_before_brand_and_brand_is_never_guessed_from_the_title():
    assert s.venue_of("나이키 롯데백화점 잠실점") == "롯데백화점잠실"
    assert s.venue_of("올리브영 NC신구로점") == "NC신구로"
    assert s.venue_of("NCT 굿즈샵") is None                                  # 「NC」 가 영문 단어 안에 있으면 매장이 아니다
    assert s.group_of(_row("1", "나이키 롯데백화점 잠실점", brand="나이키")) == "venue:롯데백화점잠실"
    assert s.group_of(_row("1", "나이키 강남점", brand="나이키")) == "brand:나이키"
    assert s.group_of(_row("1", "나이키 강남점")) is None                    # brand 칸이 비면 묶지 않는다
    assert s.group_of(_row("1", "롯데백화점 잠실점 전시", ctype="14")) is None  # 쇼핑만


def test_venue_copies_the_two_thirds_majority_as_the_original_text_with_its_basis():
    rows = [_row("1", "A 롯데백화점 잠실점", "10:30~20:00", "명절"),
            _row("2", "B 롯데백화점 잠실점", "10:30-20:00", "명절"),             # 「-」/「~」 차이는 같은 값
            _row("3", "C 롯데백화점 잠실점", "10:00~22:00", "명절"),
            _row("4", "D 롯데백화점 잠실점"),
            _row("x1", "E 롯데백화점 잠실점", brand="올리브영")]                  # 브랜드 행도 채운다
    stats = _propagate(rows)
    assert stats["business_hours 옮김(venue)"] == 2 and stats["closed_days 옮김(venue)"] == 2
    assert rows[3]["business_hours"] in ("10:30~20:00", "10:30-20:00") and rows[3]["closed_days"] == "명절"
    assert f.read_sources(rows[3])["business_hours"] == {"by": "sibling", "group": "venue:롯데백화점잠실",
                                                         "basis": ["1", "2"], "checked": "2026-10-16"}
    assert f.read_sources(rows[3])["closed_days"]["basis"] == ["1", "2", "3"]
    assert f.source_errors(rows) == []


def test_brand_needs_ninety_percent_and_at_least_three_basis():
    two_of_three = [_row("1", "나이키 강남점", "10:30~22:00", brand="나이키"),
                    _row("2", "나이키 홍대점", "10:30~22:00", brand="나이키"),
                    _row("3", "나이키 명동점", "11:00~21:00", brand="나이키"),
                    _row("4", "나이키 신촌점", brand="나이키")]
    assert not _propagate(two_of_three) and two_of_three[3]["business_hours"] == ""
    only_two = [_row("1", "다이소 A점", "10:00~22:00", brand="다이소"), _row("2", "다이소 B점", "10:00~22:00", brand="다이소"),
                _row("3", "다이소 C점", brand="다이소")]
    assert not _propagate(only_two)
    many = [_row(str(i), f"다이소 {i}점", "10:00~22:00", brand="다이소") for i in range(1, 10)]
    many += [_row("10", "다이소 10점", "10:30~21:00", brand="다이소"), _row("11", "다이소 11점", brand="다이소")]
    assert _propagate(many)["business_hours 옮김(brand)"] == 1               # 10곳 중 9곳 = 90%
    assert many[-1]["business_hours"] == "10:00~22:00"


def test_people_values_na_marks_and_tourapi_values_are_left_alone_and_copies_are_not_basis():
    human = {"business_hours": {"by": "human", "checked": "2026-10-15", "note": "전화 확인"}}
    na = {"business_hours": {"by": "human", "na": True, "checked": "2026-10-15"}}
    rows = [_row("1", "A NC신구로점", "10:30~21:00"), _row("2", "B NC신구로점", "10:30~21:00"),
            _row("3", "C NC신구로점", "09:00~23:00", sources=human),            # 사람 값 — 근거도 아니고 덮지도 않는다
            _row("4", "D NC신구로점", sources=na),
            _row("5", "E NC신구로점", "11:00~20:00")]                           # TourAPI 값 — 덮지 않는다
    assert not _propagate(rows)                                               # 근거 3곳(1 · 2 · 5) 중 2곳 → 옮길 곳이 없다
    assert rows[2]["business_hours"] == "09:00~23:00" and rows[3]["business_hours"] == ""
    rows.append(_row("6", "F NC신구로점"))
    _propagate(rows)
    rows.append(_row("7", "G NC신구로점"))
    _propagate(rows)
    assert f.read_sources(rows[6])["business_hours"]["basis"] == ["1", "2"]   # 옮긴 6번은 근거가 되지 않는다


def test_rerun_is_stable_and_a_copy_is_withdrawn_when_the_basis_stops_agreeing():
    rows = [_row("1", "A IFC몰점", "10:00~22:00"), _row("2", "B IFC몰점", "10:00~22:00"),
            _row("3", "C IFC몰점", "10:00~22:00"), _row("4", "D IFC몰점")]
    _propagate(rows, "2026-10-16")
    assert not _propagate(rows, "2026-10-20")                                 # 그대로면 확인한 날도 안 바꾼다
    assert f.read_sources(rows[3])["business_hours"]["checked"] == "2026-10-16"
    rows[1]["business_hours"], rows[2]["business_hours"] = "11:00~21:00", "10:30~20:00"
    assert _propagate(rows)["business_hours 거둠"] == 1
    assert rows[3]["business_hours"] == "" and rows[3]["field_sources"] == ""


def test_a_tourapi_answer_replaces_the_copied_value_and_its_source():
    sources = {"business_hours": {"by": "sibling", "group": "venue:IFC몰", "basis": ["1"], "checked": "2026-10-16"}}
    row = _row("4", "D IFC몰점", "10:00~22:00", sources=sources)
    stats = f.apply_cache([row], {("4", "detailIntro2"): {"opentime": "10:30~22:00"}})
    assert row["business_hours"] == "10:30~22:00" and row["field_sources"] == ""
    assert stats["business_hours(사람 값→TourAPI)"] == 1


def test_sibling_source_format_is_checked():
    good = {"by": "sibling", "group": "brand:다이소", "basis": ["1", "2", "3"], "checked": "2026-10-16"}
    assert f.source_errors([_row("1", "다이소", "10:00~22:00", sources={"business_hours": good})]) == []
    bad = [_row("1", "다이소", sources={"tel": good}),
           _row("2", "다이소", "10:00~22:00", sources={"business_hours": {**good, "basis": ["x1"]}}),
           _row("3", "다이소", "10:00~22:00", sources={"business_hours": {**good, "group": "다이소"}}),
           _row("4", "다이소", "10:00~22:00", sources={"business_hours": {**good, "url": "https://a"}})]
    bad[0]["tel"] = "02"
    errors = f.source_errors(bad)
    assert any(e.startswith("1 ") for e in errors) and any(e.startswith("2 ") for e in errors)
    assert any(e.startswith("3 ") for e in errors) and any(e.startswith("4 ") for e in errors)


def test_call_order_puts_samples_first_and_settled_groups_last():
    rows = [_row(str(i), f"X{i} NC신구로점") for i in range(10, 15)]           # 아직 아무도 안 받은 매장
    rows += [_row("20", "혼자 가게", brand="혼자")]
    rows += [_row(str(i), f"Y{i} IFC몰점", "10:00~22:00", "명절") for i in (30, 31, 32)] + [_row("33", "Y33 IFC몰점")]
    order = s.call_order(rows, rows, fetched={"30", "31", "32"}, read_sources=f.read_sources)
    assert [order[str(i)] for i in range(10, 15)] == [0, 0, 0, 2, 2]          # 작은 id 3곳이 표본
    assert order["20"] == 1 and order["33"] == 3                              # 혼자 · 이미 정해진 묶음
    assert [r["contentid"] for r in f.targets(rows, order)][:3] == ["10", "11", "12"]


def test_intro_only_asks_one_operation_per_place():
    row = _row("1", "A")
    assert f.operations_for(row) == f.BOTH_OPERATIONS
    assert f.operations_for(row, intro_only=True) == ("detailIntro2",)
    assert f.operations_for(_row("x1", "A"), intro_only=True) == ()


def test_screen_note_says_copied_values_are_estimates_not_checked_pages():
    read = {"source": "official_web", "field_sources": {
        "business_hours": {"by": "sibling", "group": "venue:IFC몰", "basis": ["1"], "checked": "2026-10-16"},
        "closed_days": {"by": "human", "url": "https://a", "checked": "2026-10-15"}}}
    note, evidence = official_web_note(read)
    assert note == "휴무일: 공식 페이지(2026-10-15 확인) · 운영시간: 같은 매장 다른 지점 값(추정)"
    assert [e["by"] for e in evidence] == ["sibling", "human"]
