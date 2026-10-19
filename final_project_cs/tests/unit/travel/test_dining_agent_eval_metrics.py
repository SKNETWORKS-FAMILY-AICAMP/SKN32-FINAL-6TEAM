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
                    "expected": True, "got": False, "correct": False, "repeat": 0}]
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


def test_wilson_interval_is_wide_for_small_samples_and_bounded():
    assert runner.wilson(0, 0) is None
    low, high = runner.wilson(40, 41)
    assert 0.86 < low < 0.88 and 0.99 < high <= 1.0
    assert runner.wilson(22, 22)[0] < 0.86 and runner.wilson(22, 22)[1] == 1.0
    assert runner.wilson(0, 5)[0] == 0.0
