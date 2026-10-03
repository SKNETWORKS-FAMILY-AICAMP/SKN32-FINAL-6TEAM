# -*- coding: utf-8 -*-
"""감시가 대안을 못 찾았을 때 — **조건을 풀어 비슷한 안**을 찾아 고객에게 묻는다. `[2026-10-03 사용자 지적 — multi-agent flow 세션 전달]`

사용자 말: 「변경안 못 찾으면 탈락이고 그렇게 고객에게 알리지만, 그래도 최대한 유사한 대안 찾아서 고객에게 제공하는 걸로 논의되어 있지 않았어?」

☆왜: 조건을 풀어 되는 안을 찾는 계산(`itinerary_changes.relaxed_options` — 시각 늦추기 · 다음 일정 근처 · 반경 넓히기, 셋까지)은 **고객이 「다른 곳으로」를 요청한 길**(`plan_fresh_alternate`)에서만 불렀다.
  감시 길(식사 · 활동 · 묶음)은 부르지 않아서, 같은 조건으로 대안이 0곳이면(`no_alternate`) 또는 찾았는데 일정 전체 재판정에 다 걸리면(`recheck_failed`) 곧바로
  「일정은 그대로 두었어요 + 원인」 알림으로 끝났다 — 고객이 할 수 있는 것이 없었다.

★이제: 그런 때에도 조건을 푼 안을 계산해 **「그대로 두었어요 + 대신 이런 곳이 있어요(고르시면 바꿀게요)」** 로 묻는다(보류 제안, 이유 `relaxed` — 고객 요청 길과 같은 모양이라 고르기 · 무응답 만료 · 알림이 그대로다).
  ①**자동 적용하지 않는다** — 고객이 원한 조건(시각 · 곳 · 거리)을 바꾸는 안이라 묻는다. 답이 없으면 원래 일정 그대로(끝난 일정의 제안은 감시가 닫는다)
  ②묻는 안도 **고르면 그대로 적용될 안만** 싣는다 — 고를 때와 같은 계산(`plan_swap`)으로 시뮬레이션하고, **일정 전체 재판정**(`introduced_violations`)과 **밀도 판단**(`density_regressions`)을 통과한 안만(겹치게 · 빡빡하게 만드는 안을 고르게 두지 않는다)
  ③활동 · 식사 모두 같은 원인을 **다시 점검**한다(`check` — 재난 · 통제가 걸린 곳을 「비슷한 안」으로 권하지 않는다). 날씨 원인이면 활동은 실내만(`causes` 를 계산에 넘긴다)
  ④한 곳도 없으면 지금처럼 「일정은 그대로 두었어요」(`None` 을 돌려주면 부르는 쪽이 옛 알림을 낸다) ⑤이미 같은 항목 · 같은 판에 제안이 있으면 새로 안 낸다(`already`)
★알려진 한계: 식당의 **요리 분류를 넓히는** 안(아침엔 카페 · 베이커리)은 아직 없다 — 요식 원장의 분류와 끼니를 엮는 자료가 정리되면 더한다. 활동은 후보를 분류로 거르지 않고(순위에만 쓴다) 어차피 모든 활동 분류를 보므로 따로 넓힐 단계가 없다.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core import settings as settings_module

from .density import density_regressions
from .itinerary import Item
from .itinerary_actions import introduced_violations
from .itinerary_changes import NoChange, other_sites, plan_swap, relaxed_options, unused_places
from .itinerary_checks import parts_from_items
from .pending import Decision, PendingStore, _cause_text, _with_alternates, is_safety

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
REASON = "relaxed"


def enabled() -> bool:
    """`travel.watch.relaxed_enabled` — 끄면 감시는 전처럼 곧바로 「일정은 그대로 두었어요」로 끝난다."""
    return bool(settings_module.get_guardrails().get("travel.watch.relaxed_enabled"))   # ★호출 때 읽는다 — 시험이 바꿔 끼운 값을 따른다


def default_ledger(connect: Callable[[], Any], tenant_id: str) -> Any:
    """식사 후보를 요식 원장에서 — 감시 · 신고 창구가 쓰는 것과 같다(`trip_desk.TripDesk._ledger`)."""
    from .dining.ledger import DbLedgerView
    from .replan import ORDER_MARGIN_MIN

    return DbLedgerView(connect, tenant_id, ORDER_MARGIN_MIN)


def verified_options(*, trip: dict[str, Any], items: list[Item], places: list[dict[str, Any]], current: Item,
                     options: list[dict[str, Any]], check: Callable[..., dict[str, Any]] | None) -> list[dict[str, Any]]:
    """묻는 안 가운데 **고르면 그대로 적용될 안**만 — 고를 때(`pending.choose`)와 같은 계산으로 미리 해 본다.

    통과 조건: ①`plan_swap` 이 받는다(뒤 이동을 밀고도 다음 장소 일정에 닿는다 · 활동이면 그 시각에 같은 점검을 다시 통과) ②바꾼 뒤 **새로** 생기는 구조 위반이 없다(`introduced_violations`)
    ③하루 밀도를 나쁘게 만들지 않는다(`density_regressions` — 밀도 목표가 있는 여행만). 순위는 계산 순서 그대로 다시 매긴다."""
    by_id = {str(p["place_id"]): p for p in places}
    ranked = [{**option, "rank": n} for n, option in enumerate(options, start=1)]
    probe = [i if i.item_id != current.item_id else _with_alternates(i, ranked) for i in items]
    before, constraints = parts_from_items(items), dict(trip.get("constraints") or {})
    kept: list[dict[str, Any]] = []
    for option in ranked:
        plan = plan_swap(trip_version=trip["version"], base_version=trip["version"], items=probe, places_by_id=by_id,
                         item_id=current.item_id, choice=option["key"], message=None, request_id=None, check=check)
        if isinstance(plan, NoChange):
            continue
        # 식사도 같은 원인을 **다시 점검**한다 — `plan_swap` 은 활동만 다시 본다. 감시가 식사 대체를 고를 때도 후보마다 같은 점검을 지났다(`plan_dining_disrupted`).
        #   재난 · 통제가 걸린 동네의 식당을 「비슷한 안」으로 내밀지 않는다. 점검이 통과(`clear`)가 아니면(모름 · 치명 포함) 싣지 않는다
        if check is not None and current.kind == "dining":
            spot = by_id.get(str(option.get("place_id") or ""))
            if spot is not None:
                start = datetime.fromisoformat(option["starts_at"]) if option.get("starts_at") else current.starts_at
                if (check(place=spot, starts_at=start) or {}).get("verdict") != "clear":
                    continue
        after = plan.new_items(probe)
        if introduced_violations(trip, items, after) or density_regressions(constraints, before, parts_from_items(after)):
            continue
        kept.append(option)
    return [{**option, "rank": n} for n, option in enumerate(kept, start=1)]


def relaxed_text(*, item: Item, causes: list[dict[str, Any]], options: list[dict[str, Any]], recheck_failed: bool) -> str:
    """고객에게 보낼 문장 — 원인에 있는 말만(`_cause_text`), 안마다 무엇을 풀었는지(`note`). ★「일정은 그대로 두었어요」와 「답이 없으면 그대로」를 반드시 적는다."""
    head = "⚠️ 안전 알림 — " if is_safety({"disruptions": causes}) else ""
    problem = "바꿀 곳을 찾았지만 일정 전체와 맞지 않았어요" if recheck_failed else "같은 조건으로는 대신 갈 곳을 찾지 못했어요"
    listed = " · ".join(f"{o['rank']}) " + " ".join(part for part in (o.get("note"), o.get("option_label") or o["name"]) if part)
                        + (f"(도보 {o['walk_min']}분)" if o.get("walk_min") else "") for o in options)
    return (f"{head}{item.title} — {_cause_text(causes)}. {problem}. 그래서 **일정은 그대로 두었어요.** "
            f"조건을 조금 풀면 이런 곳이 있어요 — {listed}. 고르시면 바꿀게요. 답이 없으면 지금 일정을 그대로 둡니다.")


def offer_relaxed(conn, *, store: Any, trip_id: UUID, item_id: UUID, causes: list[dict[str, Any]],
                  check: Callable[..., dict[str, Any]] | None = None, ledger: Any | None = None,
                  recheck_failed: bool = False, now: datetime | None = None) -> dict[str, Any] | None:
    """조건을 푼 안을 **보류 제안**으로 묻는다(부르는 쪽이 `conn` 의 트랜잭션을 연다).

    돌려주는 것: `None` — 풀어서도 되는 안이 없다(끄면 · 일정이 바뀌었으면 · 식사 · 활동이 아니면 포함) → 부르는 쪽이 옛 「일정은 그대로 두었어요」 알림을 낸다.
    `{"status": "asked", "already": bool, "proposal_id", "options", "text", "safety"}` — 제안을 열었다(`already` 면 같은 항목 · 같은 판에 이미 있어 알림을 다시 안 냈다)."""
    if not enabled():
        return None
    trip, items = store.latest(conn, trip_id)
    current = next((i for i in items if i.item_id == item_id), None)
    if current is None or current.place is None or current.kind not in ("dining", "activity"):
        return None
    now = now or datetime.now(KST)
    if current.kind == "activity":
        # 활동은 관광공사 목록(DB)에서 반경을 넓혀 후보를 더한다 — 고객 요청 길(`TripDesk._widen_activities`)과 같다. 바깥을 부르지 않는다
        from .catalog_pool import widen_activity_pool
        from .itinerary_changes import RELAX_WIDE_M

        known = {str(p.get("name")) for p in store.places(conn, trip_id)}
        widen_activity_pool(conn, tenant_id=store.tenant_id, trip_id=trip_id, place=current.place, known_names=known,
                            radius_m=RELAX_WIDE_M, now=now)
    all_places = store.places(conn, trip_id)
    candidates = unused_places(all_places, items, current)             # 같은 여행에 이미 있는 곳은 후보가 아니다
    if current.kind == "activity":
        candidates = other_sites(candidates, current.place, items)     # 같은 곳(경복궁 ↔ 건청궁)도 아니다
    options = relaxed_options(trip=trip, items=items, places=candidates, current=current, ledger=ledger, causes=causes)
    options = verified_options(trip=trip, items=items, places=all_places, current=current, options=options, check=check)
    if not options:
        return None
    text = relaxed_text(item=current, causes=causes, options=options, recheck_failed=recheck_failed)
    safety = is_safety({"disruptions": causes})
    proposal_id = PendingStore(store.tenant_id).open(conn, trip_id=trip_id, item=current, base_version=trip["version"],
                                                     decision=Decision("ask", REASON, None, safety), causes=causes, options=options)
    if proposal_id is None:
        return {"status": "asked", "already": True, "text": text, "safety": safety, "options": options}
    store.enqueue_message(conn, trip_id=trip_id, key=f"proposal:{proposal_id}", payload={
        "type": "safety_alert" if safety else "proposal_request", "text": text, "language": "ko", "causes": causes,
        "proposal_id": str(proposal_id), "item_id": str(item_id), "reason": REASON, "protected_by": None,
        "options": [{"key": o["key"], "rank": o["rank"], "name": o.get("option_label") or o["name"],
                     "starts_at": o.get("starts_at"), "note": o.get("note")} for o in options],
        "replay": False})
    return {"status": "asked", "already": False, "proposal_id": str(proposal_id), "text": text, "safety": safety, "options": options}


def try_offer(connect: Callable[[], Any], *, store: Any, trip_id: UUID, item_id: UUID, causes: list[dict[str, Any]],
              check: Callable[..., dict[str, Any]] | None = None, recheck_failed: bool = False) -> dict[str, Any] | None:
    """`offer_relaxed` 를 **자기 트랜잭션**으로 — 감시 반복이 쓴다. ★어떤 실패든 `None`(로그만) — 비슷한 안을 못 찾는 것이 옛 알림까지 막으면 안 된다."""
    try:
        with connect() as conn, conn.transaction():
            return offer_relaxed(conn, store=store, trip_id=trip_id, item_id=item_id, causes=causes, check=check,
                                 ledger=default_ledger(connect, store.tenant_id), recheck_failed=recheck_failed)
    except Exception:                                  # noqa: BLE001
        logger.exception("watch relaxed offer failed trip=%s item=%s", trip_id, item_id)
        return None


__all__ = ["REASON", "default_ledger", "enabled", "offer_relaxed", "relaxed_text", "try_offer", "verified_options"]
