from uuid import uuid4

import pytest
from psycopg.types.json import Json

from acop_basement.infrastructure.db.repository import create_case
from acop_basement.infrastructure.db.session import get_connection
from acop_basement.infrastructure.graphstore.sql_adapter import SqlGraphAdapter


@pytest.fixture()
def graph_fixture():
    tenants = [f"test_{uuid4().hex}", f"test_{uuid4().hex}"]
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO tenants (tenant_id, name) VALUES (%s, %s)",
                    [(tenant, "graph adapter test") for tenant in tenants],
                )

            ids = {}
            for tenant in tenants:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO customers (tenant_id, external_id) VALUES (%s, %s) RETURNING customer_id",
                        (tenant, f"customer-{tenant}"),
                    )
                    customer_id = cur.fetchone()[0]
                case_id = create_case(conn, tenant_id=tenant, customer_id=customer_id, subject="graph test")
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO knowledge_documents "
                        "(tenant_id, title, source_uri, scope, version, pii_class) "
                        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING document_id",
                        (tenant, "graph test document", f"test://{tenant}", "test", "1", "none"),
                    )
                    document_id = cur.fetchone()[0]
                    cur.execute(
                        "INSERT INTO knowledge_chunks "
                        "(document_id, chunk_no, content, metadata_json, embedding) "
                        "VALUES (%s, %s, %s, %s, %s) RETURNING chunk_id",
                        (document_id, 0, "graph test chunk", Json({"test": True}), "[" + ",".join(["0"] * 1536) + "]"),
                    )
                    chunk_id = cur.fetchone()[0]
                    cur.execute(
                        "INSERT INTO case_events "
                        "(tenant_id, case_id, aggregate_version, event_type, payload_json, actor_type) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (
                            tenant,
                            case_id,
                            1,
                            "evidence_added",
                            Json({"evidence": [{"evidence_id": f"ev-{tenant}", "source_id": str(chunk_id)}]}),
                            "test",
                        ),
                    )
                ids[tenant] = {
                    "case_id": str(case_id),
                    "document_id": str(document_id),
                    "chunk_id": str(chunk_id),
                }

            conn.commit()
            yield conn, tenants[0], tenants[1], ids
        finally:
            conn.rollback()
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM case_events WHERE tenant_id = ANY(%s)", (tenants,))
                    cur.execute(
                        "DELETE FROM knowledge_chunks WHERE document_id IN "
                        "(SELECT document_id FROM knowledge_documents WHERE tenant_id = ANY(%s))",
                        (tenants,),
                    )
                    cur.execute("DELETE FROM knowledge_documents WHERE tenant_id = ANY(%s)", (tenants,))
                    cur.execute("DELETE FROM customer_cases WHERE tenant_id = ANY(%s)", (tenants,))
                    cur.execute("DELETE FROM customers WHERE tenant_id = ANY(%s)", (tenants,))
                    cur.execute("DELETE FROM tenants WHERE tenant_id = ANY(%s)", (tenants,))


@pytest.mark.asyncio
async def test_path_returns_case_evidence_chunk_document_hops(graph_fixture):
    conn, tenant, _, ids = graph_fixture
    adapter = SqlGraphAdapter(conn, tenant_id=tenant)

    path = await adapter.path(ids[tenant]["case_id"], ids[tenant]["document_id"], max_depth=4)

    assert path
    assert [hop["edge_type"] for hop in path] == ["start", "has_evidence", "references_chunk", "in_document"]
    assert [hop["depth"] for hop in path] == [0, 1, 2, 3]
    assert path[-1]["node_id"] == ids[tenant]["document_id"]


@pytest.mark.asyncio
async def test_graph_queries_are_tenant_isolated(graph_fixture):
    conn, tenant, other_tenant, ids = graph_fixture
    adapter = SqlGraphAdapter(conn, tenant_id=tenant)
    other = ids[other_tenant]

    assert await adapter.path(other["case_id"], other["document_id"], max_depth=4) == []
    assert await adapter.neighbors(other["case_id"], ["has_event"], depth=1) == []

    subgraph = await adapter.subgraph(other["case_id"], depth=2)
    assert subgraph["tenant_id"] == tenant
    assert subgraph["nodes"] == [other["case_id"]]
    assert subgraph["edges"] == []


@pytest.mark.asyncio
async def test_neighbors_and_subgraph_return_expected_structure(graph_fixture):
    conn, tenant, _, ids = graph_fixture
    adapter = SqlGraphAdapter(conn, tenant_id=tenant)
    case_id = ids[tenant]["case_id"]

    depth_one = await adapter.neighbors(case_id, ["has_event"], depth=1)
    depth_two = await adapter.neighbors(case_id, ["has_event"], depth=2)
    subgraph = await adapter.subgraph(case_id, depth=2)

    assert depth_one
    assert all(row["edge_type"] == "has_event" and row["depth"] == 1 for row in depth_one)
    assert len(depth_two) >= len(depth_one)
    assert subgraph["root_id"] == case_id
    assert subgraph["nodes"] == [case_id] + [row["node_id"] for row in depth_two]
    assert subgraph["edges"] == depth_two


@pytest.mark.asyncio
async def test_recursive_walk_respects_depth_limit_on_cycle(graph_fixture):
    conn, tenant, _, ids = graph_fixture
    adapter = SqlGraphAdapter(conn, tenant_id=tenant)

    rows = await adapter.neighbors(ids[tenant]["document_id"], ["contains", "in_document"], depth=4)

    assert rows
    assert max(row["depth"] for row in rows) == 4
    assert all(1 <= row["depth"] <= 4 for row in rows)
    assert len(rows) == 4
