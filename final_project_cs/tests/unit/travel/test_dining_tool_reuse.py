"""동일 실행의 확인 결과 재사용. DB·외부 API는 호출하지 않는다."""
from contextlib import nullcontext
from copy import deepcopy

import pytest

from app.domains.travel_ops.instances.dining.agent import judge_day, validate_check
from app.domains.travel_ops.instances.dining.agent_tools import DiningTools, ToolRefused
from tests.unit.travel.test_dining_agent import PLAN, UID, Script, _call, _final
from app.infrastructure.llm.tool_chat import ToolTurn


class CountingTools(DiningTools):
    def _find_place(self, name, lat=None, lng=None):
        self.executed.append(("find_place", name))
        return {"found": True, "verdict": "ok", "place_uid": UID, "name": name, "details": {"label": "original"}}

    def _check_open_at(self, place_uid, start, end=None):
        self.executed.append(("check_open_at", start, end))
        return {"verdict": "bad", "reason": "휴무", "details": {"label": "original"}}

    def _check_attributes(self, place_uid, wanted):
        self.executed.append(("check_attributes", deepcopy(wanted)))
        return {"attributes": {attr: {"state": "yes"} for attr in wanted}}


def tools(**kw):
    got = CountingTools(lambda: nullcontext(None), **kw)
    got.executed = []
    return got


ARGS = {"place_uid": UID, "start": "2026-10-25T12:00", "end": "2026-10-25T13:00"}


def test_identical_query_reuses_original_evidence_without_another_call():
    got = tools()
    first = got.call("check_open_at", ARGS)
    again = got.call("check_open_at", dict(reversed(list(ARGS.items()))))
    assert again == {**first, "reused": True}
    assert len(got.executed) == len(got.calls) == 1 and got.refused == []
    assert got.reused == [{"tool": "check_open_at", "call_id": "c1"}]
    assert validate_check({"check": "open_at", "verdict": "bad", "evidence": [
        {"call_id": again["call_id"], "path": "verdict", "value": "bad"}]}, got,
        place_uid=UID, start=ARGS["start"], end=ARGS["end"]) is None


def test_reuse_remains_available_at_the_call_limit_but_new_queries_are_refused():
    got = tools(max_calls=1)
    got.call("check_open_at", ARGS)
    assert got.call("check_open_at", ARGS)["call_id"] == "c1"
    assert "refused" in got.call("check_open_at", {**ARGS, "start": "2026-10-25T18:00"})
    assert len(got.executed) == 1


@pytest.mark.parametrize("patch", [
    {"place_uid": "22222222-2222-2222-2222-222222222222"},
    {"start": "2026-10-26T12:00"}, {"end": "2026-10-25T14:00"},
])
def test_changed_place_or_time_is_a_new_query(patch):
    got = tools()
    got.call("check_open_at", ARGS)
    assert got.call("check_open_at", {**ARGS, **patch})["call_id"] == "c2"
    assert len(got.executed) == 2


def test_changed_attribute_is_a_new_query_and_original_input_cannot_rewrite_the_key():
    got = tools()
    args = {"place_uid": UID, "wanted": ["halal"]}
    got.call("check_attributes", args)
    args["wanted"].append("card")
    assert got.call("check_attributes", args)["call_id"] == "c2"
    assert got.call("check_attributes", {"place_uid": UID, "wanted": ["halal"]})["call_id"] == "c1"


def test_returned_values_cannot_mutate_stored_evidence_or_future_reuse():
    got = tools()
    first = got.call("check_open_at", ARGS)
    first["details"]["label"] = "corrupted"
    again = got.call("check_open_at", ARGS)
    assert again["details"]["label"] == "original"
    again["details"]["label"] = "corrupted twice"
    assert got.calls[0]["result"]["details"]["label"] == "original"
    got.result_of("c1")["details"]["label"] = "corrupted accessor"
    assert got.result_of("c1")["details"]["label"] == "original"


def test_new_execution_has_no_shared_cached_results():
    first, second = tools(), tools()
    first.call("check_open_at", ARGS)
    response = second.call("check_open_at", ARGS)
    assert not response.get("reused") and len(second.executed) == 1


@pytest.mark.parametrize("failure", ["unknown", "refused", "exception"])
def test_unconfirmed_results_and_failures_are_not_reused(failure):
    got = tools()
    original = got._check_open_at
    def flaky(**kw):
        got._check_open_at = original
        if failure == "refused":
            raise ToolRefused("temporary refusal")
        if failure == "exception":
            raise RuntimeError("temporary provider error")
        return {"verdict": "unknown", "reason": "provider unavailable"}
    got._check_open_at = flaky
    if failure == "exception":
        with pytest.raises(RuntimeError):
            got.call("check_open_at", ARGS)
    else:
        got.call("check_open_at", ARGS)
    response = got.call("check_open_at", ARGS)
    assert response.get("verdict") == "bad" and not response.get("reused")
    assert len(got.executed) == 1


def test_cached_result_cannot_bypass_updated_tool_permission_or_scope():
    got = tools()
    got.call("find_place", {"name": "시험식당"})
    got.allowed = frozenset({"check_open_at"})
    assert "refused" in got.call("find_place", {"name": "시험식당"})
    got.allowed = None
    got.off_scope = frozenset({"시험식당"})
    assert "refused" in got.call("find_place", {"name": "시험식당"})


@pytest.mark.parametrize("name,args,result", [
    ("find_place", {"name": "못찾는식당"}, {"found": False, "verdict": "bad"}),
    ("map_search", {"query": "시험식당"}, {"hits": [], "reason": "provider unavailable"}),
    ("map_search", {"query": "시험식당"}, {"hits": []}),
    ("nearby_places", {"lat": 37.5, "lng": 127.0}, {"places": []}),
    ("place_detail", {"place_uid": UID}, {"found": False}),
    ("check_attributes", {"place_uid": UID, "wanted": ["halal"]}, {"attributes": {"halal": {"state": "unknown"}}}),
    ("check_attributes", {"place_uid": UID, "wanted": ["halal"]}, {"attributes": {}}),
    ("check_open_at", ARGS, {"verdict": "bad", "error": "provider_error"}),
])
def test_failed_data_and_unconfirmed_attributes_are_queried_again(name, args, result):
    got = tools()
    executions = []
    def query(**kw):
        executions.append(kw)
        return result
    setattr(got, "_" + name, query)
    got.call(name, args)
    again = got.call(name, args)
    assert again["call_id"] == "c2" and not again.get("reused")
    assert len(executions) == 2


@pytest.mark.parametrize("name,args,result", [
    ("map_search", {"query": "시험식당"}, {"hits": [{"name": "시험식당"}]}),
    ("nearby_places", {"lat": 37.5, "lng": 127.0}, {"places": [{"name": "시험식당"}]}),
    ("place_detail", {"place_uid": UID}, {"found": True, "name": "시험식당"}),
])
def test_confirmed_data_results_are_reused_as_well_as_rule_verdicts(name, args, result):
    got = tools()
    executions = []
    def query(**kw):
        executions.append(kw)
        return result
    setattr(got, "_" + name, query)
    first = got.call(name, args)
    assert got.call(name, args) == {**first, "reused": True}
    assert len(executions) == 1


def test_agent_receives_original_evidence_on_repeat_and_records_saved_calls():
    got = tools()
    chat = Script(
        ToolTurn(content=None, tool_calls=[_call(1, "find_place", name="시험식당"), _call(2, "check_open_at", **ARGS)]),
        ToolTurn(content=None, tool_calls=[_call(3, "check_open_at", **ARGS)]),
        _final([{"check": "open_at", "verdict": "bad", "evidence": [
            {"call_id": "c2", "path": "verdict", "value": "bad"}]}]),
    )
    result = judge_day(PLAN, tools=got, chat=chat)
    assert result.failure is None and result.items[0]["checks"][0]["verdict"] == "bad"
    assert result.stats["tool_calls"] == 2 and result.stats["cache_hits"] == 1
    assert result.stats["refused"] == 0
