# -*- coding: utf-8 -*-
"""재난문자가 활동을 막는가 — 유스케이스 수정본 §8 재해 분류표(D2). `[2026-10-11]` 구현 계획 2.4.

★기준은 **등급이 아니라 재해의 성격**이다.
    지역 위험형   그 구에 가는 것 자체가 위험 — 실내 · 야외 모두 막는다
    야외 위험형   야외에 있는 것만 위험 — 야외 활동만 막는다. 실내인지 모르면 막지도 넘기지도 않고 묻는다(UC-A3 `3b2`)
    반영 안 함    막지 않는다
    분류되지 않음 막지 않고 근거 · 경고로 남긴다(UC-A3 `3b4`)
★표는 `config/guardrails.yaml` 의 `travel.safety.impact` 하나다 — 재난 정지(`day_kinds` · `trip_kinds`)와 한곳에 둔다.
★문자는 이미 그 장소의 구 · 시각으로 걸러져 온다(`read.disaster` → `disaster_msg.near()`). 여기서 지역을 다시 가르지 않는다.

계산만 한다. DB · 도구 · LLM 을 부르지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

REGION = "region"
OUTDOOR = "outdoor"
IGNORED = "ignored"
UNCLASSIFIED = "unclassified"


def _key(kind: Any) -> str:
    return "".join(str(kind or "").split())


@dataclass(frozen=True)
class ImpactRules:
    region: frozenset[str]
    outdoor: frozenset[str]
    ignored: frozenset[str]
    #: 본문에 이 낱말이 있으면 반영하지 않는다 — 훈련 · 해제 문자(재난 정지와 같은 `travel.safety.exclude_keywords`)
    exclude_words: tuple[str, ...] = ()

    @classmethod
    def load(cls) -> ImpactRules:
        from app.core.settings import get_guardrails

        guard = get_guardrails()

        def listed(name: str) -> frozenset[str]:
            return frozenset(_key(x) for x in guard.get(f"travel.safety.impact.{name}"))

        return cls(region=listed("region_kinds"), outdoor=listed("outdoor_kinds"), ignored=listed("ignored_kinds"),
                   exclude_words=tuple(str(x) for x in guard.get("travel.safety.exclude_keywords")))

    def kind_class(self, kind: Any, text: Any = "") -> str:
        if any(word in str(text or "") for word in self.exclude_words):
            return IGNORED
        key = _key(kind)
        if key in self.region:
            return REGION
        if key in self.outdoor:
            return OUTDOOR
        if key in self.ignored:
            return IGNORED
        return UNCLASSIFIED


@dataclass
class Impact:
    """문자들을 분류한 결과. 각 목록은 문자에 `impact`(분류)를 붙인 사본이다."""
    blocks: list[dict[str, Any]] = field(default_factory=list)
    ask: list[dict[str, Any]] = field(default_factory=list)       # 야외 위험형인데 실내외를 모른다
    unclassified: list[dict[str, Any]] = field(default_factory=list)
    no_effect: list[dict[str, Any]] = field(default_factory=list)

    def record(self) -> dict[str, Any]:
        """`decisions` 에 싣는 모양 — 문자 원문은 근거(evidence)가 들고, 여기에는 분류와 건수만."""
        def brief(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [{"kind": m.get("kind"), "step": m.get("step"), "impact": m.get("impact"),
                     "created_at": m.get("created_at")} for m in items]
        return {"blocks": bool(self.blocks), "blocking": brief(self.blocks), "ask": brief(self.ask),
                "unclassified": brief(self.unclassified), "no_effect": len(self.no_effect)}


def assess(messages: Iterable[dict[str, Any]], outdoor: bool | None, rules: ImpactRules) -> Impact:
    """`outdoor`: 야외면 True · 실내면 False · 모르면 None(장소의 `weather_sensitive` 와 같은 뜻)."""
    out = Impact()
    for message in messages:
        if not isinstance(message, dict):
            continue
        kind = rules.kind_class(message.get("kind"), message.get("text"))
        item = {**message, "impact": kind}
        if kind == REGION or (kind == OUTDOOR and outdoor is True):
            out.blocks.append(item)
        elif kind == OUTDOOR and outdoor is None:
            out.ask.append(item)
        elif kind == UNCLASSIFIED:
            out.unclassified.append(item)
        else:
            out.no_effect.append(item)
    return out
