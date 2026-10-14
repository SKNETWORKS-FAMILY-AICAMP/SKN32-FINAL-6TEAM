# -*- coding: utf-8 -*-
"""booking · offers — 열차 · 고속버스 · 시외버스 운행 비교. `[2026-10-14]` 예약 모듈 확장(항공 → 기차 · 버스).

에이전트(예약 모듈 `instances/booking/`) → 이 모듈 → TAGO 어댑터(`ports/data_sources/tago_transit.py`) → 결과. 항공 비교(`flights.py`)와 같은 자리.

- 고객이 말한 곳 이름(「서울」 「부산」 「동대구」 「광주」)을 **역 · 터미널**로 옮긴다 — 열차는 역 사전(`STATIONS`: 이름 → 역 이름 · 시 · 도)으로
  시 · 도의 역 목록에서 찾고, 버스는 공급자 터미널 목록을 이름 조각으로 찾는다. 「서울」처럼 터미널이 여럿이면(서울경부 · 서울호남 · 동서울)
  앞의 몇 곳(`TERMINALS_EACH`)을 다 물어 합친다 — 어느 터미널인지는 결과 줄에 그대로 적는다.
- 버스는 고속을 먼저 보고, 고객이 「시외」라고 했거나 고속에 결과가 없을 때 시외를 본다(호출 수를 아끼려고 — 하루 한도 `rate_tago_per_day`).
- 돌려주는 모양은 항공과 같은 골격 — `options`(운행 하나씩, 출발 시각순) · `sources`(`tago` 의 status · count · seconds · 부른 횟수) ·
  `resolved`(출발 · 도착으로 쓴 역 · 터미널 이름) · `elsewhere`(예매 사이트 첫 화면 링크) · `confirmed_at`. 운행마다 `links` — 조건을 채워
  여는 예매 주소(SRT · 트립닷컴 · 버스타고, `transit_links.py`) — 가 붙고, 없으면 빈 목록이다.
- 예매 · 결제는 하지 않는다. 요금은 공급자의 어른 1인 값 그대로(조회 시점 참고값).
"""
from __future__ import annotations

from datetime import UTC, datetime
import time
from typing import Any

from app.domains.travel_ops.components.booking.offers.transit_links import run_links

#: 고객이 말하는 이름 → (열차 역 이름, 시 · 도). 역 목록에서 「역 이름으로 시작」하는 것을 고른다(「울산(통도사)」 · 「김천(구미)」).
#: 도시 이름은 그 도시의 고속철 역으로 — 대구 → 동대구 · 광주 → 광주송정 · 창원 → 창원중앙 · 여수 → 여수엑스포 · 청주 → 오송(우리가 고른 값).
STATIONS: dict[str, tuple[str, str]] = {
    "서울": ("서울", "서울"), "서울역": ("서울", "서울"), "용산": ("용산", "서울"), "수서": ("수서", "서울"), "청량리": ("청량리", "서울"),
    "영등포": ("영등포", "서울"), "행신": ("행신", "경기"), "광명": ("광명", "경기"), "수원": ("수원", "경기"), "평택": ("평택", "경기"),
    "천안아산": ("천안아산", "충남"), "천안": ("천안", "충남"), "아산": ("천안아산", "충남"), "오송": ("오송", "충북"), "청주": ("오송", "충북"),
    "대전": ("대전", "대전"), "서대전": ("서대전", "대전"), "김천구미": ("김천(구미)", "경북"), "김천": ("김천", "경북"), "구미": ("구미", "경북"),
    "동대구": ("동대구", "대구"), "대구": ("동대구", "대구"), "경산": ("경산", "경북"), "경주": ("경주", "경북"), "신경주": ("경주", "경북"),
    "포항": ("포항", "경북"), "안동": ("안동", "경북"), "영주": ("영주", "경북"), "울산": ("울산(통도사)", "울산"), "통도사": ("울산(통도사)", "울산"),
    "부산": ("부산", "부산"), "부산역": ("부산", "부산"), "구포": ("구포", "부산"), "밀양": ("밀양", "경남"), "마산": ("마산", "경남"),
    "창원": ("창원중앙", "경남"), "창원중앙": ("창원중앙", "경남"), "진주": ("진주", "경남"), "익산": ("익산", "전북"), "전주": ("전주", "전북"),
    "정읍": ("정읍", "전북"), "남원": ("남원", "전북"), "광주송정": ("광주송정", "광주"), "광주": ("광주송정", "광주"), "나주": ("나주", "전남"),
    "목포": ("목포", "전남"), "순천": ("순천", "전남"), "여수": ("여수엑스포", "전남"), "여수엑스포": ("여수엑스포", "전남"),
    "강릉": ("강릉", "강원"), "춘천": ("춘천", "강원"), "원주": ("원주", "강원"), "만종": ("만종", "강원"), "평창": ("평창", "강원"),
    "진부": ("진부(오대산)", "강원"), "동해": ("동해", "강원"), "제천": ("제천", "충북"), "충주": ("충주", "충북"), "논산": ("논산", "충남"),
    "공주": ("공주", "충남"), "인천공항": ("인천공항T1", "인천"), "검암": ("검암", "인천"),
}

#: 버스 터미널 조각 — 고객 말 → 공급자 터미널 이름에서 찾을 조각. 없으면 말한 이름 그대로 찾는다
TERMINAL_HINT: dict[str, str] = {"서울역": "서울", "부산역": "부산", "동대구": "대구", "광주송정": "광주", "창원중앙": "창원", "여수엑스포": "여수"}

#: 「서울」 같은 이름에 터미널이 여럿일 때 물어볼 최대 수(출발 × 도착 조합이 호출 수)
TERMINALS_EACH = 3
#: 한 검색에서 운행 조회를 부를 최대 수(열차 1 + 버스 고속 ≤ 6 + 시외 ≤ 6 보다 작게)
MAX_SCHEDULE_CALLS = 8

#: 예매 사이트 **첫 화면** — 조건을 채워 여는 주소는 `transit_links`(SRT · 트립닷컴 · 버스타고)에 있고, 여기는 그것이 없을 때의 대비.
#: `[2026-10-14 저녁]` 코레일은 `letskorail.com` 이 `korail.com` 으로 넘어가고(302), 버스타고 루트는 404 라 주소를 바꿨다(직접 열어 봄).
BOOKING_SITES = {
    "train": [{"name": "코레일 승차권 예매(KTX · ITX · 무궁화)", "url": "https://www.korail.com/ticket/main"},
              {"name": "SRT 예매", "url": "https://etk.srail.kr/"}],
    "express": [{"name": "코버스 고속버스 예매", "url": "https://www.kobus.co.kr/"}],
    "suburbs": [{"name": "버스타고 시외버스 예매", "url": "https://www.bustago.or.kr/newweb/kr/index.do"},
                {"name": "티머니 시외버스 예매", "url": "https://txbus.t-money.co.kr/"}],
}


FAILED = object()      # 어댑터가 못 불렀다(장애 · 한도) — 「이름을 못 찾음」과 가른다(검토 10-14)


def _station(adapter: Any, said: str, calls: list[str]) -> dict[str, Any] | None | object:
    """말한 이름 → 역 {id, name}. 사전에 없거나 목록에 없으면 `None`, 어댑터가 못 불렀으면 `FAILED`."""
    entry = STATIONS.get(said) or STATIONS.get(said.replace("역", "")) or STATIONS.get(said + "역")
    if entry is None:
        return None
    wanted, city = entry
    calls.append(f"train_stations:{city}")
    stations = adapter.train_stations(city)
    if stations is None:
        return FAILED
    exact = [s for s in stations if s["name"] == wanted]
    starts = [s for s in stations if s["name"].startswith(wanted)]
    holds = [s for s in stations if wanted in s["name"]]
    for group in (exact, starts, holds):
        if group:
            return group[0]
    return None


def _terminals(adapter: Any, kind: str, said: str, calls: list[str]) -> list[dict[str, Any]] | object:
    keyword = TERMINAL_HINT.get(said, said)
    calls.append(f"bus_terminals:{kind}:{keyword}")
    found = adapter.bus_terminals(kind, keyword)
    if found is None:
        return FAILED
    exact = [t for t in found if t["name"] == keyword]
    starts = [t for t in found if t["name"].startswith(keyword) and t not in exact]
    rest = [t for t in found if t not in exact and t not in starts]
    return (exact + starts + rest)[:TERMINALS_EACH]


def _sort_key(option: dict[str, Any]) -> tuple[str, str]:
    return (option.get("date") or "", option.get("depart") or "99:99")


def search_transit(travel: Any, *, mode: str, origin: str, destination: str, depart_date: str,
                   adults: int | None = None, kind: str | None = None) -> dict[str, Any]:
    """열차(`mode="train"`) 또는 버스(`mode="bus"`) 운행 비교 한 번(편도 한 날). 오는 편은 부르는 쪽이 날짜 · 방향을 바꿔 한 번 더 부른다.

    `kind` 는 버스일 때 고객이 말한 종류(express · suburbs) — 없으면 고속 먼저, 없으면 시외.
    """
    adapter = getattr(travel, "transit_schedule", None) if travel is not None else None
    started = time.perf_counter()
    calls: list[str] = []
    result: dict[str, Any] = {
        "mode": mode, "query": {"origin": origin, "destination": destination, "depart_date": depart_date, "adults": adults, "kind": kind},
        "options": [], "resolved": {"origin": None, "destination": None}, "sources": {}, "elsewhere": [],
        "confirmed_at": datetime.now(UTC).isoformat()}
    if adapter is None:
        result["sources"]["tago"] = {"status": "failed", "reason": "transit_schedule 소스 없음(ACOP_TAGO_API_KEY)"}
        return result
    options: list[dict[str, Any]] = []
    status = "ok"
    unresolved: list[str] = []
    if mode == "train":
        dep, arr = _station(adapter, origin, calls), _station(adapter, destination, calls)
        if dep is FAILED or arr is FAILED:
            status = "failed"
        elif dep is None or arr is None:
            unresolved = [name for name, found in ((origin, dep), (destination, arr)) if found is None]
            status = "unresolved"
        else:
            result["resolved"] = {"origin": dep["name"], "destination": arr["name"]}
            calls.append("train_schedules")
            rows = adapter.train_schedules(dep_id=dep["id"], arr_id=arr["id"], date=depart_date)
            if rows is None:
                status = "failed"
            else:
                options = rows
        result["elsewhere"] = list(BOOKING_SITES["train"])
    else:
        kinds = [kind] if kind in ("express", "suburbs") else ["express", "suburbs"]
        used: list[str] = []
        broken = paired = False
        for bus_kind in kinds:
            deps, arrs = _terminals(adapter, bus_kind, origin, calls), _terminals(adapter, bus_kind, destination, calls)
            if deps is FAILED or arrs is FAILED:
                broken = True
                continue
            if not deps or not arrs:
                if not unresolved:
                    unresolved = [name for name, found in ((origin, deps), (destination, arrs)) if not found]
                continue
            paired = True
            got_any = False
            for dep in deps:
                for arr in arrs:
                    if len([c for c in calls if c.startswith("bus_schedules")]) >= MAX_SCHEDULE_CALLS:
                        break
                    calls.append(f"bus_schedules:{bus_kind}:{dep['name']}→{arr['name']}")
                    rows = adapter.bus_schedules(bus_kind, dep_id=dep["id"], arr_id=arr["id"], date=depart_date)
                    if rows is None:
                        status = "failed" if not options else status
                        continue
                    got_any = got_any or bool(rows)
                    options.extend(rows)
            if got_any:
                used.append(bus_kind)
                unresolved = []
                if kind is None:
                    break                                  # 고속에 있으면 시외는 안 본다(호출 아끼기)
        if options:
            status = "ok"
            names_dep = sorted({option["origin"] for option in options if option.get("origin")})
            names_arr = sorted({option["destination"] for option in options if option.get("destination")})
            result["resolved"] = {"origin": " · ".join(names_dep) or None, "destination": " · ".join(names_arr) or None}
        elif broken or status == "failed":
            status = "failed"
        elif unresolved and not paired:
            status = "unresolved"                        # 터미널을 한 쌍도 못 찾았을 때만 「못 찾음」
        else:
            status, unresolved = "ok", []                 # 터미널은 찾았는데 그날 운행이 없다
        result["elsewhere"] = [site for bus_kind in (used or kinds) for site in BOOKING_SITES[bus_kind]]
    options.sort(key=_sort_key)
    for option in options:                                 # 운행마다 조건을 채워 여는 예매 링크(없으면 빈 목록 → 첫 화면 링크)
        option["links"] = run_links(option, adults=adults)
    result["options"] = options
    result["sources"]["tago"] = {"status": status, "count": len(options), "calls": calls,
                                 "seconds": round(time.perf_counter() - started, 1),
                                 **({"unresolved": unresolved} if unresolved else {})}
    return result


__all__ = ["BOOKING_SITES", "STATIONS", "TERMINALS_EACH", "search_transit"]
