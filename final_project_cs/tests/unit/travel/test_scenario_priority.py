# -*- coding: utf-8 -*-
"""시연용 순위(`scenario_priority`) — 시나리오 모드는 대본대로 도는 데모 모드다. `[2026-09-28 사용자 지시]`

★실서비스 규칙이 바뀌자(식당 가격을 순위에서 뺐다) 시나리오의 대체 식당이 대본과 달라졌다. 대본 장소에 순위를 두어
  대본이 고른 곳이 먼저 골라지게 한다. ★탈락한 곳은 살리지 못하고, 순위가 없는 실제 장소끼리는 예전 순서 그대로다."""
from __future__ import annotations

from app.domains.travel_ops.components.planning.replan import Candidate, choose


def _cand(key, *, walk, priority=None, rejected=()):
    attributes = {} if priority is None else {"scenario_priority": priority}
    return Candidate(key=key, place={"name": key, "attributes": attributes}, changed_items=1, extra_cost_krw=None,
                     shift_minutes=0, walk_min=walk, rejected=list(rejected))


def test_the_scripted_place_wins_among_places_that_passed():
    best, others, _ = choose([_cand("국수", walk=6, priority=2), _cand("브런치", walk=6, priority=1)])
    assert best.key == "브런치" and [c.key for c in others] == ["국수"]


def test_the_scripted_place_cannot_revive_a_rejected_one():
    best, _, rejected = choose([_cand("브런치", walk=6, priority=1, rejected=["그 시각 영업하지 않는다"]),
                                _cand("국수", walk=6, priority=2)])
    assert best.key == "국수" and [c.key for c in rejected] == ["브런치"]


def test_real_places_without_a_priority_keep_the_old_order():
    best, _, _ = choose([_cand("먼 곳", walk=9), _cand("가까운 곳", walk=4)])
    assert best.key == "가까운 곳"
