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


def test_resume_ttl_comes_from_guardrails():
    """★값은 24 로 같았지만 코드에 박혀 있어 `resume.token_ttl_hours` 를 낮춰도
    아무 일이 없었다. 보안 한도를 조인 줄 알게 되는 종류다(2026-09-03)."""
    from datetime import UTC, datetime

    from app.application.case_service import CaseService

    meta = CaseService.resume_metadata(CaseService(), "t", "customer_input")
    expires = datetime.fromisoformat(meta["resume_token_expires_at"])
    hours = (expires - datetime.now(UTC)).total_seconds() / 3600
    assert abs(hours - float(get_guardrails().get("resume.token_ttl_hours"))) < 0.1


def test_the_surge_formula_reads_its_constants():
    """★5·1.5·3 이 `is_surge` 에 박혀 있어 `feedback_analytics.surge_*` 를 고쳐도
    급증 판정이 안 바뀌었다. 기준을 조정한 줄 알게 되는 종류다."""
    import app.core.settings as settings_module
    from app.application.feedback_job import is_surge

    real = get_guardrails()

    class Raised:
        """min_count 만 크게 올린 가짜 가드레일."""

        def get(self, key):
            return 1000 if key == "feedback_analytics.surge_min_count" else real.get(key)

    assert is_surge(15, 4.2) is True
    original = settings_module.get_guardrails
    settings_module.get_guardrails = lambda: Raised()
    try:
        # 기준을 올렸으므로 같은 입력이 더 이상 급증이 아니어야 한다
        assert is_surge(15, 4.2) is False
    finally:
        settings_module.get_guardrails = original
