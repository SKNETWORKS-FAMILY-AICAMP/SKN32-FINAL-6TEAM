# -*- coding: utf-8 -*-
"""EVAL-A 채점기(`eval/activity_judge/eval_a.py`) — A1 판정 순서 · A4 재난 분류표. LLM · DB 없이. `[2026-10-12]`"""
from __future__ import annotations

from eval.activity_judge import eval_a


def test_a1_every_overlap_answers_with_the_earliest_problem():
    report = eval_a.run_a1()
    failed = [r for r in report["rows"] if not r["pass"]]
    assert report["total"] == 15 and not failed, failed


def test_a4_region_filter_uses_the_place_district():
    assert eval_a.reaches({"regions": ["서울특별시 종로구"]}, "종로구") is True
    assert eval_a.reaches({"regions": ["부산광역시 해운대구"]}, "종로구") is False
    assert eval_a.reaches({"regions": ["서울특별시"]}, None) is True          # 시 전체는 구를 몰라도 닿는다
    assert eval_a.reaches({"regions": ["서울특별시 마포구"]}, None) is None    # 구를 모르면 모름


def _case(place, messages):
    return {"kind": "disaster_effect", "inputs": {"place_name": place, "place_kind": "activity", "messages": messages,
                                                  "starts_at": "2026-10-14T14:00:00+09:00"}}


def test_a4_table_answer_follows_the_impact_table():
    region = {"kind": "지진", "step": "긴급재난", "text": "지진 발생", "regions": ["서울특별시"],
              "created_at": "2026-10-14T09:00:00+09:00"}
    elsewhere = {**region, "regions": ["부산광역시 해운대구"]}
    released = {**region, "text": "정전 복구가 완료되었습니다", "kind": "정전"}

    assert eval_a.table_answer(_case("경복궁", [region]))[0] == "blocks"
    assert eval_a.table_answer(_case("경복궁", [elsewhere]))[0] == "no_effect"
    assert eval_a.table_answer(_case("경복궁", [released]))[0] == "no_effect"
    assert eval_a.table_answer(_case("없는장소이름XYZ", [{**region, "regions": ["서울특별시 종로구"]}]))[0] == "unknown"


def test_a4_reports_labels_that_differ_from_the_table():
    report = eval_a.run_a4()
    assert report["cases"] == 12
    assert report["label_agrees"] <= report["cases"]
    assert all({"case_id", "table", "label", "label_agrees"} <= set(r) for r in report["rows"])
