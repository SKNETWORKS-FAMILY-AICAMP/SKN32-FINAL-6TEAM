"""Explicit catalog of the reusable example Team modules."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExampleEntry:
    example_id: str
    case_type: str
    summary: str
    module_path: str
    implementation_ref: str
    required_modules: tuple[str, ...]
    required_ports: dict[str, str]
    knowledge_scope: str | None = None


_REQUIRED_MODULES = (
    # vector_rag: app/composition.py:118 (build_registry 의 기본 ReadToolbox 조립에 필수)
    # graph_store: app/composition.py:159, acop_basement/introspection/contract.py:116
    # mcp: 현재 module_enabled() 로 게이팅되지 않지만 기본 project.yaml 이 켜 두는 상태와 맞춘다
    # ops_ui: acop_basement/presentation/ui/__init__.py:34 (앱 기동 시 이 키를 조회한다 — 없으면 KeyError)
    "vector_rag",
    "graph_store",
    "mcp",
    "ops_ui",
    # ★a2a_executor·voc 는 이 두 예시 Team 에 필요하지 않아 뺐다:
    #   a2a_executor 는 team_executor 포트가 "a2a" 일 때만 요구된다
    #   (app/composition.py:76) — 아래 required_ports 는 "local" 이라 불일치.
    #   voc 는 FeedbackAnalyticsTeam 전용이고 module_enabled("voc") 를 조회하는
    #   코드가 없다 — billing/technical 예시와 무관하다.
)
_REQUIRED_PORTS = {
    "team_executor": "local",
    "message_broker": "outbox",
    "graph_store": "sql",
}


CATALOG: tuple[ExampleEntry, ...] = (
    ExampleEntry(
        example_id="billing_subscription",
        case_type="구독/결제",
        summary="결제·구독을 읽고 설명하며 환불을 제안하는 Team (읽기·설명·제안 전용)",
        module_path="examples/customer_ops/billing.py",
        implementation_ref="app.modules.customer_ops.billing:BillingSubscriptionTeam",
        required_modules=_REQUIRED_MODULES,
        required_ports=_REQUIRED_PORTS,
        knowledge_scope="billing, subscription, refund",
    ),
    ExampleEntry(
        example_id="technical_entitlement",
        case_type="기술 지원",
        summary="계정·권한·인시던트를 진단하고 지원 조치를 제안하는 Team (접근 권한 변경 없음)",
        module_path="examples/customer_ops/technical.py",
        implementation_ref="app.modules.customer_ops.technical:TechnicalEntitlementTeam",
        required_modules=_REQUIRED_MODULES,
        required_ports=_REQUIRED_PORTS,
        knowledge_scope="entitlement, incident, technical",
    ),
)


__all__ = ["CATALOG", "ExampleEntry"]
