from app.core.settings import get_guardrails
from app.presentation.api.mcp import mcp


# invariant: INV-CS-SEC-007
def test_scopes_are_guardrail_owned():
    """★2026-08-18: Composer 쓰기 채널 이식(S-COMPOSER-WRITE-CHANNEL-PORT)이
    guardrails.yaml에 composer:read/validate/write 3개를 추가했다. 이 계약
    테스트가 그 변경을 안 반영한 채 남아 있었다 — 여기서 맞춘다.

    ★2026-09-06: `composer:admin` 추가(v9 §8-D · D-011). 항목 하나를 켜고 끄는
      것(`/toggle`·`/changes`, `composer:write`)과 선언 **전체**를 갈아끼우거나
      되돌리는 것(`/apply`·`/restore`)은 다른 행위다.

    ★2026-09-06: `ops:reload` 추가(sample 에서 reload 계약 이식). `composer:write`
      (저장)와 분리한다 — 저장은 되돌릴 수 있지만 반영은 그 순간 트래픽이 받는
      것을 바꾼다.

    ★2026-09-14: `trip:read`·`trip:write` 추가(여행 일정 API). Trip 은 Case 보다
      오래 살고 쓰기가 일정 버전을 올린다 — `case:*` 와 나눈다.

    ★이름에서 개수를 뺐다 — scope 가 늘 때마다 함수 이름이 낡는다."""
    assert set(get_guardrails().get("security.scopes")) == {
        "case:read", "case:write", "order:read", "return:read", "action:approve", "mcp:read",
        "composer:read", "composer:validate", "composer:write", "composer:admin",
        "ops:introspect", "ops:reload", "trip:read", "trip:write",
    }


# invariant: INV-CS-SEC-008
def test_mcp_has_exactly_three_read_scoped_tools():
    tools = mcp._tool_manager._tools
    assert set(tools) == {"get_my_cases", "get_case_detail", "open_support_case"}
    assert all(tool.meta["required_scope"] == "mcp:read" for tool in tools.values())
