# -*- coding: utf-8 -*-
"""읽기 단계(`read_source`)가 이름 없는 줄(종류 + 지역만)을 **가게로 찾지 않고** 뜻의 조각 · 예약 · 종류를 값 줄로 남긴다. `[2026-10-03 ui 세션 요청서 「장소 해석 개선」]`

DB 없이 도는 단위 시험 — 같은 일을 DB · 실제 접수 흐름으로 보는 것은 `tests/e2e/test_intake_nameless_lines.py`.

★지키려는 것: ①이름 없는 줄은 관광공사 · 카카오에 **그 문구를 묻지 않는다** ②장소 값은 비고(`None`) 근거에 조각(`parts`)과 예약이 남는다 ③일정 종류 줄이 식사 · 활동으로 정해진다(규칙이 이미 정한 종류는 덮지 않는다)
④고객이 앞서 이 글을 다른 이름으로 고친 적이 있으면(별칭) **옛 길(그 이름으로 다시 찾기)이 먼저** ⑤진행 알림의 「장소 n/m」에 이름 없는 줄도 센다 ⑥지명 사전이 없어도(None) 읽기는 안 깨진다.

재현:

    python -m pytest tests/unit/travel/test_intake_nameless_read.py -v
"""
from __future__ import annotations

from datetime import date

from app.domains.travel_ops.components.intake.areas import AreaIndex
from app.domains.travel_ops.components.intake.pipeline import read_source
from app.domains.travel_ops.components.intake.places import normalize
from app.domains.travel_ops.components.intake.terms import load_terms

AREAS = AreaIndex.from_rows([("hub", "성수", 37.5449, 127.0512), ("hub", "서울역", 37.5569, 126.9749)], load_terms())
TODAY = date(2026, 10, 3)


class _Tour:
    PLACES = {"경복궁": ("126508", "12", 37.5796, 126.9770), "엘 샌드위치": ("777", "39", 37.5450, 127.0510)}

    def __init__(self):
        self.asked: list[str] = []
        self.misses: dict = {}

    def find(self, name, area_code=None):
        self.asked.append(name)
        if name not in self.PLACES:
            return None
        cid, ctype, lat, lon = self.PLACES[name]
        return {"matched_title": name, "content_id": cid, "content_type_id": ctype, "latitude": lat, "longitude": lon,
                "address": "서울특별시 성동구"}


class _Kakao:
    def __init__(self):
        self.asked: list = []
        self.misses: dict = {}

    def search(self, query, size=5, near=None):
        self.asked.append(query)
        return []


def _rows(text, **options):
    tour, kakao = _Tour(), _Kakao()
    options.setdefault("areas", AREAS)
    rows = read_source(text, tour=tour, kakao=kakao, our_places=[], today=TODAY, **options)
    return rows, tour, kakao


def _field(rows, name):
    return next((r for r in rows if r["field"] == name), None)


def test_a_nameless_line_is_not_looked_up_and_keeps_the_parts_and_the_booking_as_evidence():
    rows, tour, kakao = _rows("2026-10-15\n13:00 성수 예약 식당 · 예약 있음")
    assert tour.asked == [] and kakao.asked == []                                      # ★그 문구를 바깥에 묻지 않았다
    place = _field(rows, "items[0].place")
    assert place["value"] is None and place["needs_review"] is True and place["method"] == "lookup"
    evidence = place["evidence"]
    assert evidence["method"] == "nameless" and evidence["booked"] is True and evidence["line"] == 2
    assert evidence["parts"]["label"] == "식당" and evidence["parts"]["area"]["name"] == "성수" and evidence["parts"]["area"]["radius_m"] == 1500
    kind = _field(rows, "items[0].kind")
    assert kind["value"] == "dining" and kind["evidence"]["rule"] == "line_parts"


def test_a_word_in_the_line_can_say_booked_and_a_missing_word_stays_unknown():
    said, _, _ = _rows("2026-10-15\n13:00 예약한 성수 식당")
    assert _field(said, "items[0].place")["evidence"]["booked"] is True                # 줄 글자의 「예약한」
    silent, _, _ = _rows("2026-10-15\n13:00 성수 식당")
    assert _field(silent, "items[0].place")["evidence"]["booked"] is None              # 말이 없으면 모른다 — 예약 안 했다고 적지 않는다
    refused, _, _ = _rows("2026-10-15\n13:00 성수 식당 · 예약 없음")
    assert _field(refused, "items[0].place")["evidence"]["booked"] is False


def test_the_kind_the_rules_already_decided_is_not_overwritten_and_an_activity_line_gets_its_kind():
    meal, _, _ = _rows("2026-10-15\n13:00 성수 식당 점심")                                 # 규칙이 끼니 말을 떼고 dining 을 정했다
    kinds = [r for r in meal if r["field"] == "items[0].kind"]
    assert len(kinds) == 1 and kinds[0]["evidence"]["source"] == "text"                # 규칙의 줄 하나뿐 — 덮지 않았다
    shop, _, _ = _rows("2026-10-15\n11:00 성수 쇼핑")
    assert _field(shop, "items[0].kind")["value"] == "activity"
    assert _field(shop, "items[0].place")["evidence"]["parts"]["content_type"] == "38"


def test_a_line_with_a_name_still_goes_the_old_way():
    rows, tour, _ = _rows("2026-10-15\n10:00 경복궁 관람\n13:00 성수 식당")
    assert "경복궁 관람" in tour.asked and _field(rows, "items[0].place")["value"]["name"] == "경복궁"
    assert _field(rows, "items[0].place")["evidence"].get("method") != "nameless"
    assert _field(rows, "items[1].place")["evidence"]["method"] == "nameless"


def test_a_name_the_customer_gave_before_wins_over_the_nameless_reading():
    """고객이 「성수 식당」을 앞서 「엘 샌드위치」로 고쳤다 — 그 별칭(그 고객의 것)으로 다시 찾는다."""
    rows, tour, _ = _rows("2026-10-15\n13:00 성수 식당", aliases={normalize("성수 식당"): "엘 샌드위치"})
    assert _field(rows, "items[0].place")["value"]["name"] == "엘 샌드위치" and "엘 샌드위치" in tour.asked


def test_progress_counts_nameless_lines_in_the_place_counter():
    seen: list[tuple] = []
    _rows("2026-10-15\n10:00 경복궁\n13:00 성수 식당\n18:00 서울역 인근 저녁 식당",
          on_progress=lambda phase, done, total, index, title: seen.append((phase, done, total, index, title)))
    assert [(d, t) for _, d, t, _, _ in seen] == [(1, 3), (2, 3), (3, 3)]
    assert {title for *_, title in seen} == {"경복궁", "성수 식당", "서울역 인근 저녁 식당"}


def test_without_a_dictionary_only_kind_and_meal_lines_are_nameless():
    rows, tour, _ = _rows("2026-10-15\n13:00 점심\n18:00 성수 식당", areas=None)
    assert _field(rows, "items[0].place")["evidence"]["method"] == "nameless"
    assert _field(rows, "items[1].place")["evidence"].get("method") != "nameless"      # 사전이 없어 「성수」는 이름 조각이다 — 옛 길
    assert "성수 식당" in tour.asked
