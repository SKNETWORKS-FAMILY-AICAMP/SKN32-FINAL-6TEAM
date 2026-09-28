# -*- coding: utf-8 -*-
"""Dining Team 폴더 — 이 팀의 파일은 전부 이 폴더 안에 둔다(2026-09-28).

★**바깥에서 부르는 경로는 파일 하나였을 때와 같다.**
  등록 문자열 `app.modules.travel_ops.dining:DiningTeam` 와
  `from app.modules.travel_ops.dining import DiningTeam` 를 고치지 않는다.
  그래서 Team 본체는 `team.py` 에 두고 여기서는 다시 내보내기만 한다.

★**본체를 이 `__init__.py` 에 직접 써도 된다.** 시험은 등록 문자열이 가리키는
  클래스가 실제로 정의된 파일을 찾아 검사하므로 어느 쪽이든 통과한다.
  옆에 도우미 파일(`<이름>.py`)이나 하위 폴더를 더 두는 것도 자유다 —
  폴더 안 `.py` 는 전부 이 팀 코드로 보고 같은 규율(인프라 직접 import 금지)을 건다.

★**`dining.py` 파일과 이 폴더를 같이 두지 않는다.** 둘 다 있으면 파이썬은
  폴더를 먼저 불러와 `dining.py` 를 조용히 무시한다 — 고쳐도 반영이 안 된다.
  `tests/contract/test_team_layout.py` 가 이 경우를 막는다.
  엔진을 따로 두려면 `dining_engine/` 처럼 다른 이름의 폴더를 쓴다(Mobility 방식).
"""
from .team import DiningTeam

__all__ = ["DiningTeam"]
