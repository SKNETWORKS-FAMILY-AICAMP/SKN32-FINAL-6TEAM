"""활동 규정 검색 질문 변환 — 사전만 쓰고, 원문을 지우지 않고, 걸리는 게 없으면 그대로 둔다(2026-10-14)."""
from __future__ import annotations

import pytest

from app.domains.travel_ops.instances.activity.policy_query import expand_policy_query


@pytest.mark.parametrize("text, term", [
    ("할아버지 상을 당해서 여행을 못 가요", "3촌 이내 친족 사망"),
    ("태풍 때문에 비행기가 결항됐어요", "천재지변"),
    ("골프연습장 3개월권을 끊었다가 그만두려고요", "이용료 위약금"),
    ("콘서트를 하루 전에 취소하면 얼마 돌려받나요", "공연 입장료"),
    ("여행사가 최소 인원이 안 됐다고 취소했어요", "계약금 100% 배상"),
])
def test_known_expressions_get_document_terms(text, term):
    out = expand_policy_query(text)
    assert out.startswith(text)                      # 원문은 그대로 앞에 둔다
    assert term in out


def test_unknown_question_is_untouched():
    assert expand_policy_query("영업시간이 어떻게 되나요") == "영업시간이 어떻게 되나요"
    assert expand_policy_query("") == ""


def test_appends_at_most_three_rules():
    q = "할아버지 상을 당했고 입원도 했고 몸이 아프고 태풍도 와요"
    assert len(expand_policy_query(q)) - len(q) < 200


def test_mode_off_leaves_query(monkeypatch):
    from app.domains.travel_ops.instances.activity.team import ActivityTeam

    class _G:
        def get(self, key):
            return "off" if key == "travel.activity_policy_query.mode" else None

    monkeypatch.setattr("app.core.settings.get_guardrails", lambda: _G())
    assert ActivityTeam._policy_query("할아버지 상을 당해서") == "할아버지 상을 당해서"
