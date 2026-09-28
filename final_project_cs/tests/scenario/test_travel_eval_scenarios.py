# -*- coding: utf-8 -*-
"""여행 평가 시나리오가 **필수 조건 위반 0건**으로 도는가 — v11 §12 DoD-22 의 회귀 고정.

★전체 측정은 러너가 한다(`python -m eval.runners.travel_scenarios`, 보고서는 `eval/reports/`).
  여기서는 성격이 다른 **네 건**만 돌려 회귀를 막는다 — 전부 돌리면 시험 한 판이 40초 가까이 는다.

★무엇이 위반인가: 등록 때와 **같은 판정기**(`itinerary_checks`)로 적용된 모든 일정 버전을 다시 본다 —
  겹침 · 이동 소요 · 영업시간 · 브레이크 · 결제 수단 · 예산.

★**표본이 작다**(시나리오 10건 · 하루 1종 · 서울 1도시). 이 시험이 파랗다고 다른 일정에서도 위반이
  없다는 뜻이 아니다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.runners.travel_scenarios import DATASET, run_case

SPECS = {spec["case_id"]: spec
         for spec in (json.loads(line) for line in Path(DATASET).read_text(encoding="utf-8").splitlines()
                      if line.strip())}
#: 성격이 다른 넷 — 사건 전부 · 사건 없음 · 제약이 다른 여행 · 재요청
SAMPLE = ("t-confirmed", "t-quiet", "t-cash-only", "t-swap-rollback")


@pytest.mark.parametrize("case_id", SAMPLE)
def test_a_scenario_runs_without_breaking_a_hard_constraint(case_id):
    outcome = run_case(SPECS[case_id])
    assert outcome["violations"] == [], outcome["violations"]
    assert outcome["verdict"]["passed"], outcome["verdict"]["failures"]


def test_the_dataset_and_the_runner_still_match():
    """★데이터셋의 단계 이름이 러너와 어긋나면 측정이 **조용히 덜 돈다**."""
    known = {"tick", "say", "swap", "rollback"}
    for case_id, spec in SPECS.items():
        assert spec["steps"], case_id
        assert {step.split(":")[0] for step in spec["steps"]} <= known, (case_id, spec["steps"])
        assert "violations" in (spec.get("expect") or {}), case_id
