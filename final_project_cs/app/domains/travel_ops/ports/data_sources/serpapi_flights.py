# -*- coding: utf-8 -*-
"""SerpApi Google Flights — 구글 항공권을 **한국 설정**(gl=kr · hl=ko · KRW)으로 검색한다. `[2026-10-09]`

- 주소 `https://serpapi.com/search.json`, `engine=google_flights`. 키(설정 `serpapi_api_key`)는 주소의 `api_key` 로 간다 —
  ★그래서 응답 캐시에 넣지 않는다(캐시 열쇠에 키가 실린다). 무료는 월 250회, 검색 1번 = 1회.
- 2026-10-09 15:08 playdata 실호출(`scripts/probe_serpapi_flights.py`, ICN→NRT 10-20 편도): 5.50초, best 4 · other 30,
  첫 편 에어부산 BX164 07:10 122,900원(Ignav 와 같은 값). 결과 페이지 주소 `search_metadata.google_flights_url` 있음.
- 판매처 목록은 편마다 `booking_token` 으로 **한 번 더** 불러야 하고(1회 더 씀), 받은 예약 주소는 google.com 으로 보내는
  POST(`booking_request.url` + `post_data`)라 눌러서 여는 링크로 줄 수 없다. 15:08 BX164 는 판매처가 에어부산 하나였다.
  → 편마다 가격만 쓰고, 링크는 **구글 항공권 결과 페이지 하나**를 준다(`link_kind="route_search"`, 답 끝에 한 번).
- 왕복은 결과가 가는 편만 담고 가격이 왕복 합이라 다른 소스와 편끼리 묶을 수 없다 — `[2026-10-10]` 편 목록은 비우고
  **왕복 최저가 참고**(`price_insights.lowest_price`)와 결과 페이지 주소만 준다(`round_trip_lowest` · `page`). 1회 쓴다.
  왕복 응답에 두 항목이 오는지는 확인 안 함 — 없으면 그 칸이 빈다.
- 폴백 금지(`base.py` ①~④): 못 가져오면 `None` 이고 이유를 센다.
"""
from __future__ import annotations

from typing import Any, Callable

import httpx

from .base import TravelSource

URL = "https://serpapi.com/search.json"
SOURCE = "serpapi_flights"
#: 검색 한 번 5.50초(서버 처리 5.14초, 2026-10-09 playdata). 넉넉히 30초. 우리가 고른 값
TIMEOUT_SECONDS = 30.0
CABINS = {"ECONOMY": 1, "PREMIUM_ECONOMY": 2, "BUSINESS": 3, "FIRST": 4}


def _segment_number(segment: dict[str, Any]) -> str:
    return str(segment.get("flight_number") or "").replace(" ", "")


def _leg(segments: list[Any], total: Any) -> dict[str, Any] | None:
    rows = [row for row in segments if isinstance(row, dict)]
    if not rows:
        return None
    first, last = rows[0], rows[-1]
    depart = str((first.get("departure_airport") or {}).get("time") or "")
    arrive = str((last.get("arrival_airport") or {}).get("time") or "")
    numbers = [_segment_number(row) for row in rows]
    code = numbers[0][:2] if numbers and len(numbers[0]) > 2 else ""
    return {"origin": (first.get("departure_airport") or {}).get("id"),
            "destination": (last.get("arrival_airport") or {}).get("id"),
            "flightNumber": "/".join(number for number in numbers if number) or None,
            "departDate": depart[:10] or None, "departTime": depart[11:16] or None,
            "arriveDate": arrive[:10] or None, "arriveTime": arrive[11:16] or None,
            "stops": len(rows) - 1, "isDirect": len(rows) == 1, "carrierCode": code or None,
            "durationMinutes": total if isinstance(total, int) else None}


class SerpApiFlights(TravelSource):
    name = SOURCE

    def __init__(self, *, api_key: str, transport: Callable[..., httpx.Response] | None = None, **kwargs: Any) -> None:
        kwargs.pop("cache", None)                    # 캐시 열쇠에 키가 실리므로 받지 않는다
        super().__init__(timeout=TIMEOUT_SECONDS, transport=transport, **kwargs)
        self._key = api_key

    def flight_search(self, *, origin: str, destination: str, depart_date: str, return_date: str | None = None,
                      domestic: bool | None = None, direct_only: bool | None = None, cabin: str | None = None,
                      max_results: int = 10, adults: int | None = None, children: int | None = None,
                      infants: int | None = None) -> dict[str, Any] | None:
        """마이리얼트립 `flight_search` 와 **같은 인자 · 같은 모양**. `domestic` 은 받기만 한다."""
        origin, destination = str(origin or "").strip().upper(), str(destination or "").strip().upper()
        if len(origin) != 3 or len(destination) != 3:
            self._miss("no_airport_code", f"{origin!r}->{destination!r}")
            return None
        base = {"flights": [], "total": None, "origin": origin, "destination": destination,
                "depart_date": depart_date, "return_date": return_date}
        params: dict[str, Any] = {"engine": "google_flights", "departure_id": origin, "arrival_id": destination,
                                  "outbound_date": depart_date, "type": 1 if return_date else 2, "currency": "KRW",
                                  "hl": "ko", "gl": "kr", "api_key": self._key}
        if return_date:
            params["return_date"] = return_date
        for name, value in (("adults", adults), ("children", children), ("infants_on_lap", infants)):
            if value is not None:
                params[name] = int(value)
        if cabin and str(cabin).upper() in CABINS:
            params["travel_class"] = CABINS[str(cabin).upper()]
        if direct_only:
            params["stops"] = 1
        data = self._fetch_json(URL, params)
        if data is None:
            return None
        page = str((data.get("search_metadata") or {}).get("google_flights_url") or "")
        if return_date:
            lowest = (data.get("price_insights") or {}).get("lowest_price")
            return self.stamp({**base, "note": "왕복은 편별 대신 최저가 참고",
                               "round_trip_lowest": float(lowest) if isinstance(lowest, (int, float)) else None,
                               "page": page}, source=SOURCE)
        rows = [*(data.get("best_flights") or []), *(data.get("other_flights") or [])]
        flights = []
        for row in rows[:max(1, int(max_results))]:
            if not isinstance(row, dict):
                continue
            segments = row.get("flights") or []
            leg = _leg(segments, row.get("total_duration"))
            if leg is None:
                continue
            price = row.get("price")
            flights.append({
                "airline_code": str(leg.get("carrierCode") or ""), "airline": str((segments[0] or {}).get("airline") or ""),
                "duration_minutes": row.get("total_duration") if isinstance(row.get("total_duration"), int) else None,
                "stops": leg["stops"], "direct": leg["isDirect"], "legs": [leg],
                "price_total": float(price) if isinstance(price, (int, float)) else None, "currency": "KRW",
                "seats": None, "link": page, "link_kind": "route_search" if page else ""})
        return self.stamp({**base, "flights": flights}, source=SOURCE)

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        error = payload.get("error")
        return str(error)[:200] if error else None


__all__ = ["SOURCE", "SerpApiFlights", "URL"]
