from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("A-COP")

@mcp.tool(meta={"required_scope": "mcp:read"})
def get_my_cases(customer_id: str, limit: int = 20) -> list[dict]:
    from app.presentation.api.cases import _mcp_cases
    return _mcp_cases(customer_id, limit)

@mcp.tool(meta={"required_scope": "mcp:read"})
def get_case_detail(customer_id: str, case_id: str) -> dict:
    from app.presentation.api.cases import _mcp_detail
    return _mcp_detail(customer_id, case_id)

@mcp.tool(meta={"required_scope": "mcp:read"})
def open_support_case(customer_id: str, message: str, channel: str = "mcp") -> dict:
    from app.presentation.api.cases import _mcp_open
    return _mcp_open(customer_id, message, channel)
