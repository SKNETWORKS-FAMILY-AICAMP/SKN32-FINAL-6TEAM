"""채팅 업무의 담당 팀은 근거(대상 일정 · 되묻기 후보 · 되돌릴 판의 바뀐 일정)로만 정한다 — 근거가 없으면 활동 팀에 넣지 않고 되묻는다.

계약(wiki `external/chat-inquiry-guide.md` 「담당 근거가 없을 때」): 두 축 라우팅의 대상 축이 비면 `activity` 기본 배정(무음 폴백)을 하지 않는다.
"""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4


NOW = datetime(2031, 3, 10, 0, 0, tzinfo=timezone.utc)


def _item(kind, title, hours, *, place=True, place_id=None):
    return SimpleNamespace(item_id=uuid4(), title=title, kind=kind, seq=hours, detail={},
                           starts_at=NOW + timedelta(hours=hours), ends_at=NOW + timedelta(hours=hours, minutes=50),
                           place={"name": title, "place_id": place_id or str(uuid4())} if place else None,
                           place_id=place_id)


def _store(items, *, versions=None, version_items=None, version=5):
    trip = {"trip_id": uuid4(), "customer_id": uuid4(), "version": version}
    history = versions if versions is not None else [{"version": v, "reason": "customer_request", "causes": [],
                                                      "created_at": NOW} for v in range(1, version + 1)]
    return trip, SimpleNamespace(latest=lambda *a: (trip, items), versions=lambda *a: history,
                                 items=lambda conn, trip_id, v: (version_items or {}).get(v, items))


def _decision(action, *, item=None, change=None, choices=None, question=""):
    from app.domains.travel_ops.components.conversation import decision_unit as du

    return du.Decision(action, item, change, "none", None, question, choices=choices or [])


def _plan(decision, items, store, trip, message="바꿔 줘"):
    from app.domains.travel_ops.components.conversation import trip_messages as tm

    return tm._dispatch_decision(object(), controller=None, tenant="t", trip_id=trip["trip_id"], case_id=uuid4(),
                                 message=message, at=NOW, store=store, items=items, decision=decision,
                                 selected=None, actor_id="a", desk=None, prepare_only=True)


def test_targetless_change_is_asked_across_kinds_and_owned_by_the_chosen_kind_not_activity():
    lunch = _item("dining", "명동교자 점심", 3)
    trip, store = _store([lunch])
    plan = _plan(_decision("apply_change"), [lunch], store, trip)
    request = plan["subject_ref"]["request"]
    assert plan["team_id"] == "dining"
    assert request["action"] == "clarify" and request["pending_action"] == "apply_change"
    assert [c["item_id"] for c in request["choices"]] == [str(lunch.item_id)]


def test_clarify_owner_comes_from_the_first_choice_that_points_at_an_item():
    lunch = _item("dining", "명동교자 점심", 3)
    choices = [{"action": "answer_fact", "item": None, "change": None, "fact": "weather"},
               {"action": "apply_change", "item": lunch, "change": None, "fact": "none"}]
    trip, store = _store([lunch])
    plan = _plan(_decision("clarify", choices=choices), [lunch], store, trip)
    assert plan["team_id"] == "dining"


def test_clarify_without_any_kind_evidence_is_not_given_to_activity():
    walk = _item("mobility", "이동", 1, place=False)
    trip, store = _store([walk])
    plan = _plan(_decision("clarify"), [walk], store, trip)
    assert plan["team_id"] is None
    assert plan["outcome"]["status"] == "clarify" and plan["outcome"]["text"]


def test_version_rollback_is_owned_by_the_kind_of_the_items_it_restores():
    lunch, palace = _item("dining", "명동교자 점심", 3), _item("activity", "경복궁 관람", 1)
    old_lunch = SimpleNamespace(**{**vars(lunch), "place": {"name": "옛 식당", "place_id": str(uuid4())}, "title": "옛 식당"})
    trip, store = _store([palace, lunch], version_items={2: [palace, old_lunch]})
    plan = _plan(_decision("rollback"), [palace, lunch], store, trip, message="2번 일정으로 되돌려 줘")
    assert plan["subject_ref"]["request"]["to_version"] == 2
    assert plan["team_id"] == "dining"


def test_version_rollback_spanning_two_kinds_is_asked_not_given_to_activity():
    lunch, palace = _item("dining", "명동교자 점심", 3), _item("activity", "경복궁 관람", 1)
    old_lunch = SimpleNamespace(**{**vars(lunch), "starts_at": lunch.starts_at + timedelta(hours=1)})
    old_palace = SimpleNamespace(**{**vars(palace), "place": {"name": "덕수궁", "place_id": str(uuid4())}, "title": "덕수궁"})
    trip, store = _store([palace, lunch], version_items={2: [old_palace, old_lunch]})
    plan = _plan(_decision("rollback"), [palace, lunch], store, trip, message="2번 일정으로 되돌려 줘")
    assert plan["team_id"] is None
    assert plan["outcome"]["status"] == "clarify"
    assert "일정은 바꾸지 않았어요" in plan["outcome"]["text"]


def test_item_kind_owner_is_unchanged():
    lunch = _item("dining", "명동교자 점심", 3)
    trip, store = _store([lunch])
    assert _plan(_decision("apply_change", item=lunch), [lunch], store, trip)["team_id"] == "dining"


def test_unresolved_owner_is_answered_as_a_question_without_any_team_dispatch(monkeypatch):
    from app.application import classification
    from app.core import settings, transition
    from app.core.case_lifecycle.events import EventType
    from app.domains.travel_ops.components.conversation import case_dispatch, chat_log, trip_messages as tm
    from app.infrastructure.db import repository

    walk = _item("mobility", "이동", 1, place=False)
    trip, store = _store([walk])
    conn = SimpleNamespace(commit=lambda: None, transaction=lambda: nullcontext())
    moves, patches = [], []
    monkeypatch.setattr(tm, "get_connection", lambda: nullcontext(conn))
    monkeypatch.setattr(repository, "get_case", lambda *a, **kw: {"version": 1, "status": "routing"})

    def classify(*a, **kw):
        patches.append(kw.get("state_patch"))
        return EventType.CLASSIFIED
    monkeypatch.setattr(classification, "classify_case", classify)
    monkeypatch.setattr(transition, "transition_case", lambda *a, **kw: moves.append((kw["event_type"], kw["payload"])))
    monkeypatch.setattr(settings, "get_guardrails", lambda: SimpleNamespace(get=lambda key: 1800))
    monkeypatch.setattr(chat_log, "recent", lambda *a, **kw: [])

    def never(*a, **kw):
        raise AssertionError("담당 근거가 없는 업무를 팀에 보냈다")
    monkeypatch.setattr(case_dispatch, "execute", never)
    result = tm._run_decision(conn, tenant="t", trip_id=trip["trip_id"], case_id=uuid4(), message="그거 바꿔 줘",
                              request_id="r", at=NOW, desk=None, store=store, items=[walk],
                              decision=_decision("clarify"), failure=None, actor_id="a", policy_search=None,
                              place_source=None, selected=None)
    assert result["status"] == "clarify" and result["answer"]
    routed = [p for e, p in moves if e is EventType.ROUTED]
    assert routed and routed[0]["owner_team_id"] == "trip_desk" and routed[0]["owner_basis"] == "unresolved"
    assert all(p.get("owner_team_id") != "activity" for _, p in moves)
    assert [e for e, _ in moves][-1] is EventType.COMPLETED
    assert patches == [None]                       # 실행 계획이 없는 업무는 재시도 계획으로 저장하지 않는다


def _run(monkeypatch, decision, items, store, trip, message):
    from app.application import classification
    from app.core import settings, transition
    from app.core.case_lifecycle.events import EventType
    from app.domains.travel_ops.components.conversation import case_dispatch, chat_log, trip_messages as tm
    from app.infrastructure.db import repository

    conn = SimpleNamespace(commit=lambda: None, transaction=lambda: nullcontext())
    moves = []
    monkeypatch.setattr(tm, "get_connection", lambda: nullcontext(conn))
    monkeypatch.setattr(repository, "get_case", lambda *a, **kw: {"version": 1, "status": "routing"})
    monkeypatch.setattr(classification, "classify_case", lambda *a, **kw: EventType.CLASSIFIED)
    monkeypatch.setattr(transition, "transition_case", lambda *a, **kw: moves.append((kw["event_type"], kw["payload"])))
    monkeypatch.setattr(settings, "get_guardrails", lambda: SimpleNamespace(get=lambda key: 1800))
    monkeypatch.setattr(chat_log, "recent", lambda *a, **kw: [])

    def never(*a, **kw):
        raise AssertionError("담당 근거가 없는 업무를 팀에 보냈다")
    monkeypatch.setattr(case_dispatch, "execute", never)
    result = tm._run_decision(conn, tenant="t", trip_id=trip["trip_id"], case_id=uuid4(), message=message,
                              request_id="r", at=NOW, desk=None, store=store, items=items, decision=decision,
                              failure=None, actor_id="a", policy_search=None, place_source=None, selected=None)
    return result, moves


def test_targetless_rollback_with_nothing_to_undo_keeps_the_finished_answer(monkeypatch):
    """role-manager c286b906 「되돌릴 변경이 없어요」(끝난 답)는 담당 근거가 없어도 그대로다 — 「한 종류로 정하지 못해」 되묻기로 바꾸지 않는다.

    ☆이식 중 발견(2026-10-26 L01 → role-manager): 대상 없는 되돌리기 + 처음 판 그대로(`latest <= 1`)는 `to_version` 이 없어
    담당 근거가 없다고 판정되어 고객 답이 「되돌리면 바뀌는 일정을 한 종류(식사 · 활동 등)로 정하지 못해 …」로 바뀌었다.
    """
    from app.core.case_lifecycle.events import EventType
    from app.domains.travel_ops.components.conversation import trip_messages as tm

    lunch = _item("dining", "명동교자 점심", 3)
    trip, store = _store([lunch], version=1)
    monkeypatch.setattr(tm, "get_connection", lambda: nullcontext(object()))
    plan = _plan(_decision("rollback"), [lunch], store, trip, message="되돌려 줘")
    assert plan["team_id"] is None
    assert plan["outcome"]["status"] == "answered" and plan["outcome"]["reason"] == "nothing_to_undo"
    assert "되돌릴 변경이 없어요" in plan["outcome"]["text"] and "한 종류" not in plan["outcome"]["text"]

    result, moves = _run(monkeypatch, _decision("rollback"), [lunch], store, trip, "되돌려 줘")
    assert result["status"] == "answered" and "되돌릴 변경이 없어요" in result["answer"]
    from app.domains.travel_ops.components.conversation import trip_replies
    assert trip_replies.INQUIRY_GUIDE not in trip_replies.with_inquiry_guide(result)["answer"]   # 끝난 답 — 문의함 안내 없음
    assert [e for e, _ in moves][-1] is EventType.COMPLETED
    assert all(p.get("owner_team_id") != "activity" for _, p in moves)
