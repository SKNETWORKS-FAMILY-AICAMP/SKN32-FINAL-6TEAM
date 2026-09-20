# -*- coding: utf-8 -*-
"""Case 가 가리키는 여행을 **서버가 확인한다** — `subject_ref` 의 여행판 확인기.

★`[결정 2026-09-17]` wiki `external/rest-endpoints.md` 「subject_ref」.

    kind     "trip" 만 받는다
    id       trip_id — 이 테넌트·이 고객의 여행이 아니면 SubjectNotFound(404)
    part_id  일정 항목 — 이 여행의 **어느 버전에든** 있던 항목이어야 한다
             (고객이 본 뒤 바뀌었을 수 있다 — 낡았는지는 적용 순간 기준 버전이 가린다)

★라우팅 힌트 — **분류가 대상 접두를 못 붙였을 때만** 코어가 쓴다(`routing.case_type_of`).
    part_id 가 있으면 그 항목의 종류
    없으면 **가장 최근에 바뀐, 「다른 안」을 가진 항목**의 종류
  「다른 안으로 바꿔 줘」는 무엇을 바꾸라는지 문장에 없다. v11 §5-B 는 모르면 사람에게
  넘기라 하지만, 여행이 이미 정해진 Case 에서는 **방금 우리가 바꾼 것**이 그 대상이다 —
  시나리오 버전(`trip_messages._latest_changed_item`)과 같은 규칙이다.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.subjects import ResolvedSubject, SubjectNotFound

from .itinerary import TripStore

KIND = "trip"


def recent_changed_item(store: TripStore, conn: Any, trip_id: UUID, version: int, items: list):
    """가장 최근 버전에서 새로 바뀐, 「다른 안」을 가진 항목. 없으면 가장 뒤의 그런 항목."""
    previous = {i.item_id for i in store.items(conn, trip_id, version - 1)} if version > 1 else set()
    candidates = [i for i in items if i.detail.get("alternates")]
    fresh = [i for i in candidates if i.item_id not in previous]
    pick = fresh or candidates
    return max(pick, key=lambda i: i.seq) if pick else None


def resolve_subject(conn: Any, *, tenant_id: str, customer_id: UUID,
                    subject_ref: dict[str, Any]) -> ResolvedSubject:
    if subject_ref.get("kind") != KIND:
        raise SubjectNotFound(f"unsupported subject kind: {subject_ref.get('kind')}")
    try:
        trip_id = UUID(str(subject_ref["id"]))
    except (KeyError, ValueError) as exc:
        raise SubjectNotFound("subject id is not a trip id") from exc
    store = TripStore(tenant_id)
    try:
        trip, items = store.latest(conn, trip_id)
    except KeyError as exc:
        raise SubjectNotFound("trip not found") from exc
    if str(trip["customer_id"]) != str(customer_id):
        raise SubjectNotFound("trip not found")

    part_kind = None
    part_id = subject_ref.get("part_id")
    if part_id:
        with conn.cursor() as cur:
            cur.execute("SELECT kind FROM itinerary_items WHERE tenant_id=%s AND trip_id=%s "
                        "AND item_id=%s LIMIT 1", (tenant_id, trip_id, str(part_id)))
            row = cur.fetchone()
        if row is None:
            raise SubjectNotFound("item not found in this trip")
        part_kind = row[0]
    recent = recent_changed_item(store, conn, trip_id, trip["version"], items)

    normalized = {"kind": KIND, "id": str(trip_id), "version": trip["version"],
                  "part_id": str(part_id) if part_id else None, "part_kind": part_kind,
                  "recent_part_id": str(recent.item_id) if recent else None,
                  "recent_part_kind": recent.kind if recent else None,
                  "base_version": subject_ref.get("base_version"),
                  "request": subject_ref.get("request")}
    hint = part_kind or (recent.kind if recent else None)
    # ★지정·확인된 항목의 종류는 사실이다 — 분류보다 우선한다. 짐작(최근 바뀐 항목)은 아니다.
    return ResolvedSubject(subject_ref=normalized, routing_hint=hint, hint_is_verified=part_kind is not None)


#: 신고 종류 → 그 일을 맡는 대상 종류(= Team). 재요청은 **대상 항목의 종류**를 따른다.
REPORT_OWNER = {"delay": "dining", "closed": "dining", "stock_out": "activity"}


def make_subject_interpreter(extractor):
    """`[2026-09-17]` 여행 Case 의 문장 해석기 — 신고 종류로 담당을 정한다(`app/core/subjects.py`).

    ★화면 버튼처럼 **구조가 정해진 요청**(`subject_ref.request.type`)은 모델을 부르지 않는다.
    ★모르면 힌트를 내지 않는다 — 그때는 분류 접두로 간다(지어내지 않는다).
    """
    def interpret(*, text: str, subject_ref: dict) -> dict:
        request = dict(subject_ref.get("request") or {})
        report = {k: v for k, v in request.items() if k != "at"} if request.get("type") else None
        if report is None:
            if extractor is None:
                return {"routing_hint": None, "report": None, "reason": "no_extractor"}
            report = extractor(text)
        kind = (report or {}).get("type")
        if kind in REPORT_OWNER:
            hint = REPORT_OWNER[kind]
        elif kind in ("change", "rollback"):
            hint = subject_ref.get("part_kind") or subject_ref.get("recent_part_kind")
        else:
            hint = None
        return {"routing_hint": hint, "report": report}
    return interpret


__all__ = ["KIND", "REPORT_OWNER", "make_subject_interpreter", "recent_changed_item", "resolve_subject"]
