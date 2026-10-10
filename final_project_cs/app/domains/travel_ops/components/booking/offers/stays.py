# -*- coding: utf-8 -*-
"""booking · offers — 숙소 비교. 마이리얼트립 목록과 구글 호텔 목록을 받고, 다른 곳 검색 링크를 붙인다. `[2026-10-10]`

전에 숙소 팀(`instances/lodging/team.py`) 안에 있던 「어느 소스를 부르나 · 다른 곳 링크」를 옮긴 것이다 — 동작은 그대로다.
어느 숙소를 보여 줄지(객실 없는 곳 건너뛰기 · 상세 확인 · 이미 보인 이름 빼기)는 추천이라 숙소 팀에 남긴다.

- 어댑터: 마이리얼트립 MCP(`travel_search.stay_search`) · SerpApi 구글 호텔(`stay_google.stay_search`). 없는 소스는 「조회 실패」로 센다.
- 두 소스의 숙소 이름이 달라(한국어 · 영어 · 지점 표기) 같은 숙소로 묶지 않는다 — 목록을 따로 돌려준다.
- 마이리얼트립이 429 뒤 쉬는 중이면 `resting` 으로 센다(어댑터가 `cooldown_seconds` 표시만 준다).
- 다른 곳 링크: `[2026-10-10 17시대 playdata 내장 브라우저 확인]` 검색어 · 날짜 · 인원이 주소로 채워지는 곳만 싣는다(조건 「명동」·「시부야」
  2026-11-06~09 성인 2).
    · 부킹닷컴 — 지역 · 날짜 · 인원 채워짐(앞선 사용자 확인).
    · 익스피디아 · 호텔스닷컴 — `destination` 글자를 지역으로 풀었다(시부야 → 도쿄 시부야 376곳, 명동 → 서울 명동 298곳), 날짜 · 인원 채워짐.
      어린이는 나이(`children=1_8`)로 받아 수만으로는 못 넣는다 — 어린이가 있으면 그 화면에서 넣으라고 적는다.
    · 여기어때(국내) — `keyword` · `checkIn` · `checkOut` · `personal`(총 인원) 채워짐. ☆「명동」만 넣으면 춘천 명동이 먼저 나왔고
      「서울 명동」은 서울 명동 43곳 — 검색어가 짧으면 다른 지역이 섞일 수 있다.
    · 야놀자(국내) — 검색어는 채워지나 날짜 · 인원은 주소로 안 들어갔다(오늘 1박 2명으로 열림) — 그렇다고 적는다.
    · 에어비앤비(해외) — 지역 · 날짜 · 인원 채워짐(시부야 3박 총액). 숙박 공유라 해외에만 싣는다(국내는 내국인 숙박 공유 제한이 있어서).
    · 싣지 않음: 아고다(글자 검색 주소가 첫 화면으로 감 — 지역 번호가 있어야 한다), 트립닷컴 숙소(`searchWord` 를 무시하고 서울 목록을
      보였다 — 「시부야」로도 서울), 네이버 호텔(첫 화면, 앞선 확인).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote


def elsewhere(*, keyword: str, check_in: str, check_out: str, adults: int | None, children: int | None,
              domestic: bool | None = None) -> list[dict[str, str]]:
    """같은 조건의 다른 곳 검색 링크. 국내면 여기어때 · 야놀자를, 해외면 호텔스닷컴 · 에어비앤비를 더한다. 모르면 공통만."""
    word, adults, children = quote(keyword or ""), adults or 1, children or 0
    kid_note = {"note": "어린이 인원은 그 화면에서 넣어 주세요"} if children else {}
    links = [
        {"name": "부킹닷컴", "url": f"https://www.booking.com/searchresults.ko.html?ss={word}&checkin={check_in}&checkout={check_out}"
                                 f"&group_adults={adults}&no_rooms=1&group_children={children}"},
        {"name": "익스피디아", "url": f"https://www.expedia.co.kr/Hotel-Search?destination={word}&startDate={check_in}&endDate={check_out}"
                                  f"&adults={adults}&rooms=1", **kid_note},
    ]
    if domestic is True:
        links += [
            {"name": "여기어때", "url": f"https://www.yeogi.com/domestic-accommodations?keyword={word}&checkIn={check_in}"
                                    f"&checkOut={check_out}&personal={adults + children}"},
            {"name": "야놀자", "url": f"https://www.yanolja.com/search/{word}", "note": "날짜 · 인원은 그 화면에서 다시 고르셔야 합니다"},
        ]
    elif domestic is False:
        links += [
            {"name": "호텔스닷컴", "url": f"https://kr.hotels.com/Hotel-Search?destination={word}&startDate={check_in}&endDate={check_out}"
                                      f"&adults={adults}&rooms=1", **kid_note},
            {"name": "에어비앤비(숙박 공유)", "url": f"https://www.airbnb.co.kr/s/{word}/homes?checkin={check_in}&checkout={check_out}"
                                             f"&adults={adults}" + (f"&children={children}" if children else "")},
        ]
    return links


def _status(got: dict[str, Any] | None, *, absent: bool) -> dict[str, Any]:
    if absent or got is None:
        return {"status": "failed"}
    if got.get("cooldown_seconds"):
        return {"status": "resting", "cooldown_seconds": got["cooldown_seconds"]}
    return {"status": "ok", "count": len(got.get("stays") or [])}


def search_stays(travel: Any, *, keyword: str, check_in: str, check_out: str, adults: int | None = None,
                 children: int | None = None, domestic: bool | None = None, size: int = 20,
                 max_price: int | None = None, min_review_rating: float | None = None) -> dict[str, Any]:
    """숙소 비교 한 번. 돌려주는 것: `myrealtrip`(목록 그대로, 못 받았으면 `None`) · `google`(목록 그대로 또는 `None`) ·
    `sources`(소스별 `status` — ok · failed · resting) · `elsewhere` · `confirmed_at`."""
    query = {"keyword": keyword, "check_in": check_in, "check_out": check_out, "adults": adults, "children": children,
             "domestic": domestic, "size": size, "max_price": max_price, "min_review_rating": min_review_rating}
    wanted = {"myrealtrip": ("travel_search", query),
              # 구글 호텔은 국내 여부 · 최소 평점을 받지 않는다
              "google": ("stay_google", {key: query[key] for key in ("keyword", "check_in", "check_out", "adults",
                                                                      "children", "size", "max_price")})}
    results: dict[str, Any] = {}
    sources: dict[str, dict[str, Any]] = {}
    for name, (slot, arguments) in wanted.items():
        adapter = getattr(travel, slot, None) if travel is not None else None
        got = adapter.stay_search(**{key: value for key, value in arguments.items() if value is not None}) \
            if adapter is not None else None
        sources[name] = _status(got, absent=adapter is None)
        results[name] = got if sources[name]["status"] == "ok" else None
    return {"query": query, **results, "sources": sources,
            "elsewhere": elsewhere(keyword=keyword, check_in=check_in, check_out=check_out, adults=adults, children=children,
                                   domestic=domestic),
            "confirmed_at": datetime.now(UTC).isoformat(), "source": "booking"}


__all__ = ["elsewhere", "search_stays"]
