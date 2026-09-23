# -*- coding: utf-8 -*-
"""Activity 의 **취소 판정** — 「지금 취소하면 얼마인가」. `[2026-09-23]`

★★**이 갈래에는 시험이 하나도 없었다**(2026-09-23 실측 — `tests/` 전체에서
  `check_cancelable` 이 0건). 그래서 취소 기한·위약금율이 **언제나 `None`** 인 채로
  몇 달이 지났다: `_terms_hours` 가 `read.policy` 의 청크를 `isinstance(chunk, dict)` 로
  걸렀는데 RAG 는 `PolicyChunk` 를 준다 — 그 검사가 항상 거짓이었다.
  기록 — `wiki/records/reports/debugs/2026-09-22_정책청크에서_수치를_못_꺼낸다.md`

★**픽스처가 그 결함을 가렸다.** 옛 시험의 `read.policy` 는 `[{"cancel_deadline_hours": 24}]`
  라는 **dict 목록**이었다. 실제 RAG 가 주는 모양과 달라서, 시험은 초록인데 운영은
  한 번도 안 됐다. 그래서 여기서는 **실제 도구가 주는 모양**으로만 시험한다.

재현:

    python -m pytest tests/unit/travel/test_activity_cancelable.py -v
"""
from __future__ import annotations

import pytest

from app.core.context import PolicyChunk
from app.core.contracts import NextAction
from app.modules.travel_ops.activity import ActivityTeam

from .helpers import FakeTools, in_hours, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools


def _task():
    return task("activity", "activity.check_cancelable",
                pack("activity", scope=["travel_activity"]), ALLOWED)


def _chunks():
    """`read.policy` 가 **실제로** 주는 모양 — 문장 근거지 수치가 아니다."""
    return [PolicyChunk(document_id="t_doc_01", chunk_no=3, scope="travel_activity", score=0.7,
                        content="취소는 시작 전까지 접수하고 위약금은 업체 조건을 따른다.")]


def _values(*, terms, hours_left=30.0):
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1", "kind": "activity",
                         "starts_at": in_hours(hours_left), "party_size": 2, "capacity": 4},
        "read.policy": _chunks(),
        "read.booking_terms": terms,
    }


def _terms(deadline=24, table=None, scope="booking"):
    return {"booking_id": "b1", "matched_scope": scope, "cancel_deadline_hours": deadline,
            "penalty_by_hours": table if table is not None else {"24": 0.5, "48": 0.3},
            "source": "seed:mock", "observed_at": "2026-09-23T00:00:00+00:00"}


# ── 되는 것 ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_it_finally_answers_the_penalty_rate():
    """★이 시험이 **고치기 전에는 빨갰다** — 위약금율이 언제나 `None` 이었다."""
    result = await ActivityTeam(FakeTools(_values(terms=_terms(), hours_left=30))).execute(_task())

    assert result.outcome == "completed" and result.next_action is NextAction.RESPOND
    decision = result.decisions[0]
    assert decision["cancelable"] is True
    assert decision["penalty_rate"] == 0.3          # 30시간 남음 → 48시간 구간에 걸린다
    assert "30%" in result.answer
    assert result.warnings == []


@pytest.mark.asyncio
async def test_the_tightest_bracket_wins_when_several_match():
    """★두 구간에 걸리면 **센 쪽**이다 — 적게 받았다가 더 받으면 말을 바꾸는 것이 된다.

    기한은 6시간이라 10시간 남은 지금은 **취소할 수 있고**, 24·48 두 구간에 다 걸린다.
    """
    result = await ActivityTeam(FakeTools(
        _values(terms=_terms(deadline=6), hours_left=10))).execute(_task())
    assert result.decisions[0]["cancelable"] is True
    assert result.decisions[0]["penalty_rate"] == 0.5


@pytest.mark.asyncio
async def test_missing_the_deadline_by_minutes_is_not_reported_as_the_same_number():
    """★`[실측 2026-09-23]` demo 에서 **자기모순으로 읽히는 답변**이 실제로 나왔다 —
    「6시간 전까지 취소할 수 있는데 지금은 6.0시간 남았습니다」(기한 6 · 남은 5.98).
    고객은 그걸 읽고 「그럼 되는 거 아닌가」 하고 다시 묻는다.
    """
    result = await ActivityTeam(FakeTools(
        _values(terms=_terms(deadline=6), hours_left=5.98))).execute(_task())

    assert result.decisions[0]["cancelable"] is False
    assert "6.0시간 남았습니다" not in result.answer
    assert "1분 차이로 지났습니다" in result.answer
    assert result.decisions[0]["late_by_minutes"] == 1


@pytest.mark.asyncio
async def test_past_the_deadline_it_says_no_and_shows_both_numbers():
    result = await ActivityTeam(FakeTools(
        _values(terms=_terms(deadline=48), hours_left=12))).execute(_task())
    decision = result.decisions[0]
    assert decision["cancelable"] is False and decision["deadline_hours"] == 48
    assert "48시간" in result.answer and "12.0시간" in result.answer


# ── 모르는 것 ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_without_terms_it_does_not_invent_an_amount():
    """★모르면 사람에게 간다. 지어낸 금액을 말하지 않는다(CLAUDE.md §0.1)."""
    result = await ActivityTeam(FakeTools(_values(terms=None))).execute(_task())
    assert result.outcome == "escalated"
    assert all("%" not in str(decision) for decision in result.decisions)


@pytest.mark.asyncio
async def test_a_deadline_without_a_penalty_table_answers_only_what_it_knows():
    result = await ActivityTeam(FakeTools(
        _values(terms=_terms(table={}), hours_left=30))).execute(_task())
    decision = result.decisions[0]
    assert decision["cancelable"] is True and decision["penalty_rate"] is None
    assert "금액은 안내하지 못합니다" in result.answer
    assert any("위약금율을 확인하지 못했다" in warning for warning in result.warnings)


# ── 되돌아오지 못하게 ─────────────────────────────────────────────
def test_feeding_rag_chunks_to_the_number_reader_is_refused_loudly():
    """★★**이 시험이 그 결함을 막는다.** 전에는 청크를 넘기면 조용히 `None` 이었다 —
    조용하니까 아무도 몰랐고 몇 달이 갔다. 이제는 모양이 다르면 **그렇게 말한다.**
    """
    with pytest.raises(TypeError, match="read.booking_terms"):
        ActivityTeam._terms_hours(_chunks(), "cancel_deadline_hours")
    with pytest.raises(TypeError, match="read.booking_terms"):
        ActivityTeam._penalty_rate(_chunks(), 10.0)


def test_none_is_unknown_and_stays_quiet():
    """`None`(모름)은 잘못된 모양이 아니다 — 여기서 터지면 안 된다."""
    assert ActivityTeam._terms_hours(None, "cancel_deadline_hours") is None
    assert ActivityTeam._penalty_rate(None, 10.0) is None


def test_the_numbers_never_come_from_the_policy_tool_again():
    """★`read.policy` 는 **문장 근거**만 댄다. 수치를 거기서 읽으면 또 같은 일이 난다."""
    import inspect

    source = inspect.getsource(ActivityTeam._check_cancelable)
    assert "read.policy" not in source and " policy" not in source,         "취소 판정이 다시 규정 문장에서 수치를 읽고 있다"
    assert "_terms_hours(terms" in source and "_penalty_rate(terms" in source
    assert "read.booking_terms" in ActivityTeam.manifest.allowed_tools
