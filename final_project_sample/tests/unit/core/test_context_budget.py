from uuid import uuid4

import pytest

from acop_basement.core.context import ContextBroker, ContextBudgetError, ContextInputs, PolicyChunk


def inputs(**overrides):
    values = {
        "case_id": uuid4(),
        "tenant_id": "test_context",
        "team_id": "test_team",
        "knowledge_scope": ["billing"],
        "system_instruction": "answer with evidence",
        "current_state": {"status": "routing", "version": 2},
    }
    values.update(overrides)
    return ContextInputs(**values)


def test_context_broker_eviction_is_budgeted_and_ordered():
    broker = ContextBroker()
    pack = broker.build(inputs(
        similar_cases=[{"case_id": str(uuid4()), "body": "similar " * 2000}],
        history_entries=["history " * 500],
        policy_chunks=[
            PolicyChunk("high", 1, "high policy " * 1000, 0.99, "billing"),
            PolicyChunk("low", 1, "low policy " * 1000, 0.10, "billing"),
        ],
    ))

    assert pack.estimated_input_tokens <= 12000
    assert pack.omissions
    assert pack.omissions[0].startswith("similar_cases:")
    assert not any(item.startswith("case_state:") for item in pack.omissions)
    assert any(item.startswith("policy_rag:low_score:low#c1") for item in pack.omissions)


@pytest.mark.parametrize("field, value", [
    ("system_instruction", "system " * 3000),
    ("current_state", {"state": "case " * 5000}),
])
def test_context_broker_rejects_untruncatable_sections(field, value):
    with pytest.raises(ContextBudgetError):
        ContextBroker().build(inputs(**{field: value}))
