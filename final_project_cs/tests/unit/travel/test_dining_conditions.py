# -*- coding: utf-8 -*-
"""동행 조건 판정(`dining.check_conditions`) — 「불가로 확인된 조건」을 충족으로 답하지 않는다. `[2026-10-06]`

★결함: 요청한 조건이 원장에서 **아닌 것으로 확인**(`dietary_absent`)되면 「모름」도 「충족」도 아닌데,
  `_conditions` 가 그 갈래를 몰라 할랄 불가 가게에 할랄을 물어도
  「요청한 조건이 없어 별도 확인 없이 진행할 수 있습니다」(또는 섞이면 「모두 만족합니다」)라고 답했다.
"""
from __future__ import annotations

import pytest

from app.modules.travel_ops.dining import DiningTeam

from .helpers import FakeTools, pack, task


def _ask(wanted: list[str], *, known: list[str], absent: list[str]):
    context = pack("dining", scope=["dining"], state={"dietary": wanted})
    request = task("dining", "dining.check_conditions", context, DiningTeam.manifest.allowed_tools)
    tools = FakeTools({
        "read.booking": {"booking_id": "b1", "place_id": "p9"},
        "read.place": {"place_id": "p9", "confirmed_at": "2026-10-06T00:00:00+00:00",
                       "dietary": known, "dietary_absent": absent},
    })
    return DiningTeam(tools).execute(request)


@pytest.mark.asyncio
async def test_a_condition_confirmed_absent_is_answered_as_not_met():
    result = await _ask(["halal"], known=[], absent=["halal"])

    assert result.outcome == "completed"
    assert result.decisions[0]["conditions_not_met"] == ["halal"]
    assert "충족하지 않" in result.answer
    assert "별도 확인 없이" not in result.answer


@pytest.mark.asyncio
async def test_one_absent_condition_is_not_hidden_behind_the_met_ones():
    result = await _ask(["vegan", "halal"], known=["vegan"], absent=["halal"])

    assert result.decisions[0]["conditions_met"] == ["vegan"]
    assert result.decisions[0]["conditions_not_met"] == ["halal"]
    assert "모두 만족" not in result.answer


@pytest.mark.asyncio
async def test_a_confirmed_absence_is_answered_even_when_another_condition_is_unknown():
    """확인된 불가가 하나라도 있으면 그 식당은 요청을 충족하지 못한다 — 모르는 것을 기다릴 필요가 없다.
    모르는 조건은 확인된 것처럼 말하지 않고 경고로 남긴다."""
    result = await _ask(["halal", "kids"], known=[], absent=["halal"])

    assert result.outcome == "completed"
    assert result.decisions[0]["conditions_not_met"] == ["halal"]
    assert result.decisions[0]["conditions_unknown"] == ["kids"]
    assert any("kids" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_only_known_conditions_are_still_answered_as_met():
    result = await _ask(["vegan"], known=["vegan"], absent=[])

    assert result.outcome == "completed"
    assert "모두 만족" in result.answer
