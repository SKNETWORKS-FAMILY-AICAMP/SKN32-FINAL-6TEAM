# -*- coding: utf-8 -*-
"""Ignav MCP — 항공편 **검색 + 판매처 예약 링크** 어댑터. `[2026-10-09]`

- 주소 `https://ignav.com/mcp` · 키 `X-Api-Key`(설정 `ignav_api_key`) · JSON-RPC(`tools/call`), 도구 `search_flights`.
  2026-10-08 23:56 ~ 10-09 11:53 기기 playdata 실호출로 응답 모양을 확인했다(`scripts/probe_ignav_mcp.py`).
- 일정마다 `booking_url`(항공사 · OTA 예약 페이지)이 붙는다. 예약 · 결제는 하지 않고 **링크만** 준다.
  ☆열면 그 노선 · 날짜 · 인원의 판매처 검색 화면까지 가고 편이 미리 선택되지는 않았다(제주항공, 사용자 확인).
    같은 모양의 링크가 판매처 오류 화면으로 가기도 했다 — 답에는 다른 링크를 함께 준다(팀이 한다).
- 약관(2026-10-01 판): 받은 항공 데이터는 보관 · 표시 · 재배포 가능, 출처 표시 의무 없음. 정확성 보장 없음 —
  가격은 「조회 시점 참고」다. FAQ 는 몇 시간 넘게 캐시하지 말라 — 응답을 캐시에 담지 않는다.
- 단위를 바꾸지 않는다: `price.amount` 는 시장(`market`) 통화 그대로다. 승객 여럿일 때 1인가 전체인가는 **확인 안 함**.
- `[확인 안 함]` 왕복일 때 돌아오는 구간 항목 이름(`inbound` · `return` 둘 다 읽어 본다) · 정렬 기준(가격순으로 보였다).
- 폴백 금지(`base.py` ①~④): 못 가져오면 `None` 이고 이유를 센다.
"""
from __future__ import annotations

from typing import Any, Callable

import httpx

from .myrealtrip import McpToolTransport, _number

URL = "https://ignav.com/mcp"
SOURCE = "ignav"
#: 검색 한 번에 6.35~21.51초가 걸렸다(2026-10-08~09 playdata). 마이리얼트립과 같은 30초로 둔다. 우리가 고른 값
TIMEOUT_SECONDS = 30.0
#: 한국 시장 가격(원화)으로 받는다 — 2026-10-08 실호출에서 KRW 로 왔다
MARKET = "KR"
CABINS = {"ECONOMY": "economy", "PREMIUM_ECONOMY": "premium_economy", "BUSINESS": "business", "FIRST": "first"}


def _leg(segments: list[Any]) -> dict[str, Any] | None:
    """구간(segment) 여럿을 한 방향의 다리 하나로. 출발은 첫 구간, 도착은 마지막 구간. 편명은 구간마다 이어 붙인다."""
    rows = [row for row in segments if isinstance(row, dict)]
    if not rows:
        return None
    first, last = rows[0], rows[-1]
    depart, arrive = str(first.get("departure_time_local") or ""), str(last.get("arrival_time_local") or "")
    numbers = [f"{row.get('marketing_carrier_code') or ''}{row.get('flight_number') or ''}" for row in rows]
    return {"origin": first.get("departure_airport"), "destination": last.get("arrival_airport"),
            "flightNumber": "/".join(number for number in numbers if number) or None,
            "departDate": depart[:10] or None, "departTime": depart[11:16] or None,
            "arriveDate": arrive[:10] or None, "arriveTime": arrive[11:16] or None,
            "stops": len(rows) - 1, "isDirect": len(rows) == 1,
            "carrierCode": first.get("marketing_carrier_code")}


class IgnavMcp(McpToolTransport):
    name = SOURCE

    def __init__(self, *, api_key: str, url: str = URL,
                 post: Callable[[str, dict[str, Any], dict[str, str]], httpx.Response] | None = None,
                 **kwargs: Any) -> None:
        super().__init__(url=url, post=post, timeout_seconds=TIMEOUT_SECONDS, **kwargs)
        self._key = api_key

    def _extra_headers(self) -> dict[str, str]:
        return {"X-Api-Key": self._key}

    def flight_search(self, *, origin: str, destination: str, depart_date: str, return_date: str | None = None,
                      domestic: bool | None = None, direct_only: bool | None = None, cabin: str | None = None,
                      max_results: int = 10, adults: int | None = None, children: int | None = None,
                      infants: int | None = None) -> dict[str, Any] | None:
        """마이리얼트립 `flight_search` 와 **같은 인자 · 같은 모양**으로 돌려준다. `domestic` 은 이 도구에 필요 없어 받기만 한다."""
        origin, destination = str(origin or "").strip().upper(), str(destination or "").strip().upper()
        if len(origin) != 3 or len(destination) != 3:
            self._miss("no_airport_code", f"{origin!r}->{destination!r}")
            return None
        arguments: dict[str, Any] = {"origin": origin, "destination": destination, "departure_date": depart_date,
                                     "market": MARKET, "max_results": max(1, int(max_results))}
        if return_date:
            arguments["return_date"] = return_date
        for name, value in (("adults", adults), ("children", children), ("infants_on_lap", infants)):
            if value is not None:
                arguments[name] = int(value)
        if cabin and str(cabin).upper() in CABINS:
            arguments["cabin_class"] = CABINS[str(cabin).upper()]
        if direct_only:
            arguments["max_stops"] = 0
        data = self._call("search_flights", arguments)
        if data is None:
            return None
        rows = data.get("itineraries")
        if not isinstance(rows, list):
            self._miss("unexpected_shape", f"search_flights: {sorted(data)[:8]}")
            return None
        flights = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            legs = []
            for side in ("outbound", "inbound", "return"):
                part = row.get(side)
                if isinstance(part, dict):
                    leg = _leg(part.get("segments") or [])
                    if leg is not None:
                        leg["durationMinutes"] = part.get("duration_minutes")
                        legs.append(leg)
            if not legs:
                continue
            price = row.get("price") if isinstance(row.get("price"), dict) else {}
            outbound = row.get("outbound") if isinstance(row.get("outbound"), dict) else {}
            kind = str(row.get("booking_provider_type") or "")
            flights.append({
                "airline_code": str(legs[0].get("carrierCode") or ""), "airline": str(outbound.get("carrier") or ""),
                "duration_minutes": outbound.get("duration_minutes"),
                "stops": legs[0]["stops"], "direct": all(leg["isDirect"] for leg in legs), "legs": legs,
                "price_total": _number(price.get("amount")), "currency": str(price.get("currency") or ""),
                "price_status": str(price.get("status") or ""), "seats": None,
                "seller": str(row.get("booking_provider_name") or ""), "seller_type": kind,
                "link": str(row.get("booking_url") or ""),
                "link_kind": (f"seller_{kind}" if kind else "seller") if row.get("booking_url") else "",
                "self_transfer": bool(row.get("requires_self_transfer"))})
        return self.stamp({"flights": flights, "total": None, "origin": origin, "destination": destination,
                           "depart_date": depart_date, "return_date": return_date}, source=SOURCE)


__all__ = ["IgnavMcp", "SOURCE", "URL"]
