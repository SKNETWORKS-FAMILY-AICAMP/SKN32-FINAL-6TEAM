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
"""
from __future__ import annotations

import json
from typing import Any, Mapping
from uuid import UUID

from app.core.actions import ActionConflict, ActionRejected, AppliedAction
from app.core.transition import OutboxMessage

from .itinerary import StaleItinerary, TripStore, item_from_dict, item_to_dict
from .itinerary_changes import ItineraryChange

ACTION_TYPE = "itinerary.apply"
NOTICE_TOPIC = "trip.notice"


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
        except (KeyError, TypeError, ValueError) as exc:
            raise ActionRejected(f"itinerary.apply arguments are malformed: {exc}") from exc

        known_places = {str(place["place_id"]) for place in store.places(conn)}
        unknown = sorted({str(item.place_id) for item in new_items
                          if item.place_id is not None and str(item.place_id) not in known_places})
        if unknown:
            raise ActionRejected(f"places not in this tenant: {unknown}")

        try:
            version = store.append_version(conn, trip_id=trip_id, base_version=base, items=new_items,
                                           reason=str(arguments["reason"]),
                                           causes=list(arguments.get("causes") or []), case_id=case_id)
        except StaleItinerary as exc:
            raise ActionConflict(str(exc)) from exc
        payload = _plain({"locale": trip.get("locale"), **dict(arguments.get("notice") or {}),
                          "version": version})
        return AppliedAction(
            result_ref=f"trip:{trip_id}:v{version}",
            summary=_plain({"trip_id": str(trip_id), "version": version,
                            "reason": arguments["reason"], **dict(arguments.get("summary") or {})}),
            outbox=[OutboxMessage(topic=NOTICE_TOPIC, payload=payload,
                                  dedupe_key=f"{trip_id}:v{version}")])


ACTION_HANDLERS = (ItineraryApply(),)

__all__ = ["ACTION_HANDLERS", "ACTION_TYPE", "ItineraryApply", "change_arguments"]
