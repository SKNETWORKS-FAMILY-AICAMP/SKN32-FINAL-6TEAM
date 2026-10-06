"""판정 프롬프트 — 종류마다 파일이 있고, 키가 등록 허용 목록에 있는가.

★2026-08-30 결함과 같은 자리를 막는다 — 허용 목록에 없으면 `register_prompt_files()` 가 조용히 건너뛰고
  실제(DB 감사) 호출이 「no active prompt registered」로 멈춘다(`tests/unit/test_prompt_key_registration.py`).
"""
from __future__ import annotations

from app.modules.travel_ops.activity.judge import KINDS, prompt_key
from app.modules.travel_ops.activity.judge.llm import known_prompt_files
from app.tools.read_tools import ALLOWED_PROMPT_KEYS


def test_every_kind_has_a_prompt_file():
    assert set(known_prompt_files()) == set(KINDS)


def test_every_kind_key_is_allowlisted_and_nothing_extra():
    judge_keys = {key for key in ALLOWED_PROMPT_KEYS if key.startswith("activity_judge.")}
    assert judge_keys == {prompt_key(kind) for kind in KINDS}
