# -*- coding: utf-8 -*-
"""재난문자가 활동을 막는가 — 유스케이스 수정본 §8 재해 분류표(D2). `[2026-10-11]` 구현 계획 2.4.

★기준은 **등급이 아니라 재해의 성격**이다.
    지역 위험형   그 구에 가는 것 자체가 위험 — 실내 · 야외 모두 막는다
    야외 위험형   야외에 있는 것만 위험 — 야외 활동만 막는다. 실내인지 모르면 막지도 넘기지도 않고 묻는다(UC-A3 `3b2`)
    반영 안 함    막지 않는다
    분류되지 않음 막지 않고 근거 · 경고로 남긴다(UC-A3 `3b4`)
★`[2026-10-11 사용자 결정]` 표 앞에 세 규칙을 둔다(골든셋 검수 — disaster-03 · 09 · 10).
    ① 해제 · 복구 문자(「복구가 완료」 등 — 상황이 끝났다는 말)는 막지 않는다
    ② 문자에 통제 시간이 적혀 있으면 **방문 시각이 그 안일 때만** 막는다 — 문제가 생긴 시각에만 막는다
    ③ 그 장소를 이름으로 지목해 관람 · 운영 중단을 알리는 문자는 재해구분(「기타」 포함)과 상관없이 막는다 — 가도 못 본다
★표 · 낱말은 `config/guardrails.yaml` 의 `travel.safety.impact` 하나다 — 재난 정지(`day_kinds` · `trip_kinds`)와 한곳에 둔다.
★문자는 이미 그 장소의 구 · 시각으로 걸러져 온다(`read.disaster` → `disaster_msg.near()`). 여기서 지역을 다시 가르지 않는다.

계산만 한다. DB · 도구 · LLM 을 부르지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

REGION = "region"
OUTDOOR = "outdoor"
IGNORED = "ignored"
UNCLASSIFIED = "unclassified"
#: ③ 장소 지목 중단 공지 · ② 통제 시간 밖 — 분류 결과에 이유를 남기려고 따로 이름을 둔다
PLACE_CLOSED = "place_closed"
OUTSIDE_WINDOW = "outside_window"

#: 통제 시간 — 「10/14 06:00~10/14 12:00」 · 「14:00~14:20」(날짜가 없으면 문자를 보낸 날)
_WINDOW = re.compile(r"(?:(\d{1,2})/(\d{1,2})\s*)?(\d{1,2}):(\d{2})\s*[~∼-]\s*(?:(\d{1,2})/(\d{1,2})\s*)?(\d{1,2}):(\d{2})")


def _key(text: Any) -> str:
    return "".join(str(text or "").split())


@dataclass(frozen=True)
class ImpactRules:
    region: frozenset[str]
    outdoor: frozenset[str]
    ignored: frozenset[str]
    #: 본문에 이 낱말이 있으면 반영하지 않는다 — 훈련 · 해제 문자(재난 정지와 같은 `travel.safety.exclude_keywords`)
    exclude_words: tuple[str, ...] = ()
    #: ① 상황이 끝났다는 말(띄어쓰기 무시) — 막지 않는다
    release_words: tuple[str, ...] = ()
    #: ③ 장소 이름과 함께 있으면 그 장소가 닫혔다는 말(띄어쓰기 무시)
    closure_words: tuple[str, ...] = ()

    @classmethod
    def load(cls) -> ImpactRules:
        from app.core.settings import get_guardrails

        guard = get_guardrails()

        def listed(name: str) -> frozenset[str]:
            return frozenset(_key(x) for x in guard.get(f"travel.safety.impact.{name}"))

        def words(name: str) -> tuple[str, ...]:
            return tuple(_key(x) for x in guard.get(name))

        return cls(region=listed("region_kinds"), outdoor=listed("outdoor_kinds"), ignored=listed("ignored_kinds"),
                   exclude_words=tuple(str(x) for x in guard.get("travel.safety.exclude_keywords")),
                   release_words=words("travel.safety.impact.release_keywords"),
                   closure_words=words("travel.safety.impact.place_closure_keywords"))

    def is_released(self, text: Any) -> bool:
        """훈련 문자(재난 정지와 같은 낱말)와 ① 상황이 끝났다는 문자.

        ★`[2026-10-13]` 「끝났나」는 공용 판정(`notice_status`)도 본다 — 재난 정지 제외 낱말에서 「해제」를 뺐기 때문이다
          (「해제 시까지 대피」 · 「해제 예정」은 끝이 아니다). 「통제가 완전 해제되었음」 · 「교통통제 해제」는 공용 판정이 끝으로 본다."""
        # ★팀은 ports 를 직접 부르지 않는다(계약 시험 `test_team_tool_discipline`) — 공용 판정은 부품 층(`planning.safety`)이 넘긴다
        from app.domains.travel_ops.components.planning.safety import notice_status

        return (any(word in str(text or "") for word in self.exclude_words)
                or any(word in _key(text) for word in self.release_words)
                or notice_status(str(text or "")).ended)

    def kind_class(self, kind: Any, text: Any = "") -> str:
        if self.is_released(text):
            return IGNORED
        key = _key(kind)
        if key in self.region:
            return REGION
        if key in self.outdoor:
            return OUTDOOR
        if key in self.ignored:
            return IGNORED
        return UNCLASSIFIED

    def names_place_closed(self, text: Any, place_name: Any) -> bool:
        """③ 본문이 그 장소를 이름으로 지목하고 중단 · 휴관 · 통제를 알리나. 이름을 모르면 False(짐작하지 않는다)."""
        name, body = _key(place_name), _key(text)
        return bool(name) and name in body and any(word in body for word in self.closure_words)


def control_window(text: Any, created_at: Any) -> tuple[datetime, datetime] | None:
    """② 본문에 적힌 통제 시간. 못 읽으면 None — 그때는 시간을 보지 않고 표대로 간다(모르는 시간을 「끝났다」로 읽지 않는다)."""
    try:
        sent = datetime.fromisoformat(str(created_at))
    except (TypeError, ValueError):
        return None
    match = _WINDOW.search(str(text or ""))
    if match is None:
        return None
    m1, d1, h1, n1, m2, d2, h2, n2 = match.groups()
    try:
        start = sent.replace(month=int(m1 or sent.month), day=int(d1 or sent.day), hour=int(h1), minute=int(n1),
                             second=0, microsecond=0)
        end = start.replace(month=int(m2 or m1 or sent.month), day=int(d2 or d1 or sent.day), hour=int(h2), minute=int(n2))
    except ValueError:
        return None
    return (start, end) if start <= end else None


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


def assess(messages: Iterable[dict[str, Any]], outdoor: bool | None, rules: ImpactRules, *,
           at: datetime | None = None, place_name: str | None = None) -> Impact:
    """`outdoor`: 야외면 True · 실내면 False · 모르면 None(장소의 `weather_sensitive` 와 같은 뜻). `at`: 방문 시각."""
    out = Impact()
    for message in messages:
        if not isinstance(message, dict):
            continue
        text = message.get("text")
        window = control_window(text, message.get("created_at")) if isinstance(at, datetime) else None
        if rules.is_released(text):
            kind = IGNORED                                              # 훈련 · 해제 · ① 복구
        elif window is not None and not (window[0] <= at <= window[1]):
            kind = OUTSIDE_WINDOW                                       # ② 문제가 생긴 시각이 아니다
        elif rules.names_place_closed(text, place_name):
            kind = PLACE_CLOSED                                         # ③ 그 장소가 닫혔다(「기타」여도)
        else:
            kind = rules.kind_class(message.get("kind"), text)
        item = {**message, "impact": kind}
        if kind in (REGION, PLACE_CLOSED) or (kind == OUTDOOR and outdoor is True):
            out.blocks.append(item)
        elif kind == OUTDOOR and outdoor is None:
            out.ask.append(item)
        elif kind == UNCLASSIFIED:
            out.unclassified.append(item)
        else:
            out.no_effect.append(item)
    return out
