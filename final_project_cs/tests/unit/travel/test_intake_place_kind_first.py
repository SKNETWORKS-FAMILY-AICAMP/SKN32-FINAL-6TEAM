# -*- coding: utf-8 -*-
"""장소를 찾기 전에 종류(숙소 · 식사 · 활동 · 이동)와 가리키는 곳을 정한다 — 2026-10-19 세 환경 계획서 진단의 회귀 시험.

근거: wiki/records/reports/2026-10-19_chat-intake-secretary-review.md 「2. 장소를 엉뚱한 곳·엉뚱한 종류로 붙인다」
    · 「호텔」 · 「호텔 조식」 · 경복궁스테이 · 노스텔지어 더블재 · 트레블로지가 「식사」(식당)로 들어갔다
    · 「택시로 이동」을 장소로 읽어 회사 본사를 붙였다 · 「공항철도 타고 인천공항」을 장소로 찾았다
    · 창덕궁 → 서울 운현궁 · 국립중앙박물관 → 서울아프리카페스티벌 · 국립민속박물관 → 오촌댁 · 명동 롯데호텔 서울 → 「명동」
    · 광장시장 → 삼모녀꼬마김밥(한 가게, 24회) · 인사동 → 매듭공방
    · 숙소 대체 후보로 서울 호텔 대신 268km 떨어진 광주 호텔
    · 운영시간 「모름」 상위 N서울타워 · 광장시장 · 창덕궁 · 청계천
가짜 자료(관광공사 · 카카오 · 요식 원장)는 그 사고가 난 모양 그대로 답한다 — 고친 코드가 그 답을 **버리는지** 본다.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import candidates
from app.domains.travel_ops.components.intake.hours import facts_for
from app.domains.travel_ops.components.intake.landmarks import find_landmark, is_lodging_text, read_move
from app.domains.travel_ops.components.intake.pipeline import _place_kind_hint
from app.domains.travel_ops.components.intake.places import resolve
from app.domains.travel_ops.components.team_hooks import lodging_alternatives

KST = ZoneInfo("Asia/Seoul")
GWANGHWAMUN = (37.5759, 126.9768)
MARKET = (37.5700, 126.9996)


# ── 가짜 자료 ────────────────────────────────────────────────────────
class Tour:
    """관광공사 자리 — `answers` 의 이름이면 그 값을 낸다(사고가 난 모양: 다른 곳의 이름을 낸다)."""

    def __init__(self, answers=None):
        self.answers, self.asked, self.misses = answers or {}, [], {}

    def find(self, name, area_code=None, **_):
        self.asked.append(name)
        got = self.answers.get(name)
        if got is None:
            return None
        title, (lat, lon), kind = got
        return {"matched_title": title, "content_id": "c-" + title, "content_type_id": kind,
                "latitude": lat, "longitude": lon, "address": "서울특별시 종로구"}


class Kakao:
    def __init__(self, hits=None):
        self.hits, self.asked, self.misses = hits or {}, [], {}

    def search(self, query, size=5, near=None, **kw):
        self.asked.append((query, near))
        return list(self.hits.get(query, []))


class Ledger:
    """요식 원장 — 이름으로 찾으면 **같은 이름 식당**(인허가 자료)을 낸다. 시장 근처 식당 하나도 낸다."""

    def __init__(self, shops=None, near_shop=None):
        self.shops, self.near_shop, self.asked, self.meal_asked, self.misses = shops or {}, near_shop, [], [], {}

    def find(self, name, **_):
        self.asked.append(name)
        return self.shops.get(name)

    def find_dish_near(self, text, latitude, longitude):
        self.meal_asked.append(("dish", text))
        return self.near_shop

    def find_meal_near(self, latitude, longitude):
        self.meal_asked.append(("meal", latitude, longitude))
        return self.near_shop


def _hit(name, at=GWANGHWAMUN, group="", category=""):
    return {"id": name, "name": name, "category": category, "category_group": group, "address": "서울 종로구",
            "latitude": at[0], "longitude": at[1]}


def _shop(name, at=GWANGHWAMUN, license=True):
    return {"matched_title": name, "content_id": None, "content_type_id": "39", "latitude": at[0], "longitude": at[1],
            "address": "서울특별시 종로구", "dining_place_uid": "uid-" + name, "license": license}


# ── 1. 숙소는 숙소 자료에서만 ───────────────────────────────────────────
@pytest.mark.parametrize("title", ["경복궁스테이", "노스텔지어 더블재", "트레블로지 명동"])
def test_a_hotel_is_never_resolved_to_a_same_named_restaurant(title):
    """☆경복궁스테이 · 노스텔지어 더블재 · 트레블로지가 요식 원장(인허가)의 같은 이름 식당이 돼 「식사」가 됐다."""
    ledger = Ledger({title: _shop(title)})
    kakao = Kakao({title: [_hit(title, group="FD6", category="음식점 > 한식")]})
    found = resolve(title, our_places=[], tour=Tour(), kakao=kakao, dining=ledger, kind_hint="lodging")
    assert found.kind != "dining" and found.method not in ("dining_ledger", "dining_license")
    assert ledger.asked == []                                       # 원장을 아예 묻지 않는다
    assert found.status == "unresolved"                            # 숙박 분류 결과가 없으면 정하지 않는다(식당으로 바꾸지 않는다)


def test_a_hotel_found_on_the_map_as_lodging_is_taken_as_a_stay():
    kakao = Kakao({"경복궁스테이": [_hit("경복궁스테이", group="FD6"), _hit("경복궁스테이", group="AD5", category="여행 > 숙박 > 게스트하우스")]})
    found = resolve("경복궁스테이", our_places=[], tour=Tour(), kakao=kakao, dining=Ledger({"경복궁스테이": _shop("경복궁스테이")}))
    assert (found.status, found.name, found.content_type_id, found.kind) == ("resolved", "경복궁스테이", "32", "activity")


def test_lodging_words_alone_decide_the_kind_before_lookup():
    """숙소 말은 원문 글자로 확인한다 — 「○○스테이」 · 「호텔」 · 상표(트레블로지) · 체크인. 「경복궁」만으로는 숙소가 아니다."""
    assert all(is_lodging_text(t) for t in ["경복궁스테이", "호텔 조식", "트레블로지 명동", "노스텔지어 더블재 체크인", "롯데호텔 서울"])
    assert not any(is_lodging_text(t) for t in ["경복궁", "광장시장 점심", "N서울타워", "스테이크 하우스 저녁"])


def test_the_kind_hint_puts_lodging_first_even_with_a_meal_word_and_reads_the_original_title():
    """체크인 말은 찾을 말에서 떼므로(「노스텔지어 더블재」) 종류는 원문 제목으로 본다. 에이전트가 숙소라고 읽은 항목도 숙소다."""
    assert _place_kind_hint({"title": "노스텔지어 더블재 체크인", "meal": False}) == "lodging"
    assert _place_kind_hint({"title": "호텔 조식", "meal": True}) == "lodging"
    assert _place_kind_hint({"title": "노스텔지어 더블재", "meal": False, "lodging": True}) == "lodging"
    assert _place_kind_hint({"title": "토속촌삼계탕", "meal": True}) == "dining"
    # 줄 전체(「체크인 후 경복궁 산책」)는 보지 않는다 — 경복궁까지 숙소가 되면 안 된다
    assert _place_kind_hint({"title": "경복궁", "meal": False, "segment": {"text": "체크인 후 경복궁 산책"}}) == "activity"


def test_myeongdong_lotte_hotel_seoul_is_the_hotel_not_myeongdong():
    """☆「명동 롯데호텔 서울」 → 뒤 단어를 떼어 가며 찾다가 「명동」이 됐다."""
    tour = Tour({"명동": ("명동", (37.5636, 126.9850), "12")})
    kakao = Kakao({"롯데호텔 서울": [_hit("롯데호텔 서울", (37.5653, 126.9810), "AD5", "여행 > 숙박 > 호텔")]})
    found = resolve("명동 롯데호텔 서울", our_places=[], tour=tour, kakao=kakao, dining=Ledger())
    assert (found.status, found.name, found.content_type_id) == ("resolved", "롯데호텔 서울", "32")
    assert "명동" not in tour.asked


# ── 2. 이동 말은 장소가 아니다 ─────────────────────────────────────────
@pytest.mark.parametrize("title, mode, dest", [
    ("택시로 이동", "택시", None), ("지하철 타고", "지하철", None), ("택시", "택시", None),
    ("공항철도 타고 인천공항", "공항철도", "인천공항"), ("택시로 김포공항", "택시", "김포공항"), ("버스 타고 서울역", "버스", "서울역"),
])
def test_move_phrases_are_moves_not_places(title, mode, dest):
    move = read_move(title)
    assert move is not None and move.is_move and move.mode == mode and move.destination == dest


def test_a_ride_to_a_sight_keeps_the_sight_and_other_words_are_not_moves():
    assert read_move("따릉이 타고 한강") == read_move("따릉이 타고 한강")       # 결정적이다
    ride = read_move("따릉이 타고 한강")
    assert ride is not None and not ride.is_move and ride.destination == "한강"
    assert read_move("버스킹 공연") is None
    assert read_move("차 마시고 인사동") is None                       # 「차」 뒤에 「로 · 타고」가 없으면 수단이 아니다
    assert read_move("경복궁") is None


def test_the_reader_does_not_look_up_a_move_line(monkeypatch):
    """☆「택시로 이동」이 카카오의 택시 회사 본사가 됐다 — 이제 장소를 찾지 않고 「장소 없이 둔」 줄이 된다."""
    from app.domains.travel_ops.components.intake import pipeline

    kakao = Kakao({"택시로 이동": [_hit("○○택시 본사")], "인천공항": [_hit("인천국제공항")]})
    rows = pipeline.read_source("1일차 2030-01-05\n10:00 경복궁\n11:30 택시로 이동\n18:00 공항철도 타고 인천공항",
                                tour=Tour({"경복궁": ("경복궁", (37.5796, 126.9770), "12")}), kakao=kakao,
                                our_places=[], today=datetime(2030, 1, 1).date())
    places = {r["field"]: r for r in rows if r["field"].endswith(".place")}
    moves = [r for r in places.values() if (r.get("evidence") or {}).get("method") == "move_phrase"]
    assert len(moves) == 2 and all(r["value"] is None for r in moves)
    assert {r["evidence"]["destination"] for r in moves} == {None, "인천공항"}
    assert not [q for q, _ in kakao.asked if "택시" in q or "공항" in q]


def test_the_review_shows_a_move_line_as_placeless_not_unresolved():
    from app.domains.travel_ops.components.intake.review import _place_line, place_state

    row = {"title": "택시로 이동", "kind": "activity", "place": None,
           "claims": {"place": {"value": None, "method": "lookup", "needs_review": False,
                                "evidence": {"method": "move_phrase", "mode": "택시", "destination": None}}}}
    state, value = place_state(row)
    assert (state, value) == ("none", None)
    assert "이동" in _place_line(row, state, value)["text"]


# ── 3. 대표 장소는 정답 이름 하나 ───────────────────────────────────────
@pytest.mark.parametrize("written", ["남산타워", "남산서울타워", "N서울타워", "남산타워 야경 구경"])
def test_namsan_tower_names_are_n_seoul_tower(written):
    tour = Tour({"N서울타워": ("N서울타워", (37.5512, 126.9882), "12")})
    found = resolve(written, our_places=[], tour=tour, kakao=Kakao(), dining=Ledger())
    assert (found.status, found.name) == ("resolved", "N서울타워")


def test_changdeokgung_never_becomes_unhyeongung():
    """☆창덕궁 → 서울 운현궁. 자료가 다른 이름을 내면 버리고 「찾지 못했다」로 둔다."""
    tour = Tour({"창덕궁과 후원": ("서울 운현궁", (37.5765, 126.9867), "12")})
    kakao = Kakao({"창덕궁과 후원": [_hit("서울 운현궁")]})
    found = resolve("창덕궁", our_places=[], tour=tour, kakao=kakao, dining=Ledger({"창덕궁": _shop("서울 운현궁")}))
    assert found.status == "unresolved" and found.name is None
    good = resolve("창덕궁", our_places=[], tour=Tour({"창덕궁과 후원": ("창덕궁과 후원", (37.5794, 126.9910), "12")}),
                   kakao=Kakao(), dining=Ledger())
    assert (good.status, good.name, good.needs_review) == ("resolved", "창덕궁과 후원", False)


@pytest.mark.parametrize("written, wrong, right", [
    ("국립중앙박물관", "서울아프리카페스티벌", "국립중앙박물관"),
    ("국립민속박물관", "오촌댁", "국립민속박물관"),
])
def test_museums_keep_their_own_name_over_events_and_houses_inside(written, wrong, right):
    kakao = Kakao({right: [_hit(wrong, category="여행 > 관광,명소"), _hit(right, category="문화,예술 > 박물관")]})
    found = resolve(written, our_places=[], tour=Tour({right: (wrong, GWANGHWAMUN, "15")}), kakao=kakao,
                    dining=Ledger({written: _shop(wrong)}))
    assert (found.status, found.name) == ("resolved", right)


def test_the_landmark_table_reads_the_longest_phrase():
    hit = find_landmark("명동 롯데호텔 서울")
    assert hit.landmark.name == "롯데호텔 서울" and hit.rest == ()
    assert find_landmark("창덕궁 후원 관람").landmark.name == "창덕궁과 후원"
    assert find_landmark("토속촌삼계탕") is None


# ── 4. 시장 · 거리 · 동네는 구역 ───────────────────────────────────────
@pytest.mark.parametrize("written", ["광장시장 점심", "점심 광장시장"])
def test_a_meal_at_gwangjang_market_stays_at_the_market(written):
    """☆광장시장이 시장 안 가게 하나(삼모녀꼬마김밥)로 24번 좁혀졌다."""
    ledger = Ledger(near_shop=_shop("삼모녀꼬마김밥", MARKET, license=False))
    tour = Tour({"광장시장": ("광장시장", MARKET, "38")})
    found = resolve(written, our_places=[], tour=tour, kakao=Kakao(), dining=ledger, kind_hint="dining")
    assert (found.status, found.name, found.kind, found.item_kind) == ("resolved", "광장시장", "activity", "dining")
    assert ledger.meal_asked == []                                   # 근처 가게를 찾지도 않는다


def test_a_dish_at_a_market_keeps_the_market_and_asks_about_the_dish():
    ledger = Ledger(near_shop=_shop("순희네빈대떡", MARKET, license=False))
    found = resolve("광장시장 빈대떡", our_places=[], tour=Tour({"광장시장": ("광장시장", MARKET, "38")}), kakao=Kakao(),
                    dining=ledger)
    assert (found.status, found.name) == ("resolved", "광장시장")
    assert found.needs_review is True and "빈대떡" in (found.note or "")
    assert ledger.meal_asked == []


def test_a_market_not_in_the_table_is_also_a_zone():
    ledger = Ledger(near_shop=_shop("통인가게", (37.5806, 126.9696)))
    found = resolve("통인시장", our_places=[], tour=Tour({"통인시장": ("통인시장", (37.5806, 126.9696), "38")}), kakao=Kakao(),
                    dining=ledger, kind_hint="dining")
    assert (found.name, found.item_kind) == ("통인시장", "dining") and ledger.meal_asked == []


@pytest.mark.parametrize("written, name, at", [
    ("인사동", "인사동", (37.5740, 126.9850)), ("익선동", "익선동", (37.5743, 126.9893)),
    ("성수동 카페거리", "성수동 카페거리", (37.5446, 127.0557)),
])
def test_streets_and_neighbourhoods_are_not_narrowed_to_one_shop(written, name, at):
    """☆인사동 → 매듭공방. 원문으로 시작하는 가게 이름 하나(「인사동매듭공방」)를 받지 않는다."""
    kakao = Kakao({name: [_hit(written + "매듭공방", at, "", "가정,생활 > 공방"), _hit(name, at, "", "여행 > 관광,명소 > 테마거리")]})
    found = resolve(written, our_places=[], tour=Tour(), kakao=kakao, dining=Ledger({written: _shop(written + "칼국수")}))
    assert (found.status, found.name) == ("resolved", name)


# ── 5. 숙소 대체 후보는 같은 도시 · 반경 안 ─────────────────────────────
def test_lodging_alternatives_outside_seoul_are_dropped(monkeypatch):
    """☆서울 호텔 대신 268km 떨어진 광주 호텔이 후보로 나왔다."""
    import app.core.settings as settings
    from .test_intake_lodging_candidates import review
    from .test_intake_lodging_registered import LocationConnection

    monkeypatch.setattr(settings, "get_guardrails",
                        lambda: SimpleNamespace(get=lambda key: 15000 if key.endswith("radius_m") else True))
    gwangju = {"name": "광주 호텔", "latitude": 35.1595, "longitude": 126.8526}
    seoul = {"name": "광화문 호텔", "latitude": 37.5720, "longitude": 126.9770}
    monkeypatch.setattr(lodging_alternatives, "ranked", lambda **kw: {"alternatives": [gwangju, seoul]})
    view = review(meal=True)
    view["party_size"] = 2
    got = candidates._team_lodging_places(LocationConnection(), "travel", view, view["items"][0], None, view["items"])
    assert [p["name"] for p in got] == ["광화문 호텔"]
    monkeypatch.setattr(lodging_alternatives, "ranked", lambda **kw: {"alternatives": [gwangju]})
    assert candidates._team_lodging_places(LocationConnection(), "travel", view, view["items"][0], None, view["items"]) is None


def test_a_far_corner_of_seoul_beyond_the_radius_is_dropped(monkeypatch):
    import app.core.settings as settings

    monkeypatch.setattr(settings, "get_guardrails", lambda: SimpleNamespace(get=lambda key: 15000))
    assert candidates._stay_in_range({"latitude": 37.5720, "longitude": 126.9770}, GWANGHWAMUN)
    assert not candidates._stay_in_range({"latitude": 37.4300, "longitude": 127.1800}, GWANGHWAMUN)   # 서울 사각 안이지만 18km 밖
    assert not candidates._stay_in_range({"latitude": None, "longitude": None}, GWANGHWAMUN)


# ── 6. 대표 장소 운영시간 ─────────────────────────────────────────────
def _hours(name, when):
    return facts_for(None, "travel", {"name": name, "kind": "activity", "source": "tour_api"}, "activity", when,
                     None, activity_verdict=False)


def test_changdeokgung_hours_and_monday_closing_come_from_the_table():
    wed = _hours("창덕궁과 후원", datetime(2026, 10, 21, 10, 0, tzinfo=KST))
    assert wed.known and wed.source == "landmark_table"
    assert wed.attributes["hours_week"]["wed"] == {"open": "09:00", "close": "18:00", "last_entry": "17:00"}
    assert wed.attributes["hours_read"]["checked"] == "2026-10-19"
    mon = _hours("창덕궁과 후원", datetime(2026, 10, 19, 10, 0, tzinfo=KST))
    assert mon.attributes["hours_week"] == {"mon": "closed"}


def test_the_secret_garden_reservation_is_a_tip_not_a_closing_condition():
    """`[2026-10-20]` 「후원은 따로 예약」은 방문 안내다 — 휴무 판정 조건에 넣으면 창덕궁 전체가 「확인해 주세요」 · 대체 후보 `fits: false` 가 된다(알려진 시험 실패 조사 「결함 B」)."""
    wed = _hours("창덕궁과 후원", datetime(2026, 10, 21, 10, 0, tzinfo=KST))
    assert wed.conditions == []
    assert wed.tips == ["후원은 따로 예약해야 들어갈 수 있어요"]


def test_n_seoul_tower_and_cheonggyecheon_hours_are_known():
    sat = _hours("N서울타워", datetime(2026, 10, 24, 20, 0, tzinfo=KST))
    assert sat.known and sat.attributes["hours_week"]["sat"] == {"open": "10:00", "close": "23:00"}
    assert sat.conditions == []                                        # 출처 차이는 기록만 — 휴무 줄을 「확인해 주세요」로 만들지 않는다
    stream = _hours("청계천", datetime(2026, 10, 22, 21, 0, tzinfo=KST))
    assert stream.known and stream.attributes["hours_week"]["thu"] == {"open": "00:00", "close": "23:59"}


def test_a_market_says_why_hours_are_unknown_instead_of_inventing_them():
    market = _hours("광장시장", datetime(2026, 10, 22, 12, 0, tzinfo=KST))
    assert market.known is False and "점포마다" in (market.why_unknown or "")


def test_places_outside_the_table_are_unchanged():
    other = _hours("어느 미술관", datetime(2026, 10, 22, 12, 0, tzinfo=KST))
    assert other.known is False and other.why_unknown == "관광공사 운영시간을 아직 읽지 못했어요"
