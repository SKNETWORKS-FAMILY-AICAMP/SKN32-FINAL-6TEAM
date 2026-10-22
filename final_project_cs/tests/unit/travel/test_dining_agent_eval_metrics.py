# -*- coding: utf-8 -*-
"""요식 판정 에이전트 평가 채점(`eval/runners/dining_agent.score` · `quality`) — v2 지표. `[2026-10-18]`

★오류 방향(bad_as_ok · ok_as_bad) · 필수/선호(required_as_preference) · 묶음별 · 반복 일관성이 맞게 세어지는지 본다.
  모델은 부르지 않는다 — 채점 함수만 본다.
"""
from __future__ import annotations

from eval.runners import dining_agent as runner

CASE = {"id": "DG2-001", "slice": "cond_required",
        "expect": {"m1": {"must": ["found", "open_at", "dietary"], "must_not": ["kids", "payment"],
                          "verdicts": {"found": "ok", "open_at": "bad", "dietary": "bad"},
                          "required": {"dietary": True}}}}


def _rows(reported, required=None, repeat=0):
    rows = runner.score(CASE, reported, required)
    for row in rows:
        row["repeat"] = repeat
    return rows


def test_score_marks_required_and_treats_an_omitted_flag_as_preference():
    rows = _rows({"m1": {"found": "ok", "open_at": "bad", "dietary": "bad"}}, {"m1": {"dietary": False}})
    req = [r for r in rows if r["kind"] == "required"]
    assert req == [{"case": "DG2-001", "item": "m1", "check": "dietary", "kind": "required", "slice": "cond_required",
                    "expected": True, "got": False, "correct": False, "flag_missing": False, "repeat": 0}]
    assert all(r["slice"] == "cond_required" for r in rows)


def test_a_missing_check_has_no_required_answer():
    rows = _rows({"m1": {"found": "ok", "open_at": "bad"}})
    req = next(r for r in rows if r["kind"] == "required")
    assert req["got"] is None and req["correct"] is False


def test_v1_cases_without_slice_or_required_still_score():
    v1 = {"id": "DG-001", "expect": {"m1": {"must": ["found"], "must_not": [], "verdicts": {"found": "ok"}}}}
    rows = runner.score(v1, {"m1": {"found": "ok"}})
    assert [r["kind"] for r in rows] == ["must"] and rows[0]["correct"] and rows[0]["slice"] is None


def test_quality_counts_the_direction_of_errors():
    rows = _rows({"m1": {"found": "ok", "open_at": "ok", "dietary": "bad", "kids": "ok"}}, {"m1": {"dietary": True}})
    q = runner.quality(rows)
    assert q["harm"]["bad_as_ok"]["num"] == 1 and q["harm"]["bad_as_ok"]["den"] == 2      # 닫힌 시각을 영업한다고 했다
    assert q["harm"]["bad_recall"]["num"] == 1 and q["harm"]["ok_as_bad"]["num"] == 0
    assert q["confusion"] == {"bad": {"ok": 1, "bad": 1}, "ok": {"ok": 1}}
    assert q["by_slice"]["cond_required"]["num"] == 2 and q["by_slice"]["cond_required"]["den"] == 3
    assert q["required"]["accuracy"]["num"] == 1 and q["required"]["required_as_preference"]["num"] == 0


def test_required_read_as_preference_is_counted_as_the_dangerous_side():
    q = runner.quality(_rows({"m1": {"found": "ok", "open_at": "bad", "dietary": "bad"}}))
    assert q["required"]["required_as_preference"] == {"num": 1, "den": 1, "rate": 1.0, "ci95": runner.wilson(1, 1)}


def test_consistency_appears_only_with_repeats():
    first = _rows({"m1": {"found": "ok", "open_at": "bad", "dietary": "bad"}}, repeat=0)
    assert "consistency" not in runner.quality(first)
    second = _rows({"m1": {"found": "ok", "open_at": "ok", "dietary": "bad"}}, repeat=1)
    assert runner.quality(first + second)["consistency"]["num"] == 2                    # open_at 만 두 판이 갈렸다


def test_selection_scores_choosing_checks_apart_from_the_verdict():
    # `[2026-10-19]` 체크 고르기 — 판정이 틀려도 고른 것은 고른 것이다(판정은 must_accuracy 가 본다)
    rows = _rows({"m1": {"found": "ok", "open_at": "ok", "kids": "ok", "closed_day": "ok"}})
    sel = runner.quality(rows)["selection"]
    assert sel["recall"] == {"num": 2, "den": 3, "rate": 0.667}               # dietary 를 빠뜨림
    assert sel["precision"] == {"num": 2, "den": 3, "rate": 0.667}            # kids 는 고르면 안 됐다 · closed_day 는 라벨이 없어 안 센다
    assert sel["f1"] == {"num": 4, "den": 6, "rate": 0.667}
    assert sel["f2"] == 0.667


def test_pass_k_counts_a_case_only_when_every_check_is_right_and_nothing_extra():
    right = {"m1": {"found": "ok", "open_at": "bad", "dietary": "bad"}}
    extra = {"m1": {"found": "ok", "open_at": "bad", "dietary": "bad", "payment": "ok"}}
    assert runner.quality(_rows(right))["pass_k"]["pass_hat_k"] == 1.0
    assert runner.quality(_rows(extra))["pass_k"]["pass_hat_k"] == 0.0              # 쓸데없는 체크 하나로 과제 실패
    three = _rows(right, repeat=0) + _rows(right, repeat=1) + _rows(extra, repeat=2)
    got = runner.quality(three)["pass_k"]
    assert got["k"] == 3 and got["pass_hat_k"] == 0.0 and got["pass_at_k"] == 1.0
    assert got["all_trials_pass"] == {"num": 0, "den": 1, "rate": 0.0}


# ── `[2026-10-19]` 도구 호출 · 모름 ───────────────────────────────

UID, OTHER = "c7441880-a22b-5b8e-821e-bfecddbeafa1", "4ad0881d-de7b-5b78-b7f8-e10c0048c66c"
PLAN_CASE = {**CASE, "plan": {"date": "2026-11-10", "items": [
    {"item_id": "m1", "kind": "dining", "start": "2026-11-10T18:00", "end": "2026-11-10T19:00", "place": {"name": "미 피아체"}}]},
    "expect": {"m1": {**CASE["expect"]["m1"], "place_uid": UID}}}


def _run(calls, refused=(), mode="rule_tools"):
    return {"case": PLAN_CASE["id"], "repeat": 0, "mode": mode, "calls": calls, "refused_calls": list(refused)}


def test_tool_selection_covers_each_needed_check_and_flags_tools_nothing_needed():
    calls = [{"tool": "find_place", "args": {"name": "미 피아체"}},
             {"tool": "check_open_at", "args": {"place_uid": UID, "start": "2026-11-10T18:00", "end": "2026-11-10T19:00"}},
             {"tool": "check_business", "args": {"place_uid": UID}},                    # 영업 ok 를 막는 근거라 쓰인 것으로 본다
             {"tool": "nearby_places", "args": {"lat": 37.5, "lng": 127.0}}]            # 근처 찾기는 고를 이유가 없었다
    got = runner.tool_use([PLAN_CASE], [_run(calls)])
    sel = got["selection"]
    assert sel["recall"] == {"num": 2, "den": 3, "rate": 0.667}                  # dietary 를 볼 check_attributes 가 없다
    assert sel["precision"] == {"num": 3, "den": 4, "rate": 0.75}
    assert got["missing_tools"] == {"check_attributes": 1} and got["extra_tools"] == {"nearby_places": 1}


def test_argument_accuracy_checks_the_shop_and_the_whole_meal_slot():
    calls = [{"tool": "check_open_at", "args": {"place_uid": UID, "start": "2026-11-10T18:00", "end": "2026-11-10T19:00"}},
             {"tool": "check_open_at", "args": {"place_uid": UID, "start": "2026-11-10T18:00"}},          # 끝 시각을 빼먹음
             {"tool": "check_attributes", "args": {"place_uid": OTHER, "wanted": ["halal"]}},             # 다른 가게
             {"tool": "find_place", "args": {"name": "미피아체"}}]                                          # 이름 질의는 안 잰다
    got = runner.tool_use([PLAN_CASE], [_run(calls)])
    assert got["arguments"] == {"num": 1, "den": 3, "rate": 0.333}
    assert got["argument_errors"] == {"check_open_at": 1, "check_attributes": 1}


def test_repeats_count_refused_duplicates_and_the_same_question_asked_again():
    calls = [{"tool": "check_open_at", "args": {"place_uid": UID, "start": "2026-11-10T18:00", "end": "2026-11-10T19:00"}},
             {"tool": "check_open_at", "args": {"place_uid": UID, "start": "2026-11-10 18:00", "end": "2026-11-10 19:00"}}]
    refused = [{"tool": "check_open_at", "why": "같은 도구를 같은 인자로 다시 불렀다 — 앞의 결과를 쓴다"},
               {"tool": "check_open_at", "why": "필수 인자가 없다: ['start']"}]
    got = runner.tool_use([PLAN_CASE], [_run(calls, refused)])
    assert got["repeats"] == {"exact_refused": 1, "same_question": 1, "calls": 2, "attempts": 4,
                              "rate": {"num": 2, "den": 4, "rate": 0.5}}
    assert got["refused"] == 2


def test_direct_mode_expects_the_data_tool_for_opening_hours():
    calls = [{"tool": "find_place", "args": {"name": "미 피아체"}},
             {"tool": "place_detail", "args": {"place_uid": UID, "date": "2026-11-10"}},
             {"tool": "check_attributes", "args": {"place_uid": UID, "wanted": ["halal"]}}]
    got = runner.tool_use([PLAN_CASE], [_run(calls, mode="llm_direct")])
    assert got["selection"]["f1"]["rate"] == 1.0 and got["arguments"]["rate"] == 1.0


def test_tool_use_is_absent_for_the_rule_config():
    assert runner.tool_use([PLAN_CASE], [{"case": "DG2-001", "repeat": 0}]) is None


def test_unknown_rate_separates_honest_unknowns_from_giving_up_on_knowable_checks():
    rows = _rows({"m1": {"found": "ok", "open_at": "unknown", "dietary": "bad"}})
    u = runner.quality(rows)["unknown"]
    assert u["rate"] == {"num": 1, "den": 3, "rate": 0.333}                       # 낸 판정 중 모름
    assert u["when_knowable"] == {"num": 1, "den": 3, "rate": 0.333}              # 기대가 ok · bad 인데 모름
    assert u["answered_accuracy"] == {"num": 2, "den": 2, "rate": 1.0}           # 모름을 뺀 판정의 정확도


def test_an_omitted_required_flag_is_counted_apart_from_an_explicit_false():
    # `[2026-10-20]` 필수 조건을 선호로 읽은 것 중 — 모델이 required 를 아예 안 적은 것(서버가 선호로 본다)과 false 로 적은 것을 가른다
    reported = {"m1": {"found": "ok", "open_at": "bad", "dietary": "bad"}}
    omitted = runner.score(CASE, reported, {"m1": {"dietary": False}}, {"m1": ["dietary"]})
    explicit = runner.score(CASE, reported, {"m1": {"dietary": False}}, {"m1": []})
    assert runner.quality(omitted)["required"]["flag_missing"] == {"num": 1, "den": 1, "rate": 1.0, "ci95": runner.wilson(1, 1)}
    assert runner.quality(explicit)["required"]["flag_missing"]["num"] == 0
    assert runner.quality(explicit)["required"]["required_as_preference"]["num"] == 1


def test_wilson_interval_is_wide_for_small_samples_and_bounded():
    assert runner.wilson(0, 0) is None
    low, high = runner.wilson(40, 41)
    assert 0.86 < low < 0.88 and 0.99 < high <= 1.0
    assert runner.wilson(22, 22)[0] < 0.86 and runner.wilson(22, 22)[1] == 1.0
    assert runner.wilson(0, 5)[0] == 0.0
