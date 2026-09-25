# -*- coding: utf-8 -*-
"""구글 장소(Places API New) — **새벽 3시 식당 영업 확인** 전용. `[2026-09-25]` D-020

★두 가지만 한다.
    find_place_id(name, lat, lon)   우리 장소 → 구글 `place_id`. 이름 검색 결과가 우리 좌표에서
                                    `match_radius_m` 안일 때만 같은 곳으로 본다(먼 것을 맞다고 하지 않는다)
    open_verdict(place_id, start, end)
                                    그 시각에 여는가 — `open` · `closed` · `unknown`

★★약관 — `place_id` 만 저장한다. 영업시간 원문은 **판정에만 쓰고 버린다**(저장·캐시 안 함, 응답 캐시도
  끈다). `wiki/research/place-api-quota-and-terms.md`.
★공통 규율(`base.py`)을 지킨다 — 못 가져오면 `None` + 이유를 센다, HTTP 200 이어도 본문을 본다.
★키는 `ACOP_GOOGLE_MAPS_API_KEY`. 비어 있으면 이 어댑터를 **만들지 않는다**(부르는 쪽이 「꺼짐」을 센다).
★★`[2026-09-25 사용자 지시]` **무료 한도를 무조건 넘지 않는다** — 호출 예산(`call_budget.CallBudget`)이
  **필수 인자**다. 부르기 전에 DB 에서 월·일 한 칸을 확보하고, 못 하면 부르지 않는다(`budget_exhausted`).
  요금 등급(`[확인 2026-09-25, 공식 요금표]`): 영업시간 상세 = Place Details **Enterprise**(월 1,000건 무료),
  장소 찾기(id·좌표) = Text Search **Pro**(월 5,000건 무료). 상세는 **한 번에 한 곳**이다(`places/{id}`).
`[실측 2026-09-25]` 실제 키로 4건 — 찾기·상세 응답 모양이 이 코드의 가정과 같았다(영업시간 구간에 날짜 포함).

출처: Places API (New) — `POST https://places.googleapis.com/v1/places:searchText`,
`GET https://places.googleapis.com/v1/places/{id}`, 인증은 `X-Goog-Api-Key`, 받을 칸은 `X-Goog-FieldMask`.
`[미확인]` 실제 키로 부른 적이 아직 없다 — 응답 모양은 공식 문서 기준이다. 키가 들어오면 라이브로 확인한다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import math
from typing import Any, Callable
from zoneinfo import ZoneInfo

import httpx

from .base import TravelSource

KST = ZoneInfo("Asia/Seoul")
SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAIL_URL = "https://places.googleapis.com/v1/places/{place_id}"
#: 받을 칸 — 적을수록 싸다. 검색은 id·이름·좌표만, 상세는 영업 상태·영업시간만
SEARCH_FIELDS = "places.id,places.displayName,places.location"
METER_SEARCH = "google_places_text_search_pro"
METER_DETAILS = "google_places_details_enterprise"
DETAIL_FIELDS = "id,businessStatus,currentOpeningHours,regularOpeningHours"
#: 구글 요일(0=일요일) ↔ 파이썬 요일(0=월요일)
_GOOGLE_DAY = {6: 0, 0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6}


class GooglePlaces(TravelSource):
    name = "google_places"
    cache_ttl_seconds = 0          # ★약관 — 영업시간을 담아 두지 않는다

    def __init__(self, *, api_key: str, budget: Any, match_radius_m: float = 300.0,
                 request: Callable[..., httpx.Response] | None = None, **kwargs: Any) -> None:
        kwargs.pop("cache", None)   # ★응답 캐시를 받지 않는다(위 약관)
        super().__init__(**kwargs)
        if not api_key:
            raise ValueError("ACOP_GOOGLE_MAPS_API_KEY 가 비어 있다 — 어댑터를 만들지 않는다")
        if budget is None:
            raise ValueError("호출 예산 없이 구글을 부르지 않는다 — 무료 한도를 넘을 수 있다")
        self._key, self.match_radius_m, self._budget = api_key, float(match_radius_m), budget
        # ★시험이 네트워크 없이 돌 수 있게 — (method, url, headers, json) → Response
        self._request = request or self._http_request

    def _http_request(self, method: str, url: str, headers: dict[str, str],
                      json: dict[str, Any] | None) -> httpx.Response:
        proxy = getattr(self, "_proxy", None)
        kwargs: dict[str, Any] = {"headers": headers, "timeout": self._timeout}
        if proxy:
            kwargs["proxy"] = proxy
        return httpx.request(method, url, json=json, **kwargs)

    def _call(self, method: str, url: str, fields: str, meter: str,
              body: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not self._allow():
            return None
        if not self._budget.try_reserve(meter):
            # ★무료 한도 보호 — 부르지 않는다. 세고 「모름」으로 넘긴다(부르는 쪽이 fatal 로 센다)
            self._miss("budget_exhausted", meter)
            return None
        headers = {"X-Goog-Api-Key": self._key, "X-Goog-FieldMask": fields,
                   "Content-Type": "application/json"}
        try:
            response = self._request(method, url, headers, body)
        except httpx.TimeoutException as exc:
            self._miss("timeout", str(exc))
            return None
        except httpx.HTTPError as exc:
            self._miss("transport_error", f"{type(exc).__name__}: {exc}")
            return None
        if response.status_code != 200:
            self._miss(f"http_{response.status_code}", response.text[:200])
            return None
        try:
            payload = response.json()
        except ValueError:
            self._miss("not_json", response.text[:200])
            return None
        if not isinstance(payload, dict):
            self._miss("unexpected_shape", type(payload).__name__)
            return None
        if "error" in payload:
            self._miss("body_error", str(payload["error"])[:200])
            return None
        return payload

    # ── 우리 장소 → 구글 place_id ────────────────────────────────
    def find_place_id(self, *, name: str, latitude: float, longitude: float
                      ) -> tuple[str, float] | None | str:
        """(place_id, 거리 m). 못 불렀으면 `None`, 불렀는데 **맞는 곳이 없으면** `"unmatched"`.

        ★둘을 가른다 — 못 부른 것은 다음 회차에 다시 부르고, 맞는 곳이 없는 것은 판정으로 남긴다.
        """
        payload = self._call("POST", SEARCH_URL, SEARCH_FIELDS, METER_SEARCH, {
            "textQuery": name, "languageCode": "ko", "maxResultCount": 5,
            "locationBias": {"circle": {"center": {"latitude": latitude, "longitude": longitude},
                                        "radius": self.match_radius_m}}})
        if payload is None:
            return None
        best: tuple[str, float] | None = None
        for place in payload.get("places") or []:
            location = place.get("location") or {}
            if "latitude" not in location or not place.get("id"):
                continue
            meters = _distance_m(latitude, longitude, float(location["latitude"]),
                                 float(location["longitude"]))
            if meters <= self.match_radius_m and (best is None or meters < best[1]):
                best = (str(place["id"]), round(meters, 1))
        return best if best is not None else "unmatched"

    # ── 그 시각에 여는가 ──────────────────────────────────────────
    def open_verdict(self, place_id: str, *, start: datetime, end: datetime) -> tuple[str, str] | None:
        """(verdict, 이유 한 줄). 못 불렀으면 `None`. ★영업시간 원문은 돌려주지 않는다(약관)."""
        payload = self._call("GET", DETAIL_URL.format(place_id=place_id), DETAIL_FIELDS, METER_DETAILS)
        if payload is None:
            return None
        return verdict_from_details(payload, start=start, end=end)


def verdict_from_details(payload: dict[str, Any], *, start: datetime, end: datetime) -> tuple[str, str]:
    """상세 응답 → (open|closed|unknown, 이유). ★순수 함수 — 시험이 응답 모양을 직접 넣는다.

    - 임시·영구 휴업(`businessStatus`)이면 closed
    - 영업시간(`currentOpeningHours` — 특별 영업일 반영, 없으면 `regularOpeningHours`) 중 한 구간이
      계획한 **[시작, 끝] 전체를 덮으면** open. 걸쳐만 있으면 closed(일찍 닫거나 늦게 연다)
    - 영업시간 칸이 없으면 unknown — 「연다」고 하지 않는다
    """
    status = str(payload.get("businessStatus") or "")
    if status == "CLOSED_PERMANENTLY":
        return "closed", "영구 휴업"
    if status == "CLOSED_TEMPORARILY":
        return "closed", "임시 휴업"
    hours = payload.get("currentOpeningHours") or payload.get("regularOpeningHours")
    periods = (hours or {}).get("periods")
    if not periods:
        return "unknown", "영업시간 정보가 없다"
    start, end = start.astimezone(KST), end.astimezone(KST)
    for period in periods:
        opens = _moment(period.get("open"), start.date())
        if opens is None:
            continue
        close_point = period.get("close")
        if close_point is None:
            return "open", "24시간 영업"
        closes = _moment(close_point, opens.date())
        if closes is None:
            continue
        if closes <= opens:
            closes += timedelta(days=7)          # 주를 넘는 구간(토 → 일 새벽)
        for shift in (timedelta(0), timedelta(days=-7), timedelta(days=7)):
            if opens + shift <= start and end <= closes + shift:
                return "open", "계획한 시각에 영업"
    return "closed", f"{start:%m-%d %H:%M}~{end:%H:%M} 에 영업하지 않는다"


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def _moment(point: dict[str, Any] | None, anchor: date) -> datetime | None:
    """영업시간의 한 점(요일·시·분, 있으면 날짜) → 서울 시각. 날짜가 없으면 anchor 가 든 주에서 찾는다."""
    if not isinstance(point, dict) or "hour" not in point:
        return None
    hour, minute = int(point.get("hour", 0)), int(point.get("minute", 0))
    when = point.get("date")
    if isinstance(when, dict) and {"year", "month", "day"} <= set(when):
        day = date(int(when["year"]), int(when["month"]), int(when["day"]))
    else:
        if "day" not in point:
            return None
        # anchor 당일이거나 그 전의 가장 가까운 그 요일. 앞뒤 한 주는 부르는 쪽이 ±7일로 본다
        wanted, current = int(point["day"]), _GOOGLE_DAY[anchor.weekday()]   # 0=일요일
        day = anchor - timedelta(days=(current - wanted) % 7)
    if hour == 24:                                              # 24:00 = 다음 날 00:00
        return datetime(day.year, day.month, day.day, tzinfo=KST) + timedelta(days=1)
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=KST)


__all__ = ["GooglePlaces", "verdict_from_details"]
