# -*- coding: utf-8 -*-
"""Activity Team 실패·예외 코드 — 한 곳에 모은다. `[2026-10-05]`

★출처: 활동 팀(조직 develop `activity/failure_codes.py`)의 구조를 **우리 흐름에 있는 것만** 옮겼다. 팀 쪽 코드 가운데 휴무 요일 ·
  장소 이름 조회 · 대체 후보 풀처럼 우리 흐름에 없는 갈래(예약 경로의 자체 판정)는 가져오지 않았다.
★**무엇이 이미 있고 무엇이 새것인가.** 사람에게 넘기는(escalate) 실패는 코어가 이미 `failure_code` 와 함께 이벤트로 남긴다
  (`TravelTeamBase._escalate`). 여기 코드는 코어가 못 보는 것 — 사람에게 넘기지 않고 **정상 응답으로 끝나는 실패**(이미 시작됨 ·
  정원 초과)와 **도구(API·DB) 예외** — 에만 쓴다. 결과의 `decisions[].failure_code` 와 로그(`acop.activity.failure`)에 같은 값이 나간다.
★로그에는 좌표·장소명·고객 문장·예외 문구를 싣지 않는다 — Case id · capability · 코드와 도구 이름 · 예외 종류만.
★코드는 소문자 스네이크다. 새 코드를 더하면 `DESCRIPTIONS` 에도 한 줄 적는다(시험이 둘이 맞는지 본다).
"""
from __future__ import annotations

from typing import Final

#: 로그 이름. 어디에 쓸지(파일·수집기)는 운영의 logging 설정이 정한다 — 경로를 코드에 박지 않는다.
LOGGER_NAME: Final = "acop.activity.failure"

ALREADY_STARTED: Final = "already_started"
PARTY_OVER_CAPACITY: Final = "party_over_capacity"
TOOL_ERROR: Final = "tool_error"

DESCRIPTIONS: Final[dict[str, str]] = {
    ALREADY_STARTED: "이미 시작됐거나 끝난 활동이다 — 성립을 다시 점검하지 않는다",
    PARTY_OVER_CAPACITY: "신청 인원이 정원을 넘는다",
    TOOL_ERROR: "읽기 도구(API·DB)가 예외를 냈다 — 삼키지 않고 다시 던졌다",
}
