from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.conversation.decision_unit import Decision
from app.domains.travel_ops.components.conversation.fact_context import named_items, resolve

NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


def test_each_explicit_alias_target_survives_other_read_name():
    from dataclasses import replace

    market, tower = _item("시민시장"), _item("도심전망대")
    decision = replace(_decision(tower), fact="duration", reads=[{"reference": "explicit"}])
    got, focus, stale = resolve(decision, items=[market, tower],
        message="시민시장 주소랑 전망대 머무는 시간 알려줘", selected=None,
        turns=[], version=1, now=NOW, ttl_seconds=1800)
    assert got.item is tower and not stale
    assert focus["item_id"] == str(tower.item_id)


def _item(name):
    return SimpleNamespace(item_id=uuid4(), title=name, kind="activity", place={"name": name})


def _decision(item=None, action="answer_fact"):
    return Decision(action=action, item=item, change=None, fact="detail", minutes=None, question="")


def _resolve(message="자세히 알려줘", **kw):
    first, second = _item("N서울타워"), _item("경복궁 관람")
    turns = [{"role": "assistant", "reply": {"focus": {"item_id": str(first.item_id), "version": 1, "at": NOW.isoformat()}}}]
    args = dict(items=[first, second], message=message, selected=None, turns=turns, version=1, now=NOW, ttl_seconds=1800)
    args.update(kw)
    return first, second, resolve(_decision(), **args)


@pytest.mark.parametrize("text", ["서울 타워 저거 뭐야?", "N 서울 타워 주소 알려줘", "n서울타워 상세 알려줘"])
def test_spacing_case_and_mixed_script_names(text):
    first, _, (decision, focus, stale) = _resolve(text)
    assert decision.item is first and focus["source"] == "message" and not stale


@pytest.mark.parametrize("text", ["자세히 알려줘", "거기 알려줘", "그거 자세히 알려 줘", "그건 뭐야?"])
def test_short_followup_uses_structured_previous_fact(text):
    first, _, (decision, focus, stale) = _resolve(text)
    assert decision.item is first and focus["source"] == "previous_fact" and not stale


@pytest.mark.parametrize("kw", [{"version": 2}, {"now": NOW + timedelta(minutes=31)}, {"now": NOW - timedelta(seconds=1)}, {"turns": []},
                              {"turns": [{"role": "assistant", "reply": {}}]}])
def test_version_time_and_unrelated_turn_invalidate_focus(kw):
    _, _, (decision, focus, _) = _resolve(**kw)
    assert decision.item is None and focus is None


@pytest.mark.parametrize("text", ["내일 자세히 알려줘", "2일차 상세 알려줘", "15:00 상세 알려줘", "다른 관광지 자세히 알려줘"])
def test_new_scope_does_not_inherit_old_target(text):
    _, _, (decision, focus, _) = _resolve(text)
    assert decision.item is None and focus is None


def test_unknown_id_and_write_actions_never_use_fact_focus():
    _, _, (decision, focus, stale) = _resolve(selected=uuid4())
    assert stale and decision.item is None and focus is None
    item = _item("경복궁")
    write = _decision(action="apply_change")
    assert resolve(write, items=[item], message="그거 바꿔", selected=None, turns=[], version=1, now=NOW, ttl_seconds=1800) == (write, None, False)


def test_names_shared_by_two_dates_are_ambiguous():
    items = [_item("경복궁"), _item("경복궁")]
    assert len(named_items(items, "경복궁 알려줘")) == 2


def test_bare_followup_uses_verified_focus_over_a_different_model_guess():
    first, second = _item("경복궁"), _item("서울숲")
    turns = [{"role": "assistant", "reply": {"focus": {"item_id": str(first.item_id), "version": 1, "at": NOW.isoformat()}}}]
    decision, focus, stale = resolve(_decision(second), items=[first, second], message="그거 자세히 알려줘",
                                    selected=None, turns=turns, version=1, now=NOW, ttl_seconds=1800)
    assert decision.item is first and focus["source"] == "previous_fact" and not stale


def test_model_guess_cannot_bypass_focus_expiry():
    item = _item("경복궁")
    turns = [{"role": "assistant", "reply": {"focus": {"item_id": str(item.item_id), "version": 1, "at": NOW.isoformat()}}}]
    decision, focus, stale = resolve(_decision(item), items=[item], message="자세히 알려줘", selected=None,
                                    turns=turns, version=2, now=NOW, ttl_seconds=1800)
    assert decision.item is None and focus is None and stale


def _previous(item):
    from dataclasses import replace
    return replace(_decision(item), fact="time", reads=[{"reference": "previous"}])


def test_a_self_contained_question_marked_previous_uses_the_model_target_when_there_is_no_previous():
    """★`[2026-10-14]` 「내일 첫 일정 몇 시야?」를 모델이 「앞에서 말한 것」으로 적어도, 앞 대상이 없으면 모델이 고른 일정으로 답한다."""
    first, second = _item("남산서울타워"), _item("명동교자")
    decision, focus, stale = resolve(_previous(first), items=[first, second], message="내일 첫 일정 몇 시야?", selected=None,
                                    turns=[], version=1, now=NOW, ttl_seconds=1800)
    assert decision.item is first and focus["source"] in ("decision", "decision_without_previous") and not stale


def test_a_question_that_names_a_time_does_not_inherit_the_previous_target_even_if_marked_previous():
    first, second = _item("경복궁 관람"), _item("온지음")
    turns = [{"role": "assistant", "reply": {"focus": {"item_id": str(first.item_id), "version": 1, "at": NOW.isoformat()}}}]
    decision, focus, stale = resolve(_previous(second), items=[first, second], message="12시 반에 뭐 해?", selected=None,
                                    turns=turns, version=1, now=NOW, ttl_seconds=1800)
    assert decision.item is second and focus["source"] == "decision" and not stale


def test_a_bare_followup_still_never_falls_back_to_the_model_guess():
    first = _item("경복궁")
    decision, focus, stale = resolve(_previous(first), items=[first], message="거기 알려줘", selected=None,
                                    turns=[], version=1, now=NOW, ttl_seconds=1800)
    assert decision.item is None and focus is None and stale


def test_a_pointing_followup_without_a_previous_target_is_asked_back_not_guessed():
    first = _item("성수 점심")
    decision, focus, stale = resolve(_previous(first), items=[first], message="그쪽 몇 시까지 열어?", selected=None,
                                    turns=[], version=1, now=NOW, ttl_seconds=1800)
    assert decision.item is None and focus is None and stale
