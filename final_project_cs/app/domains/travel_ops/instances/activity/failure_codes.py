# -*- coding: utf-8 -*-
"""Activity Team 실패·예외 코드 — 한 곳에 모은다. `[2026-10-05]`

★출처: 활동 팀(조직 develop `activity/failure_codes.py`)의 구조를 **우리 흐름에 있는 것만** 옮겼다. 팀 쪽 코드 가운데 휴무 요일 ·
  장소 이름 조회 · 대체 후보 풀처럼 우리 흐름에 없는 갈래(예약 경로의 자체 판정)는 가져오지 않았다.
★**무엇이 이미 있고 무엇이 새것인가.** 사람에게 넘기는(escalate) 실패는 코어가 이미 `failure_code` 와 함께 이벤트로 남긴다
  (`TravelTeamBase._escalate`). 여기 코드는 코어가 못 보는 것 — 사람에게 넘기지 않고 **정상 응답으로 끝나는 실패**(이미 시작됨 ·
  정원 초과)와 **도구(API·DB) 예외** — 에만 쓴다. 결과의 `decisions[].failure_code` 와 로그(`acop.activity.failure`)에 같은 값이 나간다.
★로그에는 좌표·장소명·고객 문장·예외 문구를 싣지 않는다 — Case id · capability · 코드와 도구 이름 · 예외 종류만.
★코드는 소문자 스네이크다. 새 코드를 더하면 `DESCRIPTIONS` 에도 한 줄 적는다(시험이 둘이 맞는지 본다).
★`[2026-10-08]` **role-activity 판(`failure_codes.py`)을 합쳤다.** 위 세 코드는 develop 그대로 두고, 보존한 활동 팀 판
  (`team_a.py` · 성립 판정 · 대체 장소 · 장소 이름 조회 · 판정 LLM 실험)이 쓰는 코드를 아래에 더했다. 값이 겹치는 코드는
  없었다(세 코드는 양쪽이 같은 값). ★`[2026-10-09]` team 통합 ①~⑥ 으로 등록된 팀(`team.py`)도 아래 코드 일부(휴무 · 운영시간 밖 ·
  재난 · 시각/장소 모름 · 대체 장소 · 판정 LLM)를 쓴다. 보존본 `team_a.py` 는 `legacy/final_project_cs/` 로 옮겼다.
"""
from __future__ import annotations

from typing import Final

#: 로그 이름. 어디에 쓸지(파일·수집기)는 운영의 logging 설정이 정한다 — 경로를 코드에 박지 않는다.
LOGGER_NAME: Final = "acop.activity.failure"

ALREADY_STARTED: Final = "already_started"
PARTY_OVER_CAPACITY: Final = "party_over_capacity"
TOOL_ERROR: Final = "tool_error"

# ── role-activity 판(보존한 활동 팀 판이 쓴다) `[2026-10-08 합침]` ──────────────────
CLOSED_WEEKDAY: Final = "closed_weekday"
DISASTER_BLOCKS: Final = "disaster_blocks"
PLACE_UNKNOWN: Final = "place_unknown"
TIME_UNKNOWN: Final = "time_unknown"
PLACE_NOT_FOUND: Final = "place_not_found"
PLACE_AMBIGUOUS: Final = "place_ambiguous"
PLACE_EXISTS_UNREGISTERED: Final = "place_exists_unregistered"
PLACE_LOOKUP_BLOCKED: Final = "place_lookup_blocked"
ALTERNATIVES_WITHHELD: Final = "alternatives_withheld"
ALTERNATIVES_NO_CONTENT_ID: Final = "alternatives_no_content_id"
ALTERNATIVES_NO_COORDINATES: Final = "alternatives_no_coordinates"
ALTERNATIVES_POOL_UNAVAILABLE: Final = "alternatives_pool_unavailable"
ALTERNATIVES_NONE: Final = "alternatives_none"
ALTERNATIVES_UNCONFIRMED: Final = "alternatives_unconfirmed"
# ★`[2026-10-06]` 활동 판정 LLM(D-CS-008). 섀도 모드에서는 차이 로그에만 나가고 고객 결과에는 나가지 않는다.
LIVE_CLOSED: Final = "live_closed"
OUTSIDE_HOURS: Final = "outside_hours"
LLM_TIMEOUT: Final = "llm_timeout"
LLM_SCHEMA_INVALID: Final = "llm_schema_invalid"
LLM_UNCITED: Final = "llm_uncited"
LLM_ERROR: Final = "llm_error"
LLM_FALLBACK_RULE: Final = "llm_fallback_rule"

DESCRIPTIONS: Final[dict[str, str]] = {
    ALREADY_STARTED: "이미 시작됐거나 끝난 활동이다 — 성립을 다시 점검하지 않는다",
    PARTY_OVER_CAPACITY: "신청 인원이 정원을 넘는다",
    TOOL_ERROR: "읽기 도구(API·DB)가 예외를 냈다 — 삼키지 않고 다시 던졌다",
    # ── role-activity 판 ──
    CLOSED_WEEKDAY: "요청 요일이 정기휴무 요일이다(판정: 불가)",
    DISASTER_BLOCKS: "위급재난이 확인돼 성립하지 않는다(판정: 불가)",
    PLACE_UNKNOWN: "예약의 장소·운영 정보를 읽지 못했다(판정: 정보 부족)",
    TIME_UNKNOWN: "예약 시각을 읽지 못해 성립 여부를 판정하지 않았다(판정: 정보 부족)",
    PLACE_NOT_FOUND: "고객이 말한 장소 이름을 카탈로그·TourAPI 에서 하나로 특정하지 못했다(고객에게 되묻는다)",
    PLACE_AMBIGUOUS: "고객이 말한 장소 이름이 카탈로그의 둘 이상을 가리킨다(고객에게 고르게 한다)",
    PLACE_EXISTS_UNREGISTERED: "장소는 실재하지만 우리 카탈로그에 없다(저장하지 않고 고객에게 되묻는다)",
    PLACE_LOOKUP_BLOCKED: "장소 조회가 막혀 있는지 없는지 확인하지 못했다(없음이 아니다 — 사람에게 넘긴다)",
    ALTERNATIVES_WITHHELD: "위급재난이라 대체 장소를 안내하지 않았다",
    ALTERNATIVES_NO_CONTENT_ID: "원래 장소의 식별자가 없어 대체 후보를 찾지 못했다",
    ALTERNATIVES_NO_COORDINATES: "원래 장소의 좌표가 없어 근처 대체 후보를 잴 수 없었다",
    ALTERNATIVES_POOL_UNAVAILABLE: "대체 후보 풀을 읽지 못했다(원래 장소가 카탈로그에 없거나 조회 실패)",
    ALTERNATIVES_NONE: "최대 반경(10km) 안에 조건에 맞는 대체 후보가 없다",
    ALTERNATIVES_UNCONFIRMED: "대체 후보는 있으나 운영 여부를 확인한 곳이 없어 안내하지 않았다",
    LIVE_CLOSED: "웹 공지상 그 날짜에 휴무·통제가 확인됐다(LLM 모드, 판정: 불가)",
    OUTSIDE_HOURS: "운영시간 원문상 예약 시각이 운영시간 밖이다(LLM 모드, 판정: 불가)",
    LLM_TIMEOUT: "판정 LLM 호출이 시간 제한을 넘었다(판정: 모름)",
    LLM_SCHEMA_INVALID: "판정 LLM 의 응답을 판정으로 읽을 수 없었다 — 빈 본문·JSON 아님·허용 밖 값(판정: 모름)",
    LLM_UNCITED: "판정 LLM 이 근거를 대지 못했다 — 인용이 원문에 없거나 출처가 검색 목록에 없다(판정: 모름)",
    LLM_ERROR: "판정 LLM 호출이 그 밖의 이유로 실패했다 — 429·키 없음·네트워크(판정: 모름)",
    LLM_FALLBACK_RULE: "LLM 모드에서 LLM 판정이 실패해 규칙 판정으로 답했다",
}
