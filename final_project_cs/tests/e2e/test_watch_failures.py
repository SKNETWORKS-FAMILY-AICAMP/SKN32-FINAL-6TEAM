# -*- coding: utf-8 -*-
"""감시 Case 반복이 **멈추지 않고 끝을 맺는다** — 결함 인계 #1~#3·#5 (2026-10-02, 아키텍처 그림 적대 검토에서 나왔다).

☆왜: ①Case 하나의 실행이 예외로 터지면 그 회차의 남은 Case 가 전부 끊겼다 ②끝난 일정의 제안이 기본 일꾼(Case 버전)에서는 안 닫혀 `open` 으로 남고, 고르기도 만료를
안 봤다 ③바꿀 곳을 못 찾아 끝나면 고객은 아무 말도 못 들었고, 점검 소스가 잠깐 실패해 닫힌 Case 는 같은 사건에서 영원히 다시 안 열렸다 ④낡은 기준 버전의 제안이 `open` 으로 남았다.

★지키려는 것: ①한 Case 의 예외가 나머지를 끊지 않고 그 Case 는 `escalated`(`team_error`)로 닫힌다 ②Case 버전 반복도 끝난 일정의 제안을 `expired` 로 닫고
`choose` 는 끝난 · 낡은 제안을 **고르게 두지 않고 닫는다**(커밋 뒤 409) ③`itinerary_unresolved` 는 고객에게 알리되 같은 사건에 두 번 알리지 않는다
④일시 실패는 식힘 시간 뒤 다시 열고 한도(`retry_max`)를 넘으면 멈춘다 ⑤거절돼도 제안이 **열린 채** 남는 것은 의도다 — 다른 안을 고를 수 있어야 한다.

재현:

    python -m pytest tests/e2e/test_watch_failures.py -v
"""
from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import pytest

from app.core import settings as settings_module
from app.core.transition import transition_case
from app.core.case_lifecycle.events import EventType
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.planning import pending as pending_module
from app.domains.travel_ops.components.planning.pending import CONSENT_KEY, PendingStore
from app.domains.travel_ops.components.watch.trip_watch_cases import TripWatchCaseOpener

from .test_ask_first import _ask_first, _choose, _proposals
from .test_trip_api import _at, _create, api  # noqa: F401 — 픽스처를 그대로 쓴다

DISRUPTED = {"verdict": "disrupted", "disruptions": [{"category": "traffic_control", "kind": "road_closed"}]}
SAFETY = {"verdict": "disrupted", "disruptions": [{"category": "disaster_msg", "kind": "fire"}]}


def _check_activities(report):
    """활동 항목만 깨졌다고 본다 — 그 밖은 `clear`."""
    def check(*, place, starts_at):
        return report if place.get("kind") == "activity" else {"verdict": "clear", "disruptions": []}
    return check


def _opener(api, check, run_case, hhmm="09:00"):
    return TripWatchCaseOpener(store=api["store"], check=check, connection_factory=get_connection,
                               clock=lambda: _at(hhmm), repository=repository, run_case=run_case, route_events=None)


def _tick(opener):
    return opener.tick(lookahead=timedelta(hours=14))


def _case(case_id):
    with get_connection() as conn:
        return repository.get_case(conn, tenant_id=settings_module.get_settings().tenant_id, case_id=UUID(str(case_id)))


def _move(case_id, event_type, payload):
    tenant = settings_module.get_settings().tenant_id
    with get_connection() as conn, conn.transaction():
        case = repository.get_case(conn, tenant_id=tenant, case_id=UUID(str(case_id)))
        transition_case(conn, tenant_id=tenant, case_id=UUID(str(case_id)), expected_version=case["version"],
                        event_type=event_type, payload=payload, actor_type="controller", actor_id="test")


def _start(case_id):
    _move(case_id, EventType.ROUTED, {"owner_team_id": "activity", "capability": "activity.itinerary"})   # routing → running


def _escalate(case_id, guardrail, observed=None):
    _move(case_id, EventType.GUARDRAIL_ESCALATED, {"guardrail": guardrail, "observed": [observed or guardrail]})


def _guardrail(case_id):
    tenant = settings_module.get_settings().tenant_id
    with get_connection() as conn:
        events = repository.get_case_events(conn, tenant_id=tenant, case_id=UUID(str(case_id)))
    return [e["payload_json"]["guardrail"] for e in events if e["event_type"] == "guardrail_escalated"][-1]


@pytest.fixture(autouse=True)
def guardrails(monkeypatch):
    """감시 설정만 시험이 정한다 — 나머지 값은 그대로.

    ★`[2026-10-03]` 이 파일의 시험은 **항목마다 Case 가 열리는 길**을 본다(Case 하나의 예외 · 항목별 재시도 · 항목별 알림). 한 여행에서 둘 이상 깨지면 묶음 Case 로 묶이므로(`trip_watch_batch`)
    기본으로 묶음을 꺼 둔다 — 묶음 길은 `tests/e2e/test_watch_batch.py` 가 본다."""
    real = settings_module.get_guardrails()
    override: dict[str, object] = {"travel.watch.batch_enabled": False}

    class Guard:
        def get(self, key, *args):
            return override[key] if key in override else real.get(key, *args)

    monkeypatch.setattr(settings_module, "get_guardrails", lambda: Guard())
    return override


# ── ① 한 Case 의 예외가 나머지를 끊지 않는다 ──────────────────────────

# invariant: INV-CS-RT-023
def test_one_case_blowing_up_does_not_stop_the_rest_of_the_tick_and_is_closed_as_team_error(api):
    _create(api)
    ran = []

    def run_case(*, tenant_id, case_id, actor_id):
        if not ran:
            ran.append("first")
            _start(case_id)                                # Controller 처럼 실행을 시작해 `running` 이 된 뒤
            raise RuntimeError("tool budget exhausted")      # Team 이 예외를 던졌다 — 전에는 반복 전체가 여기서 끊겼다
        ran.append(case_id)
        _start(case_id)
        _move(case_id, EventType.GUARDRAIL_ESCALATED, {"guardrail": "other", "observed": ["x"]})
        return {"status": "escalated"}

    result = _tick(_opener(api, _check_activities(DISRUPTED), run_case))
    assert len(result.opened) >= 2 and len(ran) == len(result.opened)         # 열린 Case 를 **전부** 돌렸다
    [failed] = result.failed
    assert failed["error"] == "RuntimeError" and len(result.ran) == len(result.opened) - 1
    closed = _case(failed["case_id"])
    assert str(closed["status"]) == "escalated" and _guardrail(failed["case_id"]) == "team_error"   # 죽은 채 running 이 아니다


# ── ② 끝난 일정의 제안은 Case 버전 반복도 닫고, 고르기는 끝난 제안을 안 받는다 ──

def test_the_case_watch_closes_proposals_of_finished_items_without_changing_the_trip(api):
    trip_id = _ask_first(api)
    api["tick"]("09:00")                                  # 시나리오 감시가 「바꿀까요?」를 연다
    [proposal] = _proposals(api, trip_id)
    assert proposal["status"] == "open"
    result = _tick(_opener(api, _check_activities({"verdict": "clear", "disruptions": []}), None, hhmm="23:30"))
    assert [row["proposal_id"] for row in result.expired] == [str(proposal["proposal_id"])]
    [closed] = _proposals(api, trip_id)
    assert closed["status"] == "expired"
    with get_connection() as conn:
        assert api["store"].latest(conn, UUID(str(trip_id)))[0]["version"] == 1         # 바꾸지 않았다


# invariant: INV-CS-RT-024
def test_choosing_a_proposal_whose_item_has_ended_is_refused_and_the_closing_is_kept(api, monkeypatch):
    """감시가 아직 못 닫았어도 끝난 제안은 고를 수 없다 — 그리고 닫은 기록이 **남는다**(전에는 예외로 트랜잭션이 되돌아가 계속 열려 있었다)."""
    trip_id = _ask_first(api)
    api["tick"]("09:00")
    [proposal] = _proposals(api, trip_id)
    monkeypatch.setattr(pending_module, "wall_clock", lambda: _at("23:30"))      # 그 일정이 끝난 뒤(감시는 안 돌렸다)
    refused = api["client"].post(f"/v1/trips/{trip_id}/proposals/{proposal['proposal_id']}/choose",
                                 json={"key": CONSENT_KEY}, headers=api["auth"]("trip:write"))
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "expired"
    [closed] = _proposals(api, trip_id)
    assert closed["status"] == "expired" and closed["chosen_by"] == "system:ended_before_choice"
    again = api["client"].post(f"/v1/trips/{trip_id}/proposals/{proposal['proposal_id']}/choose",
                               json={"key": CONSENT_KEY}, headers=api["auth"]("trip:write"))
    assert again.json()["error"]["code"] == "already_decided"                       # 닫혔으니 두 번째는 「이미 정해졌다」


# ── ⑤ 낡은 기준 버전 · 거절돼도 열린 채 두는 것은 의도 ─────────────────────

def test_a_stale_proposal_is_closed_for_good_through_the_rest_path(api):
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore  # noqa: F401

    trip_id = _ask_first(api)
    api["tick"]("09:00")
    [proposal] = _proposals(api, trip_id)
    store = api["store"]
    with get_connection() as conn, conn.transaction():
        trip, items = store.latest(conn, trip_id)
        store.append_version(conn, trip_id=trip_id, base_version=trip["version"], items=items,
                             reason="test_other_change", causes=[])
    stale = api["client"].post(f"/v1/trips/{trip_id}/proposals/{proposal['proposal_id']}/choose",
                               json={"key": CONSENT_KEY}, headers=api["auth"]("trip:write"))
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale"
    [closed] = _proposals(api, trip_id)
    assert closed["status"] == "superseded"           # ★409 를 돌려주고도 닫힌 채 남는다(커밋 뒤에 알린다)


def test_a_refused_option_leaves_the_proposal_open_so_another_option_can_be_chosen(api):
    """의도다(결함 인계 #5 확인): 고른 안이 지금 안 맞아 거절되면 제안은 그대로 열려 있다 — 같은 제안에서 다른 안을 고를 수 있어야 한다."""
    from app.domains.travel_ops.components.planning.pending import ProposalRefused

    trip_id = _ask_first(api)
    api["tick"]("09:00")
    [proposal] = _proposals(api, trip_id)
    with pytest.raises(ProposalRefused) as refused:
        _choose(api, trip_id, proposal["proposal_id"], "some-place-id")             # 동의 전에 안 키를 골랐다
    assert refused.value.code == "unknown_option"
    [still] = _proposals(api, trip_id)
    assert still["status"] == "open"


# ── ③ 바꿀 곳이 없으면 고객에게 알린다 · 일시 실패는 다시 연다 ───────────────

def _escalating(guardrail, calls=None, observed=None):
    def run_case(*, tenant_id, case_id, actor_id):
        if calls is not None:
            calls.append(case_id)
        _start(case_id)
        _escalate(case_id, guardrail, observed)
        return {"status": "escalated"}
    return run_case


def _notices(api):
    return [payload for _, payload in api["notices"]()]


def test_when_no_alternative_exists_the_customer_is_told_once_and_the_trip_is_left_as_it_is(api):
    trip_id = _create(api)["trip_id"]
    before = len(_notices(api))
    opener = _opener(api, _check_activities(DISRUPTED), _escalating("itinerary_unresolved"))
    first = _tick(opener)
    assert first.notified and len(first.notified) == len(first.opened)               # 열린 Case 마다 한 건씩
    sent = [n for n in _notices(api)[before:] if n.get("kind") == "no_alternate"]
    assert len(sent) == len(first.notified)
    note = sent[0]
    assert note["type"] == "guidance" and "일정은 그대로 두었어요" in note["text"]
    assert "도로가 통제돼요" in note["text"] and "road_closed" not in note["text"]           # ★`[2026-10-03]` 원인 코드 이름(영문)이 고객 문장에 새지 않는다 — 전에는 이 시험이 새는 것을 못 박고 있었다
    assert "사람" not in note["text"] and "담당자" not in note["text"]                  # 사람 대기 약속은 하지 않는다
    # 같은 사건이 그대로면 다시 알리지 않는다(같은 Case 로 모인다)
    second = _tick(opener)
    assert second.notified == [] and len([n for n in _notices(api)[before:] if n.get("kind") == "no_alternate"]) == len(sent)
    with get_connection() as conn:
        assert api["store"].latest(conn, UUID(trip_id))[0]["version"] == 1              # 일정은 안 바뀌었다


def test_a_safety_event_with_no_alternative_is_announced_as_a_safety_alert(api):
    _create(api)
    before = len(_notices(api))
    _tick(_opener(api, _check_activities(SAFETY), _escalating("itinerary_unresolved")))
    sent = [n for n in _notices(api)[before:] if n.get("kind") == "no_alternate"]
    assert sent and all(n["type"] == "safety_alert" and n["text"].startswith("⚠️ 안전 알림") for n in sent)


def test_a_transient_failure_is_reopened_after_the_cooldown_until_the_limit(api, guardrails):
    _create(api)
    guardrails.update({"travel.watch.retry_cooldown_seconds": 0, "travel.watch.retry_max": 1})
    calls: list = []
    opener = _opener(api, _check_activities(DISRUPTED), _escalating("fatal_source_failure", calls))
    first = _tick(opener)
    n = len(first.opened)
    assert n >= 1 and len(calls) == n and first.retried == []
    # 같은 사건 · 앞 Case 가 일시 실패로 닫혔다 — 다음 회차가 **다시 연다**(전에는 같은 지문의 닫힌 Case 가 영원히 막았다)
    second = _tick(opener)
    assert len(second.opened) == n and len(second.retried) == n and {r["attempt"] for r in second.retried} == {1}
    # 한도(retry_max=1)를 넘으면 더 안 연다 — 이제는 운영자 몫(escalated 로 남는다)
    third = _tick(opener)
    assert third.opened == [] and third.retried == [] and len(third.existing) == n


def test_the_cooldown_keeps_a_failing_source_from_being_asked_every_minute(api, guardrails):
    _create(api)
    guardrails.update({"travel.watch.retry_cooldown_seconds": 3600, "travel.watch.retry_max": 3})
    opener = _opener(api, _check_activities(DISRUPTED), _escalating("fatal_source_failure"))
    first = _tick(opener)
    second = _tick(opener)
    assert first.opened and second.opened == [] and second.retried == []             # 식힘 시간이 안 지났다


def test_unresolved_is_never_reopened_because_the_same_event_gives_the_same_answer(api, guardrails):
    _create(api)
    guardrails.update({"travel.watch.retry_cooldown_seconds": 0, "travel.watch.retry_max": 3})
    opener = _opener(api, _check_activities(DISRUPTED), _escalating("itinerary_unresolved"))
    first = _tick(opener)
    again = _tick(opener)
    assert first.opened and again.opened == [] and again.retried == []


# ── 같은 여행의 문제 묶음(`trip_watch_batch`)도 같은 규칙으로 닫히고 다시 열린다 `[2026-10-03]` ───────────

def test_a_batch_case_covers_its_members_and_a_transient_failure_reopens_the_whole_batch_once(api, guardrails):
    """묶음 Case 하나가 구성원 항목의 정체를 **덮는다**(다음 회차가 단일 Case 로 또 열지 않는다). 일시 실패(`action_target_changed` — 계산하는 사이 판이 움직였다)로 닫히면 같은 규칙으로 다시 열린다."""
    _create(api)
    guardrails.update({"travel.watch.batch_enabled": True, "travel.watch.retry_cooldown_seconds": 0, "travel.watch.retry_max": 1})
    calls: list = []
    opener = _opener(api, _check_activities(DISRUPTED), _escalating("action_target_changed", calls))
    first = _tick(opener)
    [opened] = first.opened                                              # ★묶음 Case 하나(전에는 활동 수만큼)
    assert opened["issue_code"] == "batch" and len(opened["items"]) >= 2 and len(calls) == 1 and first.retried == []
    second = _tick(opener)                                               # 일시 실패로 닫혔고 식힘이 지났다 — 같은 구성원으로 다시
    [reopened] = second.opened
    assert reopened["issue_code"] == "batch" and reopened["items"] == opened["items"]
    assert [r["attempt"] for r in second.retried] == [1]
    third = _tick(opener)                                                # 한도(retry_max=1)를 넘으면 더 안 연다 — 단일 Case 로 쪼개 다시 열지도 않는다
    assert third.opened == [] and third.retried == [] and len(third.existing) == len(opened["items"])


def test_a_batch_that_could_not_change_anything_notifies_once_for_the_set_and_never_again(api, guardrails):
    _create(api)
    guardrails.update({"travel.watch.batch_enabled": True})
    before = len(_notices(api))

    def run_case(*, tenant_id, case_id, actor_id):
        _start(case_id)
        items = _case(case_id)["state_json"]["trigger"]["batch"]
        _escalate(case_id, "itinerary_unresolved", " ".join(f"outcome:{entry['item_id']}:no_alternate" for entry in items))
        return {"status": "escalated"}

    opener = _opener(api, _check_activities(DISRUPTED), run_case)
    first = _tick(opener)
    [opened] = first.opened
    [note] = [n for n in _notices(api)[before:] if n.get("batch") and n.get("kind") == "no_alternate"]
    assert note["type"] == "guidance" and note["text"].count("일정은 그대로 두었어요") == len(opened["items"])
    assert "사람" not in note["text"] and "담당자" not in note["text"]
    second = _tick(opener)                                                # 같은 사건 — 다시 열지도 알리지도 않는다
    assert second.opened == [] and len([n for n in _notices(api)[before:] if n.get("batch")]) == 1


def test_a_batch_the_applier_refused_for_the_whole_itinerary_recheck_is_announced_to_every_member(api, guardrails):
    """★적대 검토(2026-10-03) — Team 은 묶음을 냈는데 적용기가 일정 전체 재판정으로 **거절**하면, 전에는 알림 표지가 없어 구성원 전원이 말없이 막혔다. 단일 Case 처럼 알린다."""
    from app.domains.travel_ops.components.actions.itinerary_actions import RECHECK_FAILED

    _create(api)
    guardrails.update({"travel.watch.batch_enabled": True})
    before = len(_notices(api))
    opener = _opener(api, _check_activities(DISRUPTED),
                     _escalating("action_rejected", observed=f"{RECHECK_FAILED}: 두 변경을 합치면 시간이 겹친다"))
    first = _tick(opener)
    [opened] = first.opened
    [note] = [n for n in _notices(api)[before:] if n.get("batch") and n.get("kind") == "recheck_failed"]
    assert note["text"].count("일정 전체와 맞지 않아") == len(opened["items"]) and "일정은 그대로 두었어요" in note["text"]


def test_a_batch_whose_close_has_no_item_tokens_is_not_announced(api, guardrails):
    """점검 소스 실패처럼 항목별 결과 표지가 없는 닫힘은 고객에게 알리지 않는다 — 바뀐 것이 있는지 모른다(운영자 몫)."""
    _create(api)
    guardrails.update({"travel.watch.batch_enabled": True})
    before = len(_notices(api))
    first = _tick(_opener(api, _check_activities(DISRUPTED), _escalating("fatal_source_failure")))
    assert first.opened and first.notified == [] and not [n for n in _notices(api)[before:] if n.get("batch")]


# ── 일정 전체 재판정이 막은 변경도 고객에게 알린다(결정 9 — 전체 일정 재검증) ───────────

def test_a_change_blocked_by_the_whole_itinerary_recheck_is_announced_with_its_own_wording(api):
    """바꿀 곳은 찾았는데 일정 전체를 다시 판정하니 앞뒤와 안 맞아 적용기가 거절했다 — 고객은 「일정은 그대로 두었어요」를 듣는다(그 이유로)."""
    from app.domains.travel_ops.components.actions.itinerary_actions import RECHECK_FAILED

    _create(api)
    before = len(_notices(api))
    opener = _opener(api, _check_activities(DISRUPTED),
                     _escalating("action_rejected", observed=f"{RECHECK_FAILED}: 아쿠아리움(11:30 종료)과 점심(11:00 시작)이 겹친다"))
    first = _tick(opener)
    assert first.notified and len(first.notified) == len(first.opened)
    sent = [n for n in _notices(api)[before:] if n.get("kind") == "recheck_failed"]
    assert len(sent) == len(first.notified)
    assert "일정 전체와 맞지 않아" in sent[0]["text"] and "일정은 그대로 두었어요" in sent[0]["text"]
    assert "사람" not in sent[0]["text"] and "담당자" not in sent[0]["text"]


def test_every_ranked_option_blocked_by_the_recheck_is_announced_the_same_way(api):
    """★`[2026-10-03]` 담당(Team)이 다음 순위 안까지 다 시험해 걸렸으면 적용기에 닿기 전에 `itinerary_recheck_failed` 로 끝난다 — 같은 문장으로 고객에게 알린다(전엔 이 경우가 알림 없이 조용했다)."""
    _create(api)
    before = len(_notices(api))
    opener = _opener(api, _check_activities(DISRUPTED),
                     _escalating("itinerary_recheck_failed", observed="일정 전체 재판정에 걸려 바꾸지 못했다: 1순위 가 — x / 2순위 나 — y"))
    first = _tick(opener)
    assert first.notified and len(first.notified) == len(first.opened)
    sent = [n for n in _notices(api)[before:] if n.get("kind") == "recheck_failed"]
    assert len(sent) == len(first.notified) and "일정은 그대로 두었어요" in sent[0]["text"]


def test_an_action_rejected_for_another_reason_is_not_announced_to_the_customer(api):
    """인자 오류 · 지어낸 장소 같은 다른 `action_rejected` 는 고객 알림이 아니라 **운영자의 오류**다."""
    _create(api)
    before = len(_notices(api))
    first = _tick(_opener(api, _check_activities(DISRUPTED),
                          _escalating("action_rejected", observed="itinerary.apply arguments are malformed: x")))
    assert first.opened and first.notified == []
    assert [n for n in _notices(api)[before:] if n.get("kind") in ("recheck_failed", "no_alternate")] == []
