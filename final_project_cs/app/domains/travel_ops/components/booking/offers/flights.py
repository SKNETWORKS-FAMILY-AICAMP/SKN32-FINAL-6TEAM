# -*- coding: utf-8 -*-
"""booking · offers — 항공편 비교. 여러 판매처 어댑터를 부르고, 같은 편끼리 묶고, 다른 곳 검색 링크를 붙인다. `[2026-10-10]`

팀 피드백(2026-10-10): 에이전트 → booking 모듈 → 항공 · 숙소(차후 철도 · 활동 · 식당) 어댑터 → 결과. 위치 · 경로는 이동 모듈이 맡는다.
이 모듈은 전에 항공 팀(`instances/flight/team.py`) 안에 있던 「어느 소스를 부르고 어떻게 합치나」를 옮긴 것이다 — 동작은 그대로다.

- 어댑터(`ports/data_sources/`): 마이리얼트립 MCP(`travel_search`) · Ignav MCP(`flight_offers`) · SerpApi 구글 항공권(`flight_google`).
  없는 소스는 건너뛰고 「조회 실패」와 같게 센다(키가 없는 환경).
- 호출 규칙:
  - 왕복은 Ignav 를 부르지 않는다(사용자 결정 2026-10-10) — ☆13:41 · 13:45 playdata ICN→NRT 왕복: Ignav 가 41.9~42.3초(전체의 90% 넘게)
    걸렸고, 준 링크가 둘 다 가는 편만 예약하는 주소였다(`TripType=OneWay`). 묶음도 가는 편 · 오는 편 항공사가 달랐다.
  - 마이리얼트립이 429 뒤 쉬는 중이면 어댑터가 `cooldown_seconds` 표시만 준다 — 결과가 아니니 `resting` 으로 센다.
  - 구글 항공권 왕복은 편 목록 대신 왕복 최저가 참고(`round_trip_lowest`)와 결과 페이지만 온다 — `reference` 로 센다.
- 결제 · 예약은 하지 않는다. 판매처 링크만 준다. 가격은 조회 시점 참고값이다(어느 소스도 정확성을 보장하지 않는다).
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

#: 소스 이름 → 답에 적는 이름(판매처가 따로 없는 소스)
SOURCE_LABEL = {"myrealtrip": "마이리얼트립", "google": "구글 항공권"}
#: 소스 이름 → `TravelSources` 의 칸
SLOTS = {"myrealtrip": "travel_search", "ignav": "flight_offers", "google": "flight_google"}

#: 공항 → 도시 코드(IATA 도시 코드). 트립닷컴 검색창은 도시(`dcity`) + 공항(`dairport`)을 따로 받아야 채워진다 —
#: ☆2026-10-10 사용자 확인: `dcity=icn&acity=nrt` 는 결과만 맞고 검색창이 비었고, `dcity=sel&acity=tyo&dairport=icn&aairport=nrt` 는 다 채워졌다.
#: 표에 없는 공항은 공항 코드를 도시 코드로 쓴다(공항 하나뿐인 도시는 대개 같다). ICN · NRT 말고는 확인 안 함
CITY = {"ICN": "SEL", "GMP": "SEL", "NRT": "TYO", "HND": "TYO", "KIX": "OSA", "ITM": "OSA", "UKB": "OSA",
        "CTS": "SPK", "TSA": "TPE", "TPE": "TPE", "PEK": "BJS", "PKX": "BJS", "PVG": "SHA", "SHA": "SHA",
        "DMK": "BKK", "BKK": "BKK", "JFK": "NYC", "LGA": "NYC", "EWR": "NYC", "CDG": "PAR", "ORY": "PAR",
        "LHR": "LON", "LGW": "LON", "FCO": "ROM", "SGN": "SGN", "HAN": "HAN"}


def _key(flight: dict[str, Any]) -> tuple[Any, ...] | None:
    """같은 편인지 가르는 열쇠 — 항공사 코드 · 첫 다리 출발 공항 · 날짜 · 시각 · 마지막 다리 도착 공항. 하나라도 없으면 묶지 않는다."""
    legs = flight.get("legs") or []
    if not legs:
        return None
    first, last = legs[0], legs[-1]
    key = (str(flight.get("airline_code") or "").upper(), first.get("origin"), first.get("departDate"),
           first.get("departTime"), last.get("destination"), len(legs))
    return key if all(key[:5]) else None


def _offer(flight: dict[str, Any], source: str) -> dict[str, Any]:
    if source in SOURCE_LABEL:
        label = SOURCE_LABEL[source]
    else:
        kind = {"seller_airline": "항공사 공식", "seller_ota": "여행사"}.get(str(flight.get("link_kind") or ""), "판매처")
        label = f"{flight.get('seller') or '판매처'}({kind})"
    return {"source": source, "label": label, "price_total": flight.get("price_total"),
            "currency": flight.get("currency") or "", "seats": flight.get("seats"),
            "link": flight.get("link") or "", "link_kind": flight.get("link_kind") or ""}


def merge(by_source: list[tuple[str, list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    """소스들의 편을 같은 편끼리 묶는다. 가격은 바꾸지 않고 판매처별로 나란히 둔다.

    ★순서: 편마다 가장 낮은 가격(원화만 비교) → 가격 모름은 뒤. 소스가 준 값만 쓴다.
    ★편명은 마이리얼트립 국제선에 없어서(2026-10-07 응답) 다른 소스의 편명을 빌려 적는다 — 같은 편으로 묶였을 때만.
    """
    options: list[dict[str, Any]] = []
    index: dict[tuple[Any, ...], dict[str, Any]] = {}
    for source, flights in by_source:
        for flight in flights:
            if not isinstance(flight, dict) or not flight.get("legs"):
                continue
            key = _key(flight)
            option = index.get(key) if key is not None else None
            if option is None:
                option = {"airline": flight.get("airline") or flight.get("airline_code") or "",
                          "legs": [dict(leg) for leg in flight["legs"]], "offers": [],
                          "minutes": flight.get("duration_minutes")}
                options.append(option)
                if key is not None:
                    index[key] = option
            else:
                for mine, theirs in zip(option["legs"], flight["legs"]):
                    if not mine.get("flightNumber") and theirs.get("flightNumber"):
                        mine["flightNumber"] = theirs["flightNumber"]
                if option["minutes"] is None:
                    option["minutes"] = flight.get("duration_minutes")
            # ★같은 소스 · 같은 판매처 · 같은 가격이면 한 줄 — ☆2026-10-10 13:41 왕복에서 Ignav 가 에어부산 340,015원을
            #   gclid 만 다른 링크로 두 번 줬다(링크로만 거르면 두 줄이 된다)
            new = _offer(flight, source)
            if not any(offer["source"] == source and (offer["link"] == new["link"]
                       or (offer["label"], offer["price_total"]) == (new["label"], new["price_total"]))
                       for offer in option["offers"]):
                option["offers"].append(new)
    for option in options:
        won = [offer["price_total"] for offer in option["offers"]
               if isinstance(offer["price_total"], (int, float)) and offer["currency"] in ("", "KRW")]
        option["best"] = min(won) if won else None
        option["offers"].sort(key=lambda offer: (not isinstance(offer["price_total"], (int, float)), offer["price_total"] or 0))
    options.sort(key=lambda option: (option["best"] is None, option["best"] or 0))
    return options


def elsewhere(*, origin: str, destination: str, depart_date: date, return_date: date | None, domestic: bool | None,
              cabin: str | None, adults: int | None, children: int | None, infants: int | None) -> list[dict[str, str]]:
    """같은 조건의 **검색 결과 페이지** 주소 — 한국 사용자가 익숙한 곳. 가격은 받지 않는다(그 사이트 화면을 긁지 않는다). `[2026-10-09]`

    ★주소 형식은 각 사이트 화면의 주소를 보고 만든 것이다. 2026-10-09~10 사용자가 ICN→NRT 10-20 편도 · 10-20~23 왕복 1명으로 열어 봤다 —
      셋 다 조건이 채워진 결과 화면(트립닷컴은 도시 + 공항 코드로 바꾼 뒤). 국내선 · 다른 공항은 확인 안 함.
    """
    go, back = depart_date, return_date
    adults, children, infants = adults or 1, children or 0, infants or 0
    o, d = origin, destination
    naver_path = f"{o}-{d}-{go:%Y%m%d}" + (f"/{d}-{o}-{back:%Y%m%d}" if back else "")
    naver = (f"https://flight.naver.com/flights/{'domestic' if domestic else 'international'}/{naver_path}"
             f"?adult={adults}&child={children}&infant={infants}&fareType={'YC' if domestic else 'Y'}")
    seat = {"BUSINESS": "business", "FIRST": "first"}.get(cabin or "", "economy")
    sky = (f"https://www.skyscanner.co.kr/transport/flights/{o.lower()}/{d.lower()}/{go:%y%m%d}/"
           + (f"{back:%y%m%d}/" if back else "") + f"?adultsv2={adults}&cabinclass={seat}&rtn={1 if back else 0}")
    trip = (f"https://kr.trip.com/flights/showfarefirst?dcity={CITY.get(o, o).lower()}&acity={CITY.get(d, d).lower()}"
            f"&dairport={o.lower()}&aairport={d.lower()}&ddate={go.isoformat()}"
            + (f"&rdate={back.isoformat()}&flighttype=rt" if back else "&flighttype=ow")
            + f"&class={'c' if seat == 'business' else 'f' if seat == 'first' else 'y'}&quantity={adults}"
            "&searchboxarg=t&locale=ko-KR&curr=KRW")
    return [{"name": "네이버 항공권", "url": naver}, {"name": "스카이스캐너", "url": sky}, {"name": "트립닷컴", "url": trip}]


def _status(got: dict[str, Any] | None, *, absent: bool) -> dict[str, Any]:
    if absent or got is None:
        return {"status": "failed"}
    if got.get("cooldown_seconds"):
        return {"status": "resting", "cooldown_seconds": got["cooldown_seconds"]}
    flights = got.get("flights") or []
    if not flights and got.get("note"):
        return {"status": "reference", "note": got["note"], "round_trip_lowest": got.get("round_trip_lowest"),
                "page": got.get("page") or ""}
    return {"status": "ok", "count": len(flights)}


def search_flights(travel: Any, *, origin: str, destination: str, depart_date: str, return_date: str | None = None,
                   domestic: bool | None = None, direct_only: bool | None = None, cabin: str | None = None,
                   max_results: int = 100, adults: int | None = None, children: int | None = None,
                   infants: int | None = None) -> dict[str, Any]:
    """항공편 비교 한 번. 소스를 차례로 부르고(마이리얼트립 → Ignav → 구글 항공권) 결과를 묶어 돌려준다.

    돌려주는 것: `options`(같은 편끼리 묶은 편, 편마다 판매처별 `offers` · `best`), `sources`(소스별 `status` — ok · failed · resting ·
    skipped · reference), `elsewhere`(다른 곳 검색 링크), `confirmed_at`. 소스가 하나도 결과를 못 주면 `options` 가 비고 상태로 알 수 있다.
    """
    query = {"origin": origin, "destination": destination, "depart_date": depart_date, "return_date": return_date,
             "domestic": domestic, "direct_only": direct_only, "cabin": cabin, "max_results": max_results,
             "adults": adults, "children": children, "infants": infants}
    arguments = {key: value for key, value in query.items() if value is not None}
    raw: dict[str, dict[str, Any] | None] = {}
    sources: dict[str, dict[str, Any]] = {}
    for name, slot in SLOTS.items():
        adapter = getattr(travel, slot, None) if travel is not None else None
        if name == "ignav" and return_date:
            sources[name] = {"status": "skipped", "reason": "round_trip"}
            raw[name] = None
            continue
        got = adapter.flight_search(**arguments) if adapter is not None else None
        sources[name] = _status(got, absent=adapter is None)
        raw[name] = got if sources[name]["status"] == "ok" else None
    options = merge([(name, (raw[name] or {}).get("flights") or []) for name in SLOTS])
    links = elsewhere(origin=origin, destination=destination, depart_date=date.fromisoformat(depart_date),
                      return_date=date.fromisoformat(return_date) if return_date else None, domestic=domestic,
                      cabin=cabin, adults=adults, children=children, infants=infants)
    return {"query": query, "options": options, "sources": sources, "elsewhere": links,
            "confirmed_at": datetime.now(UTC).isoformat(), "source": "booking"}


__all__ = ["CITY", "SLOTS", "SOURCE_LABEL", "elsewhere", "merge", "search_flights"]
