"""v7 §27-21 이 이름으로 지정한 관계 질의 3종.

★기존 테스트는 `Case → Evidence → Chunk → Document` 축을 검사했다.
  질의 자체는 일반화돼 있었지만, **v7 이 지정한 세 축의 assertion 이 없었다.**
  "일반 질의가 되니 특정 질의도 될 것" 은 추정이다 — 이 저장소에서 추정으로 두 번 틀렸다.

  1. Case → Issue → Policy
  2. Issue → Team
  3. Case → Action
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from acop_basement.infrastructure.db.session import get_connection
from acop_basement.infrastructure.graphstore.sql_adapter import SqlGraphAdapter


@pytest.fixture()
def graph_case():
    tenant = "graphv7_" + uuid4().hex
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "graph v7"))
            cur.execute("INSERT INTO customers (tenant_id, external_id) VALUES (%s,%s) RETURNING customer_id",
                        (tenant, "c-" + uuid4().hex))
            customer_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO customer_cases (tenant_id, customer_id, status, subject, intent, issue_code, "
                "owner_team_id, version) VALUES (%s,%s,'running',%s,'billing','post_cancel_charge',"
                "'demo_team',1) RETURNING case_id", (tenant, customer_id, "graph v7 fixture"))
            case_id = cur.fetchone()[0]
            cur.execute("INSERT INTO knowledge_documents (tenant_id, title, source_uri, scope, version, pii_class) "
                        "VALUES (%s,'환불 정책','seed://p','billing','1','none') RETURNING document_id", (tenant,))
            document_id = cur.fetchone()[0]
            cur.execute("INSERT INTO action_requests (tenant_id, case_id, action_type, arguments_json, "
                        "idempotency_key, status) VALUES (%s,%s,'refund','{}',%s,'pending_approval') "
                        "RETURNING action_id", (tenant, case_id, "graphv7-" + uuid4().hex))
            action_id = cur.fetchone()[0]
        conn.commit()
        yield {"conn": conn, "tenant": tenant, "case_id": case_id, "document_id": document_id,
               "action_id": action_id}
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM action_requests WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM knowledge_documents WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM customers WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))


def _neighbors(fx, node, edges, depth=1):
    adapter = SqlGraphAdapter(fx["conn"], tenant_id=fx["tenant"])
    return asyncio.run(adapter.neighbors(node, edges, depth=depth))


def test_case_to_issue_to_policy(graph_case):
    """★축 1 — Case → Issue → Policy."""
    hops = _neighbors(graph_case, str(graph_case["case_id"]),
                      ["has_issue", "governed_by"], depth=2)
    nodes = {h["node_id"] for h in hops}
    assert "issue:post_cancel_charge" in nodes, "Case → Issue 가 없다"
    assert str(graph_case["document_id"]) in nodes, "Issue → Policy 가 없다"
    # 깊이가 실제로 2단계다
    depths = {h["node_id"]: h["depth"] for h in hops}
    assert depths["issue:post_cancel_charge"] == 1
    assert depths[str(graph_case["document_id"])] == 2


def test_issue_to_team(graph_case):
    """★축 2 — Issue → Team."""
    hops = _neighbors(graph_case, "issue:post_cancel_charge", ["handled_by"])
    assert {h["node_id"] for h in hops} == {"team:demo_team"}


def test_case_to_action(graph_case):
    """★축 3 — Case → Action."""
    hops = _neighbors(graph_case, str(graph_case["case_id"]), ["proposed"])
    assert str(graph_case["action_id"]) in {h["node_id"] for h in hops}


def test_subgraph_includes_the_v7_axes(graph_case):
    """★버그사냥 2026-08-17 — subgraph() 는 neighbors() 와 다른, 자기만의 고정
    edge_types 목록을 썼는데 v7 §27-21 이 추가한 세 축이 거기 빠져 있었다.
    neighbors() 를 직접 그 타입으로 부르면 나오는데 subgraph() 결과에서는
    조용히 사라졌다."""
    adapter = SqlGraphAdapter(graph_case["conn"], tenant_id=graph_case["tenant"])
    result = asyncio.run(adapter.subgraph(str(graph_case["case_id"]), depth=3))
    node_ids = set(result["nodes"])
    assert "issue:post_cancel_charge" in node_ids, "subgraph() 에 Case→Issue 축이 없다"
    assert str(graph_case["document_id"]) in node_ids, "subgraph() 에 Issue→Policy 축이 없다"
    assert "team:demo_team" in node_ids, "subgraph() 에 Issue→Team 축이 없다"
    assert str(graph_case["action_id"]) in node_ids, "subgraph() 에 Case→Action 축이 없다"


def test_axes_are_tenant_isolated(graph_case):
    """★남의 tenant 에서 조회하면 아무것도 안 나온다."""
    adapter = SqlGraphAdapter(graph_case["conn"], tenant_id="someone-else")
    hops = asyncio.run(adapter.neighbors(str(graph_case["case_id"]),
                                         ["has_issue", "governed_by", "proposed"], depth=2))
    assert hops == []
