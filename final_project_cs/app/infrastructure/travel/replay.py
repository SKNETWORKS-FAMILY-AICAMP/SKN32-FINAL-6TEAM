# -*- coding: utf-8 -*-
"""재생 입력 — 정해 둔 사건 흐름을 **실제 소스와 같은 모양으로** 답한다.

★왜 필요한가. 시연·시험의 사건(역사 화재·도로 통제·당일 휴무·미세먼지 경보)은
  실제 API 가 그 시각에 내주지 않는다. 그렇다고 Team·점검 코드를 시험용으로
  갈라 두면 **시험이 제품 경로를 안 탄다.** 그래서 소스 자리만 바꿔 끼운다.

★★**재생임을 표시한다**(v11 §8-A · 설계대응 §5). 모든 결과에 `mode="replay"` 와
  `source="replay:<종류>"` 를 박는다. 사후에 정한 사건을 실시간 관측처럼 둔갑시키지
  않는다. 알림·계획서에도 이 표시가 따라간다.

★타임라인에 없는 값은 **지어내지 않는다.** 그 종류의 사건이 없으면 `None`(모름)이고,
  점검은 그걸 실패로 센다 — 재생이라고 규율이 느슨해지지 않는다.

사건 하나의 모양:
    {"kind": "air_quality", "from": "2026-09-23T08:50:00+09:00",
     "until": "2026-09-23T13:00:00+09:00", "match": {"district": "송파구"}, "value": {...}}
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


def _time(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


class ReplayTimeline:
    """사건 목록 + 시계. ★시계는 **재생 시각**이다 — 벽시계가 아니다."""

    def __init__(self, events: list[dict[str, Any]], clock: Callable[[], datetime]) -> None:
        self.events = [{**event, "from": _time(event.get("from")),
                        "until": _time(event.get("until"))} for event in events]
        self.clock = clock

    def current(self, kind: str, **match: Any) -> dict[str, Any] | None:
        """지금(재생 시각) 유효한 그 종류의 사건 중 **가장 늦게 시작한 것**."""
        now = self.clock()
        live = [event for event in self.events
                if event.get("kind") == kind
                and (event["from"] is None or event["from"] <= now)
                and (event["until"] is None or now < event["until"])
                and all(event.get("match", {}).get(key) == value
                        for key, value in match.items() if value is not None)]
        if not live:
            return None
        return max(live, key=lambda event: event["from"] or datetime.min.replace(
            tzinfo=now.tzinfo))

    def stamp(self, kind: str, value: dict[str, Any]) -> dict[str, Any]:
        return {**value, "mode": "replay", "source": f"replay:{kind}",
                "confirmed_at": self.clock().isoformat()}


class _ReplaySource:
    kind = ""

    def __init__(self, timeline: ReplayTimeline) -> None:
        self.timeline = timeline
        self.name = f"replay:{self.kind}"

    def _answer(self, **match: Any) -> dict[str, Any] | None:
        event = self.timeline.current(self.kind, **match)
        if event is None:
            return None
        return self.timeline.stamp(self.kind, dict(event.get("value") or {}))


class ReplayWeather(_ReplaySource):
    kind = "forecast"

    def forecast(self, *, latitude: float, longitude: float,
                 at: datetime | None = None) -> dict[str, Any] | None:
        return self._answer()


class ReplayWarning(_ReplaySource):
    kind = "weather_warning"

    def active(self, *, region: str = "서울") -> dict[str, Any] | None:
        value = self._answer(region=region)
        return None if value is None else {**value, "region": region}


class ReplayAir(_ReplaySource):
    kind = "air_quality"

    def at(self, *, district: str | None, sido: str = "서울",
           at: datetime | None = None, latitude: float | None = None,
           longitude: float | None = None) -> dict[str, Any] | None:
        from .air_quality import reading

        event = self.timeline.current(self.kind, district=district)
        if event is None:
            return None
        return self.timeline.stamp(self.kind, reading(dict(event.get("value") or {}),
                                                       source=self.name))


class ReplayRouteEvents(_ReplaySource):
    """경로 구간에 걸린 운행·통제 사건. `targets` 는 「노선:역」·「도로:이름」 모양."""

    kind = "route_event"

    def affecting(self, targets: list[str]) -> dict[str, dict[str, Any]]:
        found = {}
        for target in targets:
            event = self.timeline.current(self.kind, target=target)
            if event is not None:
                found[target] = self.timeline.stamp(self.kind, dict(event.get("value") or {}))
        return found


__all__ = ["ReplayAir", "ReplayRouteEvents", "ReplayTimeline", "ReplayWarning",
           "ReplayWeather"]
