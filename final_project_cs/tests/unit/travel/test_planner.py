# -*- coding: utf-8 -*-
"""일정 생성기의 부품 — 선호 읽기 · 순위 · 시각 채우기 · 고쳐서 다시 판정.

★HTTP·DB 를 지나는 경로는 `tests/e2e/test_trip_planner.py` 가 본다. 여기는 **DB 없이** 도는
  순수 함수만 본다 — 규칙이 바뀌면 여기서 먼저 빨개진다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.modules.travel_ops import planner
from app.modules.travel_ops.itinerary_checks import check_itinerary
from app.modules.travel_ops.planner import Cand, preference_profile, rank_candidates

KST = planner.KST
DAY = date(2026, 10, 5)


def _cand(name, kind="activity", *, lat=37.575, lon=126.977, **attributes) -> Cand:
    return Cand(key=f"k_{name}", name=name, kind=kind, lat=lat, lon=lon,
                attributes=dict(attributes), origin="places", rank_hint=0)


# ── 선호 읽기 ─────────────────────────────────────────────────────
def test_the_free_sentence_becomes_three_axes_and_a_dislike_list():
    pref = preference_profile("실내 위주, 아이 동반, 매운 음식 싫어요")
    assert pref.indoor_first is True and pref.with_children is True
    assert "마라" in pref.avoid and "술집" in pref.avoid          # 아이 동반이면 술집도 뺀다


def test_a_word_without_a_negation_is_not_a_dislike():
    """★「매운 거 좋아요」를 싫다고 읽으면 좋아하는 것을 빼 버린다."""
    assert preference_profile("매운 거 좋아요").avoid == ()
    assert preference_profile("야외 산책 좋아요").outdoor_first is True


def test_an_empty_sentence_asks_for_nothing():
    pref = preference_profile("")
    assert pref.as_dict() == {"indoor_first": False, "outdoor_first": False,
                              "with_children": False, "avoid": []}


# ── 순위 ──────────────────────────────────────────────────────────
def test_indoor_first_moves_indoor_places_up_and_is_deterministic():
    pool = [_cand("야외 가", indoor=False), _cand("실내 나", indoor=True),
            _cand("모름 다")]
    order = [cand.name for cand in rank_candidates(pool, preference_profile("실내 위주"))]
    assert order[0] == "실내 나" and order[-1] == "야외 가"        # 모름은 가운데다
    assert order == [cand.name for cand in rank_candidates(pool, preference_profile("실내 위주"))]


def test_a_disliked_place_is_dropped_not_demoted():
    pool = [_cand("매운 마라탕", kind="dining"), _cand("순한 국수", kind="dining")]
    kept = rank_candidates(pool, preference_profile("매운 음식 싫어요"))
    assert [cand.name for cand in kept] == ["순한 국수"]


def test_a_place_whose_hours_we_know_comes_before_one_we_do_not():
    """★판정이 실제로 보는 칸을 가진 장소가 먼저다 — 예쁜 초안보다 판정 가능한 초안이 낫다."""
    pool = [_cand("가 모름"), _cand("하 아는곳", hours=["09:00", "18:00"])]
    assert [cand.name for cand in rank_candidates(pool, preference_profile(""))][0] == "하 아는곳"


# ── 시각은 우리가 채운다 ──────────────────────────────────────────
def test_the_day_is_laid_out_by_us_and_passes_the_check():
    acts = [_cand("활동 하나", hours=["09:00", "18:00"], district="종로구"),
            _cand("활동 둘", lat=37.578, lon=126.981, hours=["09:00", "18:00"], district="종로구")]
    dine = [_cand("점심", kind="dining", hours=["11:00", "21:00"], district="종로구"),
            _cand("저녁", kind="dining", lat=37.577, hours=["11:00", "21:00"], district="종로구")]
    items = planner.build_day(DAY, acts, dine, seq_from=1)
    assert [item["seq"] for item in items] == [1, 2, 3, 4]
    assert items[0]["starts_at"] == datetime(2026, 10, 5, 9, 30, tzinfo=KST)
    assert items[1]["starts_at"].time().hour == 12            # 점심은 12시 전으로 안 간다
    assert items[3]["starts_at"].time().hour == 18            # 저녁은 18시 전으로 안 간다
    for earlier, later in zip(items, items[1:]):
        assert earlier["ends_at"] <= later["starts_at"]        # 겹치지 않는다
    assert items[0]["detail"]["planner"]["transfer_basis"] == "하루 시작"
    assert "[추정]" in items[1]["detail"]["planner"]["transfer_basis"]


def test_an_item_is_pushed_inside_the_opening_hours_we_know():
    late = [_cand("늦게 여는 곳", hours=["11:00", "18:00"])]
    items = planner.build_day(DAY, late, [], seq_from=1)
    assert items[0]["starts_at"] == datetime(2026, 10, 5, 11, 0, tzinfo=KST)


def test_hours_we_do_not_know_are_left_alone():
    """★모르는 칸을 「09:00 에 연다」로 채우지 않는다 — 그러면 지어낸 값이 판정을 통과한다."""
    items = planner.build_day(DAY, [_cand("모르는 곳")], [], seq_from=1)
    assert items[0]["starts_at"] == datetime(2026, 10, 5, 9, 30, tzinfo=KST)
    assert "hours" not in items[0]["detail"].get("planner", {})


# ── 고쳐서 다시 판정 ──────────────────────────────────────────────
def _parts(items, places):
    from app.modules.travel_ops.itinerary_checks import Part

    return [Part(seq=item["seq"], kind=item["kind"], title=item["title"],
                 starts_at=item["starts_at"], ends_at=item["ends_at"],
                 place=places[item["place"]].for_check(), route=None, detail=item["detail"])
            for item in items]


def test_an_overlap_is_pushed_back_until_the_check_is_clean():
    acts = [_cand("앞", hours=["09:00", "18:00"]), _cand("뒤", hours=["09:00", "18:00"])]
    places = {cand.key: cand for cand in acts}
    items = planner.build_day(DAY, acts, [], seq_from=1)
    items[1]["starts_at"] = items[0]["starts_at"] + timedelta(minutes=30)   # 일부러 겹친다
    items[1]["ends_at"] = items[1]["starts_at"] + timedelta(minutes=90)
    before = check_itinerary(_parts(items, places))
    assert [v.code for v in before] == ["overlap"]

    fixed = planner.repair(items, places, before, spares=[], used=set(), constraints={},
                           party_size=2)
    assert fixed and "overlap" in fixed[0]
    assert check_itinerary(_parts(items, places)) == []


def test_an_unknown_violation_is_not_pretended_to_be_fixed():
    """★고칠 줄 모르는 위반에 「고쳤다」를 돌려주면 루프가 조용히 통과로 끝난다."""
    from app.modules.travel_ops.itinerary_checks import Violation

    acts = [_cand("하나", hours=["09:00", "18:00"])]
    places = {cand.key: cand for cand in acts}
    items = planner.build_day(DAY, acts, [], seq_from=1)
    unknown = [Violation("무슨_위반", (1,), "모르는 위반", "모르는 완화")]
    assert planner.repair(items, places, unknown, spares=[], used=set(), constraints={},
                          party_size=2) == []


def test_shifting_past_midnight_still_counts_as_the_same_day():
    """★자정을 넘기면 `starts_at.date()` 가 그 날을 더 이상 안 가리킨다. 그래서 계획한 날을
    `detail.planner.day` 로 들고 간다 — 안 그러면 뒤로 민 항목이 「다른 날」이 되어 그 뒤
    항목이 따라 밀리지 않는다."""
    acts = [_cand("하나"), _cand("둘", lat=37.576)]
    items = planner.build_day(DAY, acts, [], seq_from=1)
    assert {item["detail"]["planner"]["day"] for item in items} == {DAY.isoformat()}
    planner._shift(items, 1, 16 * 60)                 # 다음 날 01:30 으로 넘어간다
    assert items[0]["starts_at"].date() != DAY        # 날짜는 바뀌었지만
    assert items[1]["starts_at"].date() != DAY        # ★뒤 항목도 함께 밀렸다


# ── 상품 범위 ─────────────────────────────────────────────────────
def test_a_request_outside_the_product_is_refused_before_any_work():
    for city, days, party, code in (("부산", 2, 2, "city_not_supported"),
                                    ("서울", 9, 2, "out_of_product_scope"),
                                    ("서울", 2, 9, "out_of_product_scope")):
        try:
            planner.PlanRequest(city=city, start_date=DAY, days=days, party_size=party).validate()
        except planner.PlanRefused as refused:
            assert refused.code == code
        else:                                          # pragma: no cover - 실패하면 여기로 온다
            raise AssertionError(f"{city}/{days}일/{party}인 이 통과했다")

# ── 요청을 규정에 붙인다 (RAG) `[2026-09-22]` ──────────────────────
class _Chunk:
    """`PolicyChunk` 와 같은 모양(dataclass 가 아니라 속성만 흉내낸다)."""

    def __init__(self, document_id, chunk_no, content, score, scope):
        self.document_id, self.chunk_no = document_id, chunk_no
        self.content, self.score, self.scope = content, score, scope

    @property
    def source_id(self):
        return f"{self.document_id}#c{self.chunk_no}"


def _ask(preferences="실내 위주") -> planner.PlanRequest:
    return planner.PlanRequest(city="서울", start_date=DAY, days=1, party_size=2,
                               preferences=preferences)


def test_the_request_is_searched_against_the_travel_corpus_only():
    """★여행 질의가 쇼핑몰 `refund` 문서를 끌어온 적이 있다 — scope 를 여기서 못 박는다."""
    seen = {}

    def search(*, tenant_id, query, allowed_scopes, top_k):
        seen.update(tenant_id=tenant_id, query=query, scopes=allowed_scopes, top_k=top_k)
        return [_Chunk("t_doc_04", 3, "특보가 발효 중이면 업체 공지를 확인한다.", 0.81, "travel_weather")]

    found = planner.ground_request(tenant_id="t1", request=_ask("비 오면 어쩌죠"), search=search)

    assert seen["query"] == "비 오면 어쩌죠"          # 고객이 한 말 그대로 묻는다
    assert seen["scopes"] == list(planner.PLAN_SCOPES)
    assert all(scope.startswith("travel_") for scope in seen["scopes"]), seen["scopes"]
    assert found["hits"] == 1
    assert found["evidence"][0] == {"source_type": "policy", "source_id": "t_doc_04#c3",
                                    "scope": "travel_weather", "score": 0.81,
                                    "excerpt": "특보가 발효 중이면 업체 공지를 확인한다."}


def test_with_nothing_said_it_asks_about_the_request_and_says_so():
    """★고객이 아무 말도 안 했다고 검색을 건너뛰면 그 초안만 근거가 없어진다."""
    asked = {}

    def search(*, tenant_id, query, allowed_scopes, top_k):
        asked["query"] = query
        return []

    found = planner.ground_request(tenant_id="t1", request=_ask(""), search=search)
    assert "서울" in asked["query"] and "1일" in asked["query"]
    assert found["asked"].startswith("요청 요약")


def test_zero_hits_is_written_down_not_swallowed():
    found = planner.ground_request(tenant_id="t1", request=_ask(),
                                   search=lambda **_: [])
    assert found["hits"] == 0 and "0건" in found["note"]
    assert "규정을 보지 않고 짰다" in found["note"]


def test_a_search_failure_is_written_down_and_does_not_stop_the_draft():
    """★검색이 죽었다고 초안을 못 내면 안 되지만, **죽었다는 사실은 나가야 한다**."""

    def boom(**_):
        raise RuntimeError("1024칸이 비어 있다")

    found = planner.ground_request(tenant_id="t1", request=_ask(), search=boom)
    assert found["hits"] == 0
    assert "규정을 못 읽었다" in found["note"] and "1024칸이 비어 있다" in found["note"]


def test_nothing_found_means_the_prompt_gets_no_policy_section():
    assert planner.grounding_text({"evidence": []}) == ""
    assert planner.grounding_text({}) == ""
    text = planner.grounding_text({"evidence": [{"scope": "travel_access", "excerpt": "동반 조건"}]})
    assert text == "- (travel_access) 동반 조건"


def test_the_model_sees_the_policy_as_background_not_as_numbers_to_quote():
    """★규정에서 시각·가격을 읽어 오면 우리가 DB 에서 채우는 값과 어긋난다."""
    captured = {}

    class Chat:
        def json(self, system, user):
            captured["user"] = user
            return {"activities": ["1"], "dining": []}

    planner.order_with_model(Chat(), activities=[_cand("가")], dining=[],
                             preferences="아이 동반", day_label="2026-10-05 (day 1)",
                             grounding="- (travel_access) 동반 조건을 미리 확인한다")
    assert "동반 조건을 미리 확인한다" in captured["user"]
    assert "do not quote numbers" in captured["user"]


def test_without_grounding_the_policy_section_is_absent_entirely():
    captured = {}

    class Chat:
        def json(self, system, user):
            captured["user"] = user
            return {"activities": [], "dining": []}

    planner.order_with_model(Chat(), activities=[_cand("가")], dining=[],
                             preferences="", day_label="d", grounding="")
    assert "Operator policy" not in captured["user"]
