# -*- coding: utf-8 -*-
"""재난 · 지진이 났을 때 **정지할 만한 사건인가, 얼마나 심각한가**를 가른다(순수 — DB · 바깥 호출 없음). `[결정 2026-10-06 사용자]`

    level == "day"   재난이 난 시각에 그 지역에 여행객이 있었다 → **그날** 남은 일정을 정지한다
    level == "trip"  전쟁 · 활화산 폭발처럼 아주 심각하다 → **여행 전체**를 정지하고 근처 피난처로 안내한다
    None             정지하지 않는다 — 날씨 재해(호우 · 폭염 …)는 기존대로 실내 대체 · 안전 알림이다(`pending.decide`)

★값은 `config/guardrails.yaml` `travel.safety` 한 곳에 둔다(RULE §3.1). 그 값은 **우리가 고른 것**이다 — 공식 코드표에서 나온 것이 아니다.
★재난문자 재해구분명이 **모르는 값이어도** 본문 낱말(`trip_keywords`)로 심각함을 가른다. 모르는 구분 + 낱말 없음 = 정지하지 않는다(조용히 넘기지 않고 기존 안전 알림으로 남는다).
★훈련 · 해제 문자는 정지시키지 않는다(`exclude_keywords`) — 「민방위 훈련」 문자 한 통으로 여행이 멈추면 안 된다.
★이 파일은 **무엇을 할지의 이름**(`level`)만 정한다. 정지를 쓰고 알리는 일은 `components/watch/safety_pause.py` 가 한다.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Mapping

Level = Literal["day", "trip"]
ShelterType = Literal["civil_defense", "quake_outdoor"]

#: 날씨가 일으키는 재해 — 위급재난 단계여도 여행 전체를 정지하는 근거가 아니다(실내 대체 · 안전 알림이 맡는다). `disaster_msg.WEATHER_KINDS` 와 같은 뜻이다
_WEATHER_KINDS = frozenset({"호우", "태풍", "대설", "강풍", "폭염", "한파", "산사태", "풍랑", "황사", "홍수", "낙뢰"})
#: 대피 장소를 안내할 재해 — 지진 계열은 옥외 대피장소, 전쟁 · 폭발 · 테러 계열은 민방위 대피시설. 화재 · 산불 · 붕괴는 대피 장소 자료로 안내하지 않는다(공식 안내만)
_QUAKE_KINDS = frozenset({"지진", "지진해일"})
_SHELTER_KINDS = frozenset({"민방위", "테러", "폭발", "화산", "원전", "방사능", "가스"})
_SHELTER_KEYWORDS = ("공습경보", "경계경보", "전쟁", "미사일", "생화학", "방사능", "화산", "분화")


@dataclass(frozen=True)
class SafetyRules:
    pause_enabled: bool
    day_steps: frozenset[str]
    day_kinds: frozenset[str]
    trip_steps: frozenset[str]
    trip_kinds: frozenset[str]
    trip_keywords: tuple[str, ...]
    trip_magnitude_min: float
    exclude_keywords: tuple[str, ...]
    # 정지가 이어지는 동안 안내를 다시 보내는 규칙(`[결정 2026-10-06 사용자]` 관련 안내를 계속 보낸다)
    reminder_enabled: bool = True
    reminder_interval_hours: float = 6.0
    reminder_max_count: int = 4
    # 멈춘 다음 날 아침에 「이어갈까요?」를 한 번 묻는다(저절로 재개하지는 않는다)
    morning_ask_enabled: bool = True
    morning_ask_hour: int = 9

    @classmethod
    def from_guardrails(cls) -> "SafetyRules":
        from app.core.settings import get_guardrails

        guard = get_guardrails()

        def listed(name: str) -> list[str]:
            return [str(x) for x in guard.get(f"travel.safety.{name}")]

        return cls(pause_enabled=bool(guard.get("travel.safety.pause_enabled")),
                   day_steps=frozenset(listed("day_steps")), day_kinds=frozenset(listed("day_kinds")),
                   trip_steps=frozenset(listed("trip_steps")), trip_kinds=frozenset(listed("trip_kinds")),
                   trip_keywords=tuple(listed("trip_keywords")),
                   trip_magnitude_min=float(guard.get("travel.safety.trip_magnitude_min")),
                   exclude_keywords=tuple(listed("exclude_keywords")),
                   reminder_enabled=bool(guard.get("travel.safety.reminder.enabled")),
                   reminder_interval_hours=float(guard.get("travel.safety.reminder.interval_hours")),
                   reminder_max_count=int(guard.get("travel.safety.reminder.max_count")),
                   morning_ask_enabled=bool(guard.get("travel.safety.reminder.morning_ask_enabled")),
                   morning_ask_hour=int(guard.get("travel.safety.reminder.morning_ask_hour")))


@dataclass(frozen=True)
class SafetyEvent:
    level: Level
    category: str                      # disaster_msg · earthquake
    kind: str                          # 재해구분(모르면 빈 글자) · 지진
    label: str                         # 고객에게 보일 이름
    step: str | None                   # 재난문자 긴급단계
    at: datetime | None                # 사건 시각(KST) — 모르면 None
    text: str | None                   # 재난문자 원문(그대로)
    key: str                           # 같은 사건의 지문
    shelter_type: ShelterType | None   # 안내할 대피 장소 종류 — None 이면 대피 장소 목록 없이 공식 안내만

    def evidence(self) -> dict[str, Any]:
        """정지의 근거(`trip_safety_pauses.event_json`) — 읽은 값만, 지어낸 것 없음."""
        return {"category": self.category, "kind": self.kind, "label": self.label, "step": self.step,
                "at": self.at.isoformat() if self.at else None, "text": self.text, "level": self.level}


def _moment(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def _key(*parts: Any) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def _shelter_type(kind: str, text: str) -> ShelterType | None:
    if kind in _QUAKE_KINDS:
        return "quake_outdoor"
    if kind in _SHELTER_KINDS or any(word in text for word in _SHELTER_KEYWORDS):
        return "civil_defense"
    return None


def _from_quake(cause: Mapping[str, Any], rules: SafetyRules) -> SafetyEvent | None:
    try:
        magnitude = float(cause["magnitude"])
    except (KeyError, TypeError, ValueError):
        return None                                        # 규모를 모르면 여행 전체를 멈출 근거가 없다 — 그날 정지도 못 한다(지어내지 않는다)
    level: Level = "trip" if magnitude >= rules.trip_magnitude_min else "day"
    at = _moment(cause.get("at"))
    return SafetyEvent(level=level, category="earthquake", kind="지진", label=f"규모 {magnitude:g} 지진", step=None, at=at,
                       text=str(cause["location"]) if cause.get("location") else None,
                       key=_key("earthquake", cause.get("at"), cause.get("location"), magnitude), shelter_type="quake_outdoor")


def _from_message(cause: Mapping[str, Any], rules: SafetyRules) -> SafetyEvent | None:
    kind, step = str(cause.get("kind") or "").strip(), str(cause.get("step") or "").strip()
    text = str(cause.get("text") or "").strip()
    if any(word in text for word in rules.exclude_keywords):
        return None                                        # 훈련 · 해제 — 정지시키지 않는다
    keyword = next((word for word in rules.trip_keywords if word in text), None)
    weather = kind in _WEATHER_KINDS
    trip = ((step in rules.trip_steps and not weather) or kind in rules.trip_kinds or keyword is not None)
    day = step in rules.day_steps and kind in rules.day_kinds
    if not (trip or day):
        return None
    level: Level = "trip" if trip else "day"
    label = (f"{kind}({step})" if kind and step else kind or "긴급 안전 상황")
    return SafetyEvent(level=level, category="disaster_msg", kind=kind, label=label, step=step or None, at=_moment(cause.get("created_at")),
                       text=text or None, key=_key("disaster_msg", cause.get("created_at"), kind, step, text[:80]),
                       shelter_type=_shelter_type(kind, text))


def classify(causes: list[Mapping[str, Any]] | None, rules: SafetyRules | None = None) -> SafetyEvent | None:
    """점검이 낸 원인 목록 → **가장 심각한** 정지 사건 하나(여행 전체가 그날보다 앞선다). 정지할 만한 것이 없으면 None."""
    rules = rules or SafetyRules.from_guardrails()
    if not rules.pause_enabled:
        return None
    found: list[SafetyEvent] = []
    for cause in causes or []:
        category = cause.get("category")
        event = (_from_quake(cause, rules) if category == "earthquake"
                 else _from_message(cause, rules) if category == "disaster_msg" else None)
        if event is not None:
            found.append(event)
    if not found:
        return None
    return sorted(found, key=lambda e: (e.level != "trip",))[0]


__all__ = ["Level", "SafetyEvent", "SafetyRules", "ShelterType", "classify"]
