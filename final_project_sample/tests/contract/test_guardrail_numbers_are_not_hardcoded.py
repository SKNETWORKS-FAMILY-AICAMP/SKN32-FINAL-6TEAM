"""가드레일에 적힌 수치가 **실제로 통제하는가** (cs 에서 먼저 찾은 결함의 이식).

★`CLAUDE.md` §3 · `RULE.md` §3.1 — 가드레일 수치는 한 곳에만 둔다. 코드가 같은
  값을 따로 박으면, 설정 파일의 숫자는 **아무것도 통제하지 못하면서 통제하는
  것처럼 보인다.**

2026-09-05 실측(세 건 다 cs 와 동일했다):
  - `llm_call_timeout_seconds: 20` ↔ 어댑터 기본값 60.0 → **선언 20초, 실제 60초**
  - `resume.token_ttl_hours: 24` ↔ `timedelta(hours=24)` 하드코딩 → 낮춰도 무반응
  - `feedback_analytics.surge_*` ↔ `is_surge` 에 5·1.5·3 리터럴 → 기준 변경 무반응
"""
from __future__ import annotations

from datetime import UTC, datetime

from acop_basement.core.settings import get_guardrails


def test_llm_timeout_comes_from_guardrails():
    from acop_basement.infrastructure.llm.openai import OpenAITeamLLM

    expected = float(get_guardrails().get("reliability.llm_call_timeout_seconds"))
    assert OpenAITeamLLM().timeout == expected


def test_resume_ttl_comes_from_guardrails():
    from acop_basement.application.case_service import CaseService

    meta = CaseService.resume_metadata(CaseService(), "t", "customer_input")
    expires = datetime.fromisoformat(meta["resume_token_expires_at"])
    hours = (expires - datetime.now(UTC)).total_seconds() / 3600
    assert abs(hours - float(get_guardrails().get("resume.token_ttl_hours"))) < 0.1


def test_the_surge_formula_reads_its_constants():
    import acop_basement.core.settings as settings_module
    from acop_basement.application.feedback_job import is_surge

    real = get_guardrails()

    class Raised:
        def get(self, key):
            return 1000 if key == "feedback_analytics.surge_min_count" else real.get(key)

    assert is_surge(15, 4.2) is True
    original = settings_module.get_guardrails
    settings_module.get_guardrails = lambda: Raised()
    try:
        assert is_surge(15, 4.2) is False
    finally:
        settings_module.get_guardrails = original
