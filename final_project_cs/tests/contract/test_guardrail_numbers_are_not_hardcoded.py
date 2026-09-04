"""가드레일에 적힌 수치가 **실제로 통제하는가**.

★`CLAUDE.md` §3 · `RULE.md` §3.1 — 가드레일 수치는 `config/guardrails.yaml`
  한 곳에만 둔다. 그런데 코드가 같은 값을 따로 박아 두면, 설정 파일의 숫자는
  **아무것도 통제하지 못하면서 통제하는 것처럼 보인다.**

★2026-09-03 실측: `llm_call_timeout_seconds: 20` 이 적혀 있는데 어댑터는
  `timeout: float = 60.0`(openai) · `120.0`(local_ft) 을 기본값으로 박고 있었고,
  조립은 timeout 을 넘기지 않았다. 즉 **선언 20초, 실제 60초/120초.**
  값이 다른 것이 문제고, 같았어도 설정을 바꿔도 안 바뀌는 것이 문제다.
"""
from __future__ import annotations

import pytest

from app.core.settings import get_guardrails


@pytest.mark.parametrize("factory, key", [
    (lambda: __import__("app.infrastructure.llm.openai", fromlist=["x"]).OpenAITeamLLM(),
     "reliability.llm_call_timeout_seconds"),
    (lambda: __import__("app.infrastructure.llm.local_ft", fromlist=["x"])
     .LocalFTTeamLLM(base_url="http://example.invalid"),
     "reliability.local_ft_call_timeout_seconds"),
])
def test_llm_timeout_comes_from_guardrails(factory, key):
    assert factory().timeout == float(get_guardrails().get(key))


def test_the_two_timeouts_are_separate_keys():
    """★로컬 파인튜닝 추론은 원격 API 보다 느리다. 같은 값을 물리면 그 경로가
    타임아웃난다 — 그래서 키를 나눴다. 하나로 합치려면 실측이 먼저다."""
    remote = float(get_guardrails().get("reliability.llm_call_timeout_seconds"))
    local = float(get_guardrails().get("reliability.local_ft_call_timeout_seconds"))
    assert local > remote
