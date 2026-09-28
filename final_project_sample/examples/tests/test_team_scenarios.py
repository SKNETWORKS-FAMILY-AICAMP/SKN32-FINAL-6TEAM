from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from acop_basement.core.contracts import ContextPack, Evidence, NextAction, TeamTask, ToolNotAllowed
from acop_basement.core.verification import Facts, verify_proposal
from examples.customer_ops.billing import BillingSubscriptionTeam
from examples.customer_ops.technical import TechnicalEntitlementTeam
from app.modules.customer_ops.verification_policy import CUSTOMER_OPS_POLICY
from acop_basement.tools.read_tools import ReadToolbox, ToolLoopExceeded


NOW = datetime.now(UTC)


def pack(team_id: str, degraded: bool = False) -> ContextPack:
    return ContextPack(pack_id=uuid4(), case_id=uuid4(), team_id=team_id, tenant_id="test-team-tenant", knowledge_scope=["billing", "technical"], current_state={"customer_id": str(uuid4()), "status": "running"}, estimated_input_tokens=10, degraded=degraded, omissions=["fixture"] if degraded else [])


def task(team_id: str, capability: str, context: ContextPack, allowed: list[str]) -> TeamTask:
    return TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=context.case_id, team_id=team_id, capability=capability, case_version=1, input_text="怨좉컼 ?붿껌", context=context, allowed_tools=allowed, deadline_at=NOW + timedelta(seconds=90))


class FakeTools:
    def __init__(self, values): self.values = values
    def call(self, name, context, arguments, allowed_tools, seen):
        if name not in allowed_tools: raise ToolNotAllowed(name)
        return self.values[name]


def policy():
    return [Evidence(evidence_id="policy:refund#c1", source_type="policy", source_id="refund#c1", claim="policy", value={}, confidence=1, observed_at=NOW)]


@pytest.mark.asyncio
async def test_billing_cancelled_subscription_waits_for_refund_approval():
    payment_id = str(uuid4())
    context = pack("billing_subscription")
    tools = FakeTools({"read.subscription":{"status":"cancelled","plan":"Pro"},
                       "read.payment_history":[{"payment_id": payment_id, "status":"paid","amount_cents":19900}],
                       "read.policy":policy()})
    result = await BillingSubscriptionTeam(tools).execute(task("billing_subscription", "billing.investigate", context, BillingSubscriptionTeam.manifest.allowed_tools))
    assert result.outcome == "waiting" and result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert result.action_proposals[0].action_type == "refund.request"
    assert result.action_proposals[0].rationale_evidence_ids
    # ?낅쾭洹몄궗??2026-08-17 ??Team ??留뚮뱺 ?쒖븞???ㅼ젣濡?verify_proposal() ??    #   ?듦낵?섎뒗吏源뚯? ?뺤씤?쒕떎. ?꾩뿉??Team ?뚯뒪?몄? verification ?뚯뒪?멸?
    #   ?쒕줈 ?ㅻⅨ ?먯쑝濡?留뚮뱺 arguments 留?遊먯꽌, ?ㅼ젣 Team 異쒕젰??留ㅻ쾲 嫄곕?
    #   ?뱁븯??嫄??꾨Т??紐??≪븯?????ш린??洹??곌껐??寃?ы븳??
    proposal = result.action_proposals[0]
    assert proposal.arguments == {"payment_id": payment_id, "amount_cents": 19900}
    facts = Facts(collections={"payments": {payment_id: {"payment_id": payment_id, "amount_cents": 19900}}},
                  evidence_ids=frozenset(e.evidence_id for e in result.evidence))
    problems = verify_proposal(arguments=proposal.arguments, rationale_evidence_ids=proposal.rationale_evidence_ids,
                               facts=facts, policy=CUSTOMER_OPS_POLICY)
    assert problems == [], f"?ㅼ젣 Team ??留뚮뱺 ?쒖븞??寃利앹쓣 ?듦낵?섏? 紐삵븳?? {problems}"


@pytest.mark.asyncio
async def test_technical_mismatch_returns_procedure_without_mutation():
    context = pack("technical_entitlement")
    tools = FakeTools({"read.entitlement":{"plan":"Free"}, "read.account":{"plan":"Pro"}, "read.incident":[], "read.policy":policy()})
    result = await TechnicalEntitlementTeam(tools).execute(task("technical_entitlement", "entitlement.diagnose", context, TechnicalEntitlementTeam.manifest.allowed_tools))
    assert result.outcome == "completed"
    assert result.decisions[0]["classification"] == "entitlement_sync_mismatch"
    assert result.decisions[-1]["side_effects"] == []


@pytest.mark.asyncio
async def test_degraded_context_escalates_without_answer():
    context = pack("billing_subscription", degraded=True)
    result = await BillingSubscriptionTeam(FakeTools({})).execute(task("billing_subscription", "billing.investigate", context, BillingSubscriptionTeam.manifest.allowed_tools))
    assert result.outcome == "escalated" and result.next_action is NextAction.ESCALATE
    assert result.answer is None


def test_tool_allowlist_and_repetition_guard():
    toolbox = ReadToolbox({"read.subscription": lambda scope, **kwargs: {"status": "cancelled"}})
    context = pack("billing_subscription")
    with pytest.raises(ToolNotAllowed):
        toolbox.call("read.account", context, {}, ["read.subscription"], set())
    seen = set()
    # no DB call is needed: the second identical request is rejected first
    toolbox.call("read.subscription", context, {}, ["read.subscription"], seen)
    with pytest.raises(ToolLoopExceeded):
        toolbox.call("read.subscription", context, {}, ["read.subscription"], seen)
