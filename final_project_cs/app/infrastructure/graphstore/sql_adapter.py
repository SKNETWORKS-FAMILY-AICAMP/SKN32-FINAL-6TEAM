from __future__ import annotations

from typing import Any


class SqlGraphAdapter:
    """PostgreSQL-backed graph projection using joins and recursive CTEs.

    The adapter is deliberately connection-injected so tests can use a real
    PostgreSQL transaction or a small fake cursor without introducing a graph DB.
    """

    def __init__(self, connection, *, tenant_id: str) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        self.connection = connection
        self.tenant_id = tenant_id

    def _rows(self, sql: str, params: tuple[Any, ...]) -> list[dict]:
        with self.connection.cursor() as cur:
            cur.execute(sql, params)
            columns = [d.name if hasattr(d, "name") else d[0] for d in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    async def neighbors(self, node_id: str, edge_types: list[str], depth: int = 1) -> list[dict]:
        if depth < 1 or not edge_types:
            return []
        return self._rows(
            """WITH RECURSIVE edges(src, dst, edge_type, tenant_id) AS (
                SELECT c.customer_id::text, cc.case_id::text, 'owns', c.tenant_id
                FROM customers c JOIN customer_cases cc
                  ON cc.customer_id=c.customer_id AND cc.tenant_id=c.tenant_id
                UNION ALL
                SELECT cc.case_id::text, ce.event_id::text, 'has_event', cc.tenant_id
                FROM customer_cases cc JOIN case_events ce
                  ON ce.case_id=cc.case_id AND ce.tenant_id=cc.tenant_id
                UNION ALL
                SELECT cc.case_id::text, ar.action_id::text, 'proposed', cc.tenant_id
                FROM customer_cases cc JOIN action_requests ar
                  ON ar.case_id=cc.case_id AND ar.tenant_id=cc.tenant_id
                UNION ALL
                SELECT ar.action_id::text, aa.approval_id::text, 'approved', ar.tenant_id
                FROM action_requests ar JOIN action_approvals aa ON aa.action_id=ar.action_id
                UNION ALL
                SELECT kd.document_id::text, kc.chunk_id::text, 'contains', kd.tenant_id
                FROM knowledge_documents kd JOIN knowledge_chunks kc ON kc.document_id=kd.document_id
                UNION ALL
                SELECT kc.chunk_id::text, kd.document_id::text, 'in_document', kd.tenant_id
                FROM knowledge_chunks kc JOIN knowledge_documents kd ON kd.document_id=kc.document_id
                UNION ALL
                -- ★v7 §27-21 이 이름으로 지정한 세 축. issue_code 와 team 은 테이블이 아니라
                --   컬럼이므로 여기서 **노드로 투영**한다. 없던 게 아니라 노출을 안 했던 것이다.
                --   Case → Issue
                SELECT cc.case_id::text, 'issue:'||cc.issue_code, 'has_issue', cc.tenant_id
                FROM customer_cases cc WHERE cc.issue_code IS NOT NULL
                UNION ALL
                --   Issue → Policy  (issue 를 다룬 Case 의 Team scope 로 정책 문서를 잇는다)
                SELECT DISTINCT 'issue:'||cc.issue_code, kd.document_id::text, 'governed_by', kd.tenant_id
                FROM customer_cases cc
                JOIN knowledge_documents kd ON kd.tenant_id=cc.tenant_id
                WHERE cc.issue_code IS NOT NULL AND kd.scope IS NOT NULL
                  AND kd.scope = ANY(string_to_array(cc.intent, ','))
                UNION ALL
                --   Issue → Team
                SELECT DISTINCT 'issue:'||cc.issue_code, 'team:'||cc.owner_team_id, 'handled_by', cc.tenant_id
                FROM customer_cases cc
                WHERE cc.issue_code IS NOT NULL AND cc.owner_team_id IS NOT NULL
            ), walk(node_id, edge_type, depth) AS (
                SELECT dst, edge_type, 1 FROM edges WHERE src=%s AND tenant_id=%s AND edge_type=ANY(%s)
                UNION ALL SELECT e.dst, e.edge_type, w.depth+1 FROM walk w JOIN edges e ON e.src=w.node_id
                WHERE w.depth < %s AND e.tenant_id=%s AND e.edge_type=ANY(%s)
            ) SELECT node_id, edge_type, depth FROM walk ORDER BY depth, node_id""",
            (node_id, self.tenant_id, edge_types, depth, self.tenant_id, edge_types),
        )

    async def path(self, src: str, dst: str, max_depth: int = 4) -> list[dict]:
        if max_depth < 1:
            return []
        return self._rows(
            """WITH RECURSIVE evidence AS (
                SELECT cc.case_id::text AS case_id, cc.tenant_id,
                       x.item->>'evidence_id' AS evidence_id,
                       x.item->>'source_id' AS source_id
                FROM customer_cases cc
                JOIN case_events ce ON ce.case_id=cc.case_id AND ce.tenant_id=cc.tenant_id
                CROSS JOIN LATERAL jsonb_array_elements(
                  COALESCE(ce.payload_json->'evidence',
                           ce.payload_json->'state_patch'->'evidence', '[]'::jsonb)
                ) AS x(item)
                WHERE cc.tenant_id=%s
            ), graph(src, dst, edge_type, tenant_id) AS (
                SELECT case_id, evidence_id, 'has_evidence', tenant_id FROM evidence
                UNION ALL
                SELECT e.evidence_id, kc.chunk_id::text, 'references_chunk', e.tenant_id
                FROM evidence e JOIN knowledge_chunks kc ON kc.chunk_id::text=e.source_id
                JOIN knowledge_documents kd ON kd.document_id=kc.document_id AND kd.tenant_id=e.tenant_id
                UNION ALL
                SELECT kc.chunk_id::text, kd.document_id::text, 'in_document', kd.tenant_id
                FROM knowledge_chunks kc JOIN knowledge_documents kd ON kd.document_id=kc.document_id
                UNION ALL
                SELECT e.evidence_id, kd.document_id::text, 'references_document', e.tenant_id
                FROM evidence e JOIN knowledge_documents kd
                  ON kd.document_id::text=e.source_id AND kd.tenant_id=e.tenant_id
            ), walk(node_id, edge_type, depth, trail) AS (
                SELECT %s::text, 'start', 0, ARRAY[%s::text]
                UNION ALL
                SELECT g.dst, g.edge_type, w.depth+1, w.trail||g.dst
                FROM walk w JOIN graph g ON g.src=w.node_id AND g.tenant_id=%s
                WHERE w.depth < %s AND NOT g.dst=ANY(w.trail)
            ), target AS (SELECT trail FROM walk WHERE node_id=%s)
            SELECT w.node_id, w.edge_type, w.depth
            FROM walk w CROSS JOIN target t
            WHERE w.node_id=ANY(t.trail) ORDER BY w.depth""",
            (self.tenant_id, src, src, self.tenant_id, max_depth, dst),
        )

    async def subgraph(self, root_id: str, depth: int = 2) -> dict:
        rows = await self.neighbors(root_id, ["owns", "has_event", "proposed", "approved", "contains", "in_document", "has_issue", "governed_by", "handled_by"], depth)
        return {"root_id": root_id, "tenant_id": self.tenant_id, "nodes": [root_id] + [r["node_id"] for r in rows], "edges": rows}
