# -*- coding: utf-8 -*-
"""Lodging Team — 숙소를 찾아 주고, 이미 잡은 숙소의 위치 · 정보를 찾아 준다. `[2026-10-07]`

흐름(`lodging.assist`): 모델 **한 번**이 문장(+ 여행 일정 요약)을 고정된 구조로 옮긴다 → 서버가 검증한다 →
빠진 값이 있으면 되묻고, 없으면 도구로 찾는다 → 받은 값으로 답을 쓴다.

- 모델은 **해석만** 한다. 검색 · 고르기 · 가격 · 링크는 전부 도구(`read.stay_search` · `read.stay_detail`)가 준 값이다.
- 문장 규칙(키워드 맞추기 · 정규식)으로 뜻을 가르지 않는다 — 찾기 / 내 숙소 / 예약 상태 / 모름을 모델이 고른다.
- 예약 · 결제는 하지 않는다. 마이리얼트립 숙소 페이지 링크만 준다. 일정에 저장하지도 않는다(아직 정하지 않았다).
- ★되묻기는 `waiting` 이 아니라 **답(`completed`)으로** 한다. Case 를 다시 깨우는 입구(`POST /v1/cases/{id}/messages`)가
  고객이 보낸 글을 팀에 넘기지 않아(`Controller.resume` 은 토큰만 받고, 팀은 처음 문장을 다시 받는다) `waiting` 으로 두면
  같은 질문만 되풀이된다. 고객이 조건을 채워 다시 보내면 새 요청으로 처리된다.
- `lodging.status` 는 전과 같다 — 잠긴 예약을 조회만 한다.
- `[2026-10-10]` **비교**: 찾기에서 같은 조건으로 구글 호텔(`read.stay_google`, SerpApi 한국 설정)도 부르고, 마이리얼트립 목록 아래에
  구글 호텔 쪽 숙소(호텔만, 이미 보인 이름은 빼고) 최대 `GOOGLE_SHOWN` 곳을 따로 보여 준다. 두 소스의 숙소 이름이 달라(한국어 · 영어 ·
  지점 표기) 같은 숙소로 묶지는 않는다. 끝에 「같은 조건으로 다른 곳에서 보기」(부킹닷컴) 링크를 붙인다. 가격은 조회 시점 참고값이다.
"""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from app.core.contracts import Evidence, NextAction, TeamManifest, TeamResult, TeamTask

from app.domains.travel_ops.instances._shared._base import TravelTeamBase
from .interpret import Interpretation, InterpretationInvalid, ask, ground, needs, parse

logger = logging.getLogger(__name__)

PROMPT_KEY = "lodging.interpret"
SEOUL = ZoneInfo("Asia/Seoul")
#: 답에 싣는 숙소 수 · 그만큼 채우려고 상세를 부르는 최대 횟수(객실 없는 곳은 건너뛴다). 우리가 고른 값
SHOWN, DETAIL_CALLS = 3, 4
#: 목록에서 받는 수(찾기) · 이름으로 찾을 때 받는 수(내 숙소). 우리가 고른 값
SEARCH_SIZE, NAME_SIZE = 20, 5
#: 구글 호텔에서 따로 보여 주는 수. 우리가 고른 값
GOOGLE_SHOWN = 3


def _won(value: Any) -> str:
    return f"{int(value):,}원" if isinstance(value, (int, float)) else "가격 모름"


def _same_name(left: str, right: str) -> bool:
    return "".join(left.split()).casefold() == "".join(right.split()).casefold()


class LodgingTeam(TravelTeamBase):
    manifest = TeamManifest(
        team_id="lodging",
        display_name="Lodging Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["lodging.assist", "lodging.status"],
        accepted_case_types=["lodging"],
        # 정책 문서를 쓰지 않는다 — 선언하면 문서 0건으로 degraded 가 된다(`locked` 의 2026-09-22 주석과 같은 까닭)
        required_context=["case_state", "db_facts", "history"],
        allowed_tools=["read.booking", "read.itinerary", "read.stay_search", "read.stay_detail", "read.stay_google"],
        knowledge_scope=["lodging"],
        max_steps=8,                                  # 일정 1 + 목록 1 + 구글 호텔 1 + 상세 DETAIL_CALLS + 여유 1
        active=True,
        implementation_revision="2026-10-07",
        default_capability="lodging.assist",
    )

    async def execute(self, task: TeamTask) -> TeamResult:
        blocked = self._guard(task)
        if blocked is not None:
            return blocked
        seen: set[str] = set()
        if task.capability == "lodging.status":
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
            logger.warning("lodging interpretation invalid case=%s %s", task.case_id, exc)
            return self._escalate(task, "interpretation_invalid", evidence, warnings=[str(exc)[:200]])
        except Exception as exc:                      # noqa: BLE001 — 모델 호출 실패의 종류를 남기고 사람에게 넘긴다
            logger.warning("lodging interpretation failed case=%s %s", task.case_id, type(exc).__name__)
            return self._escalate(task, "interpretation_failed", evidence, warnings=[type(exc).__name__])

        evidence = [*evidence, Evidence(
            evidence_id=f"interpretation:{task.team_id}", source_type="customer_message", source_id=PROMPT_KEY,
            claim="고객 문장을 모델이 옮긴 구조", value={**found.model_dump(mode="json"), "ungrounded": ungrounded}, confidence=1.0,
            observed_at=datetime.now(SEOUL))]
        decision = {"task": found.task, "interpretation": found.model_dump(mode="json", exclude={"question"}),
                    "ungrounded": ungrounded}

        if found.task == "status":
            return self._status(task, seen, evidence)
        if found.task == "unclear":
            return self._respond(task, evidence, {**decision, "needs": ["task"]},
                                 "숙소를 새로 찾아 드릴지, 이미 예약하신 숙소를 알려 주시는 것인지 말씀해 주세요. "
                                 "찾아 드리려면 지역 · 날짜 · 인원을, 예약하신 숙소라면 숙소 이름과 날짜를 알려 주세요.")
        missing = needs(found, today=today)
        if missing:
            return self._respond(task, evidence, {**decision, "needs": missing}, ask(found, missing))
        if found.task == "my_stay":
            return self._my_stay(task, found, seen, evidence, decision)
        return self._search(task, found, seen, evidence, decision)

    # ── 갈래 ────────────────────────────────────────────────────
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
        dates = {"check_in": found.check_in.isoformat(), "check_out": found.check_out.isoformat()}
        party = {"adults": found.adults, "children": found.children}
        listing = self._read(task, "read.stay_search", {
            "keyword": found.keyword, **dates, **party, "domestic": found.domestic, "size": SEARCH_SIZE,
            "max_price": found.max_price_per_night, "min_review_rating": found.min_rating}, seen)
        # `[2026-10-10]` 마이리얼트립이 429 뒤 쉬는 중이면 표시만 온다 — 결과가 아니니 근거에 싣지 않는다
        resting = bool(listing and listing.get("cooldown_seconds"))
        if resting:
            listing = None
        evidence = self._evidence(task, source_id="read.stay_search", claim="숙소 검색 결과(마이리얼트립)", value=listing,
                                  base=evidence)
        google = self._read(task, "read.stay_google", {
            "keyword": found.keyword, **dates, **party, "size": SEARCH_SIZE, "max_price": found.max_price_per_night}, seen)
        evidence = self._evidence(task, source_id="read.stay_google", claim="숙소 검색 결과(SerpApi 구글 호텔, 한국 설정)",
                                  value=google, base=evidence)
        extra = self._google_block(found, dates, google, [])
        if listing is None:
            why = "요청 한도로 잠시 조회를 쉬고 있습니다" if resting else "결과를 받지 못했습니다(조회 실패)"
            if (google and google.get("stays")) or resting:
                # 마이리얼트립을 못 읽어도 구글 호텔 · 다른 곳 링크는 보여 준다 — 그렇다고 적는다
                return self._respond(task, evidence, {**decision, "found": None, "resting": resting,
                                                      "google": len((google or {}).get("stays") or [])},
                                     "\n".join([f"{found.keyword} · {dates['check_in']}~{dates['check_out']} 조건으로 마이리얼트립 검색은 {why}.",
                                                *extra]))
            return self._unknown(task, "숙소 검색 결과", evidence)
        if not listing["stays"]:
            return self._respond(task, evidence, {**decision, "found": 0},
                                 f"{found.keyword} · {dates['check_in']}~{dates['check_out']} 조건으로 찾은 숙소가 없습니다. "
                                 "지역이나 가격 · 평점 조건을 바꿔 다시 말씀해 주세요.")
        # 순서는 제공처가 준 그대로 — 우리가 다시 매기지 않는다. 다만 그 날짜에 객실이 없는 곳은 싣지 않는다.
        # ☆2026-10-07 17:48 playdata — 앞의 셋을 그대로 실었더니 둘이 「해당 날짜 객실 없음 · 가격 모름」이었다.
        lines, shown, skipped, calls = [], [], [], 0
        for stay in listing["stays"]:
            if len(lines) >= SHOWN or calls >= DETAIL_CALLS:
                break
            if stay.get("price_per_night") is None:
                # ★목록에 가격이 없는 곳은 상세를 부르지 않는다 — 2026-10-08 14:41 playdata 에서 상세가 「객실 없음」이던 곳
                #   (1356616 · 3171484)이 같은 조건의 목록에서 가격 없이 왔다. 호출을 아끼려는 것이고, 상세 확인도 그대로 둔다
                skipped.append({"gid": stay["gid"], "name": stay["name"], "reason": "no_price_in_list"})
                continue
            calls += 1
            detail = self._read(task, "read.stay_detail", {"gid": stay["gid"], **dates, **party}, seen)
            if detail and detail.get("cooldown_seconds"):
                detail = None                         # 상세 도중 429 — 쉬는 표시는 상세가 아니다(아래에서 더 부르지 않고 멈춘다)
            evidence = self._evidence(task, source_id=f"read.stay_detail:{stay['gid']}", claim="숙소 상세(마이리얼트립)",
                                      value=detail, base=evidence)
            if detail is not None and (detail.get("no_rooms") or detail.get("sold_out")):
                skipped.append({"gid": stay["gid"], "name": stay["name"], "reason": "no_rooms"})
                continue
            shown.append({"gid": stay["gid"], "name": stay["name"], "detail_read": detail is not None})
            lines.append(self._line(len(lines) + 1, stay, detail))
            if detail is None:
                # ★상세를 못 읽었으면 더 부르지 않는다 — 대개 제공처가 거절한 것이고(2026-10-08 14:35 playdata 429), 이어 부르면 부하만 보탠다
                break
        extra = self._google_block(found, dates, google, [item["name"] for item in shown])
        decision = {**decision, "found": len(listing["stays"]), "shown": shown, "skipped": skipped,
                    "google": len((google or {}).get("stays") or []) if google is not None else None}
        if not lines:
            return self._respond(task, evidence, decision,
                                 f"{found.keyword} · {dates['check_in']}~{dates['check_out']} 조건으로 받은 {len(listing['stays'])}곳 중 "
                                 f"{len(skipped)}곳이 가격이 없거나 그 날짜에 객실이 없었고, 그 밖의 곳은 확인하지 못했습니다. "
                                 "날짜나 지역을 바꿔 다시 말씀해 주세요." + ("\n" + "\n".join(extra) if extra else ""))
        head = (f"{found.keyword} · {dates['check_in']}~{dates['check_out']} · 성인 {found.adults}명 조건으로 "
                f"{listing.get('total') or len(listing['stays'])}곳 중 {len(lines)}곳입니다(마이리얼트립 검색 순서"
                + (f", 가격이 없거나 그 날짜에 객실이 없는 {len(skipped)}곳은 건너뜀" if skipped else "") + ").")
        tail = "가격과 잔여 객실은 조회 시점 기준이며 링크에서 다시 확인해 주세요. 예약은 링크한 페이지에서 직접 하시면 됩니다."
        return self._respond(task, evidence, decision, "\n".join([head, *lines, *extra, tail]))

    def _my_stay(self, task: TeamTask, found: Interpretation, seen: set[str], evidence: list[Evidence],
                 decision: dict[str, Any]) -> TeamResult:
        dates = {"check_in": found.check_in.isoformat(), "check_out": found.check_out.isoformat()}
        party = {"adults": found.adults, "children": found.children}
        listing = self._read(task, "read.stay_search", {"keyword": found.stay_name, **dates, **party,
                                                        "domestic": found.domestic, "size": NAME_SIZE}, seen)
        evidence = self._evidence(task, source_id="read.stay_search", claim="숙소 이름 검색 결과(마이리얼트립)", value=listing,
                                  base=evidence)
        if listing is None:
            return self._unknown(task, "숙소 검색 결과", evidence)
        stays = listing["stays"]
        exact = [stay for stay in stays if _same_name(stay["name"], found.stay_name)]
        chosen = exact[0] if len(exact) == 1 else stays[0] if len(stays) == 1 else None
        if chosen is None:
            if not stays:
                return self._respond(task, evidence, {**decision, "found": 0},
                                     f"「{found.stay_name}」 이름으로 찾은 숙소가 없습니다. 숙소 이름을 예약 확인서에 적힌 대로 다시 알려 주세요.")
            names = " / ".join(stay["name"] for stay in stays)
            return self._respond(task, evidence, {**decision, "found": len(stays), "needs": ["stay_name"]},
                                 f"「{found.stay_name}」 에 해당할 수 있는 숙소가 여러 곳입니다: {names}. 어느 곳인지 이름을 그대로 알려 주세요.")
        detail = self._read(task, "read.stay_detail", {"gid": chosen["gid"], **dates, **party}, seen)
        evidence = self._evidence(task, source_id=f"read.stay_detail:{chosen['gid']}", claim="숙소 상세(마이리얼트립)",
                                  value=detail, base=evidence)
        if detail is None or detail.get("latitude") is None or detail.get("longitude") is None:
            return self._unknown(task, "숙소 위치", evidence)
        stay = {key: detail.get(key) for key in ("gid", "name", "address", "latitude", "longitude", "link")}
        answer = (f"{detail['name']} — {detail.get('address') or '주소 모름'} "
                  f"(위도 {detail['latitude']}, 경도 {detail['longitude']}). "
                  f"{dates['check_in']}~{dates['check_out']} 숙박으로 확인했습니다. 숙소 페이지: {detail.get('link') or '링크 없음'}\n"
                  "위치는 마이리얼트립에 등록된 값입니다. 일정에는 아직 넣지 않았습니다.")
        return self._respond(task, evidence, {**decision, "my_stay": {**stay, **dates}}, answer)

    # ── 부품 ────────────────────────────────────────────────────
    @staticmethod
    def _google_block(found: Interpretation, dates: dict[str, str], google: dict[str, Any] | None,
                      shown_names: list[str]) -> list[str]:
        """구글 호텔 쪽 줄 + 다른 곳에서 보기 링크. 이미 보인 이름(공백 · 대소문자 무시)과 숙박 공유(vacation rental)는 뺀다.

        ★숙박 공유를 빼는 까닭 — ☆2026-10-10 14:21 playdata 「서울 명동」 앞의 셋이 숙박 공유(Bluepillow · Vio)였고 평점 · 후기가 없었다.
        ★가격이 없는 곳도 뺀다 — ☆15:37 「지요크 명동」이 가격 · 링크 없이 왔다(비교에 쓸 수 없다).
        """
        lines: list[str] = []
        if google is None:
            lines.append("구글 호텔 비교는 받지 못했습니다(조회 실패).")
        else:
            seen = {"".join(name.split()).casefold() for name in shown_names}
            picks = [stay for stay in google.get("stays") or []
                     if stay.get("type") != "vacation rental" and stay.get("price_per_night") is not None
                     and "".join(stay["name"].split()).casefold() not in seen][:GOOGLE_SHOWN]
            if picks:
                lines.append("구글 호텔에서 본 같은 조건 숙소(구글 순서, 숙박 공유 제외):")
                for stay in picks:
                    rating = (f"평점 {stay['rating']:.1f}/5" + (f"(후기 {stay['review_count']:,})" if isinstance(stay.get("review_count"), int) else "")
                              if stay.get("rating") else "평점 없음")
                    star = f"{stay['hotel_class']}성급 · " if stay.get("hotel_class") else ""
                    lines.append(f"   · {stay['name']} — {star}1박 {_won(stay.get('price_per_night'))} · 전체 {_won(stay.get('total_price'))} · "
                                 f"{rating}: {stay.get('link') or '링크 없음'}")
            if google.get("page"):
                lines.append(f"구글 호텔 검색 결과 페이지(날짜는 그 화면에서 다시 고르셔야 할 수 있습니다): {google['page']}")
        booking = (f"https://www.booking.com/searchresults.ko.html?ss={quote(found.keyword or '')}"
                   f"&checkin={dates['check_in']}&checkout={dates['check_out']}"
                   f"&group_adults={found.adults or 1}&no_rooms=1&group_children={found.children or 0}")
        lines += ["같은 조건으로 다른 곳에서 보기(가격은 그 사이트에서 확인):", f"   · 부킹닷컴: {booking}"]
        return lines

    def _trip(self, task: TeamTask, seen: set[str]) -> tuple[dict[str, Any] | None, list[Evidence]]:
        """Case 에 여행이 붙어 있으면 그 일정을 모델에 줄 요약으로. 없거나 못 읽으면 `None` — 없이 해석한다."""
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

    @staticmethod
    def _line(number: int, stay: dict[str, Any], detail: dict[str, Any] | None) -> str:
        # 후기가 없는 곳은 평점이 0.0 으로 온다(2026-10-07 17:48 playdata) — 0점이 아니라 평점이 없는 것이다
        rating = f"평점 {stay['rating']}/5" + (f"(후기 {stay['review_count']:,})" if stay.get("review_count") else "") \
            if stay.get("rating") else "평점 없음"
        if detail is None:
            return (f"{number}. {stay['name']} — 1박 {_won(stay.get('price_per_night'))} · {rating} · "
                    f"{stay.get('description') or ''} (상세 · 링크를 불러오지 못했습니다)")
        return (f"{number}. {stay['name']} — 1박 {_won(detail.get('price_per_night'))} · 전체 {_won(detail.get('total_price'))}(세금 포함) · "
                f"{rating} · {detail.get('address') or '주소 모름'} · {detail.get('link') or '링크 없음'}")

    def _respond(self, task: TeamTask, evidence: list[Evidence], decision: dict[str, Any], answer: str) -> TeamResult:
        return self._result(task, outcome="completed", confidence=1.0, evidence=evidence,
                            next_action=NextAction.RESPOND, answer=answer[:6000], decisions=[decision])


__all__ = ["LodgingTeam", "PROMPT_KEY"]
