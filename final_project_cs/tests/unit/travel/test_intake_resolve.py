# -*- coding: utf-8 -*-
"""계획 읽기 2주차 — 날짜 해석 · 장소 찾기 · 모델 인용 검사. `[2026-09-27]` 설계서 §3-4 · §3-5 · §4

★값은 원문과 조회가 낸다 — 모델은 위치만 가리킨다. 원문에 글자 그대로 없는 인용은 들어오지 못한다.
★날짜를 지어내지 않는다 — 어디에도 없으면 첫날 하나만 묻는다.
★카카오는 원문 전체로만 — 좁힌 이름(「한강 카약」 → 「한강」)으로 강 자체를 고르지 않는다.
"""
from __future__ import annotations

from datetime import date

from app.modules.travel_ops.intake.dates import resolve_dates
from app.modules.travel_ops.intake.llm_spans import label_lines
from app.modules.travel_ops.intake.places import jamo, narrowings, normalize, resolve

TODAY = date(2026, 9, 27)


# ── 날짜 ─────────────────────────────────────────────────────────
def test_a_written_date_wins_and_day_offsets_follow_it():
    items = [{"day": 1, "date": "2026-10-15", "line": 2}, {"day": 2, "date": None, "line": 5}]
    dated, ask = resolve_dates(items, today=TODAY)
    assert [(d.value, d.how, d.needs_review) for d in dated] == [
        ("2026-10-15", "written", False), ("2026-10-16", "day_offset", False)]
    assert ask is False


def test_a_date_without_a_year_is_the_coming_one_and_asks_for_review():
    dated, _ = resolve_dates([{"day": 1, "date": "--10-15", "line": 1}], today=TODAY)
    assert (dated[0].value, dated[0].how, dated[0].needs_review) == ("2026-10-15", "year_filled", True)
    past, _ = resolve_dates([{"day": 1, "date": "--03-01", "line": 1}], today=TODAY)
    assert past[0].value == "2027-03-01"                       # 지난 날이면 다음 해


def test_the_first_day_is_worked_back_from_a_later_written_date():
    items = [{"day": 1, "date": None, "line": 1}, {"day": 2, "date": "2026-10-16", "line": 4}]
    dated, _ = resolve_dates(items, today=TODAY)
    assert [d.value for d in dated] == ["2026-10-15", "2026-10-16"]


def test_relative_words_are_counted_from_today():
    dated, ask = resolve_dates([{"day": None, "date": None, "line": 1}], today=TODAY, lines=["내일 3시 남산타워"])
    assert (dated[0].value, dated[0].how) == ("2026-09-28", "relative") and ask is False


def test_a_departure_given_by_the_web_is_the_first_day():
    dated, ask = resolve_dates([{"day": 2, "date": None, "line": 1}], today=TODAY, departure=date(2026, 11, 1))
    assert dated[0].value == "2026-11-02" and ask is False


def test_nothing_known_asks_for_the_first_day_instead_of_inventing_one():
    dated, ask = resolve_dates([{"day": 1, "date": None, "line": 1}], today=TODAY, lines=["09:00 경복궁"])
    assert (dated[0].value, dated[0].how) == (None, "unknown") and ask is True


# ── 모델 인용 ────────────────────────────────────────────────────
class Chat:
    def __init__(self, spans):
        self.spans, self.asked = spans, None

    def json(self, system, user):
        self.asked = user
        return {"spans": self.spans}


def test_only_quotes_found_verbatim_in_the_line_are_kept():
    lines = ["09:00 경복궁", "점심은 토속촌에서 먹을래"]
    chat = Chat([{"line": 2, "quote": "토속툰", "role": "place"},        # 바꿔 적음 — 버린다
                 {"line": 2, "quote": "토속촌", "role": "place"},
                 {"line": 2, "quote": "점심", "role": "meal"},
                 {"line": 1, "quote": "경복궁", "role": "place"},        # 남은 줄이 아니다 — 버린다
                 {"line": 2, "quote": "먹을래", "role": "verdict"}])      # 모르는 역할 — 버린다
    claims, items, report = label_lines(lines, [2], chat)
    assert chat.asked == "2: 점심은 토속촌에서 먹을래"                     # ★읽은 줄은 보내지 않는다
    assert [(i.line, i.title.text, i.meal) for i in items] == [(2, "토속촌", "lunch")]
    assert (report["accepted"], len(report["rejected"])) == (2, 3)
    assert claims == []


def test_a_time_comes_from_rereading_the_quote_not_from_the_model():
    lines = ["내일 오후 3시 반에 남산타워 가자"]
    chat = Chat([{"line": 1, "quote": "오후 3시 반", "role": "time"},
                 {"line": 1, "quote": "남산타워", "role": "place"}])
    claims, items, _ = label_lines(lines, [1], chat)
    assert [c.value for c in claims] == ["15:30"] and items[0].start == "15:30"
    assert claims[0].method == "llm_span" and lines[0][claims[0].span.start:claims[0].span.end] == "오후 3시 반"


def test_a_plan_request_is_flagged():
    _, items, report = label_lines(["서울 3일 일정 짜 줘"], [1], Chat([{"line": 1, "quote": "일정 짜 줘",
                                                                   "role": "plan_request"}]))
    assert report["plan_request"] is True and items == []


# ── 장소 ─────────────────────────────────────────────────────────
OURS = [{"place_id": "p1", "name": "경복궁", "kind": "activity", "latitude": 37.5796, "longitude": 126.977},
        {"place_id": "p2", "name": "북촌한옥마을", "kind": "activity", "latitude": 37.5826, "longitude": 126.983}]


class Tour:
    def __init__(self, known):
        self.known, self.asked = known, []

    def find(self, name, area_code=None):
        self.asked.append((name, area_code))
        if name not in self.known:
            return None
        return {"matched_title": name, "content_id": "c-" + name, "content_type_id": self.known[name],
                "latitude": 37.5, "longitude": 127.0, "address": "서울특별시 중구"}


class Kakao:
    def __init__(self, hits):
        self.hits, self.asked = hits, []

    def search(self, query, size=5):
        self.asked.append(query)
        return self.hits.get(query, [])


def _hit(name, group=""):
    return {"id": "k", "name": name, "category": "", "category_group": group, "address": "서울 중구",
            "latitude": 37.56, "longitude": 126.99}


def test_normalize_and_narrowing():
    assert normalize("토속촌삼계탕 본점") == normalize("토속촌 삼계탕") == "토속촌삼계탕"
    assert narrowings("광장시장 빈대떡 먹기") == ["광장시장 빈대떡 먹기", "광장시장 빈대떡", "광장시장"]
    assert jamo("각") == "각" and jamo("A") == "A"          # 「각」 → 초성·중성·종성


def test_our_own_place_first_and_a_narrowed_name_asks_for_review():
    found = resolve("경복궁", our_places=OURS)
    assert (found.status, found.method, found.place_id, found.needs_review) == ("resolved", "places", "p1", False)
    narrowed = resolve("경복궁 야간개장", our_places=OURS)
    assert (narrowed.name, narrowed.needs_review) == ("경복궁", True)


def test_a_typo_is_fixed_against_our_names_and_marked():
    found = resolve("북촌한옥마울", our_places=OURS)
    assert (found.method, found.name, found.needs_review) == ("typo", "북촌한옥마을", True)


def test_tour_api_is_asked_for_seoul_only():
    tour = Tour({"N서울타워": "12"})
    found = resolve("N서울타워", our_places=[], tour=tour)
    assert (found.method, found.content_id) == ("tour_api", "c-N서울타워")
    assert {area for _, area in tour.asked} == {"1"}


def test_kakao_finds_the_name_and_tour_api_confirms_it():
    tour, kakao = Tour({"토속촌삼계탕": "39"}), Kakao({"토속촌": [_hit("토속촌삼계탕", "FD6")]})
    found = resolve("토속촌", our_places=[], tour=tour, kakao=kakao)
    assert (found.method, found.name, found.kind, found.needs_review) == ("tour_api", "토속촌삼계탕", "dining", True)


def test_kakao_values_go_on_the_item_only_when_tour_api_does_not_know():
    kakao = Kakao({"을지로 노가리골목": [_hit("을지로 노가리골목")]})
    found = resolve("을지로 노가리골목", our_places=[], tour=Tour({}), kakao=kakao)
    assert (found.method, found.evidence()["source"], found.needs_review) == ("kakao", "kakao", False)


def test_kakao_never_picks_a_shop_whose_name_is_not_in_the_text():
    kakao = Kakao({"명동 칼국수": [_hit("명동교자 본점", "FD6")]})
    found = resolve("명동 칼국수", our_places=[], tour=Tour({}), kakao=kakao)
    assert found.status == "unresolved" and found.needs_review


def test_kakao_is_asked_with_the_whole_text_only():
    """☆실측(2026-09-27): 「한강 카약」을 「한강」으로 좁혀 카카오가 강 자체를 골랐다."""
    kakao = Kakao({"한강": [_hit("한강")]})
    found = resolve("한강 카약", our_places=[], tour=Tour({}), kakao=kakao)
    assert kakao.asked == ["한강 카약"] and found.status == "unresolved"


def test_a_romanized_name_is_accepted_only_when_tour_api_confirms_the_korean_name():
    """☆실측(2026-09-27): 「Gyeongbokgung」의 카카오 1~5위가 전부 식당 체인 「경복궁 ○○점」이었다."""
    chain = [_hit("경복궁 관훈점", "FD6"), _hit("경복궁 방이점", "FD6")]
    found = resolve("Gyeongbokgung", our_places=[], tour=Tour({"경복궁": "12"}),
                    kakao=Kakao({"Gyeongbokgung": chain}))
    assert (found.method, found.name, found.kind, found.needs_review) == ("tour_api", "경복궁", "activity", True)
    # 관광공사가 확인하지 못하면 식당 체인을 고르지 않는다
    none = resolve("Gyeongbokgung", our_places=[], tour=Tour({}), kakao=Kakao({"Gyeongbokgung": chain}))
    assert none.status == "unresolved"


class Refusing(Tour):
    """관광공사 흉내 — 속도 제한에 걸린다(`TravelSource._allow` 가 세는 모양 그대로)."""

    def __init__(self):
        super().__init__({})
        self.misses = {}

    def find(self, name, area_code=None):
        self.misses["rate_limited"] = self.misses.get("rate_limited", 0) + 1
        return None


def test_a_refused_lookup_is_not_reported_as_a_missing_place():
    """☆실측(2026-09-27): 11번째 관광공사 호출이 속도 제한에 걸렸는데 「정하지 못했다」로만 남았다."""
    found = resolve("광장시장", our_places=[], tour=Refusing())
    assert found.status == "unresolved" and found.blocked == ["tour_api:rate_limited"]
    assert "없는 곳이라는 뜻이 아니다" in found.note and found.evidence()["blocked"] == ["tour_api:rate_limited"]
    plain = resolve("광장시장", our_places=[], tour=Tour({}))
    assert plain.blocked == [] and "막혀" not in plain.note


def test_kakao_that_could_not_be_called_is_named():
    class Down(Kakao):
        misses = {"budget_exhausted": 1}

        def search(self, query, size=5):
            return None

    found = resolve("을지로 노가리골목", our_places=[], tour=Tour({}), kakao=Down({}))
    assert found.blocked == ["kakao:budget_exhausted"]
