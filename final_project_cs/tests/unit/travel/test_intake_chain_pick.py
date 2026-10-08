# -*- coding: utf-8 -*-
"""체인점 지점 고르기 규칙(`intake/chain_pick.py`). 카카오 응답은 저장하지 않는다 — 아래 결과는 시험용으로 지은 것이다."""
from __future__ import annotations

from app.domains.travel_ops.components.intake.chain_pick import (
    CLUSTER_M, Neighbour, anchor_for, brand_of, branch_hint, needs_branch_pick, hint_request, pick_branch,
    search_requests, spread_m,
)

GYEONGBOK = (37.5788, 126.9770)
HONGDAE = (37.5572, 126.9245)
GANGNAM = (37.4980, 127.0276)


def hit(name, lat, lng, group="CE7", ident=None):
    return {"id": ident or name, "name": name, "category_group": group, "latitude": lat, "longitude": lng}


STARBUCKS = [
    hit("스타벅스 더북한산점", 37.6590, 126.9800),     # 관련도 1위 — 경복궁에서 9km
    hit("스타벅스 적선점", 37.5767, 126.9737),          # 경복궁 옆
    hit("스타벅스 압구정역점", 37.5270, 127.0283),
    hit("스타벅스 강남역신분당역사점", 37.4969, 127.0282),
]
KYOCHON = [hit("교촌치킨 종로1호점", 37.5704, 126.9920, "FD6"), hit("교촌치킨 홍대점", 37.5560, 126.9230, "FD6")]


# ── 이름 ──
def test_brand_and_branch_hint():
    assert brand_of("스타벅스 적선점") == "스타벅스"
    assert brand_of("명동교자 분점") == "명동교자"
    assert branch_hint("스타벅스 강남역점", "스타벅스") == "강남역"
    assert branch_hint("스타벅스강남역점", "스타벅스") == "강남역"              # 붙여 써도
    assert branch_hint("스타벅스 광화문점", "스타벅스") == "광화문"
    for not_place in ("명동교자 본점", "명동교자 분점", "교촌치킨 1호점", "스타벅스"):
        assert branch_hint(not_place, "명동교자" if "명동" in not_place else
                           ("교촌치킨" if "교촌" in not_place else "스타벅스")) is None


# ── 1 체인인가 ──
def test_same_brand_twice_is_a_chain():
    chain = needs_branch_pick("스타벅스", STARBUCKS)
    assert chain is not None and chain.brand == "스타벅스" and chain.hint is None


def test_exact_branch_named_once_is_not_a_chain():
    hits = [hit("스타벅스 광화문점", 37.5712, 126.9768), *STARBUCKS]
    assert needs_branch_pick("스타벅스 광화문점", hits) is None                    # 그 지점이 답이다


def test_missing_named_branch_is_a_chain_with_hint():
    chain = needs_branch_pick("스타벅스 강남역점", STARBUCKS)
    assert chain is not None and chain.hint == "강남역"


def test_branch_hint_without_jeom():
    assert branch_hint("스타벅스 광화문", "스타벅스") == "광화문"
    chain = needs_branch_pick("스타벅스 광화문", STARBUCKS)                   # 「점」 없이 — 그래도 지점 단서
    assert chain is not None and chain.brand == "스타벅스" and chain.hint == "광화문"
    hits = [hit("스타벅스 광화문점", 37.5712, 126.9768), *STARBUCKS]
    pick = pick_branch(needs_branch_pick("스타벅스 광화문", hits), hits, anchor_for(neighbours=[Neighbour(*GYEONGBOK)]))
    assert pick.place["name"] == "스타벅스 광화문점"                         # 경복궁에 더 가까운 적선점이 아니라


def test_single_shop_is_not_a_chain():
    assert needs_branch_pick("목멱산방", [hit("목멱산방", 37.5530, 126.9850, "FD6")]) is None


def test_romanized_chain_and_mixed_results():
    assert needs_branch_pick("Starbucks", STARBUCKS).brand == "스타벅스"
    mixed = [hit("경복궁", 37.5788, 126.9770, "AT4"), hit("경복궁 강남점", 37.50, 127.03, "FD6"),
             hit("경복궁 종로점", 37.57, 126.98, "FD6")]
    assert needs_branch_pick("Gyeongbokgung", mixed) is None                       # 관광지가 섞이면 체인이 아니다
    # 결과가 모두 식당 체인 「경복궁 ○○점」이어도(2026-10-07 실측과 같은 모양) 관광지 이름이면 체인이 아니다
    palace_chain = [hit("경복궁 방이점", 37.51, 127.11, "FD6"), hit("경복궁 관훈점", 37.57, 126.98, "FD6"),
                    hit("경복궁 서초점", 37.49, 127.01, "FD6")]
    assert needs_branch_pick("Gyeongbokgung", palace_chain).brand == "경복궁"       # 단서가 없으면 막지 못한다
    assert needs_branch_pick("Gyeongbokgung", palace_chain, landmarks={"경복궁"}) is None
    assert needs_branch_pick("경복궁", palace_chain, landmarks={"경복궁"}) is None


# ── 2 기준 위치 ──
def test_anchor_priority():
    certain = Neighbour(*GYEONGBOK)
    loose = Neighbour(*HONGDAE, certain=False, spread_m=120)
    assert anchor_for(hint_point=GANGNAM, neighbours=[certain]).source == "branch_hint"
    assert anchor_for(neighbours=[certain, loose]).points == (GYEONGBOK,)       # 확정된 곳만
    assert anchor_for(neighbours=[loose]).source == "cluster"                   # 후보가 모여 있으면 쓴다
    assert anchor_for(neighbours=[Neighbour(*HONGDAE, certain=False, spread_m=CLUSTER_M + 1)]) is None
    assert anchor_for() is None


def test_spread():
    assert spread_m([HONGDAE]) == 0
    assert 0 < spread_m([HONGDAE, (37.5575, 126.9250)]) < CLUSTER_M


# ── 3 다시 찾을 요청 ──
def test_search_requests_widen_radius_by_food_groups():
    chain = needs_branch_pick("스타벅스", STARBUCKS)
    requests = search_requests(chain, anchor_for(neighbours=[Neighbour(*GYEONGBOK)]))
    assert [r["radius"] for r in requests] == [1000, 3000, 5000]               # 그 브랜드의 업종(카페)만 묻는다
    assert {r["category_group_code"] for r in requests} == {"CE7"}
    mixed = needs_branch_pick("교촌치킨", KYOCHON)
    assert mixed.groups == ("FD6",)
    assert all(r["sort"] == "distance" and r["query"] == "스타벅스" for r in requests)
    assert search_requests(chain, None) == []
    assert hint_request(needs_branch_pick("스타벅스 강남역점", STARBUCKS)) == {"query": "강남역", "category_group_code": "SW8",
                                                                         "size": 1}


# ── 4 지점 고르기 (평가 세트 케이스) ──
def test_pl011_gyeongbok_then_starbucks_picks_nearby_with_review():
    pick = pick_branch(needs_branch_pick("스타벅스", STARBUCKS), STARBUCKS, anchor_for(neighbours=[Neighbour(*GYEONGBOK)]))
    assert pick.status == "picked" and pick.place["name"] == "스타벅스 적선점"
    assert pick.needs_review and pick.distance_m < 1000
    assert len(pick.alternatives) == 2


def test_pl006_no_anchor_asks_instead_of_picking():
    pick = pick_branch(needs_branch_pick("스타벅스", STARBUCKS), STARBUCKS, None)
    assert pick.status == "ask" and pick.place is None and pick.alternatives


def test_pl013_station_candidates_clustered_still_anchor():
    anchor = anchor_for(neighbours=[Neighbour(*HONGDAE, certain=False, spread_m=150)])
    pick = pick_branch(needs_branch_pick("교촌치킨", KYOCHON), KYOCHON, anchor)
    assert pick.place["name"] == "교촌치킨 홍대점"


def test_pl031_branch_name_beats_neighbours():
    chain = needs_branch_pick("스타벅스 강남역점", STARBUCKS)
    pick = pick_branch(chain, STARBUCKS, anchor_for(hint_point=GANGNAM, neighbours=[Neighbour(*GYEONGBOK)]))
    assert pick.status == "picked" and pick.place["name"] == "스타벅스 강남역신분당역사점"


def test_named_branch_missing_asks_instead_of_nearby_other_branch():
    no_gangnam = [h for h in STARBUCKS if "강남역" not in h["name"]]
    pick = pick_branch(needs_branch_pick("스타벅스 강남역점", no_gangnam), no_gangnam, anchor_for(hint_point=GANGNAM))
    assert pick.status == "ask" and pick.alternatives[0]["name"] == "스타벅스 압구정역점"


def test_too_far_asks_and_duplicates_are_merged():
    far = [hit("스타벅스 더북한산점", 37.6590, 126.9800, ident="a"), hit("스타벅스 더북한산점", 37.6590, 126.9800, ident="a"),
           hit("스타벅스 도봉점", 37.6690, 127.0400, ident="b")]
    pick = pick_branch(needs_branch_pick("스타벅스", far), far, anchor_for(neighbours=[Neighbour(*GANGNAM)]))
    assert pick.status == "ask" and pick.distance_m > 5000
    assert len({h["id"] for h in pick.alternatives}) == len(pick.alternatives) == 2


def test_two_neighbours_choose_the_branch_between_them():
    bukchon = (37.5826, 126.9830)
    between = hit("스타벅스 북촌로점", 37.5800, 126.9845)
    hits = [*STARBUCKS, between]
    pick = pick_branch(needs_branch_pick("스타벅스", hits), hits,
                       anchor_for(neighbours=[Neighbour(*GYEONGBOK), Neighbour(*bukchon)]))
    assert pick.place["name"] == "스타벅스 북촌로점"
