# -*- coding: utf-8 -*-
"""라우팅이 어긋났을 때 **한 번 더 고른다** — 그리고 지어내지 않는다. `[2026-10-06]`

이 제품에는 사람 운영자 큐가 없다. 「받는 팀이 없다」로 끝내면 그 Case 는 아무도 받지 않는다.
그래서 한 번 더 묻되, **등록된 팀이 실제로 받는 종류 안에서만** 고르게 한다.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.core_hooks import reroute as hook

TEAMS = [{"team_id": "dining", "accepts": ["dining"], "capabilities": ["dining.check"]},
         {"team_id": "mobility", "accepts": ["mobility"], "capabilities": ["mobility.check"]}]


def _ask(**over):
    kwargs = dict(subject="밥집이 닫았어요", case_type="unknown_thing", intent=None,
                  teams=TEAMS, failure="case must resolve to exactly one active team")
    kwargs.update(over)
    return hook.reroute(**kwargs)


def test_a_team_that_can_take_it_is_picked_and_the_reason_comes_with_it():
    answer = _ask(llm=lambda text: {"case_type": "dining", "intent": "incident_report", "why": "식당 영업 문제"})
    assert answer == {"case_type": "dining", "intent": "incident_report", "why": "식당 영업 문제", "by": "llm"}


def test_a_team_the_model_invents_is_refused_after_one_second_chance():
    """★목록 밖을 내면 **한 번만** 다시 묻는다(`feedback.classify` 와 같은 규칙). 그래도 밖이면 못 고른 것이다."""
    asked = []

    def stubborn(text):
        asked.append(text)
        return {"case_type": "concierge", "why": "제가 만든 팀입니다"}

    assert _ask(llm=stubborn) is None
    assert len(asked) == 2, "한 번 더 물어야 한다 — 그리고 딱 한 번만"
    assert "concierge" in asked[1] and "dining, mobility" in asked[1], "무엇이 틀렸고 무엇이 되는지 알려 줘야 한다"


def test_the_model_may_say_it_cannot_route_this_one():
    """못 고르겠다는 답(`null`)을 억지로 팀에 밀어 넣지 않는다."""
    assert _ask(llm=lambda text: {"case_type": None, "why": "여행과 무관한 문의"}) is None


def test_an_intent_outside_the_vocabulary_is_dropped_not_passed_on():
    answer = _ask(llm=lambda text: {"case_type": "mobility", "intent": "make_me_a_sandwich", "why": "x"})
    assert answer is not None and answer["intent"] is None, "모르는 요청 종류는 버린다 — 코어가 원래 것을 쓴다"


def test_nothing_to_choose_from_means_no_model_call():
    called = []
    assert _ask(teams=[], llm=lambda text: called.append(text) or {}) is None
    assert _ask(subject="   ", llm=lambda text: called.append(text) or {}) is None
    assert called == [], "고를 것이 없거나 읽을 문장이 없으면 모델을 부르지 않는다"


def test_only_the_types_registered_teams_actually_accept_are_offered():
    """★어휘를 이 파일에 적어 두지 않는다 — 선언이 바뀌면 고를 수 있는 값도 같이 바뀐다."""
    seen = {}

    def peek(text):
        seen["prompt"] = text
        return {"case_type": "lodging", "why": "숙소"}

    answer = _ask(teams=[{"team_id": "lodging", "accepts": ["lodging"], "capabilities": ["lodging.hold"]}], llm=peek)
    assert answer is not None and answer["case_type"] == "lodging"
    assert "dining" not in seen["prompt"].split("Allowed case_type values:")[1].split("\n")[0]


def test_a_model_that_blows_up_does_not_take_the_case_down():
    """★재배분이 죽어도 Case 는 종전대로 간다 — 코어가 감싼다(`Controller._reroute_once`)."""
    def broken(text):
        raise RuntimeError("provider down")

    with pytest.raises(RuntimeError):
        _ask(llm=broken)                                   # 어휘 쪽은 그대로 올린다
    from app.application.controller import Controller

    class _Registry:
        def manifests(self):
            return ()

    controller = Controller.__new__(Controller)
    controller.reroute = lambda **_: (_ for _ in ()).throw(RuntimeError("provider down"))
    controller.registry = _Registry()
    assert controller._reroute_once({"subject": "x"}, intent=None, failure="f") is None


def _controller_with(reroute, teams):
    """`_reroute_once` 만 돌리는 최소 Controller — 코어가 **다시 묻는지**를 본다."""
    from app.core.registry import RegistryError
    from app.application.controller import Controller

    class _Entry:
        class manifest:
            team_id = "dining"

    class _Registry:
        def manifests(self):
            return tuple(teams)

        def resolve(self, *, case_type, intent=None):
            if case_type != "dining":
                raise RegistryError(f"case must resolve to exactly one active team: {case_type}")
            return _Entry()

        def get(self, team_id):                              # 이미 정해진 담당 팀 — 재배분으로 라우팅된 Case 가 쓴다
            return _Entry()

        @staticmethod
        def capability_for(entry, intent=None, *, input_text=None, state=None):
            return "dining.check"

    controller = Controller.__new__(Controller)
    controller.reroute = reroute
    controller.registry = _Registry()
    return controller


class _Manifest:
    def __init__(self, team_id, accepts, active=True):
        self.team_id, self.accepted_case_types, self.capabilities, self.active = team_id, accepts, ["x"], active


def test_the_core_asks_the_registry_again_instead_of_trusting_the_answer():
    """★가장 중요한 안전장치 — 돌려받은 값으로 **Registry 에 다시 묻는다.**
    모델이 그럴듯한 이름을 내도 받는 팀이 없으면 Case 는 종전대로 escalated 로 간다."""
    teams = [_Manifest("dining", ["dining"])]
    case = {"subject": "밥집이 닫았어요", "issue_code": "unknown_thing"}

    good = _controller_with(lambda **_: {"case_type": "dining", "why": "식당"}, teams)
    picked = good._reroute_once(case, intent=None, failure="f")
    assert picked is not None and picked[0].manifest.team_id == "dining" and picked[1] == "dining.check"
    assert picked[2]["from"] == "unknown" and picked[2]["to"] == "dining", "무엇을 무엇으로 바꿨는지 남긴다"

    invented = _controller_with(lambda **_: {"case_type": "concierge", "why": "지어냄"}, teams)
    assert invented._reroute_once(case, intent=None, failure="f") is None


def test_a_rerouted_case_keeps_its_team_when_the_capability_is_asked_again():
    """★`[2026-10-07]` 재배분이 성공한 Case 는 원래 종류(`unknown`)로는 받는 팀이 없다 — 뒤에서 기능을 다시 물을 때 터지지 않고 **담당 팀**으로 찾는다.
    전에는 이것이 터져 재배분이 성공한 Case 가 곧바로 죽었다(`tests/scenario/test_case_question.py::test_the_two_reports_stay_what_they_were`)."""
    from app.core.registry import RegistryError

    controller = _controller_with(lambda **_: None, [_Manifest("dining", ["dining"])])
    rerouted = {"subject": "밥집이 닫았어요", "issue_code": "unknown_thing", "owner_team_id": "dining", "intent": None}
    assert controller._capability(rerouted) == "dining.check"
    with pytest.raises(RegistryError):                            # 담당이 정해지지 않았으면 종전대로 터진다 — 조용히 아무 팀에나 보내지 않는다
        controller._capability({**rerouted, "owner_team_id": None})


def test_only_active_teams_are_offered_to_the_chooser():
    seen = {}
    teams = [_Manifest("dining", ["dining"]), _Manifest("lodging", ["lodging"], active=False)]
    controller = _controller_with(lambda **kw: seen.update(kw) or {"case_type": "dining"}, teams)
    controller._reroute_once({"subject": "x", "issue_code": "y"}, intent=None, failure="f")
    assert [t["team_id"] for t in seen["teams"]] == ["dining"], "꺼 둔 팀은 고를 수 없다"


def test_without_a_chooser_nothing_changes():
    controller = _controller_with(None, [_Manifest("dining", ["dining"])])
    assert controller._reroute_once({"subject": "x"}, intent=None, failure="f") is None
