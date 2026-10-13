# -*- coding: utf-8 -*-
"""활동 판정 계층(D-CS-008) — 규칙 · LLM · 섀도.

    from .judge import JudgeContext, build_judge, requests
    judge = build_judge(settings.activity_judge_mode, self.judge_llm)
    verdict = judge.judge(JudgeContext(case_id=…, capability=…, run_id=…), requests.closure(restdate, starts_at))

★3단계(2026-10-06)에서는 계층만 만들었다. Team 의 판정 지점이 이것을 부르게 하는 것은 4단계다
  (`wiki/teams/액티비티 LLM 연동 계획서.md` §6).
"""
from __future__ import annotations

from . import requests
from .llm import LLMJudge, prompt_key, schema_for
from .modes import SHADOW_LOGGER_NAME, ActivityJudge, BackgroundRunner, LLMFirstJudge, ShadowJudge, build_judge
from .rule import RuleJudge
from .types import KINDS, UNKNOWN, VALUES, JudgeContext, JudgeRequest, Verdict

__all__ = [
    "KINDS", "SHADOW_LOGGER_NAME", "UNKNOWN", "VALUES", "ActivityJudge", "BackgroundRunner",
    "JudgeContext", "JudgeRequest", "LLMFirstJudge", "LLMJudge", "RuleJudge", "ShadowJudge",
    "Verdict", "build_judge", "prompt_key", "requests", "schema_for",
]
