from app.core.settings import get_guardrails
from app.presentation.api.mcp import mcp


def test_ten_scopes_are_guardrail_owned():
    """★2026-08-18: Composer 쓰기 채널 이식(S-COMPOSER-WRITE-CHANNEL-PORT)이
    guardrails.yaml에 composer:read/validate/write 3개를 추가했다. 이 계약
    테스트가 그 변경을 안 반영한 채 남아 있었다 — 여기서 맞춘다."""
    assert set(get_guardrails().get("security.scopes")) == {
        "case:read", "case:write", "order:read", "return:read", "action:approve", "mcp:read",
        "composer:read", "composer:validate", "composer:write", "ops:introspect",
    }


def test_mcp_has_exactly_three_read_scoped_tools():
    tools = mcp._tool_manager._tools
    assert set(tools) == {"get_my_cases", "get_case_detail", "open_support_case"}
    assert all(tool.meta["required_scope"] == "mcp:read" for tool in tools.values())
