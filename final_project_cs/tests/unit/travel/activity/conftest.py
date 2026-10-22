# -*- coding: utf-8 -*-
"""Activity 시험 공통 — `[2026-10-16]` 규정 검색(RAG)은 운영에서 꺼져 있다(`ActivityTeam._RAG_OFF`).

기존 시험은 규정이 **있는** 경로(취소·변경 판정)를 검증하므로 ON 으로 고정한다. 꺼진 동작은 `test_activity_rag_off.py` 가 따로 본다.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.instances.activity import ActivityTeam


@pytest.fixture(autouse=True)
def _rag_on_for_existing_tests(request, monkeypatch):
    if request.module.__name__.endswith("test_activity_rag_off"):
        return
    monkeypatch.setattr(ActivityTeam, "_RAG_OFF", False)
