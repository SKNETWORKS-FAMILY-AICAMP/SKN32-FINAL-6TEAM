# -*- coding: utf-8 -*-
"""판정 계층이 주고받는 값 — 요청(`JudgeRequest`)과 판정(`Verdict`).

★판정 종류는 다섯이다(계획서 §4). 값마다 허용 집합이 정해져 있고, 모든 종류에 `unknown` 이 있다 —
  「모름」을 「없음」이나 「성립」으로 읽지 않는다는 원칙을 값 집합에서부터 지킨다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

UNKNOWN = "unknown"

CLOSURE = "closure"                       # ① 정기휴무 원문 — 그 날이 휴무인가
OPERATING_HOURS = "operating_hours"       # ② 운영시간 원문 — 그 시각이 운영시간 안인가
WEATHER_SENSITIVE = "weather_sensitive"   # ③ 실내·실외
DISASTER_EFFECT = "disaster_effect"       # ④ 재난문자 — 이 활동을 막는가
LIVE_STATUS = "live_status"               # ⑤ 실시간 운영 상태(웹 검색)

#: 종류별 허용 값. ★`not_closed` 는 「열려 있다」가 아니다 — 「규칙·원문상 휴무로 잡히지 않는다」다.
VALUES: dict[str, tuple[str, ...]] = {
    CLOSURE: ("closed", "not_closed", UNKNOWN),
    OPERATING_HOURS: ("within", "outside", UNKNOWN),
    WEATHER_SENSITIVE: ("outdoor", "indoor", UNKNOWN),
    DISASTER_EFFECT: ("blocks", "no_effect", UNKNOWN),
    LIVE_STATUS: ("open", "closed", UNKNOWN),
}
KINDS: tuple[str, ...] = tuple(VALUES)

#: 웹 검색을 쓰는 종류. 나머지는 **받은 원문만** 해석한다.
WEB_KINDS = frozenset({LIVE_STATUS})
#: 판정이 `unknown` 이 아니면 원문 인용이 하나 이상 있어야 하는 종류와, 인용을 대조할 입력 칸.
QUOTE_SOURCES: dict[str, tuple[str, ...]] = {
    CLOSURE: ("restdate_text",),
    OPERATING_HOURS: ("usetime_text",),
    DISASTER_EFFECT: ("message_texts",),
}


@dataclass(frozen=True)
class JudgeContext:
    """어느 Case 의 판정인가 — 로그와 감사 기록을 잇는 데만 쓴다. 장소명·고객 문장은 담지 않는다."""

    case_id: UUID | str | None = None
    capability: str | None = None
    run_id: UUID | None = None
    tenant_id: str | None = None


@dataclass(frozen=True)
class JudgeRequest:
    kind: str
    inputs: dict[str, Any]

    def __post_init__(self) -> None:
        if self.kind not in VALUES:
            raise ValueError(f"unknown judge kind: {self.kind}")


@dataclass(frozen=True)
class Verdict:
    kind: str
    value: str
    #: `rule` | `llm`
    source: str
    confidence: float | None = None
    #: 규칙이 무엇으로 정했나(`title` · `category` · `weekly_pattern` …) 또는 LLM 의 판단 이유.
    basis: str | None = None
    quotes: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    #: 이 판정이 실패·강등됐으면 그 코드(`failure_codes.py` 의 `llm_*`).
    failure_code: str | None = None
    #: 검증에서 버린 인용·출처와 이유 — `place_hours.HoursRead.dropped` 와 같은 모양.
    dropped: list[str] = field(default_factory=list)
    #: 호출 계측(LLM 만) — 지연 · 검색 횟수 · 토큰 · 게시일 없는 근거 수.
    metrics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.value not in VALUES[self.kind]:
            raise ValueError(f"{self.kind} does not allow value {self.value!r}")

    @property
    def known(self) -> bool:
        return self.value != UNKNOWN
