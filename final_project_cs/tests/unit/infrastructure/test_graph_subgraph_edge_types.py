import pytest

from app.infrastructure.graphstore.sql_adapter import SqlGraphAdapter


@pytest.mark.asyncio
async def test_subgraph_uses_all_current_edge_types():
    adapter = SqlGraphAdapter(object(), tenant_id="tenant")
    seen = {}

    async def neighbors(root_id, edge_types, depth):
        seen.update(root_id=root_id, edge_types=edge_types, depth=depth)
        return []

    adapter.neighbors = neighbors
    result = await adapter.subgraph("root", depth=3)

    assert result["nodes"] == ["root"]
    assert seen["edge_types"] == [
        "owns", "has_event", "proposed", "approved", "contains", "in_document",
        "has_issue", "governed_by", "handled_by",
    ]
