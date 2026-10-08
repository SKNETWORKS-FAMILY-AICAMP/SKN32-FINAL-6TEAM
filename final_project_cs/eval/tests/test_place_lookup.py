# -*- coding: utf-8 -*-
"""장소 찾기 평가 — 시험지 모양과 채점 규칙. DB · 네트워크 없이 돈다."""
from __future__ import annotations

from eval.runners.place_lookup import LABELS, load_cases, score_case, summarize

GYEONGBOK = [37.5788, 126.977]


def _items(name=None, *, lat=None, lng=None, review=False, kind=None, blocked=None, index=1):
    place = {"name": name, "latitude": lat, "longitude": lng, "kind": kind} if name else None
    return {index: {"place": place, "review": review, "evidence": {"blocked": blocked or []}, "kind": kind}}


def _case(expect, target=1):
    return {"id": "T", "group": "near", "lines": ["10:00 경복궁", "12:30 스타벅스"], "target": target, "expect": expect}


def test_dataset_is_34_cases_with_unique_ids_and_known_expectations():
    cases = load_cases()
    assert len(cases) == 34
    assert len({c["id"] for c in cases}) == 34
    for case in cases:
        assert 0 <= case["target"] < len(case["lines"])
        assert set(case["expect"]) <= {"accept", "brand", "near", "kind", "must_review", "no_pick", "or_no_pick"}
        assert {"accept", "brand", "no_pick"} & set(case["expect"]), case["id"]


def test_right_place_with_review_is_correct_review():
    out = score_case(_case({"brand": "스타벅스", "near": {"point": GYEONGBOK, "max_km": 1.0}, "must_review": True}),
                     _items("스타벅스 적선점", lat=37.5767, lng=126.9737, review=True, kind="dining"))
    assert out["label"] == "correct_review"
    assert out["km"] < 1.0


def test_chain_confirmed_without_review_is_wrong_confirmed():
    out = score_case(_case({"brand": "스타벅스", "must_review": True}),
                     _items("스타벅스 적선점", lat=37.5767, lng=126.9737, review=False))
    assert out["label"] == "wrong_confirmed"


def test_far_branch_is_wrong_and_review_flag_decides_which_wrong():
    expect = {"brand": "교촌치킨", "near": {"point": [37.5572, 126.9245], "max_km": 1.5}}
    far = dict(lat=37.5704, lng=126.9920)                           # 종로 — 홍대에서 약 6km
    assert score_case(_case(expect), _items("교촌치킨 종로1호점", review=True, **far))["label"] == "wrong_review"
    assert score_case(_case(expect), _items("교촌치킨 종로1호점", review=False, **far))["label"] == "wrong_confirmed"


def test_accept_is_matched_after_normalizing_spaces_and_symbols():
    out = score_case(_case({"accept": ["토속촌삼계탕"], "kind": "dining"}, target=0),
                     _items("토속촌 삼계탕(본점)", lat=37.5776, lng=126.9716, kind="dining", index=0))
    assert out["label"] == "correct_confirmed"


def test_wrong_kind_fails_even_when_name_matches():
    out = score_case(_case({"accept": ["광장시장"], "kind": "dining"}),
                     _items("광장시장", lat=37.5701, lng=126.9997, kind="activity", review=True))
    assert out["label"] == "wrong_review"
    assert "kind" in out["why_wrong"]


def test_no_pick_cases():
    assert score_case(_case({"no_pick": True}), _items())["label"] == "correct_abstain"
    assert score_case(_case({"no_pick": True}), _items("한식당", lat=37.5, lng=126.9))["label"] == "wrong_confirmed"
    assert score_case(_case({"accept": ["해운대암소갈비"], "or_no_pick": True}), _items())["label"] == "correct_abstain"


def test_blocked_is_counted_apart_from_not_found():
    assert score_case(_case({"accept": ["우래옥"]}), _items(blocked=["kakao:budget_exhausted"]))["label"] == "blocked"
    assert score_case(_case({"accept": ["우래옥"]}), _items())["label"] == "not_found"
    # 막혀서 못 고른 것은 「고르지 않아도 정답」으로 세지 않는다
    assert score_case(_case({"accept": ["해운대암소갈비"], "or_no_pick": True}),
                      _items(blocked=["tour_api:rate_limited"]))["label"] == "blocked"
    assert score_case(_case({"no_pick": True}), _items(blocked=["kakao:timeout"]))["label"] == "correct_abstain"


def test_summary_counts_every_label():
    results = [{"group": "near", "label": label} for label in LABELS]
    summary = summarize(results)
    assert summary["accuracy"] == {"num": 3, "den": 8, "rate": 0.375}
    assert summary["wrong_confirmed"]["num"] == 1
    assert sum(summary["labels"].values()) == 8


def test_holdout_is_12_cases_and_does_not_overlap_the_dev_set():
    """확인용 세트 — 모양만 본다. ★이 세트를 보며 접수 코드를 고치지 않는다(발표 직전 한 번 잰다)."""
    from eval.runners.place_lookup import ROOT

    holdout = load_cases(ROOT / "eval" / "datasets" / "place_lookup_holdout_v1.jsonl")
    dev = load_cases()
    assert len(holdout) == 12 and len({c["id"] for c in holdout}) == 12
    assert not {c["id"] for c in holdout} & {c["id"] for c in dev}
    assert not {c["lines"][c["target"]] for c in holdout} & {c["lines"][c["target"]] for c in dev}
    for case in holdout:
        assert 0 <= case["target"] < len(case["lines"])
        assert set(case["expect"]) <= {"accept", "brand", "near", "kind", "must_review", "no_pick", "or_no_pick"}
