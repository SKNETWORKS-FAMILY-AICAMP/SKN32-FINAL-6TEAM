# -*- coding: utf-8 -*-
"""기상 대체 소스 사슬 — v11 §0-4 결정 15 「값을 모르는 상황을 만들지 않는다」.

1차 소스가 못 주면 **다음 소스로 값을 낸다.** 누가 답했는지는 결과의 `source`
에 그대로 남는다(Open-Meteo 면 `open_meteo`, 기상청이면 `kma`). 대체로 넘어간
사실은 `fell_back_from` 에 싣는다 — 숨기지 않는다.

★★결정 15 의 뒷부분 「대체까지 안 되면 치명 결함 — 서버를 끈다」는 **여기서
  하지 않는다.** 요청 하나를 처리하다 프로세스를 죽이면 그 순간 처리 중이던
  다른 Case 들이 같이 죽는다. 사슬 전체가 실패하면 `all_failed` 를 세고
  ERROR 로 남긴다 — 서버를 끄는 판단은 이 수를 보는 **감시 쪽**의 몫이고,
  아직 만들어지지 않았다(`[미확보]` 2026-09-14).

★속성 `misses` 는 사슬 자신의 것이다. 각 소스의 미스는 그 소스 객체에 따로
  쌓인다 — 합치면 어느 공급자가 문제인지 안 보인다.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import logging
from typing import Any

logger = logging.getLogger(__name__)


class FallbackWeather:
    name = "weather_chain"

    def __init__(self, sources: list[Any]) -> None:
        if not sources:
            raise ValueError("FallbackWeather 에 소스가 하나도 없다")
        self.sources = list(sources)
        self.misses: Counter[str] = Counter()

    def forecast(self, *, latitude: float, longitude: float,
                 at: datetime | None = None) -> dict[str, Any] | None:
        failed: list[str] = []
        for source in self.sources:
            result = source.forecast(latitude=latitude, longitude=longitude, at=at)
            if result is not None:
                if failed:
                    self.misses["fell_back"] += 1
                    result = {**result, "fell_back_from": failed}
                return result
            failed.append(getattr(source, "name", type(source).__name__))

        self.misses["all_failed"] += 1
        logger.error("weather chain exhausted — every source failed: %s", failed)
        return None


__all__ = ["FallbackWeather"]
