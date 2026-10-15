# -*- coding: utf-8 -*-
"""booking · offers — 열차 · 고속버스 · 시외버스 운행 비교. `[2026-10-14]` 예약 모듈 확장(항공 → 기차 · 버스).

에이전트(예약 모듈 `instances/booking/`) → 이 모듈 → TAGO 어댑터(`ports/data_sources/tago_transit.py`) → 결과. 항공 비교(`flights.py`)와 같은 자리.

- 고객이 말한 곳 이름(「서울」 「부산」 「동대구」 「광주」)을 **역 · 터미널**로 옮긴다 — 열차는 역 사전(`STATIONS`: 이름 → 역 이름 · 시 · 도)으로
  시 · 도의 역 목록에서 찾고, 버스는 공급자 터미널 목록을 이름 조각으로 찾는다. 「서울」처럼 터미널이 여럿이면(서울경부 · 서울호남 · 동서울)
  행선지 권역의 기본 터미널부터 묻고 운행이 있으면 멈춘다(`_prefer`, 10-15) — 어느 터미널인지는 결과 줄과 `terminals` 에 적는다.
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
from zoneinfo import ZoneInfo

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

#: `[2026-10-15 검수 · GPT 검토 #7]` 버스만 다니는 곳 · 터미널 이름 → 시 · 도. 역 사전(`STATIONS`)에 없어 「속초」 「동서울」을 못 읽었다.
#: 이름은 공급자 터미널 목록에서 조각으로 찾는다(`_terminals`) — 여기 값은 권역(`_prefer`)에만 쓴다. 우리가 고른 표(자주 가는 곳 위주).
BUS_PLACES: dict[str, str] = {
    "동서울": "서울", "서울경부": "서울", "센트럴시티": "서울", "서울호남": "서울", "서울남부": "서울", "상봉": "서울",
    "속초": "강원", "양양": "강원", "고성": "강원", "삼척": "강원", "태백": "강원", "정선": "강원", "영월": "강원", "홍천": "강원",
    "인제": "강원", "횡성": "강원", "철원": "강원", "화천": "강원", "양구": "강원", "주문진": "강원",
    "세종": "세종", "유성": "대전", "대전복합": "대전", "보령": "충남", "대천": "충남", "서산": "충남", "당진": "충남", "태안": "충남",
    "홍성": "충남", "예산": "충남", "단양": "충북", "보은": "충북", "옥천": "충북", "영동": "충북",
    "군산": "전북", "김제": "전북", "부안": "전북", "고창": "전북", "완도": "전남", "해남": "전남", "강진": "전남", "진도": "전남",
    "통영": "경남", "거제": "경남", "남해": "경남", "사천": "경남", "하동": "경남", "거창": "경남", "합천": "경남", "김해": "경남",
    "양산": "경남", "영덕": "경북", "울진": "경북", "문경": "경북", "상주": "경북", "영천": "경북",
    "인천": "인천", "성남": "경기", "용인": "경기", "이천": "경기", "여주": "경기", "안성": "경기", "의정부": "경기", "동탄": "경기",
    "부천": "경기", "고양": "경기", "일산": "경기", "파주": "경기",
}

#: 버스 터미널 조각 — 고객 말 → 공급자 터미널 이름에서 찾을 조각. 없으면 말한 이름 그대로 찾는다
TERMINAL_HINT: dict[str, str] = {"서울역": "서울", "부산역": "부산", "동대구": "대구", "광주송정": "광주", "창원중앙": "창원", "여수엑스포": "여수"}

#: 「서울」 같은 이름에 터미널이 여럿일 때 물어볼 최대 수(출발 × 도착 조합이 호출 수)
TERMINALS_EACH = 3

#: `[2026-10-15 고도화]` 터미널이 여럿인 출발지(서울)는 **행선지 권역으로 기본 터미널을 먼저** 묻고, 운행이 있으면 거기서 멈춘다(호출 10 → 3).
#: 권역은 역 사전(`STATIONS`)의 시 · 도 — 사전에 없는 곳은 기본 순서. 고객이 터미널 이름을 말하면(「동서울에서」) 이 규칙은 안 탄다(그 터미널만 찾힌다).
#: 순서는 우리가 정한 값(한국 고속 · 시외 노선망 상식) — 틀린 권역이면 다음 터미널로 넘어가므로 답이 비는 일은 없고 호출만 는다.
_HONAM = {"광주", "전남", "전북"}
_GANGWON = {"강원"}
_SOUTH_SUBURBS = {"충남", "경남", "전북", "전남", "광주"}            # 시외: 서울남부터미널이 맡는 쪽(충남 서해안 · 경남 서부 · 호남)
_TERMINAL_ORDER: dict[str, dict[str, tuple[str, ...]]] = {
    "express": {"honam": ("서울호남", "센트럴", "동서울", "서울경부"), "gangwon": ("동서울", "서울경부", "서울호남"),
                "default": ("서울경부", "동서울", "서울호남", "센트럴")},
    "suburbs": {"south": ("서울남부", "동서울", "서울경부"), "default": ("동서울", "서울남부", "서울경부")},
}


def _region(said: str) -> str | None:
    entry = STATIONS.get(said) or STATIONS.get(said.replace("역", ""))
    return entry[1] if entry else BUS_PLACES.get(said)


def _prefer(kind: str, terminals: list[dict[str, Any]], destination: str) -> list[dict[str, Any]]:
    """출발 터미널 후보를 행선지 권역의 기본 터미널 순으로 — 이름에 순서표의 조각이 든 것을 앞으로, 나머지는 원래 순서."""
    if len(terminals) < 2:
        return terminals
    region = _region(destination)
    table = _TERMINAL_ORDER[kind]
    if kind == "express":
        order = table["honam"] if region in _HONAM else table["gangwon"] if region in _GANGWON else table["default"]
    else:
        order = table["south"] if region in _SOUTH_SUBURBS else table["default"]
    rank = {t["name"]: next((i for i, piece in enumerate(order) if piece in t["name"]), len(order)) for t in terminals}
    return sorted(terminals, key=lambda t: rank[t["name"]])
#: 버스 종류(고속 · 시외)마다 운행 조회를 부를 최대 수 — `[10-15]` 전체 8 에서 종류별 4 로: 고속이 전부 0편이면(서울→광주 10-16 실호출)
#: 예산을 다 써 시외는 묻지도 못했다. 기본 터미널 순서(`_prefer`)라 앞 조합이 가장 그럴듯하다.
MAX_SCHEDULE_CALLS = 4

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
    return exact + starts + rest                           # 자르기는 부르는 쪽이(`_prefer` 뒤에 `TERMINALS_EACH`) — 동서울이 잘리지 않게(10-15)


#: 버스 운행은 공급자(TAGO)가 가까운 날만 준다 — 10-14 저녁 관찰: 10-16 까지 있고 10-17 부터 0편(팀장 점검 LB-03). 이 날 수 밖인데 0편이면
#: 「운행 없음」이 아니라 「아직 안 줌」일 수 있어, 오늘 같은 구간에 운행이 있는지 한 번 더 물어 가른다(호출 1회).
BUS_WINDOW_DAYS = 1


def _beyond_window(depart_date: str) -> bool:
    try:
        wanted = datetime.strptime(depart_date, "%Y-%m-%d").date()
    except ValueError:
        return False
    return (wanted - datetime.now(ZoneInfo("Asia/Seoul")).date()).days > BUS_WINDOW_DAYS


def _runs_today(adapter: Any, kinds: list[str], pair: tuple[str, dict[str, Any], dict[str, Any]] | None, calls: list[str]) -> bool | None:
    """같은 터미널 쌍을 오늘 날짜로 한 번 — 오늘은 있는데 그날은 없으면 공급자가 아직 안 준 것이다. 못 불렀으면 None(모름)."""
    if pair is None:
        return None
    bus_kind, dep, arr = pair
    today = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    calls.append(f"bus_schedules:{bus_kind}:{dep['name']}→{arr['name']}:today")
    rows = adapter.bus_schedules(bus_kind, dep_id=dep["id"], arr_id=arr["id"], date=today)
    return None if rows is None else bool(rows)


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
        first_pair: tuple[str, dict[str, Any], dict[str, Any]] | None = None
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
            deps, arrs = _prefer(bus_kind, deps, destination)[:TERMINALS_EACH], arrs[:TERMINALS_EACH]
            first_pair = first_pair or (bus_kind, deps[0], arrs[0])
            if len(deps) > 1:
                result["terminals"] = {"origin": [t["name"] for t in deps], "rule": _region(destination) or "default"}
            got_any = False
            for dep in deps:
                for arr in arrs:
                    if len([c for c in calls if c.startswith(f"bus_schedules:{bus_kind}:")]) >= MAX_SCHEDULE_CALLS:
                        break
                    calls.append(f"bus_schedules:{bus_kind}:{dep['name']}→{arr['name']}")
                    rows = adapter.bus_schedules(bus_kind, dep_id=dep["id"], arr_id=arr["id"], date=depart_date)
                    if rows is None:
                        status = "failed" if not options else status
                        continue
                    got_any = got_any or bool(rows)
                    options.extend(rows)
                if got_any:
                    break                                  # 기본 터미널에 운행이 있으면 다른 출발 터미널은 안 묻는다(`[10-15]` 호출 아끼기)
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
        elif _beyond_window(depart_date):
            # 공급자가 그 날짜를 아직 안 준다(팀장 점검 LB-03) — 「운행 없음」과 가른다. `[2026-10-15 검수 · GPT 검토 #10]` 오늘 첫 쌍이 비거나
            #   못 불렀어도 먼 날짜의 0편은 「운행 없음」의 근거가 아니다(다른 쌍엔 있을 수 있다) → 오늘 있으면 not_yet, 아니면 unconfirmed(모름)
            today = _runs_today(adapter, kinds, first_pair, calls)
            status, unresolved = ("not_yet" if today else "unconfirmed"), []
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


__all__ = ["BOOKING_SITES", "BUS_PLACES", "STATIONS", "TERMINALS_EACH", "search_transit"]
