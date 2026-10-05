# -*- coding: utf-8 -*-
"""Case 버전의 **일정 적용기** — Team 이 낸 `itinerary.apply` 제안을 새 일정 버전으로 쓴다.

★v11 §4-C — 「먼저 고치고 알린다」는 **우리 DB 안의 일정 버전에만** 허락된다. 업체 예약은
  여기 오지 않는다(그건 승인 경로 · Booking Handoff).

★코어는 이 파일을 모른다. 조립(`composition.build_action_handlers`)이 넣고, 코어는
  `app/core/actions.py` 규격으로만 부른다. 적용 조건(승인 불요 · 위험 낮음 · 대조 통과 ·
  degraded 아님)은 코어가 먼저 본다 — wiki `actions/approval.md`.

★적용 순간에 **다시 확인한다.** Team 이 읽은 뒤로 시간이 흘렀다.
    - 이 고객의 여행인가          아니면 ActionRejected
    - 계산한 기준 버전 그대로인가  아니면 ActionConflict(재계산 없이 밀어 넣지 않는다, §6-C-7)
    - 바꾸는 항목이 지금 일정에 있나 · 새 항목의 장소가 이 테넌트에 실재하나
                                    아니면 ActionRejected(지어낸 장소를 쓰지 않는다)

★통지는 직접 넣지 않고 `AppliedAction.outbox` 로 돌려준다 — 코어가 Case 완료 전이와
  **같은 트랜잭션**에 싣는다. 버전당 하나(`{trip_id}:v{version}`, §6-C-6)는 시나리오
  버전의 `TripStore.enqueue_notice` 와 같은 키다.

★`[2026-09-25]` **감시·신고에서 온 변경은 판정 문을 지난다**(`pending.decide`, D-020) — 시나리오용 여행
  버전의 감시(`trip_watch`)·신고(`trip_desk`)와 같은 판정·같은 보류 제안·같은 알림이다.
  설문 15번 「먼저 물어봐줘」거나 「변경 안 할 일정」이 걸리면 **새 버전을 쓰지 않고** 제안을 열고
  묻는 알림을 돌려준다(`summary.status = "asked"`). 안전 사건은 원인(`causes`)의 종류로 가른다.
  ★고객이 **직접 고른 것**(다른 안으로 · 되돌리기 · 제안 고르기)은 지나지 않는다 — 그 자체가 답이다.

★`[2026-10-03 사용자 결정 — D-017 「전체 일정 재검증」]` **자동으로 바꾸기 전에 일정 전체를 다시 판정한다**(`check_itinerary` — 등록 때와 같은 판정기). 후보는 **항목 하나**만 점검해 고르므로,
  통과한 대체가 앞뒤 항목과 시간이 겹치거나 이동이 안 닿거나 예산 · 결제 조건을 깨는 것은 항목 점검이 못 본다. 바꾼 뒤 **새로 생긴** 위반(`(code, 항목)` 이 바꾸기 전에 없던 것)이 하나라도 있으면
  **적용하지 않고** `ActionRejected("itinerary re-check failed: …")` — 코어가 Case 를 `escalated`(`action_rejected`)로 닫고, 감시(`trip_watch_cases`)가 고객에게 「일정은 그대로 두었어요」를 알린다.
  ★바꾸기 전에 이미 있던 위반은 이 일의 탓이 아니라 막지 않는다. 고객이 고른 변경 · 되돌리기(`full_items`)는 이 문을 지나지 않는다 — 그 자체가 답이다.

★`[2026-10-03 사용자 지시]` **같은 여행의 문제 묶음**(`trip_watch_batch`) — 제안에 `batch` 가 있으면 한 번에 푼다: 바꿀 항목은 **판 하나 · 알림 하나**로 쓰고, 「묻는」 항목(변경 안 할 일정 · 먼저 물어봐 · 날씨만이라 바꿀까요)은
  **새 판을 기준으로** 보류 제안을 연다(같은 판을 기준으로 열면 이 판이 곧 낡아 `choose` 가 못 고르게 닫는다). 항목마다 판정(`decide`)은 **적용기가 한다** — Team 의 분류와 같은 함수 · 같은 입력이지만 권한은 이쪽에 있다.
  묻는 것은 묶지 않고 항목마다 알림이 따로 나간다(D-020). 바꿀 것이 없고 못 푼 것만 있으면 판 없이 「그대로 두었어요」 알림 하나(`guidance`)를 싣는다.
"""
from __future__ import annotations

import json
from typing import Any, Mapping
from uuid import UUID

from app.core.actions import ActionConflict, ActionRejected, AppliedAction
from app.core.transition import OutboxMessage

from app.domains.travel_ops.components.itinerary.itinerary import Item, StaleItinerary, TripStore, item_from_dict, item_to_dict
from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange, refresh_moves_around
from app.domains.travel_ops.components.itinerary.itinerary_checks import Violation, check_itinerary, parts_from_items
from app.domains.travel_ops.components.planning.pending import PendingStore, decide, options_for, proposal_notice

ACTION_TYPE = "itinerary.apply"
NOTICE_TOPIC = "trip.notice"
#: 고객이 직접 고른 변경 — 판정 문을 지나지 않는다(그 자체가 답이다)
CHOSEN_BY_CUSTOMER = frozenset({"customer_request", "rollback", "customer_choice"})
#: 전체 재판정이 막았을 때 `ActionRejected` 문구의 머리 — 감시가 이것으로 「일정 전체와 안 맞아서」를 가려 고객에게 알린다(`trip_watch_cases._after_run`)
RECHECK_FAILED = "itinerary re-check failed"


#: 일정 **전체**에 걸리는 위반 — 항목 하나가 아니라 합계로 정해져(예산) 항목 id 로 비교할 수 없다. 종류만으로 비교한다(바꾸기 전에도 있었으면 이 변경의 탓이 아니다)
_TRIP_LEVEL = frozenset({"over_budget"})


def _signature(violation: Violation, ids_by_seq: Mapping[int, Any]) -> tuple:
    if violation.code in _TRIP_LEVEL:
        return (violation.code,)
    return (violation.code, tuple(ids_by_seq.get(seq) for seq in violation.seq))


def introduced_violations(trip: Mapping[str, Any], current: list[Item], new_items: list[Item]) -> list[Violation]:
    """바꾼 일정에 **새로** 생긴 위반 — 바꾸기 전(`current`)에 **같은 항목(id)** 에 걸린 같은 종류의 위반이 있었으면 이 변경의 탓이 아니라 뺀다.

    ☆`[2026-10-03 적대 검토]` 전에는 `(종류, 항목 순번)` 으로 비교했다 — 대체 항목은 **순번을 물려받아**, 원래 곳이 그날 휴무였고 대체할 곳도 그날 쉬면 「원래 있던 위반」으로 보고 통과했다.
    이제 위반이 가리키는 항목의 **id** 로 비교한다 — 바뀐 항목은 새 id 라 그 항목에 걸린 위반은 전부 새 위반이고, 손대지 않은 항목끼리의 위반(같은 id)은 원래 있던 것이다."""
    constraints, party = dict(trip.get("constraints") or {}), trip.get("party_size")
    before_ids = {item.seq: item.item_id for item in current}
    after_ids = {item.seq: item.item_id for item in new_items}
    before = {_signature(v, before_ids)
              for v in check_itinerary(parts_from_items(current), constraints=constraints, party_size=party)}
    after = check_itinerary(parts_from_items(new_items), constraints=constraints, party_size=party)
    return [v for v in after if _signature(v, after_ids) not in before]


def _plain(value: Any) -> Any:
    """제안 인자·통지는 DB(jsonb)로 간다 — 시각·UUID 를 문자열로 고정한다."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def change_arguments(*, trip_id: UUID | str, base_version: int, change: ItineraryChange) -> dict[str, Any]:
    """계산 결과(`ItineraryChange`)를 제안 인자로. Team 이 부른다."""
    arguments: dict[str, Any] = {
        "trip_id": str(trip_id), "base_version": int(base_version),
        "reason": change.reason, "causes": change.causes, "notice": change.notice,
        "summary": change.summary,
    }
    if change.full_items is not None:
        arguments["full_items"] = [item_to_dict(item) for item in change.full_items]
    else:
        arguments["replacements"] = [{"item_id": str(old), "item": item_to_dict(new)}
                                     for old, new in change.replacements.items()]
    return _plain(arguments)


def consent_arguments(*, trip_id: UUID | str, base_version: int, item_id: UUID | str,
                      causes: list[dict[str, Any]], indoor_unknown: bool = True) -> dict[str, Any]:
    """★`[2026-09-29]` 「바꿀까요?」만 묻는 제안 인자 — 대체안이 없다(아직 계산하지 않았다). Team 이 부른다.
    `indoor_unknown` — 실내·야외를 몰라서 묻는가(알림 문구가 갈린다). 아는 곳이면 「제안이 기본」이라 묻는 것이다."""
    return _plain({"trip_id": str(trip_id), "base_version": int(base_version), "reason": "indoor_unknown",
                   "causes": causes, "consent": {"item_id": str(item_id), "indoor_unknown": bool(indoor_unknown)}})


class ItineraryApply:
    action_type = ACTION_TYPE
    auto_apply = True

    def subject(self, arguments: Mapping[str, Any]) -> str:
        """★멱등 키의 대상 — 서버가 인자에서 꺼낸다(v11 §4-E). 같은 여행·같은 기준 버전은 한 번."""
        trip_id, base = arguments.get("trip_id"), arguments.get("base_version")
        if not trip_id or base is None:
            raise ActionRejected("itinerary.apply needs trip_id and base_version")
        try:
            return f"{UUID(str(trip_id))}:v{int(base)}"
        except (TypeError, ValueError) as exc:
            raise ActionRejected(f"itinerary.apply target is malformed: {exc}") from exc

    def apply(self, conn: Any, *, tenant_id: str, customer_id: UUID, case_id: UUID,
              arguments: Mapping[str, Any]) -> AppliedAction:
        store = TripStore(tenant_id)
        trip_id = UUID(str(arguments["trip_id"]))
        base = int(arguments["base_version"])
        try:
            trip, current = store.latest(conn, trip_id)
        except KeyError as exc:
            raise ActionRejected("trip not found") from exc
        if str(trip["customer_id"]) != str(customer_id):
            raise ActionRejected("trip not found")        # ★남의 여행 — 있는지도 말하지 않는다
        if trip["version"] != base:
            raise ActionConflict(f"trip {trip_id} moved from v{base} to v{trip['version']}")
        if arguments.get("consent"):
            return _ask_consent(conn, tenant_id=tenant_id, trip=trip, trip_id=trip_id, base=base,
                                current=current, arguments=arguments)
        if arguments.get("batch") is not None:
            return _apply_batch(conn, store=store, tenant_id=tenant_id, trip=trip, trip_id=trip_id, base=base,
                                current=current, case_id=case_id, arguments=arguments)

        try:
            if arguments.get("full_items") is not None:
                new_items = [item_from_dict(entry) for entry in arguments["full_items"]]
            else:
                replacements = {UUID(str(entry["item_id"])): item_from_dict(entry["item"])
                                for entry in arguments.get("replacements") or []}
                if not replacements:
                    raise ActionRejected("itinerary.apply changes nothing")
                present = {item.item_id for item in current}
                missing = sorted(str(old) for old in replacements if old not in present)
                if missing:
                    raise ActionRejected(f"items not in the current itinerary: {missing}")
                new_items = [replacements.get(item.item_id, item) for item in current]
                # ☆`[2026-09-29 이동 계산기 문제목록 #44]` 여행 버전(ItineraryChange.new_items)과 같게 — 장소가 멀리 바뀐
                #   항목의 바로 앞뒤 이동을 새 장소 기준으로 다시 만든다(두 경로의 결과가 갈리지 않게)
                from app.domains.travel_ops.components.itinerary.itinerary_changes import refresh_moves_around
                new_items = refresh_moves_around(current, new_items, replacements)
        except (KeyError, TypeError, ValueError) as exc:
            raise ActionRejected(f"itinerary.apply arguments are malformed: {exc}") from exc

        known_places = {str(place["place_id"]) for place in store.places(conn, trip_id)}
        unknown = sorted({str(item.place_id) for item in new_items
                          if item.place_id is not None and str(item.place_id) not in known_places})
        if unknown:
            raise ActionRejected(f"places not in this tenant: {unknown}")

        if arguments.get("full_items") is None and str(arguments["reason"]) not in CHOSEN_BY_CUSTOMER:
            asked = _ask_instead(conn, tenant_id=tenant_id, trip=trip, trip_id=trip_id, base=base,
                                 current=current, replacements=replacements, arguments=arguments)
            if asked is not None:
                return asked

        if arguments.get("full_items") is None and str(arguments["reason"]) not in CHOSEN_BY_CUSTOMER:
            # ★자동 변경은 쓰기 전에 **일정 전체**를 다시 판정한다 — 항목 하나를 점검해 고른 대체가 앞뒤와 안 맞는 것은 항목 점검이 못 본다(머리말)
            introduced = introduced_violations(trip, current, new_items)
            if introduced:
                raise ActionRejected(f"{RECHECK_FAILED}: " + " / ".join(v.reason for v in introduced))
        try:
            version = store.append_version(conn, trip_id=trip_id, base_version=base, items=new_items,
                                           reason=str(arguments["reason"]),
                                           causes=list(arguments.get("causes") or []), case_id=case_id)
        except StaleItinerary as exc:
            raise ActionConflict(str(exc)) from exc
        return AppliedAction(
            result_ref=f"trip:{trip_id}:v{version}",
            summary=_plain({"trip_id": str(trip_id), "version": version,
                            "reason": arguments["reason"], **dict(arguments.get("summary") or {})}),
            outbox=[_version_notice(tenant_id=tenant_id, trip=trip, trip_id=trip_id, version=version, base=base,
                                    arguments=arguments)])


def _ask_instead(conn: Any, *, tenant_id: str, trip: Mapping[str, Any], trip_id: UUID, base: int,
                 current: list[Item], replacements: Mapping[UUID, Item],
                 arguments: Mapping[str, Any]) -> AppliedAction | None:
    """바꿀 항목 중 하나라도 판정이 「바꾸지 말라」면 **바꾸지 않고 묻는다.** None 이면 바꿔도 된다."""
    from app.domains.travel_ops.components.itinerary.plan_link import plan_url

    causes = list(arguments.get("causes") or [])
    report = {"disruptions": causes}           # ★안전 사건 여부는 원인의 종류(`category`)로 가른다
    pending = PendingStore(tenant_id)
    for item_id, best in replacements.items():
        item = next(i for i in current if i.item_id == item_id)
        decision = decide(constraints=trip.get("constraints"), item=item, report=report)
        if decision.action == "apply":
            continue
        summary, outbox = _open_ask(conn, tenant_id=tenant_id, trip=trip, trip_id=trip_id, base=base, item=item,
                                    best=best, decision=decision, causes=causes)
        return AppliedAction(result_ref=f"trip:{trip_id}:proposal:{summary['proposal_id']}", summary=summary,
                             outbox=outbox)
    return None


def _open_ask(conn: Any, *, tenant_id: str, trip: Mapping[str, Any], trip_id: UUID, base: int, item: Item, best: Item,
              decision: Any, causes: list[dict[str, Any]]) -> tuple[dict[str, Any], list[OutboxMessage]]:
    """「바꾸지 말라」는 판정 — 보류 제안을 열고 묻는 알림을 싣는다. `base` 는 **그 제안이 기준으로 삼는 판**. 이미 물었으면 알림은 안 싣는다."""
    from app.domains.travel_ops.components.itinerary.plan_link import plan_url

    options = options_for(best)
    pending = PendingStore(tenant_id)
    proposal_id = pending.open(conn, trip_id=trip_id, item=item, base_version=base,
                               decision=decision, causes=causes, options=options)
    already = proposal_id is None
    if already:                               # 이미 물었다 — 다시 알리지 않는다
        proposal_id = next(row["proposal_id"] for row in pending.list(conn, trip_id)
                           if row["item_id"] == item.item_id and row["base_version"] == base)
    summary = _plain({"status": "asked", "already": already, "trip_id": str(trip_id),
                      "version": base, "proposal_id": str(proposal_id), "item": item.title,
                      "reason": decision.reason, "protected_by": decision.protected_by,
                      "safety": decision.safety})
    outbox = [] if already else [OutboxMessage(
        topic=NOTICE_TOPIC, dedupe_key=f"{trip_id}:proposal:{proposal_id}",
        payload=_plain({"locale": trip.get("locale"), "plan_url": plan_url(tenant_id, trip_id),
                        **proposal_notice(item=item, decision=decision, causes=causes,
                                          options=options, proposal_id=proposal_id)}))]
    return summary, outbox


def _version_notice(*, tenant_id: str, trip: Mapping[str, Any], trip_id: UUID, version: int, base: int,
                    arguments: Mapping[str, Any]) -> OutboxMessage:
    """새 판의 알림 하나. ★`[2026-09-22]` **링크를 싣는다** — 상태의 정본은 링크다(v11 §6-A). 시나리오용 여행 버전은 `TripStore.enqueue_notice` 가 붙여 주지만
    Case 버전은 코어가 바깥함에 **직접** 쓰기 때문에 그 자리를 지나지 않아 링크 없이 나갔다 — 화면에서 통지를 열어 보고 찾았다."""
    from app.domains.travel_ops.components.planning.pending import rollback_offer
    from app.domains.travel_ops.components.itinerary.plan_link import plan_url

    # ★`[2026-09-29]` 우리가 **자동으로** 바꾼 것(고객이 고른 것이 아닌)에는 되돌리기를 싣는다 — 화면이 버튼을 띄운다
    offer = ({} if str(arguments["reason"]) in CHOSEN_BY_CUSTOMER
             else {"rollback": rollback_offer(version=version, previous=base)})
    payload = _plain({"locale": trip.get("locale"), "plan_url": plan_url(tenant_id, trip_id),
                      **dict(arguments.get("notice") or {}), "version": version, **offer})
    return OutboxMessage(topic=NOTICE_TOPIC, payload=payload, dedupe_key=f"{trip_id}:v{version}")


def _apply_batch(conn: Any, *, store: TripStore, tenant_id: str, trip: Mapping[str, Any], trip_id: UUID, base: int,
                 current: list[Item], case_id: UUID, arguments: Mapping[str, Any]) -> AppliedAction:
    """같은 여행의 문제 묶음 — 바꿀 것은 판 하나 · 알림 하나, 묻는 것은 새 판 기준으로 항목마다 따로(머리말). 한 트랜잭션이다 — 중간에 터지면 아무것도 안 남는다."""
    from app.domains.travel_ops.components.itinerary.plan_link import plan_url
    from app.domains.travel_ops.components.watch.trip_watch_batch import guidance_key

    batch = dict(arguments["batch"])
    causes_of = {str(k): list(v) for k, v in (batch.get("causes") or {}).items()}
    consents = list(batch.get("consents") or [])
    try:
        replacements = {UUID(str(entry["item_id"])): item_from_dict(entry["item"])
                        for entry in arguments.get("replacements") or []}
    except (KeyError, TypeError, ValueError) as exc:
        raise ActionRejected(f"itinerary.apply arguments are malformed: {exc}") from exc
    if not replacements and not consents:
        raise ActionRejected("itinerary.apply changes nothing")
    by_id = {item.item_id: item for item in current}
    missing = sorted(str(old) for old in replacements if old not in by_id)
    if missing:
        raise ActionRejected(f"items not in the current itinerary: {missing}")

    # 판정은 적용기가 한다 — 「바꾸지 말라」면 묻는 쪽으로
    to_apply: dict[UUID, Item] = {}
    to_ask: list[tuple[Item, Item, Any, list[dict[str, Any]]]] = []
    for item_id, best in replacements.items():
        item = by_id[item_id]
        causes = causes_of.get(str(item_id)) or list(arguments.get("causes") or [])
        decision = decide(constraints=trip.get("constraints"), item=item, report={"disruptions": causes})
        if decision.action == "apply":
            to_apply[item_id] = best
        else:
            to_ask.append((item, best, decision, causes))

    version: int | None = None
    if to_apply:
        new_items = refresh_moves_around(current, [to_apply.get(i.item_id, i) for i in current], to_apply)
        known_places = {str(place["place_id"]) for place in store.places(conn, trip_id)}
        unknown = sorted({str(i.place_id) for i in new_items if i.place_id is not None and str(i.place_id) not in known_places})
        if unknown:
            raise ActionRejected(f"places not in this tenant: {unknown}")
        introduced = introduced_violations(trip, current, new_items)       # 마지막 안전망 — Team 이 이미 한 번 봤다
        if introduced:
            raise ActionRejected(f"{RECHECK_FAILED}: " + " / ".join(v.reason for v in introduced))
        try:
            version = store.append_version(conn, trip_id=trip_id, base_version=base, items=new_items,
                                           reason=str(arguments["reason"]), causes=list(arguments.get("causes") or []),
                                           case_id=case_id)
        except StaleItinerary as exc:
            raise ActionConflict(str(exc)) from exc

    outbox: list[OutboxMessage] = []
    if version is not None:
        outbox.append(_version_notice(tenant_id=tenant_id, trip=trip, trip_id=trip_id, version=version, base=base,
                                      arguments=arguments))
    ask_base = version if version is not None else base                     # ★묻는 제안은 **새 판**이 기준이다
    asked: list[dict[str, Any]] = []
    for item, best, decision, causes in to_ask:
        summary, messages = _open_ask(conn, tenant_id=tenant_id, trip=trip, trip_id=trip_id, base=ask_base, item=item,
                                      best=best, decision=decision, causes=causes)
        asked.append(summary)
        outbox += messages
    for entry in consents:
        item = by_id.get(UUID(str(entry["item_id"])))
        if item is None:
            raise ActionRejected(f"consent item not in the current itinerary: {entry['item_id']}")
        summary, messages = _open_consent(conn, tenant_id=tenant_id, trip=trip, trip_id=trip_id, base=ask_base, item=item,
                                          causes=list(entry.get("causes") or []),
                                          indoor_unknown=bool(entry.get("indoor_unknown", True)))
        asked.append(summary)
        outbox += messages
    guidance = arguments.get("guidance")
    if version is None and guidance:
        outbox.append(OutboxMessage(
            topic=NOTICE_TOPIC, dedupe_key=f"{trip_id}:guidance:{guidance_key(guidance)}",
            payload=_plain({"locale": trip.get("locale"), "plan_url": plan_url(tenant_id, trip_id), **dict(guidance)})))
    if not outbox and not asked:
        raise ActionRejected("itinerary.apply changes nothing")
    result_ref = (f"trip:{trip_id}:v{version}" if version is not None
                  else f"trip:{trip_id}:proposal:{asked[0]['proposal_id']}" if asked else f"trip:{trip_id}:guidance")
    return AppliedAction(
        result_ref=result_ref,
        summary=_plain({"trip_id": str(trip_id), "version": version if version is not None else base,
                        "reason": arguments["reason"], **dict(arguments.get("summary") or {}),
                        # ★`retry` — 다시 열 항목의 id. 감시가 이 Case 의 `applied_actions[].summary.batch.retry` 를 읽어 그 항목의 덮음을 푼다(`trip_watch_cases._attempt`)
                        "batch": {"applied": [i.title for i in (by_id[k] for k in to_apply)], "asked": asked,
                                  "retry": [str(x) for x in (batch.get("retry") or [])]}}),
        outbox=outbox)


def _ask_consent(conn: Any, *, tenant_id: str, trip: Mapping[str, Any], trip_id: UUID, base: int,
                 current: list[Item], arguments: Mapping[str, Any]) -> AppliedAction:
    """「바꿀까요?」 보류 제안을 열고 묻는 알림을 바깥함에 싣는다. **일정은 안 바꾼다.**"""
    from app.domains.travel_ops.components.planning.pending import CONSENT_REASON, Decision, consent_notice
    from app.domains.travel_ops.components.itinerary.plan_link import plan_url

    causes = list(arguments.get("causes") or [])
    wanted = str((arguments.get("consent") or {}).get("item_id"))
    item = next((i for i in current if str(i.item_id) == wanted), None)
    if item is None:
        raise ActionRejected(f"consent item not in the current itinerary: {wanted}")
    summary, outbox = _open_consent(conn, tenant_id=tenant_id, trip=trip, trip_id=trip_id, base=base, item=item,
                                    causes=causes,
                                    indoor_unknown=bool((arguments.get("consent") or {}).get("indoor_unknown", True)))
    return AppliedAction(result_ref=f"trip:{trip_id}:proposal:{summary['proposal_id']}", summary=summary, outbox=outbox)


def _open_consent(conn: Any, *, tenant_id: str, trip: Mapping[str, Any], trip_id: UUID, base: int, item: Item,
                  causes: list[dict[str, Any]], indoor_unknown: bool) -> tuple[dict[str, Any], list[OutboxMessage]]:
    """「바꿀까요?」 보류 제안 하나를 열고 묻는 알림을 싣는다(안 없이). 이미 물었으면 알림은 안 싣는다."""
    from app.domains.travel_ops.components.planning.pending import CONSENT_REASON, Decision, consent_notice
    from app.domains.travel_ops.components.itinerary.plan_link import plan_url

    pending = PendingStore(tenant_id)
    proposal_id = pending.open(conn, trip_id=trip_id, item=item, base_version=base,
                               decision=Decision("ask", CONSENT_REASON, None, False), causes=causes, options=[])
    already = proposal_id is None
    if already:                                   # 이미 물었다 — 다시 알리지 않는다
        proposal_id = next(row["proposal_id"] for row in pending.list(conn, trip_id)
                           if row["item_id"] == item.item_id and row["base_version"] == base)
    summary = _plain({"status": "asked", "already": already, "trip_id": str(trip_id), "version": base,
                      "proposal_id": str(proposal_id), "item": item.title, "reason": CONSENT_REASON,
                      "protected_by": None, "safety": False})
    outbox = [] if already else [OutboxMessage(
        topic=NOTICE_TOPIC, dedupe_key=f"{trip_id}:proposal:{proposal_id}",
        payload=_plain({"locale": trip.get("locale"), "plan_url": plan_url(tenant_id, trip_id),
                        **consent_notice(item=item, causes=causes, proposal_id=proposal_id,
                                         indoor_unknown=indoor_unknown)}))]
    return summary, outbox


ACTION_HANDLERS = (ItineraryApply(),)

__all__ = ["ACTION_HANDLERS", "ACTION_TYPE", "ItineraryApply", "change_arguments", "consent_arguments"]
