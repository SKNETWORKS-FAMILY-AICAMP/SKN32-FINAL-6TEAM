# -*- coding: utf-8 -*-
"""분류기가 내는 라벨로 **실제로 팀에 도달하는지** 본다.

★2026-08-17 사고의 재발 방지. 그때 `feedback.INTENTS` 가 옛 도메인 어휘로
  남아 있었는데 이 함수가 **운영 REST API 의 기본 분류기**였다 — 새 도메인의
  Case 는 전부 분류 실패로 떨어졌을 것이다. 커머스판 검사는
  `tests/unit/voc/test_feedback_intent_alignment.py` 였다.

★그때보다 한 겹 더 본다. 커머스판은 `INTENTS ⊇ accepted_case_types` 만 봤는데,
  **라우팅이 두 축이 되면서 그 검사로는 부족해졌다**(v11 §5-B). 지금 팀을
  고르는 것은 `intent` 가 아니라 `issue_code` 의 **접두**다. 그래서 접두를 센다.

★2026-09-09 실측으로 확인된 실패: 요청 종류 다섯(`itinerary_submit` 등)을
  `case_type` 자리에 넣으면 여섯 팀 어디에도 도달하지 못한다.
"""
from __future__ import annotations

import pytest

from app.application.routing import case_type_of
from app.composition import build_registry
from app.modules.travel_ops.feedback import INTENTS, ISSUE_CODES


def _registered_case_types() -> set[str]:
    types: set[str] = set()
    for manifest in build_registry().manifests():
        types |= {value.lower() for value in manifest.accepted_case_types}
    return types


def test_there_is_something_to_check():
    """★빈 집합끼리 비교하면 아래 검사가 전부 통과한다."""
    assert _registered_case_types(), "등록된 Team 이 없다 — config/project.yaml 확인"
    assert ISSUE_CODES and INTENTS


def test_every_routable_case_type_has_at_least_one_issue_code():
    """팀이 받는 `case_type` 마다 그것을 **낼 수 있는** issue_code 가 있어야 한다.

    없으면 그 팀은 등록만 돼 있고 **영원히 Case 를 못 받는다.**
    """
    producible = {case_type_of(code) for code in ISSUE_CODES}
    unreachable = sorted(_registered_case_types() - producible)
    assert not unreachable, (
        f"등록됐지만 분류기가 도달시킬 수 없는 Team 의 case_type: {unreachable}\n"
        f"  분류기가 낼 수 있는 접두: {sorted(producible)}\n"
        f"  → `app/modules/travel_ops/feedback.py::ISSUE_CODES` 에 그 접두의 "
        f"코드를 넣거나, 그 팀을 등록에서 뺀다.")


@pytest.mark.parametrize("issue_code", sorted(ISSUE_CODES))
def test_every_issue_code_either_routes_or_is_deliberately_unroutable(issue_code: str):
    """접두가 어느 팀과도 안 맞는 코드는 **`other` 하나뿐**이어야 한다.

    ★오타 한 글자(`activty_...`)면 그 갈래의 Case 가 전부 조용히 escalate 된다.
      `other` 는 의도된 미도달이다 — 모르는 것을 아무 팀에나 보내지 않는다.
    """
    case_type = case_type_of(issue_code)
    if case_type in _registered_case_types():
        return
    assert issue_code == "other", (
        f"issue_code '{issue_code}' 의 접두 '{case_type}' 를 받는 Team 이 없다. "
        f"오타이거나 등록에서 빠진 팀이다. 등록된 case_type: "
        f"{sorted(_registered_case_types())}")


def test_request_kinds_are_not_used_as_case_types():
    """★요청 종류(intent)를 `case_type` 자리에 쓰면 안 된다 — 이것이 2026-09-09 의 실패다."""
    overlap = sorted(INTENTS & _registered_case_types())
    assert not overlap, (
        f"요청 종류 {overlap} 가 팀의 accepted_case_types 와 겹친다. "
        f"두 축이 같은 말이 되면 라우팅이 어느 축으로 됐는지 알 수 없다.")
