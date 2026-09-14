# -*- coding: utf-8 -*-
"""일정 성립 점검 — 바깥 소스를 **한 번에** 돌려 판정 하나로 모은다.

★왜 묶나(2026-09-14 사용자 지적). 일정이 서느냐는 예보·특보·재난문자·대기질·
  통제를 **다 본 뒤에** 정해진다. 소스마다 도구를 따로 주면
    - Team 이 매번 같은 조합을 복붙한다(커머스 때 가드가 팀마다 달라진 모양)
    - 도구 예산이 먼저 바닥난다 — Activity 는 `max_steps=6` 인데 예보·특보만으로
      이미 5 를 썼다(실측). 소스를 셋 더 붙이면 8 이 되어 `ToolBudgetExceeded`
    - 문의 때 판정과 감시 루프의 판정이 서로 다른 조합으로 갈린다
  그래서 **어댑터는 따로(키·성공 코드·한도·주기가 다르다), 점검은 하나**다.

판정 규칙(v11 §0-4 결정 15):

    failed_categories 가 하나라도 있다  → verdict = "fatal"
        ★「항목 하나의 1차·대체 소스가 전부 실패」가 한 건이다. 항목이 하나라도
          끝까지 못 가져오면 치명이다. **조회 실패를 일정 변경 사유로 쓰지 않는다**
          — 무료 API 가 잠깐 끊길 때마다 멀쩡한 일정이 바뀐다.
    disruptions 가 하나라도 있다        → verdict = "disrupted"  (일정 변경 대상)
    둘 다 없다                          → verdict = "clear"

★「이상(disruptions)」과 「주의(advisories)」를 가른다. 특보·재난문자·통제는 **사건**
  이라 이상이다. 예보의 강수확률·풍속은 **수치**라 주의로만 둔다 — 수치 몇부터
  불가인지는 운영 규정이 정할 일이고, 가드레일 값은 우리가 고른 주의 문구 기준이다.

★「해당 없음」과 「미연결」은 실패가 아니다.
    not_applicable  이 장소에는 볼 필요가 없다(실내 활동의 예보)
    not_connected   소스를 아직 붙이지 못했다(활용신청 전·샘플 기간 밖).
                    ★숨기지 않고 목록에 싣는다
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import math
from typing import Any, Callable

#: 아직 못 붙인 항목과 그 이유. ★활용신청이 끝나 어댑터가 붙으면 여기서 지운다.
#:  재난문자는 여기 없다 — 샘플 CSV 판이 붙어 있고(`disaster_msg.py`), 소스가
#:  없을 때의 이유는 조립이 `unavailable["disaster"]` 에 적는다.
#:  ☆2026-09-14 지진정보가 여기 있다가 어댑터(`kma_earthquake.py`)가 붙어 빠졌다.
#:    지금은 비어 있다 — 소스가 없을 때의 이유는 조립이 `unavailable` 에 적는다.
NOT_CONNECTED: dict[str, str] = {}


def forecast_advisories(forecast: dict[str, Any], *, pop_limit: float | None,
                        wind_limit: float | None) -> list[dict[str, Any]]:
    """예보 수치 → 주의 목록. ★「불가」를 만들지 않는다."""
    notes = []
    pop = forecast.get("precipitation_probability")
    wind = forecast.get("wind_speed_kmh")
    if pop is not None and pop_limit is not None and pop >= pop_limit:
        notes.append({"category": "forecast", "field": "precipitation_probability",
                      "value": pop, "limit": pop_limit, "source": forecast.get("source")})
    if wind is not None and wind_limit is not None and wind >= wind_limit:
        notes.append({"category": "forecast", "field": "wind_speed_kmh",
                      "value": wind, "limit": wind_limit, "source": forecast.get("source")})
    return notes


def _default_limits() -> tuple[float | None, float | None]:
    from app.core.settings import get_guardrails

    guardrails = get_guardrails()
    return (guardrails.get("travel.weather.advisory_precipitation_probability"),
            guardrails.get("travel.weather.advisory_wind_speed_kmh"))


def _default_quake_rules() -> tuple[float, float, float]:
    """(규모 하한, 반경 km, 돌아보는 시간). 값은 `config/guardrails.yaml` 한 곳에만 둔다."""
    from app.core.settings import get_guardrails

    guardrails = get_guardrails()
    return (float(guardrails.get("travel.earthquake.magnitude_min")),
            float(guardrails.get("travel.earthquake.radius_km")),
            float(guardrails.get("travel.earthquake.lookback_hours")))


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


class DisruptionCheck:
    """`TravelSources` 를 받아 일정 항목 하나를 점검한다."""

    def __init__(self, sources: Any, *,
                 limits: Callable[[], tuple[float | None, float | None]] | None = None,
                 quake_rules: Callable[[], tuple[float, float, float]] | None = None) -> None:
        self.sources = sources
        self._limits = limits or _default_limits
        self._quake_rules = quake_rules or _default_quake_rules

    def check(self, *, place: dict[str, Any], starts_at: datetime | None,
              region: str = "서울") -> dict[str, Any]:
        sensitive = bool(place.get("weather_sensitive"))
        jobs: dict[str, Callable[[], dict[str, Any]]] = {
            "forecast": lambda: self._forecast(place, starts_at, sensitive),
            "weather_warning": lambda: self._warning(region, sensitive),
            "disaster_msg": lambda: self._disaster(place, starts_at, region, sensitive),
            "traffic_control": lambda: self._traffic(place, starts_at),
            "air_quality": lambda: self._air(place, starts_at, sensitive),
            "earthquake": lambda: self._earthquake(place, starts_at),
        }
        # ★동시에 돌린다 — 소스 하나가 느려도 나머지를 기다리게 하지 않는다.
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = {name: pool.submit(job) for name, job in jobs.items()}
            checks = [futures[name].result() for name in jobs]

        for name, reason in NOT_CONNECTED.items():
            checks.append({"category": name, "status": "not_connected", "reason": reason})

        disruptions = [item for check in checks for item in check.pop("_disruptions", [])]
        advisories = [item for check in checks for item in check.pop("_advisories", [])]
        failed = [check["category"] for check in checks if check["status"] == "failed"]
        verdict = "fatal" if failed else ("disrupted" if disruptions else "clear")
        return {
            "verdict": verdict,
            "disruptions": disruptions,
            "advisories": advisories,
            "checks": checks,
            "failed_categories": failed,
            "not_connected": [c["category"] for c in checks if c["status"] == "not_connected"],
            "place_id": place.get("place_id"),
            "starts_at": starts_at.isoformat() if isinstance(starts_at, datetime) else None,
            "region": region,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    # ── 항목별 ──────────────────────────────────────────────────
    def _forecast(self, place: dict[str, Any], at: datetime | None,
                  sensitive: bool) -> dict[str, Any]:
        base = {"category": "forecast"}
        if not sensitive:
            return {**base, "status": "not_applicable", "reason": "날씨 영향을 받지 않는 장소"}
        source = getattr(self.sources, "weather", None)
        if source is None:
            reason = (getattr(self.sources, "unavailable", {}) or {}).get("weather", "기상 소스 없음")
            return {**base, "status": "failed", "reason": reason}
        latitude, longitude = place.get("latitude"), place.get("longitude")
        if latitude is None or longitude is None:
            # ★「어디인지 모르는 곳의 날씨」는 없다. 좌표가 없으면 값을 못 낸다.
            return {**base, "status": "failed", "reason": "장소 좌표 없음"}
        value = source.forecast(latitude=float(latitude), longitude=float(longitude), at=at)
        if value is None:
            tried = [getattr(s, "name", "?") for s in getattr(source, "sources", [source])]
            return {**base, "status": "failed", "tried": tried,
                    "reason": "1차·대체 소스가 모두 값을 못 냈다"}
        pop_limit, wind_limit = self._limits()
        return {**base, "status": "ok", "source": value.get("source"),
                "fell_back_from": value.get("fell_back_from", []),
                "confirmed_at": value.get("confirmed_at"), "value": value,
                "_advisories": forecast_advisories(value, pop_limit=pop_limit,
                                                   wind_limit=wind_limit)}

    def _warning(self, region: str, sensitive: bool) -> dict[str, Any]:
        base = {"category": "weather_warning"}
        if not sensitive:
            return {**base, "status": "not_applicable", "reason": "날씨 영향을 받지 않는 장소"}
        source = getattr(self.sources, "warning", None)
        if source is None:
            reason = (getattr(self.sources, "unavailable", {}) or {}).get("warning", "특보 소스 없음")
            return {**base, "status": "not_connected", "reason": reason}
        value = source.active(region=region)
        if value is None:
            return {**base, "status": "failed", "tried": [getattr(source, "name", "?")],
                    "reason": "특보 발효 현황을 못 읽었다"}
        disruptions = [{"category": "weather_warning", "kind": item.get("kind"),
                        "areas": item.get("areas", []), "source": value.get("source"),
                        "announced_at": value.get("announced_at"),
                        "confirmed_at": value.get("confirmed_at")}
                       for item in value.get("for_region") or []]
        return {**base, "status": "ok", "source": value.get("source"),
                "confirmed_at": value.get("confirmed_at"), "value": value,
                "_disruptions": disruptions}

    def _disaster(self, place: dict[str, Any], at: datetime | None, region: str,
                  sensitive: bool) -> dict[str, Any]:
        """재난문자. ★날씨형(호우 등)은 날씨 영향 장소에만, 통제·화재 등은 모든 장소에."""
        base = {"category": "disaster_msg"}
        source = getattr(self.sources, "disaster", None)
        if source is None:
            reason = (getattr(self.sources, "unavailable", {}) or {}).get(
                "disaster", "행정안전부 긴급재난문자 — 키 발급 대기 (data.go.kr/data/15134001)")
            return {**base, "status": "not_connected", "reason": reason}
        moment = at if isinstance(at, datetime) else datetime.now(UTC)
        value = source.active(region=region, at=moment, district=place.get("district"))
        if value is None:
            return {**base, "status": "failed", "tried": [getattr(source, "name", "?")],
                    "reason": "재난문자를 못 읽었다"}
        mode = value.get("mode", "api")
        if not value.get("covered", True):
            # ★샘플 기간 밖 = 모름이다. 「재난문자 없음」이라고 답하지 않는다.
            coverage = value.get("coverage") or {}
            return {**base, "status": "not_connected", "mode": mode,
                    "reason": (f"샘플 기간({coverage.get('from')} ~ {coverage.get('to')}) 밖 — "
                               f"실키 발급 대기 (data.go.kr/data/15134001)")}
        disruptions = [{"category": "disaster_msg", "kind": item.get("kind"),
                        "step": item.get("step"), "text": item.get("text"),
                        "created_at": item.get("created_at"), "source": value.get("source"),
                        "mode": mode}
                       for item in value.get("for_region") or []
                       if sensitive or not item.get("weather")]
        return {**base, "status": "ok", "mode": mode, "source": value.get("source"),
                "confirmed_at": value.get("confirmed_at"),
                "unclassified": value.get("unclassified", []),
                "_disruptions": disruptions}


    def _traffic(self, place: dict[str, Any], at: datetime | None) -> dict[str, Any]:
        """교통 돌발·통제. ★장소를 가리지 않는다 — 실내 일정도 가는 길이 막힌다.

        ★ITS 와 UTIC 를 **합친다**(`traffic_chain.CombinedTraffic`). 시내 집회·행사는 UTIC 이
          본체다 — UTIC 가 못 답한 회차에는 ITS 에 태그로 들어온 것만 잡힌다(실측 서울 122건 중
          [집회] 1건). 그때는 `note` 로 남긴다 — 「집회 없음」이라고 단정하지 않는다.
        ★둘 중 하나만 답해도 판정은 한다(`partial_from` 에 못 답한 쪽). 둘 다 못 답하면 치명.
        """
        base = {"category": "traffic_control"}
        source = getattr(self.sources, "traffic", None)
        if source is None:
            reason = (getattr(self.sources, "unavailable", {}) or {}).get(
                "traffic", "교통 돌발 — ITS 키 없음 (ACOP_ITS_API_KEY)")
            return {**base, "status": "not_connected", "reason": reason}
        latitude, longitude = place.get("latitude"), place.get("longitude")
        if latitude is None or longitude is None:
            return {**base, "status": "failed", "reason": "장소 좌표 없음"}
        moment = at if isinstance(at, datetime) else datetime.now(UTC)
        value = source.near(latitude=float(latitude), longitude=float(longitude), at=moment)
        if value is None:
            tried = [getattr(s, "name", "?") for s in getattr(source, "sources", [source])]
            return {**base, "status": "failed", "tried": tried,
                    "reason": "교통 돌발 소스가 모두 못 읽었다"}
        disruptions = [{"category": "traffic_control", "kind": item.get("reason"),
                        "road": item.get("road"), "distance_m": item.get("distance_m"),
                        "message": item.get("message"),
                        "source": item.get("source") or value.get("source")}
                       for item in value.get("for_place") or []]
        advisories = [{"category": "traffic_control", "field": "partial_lane",
                       "value": item.get("road"), "note": item.get("reason"),
                       "source": item.get("source") or value.get("source")}
                      for item in value.get("advisories") or []]
        answered = value.get("sources") or [value.get("source")]
        result = {**base, "status": "ok", "source": value.get("source"),
                  "confirmed_at": value.get("confirmed_at"),
                  "partial_from": value.get("partial_from", []),
                  "_disruptions": disruptions, "_advisories": advisories}
        if "utic" not in answered:
            result["note"] = "UTIC 가 답하지 않았다 — 시내 집회·행사는 ITS 에 태그된 것만 본다"
        return result


    def _air(self, place: dict[str, Any], at: datetime | None,
             sensitive: bool) -> dict[str, Any]:
        """대기질. ★날씨 영향 장소에만 — 전망 데크의 시야, 야외 활동.

        발령 **기준**을 넘으면 이상, 등급 「나쁨」(3) 이상은 주의다. 기준은
        `air_quality.ALERT_THRESHOLDS`(대기환경보전법 시행규칙 별표 7).
        """
        base = {"category": "air_quality"}
        if not sensitive:
            return {**base, "status": "not_applicable", "reason": "날씨 영향을 받지 않는 장소"}
        source = getattr(self.sources, "air", None)
        if source is None:
            reason = (getattr(self.sources, "unavailable", {}) or {}).get(
                "air", "에어코리아 대기오염정보 소스 없음")
            return {**base, "status": "not_connected", "reason": reason}
        district = place.get("district")
        latitude, longitude = place.get("latitude"), place.get("longitude")
        if not district and (latitude is None or longitude is None):
            # ★측정소는 구로, 모델 대체는 좌표로 찾는다. 둘 다 없으면 어디 값인지 모른다.
            return {**base, "status": "failed", "reason": "장소의 구도 좌표도 몰라 값을 고를 수 없다"}
        value = source.at(district=district, at=at, latitude=latitude, longitude=longitude)
        if value is None:
            tried = [getattr(s, "name", "?") for s in getattr(source, "sources", [source])]
            return {**base, "status": "failed", "tried": tried,
                    "reason": "1차·대체 소스가 모두 대기질을 못 냈다"}
        alert = value.get("alert")
        disruptions = [] if not alert else [{
            "category": "air_quality", "kind": f"{alert['pollutant']} {alert['level']} 기준 초과",
            "value": alert["value"], "limit": alert["limit"], "station": value.get("station"),
            "basis": value.get("basis"), "source": value.get("source"),
            "mode": value.get("mode", "live")}]
        grades = [g for g in (value.get("pm10_grade"), value.get("pm25_grade")) if g]
        advisories = [] if alert or not grades or max(grades) < 3 else [{
            "category": "air_quality", "field": "grade", "value": max(grades),
            "station": value.get("station"), "source": value.get("source")}]
        return {**base, "status": "ok", "source": value.get("source"),
                "mode": value.get("mode", "live"), "confirmed_at": value.get("confirmed_at"),
                "fell_back_from": value.get("fell_back_from", []),
                "value": value, "_disruptions": disruptions, "_advisories": advisories}


    def _earthquake(self, place: dict[str, Any], at: datetime | None) -> dict[str, Any]:
        """지진. ★장소를 가리지 않는다 — 실내 시설도 점검·운영 중단이 난다.

        반경 안 + 규모 하한 이상 → 이상, 반경 안 + 미만 → 주의, 반경 밖 → 무시.
        ★「지진 없음」은 빈 목록(아는 사실), 조회 실패는 `None`(모름 → 치명)이다.
        """
        from .kma_earthquake import window_until

        base = {"category": "earthquake"}
        source = getattr(self.sources, "earthquake", None)
        if source is None:
            reason = (getattr(self.sources, "unavailable", {}) or {}).get(
                "earthquake", "기상청 지진정보 소스 없음 (data.go.kr/data/15000420)")
            return {**base, "status": "not_connected", "reason": reason}
        latitude, longitude = place.get("latitude"), place.get("longitude")
        if latitude is None or longitude is None:
            return {**base, "status": "failed", "reason": "장소 좌표 없음"}
        magnitude_min, radius_km, lookback_hours = self._quake_rules()
        until = window_until(at if isinstance(at, datetime) else None, datetime.now(UTC))
        value = source.recent(since=until - timedelta(hours=lookback_hours), until=until)
        if value is None:
            return {**base, "status": "failed", "tried": [getattr(source, "name", "?")],
                    "reason": "지진정보를 못 읽었다"}
        disruptions, advisories = [], []
        for event in value.get("events") or []:
            distance = round(_distance_km(float(latitude), float(longitude),
                                          event["latitude"], event["longitude"]), 1)
            if distance > radius_km:
                continue
            record = {"category": "earthquake", "magnitude": event["magnitude"],
                      "distance_km": distance, "location": event.get("location"),
                      "at": event.get("at"), "intensity": event.get("intensity"),
                      "source": value.get("source")}
            if event["magnitude"] >= magnitude_min:
                disruptions.append({**record, "kind": f"규모 {event['magnitude']} 지진"})
            else:
                advisories.append({**record, "field": "magnitude", "value": event["magnitude"],
                                   "limit": magnitude_min})
        return {**base, "status": "ok", "source": value.get("source"),
                "confirmed_at": value.get("confirmed_at"), "window": value.get("window"),
                "rules": {"magnitude_min": magnitude_min, "radius_km": radius_km,
                          "lookback_hours": lookback_hours},
                "_disruptions": disruptions, "_advisories": advisories}


__all__ = ["DisruptionCheck", "NOT_CONNECTED", "forecast_advisories"]
