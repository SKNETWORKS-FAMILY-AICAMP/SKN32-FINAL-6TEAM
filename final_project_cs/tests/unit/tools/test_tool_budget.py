"""도구 호출 예산이 **실제로 막는지** 본다.

★2026-09-09 — `manifest.max_steps` 는 **선언만 되고 아무도 강제하지 않았다.**
  전수 조사: 정의(`contracts.py`) · introspection · 화면 표시 · 그리고
  `assert manifest.max_steps == 6` 이라는 테스트까지 있었는데, 실행 경로
  세 곳(executor · controller · read_tools)에는 **0회**였다.

  ★**테스트가 있어서 더 나빴다.** 그 테스트는 **선언값**을 봤지 **강제**를 안 봤다.
  초록불이 켜져 있어 "검증됐다" 고 읽혔다. 그래서 이 파일은
  **선언이 아니라 동작**을 본다 — 예산을 넘기면 실제로 예외가 나는지.

  경위: `wiki/records/reports/debugs/2026-09-09_max_steps가_강제되지_않는다.md`
  근거: arXiv 2601.03328 이 지적한 loop divergence — "최대 반복 횟수를 강제하라"

★막는 것만 보면 안 된다. **예산 안에서는 통과하는지**도 함께 본다 —
  관문이 항상 막는 상태여도 "막힌다" 테스트는 통과하기 때문이다.
"""
from __future__ import annotations

import pytest

from app.core.contracts import ToolNotAllowed
from app.tools.read_tools import ReadToolbox, ToolBudgetExceeded, ToolLoopExceeded

ALLOWED = ["read.policy", "read.order"]


def _toolbox() -> ReadToolbox:
    # 커넥션은 안 쓴다 — 예산·중복 검사는 DB 에 닿기 전에 끝난다.
    return ReadToolbox(lambda: None)


def test_budget_none_keeps_the_old_behaviour():
    """★기본값이 `None` 이면 예전과 똑같이 동작한다.

    이걸 먼저 고정한다 — 이 인자를 더하면서 기존 호출부 18곳을 안 고쳤으므로,
    안 넘겼을 때 동작이 바뀌면 그 전부가 조용히 깨진다.
    """
    toolbox, seen = _toolbox(), set()
    # 예산이 없으면 호출 수와 무관하게 예산 예외가 나지 않는다.
    for index in range(20):
        with pytest.raises(Exception) as caught:
            toolbox.call("read.policy", None, {"q": index}, ALLOWED, seen)
        assert not isinstance(caught.value, ToolBudgetExceeded)
    assert len(seen) == 20


def test_calls_within_budget_are_not_blocked_by_budget():
    """예산 안의 호출은 **예산 때문에** 막히지 않는다.

    ★막는 것만 검사하면 관문이 전부 막는 상태여도 통과한다.
    """
    toolbox, seen = _toolbox(), set()
    for index in range(3):
        with pytest.raises(Exception) as caught:
            toolbox.call("read.policy", None, {"q": index}, ALLOWED, seen, budget=3)
        assert not isinstance(caught.value, ToolBudgetExceeded), (
            f"{index + 1}번째 호출이 예산 3 안인데 예산으로 막혔다")
    assert len(seen) == 3


def test_budget_blocks_the_call_that_exceeds_it():
    """★예산을 채우면 **다음 호출**이 막힌다 — 다른 인자여도 막힌다.

    이게 `seen` 중복 차단만으로는 못 막던 경로다.
    """
    toolbox, seen = _toolbox(), set()
    for index in range(2):
        with pytest.raises(Exception):
            toolbox.call("read.policy", None, {"q": index}, ALLOWED, seen, budget=2)
    assert len(seen) == 2

    with pytest.raises(ToolBudgetExceeded) as caught:
        toolbox.call("read.policy", None, {"q": "새 인자"}, ALLOWED, seen, budget=2)
    assert "budget 2" in str(caught.value)


def test_budget_and_loop_guard_are_different_exceptions():
    """중복과 예산 초과는 **다른 예외**다. 원인이 달라 로그에서 갈려야 한다."""
    toolbox, seen = _toolbox(), set()
    with pytest.raises(Exception):
        toolbox.call("read.policy", None, {"q": 1}, ALLOWED, seen, budget=5)

    # 같은 인자로 다시 → 중복
    with pytest.raises(ToolLoopExceeded):
        toolbox.call("read.policy", None, {"q": 1}, ALLOWED, seen, budget=5)


def test_permission_is_checked_before_budget():
    """★권한 없는 도구는 **예산과 무관하게** 거부된다.

    예산을 먼저 보면 "예산이 없어서 못 썼다" 로 보고돼 원인을 잘못 전한다.
    """
    toolbox, seen = _toolbox(), set()
    with pytest.raises(ToolNotAllowed):
        toolbox.call("read.shipment", None, {}, ALLOWED, seen, budget=0)
