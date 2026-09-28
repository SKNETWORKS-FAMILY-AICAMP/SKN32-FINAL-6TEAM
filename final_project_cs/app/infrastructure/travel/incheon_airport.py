# -*- coding: utf-8 -*-
"""인천국제공항공사 여객편 운항현황 — **편명으로 지연·결항을 본다.**

실측(2026-09-10, 실 키):

    GET https://apis.data.go.kr/B551177/StatusOfPassengerFlightsOdp/getPassengerArrivalsOdp
        ?from_time=0000&to_time=2400&lang=K&type=json
    → HTTP 200
      {"typeOfFlight":"I","airline":"트리니티항공","flightId":"TW9624",
       "scheduleDateTime":"2235","estimatedDateTime":"0001","airport":"윈청옌후 국제공항",
       "gatenumber":"104","carousel":"10","exitnumber":"B","remark":"도착",
       "airportCode":"YCU","terminalId":"P02"}
    `flight_id` 로 좁히면 그 편만 온다.

★★**인천은 한국공항공사 API 에 없다.** 한국공항공사는 김포·김해·제주 등 14개
  공항이고 인천은 **별도 기관**(B551177)이다. 여행 CS 에서 국제선 대부분이
  인천을 지나가므로 이쪽이 먼저다. 키는 같다(공공데이터포털 계정당 하나).

★**지연 시간을 우리가 계산하지 않는다.**
  `scheduleDateTime`·`estimatedDateTime` 은 **날짜 없는 HHMM** 이다. 위 샘플만
  봐도 2235 → 0001 로 자정을 넘는다. 날짜 없이 뺄셈하면 「-22시간 21분 빨리
  도착」 같은 값이 나온다. 그 숫자가 고객 답변까지 가면 안 된다.
  **두 시각을 그대로 싣고, 상태는 공급자의 `remark` 를 그대로 전한다.**

★찾는 데 오래 걸린 이유를 적어 둔다 — 경로를 13번 추측했는데 전부
  `NO_OPENAPI_SERVICE_ERROR` 였다. 맞는 것은 `StatusOfPassengerFlightsOdp`
  이고, 내가 시도한 `StatusOfPassengerFlightsDSOdp`/`...DS` 는 없는 이름이다.
  **오퍼레이션명은 추측하지 말고 활용신청 상세의 호출주소를 본다.**
"""
from __future__ import annotations

from typing import Any

from .base import TravelSource

BASE_URL = "https://apis.data.go.kr/B551177/StatusOfPassengerFlightsOdp"

ARRIVALS = "getPassengerArrivalsOdp"
DEPARTURES = "getPassengerDeparturesOdp"


class IncheonAirportFlights(TravelSource):
    """인천공항 여객편. ★인천만이다 — 김포·김해·제주는 한국공항공사 쪽이다."""

    name = "incheon_airport"

    #: 이 소스가 다루는 공항. Team 이 다른 공항을 물으면 「모름」이어야 한다.
    AIRPORT_CODE = "ICN"

    def __init__(self, *, service_key: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key

    def flight(self, flight_id: str, *, arriving: bool = True
               ) -> dict[str, Any] | None:
        """편명 하나의 현재 상태. 못 찾으면 `None`(모름).

        ★`arriving` 이 방향을 가른다. 도착편과 출발편은 **다른 오퍼레이션**이고,
          같은 편명이 양쪽에 있을 수 있다(경유). 방향을 안 주고 합치면
          어느 쪽 시각인지 모르게 된다.
        """
        if not self._key:
            self._miss("no_service_key")
            return None
        if not flight_id or not flight_id.strip():
            self._miss("no_flight_id")
            return None

        operation = ARRIVALS if arriving else DEPARTURES
        payload = self._fetch_json(f"{BASE_URL}/{operation}", {
            "serviceKey": self._key, "numOfRows": "10", "pageNo": "1",
            "from_time": "0000", "to_time": "2400", "lang": "K", "type": "json",
            "flight_id": flight_id.strip().upper()})
        if payload is None:
            return None

        rows = self._rows(payload)
        if not rows:
            # ★없다 = 「그 편이 없다」가 아니다. 오늘 그 방향 일정에 없을 뿐일
            #   수도 있다(어제 편, 내일 편, 반대 방향). 「모름」으로 둔다.
            self._miss("not_in_todays_schedule", f"{flight_id} ({operation})")
            return None

        row = rows[0]
        return self.stamp({
            "flight_id": str(row.get("flightId") or ""),
            "airline": str(row.get("airline") or "") or None,
            "direction": "arrival" if arriving else "departure",
            "airport_code": self.AIRPORT_CODE,
            # ★상대 공항. 도착편이면 출발지, 출발편이면 도착지다.
            "counterpart_airport": str(row.get("airport") or "") or None,
            "counterpart_airport_code": str(row.get("airportCode") or "") or None,
            # ★★HHMM 이고 **날짜가 없다.** 뺄셈하지 않는다.
            "scheduled_hhmm": str(row.get("scheduleDateTime") or "") or None,
            "estimated_hhmm": str(row.get("estimatedDateTime") or "") or None,
            "times_are_hhmm_without_date": True,
            # ★상태는 공급자 문구 그대로. 우리가 다시 분류하지 않는다.
            "status_text": str(row.get("remark") or "") or None,
            "terminal": str(row.get("terminalId") or "") or None,
            "gate": str(row.get("gatenumber") or "") or None,
            "carousel": str(row.get("carousel") or "") or None,
            "exit": str(row.get("exitnumber") or "") or None,
            # ★지연/결항 판정을 boolean 으로 내지 않는다 — 아래 주석 참고.
            "answers_delay_minutes": False,
        }, source=self.name)

    @staticmethod
    def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
        body = (payload.get("response") or {}).get("body")
        if not isinstance(body, dict):
            return []
        items = body.get("items")
        if isinstance(items, dict):
            rows = items.get("item") or []
        else:
            rows = items or []
        if isinstance(rows, dict):
            return [rows]
        return [r for r in rows if isinstance(r, dict)]

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        header = (payload.get("response") or {}).get("header")
        if isinstance(header, dict):
            code = str(header.get("resultCode", ""))
            if code and code not in ("00", "0000"):
                return f'{code} {header.get("resultMsg", "")}'.strip()
        return TravelSource._body_error(payload)


__all__ = ["ARRIVALS", "BASE_URL", "DEPARTURES", "IncheonAirportFlights"]
