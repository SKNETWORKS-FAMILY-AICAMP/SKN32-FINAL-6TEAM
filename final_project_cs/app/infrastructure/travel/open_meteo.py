# -*- coding: utf-8 -*-
"""Open-Meteo 기상 어댑터 — **키가 필요 없다.**

실측(2026-09-09):

    GET https://api.open-meteo.com/v1/forecast
        ?latitude=37.5665&longitude=126.9780&timezone=Asia/Seoul
        &hourly=temperature_2m,precipitation_probability,precipitation,wind_speed_10m
    → HTTP 200, hourly 48행, 단위 °C / % / mm / km/h

★**그래서 여섯 소스 중 이것 하나만 오늘 붙는다.** TourAPI·기상청·ODsay 는
  전부 키를 요구했다(같은 날 실호출로 확인: 401 / 401 / 200+ApiKeyAuthFailed).
  키 발급은 사람이 해야 하는 일이라 그 셋은 골격만 두고 비활성이다.

★비상업 사용 기준 하루 10,000 호출까지 무료라고 공급자가 밝히고 있다.
  **상업 배포 전에 요금제를 다시 확인해야 한다** — 지금 값은 조사 시점 기준이다.

★예보는 **예정**이지 관찰이 아니다. `confirmed_at` 은 「우리가 조회한 시각」,
  `matched_hour` 는 「예보표에서 고른 칸」이다. Team 이 이 둘을 섞어 말하면
  예보를 현장 확인처럼 전한다(v10 §4-D).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import TravelSource

ENDPOINT = "https://api.open-meteo.com/v1/forecast"

#: 우리가 읽는 시간별 항목. ★늘리기 전에 Team 이 실제로 쓰는지 본다 —
#:  안 쓰는 값을 받아 두면 「있으니까 판정에 넣자」가 근거 없이 생긴다.
HOURLY_FIELDS = ("temperature_2m", "precipitation_probability",
                 "precipitation", "wind_speed_10m")

#: 예보가 닿는 범위. 이 밖을 물으면 **모름**이다. 늘려 잡아 답하지 않는다.
MAX_FORECAST_DAYS = 16


class OpenMeteoWeather(TravelSource):
    name = "open_meteo"

    def forecast(self, *, latitude: float, longitude: float,
                 at: datetime | None = None) -> dict[str, Any] | None:
        """`at` 시각의 예보 한 칸. 못 가져오거나 범위 밖이면 `None`(모름)."""
        target = at
        if target is not None and target.tzinfo is not None:
            target = target.astimezone().replace(tzinfo=None)

        days = self._days_needed(target)
        if days is None:
            self._miss("outside_forecast_window",
                       f"요청 {target}, 예보 한계 {MAX_FORECAST_DAYS}일")
            return None

        payload = self._fetch_json(ENDPOINT, {
            "latitude": latitude, "longitude": longitude,
            "hourly": ",".join(HOURLY_FIELDS),
            "timezone": "auto",          # ★장소의 현지 시각으로 받는다
            "forecast_days": days,
        })
        if payload is None:
            return None

        hourly = payload.get("hourly")
        if not isinstance(hourly, dict) or not hourly.get("time"):
            self._miss("empty_hourly", str(list(payload))[:120])
            return None

        index = self._pick_hour(hourly["time"], target)
        if index is None:
            self._miss("hour_not_in_response", str(target))
            return None

        return self.stamp({
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "requested_at": target.isoformat() if target else None,
            # ★고른 칸을 밝힌다. "14시를 물었는데 13시 값을 봤다" 를 숨기지 않는다.
            "matched_hour": hourly["time"][index],
            "temperature_c": self._at(hourly, "temperature_2m", index),
            "precipitation_probability": self._at(hourly, "precipitation_probability", index),
            "precipitation_mm": self._at(hourly, "precipitation", index),
            "wind_speed_kmh": self._at(hourly, "wind_speed_10m", index),
            "timezone": payload.get("timezone"),
            "kind": "forecast",   # ★관찰이 아니다
        }, source=self.name)

    # ── 부품 ────────────────────────────────────────────────────
    @staticmethod
    def _days_needed(target: datetime | None) -> int | None:
        if target is None:
            return 1
        ahead = (target.date() - datetime.now().date()).days
        if ahead < 0 or ahead >= MAX_FORECAST_DAYS:
            return None
        return ahead + 1

    @staticmethod
    def _pick_hour(times: list[str], target: datetime | None) -> int | None:
        """요청 시각이 속한 **정시 칸**을 고른다.

        ★가장 가까운 칸을 찾아 헤매지 않는다. 정시로 내림한 값이 표에 없으면
          `None` 이다 — 없는 것을 근처 값으로 바꿔치기하면 그게 폴백이다.
        """
        if target is None:
            return 0
        key = target.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")
        try:
            return times.index(key)
        except ValueError:
            return None

    @staticmethod
    def _at(hourly: dict[str, Any], field: str, index: int) -> Any:
        values = hourly.get(field)
        if not isinstance(values, list) or index >= len(values):
            return None      # ★없으면 없는 대로 둔다. 0 으로 채우지 않는다
        return values[index]


__all__ = ["ENDPOINT", "HOURLY_FIELDS", "MAX_FORECAST_DAYS", "OpenMeteoWeather"]
