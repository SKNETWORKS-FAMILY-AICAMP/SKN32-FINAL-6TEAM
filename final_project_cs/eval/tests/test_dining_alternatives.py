# -*- coding: utf-8 -*-
"""대체 식당 평가 — 시나리오가 스스로 맞는지(정답이 동선을 지키나)와 채점 규칙. 순수 계산이라 DB 없이 돈다."""
from __future__ import annotations

from datetime import timedelta

from app.modules.travel_ops.itinerary_changes import round_up_5
from app.modules.travel_ops.replan import SEATING_BUFFER_MIN
from eval.runners import dining_alternatives as da


def _visit(case, items, places, key):
    """후보 key 로 바꿨을 때의 식사 항목 — 계산 코드가 정하는 입장 시각 규칙을 그대로 따른다."""
    meal = next(i for i in items if i.seq == case["meal"])
    start = meal.starts_at
    if case["path"] == "closed_now":
        start = round_up_5(da._at(case["at"]) + timedelta(minutes=da.walk_min(meal.place, places[key]) + SEATING_BUFFER_MIN))
    elif case["path"] == "delay":
        start = meal.starts_at + timedelta(minutes=case["delay_min"])
    return meal.replaced_by(place=places[key], title="x", starts_at=start, ends_at=start + (meal.ends_at - meal.starts_at))


def test_dataset_shape():
    cases = da.load_cases()
    assert len(cases) == 19 and len({c["id"] for c in cases}) == 19
    assert {c["id"] for c in cases if c.get("needs") == "mobility"} == {"DA-018", "DA-019"}
    for case in cases:
        keys = {p["key"] for p in case["places"]}
        assert "O" in keys and {i["place"] for i in case["items"]} <= keys
        assert case["path"] in {"closed_on_day", "closed_now", "delay"}
        assert set(case["expect"]) <= {"accept", "ok", "no_change"} and case["expect"]
        assert set(case["expect"].get("accept", [])) | set(case["expect"].get("ok", [])) <= keys


def test_every_accepted_place_keeps_the_route_and_wrong_move_places_are_worse():
    """시나리오가 스스로 맞는지 — 정답은 동선을 지키고, 동선 묶음의 오답은 다음 일정에 늦거나 이동이 더 늘어난다.
    이동 계산기 묶음(transit)은 계산기 자료가 있어야 잰다 — 여기서는 뺀다(`--mobility` 로 돌릴 때 평가기가 같은 판정을 한다)."""
    for case in (c for c in da.load_cases() if c.get("needs") != "mobility"):
        _, items, places = da.build(case)
        checks = {key: da.route_check(case, items, places, key, _visit(case, items, places, key))
                  for key in (p["key"] for p in case["places"] if p.get("kind", "dining") == "dining" and p["key"] != "O")}
        for key in case["expect"].get("accept", []):
            assert not checks[key]["violation"], (case["id"], key)
        if case["group"] == "move" and case["id"] != "DA-005":
            best = min(checks[k]["added_walk_min"] for k in case["expect"]["accept"])
            for key, check in checks.items():
                if key not in case["expect"]["accept"]:
                    assert check["violation"] or check["added_walk_min"] > best, (case["id"], key)


def test_score_rules():
    case = {"expect": {"accept": ["A"], "ok": ["B"]}}
    fine, late = {"violation": False}, {"violation": True}
    assert da.score_case(case, "A", fine) == "correct"
    assert da.score_case(case, "B", fine) == "ok"
    assert da.score_case(case, "C", fine) == "wrong"
    assert da.score_case(case, "A", late) == "wrong_violation"          # 동선을 깨면 정답 가게여도 위반
    assert da.score_case(case, None, None) == "missed"
    assert da.score_case({"expect": {"no_change": True}}, None, None) == "correct_no_change"
    assert da.score_case({"expect": {"no_change": True}}, "A", fine) == "wrong_change"


def test_ids_change_with_seed_so_ties_are_exposed():
    case = da.load_cases()[0]
    ids = {seed: da.build(case, seed)[2]["E"]["place_id"] for seed in range(3)}
    assert len(set(ids.values())) == 3


def test_transit_cases_are_skipped_without_the_engine():
    case = next(c for c in da.load_cases() if c["id"] == "DA-018")
    assert da._LEG["leg"] is None
    assert da.run_case(case)["label"] == "skipped"
    assert da.summarize([{"id": "DA-018", "group": "transit", "label": "skipped"},
                         {"id": "X", "group": "move", "label": "correct"}])["accuracy"]["den"] == 1


HOLDOUT = da.ROOT / "eval" / "datasets" / "dining_alternatives_holdout_v1.jsonl"


def test_holdout_shape_and_accepted_places_keep_the_route():
    """확인용 세트 — 모양과 「정답이 동선을 지키나」만 본다. ★이 세트를 보며 계산 코드를 고치지 않는다."""
    cases = da.load_cases(HOLDOUT)
    assert len(cases) == 8 and not {c["id"] for c in cases} & {c["id"] for c in da.load_cases()}
    for case in cases:
        _, items, places = da.build(case)
        for key in case["expect"].get("accept", []):
            assert not da.route_check(case, items, places, key, _visit(case, items, places, key))["violation"], case["id"]
