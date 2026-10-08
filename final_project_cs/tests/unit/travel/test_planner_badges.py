# -*- coding: utf-8 -*-
"""일정 생성기가 미쉐린 · 노포 표시를 읽는다 — 원하면 앞에 세우고, 화면에는 출처와 함께 보인다. `[2026-10-07]`

★취향이지 조건이 아니다 — 표시가 없는 식당을 거르지 않는다. 원한다고 하지 않으면 순서가 그대로다.
★DB 없이 돈다. 원장 SQL(`shop_badges`)은 흉내 커서로, 실제 SQL 은 `tests/integration/dining` 이 본다.
"""
from __future__ import annotations

from app.domains.travel_ops.components.planning import planner
from app.domains.travel_ops.instances.dining.ledger import shop_badges
from app.domains.travel_ops.components.planning.survey import likes_from_survey
from app.domains.travel_ops.components.planning.planner import Cand, preference_profile, rank_candidates
from app.domains.travel_ops.entry.trip_api import _badges

MICHELIN = {"code": "michelin", "label": "미쉐린 빕 구르망 (2026)", "source": "미쉐린 가이드 서울"}
NOPO = {"code": "nopo", "label": "노포", "source": "카카오맵 노포 지도"}


def _shop(name, *badges, district="종로구", lat=37.5752, lon=126.9775):
    attributes = {"source": "dining_ledger", "dining_place_uid": name, "district": district}
    if badges:
        attributes["badges"] = list(badges)
    return Cand(key=f"dn_{name}", name=name, kind="dining", lat=lat, lon=lon, attributes=attributes,
                origin="dining_ledger", rank_hint=0)


# ── 문장 · 설문에서 취향을 읽는다 ────────────────────────────────────
def test_a_sentence_asking_for_michelin_or_nopo_becomes_a_like():
    assert preference_profile("미슐랭 맛집 가고 싶어요").likes == ("michelin",)
    assert preference_profile("점심은 노포 위주로, 저녁은 미쉐린").likes == ("michelin", "nopo")
    assert preference_profile("오래된 식당 좋아해요").likes == ("nopo",)


def test_a_negated_mention_is_not_a_like():
    assert preference_profile("노포는 싫어요").likes == ()
    assert preference_profile("미쉐린 말고 편한 곳").likes == ()


def test_the_survey_food_details_carry_likes_in_a_fixed_order():
    survey = {"survey": {"priority_details": {"food": ["nopo", "taste", "michelin", "halal"]}}}
    assert likes_from_survey(survey) == ("michelin", "nopo")
    assert likes_from_survey({}) == ()
    assert likes_from_survey({"survey": "broken"}) == ()


# ── 원장 표시가 후보에 실린다 ─────────────────────────────────────────
def test_ledger_shops_carry_their_badges_and_shops_without_badges_carry_none():
    cands = planner.ledger_candidates([
        {"place_uid": "u1", "name": "필동면옥", "lat": 37.56, "lng": 126.99, "address": "서울특별시 중구 서애로 26",
         "content_id": None, "badges": [MICHELIN, NOPO]},
        {"place_uid": "u2", "name": "보통 식당", "lat": 37.56, "lng": 126.99, "address": None, "content_id": None,
         "badges": []}])
    assert cands[0].attributes["badges"] == [MICHELIN, NOPO]
    assert "badges" not in cands[1].attributes


def test_shop_badges_reads_one_badge_per_kind_labels_it_and_keeps_screen_order():
    class Cursor:
        def execute(self, sql, params):
            assert "production_allowed" in sql and params == (["michelin", "nopo"],)

        def fetchall(self):
            return [("u1", "nopo", None, "카카오맵 노포 지도"),
                    ("u1", "michelin", "빕 구르망 (2026)", "미쉐린 가이드 서울"),
                    ("u1", "michelin", "셀렉티드 (2025)", "미쉐린 가이드 서울"),      # 같은 표시의 옛 것 — 버린다
                    ("u2", "nopo", None, "카카오맵 노포 지도")]

    got = shop_badges(Cursor())
    assert got["u1"] == [MICHELIN, NOPO]
    assert got["u2"] == [NOPO]


# ── 순위 ─────────────────────────────────────────────────────────────
def test_a_wanted_badge_comes_first_but_nothing_is_dropped():
    plain, old = _shop("가 식당"), _shop("하 노포집", NOPO)
    ranked = rank_candidates([plain, old], preference_profile("노포 좋아요"))
    assert [c.name for c in ranked] == ["하 노포집", "가 식당"]


def test_without_a_like_the_order_is_unchanged():
    plain, old = _shop("가 식당"), _shop("하 노포집", NOPO)
    assert [c.name for c in rank_candidates([plain, old], preference_profile(""))] == ["가 식당", "하 노포집"]


def test_known_hours_still_come_before_a_wanted_badge():
    known = _shop("가 식당")
    known.attributes["hours"] = ["11:00", "21:00"]
    old = _shop("하 노포집", NOPO)
    assert [c.name for c in rank_candidates([old, known], preference_profile("노포"))] == ["가 식당", "하 노포집"]


def test_day_pools_put_a_wanted_shop_first_within_the_district_and_nearby_only():
    anchor = Cand(key="a", name="고궁", kind="activity", lat=37.5796, lon=126.9770,
                  attributes={"district": "종로구"}, origin="places", rank_hint=0)
    near_plain = _shop("가까운 식당", lat=37.5797, lon=126.9771)
    far_old = _shop("조금 먼 노포", NOPO, lat=37.5850, lon=126.9850)          # 같은 구 · 약 1km
    other_close = _shop("옆 구 노포", NOPO, district="중구", lat=37.5700, lon=126.9800)   # 약 1.1km
    other_far = _shop("먼 구 노포", NOPO, district="강남구", lat=37.5000, lon=127.0300)   # 약 10km
    other_plain = _shop("옆 구 식당", district="중구", lat=37.5790, lon=126.9775)

    def want(cand):
        return planner.liked(cand, preference_profile("노포"))

    got = [c.name for c in planner._near_dining([near_plain, far_old, other_plain, other_far, other_close],
                                                [anchor], "종로구", want)]
    assert got[:2] == ["조금 먼 노포", "가까운 식당"]                 # 같은 구 안에서 노포가 먼저
    assert got[2] == "옆 구 노포"                                      # 다른 구는 3km 안일 때만 먼저
    assert got.index("옆 구 식당") < got.index("먼 구 노포")           # 10km 밖 노포는 가까운 순 그대로


def test_the_model_sees_the_badge_as_a_tag():
    lines = planner._order_lines([_shop("필동면옥", MICHELIN, NOPO), _shop("보통 식당")])
    assert lines.splitlines()[0].endswith("| 미쉐린 빕 구르망 (2026), 노포")
    assert "|" not in lines.splitlines()[1].split("indoor unknown")[-1]


# ── 화면 ─────────────────────────────────────────────────────────────
def test_the_item_view_passes_well_formed_badges_with_their_source_and_drops_the_rest():
    place = {"badges": [MICHELIN, {"code": "nopo", "label": "노포"}, "broken", {**NOPO, "extra": 1}]}
    assert _badges(place) == [MICHELIN, NOPO]
    assert _badges(None) == [] and _badges({}) == []


# ── 일정 생성 끝까지 (DB 없이 — 후보 읽기와 원장을 흉내 낸다) ─────────────
def test_the_planner_picks_the_wanted_nopo_only_when_asked(monkeypatch):
    from datetime import date

    from app.domains.travel_ops.components.planning.planner import PlanRequest

    def act(name, lat):
        return Cand(key=f"k_{name}", name=name, kind="activity", lat=lat, lon=126.977,
                    attributes={"hours": ["09:00", "18:00"], "district": "종로구"}, origin="places", rank_hint=0)

    class Ledger:
        def shops(self):
            near = [{"place_uid": f"p{i}", "name": f"가{i} 식당", "lat": 37.5795 + i * 0.0001, "lng": 126.9772,
                     "address": "서울특별시 종로구 1", "content_id": None, "badges": []} for i in range(6)]
            return near + [{"place_uid": "old", "name": "하 노포집", "lat": 37.5720, "lng": 126.9900,
                            "address": "서울특별시 종로구 2", "content_id": None, "badges": [NOPO]}]

        def verdicts(self, slots):
            return {s["seq"]: {"open_at_slot": True, "closed": False} for s in slots if s.get("place_uid")}

        def open_among(self, uids, at, until):
            return {uid: True for uid in uids}

    monkeypatch.setattr(planner, "load_candidates", lambda conn, tenant_id, **kw: [
        act("고궁", 37.5796), act("박물관", 37.5800), act("미술관", 37.5810), act("공원", 37.5820)])

    def meals(words, constraints=None):
        out = planner.plan_trip(conn=None, tenant_id="t", ledger=Ledger(), request=PlanRequest(
            city="서울", start_date=date(2026, 10, 12), days=1, party_size=2, preferences=words,
            constraints=constraints or {}))
        return [item["title"] for item in out.as_dict()["draft"]["items"] if item.get("kind") == "dining"]

    assert not any("노포집" in title for title in meals(""))
    assert any("노포집" in title for title in meals("노포 위주로 먹고 싶어요"))
    assert any("노포집" in title for title in meals("", {"survey": {
        "version": "2026-09-24.v1", "priority_details": {"food": ["nopo"]}}}))
