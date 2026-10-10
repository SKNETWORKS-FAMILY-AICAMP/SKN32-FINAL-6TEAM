# -*- coding: utf-8 -*-
"""SerpApi Google Hotels — 구글 호텔을 **한국 설정**(gl=kr · hl=ko · KRW)으로 검색한다. `[2026-10-10]`

- 주소 `https://serpapi.com/search.json`, `engine=google_hotels`. 키는 항공과 같은 `serpapi_api_key`(주소의 `api_key`) —
  ★그래서 응답 캐시에 넣지 않는다. 검색 1번 = 1회(무료 월 250회, 항공과 함께 쓴다).
- 2026-10-10 14:21 playdata 실호출(`scripts/probe_serpapi_hotels.py 서울 명동 2026-11-06 2026-11-09 --adults 2`): 2.32초, 20곳.
  곳마다 `name` · `type`(hotel · vacation rental) · `rate_per_night.extracted_lowest` · `total_rate.extracted_lowest` ·
  `overall_rating`(5점) · `reviews` · `extracted_hotel_class` · `gps_coordinates` · `link`(호텔 공식 사이트 또는 판매처) 가 왔다.
  앞의 셋은 숙박 공유(vacation rental, Bluepillow · Vio)였다. 결과 페이지 `search_metadata.google_hotels_url` 은 검색어만 담고 날짜가 없다.
- 숙소 이름 하나로 찾으면(「롯데호텔 서울」) 「결과 없음」 오류가 왔다(14:22) — 이름 찾기(내 숙소)에는 쓰지 않는다.
- 가격에 세금이 들었는지는 **확인 안 함**. 단위는 받은 그대로(원).
- 폴백 금지(`base.py` ①~④): 못 가져오면 `None` 이고 이유를 센다.
"""
from __future__ import annotations

from typing import Any, Callable

import httpx

from .base import TravelSource

URL = "https://serpapi.com/search.json"
SOURCE = "serpapi_hotels"
#: 검색 한 번 2.32초(2026-10-10 playdata). 넉넉히 20초. 우리가 고른 값
TIMEOUT_SECONDS = 20.0


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class SerpApiHotels(TravelSource):
    name = SOURCE

    def __init__(self, *, api_key: str, transport: Callable[..., httpx.Response] | None = None, **kwargs: Any) -> None:
        kwargs.pop("cache", None)                    # 캐시 열쇠에 키가 실리므로 받지 않는다
        super().__init__(timeout=TIMEOUT_SECONDS, transport=transport, **kwargs)
        self._key = api_key

    def stay_search(self, *, keyword: str, check_in: str, check_out: str, adults: int | None = None,
                    children: int | None = None, size: int = 20, max_price: int | None = None,
                    **_: Any) -> dict[str, Any] | None:
        """마이리얼트립 `stay_search` 와 같은 이름의 인자. 돌려주는 곳 모양은 우리 쪽에서 정한 것(아래 `stays`)."""
        keyword = str(keyword or "").strip()
        if not keyword or not check_in or not check_out:
            self._miss("missing_input", f"{keyword!r} {check_in}~{check_out}")
            return None
        params: dict[str, Any] = {"engine": "google_hotels", "q": keyword, "check_in_date": check_in,
                                  "check_out_date": check_out, "currency": "KRW", "hl": "ko", "gl": "kr",
                                  "api_key": self._key}
        if adults is not None:
            params["adults"] = int(adults)
        if children:
            params["children"] = int(children)
        if max_price:
            params["max_price"] = int(max_price)
        data = self._fetch_json(URL, params)
        if data is None:
            return None
        rows = data.get("properties")
        if not isinstance(rows, list):
            self._miss("unexpected_shape", f"{sorted(data)[:8]}")
            return None
        stays = []
        for row in rows[:max(1, int(size))]:
            if not isinstance(row, dict) or not row.get("name"):
                continue
            gps = row.get("gps_coordinates") or {}
            stays.append({
                "name": str(row["name"]), "type": str(row.get("type") or ""),
                "price_per_night": _number((row.get("rate_per_night") or {}).get("extracted_lowest")),
                "total_price": _number((row.get("total_rate") or {}).get("extracted_lowest")),
                "rating": _number(row.get("overall_rating")), "review_count": row.get("reviews"),
                "hotel_class": row.get("extracted_hotel_class"),
                "latitude": _number(gps.get("latitude")), "longitude": _number(gps.get("longitude")),
                "link": str(row.get("link") or "")})
        page = str((data.get("search_metadata") or {}).get("google_hotels_url") or "")
        return self.stamp({"stays": stays, "page": page, "keyword": keyword, "check_in": check_in,
                           "check_out": check_out}, source=SOURCE)

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        error = payload.get("error")
        return str(error)[:200] if error else None


__all__ = ["SOURCE", "SerpApiHotels", "URL"]
