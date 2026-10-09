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
from .interpret import Interpretation, InterpretationInvalid, ask, ground, needs, parse

logger = logging.getLogger(__name__)

PROMPT_KEY = "flight.interpret"
SEOUL = ZoneInfo("Asia/Seoul")
#: 받는 항공편 수 = 답에 싣는 수. 한 번만 부른다. 우리가 고른 값
SHOWN = 3
#: 소스마다 받는 수 — 묶기 위해 보여 줄 수보다 넉넉히 받는다. 우리가 고른 값
FETCH = 10


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


def _offer(flight: dict[str, Any], source: str) -> dict[str, Any]:
    if source == "myrealtrip":
        label = "마이리얼트립"
    else:
        kind = {"seller_airline": "항공사 공식", "seller_ota": "여행사"}.get(str(flight.get("link_kind") or ""), "판매처")
        label = f"{flight.get('seller') or '판매처'}({kind})"
    return {"source": source, "label": label, "price_total": flight.get("price_total"),
            "currency": flight.get("currency") or "", "seats": flight.get("seats"),
            "link": flight.get("link") or "", "link_kind": flight.get("link_kind") or ""}


def _merge(mrt: list[dict[str, Any]], offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """두 소스의 편을 같은 편끼리 묶는다. 가격은 바꾸지 않고 판매처별로 나란히 둔다.

    ★순서: 편마다 가장 낮은 가격(원화만 비교) → 가격 모름은 뒤. 소스가 준 값만 쓴다.
    ★편명은 마이리얼트립 국제선에 없어서(2026-10-07 응답) Ignav 쪽 편명을 빌려 적는다 — 같은 편으로 묶였을 때만.
    """
    options: list[dict[str, Any]] = []
    index: dict[tuple[Any, ...], dict[str, Any]] = {}
    for source, flights in (("myrealtrip", mrt), ("ignav", offers)):
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
            if not any(offer["source"] == source and offer["link"] == (flight.get("link") or "") for offer in option["offers"]):
                option["offers"].append(_offer(flight, source))
    for option in options:
        won = [offer["price_total"] for offer in option["offers"]
               if isinstance(offer["price_total"], (int, float)) and offer["currency"] in ("", "KRW")]
        option["best"] = min(won) if won else None
        option["offers"].sort(key=lambda offer: (not isinstance(offer["price_total"], (int, float)), offer["price_total"] or 0))
    options.sort(key=lambda option: (option["best"] is None, option["best"] or 0))
    return options


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
        allowed_tools=["read.booking", "read.itinerary", "read.flight_search", "read.flight_offers"],
        knowledge_scope=["flight"],
        max_steps=4,                                  # 일정 1 + 검색 2(마이리얼트립 · Ignav) + 여유 1
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
        offers = self._read(task, "read.flight_offers", dict(arguments), seen)
        evidence = self._evidence(task, source_id="read.flight_offers", claim="항공편 검색 결과(Ignav · 판매처 링크)",
                                  value=offers, base=evidence)
        if mrt is None and offers is None:
            return self._unknown(task, "항공편 검색 결과", evidence)
        route = f"{found.origin} → {found.destination}"
        options = _merge((mrt or {}).get("flights") or [], (offers or {}).get("flights") or [])
        if not options:
            return self._respond(task, evidence, {**decision, "found": 0},
                                 f"{route} · {when} 조건으로 찾은 항공편이 없습니다. 날짜나 공항을 바꿔 다시 말씀해 주세요.")
        party = f"성인 {found.adults}명" + (f" · 아동 {found.children}명" if found.children else "") \
            + (f" · 유아 {found.infants}명" if found.infants else "")
        shown_options = options[:SHOWN]
        fastest = min((option["minutes"] for option in shown_options if isinstance(option["minutes"], int)), default=None)
        lines = []
        for number, option in enumerate(shown_options, start=1):
            legs = " / ".join(_leg(leg) for leg in option["legs"]) or "구간 정보 없음"
            tags = []
            if number == 1 and option["best"] is not None:
                tags.append("최저가")
            if fastest is not None and option["minutes"] == fastest and len(shown_options) > 1:
                tags.append("가장 짧음")
            lines.append(f"{number}. {option['airline'] or '항공사 모름'} — {legs}" + (f" [{' · '.join(tags)}]" if tags else ""))
            for offer in option["offers"]:
                seats = f" · 남은 좌석 {offer['seats']}" if isinstance(offer.get("seats"), int) else ""
                # 국내선 마이리얼트립은 편마다가 아니라 노선 검색 주소 하나다 — 줄마다 붙이지 않고 끝에 한 번 적는다
                link = "" if offer.get("link_kind") == "route_search" else f": {offer.get('link') or '링크 없음'}"
                lines.append(f"   · {offer['label']} {_won(offer.get('price_total'), offer.get('currency') or '')}{seats}{link}")
        searches = sorted({offer["link"] for option in shown_options for offer in option["offers"]
                           if offer.get("link_kind") == "route_search" and offer.get("link")})
        pages = [f"마이리얼트립 이 노선 · 날짜의 검색 결과 페이지(위 편을 목록에서 고르시면 됩니다): {url}" for url in searches]
        counted = [f"마이리얼트립 {len(mrt.get('flights') or [])}개" if mrt is not None else "마이리얼트립 조회 실패",
                   f"항공사·여행사 판매처 {len(offers.get('flights') or [])}개" if offers is not None else "판매처 비교 조회 실패"]
        head = (f"{route} · {when} · {party} 조건으로 찾은 결과({' · '.join(counted)})를 같은 편끼리 묶어 "
                f"가격이 낮은 순으로 {len(shown_options)}개 보여 드립니다.")
        tail = ("가격과 좌석은 조회 시점 참고값이며 판매처 화면에서 달라질 수 있습니다. 링크가 열리지 않으면 같은 편의 다른 판매처 링크를 써 주세요. "
                "예약 · 결제는 링크한 판매처에서 직접 하시면 됩니다.")
        shown = [{"airline": option["airline"], "best": option["best"],
                  "offers": [{"source": offer["source"], "price_total": offer.get("price_total"), "link_kind": offer.get("link_kind")}
                             for offer in option["offers"]]} for option in shown_options]
        # 두 소스가 다 판 편 — 보여 준 것뿐 아니라 묶인 전부. 같은 편 가격 차이를 재려고 남긴다(답에는 안 싣는다)
        both = [{"flight": "/".join(str(leg.get("flightNumber") or "?") for leg in option["legs"]),
                 "depart": option["legs"][0].get("departTime"),
                 **{source: min((offer["price_total"] for offer in option["offers"]
                                 if offer["source"] == source and isinstance(offer["price_total"], (int, float))), default=None)
                    for source in ("myrealtrip", "ignav")}}
                for option in options if {offer["source"] for offer in option["offers"]} >= {"myrealtrip", "ignav"}]
        return self._respond(task, evidence, {**decision, "found": len(options), "shown": shown, "both": both},
                             "\n".join([head, *lines, *pages, tail]))

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
