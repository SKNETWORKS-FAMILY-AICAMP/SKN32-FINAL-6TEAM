# -*- coding: utf-8 -*-
"""비서처럼 먼저 채우기 — 읽은 직후 빈칸을 담당에게 보내 제안을 받고, 코드가 초안에 대 본 뒤 「우리가 채움」 + 이유로 싣는다. `[2026-10-16 D-025]`

    빈칸     모델이 분류한 것(`reading.agent` 의 gaps · missing · guard) + 사실 검사가 찾은 것(검사의 「확인 필요」 일정 · 늦게 닿는 구간 · 범위)
    담당     `gaps.ROUTES` 의 연결표대로 — 식당 팀 · 활동 팀 · 이동 판정은 **전체 자동 추천**(`autofix.plan`: 후보는 팀이 먼저, 운영시간 · 휴무 · 앞뒤 이동을 맞춰 본 것만)
             으로, 통째 빈 시간대는 계획 에이전트(`plan_slot` — 정리표 + 선호를 받고 빈칸 하나만 채운다), 고객만 아는 값은 고객 질문으로
    적용     `pipeline.edit(via="autofix")` — 고객이 고른 것과 같은 길이라 확인 화면의 되돌리기(앞 값으로 다시 고치기)가 그대로 된다
    기록     값 줄 `reading.prefill` — 무엇을 왜 채웠나(`filled`) · 묻는 것(`questions`) · 회차(`rounds`). 확인 화면이 「우리가 채움」 표시와 이유를 여기서 읽는다

★고정한 일정 · 예약 일정 · 재난 규칙은 건드리지 않는다(자동 추천이 이미 지킨다 — `kept: locked · booked`). 맞는 안이 없으면 지어내지 않고 그대로 둔다.
★영업시간 모름 · 이동 빠듯은 노란 표시만 — 막지 않는다(검사 결과 그대로). 돈(유료 입장)은 지금 범위 밖이다.
★새 충돌이 생기면 최대 2회까지 다시 돈다(`gaps.MAX_ROUNDS`).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Mapping
from uuid import UUID

from . import gaps as gaps_module
from .fact_check import guard_gaps, scope_gaps
from .gaps import Gap, Proposal
from . import lodging_context

log = logging.getLogger(__name__)

#: 담당 이름 → 고객에게 보일 이름
OWNER_LABEL = {"dining_team": "식당 팀", "activity_team": "활동 팀", "mobility": "이동 판정", "planner": "계획 에이전트",
               "lodging_team": "숙소 추천", "ask_customer": "고객 확인"}
#: 한 접수에서 계획 에이전트에게 맡기는 빈 시간대 수의 상한(우리가 고른 값)
MAX_PLANNER_SLOTS = 3
MISSING_QUESTION = {"first_day_date": "여행 첫날이 언제인가요?", "lodging_name": "묵는 숙소 이름을 알려 주시면 숙소 기준으로 동선을 맞출게요",
                    "booked_place_name": "예약하신 곳의 이름을 알려 주세요 — 예약 일정은 우리가 바꾸지 않아요"}
#: `[2026-10-19 사용자 결정 — 못 찾은 줄은 후보 보이고 묻기 + 직접 고르기]` 못 찾은 줄의 질문 카드.
#:   후보는 질문에 싣지 않는다 — 화면이 이미 있는 `GET …/candidates` 로 받는다(같은 검사 · 같은 순서, 판이 바뀌어도 낡지 않게).
#:   「직접 고르기」는 그 줄의 장소 바꾸기 · 검색을 연다(새 화면 없음). 설계 `wiki/records/plans/2026-10-19_못찾은장소_후보와_직접고르기_설계.md`
PLACE_NOT_FOUND_QUESTION = "「{title}」을 지도에서 찾지 못했어요 — 후보에서 고르거나 직접 골라 주세요"
PLACE_NOT_FOUND_BLOCKED_QUESTION = "「{title}」은 장소 조회가 막혀 다시 찾아봤지만 찾지 못했어요 — 후보에서 고르거나 직접 골라 주세요"
PLACE_NOT_FOUND_ACTIONS = ("pick_candidate", "pick_myself", "no_place")
#: `[2026-10-26 사용자 지시 — 호텔 후보는 고객이 고른다]` 이름 없는 호텔 줄의 질문 카드 — 못 찾은 줄과 같은 모양(그 일정 · 후보 · 직접 고르기).
#:   후보는 싣지 않는다 — 화면이 `GET …/candidates` 로 받는다(최대 3곳 + 숙소 안 식사 짝). 후보가 하나여도 먼저 채우지 않는다
LODGING_PICK_QUESTION = "「{title}」 — 묵을 숙소를 후보에서 골라 주세요(후보가 하나여도 고르신 뒤에 넣어요)"


def _open_stay(item: Mapping[str, Any]) -> bool:
    return (item.get("place_state") == "needs_choice" and lodging_context.generic(item)
            and not lodging_context.protected(item))


def model_gaps(claims: list[Mapping[str, Any]], items: list[Mapping[str, Any]]) -> list[Gap]:
    """이해 에이전트가 분류한 빈칸 — 원본마다 `reading.agent` 값 줄에서. 빈칸 근거가 이미 있는 일정(이름 없는 자리)을 가리키면 그 일정에 붙인다."""
    out: list[Gap] = []
    for row in claims:
        if row.get("field") != "reading.agent" or not isinstance(row.get("value"), dict) or not row["value"].get("used"):
            continue
        value = row["value"]
        source_id = str(row.get("source_id") or "")
        for gap in value.get("gaps") or []:
            target = _item_for_quote(items, source_id, gap.get("quote") or "")
            if target is not None and target.get("place_state") not in (None, "needs_choice"):
                continue                               # 고객이 이름을 적은 자리 — 빈칸이 아니다(모델이 빈칸이라 해도 채우지 않는다)
            if target is not None:
                if lodging_context.protected(target):
                    continue
                kind = "lodging_place" if _open_stay(target) else gap["kind"] if gap["kind"] != "free_slot" else "activity_place"
                out.append(Gap(kind, {"item": target["id"]},
                               f"계획서의 「{gap['quote']}」", quote=gap["quote"]))
            else:
                out.append(Gap("free_slot", {"source_id": source_id, "day": gap.get("day"), "window": [gap.get("start"), gap.get("end")],
                                             "meal": gap["kind"] == "meal_place"},
                               f"계획서의 「{gap['quote']}」", quote=gap["quote"]))
        for code in value.get("missing") or []:
            if code == "lodging_name" and any(_open_stay(item) or (lodging_context.is_stay(item) and item.get("place")) for item in items):
                continue
            if code == "booked_place_name":
                booked = [item for item in items if str(item.get("source_id") or "") == source_id and item.get("booked") is True]
                if booked and all(item.get("place") for item in booked):
                    continue                         # 원문 예약 장소를 확인했다면 모델의 이름 누락 추측보다 확인한 값을 따른다.
            out.append(Gap(code, {"trip": code}, MISSING_QUESTION.get(code, code)))
        out.extend(guard_gaps(value.get("guard")))
    return out


def check_gaps(review: Mapping[str, Any], *, trip: Mapping[str, Any] | None = None) -> list[Gap]:
    """사실 검사가 찾은 빈칸 — **빈칸만**이다. ★고객이 적은 장소 · 시각 · 빠듯한 이동은 빈칸이 아니다(노란 표시만 — D-025 「확인 화면」).

        이름 없는 자리(`needs_choice` — 「성수 식당」처럼 종류 · 동네만)   → 식당 팀 · 활동 팀이 채운다
        예약했다는데 이름이 없다(`needs_name`)                             → 고객 질문(예약 일정은 우리가 고르지 않는다)
        장소를 못 찾았다(`unresolved`)                                       → 고객 질문(이름을 지어내지 않는다) — 후보 · 직접 고르기 카드(`run` 의 질문 모양)
        상품 범위(서울 · 7일 · 4인)                                         → 고객 질문(거절하지 않는다)
    """
    from ..planning.planner import MAX_DAYS, MAX_PARTY

    out: list[Gap] = []
    for item in review.get("items") or []:
        if item.get("locked"):
            continue
        state, title = item.get("place_state"), item.get("title") or "이름 없는 일정"
        parts = item.get("parts") or {}
        if _open_stay(item):
            out.append(Gap("lodging_place", {"item": item["id"]}, f"「{title}」 — 전체 동선에 맞는 공통 숙소를 추천해요",
                           source="check", quote=item.get("title")))
        elif state in ("needs_choice", "needs_name") and (parts.get("lodging_meal") or parts.get("label") == "숙소"
                                                        or item.get("kind") in ("lodging", "stay")):
            # 예약한 숙소의 이름은 추천으로 대신하지 않는다.
            out.append(Gap("lodging_name", {"item": item["id"]}, f"「{title}」 — 묵는 숙소 이름을 알려 주시면 숙소 기준으로 동선을 맞출게요",
                           source="check"))
        elif state == "needs_choice":
            kind = "meal_place" if item.get("kind") == "dining" else "activity_place"
            out.append(Gap(kind, {"item": item["id"]}, f"「{title}」 — 가게 이름이 없는 자리", source="check", quote=item.get("title")))
        elif state == "needs_name":
            out.append(Gap("booked_place_name", {"item": item["id"]}, f"「{title}」 — 예약하신 곳의 이름을 알려 주세요", source="check"))
        elif state == "unresolved":
            out.append(Gap("place_not_found", {"item": item["id"]}, PLACE_NOT_FOUND_QUESTION.format(title=title),
                           source="check", quote=item.get("title")))
    trip = trip or {}
    out.extend(scope_gaps(party_size=_int(trip.get("party_size")), days=_int(trip.get("days")),
                          dates=[i.get("date") for i in review.get("items") or []], max_days=MAX_DAYS, max_party=MAX_PARTY))
    return out


def autofix_owner(plan: Callable[[], Mapping[str, Any]]) -> Callable[[Gap, Mapping[str, Any]], Proposal]:
    """식당 팀 · 활동 팀 · 이동 판정 — 회차마다 전체 자동 추천을 **한 번** 계산하고, 빈칸이 가리키는 일정의 바꿀 안을 제안으로 낸다."""
    cache: dict[str, Any] = {}

    def owner(gap: Gap, draft: Mapping[str, Any]) -> Proposal:
        key = draft.get("revision")
        if cache.get("revision") != key:
            cache.update(revision=key, plan=plan())
        got = cache["plan"]
        item_id = gap.where.get("item")
        change = next((c for c in got.get("changes") or [] if c.get("id") == item_id
                       and any(e.get("field") == "place" for e in c.get("edits") or [])), None)
        if change is None:
            kept = next((k for k in got.get("kept") or [] if k.get("id") == item_id), None)
            return Proposal(gap, gap.owner, [], reason=_kept_reason((kept or {}).get("reason")))
        return Proposal(gap, gap.owner, [{"change": change, "title": ((change.get("to") or {}).get("place") or {}).get("name")
                                          or change.get("title"), "reason": _change_reason(change, gap)}],
                        reason=_change_reason(change, gap),
                        checks=[{"code": "hours", "ok": bool(change.get("hours_known")),
                                 "note": "운영시간 확인" if change.get("hours_known") else "운영시간 모름 — 노란 표시"}])

    return owner


def planner_owner(plan_slot: Callable[[Gap, Mapping[str, Any]], list[dict[str, Any]]] | None) -> Callable[[Gap, Mapping[str, Any]], Proposal]:
    """계획 에이전트 — 정리표 + 선호를 받고 **빈칸 하나**(하루 · 시간대)만 채운다. 후보는 새 일정 하나씩(이름 · 날짜 · 시작 · 끝 · 종류 · 장소)."""

    asked = {"n": 0}

    def owner(gap: Gap, draft: Mapping[str, Any]) -> Proposal:
        if plan_slot is None:
            return Proposal(gap, "planner", [], reason="계획 에이전트가 연결되지 않았다", error="no planner")
        asked["n"] += 1
        if asked["n"] > MAX_PLANNER_SLOTS:
            # ★한 접수에서 계획 에이전트는 몇 번만 — 하루 짜기 한 번이 관광공사 조회 · 판정을 부르므로 읽기가 길어진다(시험지 69건에 빈 시간대 23개)
            return Proposal(gap, "planner", [], reason=f"빈 시간대가 많아 앞 {MAX_PLANNER_SLOTS}곳만 먼저 채웠어요 — 나머지는 「일정 짜 줘」로 채울 수 있어요")
        found = plan_slot(gap, draft) or []
        return Proposal(gap, "planner", [{**f, "reason": f.get("reason") or f"{gap.reason}에 맞춰 골랐어요"} for f in found[:gaps_module.MAX_CANDIDATES]],
                        reason=f"{gap.reason}에 맞춰 골랐어요" if found else "맞는 곳을 찾지 못했다")

    return owner


def planner_slot(conn, *, tenant_id: str, tour: Any, review: Callable[[], Mapping[str, Any]], preferences: str,
                 party_size: int | None) -> Callable[[Gap, Mapping[str, Any]], list[dict[str, Any]]]:
    """계획 에이전트(`planning/planner.py`)에게 **빈칸 하나**를 맡긴다 — 그날 하루만 짜 보게 하고, 빈 시간대 안 · 그날 일정과 겹치지 않는 곳만 후보로 받는다.

    ★고객 원문을 넘기지 않는다 — 정리표(그날 이미 있는 일정 · 이름)와 선호(이해 에이전트가 읽은 성향 · 조건의 원문 인용)만.
    ★날짜를 모르면(첫날 미정) 짜지 않는다 — 그 빈칸은 고객 질문으로 남는다."""
    from datetime import date as date_type, timedelta

    from ..planning import planner as planner_module

    def slot(gap: Gap, draft: Mapping[str, Any]) -> list[dict[str, Any]]:
        now = review()
        items = [i for i in now.get("items") or [] if i.get("date")]
        day_no = gap.where.get("day")
        day = next((i["date"] for i in items if i.get("day") == day_no), None) if day_no else None
        if day is None and items and day_no:
            first = min(date_type.fromisoformat(i["date"]) for i in items)
            day = (first + timedelta(days=int(day_no) - 1)).isoformat()
        if day is None:
            return []
        same = [i for i in items if i["date"] == day and i.get("starts_at")]
        window = gap.where.get("window") or [None, None]
        lo, hi = window[0] or "09:00", window[1] or "21:00"
        try:
            from app.domains.travel_ops.components.team_hooks import dining_ledger

            ledger = dining_ledger.planner_factory(conn)
        except Exception:                              # noqa: BLE001 — 원장이 안 꽂혔으면 관광공사 · 우리 목록만으로
            ledger = None
        request = planner_module.PlanRequest(city="서울", start_date=date_type.fromisoformat(day), days=1,
                                             party_size=max(1, min(party_size or 2, planner_module.MAX_PARTY)),
                                             preferences=preferences, locale="ko")
        try:
            outcome = planner_module.plan_trip(conn=conn, tenant_id=tenant_id, request=request, chat=None, tour_api=tour,
                                               exclude_names=[i["title"] for i in items if i.get("title")], ledger=ledger)
        except planner_module.PlanRefused as refused:
            log.info("prefill planner refused: %s", refused.code)
            return []
        places = {p["key"]: p for p in outcome.draft.places}
        out: list[dict[str, Any]] = []
        for it in outcome.draft.items:
            if it["kind"] == "mobility" or not it.get("place") or it["place"] not in places:
                continue
            if gap.where.get("meal") and it["kind"] != "dining":
                continue
            start, end = it["starts_at"], it["ends_at"] or it["starts_at"] + timedelta(minutes=60)
            hhmm_s, hhmm_e = start.strftime("%H:%M"), end.strftime("%H:%M")
            if not (lo <= hhmm_s and hhmm_e <= hi):
                continue
            if any(_overlaps(hhmm_s, hhmm_e, s.get("starts_at"), s.get("ends_at") or s.get("starts_at")) for s in same):
                continue
            place = places[it["place"]]
            if place.get("lat") is None or place.get("lon") is None:
                continue
            out.append({"title": it["title"], "date": day, "starts_at": hhmm_s, "ends_at": hhmm_e, "kind": it["kind"],
                        "place": {"name": place["name"], "latitude": place["lat"], "longitude": place["lon"], "source": "places",
                                  "kind": place["kind"]},
                        "reason": f"{gap.reason} — 그날 빈 시간({hhmm_s}~{hhmm_e})에 맞춰 계획 에이전트가 골랐어요"})
        return out

    return slot


def _overlaps(a_start: str, a_end: str, b_start: Any, b_end: Any) -> bool:
    if not b_start:
        return False
    return a_start < str(b_end or b_start) and str(b_start) < a_end


def ask_owner(gap: Gap, draft: Mapping[str, Any]) -> Proposal:
    return Proposal(gap, "ask_customer", [{"question": gap.reason}], reason="고객만 아는 값이라 묻는다")


def run(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int, tour: Any = None, kakao: Any = None,
        dining: Any = None, plan_slot: Callable[[Gap, Mapping[str, Any]], list[dict[str, Any]]] | None = None,
        max_rounds: int = gaps_module.MAX_ROUNDS,
        on_progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    """먼저 채운 결과 `{revision, filled, questions, rounds}`. 바꿀 것이 없으면 판을 만들지 않고 기록만 남긴다.

    `on_progress(몸통)` `[2026-10-24 사용자 확정 — 진행 표시 ③ · ST4F-732]` 진행 알림 `progress{phase: prefill}` 의 몸통 `{done, total, current, step?}` —
      빈칸을 모은 직후 `done: 0`(빈칸이 없으면 `0/0` 하나) · 빈칸마다 담당에게 묻기 · 막힌 조회 다시 찾기 전에 `current` = 그 일정(일정이 아닌 빈칸은 null) ·
      채운 값을 판에 넣고 다시 검사하는 동안 `step: "recheck"` · 끝에 `done: total`. `total` 은 다시 검사가 새 빈칸을 내면 늘어난다. 알림이 던져도 채우기는 계속된다."""
    from . import autofix as autofix_module
    from . import pipeline

    _, found = pipeline.current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision)
    claims = pipeline._claims(conn, tenant_id, intake_id, revision)
    trip = {k: (v.get("value") if isinstance(v, dict) else v) for k, v in (pipeline._trip_fields(claims) or {}).items()}
    state: dict[str, Any] = {"revision": revision, "review": found}

    def plan() -> Mapping[str, Any]:
        return autofix_module.plan(conn, tenant_id=tenant_id, review=state["review"], kakao=kakao)

    team = autofix_owner(plan)
    if plan_slot is None:
        plan_slot = planner_slot(conn, tenant_id=tenant_id, tour=tour, review=lambda: state["review"],
                                 preferences=_preference_text(claims), party_size=_int(trip.get("party_size")))
    owners = {"dining_team": team, "activity_team": team, "lodging_team": team, "mobility": team, "planner": planner_owner(plan_slot),
              "ask_customer": ask_owner}

    def apply(draft: dict[str, Any], proposals: list[Proposal]) -> dict[str, Any]:
        edits: list[dict[str, Any]] = []
        seen: set[Any] = set()
        for p in proposals:
            change = (p.candidates[0] or {}).get("change")
            if change is not None and change.get("id") not in seen:
                seen.add(change.get("id"))
                # 고객이 쓴 시각은 유지한다. 원문에 없는 조식 끝만 검증한 추천으로 채운다.
                end_field = f"items[{change['index']}].ends_at"
                written_end = any(str(c.get("source_id")) == str(change["source_id"]) and c["field"] == end_field
                                  for c in claims)
                edits += [{"source_id": change["source_id"], "field": f"items[{change['index']}].{e['field']}", "value": e["value"]}
                          for e in change.get("edits") or [] if e.get("field") == "place"
                          or (p.gap.kind == "lodging_place" and not written_end and e.get("field") == "ends_at")]
        new = draft["revision"]
        if edits:
            new = pipeline.edit(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=new, edits=edits,
                                tour=tour, kakao=kakao, via="autofix", dining=dining)
        for p in proposals:                                   # 새 일정(계획 에이전트)은 한 번에 하나씩 — `edit` 의 새 일정 계약
            pick = p.candidates[0] if p.owner == "planner" else None
            if not pick or "place" not in pick:
                continue
            new = _add_item(conn, pipeline, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=new,
                            pick=pick, source_id=p.gap.where.get("source_id"), tour=tour, kakao=kakao, dining=dining) or new
        if new != draft["revision"]:
            _, state["review"] = pipeline.current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=new)
        state["revision"] = new
        return {**draft, "revision": new}

    def recheck(draft: dict[str, Any]) -> list[Gap]:
        return check_gaps(state["review"], trip=trip)

    first = gaps_module.collect(model_gaps(claims, found.get("items") or []), check_gaps(found, trip=trip))
    keys, asked = {g.key for g in first}, set()

    def note(item_id: Any = None, *, step: str | None = None, final: bool = False) -> None:
        if on_progress is None:
            return
        item = next((i for i in state["review"].get("items") or [] if item_id is not None and i.get("id") == item_id), None)
        try:
            on_progress({"done": len(keys) if final else len(asked), "total": len(keys),
                         "current": {"id": item["id"], "title": item.get("title")} if item is not None else None,
                         **({"step": step} if step else {})})
        except Exception:                                     # noqa: BLE001 — 알림 실패가 채우기를 막지 않는다
            pass

    def counted(owner: Callable[[Gap, Mapping[str, Any]], Proposal]) -> Callable[[Gap, Mapping[str, Any]], Proposal]:
        def ask(gap: Gap, draft: Mapping[str, Any]) -> Proposal:
            keys.add(gap.key)
            note(gap.where.get("item"))
            try:
                return owner(gap, draft)
            finally:
                asked.add(gap.key)
        return ask

    def applying(draft: dict[str, Any], proposals: list[Proposal]) -> dict[str, Any]:
        note(step="recheck")
        return apply(draft, proposals)

    note()

    def refind(item: Mapping[str, Any], query: str) -> bool:
        """막힌 조회를 같은 말로 한 번 더 — 고객이 이름을 고친 길(`pipeline.edit`)과 같다. 찾으면 새 판, 못 찾으면 그대로."""
        note(item.get("id"))
        try:
            new = pipeline.edit(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=state["revision"],
                                edits=[{"source_id": item["source_id"], "field": f"items[{item['index']}].place", "value": {"name": query}}],
                                tour=tour, kakao=kakao, via="autofix", dining=dining, learn_aliases=False)
        except (pipeline.IntakeRejected, pipeline.IntakeConflict) as exc:
            log.info("prefill refind kept item=%s code=%s", item.get("id"), getattr(exc, "code", None))
            return False
        state["revision"] = new
        _, state["review"] = pipeline.current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=new)
        return True

    first, refound, still_blocked = retry_blocked(first, claims=claims, items=found.get("items") or [], refind=refind)
    # 다른 장소를 채우면 전체 동선과 숙소 후보도 바뀐다. 같은 판의 실패를 반복하지 않고 바뀐 판에서만 다시 본다.
    draft, used, rounds = gaps_module.settle({"revision": state["revision"]}, first, {name: counted(owner) for name, owner in owners.items()},
                                           applying, recheck, max_rounds=max_rounds,
                                           retry_unfilled=lambda p: p.gap.kind == "lodging_place" and p.owner == "lodging_team")
    if keys:
        note(final=True)
    latest = {p.gap.key: p for p in used}
    filled = refound + [_filled_line(p) for p in latest.values() if p.owner != "ask_customer" and p.candidates and p.error is None]
    items_now = {i.get("id"): i for i in (state["review"].get("items") or [])}
    questions = [_question(p, items_now, still_blocked) for p in latest.values() if p.owner == "ask_customer"]
    kept = [{"kind": p.gap.kind, "item": p.gap.where.get("item"), "owner": p.owner, "reason": p.reason}
            for p in latest.values() if p.owner != "ask_customer" and not p.candidates]
    record = {"filled": [f for f in filled if f], "questions": _unique(questions), "kept": kept, "rounds": rounds,
              "proposals": [p.as_dict() for p in used]}
    _store(conn, tenant_id=tenant_id, intake_id=intake_id, revision=draft["revision"], record=record)
    return {"revision": draft["revision"], **record}


def blocked_query(claims: list[Mapping[str, Any]], item: Mapping[str, Any]) -> str | None:
    """이 일정의 장소 근거에 **막힌 조회**(`blocked` — 한도 · 시간 초과 · 연결 실패)가 남아 있으면 다시 찾을 말, 아니면 None.
    없는 곳이라서 못 찾은 줄은 다시 찾지 않는다(같은 답이 나온다)."""
    field = f"items[{item.get('index')}].place"
    row = next((c for c in reversed(claims) if c.get("field") == field and str(c.get("source_id")) == str(item.get("source_id"))), None)
    evidence = (row or {}).get("evidence") or {}
    if not isinstance(evidence, Mapping) or not evidence.get("blocked"):
        return None
    return str(item.get("title") or evidence.get("query") or "").strip() or None


def retry_blocked(gaps: list[Gap], *, claims: list[Mapping[str, Any]], items: list[Mapping[str, Any]],
                  refind: Callable[[Mapping[str, Any], str], bool]) -> tuple[list[Gap], list[dict[str, Any]], set[Any]]:
    """`[2026-10-19 사용자 결정]` 못 찾은 줄 중 **조회가 막혀서** 못 찾은 것은 고객에게 묻기 전에 **한 번** 다시 찾는다(횟수는 우리가 고른 값 —
    읽기 직후라 한도가 찼으면 대개 또 막힌다. 시간 초과 · 일시 실패를 건지는 몫이다).

    돌려주는 값: (남은 빈칸, 다시 찾아 채운 기록, 다시 찾아도 못 찾은 일정 id). 다시 찾아도 막힌 줄은 질문에 `blocked: true` 로 남는다."""
    by_id = {i.get("id"): i for i in items}
    left: list[Gap] = []
    filled: list[dict[str, Any]] = []
    still: set[Any] = set()
    for gap in gaps:
        item = by_id.get(gap.where.get("item")) if gap.kind == "place_not_found" else None
        query = blocked_query(claims, item) if item is not None else None
        if query is None:
            left.append(gap)
            continue
        if refind(item, query):
            filled.append({"item": item.get("id"), "title": query, "owner": "refind", "owner_label": "장소 다시 찾기",
                           "reason": "장소 조회가 막혀 못 찾았던 곳을 다시 찾아 채웠어요", "gap": gap.kind, "from": None, "to": None,
                           "new": False})
        else:
            still.add(item.get("id"))
            left.append(gap)
    return left, filled, still


def _question(p: Proposal, items: Mapping[Any, Mapping[str, Any]], blocked: set[Any]) -> dict[str, Any]:
    """질문 하나 — 다른 질문(첫날 · 숙소 이름 · 범위)과 같은 목록에 모은다. 못 찾은 줄은 그 일정을 가리키는 칸과 단추를 싣는다."""
    row = {"kind": p.gap.kind, "question": (p.candidates[0] or {}).get("question") or p.gap.reason, "quote": p.gap.quote}
    if p.gap.kind not in ("place_not_found", "lodging_place"):
        return row
    item_id = p.gap.where.get("item")
    item = items.get(item_id) or {}
    title = item.get("title") or p.gap.quote or "이름 없는 일정"
    was_blocked = item_id in blocked
    if p.gap.kind == "lodging_place":
        text = LODGING_PICK_QUESTION.format(title=title)
    else:
        text = (PLACE_NOT_FOUND_BLOCKED_QUESTION if was_blocked else PLACE_NOT_FOUND_QUESTION).format(title=title)
    return {**row, "question": text,
            "item": item_id, "source_id": item.get("source_id"), "index": item.get("index"), "mode": "change",
            "actions": list(PLACE_NOT_FOUND_ACTIONS), "blocked": was_blocked}


def _add_item(conn, pipeline, *, tenant_id, customer_id, intake_id, revision, pick, source_id, tour, kakao, dining) -> int | None:
    claims = pipeline.effective(pipeline._claims(conn, tenant_id, intake_id, revision))
    sid = source_id or next((str(c["source_id"]) for c in claims if c.get("source_id")), None)
    if sid is None:
        return None
    index = max((pipeline._item_no(c["field"]) for c in claims if str(c.get("source_id")) == sid and c["field"].startswith("items[")),
                default=-1) + 1
    edits = [{"source_id": sid, "field": f"items[{index}].{name}", "value": pick[name]}
             for name in ("title", "date", "starts_at", "ends_at", "kind", "place")]
    try:
        return pipeline.edit(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision, edits=edits,
                             tour=tour, kakao=kakao, via="autofix", dining=dining)
    except Exception:                                  # noqa: BLE001 — 하나를 못 넣어도 나머지는 그대로(지어내지 않는다)
        log.warning("prefill add item failed intake=%s", intake_id, exc_info=True)
        return None


def _filled_line(p: Proposal) -> dict[str, Any] | None:
    pick = p.candidates[0]
    change = pick.get("change") or {}
    return {"item": change.get("id") or p.gap.where.get("item"), "title": pick.get("title"), "owner": p.owner,
            "owner_label": OWNER_LABEL.get(p.owner, p.owner), "reason": pick.get("reason") or p.reason, "gap": p.gap.kind,
            "from": change.get("from"), "to": change.get("to"), "new": "place" in pick}


def _store(conn, *, tenant_id: str, intake_id: UUID, revision: int, record: dict[str, Any]) -> None:
    """값 줄 `reading.prefill` — 판에 붙는다(다음 판을 만들 때 그대로 옮겨진다). 같은 판에 다시 쓰면 앞 줄을 지운다."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM intake_claims WHERE tenant_id=%s AND intake_id=%s AND revision=%s AND field='reading.prefill'",
                    (tenant_id, intake_id, revision))
        cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, source_id, field, value_json, method, evidence, "
                    "needs_review, note, created_at) VALUES (%s,%s,%s,NULL,'reading.prefill',%s,'llm_agent',%s,false,%s, clock_timestamp())",
                    (intake_id, tenant_id, revision, json.dumps(record, ensure_ascii=False, default=str),
                     json.dumps({"source": "prefill"}), "먼저 채운 기록 — 무엇을 왜 채웠나 · 고객에게 물을 것"))


def _change_reason(change: Mapping[str, Any], gap: Gap) -> str:
    to = (change.get("to") or {})
    name = (to.get("place") or {}).get("name") or change.get("title")
    hours = "" if change.get("hours_known") else " · 운영시간은 확인 못 함"
    return f"{gap.reason} — 같은 지역 · 같은 종류에서 앞뒤 이동을 맞춰 보고 {name or '맞는 곳'}(으)로 채웠어요{hours}"


def _kept_reason(code: Any) -> str:
    return {"locked": "고정한 일정이라 그대로 두었어요", "booked": "예약한 일정이라 그대로 두었어요", "no_time": "시각이 없어 맞춰 보지 못했어요",
            "no_candidates": "맞는 후보가 없어 그대로 두었어요", "nothing_to_change": "바꿀 것이 없었어요"}.get(str(code), "맞는 안이 없어 그대로 두었어요")


def _unique(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # 같은 문장이라도 다른 일정을 가리키는 카드 질문(「호텔」 이틀)은 둘 다 남긴다 — 일정마다 그 카드가 묻는다
    out: list[dict[str, Any]] = []
    for row in rows:
        if (row["question"], row.get("item")) not in {(r["question"], r.get("item")) for r in out}:
            out.append(row)
    return out


def _item_for_quote(items: list[Mapping[str, Any]], source_id: str, quote: str) -> Mapping[str, Any] | None:
    for item in items:
        title = str(item.get("title") or "")
        if str(item.get("source_id")) == source_id and title and title in quote:
            return item
    return None


def _preference_text(claims: list[Mapping[str, Any]]) -> str:
    """계획 에이전트에게 넘기는 선호 — 이해 에이전트가 읽은 성향 · 조건의 **원문 인용**만(고객 원문 전체가 아니다)."""
    bits: list[str] = []
    for row in claims:
        value = row.get("value") if row.get("field") == "reading.agent" else None
        if isinstance(value, dict) and value.get("used"):
            bits += [p.get("quote") for p in value.get("preferences") or [] if p.get("quote")]
            bits += [c.get("quote") for c in value.get("conditions") or [] if c.get("quote")]
    return ". ".join(dict.fromkeys(bits))


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = ["autofix_owner", "blocked_query", "check_gaps", "model_gaps", "planner_owner", "retry_blocked", "run"]
