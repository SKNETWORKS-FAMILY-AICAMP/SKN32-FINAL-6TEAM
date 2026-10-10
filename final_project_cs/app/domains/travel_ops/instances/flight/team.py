# -*- coding: utf-8 -*-
"""Flight Team — 항공편을 찾아 준다. `[2026-10-08]` 숙소 팀(`instances/lodging/`)과 같은 모양이다.

흐름(`flight.assist`): 모델 **한 번**이 문장(+ 여행 일정 요약)을 고정된 구조로 옮긴다(도시 이름 → 공항 코드도 모델이) →
서버가 검증한다 → 빠진 값이 있으면 되묻고, 없으면 `read.flight_search` **한 번** → 받은 값으로 답을 쓴다.

- 모델은 해석만 한다. 항공편 · 시각 · 가격 · 링크는 전부 도구가 준 값이다. 순서는 제공처가 준 그대로다.
- 예약 · 결제는 하지 않는다. 국제선은 마이리얼트립 **검색 결과 페이지** 링크(`searchUrl`)를 준다. 국내선은 그 링크가 오지 않아
  노선 검색 주소를 끝에 한 번 준다.
- `[2026-10-09]` **비교**: 같은 조건으로 Ignav(`read.flight_offers`, 판매처 = 항공사 · OTA)도 부르고, 같은 편(항공사 코드 · 출발 공항 ·
  출발 날짜 · 시각 · 도착 공항)끼리 묶어 판매처별 가격과 링크를 나란히 보여 준다. 순서는 편마다 가장 낮은 가격순(같은 통화끼리만).
  한쪽이 못 주면 다른 쪽만으로 답하고 그렇다고 적는다. 가격은 조회 시점 참고값이다(두 소스 모두 정확성을 보장하지 않는다).
- `[2026-10-09]` **시간대**: 출발 시각으로 새벽 · 오전 · 오후 · 저녁(`interpret.TIME_BANDS`)을 나눈다. 고객이 시간대를 말했으면 그 시간대 편만
  가격순으로 보여 주고, 말하지 않았으면 **시간대마다 최저가 한 편씩** 보여 준다 — 가장 싼 편이 새벽인 경우가 많다는 사용자 지적.
  ★시간대가 비면 「그 시간대 편이 없다」가 아니라 「받은 결과에 없다」다 — 소스마다 가격순 상위 `FETCH` 개만 받는다.
- 되묻기는 숙소 팀과 같은 까닭으로 `waiting` 이 아니라 답(`completed`)으로 한다.
- `flight.status` 는 전과 같다 — 잠긴 예약을 조회만 한다.
"""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any
from zoneinfo import ZoneInfo

from app.core.contracts import Evidence, NextAction, TeamManifest, TeamResult, TeamTask

from app.domains.travel_ops.instances._shared._base import TravelTeamBase
from .interpret import TIME_BANDS, Interpretation, InterpretationInvalid, ask, ground, needs, parse

logger = logging.getLogger(__name__)

PROMPT_KEY = "flight.interpret"
SEOUL = ZoneInfo("Asia/Seoul")
#: 고객이 시간대를 말했을 때 그 시간대에서 보여 주는 편 수. 우리가 고른 값
SHOWN = 3
#: 소스마다 받는 수. 소스가 가격순으로 주므로 적게 받으면 비싼 시간대(오전)가 통째로 빠진다 —
#: ☆2026-10-09 12:35~36 playdata 김포→제주: 10 · 30개에는 오전 편 0, 100개에서 07:05 BX8025 가 잡혔다.
#: 마이리얼트립 100개는 0.2초(10개 2.4초), 느린 쪽은 Ignav(10개 15.9~25.2초)다. 국내선 상한 100 · 국제선 250(입력 정의).
#: Ignav 는 어댑터가 10개로 줄인다(`ignav.MAX_RESULTS`). 우리가 고른 값
FETCH = 100


def _won(value: Any, currency: str) -> str:
    if not isinstance(value, (int, float)):
        return "가격 모름"
    return f"{int(value):,}원" if currency in ("", "KRW") else f"{value:,} {currency}"


def _leg(leg: dict[str, Any]) -> str:
    minutes = leg.get("durationMinutes")
    took = f"{minutes // 60}시간 {minutes % 60}분" if isinstance(minutes, int) else "소요 모름"
    stops = leg.get("stops")
    # 국내선 응답에는 경유 칸이 없다(2026-10-07 17:31 playdata) — 모르면 적지 않는다
    route = "직항, " if leg.get("isDirect") or stops == 0 else (f"경유 {stops}회, " if isinstance(stops, int) else "")
    number = f" {leg['flightNumber']}" if leg.get("flightNumber") else ""
    return (f"{leg.get('departDate') or ''} {leg.get('origin') or '?'} {leg.get('departTime') or '?'} → "
            f"{leg.get('destination') or '?'} {leg.get('arriveTime') or '?'}{number} ({route}{took})")


def _key(flight: dict[str, Any]) -> tuple[Any, ...] | None:
    """같은 편인지 가르는 열쇠 — 항공사 코드 · 첫 다리 출발 공항 · 날짜 · 시각 · 마지막 다리 도착 공항. 하나라도 없으면 묶지 않는다."""
    legs = flight.get("legs") or []
    if not legs:
        return None
    first, last = legs[0], legs[-1]
    key = (str(flight.get("airline_code") or "").upper(), first.get("origin"), first.get("departDate"),
           first.get("departTime"), last.get("destination"), len(legs))
    return key if all(key[:5]) else None


#: 소스 이름 → 답에 적는 이름(판매처가 따로 없는 소스)
SOURCE_LABEL = {"myrealtrip": "마이리얼트립", "google": "구글 항공권"}


def _offer(flight: dict[str, Any], source: str) -> dict[str, Any]:
    if source in SOURCE_LABEL:
        label = SOURCE_LABEL[source]
    else:
        kind = {"seller_airline": "항공사 공식", "seller_ota": "여행사"}.get(str(flight.get("link_kind") or ""), "판매처")
        label = f"{flight.get('seller') or '판매처'}({kind})"
    return {"source": source, "label": label, "price_total": flight.get("price_total"),
            "currency": flight.get("currency") or "", "seats": flight.get("seats"),
            "link": flight.get("link") or "", "link_kind": flight.get("link_kind") or ""}


def _merge(mrt: list[dict[str, Any]], offers: list[dict[str, Any]],
           google: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """소스들의 편을 같은 편끼리 묶는다(`[2026-10-09]` 구글 항공권 추가 — 세 소스). 가격은 바꾸지 않고 판매처별로 나란히 둔다.

    ★순서: 편마다 가장 낮은 가격(원화만 비교) → 가격 모름은 뒤. 소스가 준 값만 쓴다.
    ★편명은 마이리얼트립 국제선에 없어서(2026-10-07 응답) Ignav 쪽 편명을 빌려 적는다 — 같은 편으로 묶였을 때만.
    """
    options: list[dict[str, Any]] = []
    index: dict[tuple[Any, ...], dict[str, Any]] = {}
    for source, flights in (("myrealtrip", mrt), ("ignav", offers), ("google", google or [])):
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


def _band(option: dict[str, Any]) -> str | None:
    """첫 다리 출발 시각(HH:MM, 출발 공항 현지)이 드는 시간대 이름. 시각을 모르면 None — 어느 시간대에도 넣지 않는다."""
    clock = str((option["legs"][0] if option["legs"] else {}).get("departTime") or "")
    if len(clock) != 5 or clock[2] != ":":
        return None
    return next((name for name, _, start, end in TIME_BANDS if start <= clock < end), None)


#: 시간대 이름 → 한국어
BAND_LABEL = {name: label for name, label, _, _ in TIME_BANDS}


#: 공항 → 도시 코드(IATA 도시 코드). 트립닷컴 검색창은 도시(`dcity`) + 공항(`dairport`)을 따로 받아야 채워진다 —
#: ☆2026-10-10 사용자 확인: `dcity=icn&acity=nrt` 는 결과만 맞고 검색창이 비었고, `dcity=sel&acity=tyo&dairport=icn&aairport=nrt` 는 다 채워졌다.
#: 표에 없는 공항은 공항 코드를 도시 코드로 쓴다(공항 하나뿐인 도시는 대개 같다). ICN · NRT 말고는 확인 안 함
CITY = {"ICN": "SEL", "GMP": "SEL", "NRT": "TYO", "HND": "TYO", "KIX": "OSA", "ITM": "OSA", "UKB": "OSA",
        "CTS": "SPK", "TSA": "TPE", "TPE": "TPE", "PEK": "BJS", "PKX": "BJS", "PVG": "SHA", "SHA": "SHA",
        "DMK": "BKK", "BKK": "BKK", "JFK": "NYC", "LGA": "NYC", "EWR": "NYC", "CDG": "PAR", "ORY": "PAR",
        "LHR": "LON", "LGW": "LON", "FCO": "ROM", "SGN": "SGN", "HAN": "HAN"}


def _elsewhere(found: Interpretation) -> list[tuple[str, str]]:
    """같은 조건의 **검색 결과 페이지** 주소 — 한국 사용자가 익숙한 곳. 가격은 받지 않는다(그 사이트 화면을 긁지 않는다). `[2026-10-09]`

    ★주소 형식은 각 사이트 화면의 주소를 보고 만든 것이다. 2026-10-09~10 사용자가 ICN→NRT 10-20 편도 1명으로 열어 봤다 —
      네이버 · 스카이스캐너는 조건이 다 채워진 결과 화면, 트립닷컴은 도시 + 공항 코드로 바꾼 뒤 채워졌다. 왕복 · 국내선 · 다른 공항은 확인 안 함.
    """
    go = found.depart_date
    back = found.return_date
    adults, children, infants = found.adults or 1, found.children or 0, found.infants or 0
    o, d = found.origin, found.destination
    naver_path = f"{o}-{d}-{go:%Y%m%d}" + (f"/{d}-{o}-{back:%Y%m%d}" if back else "")
    naver = (f"https://flight.naver.com/flights/{'domestic' if found.domestic else 'international'}/{naver_path}"
             f"?adult={adults}&child={children}&infant={infants}&fareType={'YC' if found.domestic else 'Y'}")
    cabin = {"BUSINESS": "business", "FIRST": "first"}.get(found.cabin or "", "economy")
    sky = (f"https://www.skyscanner.co.kr/transport/flights/{o.lower()}/{d.lower()}/{go:%y%m%d}/"
           + (f"{back:%y%m%d}/" if back else "") + f"?adultsv2={adults}&cabinclass={cabin}&rtn={1 if back else 0}")
    trip = (f"https://kr.trip.com/flights/showfarefirst?dcity={CITY.get(o, o).lower()}&acity={CITY.get(d, d).lower()}"
            f"&dairport={o.lower()}&aairport={d.lower()}&ddate={go.isoformat()}"
            + (f"&rdate={back.isoformat()}&flighttype=rt" if back else "&flighttype=ow")
            + f"&class={'c' if cabin == 'business' else 'f' if cabin == 'first' else 'y'}&quantity={adults}"
            "&searchboxarg=t&locale=ko-KR&curr=KRW")
    return [("네이버 항공권", naver), ("스카이스캐너", sky), ("트립닷컴", trip)]


def _carriers(option: dict[str, Any]) -> list[str]:
    """다리마다 운항 항공사 코드(편명 앞 두 글자, 없으면 `carrierCode`). 모르면 빈 글자."""
    found = []
    for leg in option["legs"]:
        number = str(leg.get("flightNumber") or "")
        found.append(number[:2].upper() if len(number) > 2 else str(leg.get("carrierCode") or "").upper())
    return found


def _minutes(option: dict[str, Any]) -> int | None:
    """편 전체 소요 분. 편에 값이 없으면 다리마다 값을 더한다. 하나라도 모르면 None."""
    if isinstance(option.get("minutes"), int):
        return option["minutes"]
    parts = [leg.get("durationMinutes") for leg in option["legs"]]
    return sum(parts) if parts and all(isinstance(part, int) for part in parts) else None


def _connecting(option: dict[str, Any]) -> bool:
    """경유가 **확실한** 편만 참. 경유 칸이 없으면(국내선 응답) 경유로 보지 않는다."""
    return any(isinstance(leg.get("stops"), int) and leg["stops"] > 0 for leg in option["legs"])


#: 직항이 있는 노선에서 경유 편이 가장 짧은 편의 몇 배를 넘으면 시간대 대표에서 빼나. 우리가 고른 값(2026-10-09 사용자와 정함)
SLOW_FACTOR = 2


def _drop_slow(options: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """직항이 하나라도 있으면, 경유이면서 가장 짧은 편의 `SLOW_FACTOR` 배를 넘게 걸리는 편을 뺀다. (남은 편, 뺀 수)

    ☆2026-10-09 12:39 · 14:46 playdata 인천→나리타 — 「새벽 최저가」가 세부퍼시픽 06:35 경유 1회 11시간 25분 732,000원이었다.
      직항 2시간대가 11만 원대부터 있는데 그 편을 시간대 대표로 내세웠다.
    """
    known = [minutes for option in options if (minutes := _minutes(option)) is not None]
    if not known or not any(not _connecting(option) and _minutes(option) is not None for option in options):
        return options, 0
    limit = min(known) * SLOW_FACTOR
    kept = [option for option in options
            if not (_connecting(option) and (minutes := _minutes(option)) is not None and minutes > limit)]
    return kept, len(options) - len(kept)


def _pick(options: list[dict[str, Any]], wanted: list[str] | None) -> tuple[list[tuple[dict[str, Any], str]], list[str]]:
    """답에 실을 편과 그 줄의 표시, 그리고 받은 결과에 편이 없던 시간대들.

    - 말한 시간대가 **하나**면: 그 시간대 편만 가격순 `SHOWN` 개. 표시는 시간대 이름.
    - **여럿**이면(「새벽은 싫어」 → 오전 · 오후 · 저녁): 그 시간대들 안에서 시간대마다 최저가 하나.
      ☆12:22 playdata — 여럿을 가격순 3개로 했더니 셋 다 저녁이었다. 고객은 시간대를 넓혔지 저녁을 고른 것이 아니다.
    - 없으면: 네 시간대마다 가격이 가장 낮은 편 하나, 시간대 순서(새벽 → 저녁). 표시는 「오전 최저가」.
    `options` 는 이미 가격순이다(`_merge`).
    """
    if wanted and len(wanted) == 1:
        picked = [(option, BAND_LABEL[band]) for option in options if (band := _band(option)) in wanted][:SHOWN]
        return picked, [name for name in wanted if not any(_band(option) == name for option in options)]
    picked, empty = [], []
    for name, label, _, _ in TIME_BANDS:
        if wanted and name not in wanted:
            continue
        first = next((option for option in options if _band(option) == name), None)
        if first is None:
            empty.append(name)
        else:
            picked.append((first, f"{label} 최저가"))
    return picked, empty


class FlightTeam(TravelTeamBase):
    manifest = TeamManifest(
        team_id="flight",
        display_name="Flight Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["flight.assist", "flight.status"],
        accepted_case_types=["flight"],
        # 정책 문서를 쓰지 않는다 — 선언하면 문서 0건으로 degraded 가 된다(`locked` 의 2026-09-22 주석과 같은 까닭)
        required_context=["case_state", "db_facts", "history"],
        allowed_tools=["read.booking", "read.itinerary", "read.flight_search", "read.flight_offers", "read.flight_google"],
        knowledge_scope=["flight"],
        max_steps=5,                                  # 일정 1 + 검색 3(마이리얼트립 · Ignav · 구글 항공권) + 여유 1
        active=True,
        implementation_revision="2026-10-09",
        default_capability="flight.assist",
    )

    async def execute(self, task: TeamTask) -> TeamResult:
        blocked = self._guard(task)
        if blocked is not None:
            return blocked
        seen: set[str] = set()
        if task.capability == "flight.status":
            return self._status(task, seen)

        trip, evidence = self._trip(task, seen)
        today = datetime.now(SEOUL).date()
        if self.llm is None:
            return self._escalate(task, "interpreter_missing", evidence)
        try:
            raw = await self.llm.complete(PROMPT_KEY, task.input_text,
                                          {"today": today.isoformat(), **({"trip": trip} if trip else {})},
                                          run_id=task.run_id)
            found, ungrounded = ground(parse(raw), task.input_text, has_trip=trip is not None)
        except InterpretationInvalid as exc:
            logger.warning("flight interpretation invalid case=%s %s", task.case_id, exc)
            return self._escalate(task, "interpretation_invalid", evidence, warnings=[str(exc)[:200]])
        except Exception as exc:                      # noqa: BLE001 — 모델 호출 실패의 종류를 남기고 사람에게 넘긴다
            logger.warning("flight interpretation failed case=%s %s", task.case_id, type(exc).__name__)
            return self._escalate(task, "interpretation_failed", evidence, warnings=[type(exc).__name__])

        evidence = [*evidence, Evidence(
            evidence_id=f"interpretation:{task.team_id}", source_type="customer_message", source_id=PROMPT_KEY,
            claim="고객 문장을 모델이 옮긴 구조", value={**found.model_dump(mode="json"), "ungrounded": ungrounded}, confidence=1.0,
            observed_at=datetime.now(SEOUL))]
        decision = {"task": found.task,
                    "interpretation": found.model_dump(mode="json", exclude={"question", "missing"}),
                    "ungrounded": ungrounded}

        if found.task == "status":
            return self._status(task, seen, evidence)
        if found.task == "unclear":
            return self._respond(task, evidence, {**decision, "needs": ["task"]},
                                 "항공편을 찾아 드리려면 출발지 · 도착지 · 출발 날짜 · 인원을 알려 주세요. "
                                 "이미 예약하신 항공권에 대한 문의라면 그렇게 말씀해 주세요.")
        missing = needs(found, today=today)
        if missing:
            return self._respond(task, evidence, {**decision, "needs": missing}, ask(found, missing))
        return self._search(task, found, seen, evidence, decision)

    def _status(self, task: TeamTask, seen: set[str], base: list[Evidence] | None = None) -> TeamResult:
        booking = self._read(task, "read.booking", {"case_id": str(task.case_id)}, seen)
        evidence = self._evidence(task, source_id="read.booking", claim="잠긴 예약", value=booking, base=base)
        if booking is None:
            return self._unknown(task, "예약 내역", evidence)
        return self._result(task, outcome="completed", confidence=1.0, evidence=evidence, next_action=NextAction.RESPOND,
                            answer="이 예약은 잠긴 예약으로 취급합니다. 일정 조정 대상이 아닙니다.",
                            decisions=[{"locked": True, "team": self.manifest.team_id}])

    def _search(self, task: TeamTask, found: Interpretation, seen: set[str], evidence: list[Evidence],
                decision: dict[str, Any]) -> TeamResult:
        when = found.depart_date.isoformat() + (f"~{found.return_date.isoformat()}" if found.return_date else "")
        arguments = {
            "origin": found.origin, "destination": found.destination, "depart_date": found.depart_date.isoformat(),
            "return_date": found.return_date.isoformat() if found.return_date else None, "domestic": found.domestic,
            "direct_only": found.direct_only, "cabin": found.cabin, "max_results": FETCH,
            "adults": found.adults, "children": found.children, "infants": found.infants}
        mrt = self._read(task, "read.flight_search", dict(arguments), seen)
        evidence = self._evidence(task, source_id="read.flight_search", claim="항공편 검색 결과(마이리얼트립)", value=mrt,
                                  base=evidence)
        # ★왕복은 Ignav 를 부르지 않는다(사용자 결정 2026-10-10) — ☆13:41 · 13:45 playdata ICN→NRT 왕복: Ignav 가 41.9~42.3초(전체의 90% 넘게)
        #   걸렸고, 준 링크가 둘 다 가는 편만 예약하는 주소였다(`TripType=OneWay`). 묶음도 가는 편 · 오는 편 항공사가 달랐다(BX·7C, ZG·7C)
        offers = None if found.return_date else self._read(task, "read.flight_offers", dict(arguments), seen)
        evidence = self._evidence(task, source_id="read.flight_offers", claim="항공편 검색 결과(Ignav · 판매처 링크)",
                                  value=offers, base=evidence)
        google = self._read(task, "read.flight_google", dict(arguments), seen)
        evidence = self._evidence(task, source_id="read.flight_google", claim="항공편 검색 결과(SerpApi 구글 항공권, 한국 설정)",
                                  value=google, base=evidence)
        if mrt is None and offers is None and google is None:
            return self._unknown(task, "항공편 검색 결과", evidence)
        route = f"{found.origin} → {found.destination}"
        options = _merge((mrt or {}).get("flights") or [], (offers or {}).get("flights") or [],
                         (google or {}).get("flights") or [])
        if not options:
            return self._respond(task, evidence, {**decision, "found": 0},
                                 f"{route} · {when} 조건으로 찾은 항공편이 없습니다. 날짜나 공항을 바꿔 다시 말씀해 주세요.")
        party = f"성인 {found.adults}명" + (f" · 아동 {found.children}명" if found.children else "") \
            + (f" · 유아 {found.infants}명" if found.infants else "")
        wanted = list(found.depart_times or [])
        pool, slow = _drop_slow(options)
        picked, empty = _pick(pool, wanted)
        fallback = bool(wanted) and not picked
        if fallback:
            # 말한 시간대 편이 받은 결과에 하나도 없다 — 빈 답 대신 다른 시간대 최저가를 보여 주고 그렇다고 적는다
            picked, _ = _pick(pool, None)
        shown_options = [option for option, _ in picked]
        cheapest = pool[0] if pool and pool[0]["best"] is not None else None
        minutes = [option["minutes"] for option in shown_options if isinstance(option["minutes"], int)]
        # ★소요 시간이 다 같으면 「가장 짧음」을 붙이지 않는다 — ☆12:09 김포→제주, 셋 다 75분인데 셋 다 붙었다
        fastest = min(minutes) if minutes and len(set(minutes)) > 1 else None
        lines = []
        for number, (option, mark) in enumerate(picked, start=1):
            legs = " / ".join(_leg(leg) for leg in option["legs"]) or "구간 정보 없음"
            tags = [mark]
            if option is cheapest:
                tags.append("전체 최저가")
            if fastest is not None and option["minutes"] == fastest:
                tags.append("가장 짧음")
            lines.append(f"{number}. [{' · '.join(tags)}] {option['airline'] or '항공사 모름'} — {legs}")
            codes = [code for code in _carriers(option) if code]
            if len(option["legs"]) > 1 and len(codes) == len(option["legs"]) and len(set(codes)) > 1:
                # ☆13:41 왕복 — 에어부산 BX164 / 제주항공 7C1104 묶음이었는데 에어부산 링크는 `TripType=OneWay` 가는 편만이었다
                lines.append(f"   ※ 가는 편과 오는 편 항공사가 달라({' · '.join(dict.fromkeys(codes))}) 따로 예약해야 할 수 있습니다. "
                             "판매처 화면에서 두 편이 함께 잡히는지 확인해 주세요.")
            for offer in option["offers"]:
                seats = f" · 남은 좌석 {offer['seats']}" if isinstance(offer.get("seats"), int) else ""
                # 국내선 마이리얼트립은 편마다가 아니라 노선 검색 주소 하나다 — 줄마다 붙이지 않고 끝에 한 번 적는다
                link = "" if offer.get("link_kind") == "route_search" else f": {offer.get('link') or '링크 없음'}"
                lines.append(f"   · {offer['label']} {_won(offer.get('price_total'), offer.get('currency') or '')}{seats}{link}")
        if empty and not fallback:
            # 뺀 경유 편만 있던 시간대는 「없었다」가 아니라 「뺐다」고 적는다
            slow_only = [name for name in empty if any(_band(option) == name for option in options)]
            none = [name for name in empty if name not in slow_only]
            if none:
                lines.append(f"받은 결과에 {' · '.join(BAND_LABEL[name] for name in none)} 출발 편은 없었습니다"
                             "(가격이 낮은 순으로 일부만 받습니다).")
            if slow_only:
                lines.append(f"{' · '.join(BAND_LABEL[name] for name in slow_only)} 출발은 경유로 직항보다 "
                             f"{SLOW_FACTOR}배 넘게 걸리는 편뿐이라 뺐습니다.")
        searches = sorted({(offer["label"], offer["link"]) for option in shown_options for offer in option["offers"]
                           if offer.get("link_kind") == "route_search" and offer.get("link")})
        pages = [f"{label} 이 노선 · 날짜의 검색 결과 페이지(위 편을 목록에서 고르시면 됩니다): {url}" for label, url in searches]
        counted = [f"마이리얼트립 {len(mrt.get('flights') or [])}개" if mrt is not None else "마이리얼트립 조회 실패",
                   f"항공사·여행사 판매처 {len(offers.get('flights') or [])}개" if offers is not None
                   else "항공사·여행사 판매처는 편도만" if found.return_date else "판매처 비교 조회 실패",
                   ("구글 항공권 왕복 최저가 참고" if google.get("note") and not google.get("flights")
                    else f"구글 항공권 {len(google.get('flights') or [])}개")
                   if google is not None else "구글 항공권 조회 실패"]
        if google and google.get("page") and not google.get("flights"):
            # 왕복 — 편끼리 묶지 못해 최저가 참고와 결과 페이지만 준다(`serpapi_flights.py`)
            lowest = google.get("round_trip_lowest")
            pages.append(f"구글 항공권 왕복 최저 참고 {_won(lowest, 'KRW') if lowest is not None else '가격 모름'}"
                         f"(가는 편 · 오는 편 합, 편별 비교 안 함): {google['page']}")
        said = " · ".join(BAND_LABEL[name] for name in wanted)
        if fallback:
            head = (f"{route} · {when} · {party} 조건으로 찾은 결과({' · '.join(counted)})에는 {said} 출발 편이 없어, "
                    "다른 출발 시간대마다 가장 싼 편을 보여 드립니다(가격이 낮은 순으로 일부만 받습니다).")
        else:
            how = (f"{said} 출발 편을 가격이 낮은 순으로 {len(shown_options)}개" if len(wanted) == 1
                   else f"{said} 출발 시간대마다 가장 싼 편을" if wanted else "출발 시간대마다 가장 싼 편을")
            head = f"{route} · {when} · {party} 조건으로 찾은 결과({' · '.join(counted)})를 같은 편끼리 묶어 {how} 보여 드립니다."
        others = ["같은 조건으로 다른 곳에서 보기(가격은 그 사이트에서 확인):",
                  *[f"   · {name}: {url}" for name, url in _elsewhere(found)]]
        tail = ("가격과 좌석은 조회 시점 참고값이며 판매처 화면에서 달라질 수 있습니다. 링크가 열리지 않으면 같은 편의 다른 판매처 링크를 써 주세요. "
                "예약 · 결제는 링크한 판매처에서 직접 하시면 됩니다.")
        shown = [{"airline": option["airline"], "best": option["best"], "band": _band(option),
                  "offers": [{"source": offer["source"], "price_total": offer.get("price_total"), "link_kind": offer.get("link_kind")}
                             for offer in option["offers"]]} for option in shown_options]
        # 두 소스가 다 판 편 — 보여 준 것뿐 아니라 묶인 전부. 같은 편 가격 차이를 재려고 남긴다(답에는 안 싣는다)
        both = [{"flight": "/".join(str(leg.get("flightNumber") or "?") for leg in option["legs"]),
                 "depart": option["legs"][0].get("departTime"),
                 **{source: min((offer["price_total"] for offer in option["offers"]
                                 if offer["source"] == source and isinstance(offer["price_total"], (int, float))), default=None)
                    for source in ("myrealtrip", "ignav")}}
                for option in options if {offer["source"] for offer in option["offers"]} >= {"myrealtrip", "ignav"}]
        return self._respond(task, evidence, {**decision, "found": len(options), "shown": shown, "both": both,
                                              "times": wanted or None, "empty_bands": empty, "fallback": fallback,
                                              "dropped_slow": slow},
                             "\n".join([head, *lines, *pages, *others, tail]))

    def _trip(self, task: TeamTask, seen: set[str]) -> tuple[dict[str, Any] | None, list[Evidence]]:
        """Case 에 여행이 붙어 있으면 그 일정을 모델에 줄 요약으로(숙소 팀과 같다 — 팀끼리 import 하지 않으려고 따로 둔다)."""
        ref = task.context.current_state.get("subject_ref") or {}
        evidence = list(task.context.evidence)
        if ref.get("kind") != "trip" or not ref.get("id"):
            return None, evidence
        view = self._read(task, "read.itinerary", {"trip_id": ref["id"]}, seen)
        evidence = self._evidence(task, source_id="read.itinerary", claim="현재 일정 버전", value=view, base=evidence)
        if not view:
            return None, evidence
        days = sorted(str(item["starts_at"])[:10] for item in view.get("items") or [] if item.get("starts_at"))
        return {"party_size": (view.get("trip") or {}).get("party_size"),
                "first_day": days[0] if days else None, "last_day": days[-1] if days else None,
                "places": [str(item.get("title")) for item in view.get("items") or [] if item.get("title")]}, evidence

    def _respond(self, task: TeamTask, evidence: list[Evidence], decision: dict[str, Any], answer: str) -> TeamResult:
        return self._result(task, outcome="completed", confidence=1.0, evidence=evidence,
                            next_action=NextAction.RESPOND, answer=answer[:6000], decisions=[decision])


__all__ = ["FlightTeam", "PROMPT_KEY"]
