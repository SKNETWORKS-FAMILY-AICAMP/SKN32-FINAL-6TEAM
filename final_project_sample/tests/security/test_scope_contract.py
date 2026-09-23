from acop_basement.core.settings import get_guardrails
from acop_basement.presentation.api.mcp import mcp


def test_composer_scopes_are_guardrail_owned():
    """★`ops:introspect`(읽기) · `composer:write`(쓰기) 는 mcp:read 와 분리된 scope 다 —
    개인 AI 용 표면(mcp)과 우리 도구(외부 개발 콘솔)용 표면은 다르고,
    조회 권한만으로 모듈을 켜고 끄면 안 되므로 읽기·쓰기도 서로 분리한다.

    ★`ops:reload`(2026-08-31)도 `composer:write` 와 분리한다 — 선언을 저장하는
      것과 살아 있는 프로세스의 조립을 갈아 끼우는 것은 다른 행위다. 저장은
      되돌릴 수 있지만 반영은 그 순간 트래픽이 받는 것을 바꾼다.

    ★`composer:admin`(2026-09-06, D-011)도 `composer:write` 와 분리한다 — 항목 하나를
      켜고 끄는 것과 선언 전체를 갈아끼우거나 되돌리는 것은 다른 행위다."""
    assert set(get_guardrails().get("security.scopes")) == {
        "case:read", "case:write", "subscription:read", "technical:read",
        "action:approve", "mcp:read", "ops:introspect", "composer:write",
        "composer:read", "composer:validate", "composer:admin", "ops:reload",
    }


def test_mcp_has_exactly_three_read_scoped_tools():
    tools = mcp._tool_manager._tools
    assert set(tools) == {"get_my_cases", "get_case_detail", "open_support_case"}
    assert all(tool.meta["required_scope"] == "mcp:read" for tool in tools.values())
