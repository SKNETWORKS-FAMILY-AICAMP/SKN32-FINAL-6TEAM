# -*- coding: utf-8 -*-
"""`config/project.yaml` 이 등록한 Team 목록 — **테스트가 기대하는 값**.

★왜 한 곳에 두는가(2026-09-09). 이 목록이 세 파일에 **각각 손으로** 박혀
  있었다(`test_composition_root` · `test_project_composition` ·
  `test_introspection_contract`). 도메인을 여행으로 갈아끼우자 세 곳이 동시에
  붉어졌고, 고칠 때 한 곳을 빠뜨리면 「어느 쪽이 맞는지」를 다시 세어야 한다.

★이 파일은 `project.yaml` 을 **읽지 않는다.** 읽으면 선언과 자기 자신을
  비교하는 셈이라 무엇도 못 잡는다. 등록을 바꾸면 사람이 여기도 바꾸고,
  그 diff 가 「등록을 바꿨다」는 기록이 된다.

여행 도메인 전환: 계획서 v10 §5. 커머스 시절 값은 아래에 기록으로 남긴다.
"""
from __future__ import annotations

#: 현재 등록 (v10 여행, 2026-09-09~)
EXPECTED_TEAM_IDS: frozenset[str] = frozenset({
    "activity",
    "booking_handoff",
    "mobility",
    "dining",
    "lodging",
    "flight",
})

#: ★옛 커머스 등록(v9)은 여기 두지 않는다. 2026-09-10 에 구현·카탈로그·allowlist
#:  에서 전부 빠졌고, 쓰이지 않는 목록을 남기면 "되돌릴 수 있다" 는 **틀린 인상**을
#:  준다 — 되돌리려면 그날 이전 커밋에서 모듈을 되살려야 한다.

#: LLM 주입 **배선**을 확인할 Team 하나. 이 팀이 LLM 을 쓴다는 뜻이 아니다 —
#: 실측(2026-09-09) 여행 여섯 중 `self.llm` 을 **부르는 팀은 0개**다.
#: 판정이 계산으로 되는 동안은 LLM 을 부르지 않는다(v10 §4-D).
#: 그래도 조립이 llm 을 넣어 주는지는 확인해야 한다 — 나중에 쓰기 시작할 때
#: 배선이 끊겨 있으면 그때 `None` 으로 터진다.
LLM_WIRED_TEAM_ID = "activity"

__all__ = ["EXPECTED_TEAM_IDS", "LLM_WIRED_TEAM_ID"]
