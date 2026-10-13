# -*- coding: utf-8 -*-
"""Activity 실패 · 예외 코드 목록 — 코드마다 설명이 있고 이름 모양이 맞는가.

★`[2026-10-09]` 결과 · 로그와 코드가 맞는지 보던 시험은 보존본 `team_a.py` 를 돌렸다 — `legacy/final_project_cs/tests/unit/travel/`
  로 옮겼다. develop 판 팀의 코드는 그 판정 시험(`tests/unit/travel/activity/`)이 함께 본다.
"""
from __future__ import annotations

import re

from app.domains.travel_ops.instances.activity import failure_codes as fc


def test_every_code_is_described_and_snake_case():
    codes = {v for k, v in vars(fc).items() if k.isupper() and isinstance(v, str) and k != "LOGGER_NAME"}
    assert codes == set(fc.DESCRIPTIONS), "새 코드를 더했으면 DESCRIPTIONS 에도 적는다"
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", c) for c in codes)
