# -*- coding: utf-8 -*-
"""한국천문연구원 특일 정보 — **공휴일 판정**.

실측(2026-09-10, 실 키로):

    GET https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo
        ?solYear=2026&solMonth=10&_type=json
    → HTTP 200 · 20261003 개천절 · 20261005 대체공휴일(개천절) · 20261009 한글날

★**왜 필요한가.** Dining·Activity 의 「그 날 여는가」에서 **정기휴무보다 공휴일
  휴무가 훨씬 흔하다.** 이걸 안 보고 영업 여부를 답하면 명절에 틀린다.
  그리고 그 틀린 답은 고객이 문 닫힌 가게 앞에 서게 만든다.

★★**이 소스는 「공휴일인가」만 답한다. 「그 장소가 쉬는가」는 답하지 않는다.**
  공휴일에 여는 식당도 많고, 공휴일에만 여는 곳도 있다. 둘을 같게 다루면
  근거 없는 확정이 된다 — 판정은 장소 정보와 함께 Team 이 한다.

★인증키 함정: 포털이 주는 **Encoding 키**를 그대로 `params=` 에 넘기면
  `%3D` 가 `%253D` 로 다시 인코딩돼 **HTTP 403 SERVICE_KEY_IS_NOT_REGISTERED_ERROR**
  가 난다. 문구가 「등록 안 된 키」라 원인을 숨긴다. `Settings.public_data_key()`
  가 `unquote()` 해서 넘기므로 이 어댑터는 받은 키를 그대로 쓴다.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .base import TravelSource

ENDPOINT = ("https://apis.data.go.kr/B090041/openapi/service/"
            "SpcdeInfoService/getRestDeInfo")


class HolidaySource(TravelSource):
    """월 단위로 받아 그 달의 공휴일 집합을 만든다."""

    name = "kasi_holiday"

    def __init__(self, *, service_key: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key
        # ★같은 달을 여러 번 묻는다(한 여행이 한 달 안에 몰린다). 캐시가 없으면
        #   예약마다 바깥으로 나가 개발계정 한도를 금방 먹는다.
        self._cache: dict[tuple[int, int], dict[str, str]] = {}

    def is_holiday(self, when: date) -> dict[str, Any] | None:
        """그 날짜가 공휴일인지. 모르면 `None`(모름) — **「아니다」가 아니다.**"""
        month = self._month(when.year, when.month)
        if month is None:
            return None
        key = when.strftime("%Y%m%d")
        name = month.get(key)
        return self.stamp({
            "date": when.isoformat(),
            "is_holiday": name is not None,
            "holiday_name": name,          # 공휴일이 아니면 None
            # ★이 소스가 답하지 않는 것을 밝혀 둔다.
            "answers_whether_the_place_is_closed": False,
        }, source=self.name)

    def _month(self, year: int, month: int) -> dict[str, str] | None:
        cached = self._cache.get((year, month))
        if cached is not None:
            return cached

        if not self._key:
            self._miss("no_service_key")
            return None

        payload = self._fetch_json(ENDPOINT, {
            "serviceKey": self._key, "solYear": str(year),
            "solMonth": f"{month:02d}", "_type": "json", "numOfRows": "50"})
        if payload is None:
            return None

        body = (payload.get("response") or {}).get("body")
        if not isinstance(body, dict):
            self._miss("unexpected_envelope", str(list(payload))[:120])
            return None

        # ★`totalCount == 0` 인 달이 정상으로 있다(공휴일 없는 달). 그때
        #   `items` 가 빈 문자열로 온다 — 실패가 아니라 **빈 결과**다.
        items = (body.get("items") or {})
        rows = items.get("item") if isinstance(items, dict) else None
        if rows is None:
            rows = []
        if isinstance(rows, dict):
            rows = [rows]

        found = {str(row.get("locdate")): str(row.get("dateName", "")).strip()
                 for row in rows if isinstance(row, dict) and row.get("locdate")}
        self._cache[(year, month)] = found
        return found

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        """포털의 정상 응답은 `resultCode == "00"` 이다. 그 밖은 전부 오류다."""
        header = (payload.get("response") or {}).get("header")
        if isinstance(header, dict):
            code = str(header.get("resultCode", ""))
            if code and code != "00":
                return f'{code} {header.get("resultMsg", "")}'.strip()
        return TravelSource._body_error(payload)


__all__ = ["ENDPOINT", "HolidaySource"]
