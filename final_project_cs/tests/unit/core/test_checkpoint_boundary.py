"""checkpoint 는 실행 snapshot 이다 — 2026-09-01 추가.

`CaseService.checkpoint` 반환값에 `status="running"` 을 끼워 넣어도 전체 470개가
전부 통과했다. 규칙은 "checkpoint 는 버려도 되는 실행 스냅샷이고, 권위 있는
projection 은 customer_cases 다"(CLAUDE.md §0.3).

checkpoint 가 업무 상태를 들고 다니기 시작하면 어느 쪽이 진짜인지 모르게 된다.
그래서 **무엇이 들어 있는지**를 고정한다.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.case_service import CaseService

#: checkpoint 에 있어도 되는 것. 전부 실행에 관한 값이다.
ALLOWED_KEYS = {"case_id", "run_id", "graph_revision", "node_name", "runtime_state"}

#: 업무 상태의 이름들. **최상위**에 나타나면 경계가 무너진 것이다.
#
# ★runtime_state **안**에는 같은 이름이 정당하게 들어갈 수 있다.
#   docs/evidence/_raw/DoD-04_v2.md 에 runtime_state={'case_version':2,'status':'routing'}
#   이 정상 예로 기록돼 있다. 실행 스냅샷은 관찰한 값을 담을 수 있고, 금지되는 것은
#   그것을 권위 있는 projection 으로 쓰거나 복원하는 것이다.
#   계약은 docs/evidence/DoD-04_checkpoint_projection_분리.md 의 "최상위 다섯 키" 다.
BUSINESS_KEYS = {"status", "intent", "issue_code", "sentiment", "owner_team_id",
                 "version", "state_json", "answer", "evidence"}


def make_checkpoint(**runtime):
    return CaseService(graph_revision="test-graph-v1").checkpoint(
        case_id=uuid4(), run_id=uuid4(), node_name="team.execute",
        runtime_state=runtime or {"case_version": 3},
    )


def test_checkpoint_has_only_execution_keys() -> None:
    checkpoint = make_checkpoint()
    assert set(checkpoint) == ALLOWED_KEYS, (
        "checkpoint 의 키가 바뀌었다. 실행에 관한 값만 들어가야 한다 — "
        "업무 상태를 넣으면 어느 쪽이 진짜인지 모르게 된다"
    )


def test_checkpoint_carries_no_business_state() -> None:
    checkpoint = make_checkpoint()
    leaked = BUSINESS_KEYS & set(checkpoint)
    assert not leaked, f"checkpoint 최상위에 업무 상태가 있다: {sorted(leaked)}"


def test_runtime_state_may_carry_observed_values() -> None:
    """실행 스냅샷 안에는 관찰한 값이 들어가도 된다 — DoD-04 가 그 예를 기록하고 있다.

    위 테스트가 '업무 상태 이름은 어디에도 없어야 한다' 로 과잉되지 않게 막는 대조군이다.
    """
    checkpoint = make_checkpoint(case_version=2, status="routing")
    assert checkpoint["runtime_state"] == {"case_version": 2, "status": "routing"}


def test_checkpoint_uses_the_injected_revision() -> None:
    """산출물에 버전을 박는다 — 고정 문자열이 아니라 주입된 값이어야 한다."""
    assert make_checkpoint()["graph_revision"] == "test-graph-v1"


def test_checkpoint_copies_the_runtime_state() -> None:
    """돌려준 것을 고쳐도 호출자의 것이 바뀌지 않아야 한다."""
    given = {"case_version": 3}
    checkpoint = CaseService().checkpoint(
        case_id=uuid4(), run_id=uuid4(), node_name="n", runtime_state=given)
    checkpoint["runtime_state"]["case_version"] = -1
    assert given["case_version"] == 3
