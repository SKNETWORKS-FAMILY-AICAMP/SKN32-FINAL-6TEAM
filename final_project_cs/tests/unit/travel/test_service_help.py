"""서비스 안내는 검증된 운영 지식만 읽고, 여행 실행과 섞이지 않는다."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.components.conversation import service_help
from app.domains.travel_ops.components.conversation.decision_unit import DecisionFailed, decide, labels
from knowledge.ingest import load_corpus

NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)


def chunk(number=1, **overrides):
    doc = load_corpus(service_help.MANIFEST)[0]
    return SimpleNamespace(document_id="t_service_01", chunk_no=number,
                           **({"scope": "travel_service", "score": .9,
                               "content": doc.sections[number - 1].content} | overrides))


def reply(search):
    return service_help.reply(message="너가 할 수 있는 게 뭐야?", tenant_id="customer-tenant",
                              policy_search=search, min_score=.6, now=NOW)


def test_customer_help_uses_tenant_scoped_search_and_customer_lines():
    requests = []

    def search(**kwargs):
        requests.append(kwargs)
        return [chunk()]

    status, text, basis = reply(search)
    assert status == "answered" and "triPilot 여행 도우미" in text
    assert "오늘 일정 알려줘" in text and "30분 늦어요" in text
    assert requests == [{"tenant_id": "customer-tenant", "query": "너가 할 수 있는 게 뭐야?",
                         "allowed_scopes": ["travel_service"], "top_k": 3}]
    assert basis["sources"] == ["t_service_01#c1"] and basis["checked_at"] == NOW.isoformat()
    assert "t_service_01" not in text and "현재 고객 채팅 처리기" not in text


@pytest.mark.parametrize("bad", [
    {"scope": "travel_activity"}, {"document_id": "unknown"},
    {"content": "오래된 기능·직원용 원문·예약 자동 완료"},
    {"score": .2}, {"score": float("nan")}, {"score": "broken"},
])
def test_wrong_stale_or_low_confidence_sources_cannot_be_shown(bad):
    found = chunk()
    for key, value in bad.items():
        setattr(found, key, value)
    status, text, basis = reply(lambda **_: [found])
    assert status == "service_help_unavailable"
    assert basis["service_help"] == "no_verified_match" and not basis["sources"]
    assert "자동 완료" not in text


def test_unavailable_search_is_visible_instead_of_static_success():
    assert reply(None)[2]["service_help"] == "search_unavailable"

    def broken(**_):
        raise TimeoutError("비밀 상세는 노출하지 않는다")

    status, text, basis = reply(broken)
    assert status == "service_help_unavailable" and basis["service_help"] == "error:TimeoutError"
    assert "비밀" not in text
    assert reply(lambda **_: [])[2]["service_help"] == "no_verified_match"


def test_support_boundary_is_customer_wording_and_deduplicated():
    status, text, basis = reply(lambda **_: [chunk(5), chunk(5)])
    assert status == "answered" and "자동으로 완료해 드리는 기능은 제공하지 않아요" in text
    assert basis["policy_hits"] == 1


class ServiceModel:
    def __init__(self, **overrides):
        self.overrides = overrides

    def structured(self, system, user, schema, **_):
        assert "answer_service" in schema["properties"]["action"]["enum"]
        assert "너가 할 수 있는 게 뭐야?" in system and "서비스 기능·사용법·정체 질문은 answer_service" in system
        return {"action": "answer_service", "target_item": "none", "target_change": "none",
                "fact": "none", "choices": [], "minutes": 0, **self.overrides}


def test_service_action_needs_no_itinerary_and_has_read_classification():
    decision = decide(ServiceModel(), stops=[], changes=[], history=[], selected_item_id=None,
                      message="너가 할 수 있는 게 뭐야?")
    assert decision.action == "answer_service" and decision.item is None
    assert labels(decision)["intent"] == "confirm_request"


@pytest.mark.parametrize("overrides", [{"fact": "detail"}, {"fact": "invalid_fact"}, {"target_item": "i99"},
                                        {"choices": [{"action": "apply_change"}]},
                                        {"query": {"day": "all"}}])
def test_service_action_rejects_mixed_schedule_or_change_commands(overrides):
    with pytest.raises(DecisionFailed):
        decide(ServiceModel(**overrides), stops=[], changes=[], history=[], selected_item_id=None,
               message="사용법 알려줘")
