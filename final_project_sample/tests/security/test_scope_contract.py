from acop_basement.core.settings import get_guardrails
from acop_basement.presentation.api.mcp import mcp


def test_composer_scopes_are_guardrail_owned():
    """★`ops:introspect`(읽기) · `composer:write`(쓰기) 는 mcp:read 와 분리된 scope 다 —
    개인 AI 용 표면(mcp)과 우리 도구(외부 개발 콘솔)용 표면은 다르고,
    조회 권한만으로 모듈을 켜고 끄면 안 되므로 읽기·쓰기도 서로 분리한다."""
    assert set(get_guardrails().get("security.scopes")) == {
        "case:read", "case:write", "subscription:read", "technical:read",
        "action:approve", "mcp:read", "ops:introspect", "composer:write",
        "composer:read", "composer:validate",
    }


def test_mcp_has_exactly_three_read_scoped_tools():
    tools = mcp._tool_manager._tools
    assert set(tools) == {"get_my_cases", "get_case_detail", "open_support_case"}
    assert all(tool.meta["required_scope"] == "mcp:read" for tool in tools.values())
