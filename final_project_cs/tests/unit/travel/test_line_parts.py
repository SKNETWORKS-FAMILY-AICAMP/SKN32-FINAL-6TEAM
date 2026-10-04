# -*- coding: utf-8 -*-
"""한 줄을 뜻의 조각으로 읽는다 — 이름 없는 줄(종류 + 지역만)과 이름 있는 줄을 가른다. `[2026-10-03 ui 세션 요청서 「장소 해석 개선」]`

☆왜: 「성수 예약 식당」 · 「서울역 인근 저녁 식당」 · 「이태원 소품숍」 · 「호텔 조식」은 가게 이름이 없는데 서버가 가게 이름으로 찾았다(실서버 실측). 단어 하나를 고칠 문제가 아니라
「이름 없는 줄」이라는 개념이 빠진 것이어서, 줄을 조각으로 읽는 해석기(`intake/line_parts.py`)와 그 말 표(`config/place_terms.yaml`) · 지명 사전(`intake/areas.py`)을 만들었다.

★지키려는 것
 ①아래 **평가 줄 40개**가 기대한 조각으로 읽힌다(이름 없는 줄 · 종류 · 지역 · 끼니 · 예약 · 이름 있는 줄) — 실서버에서 틀렸던 네 줄이 들어 있다
 ②**새 말은 표에 한 줄을 더하는 것만으로** 같은 길을 탄다(코드 수정 없이 — 임시 표로 확인)
 ③이름 조각이 하나라도 남으면 이름 있는 줄이다(고유 이름을 지어낸 종류로 덮지 않는다) · 지역만 있는 줄은 이름 있는 줄이다(「경복궁 관람」)
 ④지명 사전 — 같은 동의 1가 · 2가를 합치고 짧은 말(성수 · 성동)로도 부르고, 출처 우선순위(허브 > 동 > 구)를 지키고, **중앙값**이라 틀린 좌표 하나에 안 끌려간다

재현:

    python -m pytest tests/unit/travel/test_line_parts.py -v
"""
from __future__ import annotations

import pytest

from app.modules.travel_ops.intake.areas import AreaIndex
from app.modules.travel_ops.intake.line_parts import parse
from app.modules.travel_ops.intake.terms import Terms, category_label, load_terms

#: 실제 지명 사전의 모양을 흉내 낸 작은 사전 — (출처, 이름, 위도, 경도)
ROWS = [
    ("hub", "성수", 37.5449, 127.0512), ("hub", "경복궁", 37.5739, 126.9805), ("hub", "잠실", 37.5102, 127.1054),
    ("hub", "서울역", 37.5569, 126.9749),
    ("dong", "성수동", 37.5440, 127.0560), ("dong", "이촌동", 37.5200, 126.9700), ("dong", "이태원동", 37.5340, 126.9940),
    ("dong", "한남동", 37.5340, 127.0000), ("dong", "연남동", 37.5620, 126.9250), ("dong", "서교동", 37.5550, 126.9230),
    ("district", "성동구", 37.5630, 127.0370), ("district", "강남구", 37.5170, 127.0470),
]
AREAS = AreaIndex.from_rows(ROWS, load_terms())


# 평가 줄 — (제목, 이름 없는 줄인가, 일정 종류, 종류 이름, 지역 이름, 끼니, 근처 말, 말로 적은 예약, 식사 힌트)
#  ★앞 네 줄은 2026-10-03 실서버에서 틀렸던 줄이다.
LINES = [
    ("호텔 조식", True, "dining", "숙소", None, "아침", False, None, False),                    # ★`[2026-10-04]` 식사 일정이지만 장소는 숙소다(식당이 아니다)
    ("성수동 쇼핑", True, "activity", "쇼핑", "성수동", None, False, None, False),
    ("성수 예약 식당", True, "dining", "식당", "성수", None, False, None, False),
    ("서울역 인근 저녁 식당", True, "dining", "식당", "서울역", "저녁", True, None, False),
    # 종류 + 지역
    ("이촌동 점심 식당", True, "dining", "식당", "이촌동", "점심", False, None, False),
    ("이태원 소품숍", True, "activity", "쇼핑", "이태원동", None, False, None, False),
    ("성수동쇼핑", True, "activity", "쇼핑", "성수동", None, False, None, False),            # 붙여 쓴 것도 나눈다
    ("연남동 카페", True, "dining", "카페", "연남동", None, False, None, False),
    ("한남동 브런치", True, "dining", "식당", "한남동", None, False, None, False),
    ("잠실 근처 맛집", True, "dining", "식당", "잠실", None, True, None, False),
    ("경복궁 주변 식당", True, "dining", "식당", "경복궁", None, True, None, False),
    ("성수쪽 카페", True, "dining", "카페", "성수", None, True, None, False),
    ("성동구 맛집", True, "dining", "식당", "성동구", None, False, None, False),
    ("성동 맛집", True, "dining", "식당", "성동구", None, False, None, False),                  # 구 이름의 짧은 말
    ("강남구 쇼핑몰", True, "activity", "쇼핑", "강남구", None, False, None, False),
    ("서울역 호텔", True, "activity", "숙소", "서울역", None, False, None, False),
    ("홍대 카페", True, "dining", "카페", "홍대", None, False, None, False),                    # 표의 별칭(홍대 → 서교동)
    ("성수 한식 맛집", True, "dining", "식당", "성수", None, False, None, False),
    ("서울역 미술관", True, "activity", "문화시설", "서울역", None, False, None, False),
    # 종류 · 끼니만(지역 없음)
    ("점심", True, "dining", "식당", None, "점심", False, None, False),
    ("저녁 식사", True, "dining", "식당", None, "저녁", False, None, False),
    ("식당", True, "dining", "식당", None, None, False, None, False),
    ("쇼핑", True, "activity", "쇼핑", None, None, False, None, False),
    ("호텔", True, "activity", "숙소", None, None, False, None, False),
    ("미술관", True, "activity", "문화시설", None, None, False, None, False),
    # 예약을 글자로 적은 것
    ("예약한 식당", True, "dining", "식당", None, None, False, True, False),
    ("예약없는 성수 카페", True, "dining", "카페", "성수", None, False, False, False),
    # 규칙이 끼니 말을 이미 떼어 식사로 정한 줄 — 끼니 말과 같은 효과
    ("이촌동", True, "dining", "식당", "이촌동", None, False, None, True),
    ("경복궁", True, "dining", "식당", "경복궁", None, False, None, True),
    # ── 이름이 있는 줄(남는 조각이 있다) — 지금처럼 이름으로 찾는다
    ("토속촌삼계탕", False, None, "장소", None, None, False, None, False),
    ("광장시장 빈대떡", False, None, "장소", None, None, False, None, False),
    ("광장시장", False, None, "장소", None, None, False, None, False),
    ("N서울타워", False, None, "장소", None, None, False, None, False),
    ("올리브영", False, None, "장소", None, None, False, None, False),
    ("한강 카약", False, None, "장소", None, None, False, None, False),
    ("할매식당", False, None, "장소", None, None, False, None, False),                         # 「할매」가 남는다 — 가게 이름이다
    ("카페드파리", False, None, "장소", None, None, False, None, False),
    ("성수 서울숲 식당", False, None, "장소", None, None, False, None, False),                # 「서울숲」이 남는다
    # ── 이름은 없지만 읽을 수 없는 줄
    ("경복궁 관람", False, None, "장소", None, None, False, None, False),                      # 지역만(+이름 조각) — 종류 말이 없다
    ("서울역 인근", False, None, "장소", None, None, False, None, False),                      # 지역 + 근처 말뿐 — 종류도 끼니도 없다
    ("성수 식당 쇼핑", False, None, "장소", None, None, False, None, False),                  # 종류 말이 서로 다른 종류를 가리킨다
    ("홍대 쇼핑", True, "activity", "쇼핑", "홍대", None, False, None, False),
]


@pytest.mark.parametrize("line", LINES, ids=[row[0] for row in LINES])
def test_each_evaluation_line_is_read_as_the_expected_parts(line):
    title, nameless, kind, label, area, meal, near, booked, hint = line
    got = parse(title, terms=load_terms(), areas=AREAS, kind_hint="dining" if hint else None)
    assert got.nameless is nameless, (title, got)
    if nameless:
        assert (got.kind, got.label) == (kind, label), (title, got)
        assert (got.area.name if got.area else None) == area, (title, got)
        assert got.meal == meal and got.near is near and got.booked is booked, (title, got)
    else:
        assert got.residue or got.conflict or not (got.category or got.meal), (title, got)


def test_there_are_enough_evaluation_lines_and_the_four_measured_ones_come_first():
    assert len(LINES) >= 30
    assert [row[0] for row in LINES[:4]] == ["호텔 조식", "성수동 쇼핑", "성수 예약 식당", "서울역 인근 저녁 식당"]


def test_a_lodging_word_with_a_meal_word_is_a_meal_in_the_lodging_not_a_restaurant():
    """★`[2026-10-04 사용자 지적 「그거 호텔인데 왜 식당이야?」]` 「호텔 조식」 — 일정은 식사(아침)지만 **장소는 숙소**다. 이름표는 「숙소」, 후보를 거르는 분류는 숙박(32)이다.
    (앞 판은 끼니 말이 이겨 「식당」 · 식당 후보로 읽었고, 자동 추천이 호텔 줄을 식당으로 바꿨다.)"""
    got = parse("호텔 조식", terms=load_terms(), areas=AREAS)
    assert got.kind == "dining" and got.label == "숙소" and got.content_type == "32" and got.lodging_meal and got.meal == "아침"
    assert got.public()["lodging_meal"] is True and got.public()["label"] == "숙소"
    # 규칙이 끼니 말을 떼고 제목만 「호텔」로 남긴 줄(식사 힌트)도 같다 — 화면에서 본 「09:00 호텔」
    hinted = parse("호텔", terms=load_terms(), areas=AREAS, kind_hint="dining")
    assert hinted.kind == "dining" and hinted.label == "숙소" and hinted.lodging_meal and hinted.content_type == "32"
    # 끼니 말이 없으면 숙소는 그냥 활동 줄이다 · 식당 줄은 그대로 식당이다
    plain = parse("호텔", terms=load_terms(), areas=AREAS)
    assert plain.kind == "activity" and plain.label == "숙소" and not plain.lodging_meal and plain.content_type == "32"
    dinner = parse("성수 저녁 식당", terms=load_terms(), areas=AREAS)
    assert dinner.label == "식당" and not dinner.lodging_meal and dinner.content_type == "39"
    shop = parse("성수동 쇼핑", terms=load_terms(), areas=AREAS)
    assert shop.kind == "activity" and shop.content_type == "38"                   # 같은 종류면 그 분류로 거른다


def test_only_a_name_part_left_over_makes_it_a_named_line_and_the_leftover_is_kept():
    got = parse("성수 서울숲 식당", terms=load_terms(), areas=AREAS)
    assert got.residue == ["서울숲"] and not got.nameless
    assert got.area is not None and got.category is not None                       # 나머지 조각은 읽어 두었다(지금은 쓰지 않지만 근거로 남는다)


def test_the_public_shape_carries_what_a_sentence_needs_and_nothing_internal():
    got = parse("서울역 인근 저녁 식당", terms=load_terms(), areas=AREAS)
    public = got.public()
    assert public["label"] == "식당" and public["kind"] == "dining" and public["meal"] == "저녁" and public["near"] is True
    assert set(public["area"]) == {"name", "kind", "latitude", "longitude", "radius_m"} and public["area"]["name"] == "서울역"
    assert public["area"]["radius_m"] == 1500                                       # 허브의 반경(표)


# ── 새 말은 표에 한 줄 ───────────────────────────────────────────────
def test_a_new_word_in_the_table_is_enough_with_no_code_change():
    base = {"categories": [{"label": "식당", "kind": "dining", "content_type": "39", "terms": ["식당"]}]}
    assert not parse("성수 팝업", terms=Terms.from_dict(base), areas=AREAS).nameless           # 「팝업」은 아직 표에 없다 — 이름 조각으로 남는다
    merged = Terms.from_dict({**base, "categories": base["categories"] + [{"label": "쇼핑", "kind": "activity",
                                                                          "content_type": "38", "terms": ["팝업"]}]})
    got = parse("성수 팝업", terms=merged, areas=AREAS)                                         # 표에 한 줄 — 코드는 그대로
    assert got.nameless and got.kind == "activity" and got.content_type == "38" and got.label == "쇼핑"


def test_a_new_area_word_comes_from_data_rows_not_from_code():
    terms = load_terms()
    assert not parse("망원동 카페", terms=terms, areas=AREAS).nameless             # 사전에 없는 동 — 이름 조각으로 남는다
    wider = AreaIndex.from_rows(ROWS + [("dong", "망원동", 37.5560, 126.9060)], terms)
    got = parse("망원동 카페", terms=terms, areas=wider)
    assert got.nameless and got.area.name == "망원동" and parse("망원 카페", terms=terms, areas=wider).area.name == "망원동"


def test_without_a_city_dictionary_only_words_the_table_knows_are_general():
    """지명 사전이 비어도(DB 장애 · 시험) 종류 · 끼니만 있는 줄은 이름 없는 줄이고, 지역 말은 이름 조각이 된다(깨지지 않는다)."""
    assert parse("점심", terms=load_terms(), areas=None).nameless
    assert not parse("성수 식당", terms=load_terms(), areas=None).nameless


# ── 지명 사전 ────────────────────────────────────────────────────────
def test_priority_hub_beats_dong_beats_district_for_the_same_word():
    index = AreaIndex.from_rows([("district", "성수", 1.0, 1.0), ("dong", "성수동", 2.0, 2.0), ("hub", "성수", 3.0, 3.0)], load_terms())
    assert index.get("성수").kind == "hub" and index.get("성수동").kind == "dong"


def test_short_forms_do_not_make_one_letter_words():
    index = AreaIndex.from_rows([("dong", "명동", 37.56, 126.98), ("dong", "성수동", 37.54, 127.05)], load_terms())
    assert index.get("명") is None and index.get("명동") is not None                 # 「명」 한 글자는 지역 말이 아니다
    assert index.get("성수") is not None


def test_an_alias_to_an_area_the_dictionary_lacks_is_ignored_and_never_invented():
    index = AreaIndex.from_rows([("dong", "성수동", 37.54, 127.05)], load_terms())        # 서교동이 없다
    assert index.get("홍대") is None


def test_category_labels_come_from_the_table():
    assert category_label("39") == "음식점" and category_label(38) == "쇼핑" and category_label("999") is None and category_label(None) is None
