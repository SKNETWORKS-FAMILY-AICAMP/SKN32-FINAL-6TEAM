# -*- coding: utf-8 -*-
"""Dining Team 패키지.

★**본체를 `__init__.py` 에 두지 않는다.** 옆 파일 하나만 열어도 패키지
  초기화가 먼저 돌아서 Team 의 의존 사슬이 통째로 따라온다. 실제로
  `_base` → `read_tools` → `rag.retriever` → `openai` 까지 이어져,
  DB 만 있으면 되는 원장 함수를 시험하려 해도 LLM 패키지가 필요해진다.

★바깥에서 보는 경로는 파일 하나였을 때와 같다.
  `app.modules.travel_ops.dining:DiningTeam` 등록 문자열을 고치지 않는다.
"""
from .team import DiningTeam

__all__ = ["DiningTeam"]
