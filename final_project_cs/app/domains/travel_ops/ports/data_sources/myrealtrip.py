# -*- coding: utf-8 -*-
"""마이리얼트립 MCP — 숙소·항공 **검색 전용** 어댑터. `[2026-10-07]`

- 주소 `https://mcp-servers.myrealtrip.com/mcp` · 키 없음 · JSON-RPC(`tools/call`). 2026-10-07 16:46 부터 기기 playdata 에서 실호출로 확인했다
  (`scripts/probe_myrealtrip_mcp.py`). 쓰는 도구는 넷: `searchStays` · `getStayDetail` · `searchInternationalFlights` · `searchDomesticFlights`.
- 예약·결제·로그인은 하지 않는다. 고객에게는 **링크만** 준다 — 숙소는 `shareWebLink`, 항공은 `searchUrl`.
  ★항공 `reservationUrl` 은 쓰지 않는다 — 열면 「가격 변동」 뒤 다시 검색으로 간다(2026-10-07 사용자 확인).
- 서버가 연결 때 주는 안내문(AI 클라이언트용 지시 12,873자)은 **읽지 않고 쓰지 않는다** — 우리 팀의 행동은 우리 프롬프트가 정한다.
- 가격·잔여는 금방 바뀐다 — 응답을 캐시에 담지 않는다.
- 폴백 금지(`base.py` ①~④): 못 가져오면 `None` 이고 이유를 센다. 받은 값의 단위를 바꾸지 않는다 —
  숙소 평점은 **5점 만점**, 목록 가격은 **1박**, 상세 `total_price` 는 **숙박 전체(세금 포함)** 다.
- 국내선은 응답 모양이 다르다(2026-10-07 17:31 playdata 실호출): 구간이 `legs` 가 아니라 `outbound` 에 오고, `searchUrl` 이 없고
  `reservationUrl` 만 온다. 그 주소는 열면 「마감」 팝업이 떠서(2026-10-08 확인), 고른 편 값만 뺀 **노선 검색 주소**를 주고
  `link_kind="route_search"` 로 표시한다. 응답에 9.49초가 걸려
  이 소스의 시간 상한을 `TIMEOUT_SECONDS` 로 따로 둔다.
- `[확인 안 함]` 국내선 왕복의 돌아오는 구간 이름(`inbound` 로 보고 읽는다) · 국내선 도구의 승객 수 입력(국제선과 같다고 보고 보낸다) ·
  국내선 `reservationUrl` 이 열리는지 · 객실 `ratePlan` 16개 항목의 뜻(객실은 이름 · 무료 취소 여부 · 총액만 읽는다).
"""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Callable

import httpx

from .base import TravelSource

URL = "https://mcp-servers.myrealtrip.com/mcp"
PROTOCOL = "2025-03-26"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
#: 한 번에 받는 숙소 수의 서버 상한(도구 설명: size 최대 100)
MAX_STAYS = 100
#: 상세에서 싣는 객실 수 — 답변에 다 싣지 못한다. 우리가 고른 값
MAX_ROOMS = 5
SOURCE = "myrealtrip"
#: 이 소스의 호출 상한(초). 국내선 검색 한 번에 9.49초(2026-10-07 17:31), 국내선 왕복은 약 15초(2026-10-08 15:18 — 팀 전체 19.1초 중 해석 3.7초)가
#: 걸렸다(playdata). 20초로는 여유가 없어 30초로 둔다 — 팀 전체 상한(`reliability.team_timeout_seconds` 90)보다는 작다. 우리가 고른 값
TIMEOUT_SECONDS = 30.0
#: 429 를 받았는데 기다릴 시간을 못 읽었을 때 쉬는 시간(초). 우리가 고른 값
DEFAULT_RETRY_AFTER_SECONDS = 60.0

_DIGITS = re.compile(r"\d[\d,]*")


def _won(text: Any) -> int | None:
    """「188,597원/박」 「세금포함 207,456원/박」 → 188597. 숫자가 없으면 `None`."""
    found = _DIGITS.search(str(text or ""))
    return int(found.group().replace(",", "")) if found else None


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class MyRealTripMcp(TravelSource):
    name = SOURCE

    def __init__(self, *, url: str = URL,
                 post: Callable[[str, dict[str, Any], dict[str, str]], httpx.Response] | None = None,
                 **kwargs: Any) -> None:
        kwargs.pop("cache", None)                     # ★가격·잔여 — 담아 두지 않는다
        kwargs.setdefault("timeout", TIMEOUT_SECONDS)
        super().__init__(**kwargs)
        self._url = url
        # ★시험이 네트워크 없이 돌게 여는 주입 지점. 기본값은 실제 호출이다
        self._post = post or (lambda target, message, headers: httpx.post(
            target, json=message, headers=headers, timeout=self._timeout))
        self._lock = threading.Lock()
        self._ready, self._session_id, self._next_id = False, None, 0
        # ★제공처가 429 로 「잠시 멈춰라」 한 시각까지는 바깥으로 나가지 않는다(2026-10-08 14:35 playdata, retryAfter 60).
        #   그 사이 부르면 같은 거절만 늘고 제공처에 부하를 보탠다.
        self._clock = time.monotonic
        self._blocked_until = 0.0

    # ── JSON-RPC ────────────────────────────────────────────────
    def _send(self, method: str, params: dict[str, Any] | None, *, notify: bool = False) -> dict[str, Any] | None:
        """메시지 하나. 응답 봉투(`{"result"|"error"}`)를 돌려주고, 못 받으면 세고 `None`."""
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notify:
            with self._lock:
                self._next_id += 1
                message["id"] = self._next_id
        headers = dict(HEADERS)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        try:
            response = self._post(self._url, message, headers)
        except httpx.TimeoutException as exc:
            self._miss("timeout", f"{method}: {exc}")
            return None
        except httpx.HTTPError as exc:
            self._miss("transport_error", f"{method}: {type(exc).__name__}: {exc}")
            return None
        if response.headers.get("mcp-session-id"):
            self._session_id = response.headers["mcp-session-id"]
        if notify:
            return {}
        if response.status_code == 429:
            self._blocked_until = self._clock() + _retry_after(response)
        if response.status_code != 200:
            self._miss(f"http_{response.status_code}", response.text[:200])
            return None
        for item in _messages(response):
            if isinstance(item, dict) and item.get("id") == message["id"]:
                return item
        self._miss("not_json", response.text[:200])
        return None

    def _handshake(self) -> bool:
        if self._ready:
            return True
        reply = self._send("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                          "clientInfo": {"name": "tripilot", "version": "0.1"}})
        if reply is None:
            return False
        if "result" not in reply:
            self._miss("body_error", f"initialize: {str(reply.get('error'))[:160]}")
            return False
        self._send("notifications/initialized", None, notify=True)
        self._ready = True
        return True

    def _call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        """도구 하나를 부르고 본문(JSON 객체)을 돌려준다. 실패 갈래는 전부 세고 `None`."""
        wait = self._blocked_until - self._clock()
        if wait > 0:
            self._miss("rate_limited_by_provider", f"{wait:.0f}s remaining")
            self.last_wait_seconds = wait
            return None
        if not self._allow() or not self._handshake():
            return None
        reply = self._send("tools/call", {"name": tool, "arguments": arguments})
        if reply is None:
            return None
        if "result" not in reply:
            self._miss("body_error", f"{tool}: {str(reply.get('error'))[:160]}")
            return None
        result = reply["result"] if isinstance(reply["result"], dict) else {}
        content = result.get("content") if isinstance(result.get("content"), list) else []
        text = "\n".join(str(part.get("text", "")) for part in content
                         if isinstance(part, dict) and part.get("type") == "text")
        if result.get("isError"):
            self._miss("body_error", f"{tool}: {text[:160]}")
            return None
        data = result.get("structuredContent")
        if data is None:
            try:
                data = json.loads(text)
            except ValueError:
                self._miss("not_json", f"{tool}: {text[:160]}")
                return None
        if not isinstance(data, dict):
            self._miss("unexpected_shape", f"{tool}: {type(data).__name__}")
            return None
        if data.get("success") is False:
            self._miss("body_error", f"{tool}: success=false {str(data.get('message') or data.get('error') or '')[:120]}")
            return None
        return data

    # ── 숙소 ────────────────────────────────────────────────────
    def stay_search(self, *, keyword: str, check_in: str, check_out: str, adults: int = 2, children: int = 0,
                    domestic: bool = True, size: int = 20, min_price: int | None = None, max_price: int | None = None,
                    min_review_rating: float | None = None) -> dict[str, Any] | None:
        """키워드(지역 · 숙소 이름, 한국어 가능)로 숙소 목록. 좌표 · 링크는 여기 없다 — `stay_detail` 이 준다.

        돌려주는 것: `{"stays": [...], "total": 전체 수, "has_next": bool, confirmed_at, source}`. 0건은 `stays=[]`(아는 사실).
        """
        if not keyword or not keyword.strip():
            self._miss("no_keyword")
            return None
        arguments: dict[str, Any] = {"keyword": keyword.strip(), "checkIn": check_in, "checkOut": check_out,
                                     "adultCount": int(adults), "childCount": int(children),
                                     "isDomestic": bool(domestic), "size": max(1, min(int(size), MAX_STAYS))}
        for name, value in (("minPrice", min_price), ("maxPrice", max_price), ("minReviewRating", min_review_rating)):
            if value is not None:
                arguments[name] = value
        data = self._call("searchStays", arguments)
        if data is None:
            return None
        rows = data.get("stays")
        if not isinstance(rows, list):
            self._miss("unexpected_shape", f"searchStays: {sorted(data)[:8]}")
            return None
        stays = []
        for row in rows:
            if not isinstance(row, dict) or row.get("gid") is None:
                continue
            reviews = _won(row.get("reviewCount"))
            stays.append({"gid": row["gid"], "name": str(row.get("name") or ""),
                          "description": str(row.get("description") or ""),
                          "price_per_night": _won(row.get("price")),
                          "price_per_night_with_tax": _won(row.get("additionalPrice")),
                          "rating": _number(row.get("rating")),      # 5점 만점
                          "review_count": reviews,
                          "tags": [str(tag) for tag in row.get("tags") or []],
                          "thumbnail_url": str(row.get("thumbnailUrl") or "")})
        page = data.get("pagination") if isinstance(data.get("pagination"), dict) else {}
        return self.stamp({"stays": stays, "total": page.get("totalCount"), "has_next": page.get("hasNextPage")},
                          source=SOURCE)

    def stay_detail(self, *, gid: int, check_in: str, check_out: str, adults: int = 2,
                    children: int = 0) -> dict[str, Any] | None:
        """숙소 한 곳 — 좌표 · 주소 · 예약 페이지 링크 · 그 날짜의 가격. 좌표가 없으면 그 칸은 `None`(지어내지 않는다)."""
        data = self._call("getStayDetail", {"gid": int(gid), "checkIn": check_in, "checkOut": check_out,
                                            "adultCount": int(adults), "childCount": int(children)})
        if data is None:
            return None
        prop, pricing, location = (data.get(key) if isinstance(data.get(key), dict) else {}
                                   for key in ("property", "pricing", "location"))
        if not prop:
            self._miss("unexpected_shape", f"getStayDetail: {sorted(data)[:8]}")
            return None
        region = prop.get("region") if isinstance(prop.get("region"), dict) else {}
        rooms = []
        for room in (data.get("rooms") or [])[:MAX_ROOMS]:
            if not isinstance(room, dict):
                continue
            plan = room.get("ratePlan") if isinstance(room.get("ratePlan"), dict) else {}
            rooms.append({"name": str(room.get("roomName") or ""), "free_cancellation": room.get("isFreeCancellation"),
                          "total_price": plan.get("totalPrice")})
        return self.stamp({
            "gid": prop.get("gid", gid), "name": str(prop.get("name") or ""),
            "grade": str(prop.get("grade") or ""), "category": str(prop.get("category") or ""),
            "city": str(region.get("city") or ""), "country": str(region.get("country") or ""),
            "rating": _number(prop.get("reviewScore")),             # 5점 만점
            "review_count": prop.get("reviewCount"),
            "latitude": _number(location.get("latitude")), "longitude": _number(location.get("longitude")),
            "address": str(location.get("address") or ""),
            "link": str(prop.get("shareWebLink") or ""),
            "sold_out": pricing.get("isSoldOut"), "no_rooms": data.get("noRoomsAvailable"),
            "price_per_night": pricing.get("averagePrice"),         # 1박 평균
            "total_price": pricing.get("totalPrice"),               # 숙박 전체 · 세금 포함
            "room_count": data.get("roomCount"), "rooms": rooms,
            "check_in": check_in, "check_out": check_out}, source=SOURCE)

    # ── 항공 ────────────────────────────────────────────────────
    def flight_search(self, *, origin: str, destination: str, depart_date: str, return_date: str | None = None,
                      domestic: bool = False, direct_only: bool | None = None, cabin: str | None = None,
                      max_results: int = 5, adults: int | None = None, children: int | None = None,
                      infants: int | None = None) -> dict[str, Any] | None:
        """공항 코드(3글자) 둘과 날짜로 항공편. `domestic=True` 면 국내선 도구를 부른다. 승객 수를 안 주면 서버 기본(성인 1명)."""
        origin, destination = str(origin or "").strip().upper(), str(destination or "").strip().upper()
        if len(origin) != 3 or len(destination) != 3:
            self._miss("no_airport_code", f"{origin!r}->{destination!r}")
            return None
        arguments: dict[str, Any] = {"tripType": "ROUND_TRIP" if return_date else "ONE_WAY", "origin": origin,
                                     "destination": destination, "departDate": depart_date,
                                     "maxResults": max(1, int(max_results))}
        if return_date:
            arguments["returnDate"] = return_date
        if cabin:
            arguments["cabinClass"] = str(cabin).upper()
        passengers = {name: int(value) for name, value in (("adults", adults), ("children", children), ("infants", infants))
                      if value is not None}
        if passengers:
            arguments["passengers"] = passengers
        if direct_only is not None and not domestic:
            arguments["directFlightOnly"] = bool(direct_only)       # 국내선 도구에는 이 입력이 없다
        data = self._call("searchDomesticFlights" if domestic else "searchInternationalFlights", arguments)
        if data is None:
            return None
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        rows = result.get("items")
        if not isinstance(rows, list):
            self._miss("unexpected_shape", f"flights: {sorted(data)[:8]}")
            return None
        flights = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            airline, info, price = (row.get(key) if isinstance(row.get(key), dict) else {}
                                    for key in ("airline", "travelInfo", "price"))
            legs = []
            for leg in row.get("legs") or []:
                if isinstance(leg, dict):
                    legs.append({key: leg.get(key) for key in (
                        "origin", "destination", "departDate", "departTime", "arriveDate", "arriveTime",
                        "durationMinutes", "stops", "isDirect")})
            for side in ("outbound", "inbound"):                      # 국내선 모양
                leg = row.get(side)
                if isinstance(leg, dict):
                    legs.append({"origin": leg.get("departCity"), "destination": leg.get("arriveCity"),
                                 "flightNumber": leg.get("flightNumber"),
                                 **{key: leg.get(key) for key in ("departDate", "departTime", "arriveDate", "arriveTime",
                                                                  "durationMinutes")}})
            # ★국제선은 `searchUrl` 만 쓴다(`reservationUrl` 은 열면 「가격 변동」 뒤 다시 검색). 국내선은 `searchUrl` 이 오지 않아 `reservationUrl` 을 싣고 표시한다
            link, kind = str(row.get("searchUrl") or ""), "search"
            if not link and domestic and row.get("reservationUrl"):
                # ★국내선 `reservationUrl` 은 고른 편(`flightinfo`)까지 담고 있어, 열면 「가는편 여정이 마감되었습니다」가 뜬다.
                #   그 값만 뺀 주소는 같은 노선 · 날짜 · 인원의 **검색 결과 목록**이 팝업 없이 열린다(2026-10-08 15:40 playdata 사용자 확인).
                link, kind = _without_selected_flight(str(row["reservationUrl"])), "route_search"
            flights.append({"airline_code": str(airline.get("code") or ""), "airline": str(airline.get("name") or ""),
                            "duration_minutes": info.get("totalDurationMinutes", legs[0].get("durationMinutes") if len(legs) == 1 else None),
                            "stops": info.get("stops"),
                            "direct": info.get("isDirect"), "legs": legs,
                            "price_total": price.get("total"), "currency": str(price.get("currency") or ""),
                            "seats": row.get("seatCount"),
                            "link": link, "link_kind": kind if link else ""})
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        return self.stamp({"flights": flights, "total": summary.get("totalCandidates", summary.get("totalOutbound")),
                           "cheapest_total": summary.get("cheapestTotal"), "origin": origin, "destination": destination,
                           "depart_date": depart_date, "return_date": return_date, "domestic": bool(domestic)},
                          source=SOURCE)


def _without_selected_flight(url: str) -> str:
    """국내선 예약 주소에서 고른 편(`flightinfo`)만 뺀다. 나머지 값과 순서는 그대로 둔다."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "flightinfo"]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def _retry_after(response: httpx.Response) -> float:
    """429 응답이 말하는 기다릴 시간(초). 본문 `retryAfter` → 헤더 `Retry-After` → 기본값 순서로 읽는다."""
    try:
        body = response.json()
        value = body.get("retryAfter") if isinstance(body, dict) else None
    except ValueError:
        value = None
    for candidate in (value, response.headers.get("retry-after")):
        try:
            seconds = float(candidate)
        except (TypeError, ValueError):
            continue
        if seconds > 0:
            return seconds
    return DEFAULT_RETRY_AFTER_SECONDS


def _messages(response: httpx.Response) -> list[Any]:
    """JSON 또는 SSE(`text/event-stream`) 본문에서 JSON-RPC 메시지들을 꺼낸다."""
    if "text/event-stream" in response.headers.get("content-type", ""):
        found = []
        for line in response.text.splitlines():
            if line.startswith("data:"):
                try:
                    found.append(json.loads(line[5:].strip()))
                except ValueError:
                    pass
        return found
    try:
        body = response.json()
    except ValueError:
        return []
    return body if isinstance(body, list) else [body]


__all__ = ["MyRealTripMcp", "SOURCE", "URL"]
