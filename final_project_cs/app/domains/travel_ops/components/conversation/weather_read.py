"""고객이 가리킨 일정의 좌표·시각으로 기존 기상 포트를 읽는다."""
from __future__ import annotations

from datetime import datetime
import logging
import math

from .trip_facts import KST

log = logging.getLogger(__name__)


def _number(value, *, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        return None
    return value


def reply(item, *, at, lookup):
    basis = {"requested_at": at.isoformat(), "kind": "forecast"}

    def failed(code):
        return (f"{item.title}의 {at.astimezone(KST):%m월 %d일 %H:%M} 날씨 예보를 확인하지 못했어요. "
                "비가 오지 않는다고 판단하지 않았으며, 일정은 바꾸지 않았어요.",
                {**basis, "unresolved": code})

    place = item.place or {}
    latitude = _number(place.get("latitude"), minimum=-90, maximum=90)
    longitude = _number(place.get("longitude"), minimum=-180, maximum=180)
    if latitude is None or longitude is None:
        return failed("weather_coordinates_missing")
    if lookup is None:
        return failed("weather_source_unavailable")
    try:
        value = lookup(latitude=latitude, longitude=longitude, at=at)
    except Exception as exc:
        # 제공처 예외를 성공으로 숨기지 않는다. 메시지·키·주소를 로그로 옮기지 않는다.
        log.warning("chat weather lookup failed: %s", type(exc).__name__)
        return failed("weather_source_error")
    if not isinstance(value, dict):
        return failed("weather_sources_failed")
    pop = _number(value.get("precipitation_probability"), minimum=0, maximum=100)
    rain = _number(value.get("precipitation_mm"), minimum=0)
    if pop is None and rain is None:
        return failed("weather_precipitation_missing")
    try:
        matched = datetime.fromisoformat(value["matched_hour"])
        matched = matched.replace(tzinfo=KST) if matched.tzinfo is None else matched.astimezone(KST)
        confirmed = datetime.fromisoformat(value["confirmed_at"])
        if confirmed.tzinfo is None:
            raise ValueError("missing timezone")
        if (value.get("kind") != "forecast" or not isinstance(value.get("source"), str) or not value["source"].strip()
                or matched.replace(minute=0, second=0, microsecond=0)
                != at.astimezone(KST).replace(minute=0, second=0, microsecond=0)):
            raise ValueError("forecast identity mismatch")
    except (KeyError, TypeError, ValueError):
        return failed("weather_provenance_invalid")
    values = []
    if pop is not None:
        values.append(f"강수확률 {pop:g}%")
    if rain is not None:
        values.append(f"예상 강수량 {rain:g}mm")
    temperature = _number(value.get("temperature_c"))
    if temperature is not None:
        values.append(f"기온 {temperature:g}°C")
    text = (f"{item.title} — {matched:%m월 %d일 %H:%M} 예보: {', '.join(values)}. "
            f"출처: {value['source']}, 조회: {confirmed.astimezone(KST):%m월 %d일 %H:%M}(한국 시각). "
            "현장 관측이 아닌 예보이며 일정은 바꾸지 않았어요.")
    return text, {**basis, "source": value["source"], "confirmed_at": value["confirmed_at"],
                  "matched_hour": value["matched_hour"], "precipitation_probability": pop,
                  "precipitation_mm": rain, "fell_back_from": value.get("fell_back_from", [])}
