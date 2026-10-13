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
- `[2026-10-13]` **숙소 상세**(`stay_detail`, 목록의 `property_token` 으로 1번 더) — 판매처별 1박 가격 · 주소 · 전화.
  ☆10-13 10:26 playdata 명동 3박 2명(`scripts/probe_google_hotel_prices.py --detail`): 목록 20곳 중 판매처 가격(`prices`)이 온 곳은
  숙박 공유 3곳뿐이었고, 호텔스카이파크 센트럴명동점 상세(7.2초)에는 판매처 11곳(아고다 · 트립닷컴 · 클룩 · 트립비토즈 · 부킹닷컴 ·
  공식 사이트 등)과 주소 · 전화가 왔다. 판매처 링크는 모두 `google.com` 을 거친다 — 판매처 화면으로 이어지는지는 **확인 안 함**.
  상세 1번 = SerpApi 1회(무료 월 250회).
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


def _image(row: dict[str, Any]) -> str | None:
    """대표 사진 — `images[0]` 의 작은 그림(없으면 원본). 없으면 `None`."""
    images = row.get("images") if isinstance(row.get("images"), list) else []
    first = images[0] if images and isinstance(images[0], dict) else {}
    return str(first.get("thumbnail") or first.get("original_image") or "") or None


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
                "link": str(row.get("link") or ""),
                # `[2026-10-13]` 상세를 부를 열쇠 · 대표 사진(작은 그림 주소)
                "property_token": str(row.get("property_token") or "") or None,
                "image": _image(row)})
        page = str((data.get("search_metadata") or {}).get("google_hotels_url") or "")
        return self.stamp({"stays": stays, "page": page, "keyword": keyword, "check_in": check_in,
                           "check_out": check_out}, source=SOURCE)

    def stay_detail(self, *, property_token: str, keyword: str, check_in: str, check_out: str,
                    adults: int | None = None, children: int | None = None) -> dict[str, Any] | None:
        """숙소 하나의 상세 — 판매처별 1박 가격 · 주소 · 전화 · 사진. `[2026-10-13]` 판매처는 `featured_prices` · `prices` 를 합치고
        이름이 같은 것은 한 번만. 못 가져오면 `None`."""
        if not property_token or not keyword or not check_in or not check_out:
            self._miss("missing_input", f"{property_token!r} {keyword!r}")
            return None
        params: dict[str, Any] = {"engine": "google_hotels", "q": str(keyword).strip(), "property_token": property_token,
                                  "check_in_date": check_in, "check_out_date": check_out, "currency": "KRW", "hl": "ko",
                                  "gl": "kr", "api_key": self._key}
        if adults is not None:
            params["adults"] = int(adults)
        if children:
            params["children"] = int(children)
        data = self._fetch_json(URL, params)
        if data is None:
            return None
        sellers, seen = [], set()
        for group in ("featured_prices", "prices"):
            for row in data.get(group) or []:
                if not isinstance(row, dict) or not row.get("source") or str(row["source"]) in seen:
                    continue
                seen.add(str(row["source"]))
                sellers.append({"seller": str(row["source"]),
                                "price_per_night": _number((row.get("rate_per_night") or {}).get("extracted_lowest")),
                                "link": str(row.get("link") or ""), "official": row.get("official") is True})
        return self.stamp({"property_token": property_token, "name": str(data.get("name") or ""),
                           "address": str(data.get("address") or ""), "phone": str(data.get("phone") or ""),
                           "image": _image(data), "sellers": sellers}, source=SOURCE)

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        error = payload.get("error")
        return str(error)[:200] if error else None


__all__ = ["SOURCE", "SerpApiHotels", "URL"]
