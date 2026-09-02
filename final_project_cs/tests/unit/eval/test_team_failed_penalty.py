"""★Proposed 페널티가 실제로 걸리는지 고정한다.

  이 페널티는 **한 번도 적용된 적이 없었다.** `_one()` 안에서 `success = False`
  로 정했는데, 아래쪽에서 인용 검증 결과로 rubric 을 다시 접으며
  `success = bool(judge["pass"])` 로 무조건 덮어썼다.

  그래서 `docs/evidence/DoD-15_AB_Proposed_60x3_holdout.md` 의 A/B 수치는
  의도한 판정이 빠진 채 나온 값이다. 재측정 전에는 쓰지 않는다.

  ★인라인이라 테스트를 걸 수 없었던 것이 이 결함이 오래 산 이유다.
    순수 함수로 뺐고 여기서 고정한다.

# invariant: INV-CS-EVAL-001
"""
from __future__ import annotations

import pytest

from eval.runners.common import team_failed


def test_penalty_applies_only_to_proposed():
    """★A·B 에는 이 페널티가 없다. Proposed 만 Team 을 거친다."""
    failing = {"outcome": "escalated"}
    assert team_failed("Proposed", failing, {}) is True
    assert team_failed("A", failing, {}) is False
    assert team_failed("B", failing, {}) is False


@pytest.mark.parametrize("team_result", [
    {"outcome": "escalated"},
    {"outcome": "failed"},
    {"failure_code": "provider_timeout"},
    {"warnings": ["partial evidence"]},
])
def test_team_that_did_not_finish_is_penalised(team_result):
    assert team_failed("Proposed", team_result, {}) is True


def test_degraded_context_is_penalised():
    """★근거가 모자란 채 답을 냈으면 성공으로 세지 않는다."""
    assert team_failed("Proposed", {"outcome": "resolved"}, {"degraded": True}) is True


def test_clean_run_is_not_penalised():
    assert team_failed("Proposed", {"outcome": "resolved"}, {"degraded": False}) is False


def test_missing_team_result_is_not_penalised():
    """★Team 결과가 없는 것과 Team 이 실패한 것은 다르다.

    없으면 penalty 를 걸 근거가 없다. degraded 로 따로 잡힌다.
    """
    assert team_failed("Proposed", None, {}) is False


def test_penalty_reaches_success_in_the_runner():
    """★이 테스트가 원래 결함을 잡는다.

    `_one()` 이 rubric 을 다시 접은 **뒤에** 페널티를 걸어야 한다.
    순서가 뒤집히면 페널티가 다시 죽는다.
    """
    import inspect

    from eval.runners import common

    src = inspect.getsource(common._one)
    last_pass = src.rfind('judge["pass"] =')
    penalty = src.rfind("if penalised:")
    assert last_pass != -1 and penalty != -1
    assert penalty > last_pass, (
        "team_failed 페널티가 rubric 재계산보다 먼저 걸린다. "
        "그러면 success 가 덮어써져 페널티가 죽는다"
    )
