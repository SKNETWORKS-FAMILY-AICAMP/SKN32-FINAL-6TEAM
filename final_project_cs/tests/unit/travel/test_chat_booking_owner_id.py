"""규칙 경로가 담당으로 **팀 id**를 남긴다 — 종류 `booking` 을 받는 팀의 id 는 `booking_handoff`(config/project.yaml · BookingHandoffTeam).

옛 기록(owner_team_id = booking)은 이관하지 않는다. 읽는 쪽은 `canonical_team_id` 로 같은 팀으로 읽는다.
"""
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest


@pytest.mark.parametrize("case_type,team", [("booking", "booking_handoff"), ("dining", "dining"), ("activity", "activity"),
                                            ("mobility", "mobility"), ("lodging", "lodging"), ("flight", "flight"),
                                            ("trip_desk", "trip_desk"), ("other", "trip_desk"), ("shipping", "trip_desk")])
def test_case_type_is_recorded_as_the_registered_team_id(case_type, team):
    from app.domains.travel_ops.components.conversation import trip_messages as tm

    assert tm.team_for_case_type(case_type) == team


def test_case_type_map_names_only_teams_declared_in_project_config():
    from app.core.project_config import load_project_config
    from app.domains.travel_ops.components.conversation import trip_messages as tm

    declared = {team.team_id for team in load_project_config().teams}
    assert set(tm.CASE_TYPE_TEAMS.values()) <= declared
    assert "booking" not in declared


@pytest.mark.parametrize("stored,read", [("booking", "booking_handoff"), ("booking_handoff", "booking_handoff"),
                                         ("dining", "dining"), (None, None)])
def test_legacy_booking_owner_reads_as_the_booking_handoff_team(stored, read):
    from app.domains.travel_ops.components.conversation import trip_messages as tm

    assert tm.canonical_team_id(stored) == read


def test_fact_case_on_a_booking_issue_records_booking_handoff(monkeypatch):
    from app.application import classification
    from app.core import transition
    from app.core.case_lifecycle.events import EventType
    from app.domains.travel_ops.components.conversation import trip_messages as tm
    from app.infrastructure.db import repository

    conn = SimpleNamespace(transaction=lambda: nullcontext())
    moves = []
    monkeypatch.setattr(tm, "get_connection", lambda: nullcontext(conn))
    monkeypatch.setattr(classification, "classify_case", lambda *a, **kw: EventType.CLASSIFIED)
    monkeypatch.setattr(repository, "get_case", lambda *a, **kw: {"version": 1, "issue_code": "booking_cancel"})
    monkeypatch.setattr(transition, "transition_case", lambda *a, **kw: moves.append((kw["event_type"], kw["payload"])))
    done = tm._finish_fact_case(tenant="t", case_id=uuid4(), trip_id=uuid4(), message="예약 확인해 줘", classifier=None,
                                actor_id="a", fact="booking", answer="예약 기록 답")
    assert done is True
    routed = [p for e, p in moves if e is EventType.ROUTED]
    assert routed and routed[0]["owner_team_id"] == "booking_handoff"


@pytest.mark.parametrize("stored,expected", [("booking", "booking_handoff"), ("dining", None)])
def test_resuming_a_legacy_booking_case_reads_the_owner_as_booking_handoff(stored, expected):
    """재개 담당: 고른 일정이 없으면 저장된 담당을 쓴다 — 옛 `booking` 은 팀 id 로 읽고, 다른 담당은 그대로(Controller 가 저장값을 쓴다)."""
    from app.domains.travel_ops.components.conversation import case_dispatch

    current = {"owner_team_id": stored, "tenant_id": "t", "state_json": {}}
    assert case_dispatch.resume_owner(current, "네", {}) == expected
    patched = case_dispatch.resume_owner(current, "네", {"x": 1})
    assert patched == {"owner_team_id": expected or stored, "state_patch": {"x": 1}}


def test_an_older_reader_resumes_a_booking_handoff_case_with_the_registered_team():
    """롤백 안전 — 이 묶음이 남긴 `booking_handoff` 담당을 이 묶음 **이전** 판도 읽는다.

    이 시험은 이전 판(role-manager af608588)에도 있는 읽기 경로만 쓴다: Controller 는 저장 담당을 등록 팀 표
    (`config/project.yaml`, 이 묶음은 바꾸지 않는다)로 찾고, 재개 담당은 `_resume_route(...) or 저장 담당` 이다.
    옛 값 `booking` 은 등록 팀이 아니었다 — 새 값이 이전 판에서 더 잘 읽힌다.
    """
    from app.core.project_config import load_project_config
    from app.domains.travel_ops.components.conversation import case_dispatch

    declared = {team.team_id: team for team in load_project_config().teams}
    assert declared["booking_handoff"].active
    assert declared["booking_handoff"].implementation_ref.endswith(":BookingHandoffTeam")
    current = {"owner_team_id": "booking_handoff", "tenant_id": "t", "state_json": {}, "intent": "booking_verify"}
    routed = case_dispatch._resume_route(current, "네") or current["owner_team_id"]   # 이전 판 재개 route 와 같은 식
    assert routed == "booking_handoff"


def test_every_owner_this_bundle_records_is_runnable_in_the_real_registry_of_any_version():
    """롤백 안전 — 이 묶음이 기록하는 등록 팀 id 는 실제 조립 registry(`composition.build_registry`)에서 실행 가능하다.

    registry 는 `config/project.yaml` 로만 만들어지고 이 묶음은 그 파일을 바꾸지 않는다 → 이전 판 Controller 의
    `require_team(owner_team_id)` 도 같은 결과다. 옛 값 `booking` 은 실행할 수 없는 값이었다. 기록 라벨 `trip_desk` 는
    이 묶음 전에도 쓰던 값이고(등록 팀 없는 종류), 이 묶음의 `trip_desk` Case 는 `COMPLETED` 로 끝나 재개 · 재시도를 타지 않는다.
    """
    from app import composition
    from app.core.project_config import load_project_config
    from app.core.team_availability import TeamUnavailable
    from app.domains.travel_ops.components.conversation import trip_messages as tm

    registry = composition.build_registry(config=load_project_config(), tools=object(), llm=object())
    for owner in set(tm.CASE_TYPE_TEAMS.values()):
        entry = registry.require_runnable(owner)
        assert entry.manifest.team_id == owner
    with pytest.raises(TeamUnavailable, match="not_installed"):
        registry.require_runnable("booking")
