# -*- coding: utf-8 -*-
"""등록한 여행 고치기(수정 모드) — 등록한 여행을 확인 화면 접수로 **다시 열고**, 「완료」 때 **같은 여행의 새 판**을 계산한다. `[2026-10-13 사용자 결정]`

    open_for_trip   여행의 지금 판 → 수정 접수(같은 판으로 열린 것이 있으면 그것). 고칠 수 있는 일정만 넣고 나머지는 고정으로 남긴다
    session         접수가 수정 접수면 `{trip_id, version, frozen_item_ids, frozen[{item_id, reason}]}`. 보통 접수는 None
    origins         그 판의 값 줄 → (원본, 항목 번호)마다 원래 일정 id
    plan_edit       고친 접수의 항목 줄 + 원래 판의 일정 → 새 판의 일정 · 바뀐/추가/뺀 일정 · 지난 일정을 건드린 것

★계약 `wiki/external/rest-endpoints.md` 「등록한 여행 고치기」. 확인 화면의 계산(시각 · 장소 · 자동 추천 · 잠금 · 이동 · 되돌리기)은 **접수 경로를 그대로** 쓰고,
  여기서는 다시 열기와 「완료」의 비교만 한다. 새 판을 쓰는 일(장소 행 · 판정 · 판 · 알림)은 부르는 쪽(`trip_api`)이 등록 · 채팅 변경과 같은 부품으로 한다.
★지난 일정은 접수에 넣지 않는다 — 확인 화면의 고치기 · 자동 추천 · 되돌리기가 지난 일정을 건드릴 길이 처음부터 없다. 「완료」 때 그대로 다시 붙인다.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time
import hashlib
import json
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import Item

from .assemble import _place_in, collect

KST = ZoneInfo("Asia/Seoul")
#: 확인 화면이 고칠 수 있는 일정 종류 — `[2026-10-15 사용자 결정 — ST4F-490]` 숙소 · 항공도 넣는다(잠금으로 — `LOCKED_KINDS`).
#: ☆전에는 활동 · 식사만 넣어 내일 시작하는 비행 · 숙소도 지난 일정처럼 고정(회색)이었다
EDITABLE_KINDS = ("activity", "dining", "lodging", "flight")
#: `[2026-10-15 사용자 결정]` 잠금으로 들어오는 종류 — 잠금을 풀어야 고칠 수 있다. 업체 예약 표에 묶인 일정(`booking_id`)도 같다(`_policy_locked`)
LOCKED_KINDS = ("lodging", "flight")


def _end(item: Item) -> datetime:
    """일정이 끝나는 때 — 끝 시각이 없으면 시작(서버의 다른 「지났다」 판단과 같다)."""
    return item.ends_at or item.starts_at


def fixed_reason(item: Item, now: datetime) -> str | None:
    """접수에 넣지 않고 고정으로 두는 이유 — None 이면 접수에 넣는다. `[2026-10-15 ST4F-490]` 화면이 이유를 말한다(`reopen.frozen`).

    `past` 끝났다 · `overnight` 자정을 넘는다 · `no_place` 장소에 좌표가 없다 · `kind` 접수가 다루지 않는 종류.
    ★업체 예약 표에 묶인 일정(`booking_id`)은 더는 고정이 아니다 — 잠금으로 들어온다(`_policy_locked`)."""
    place = item.place
    if item.kind not in EDITABLE_KINDS:
        return "kind"
    if _end(item) <= now:
        return "past"
    # `[2026-10-14]` 자정을 넘는 일정(23:00 → 다음 날 01:00)은 고정으로 둔다 — 접수는 끝을 「시작 날짜 + HH:MM」으로만 담아(`ends_at` 값 줄에 끝 날짜가 없다)
    # 다시 열면 끝이 시작보다 앞서 「완료」가 time_order 로 막혔다. 끝 날짜를 접수에 담는 근본 수정은 따로 의논한다.
    # `[2026-10-15]` 숙소는 끝 날짜(체크아웃)를 `end_date` 값 줄로 담으므로 여기에 걸리지 않는다
    if item.kind != "lodging" and _end(item).astimezone(KST).date() != item.starts_at.astimezone(KST).date():
        return "overnight"
    # 좌표 없는 장소는 확인 화면의 검사(운영시간 · 이동)를 못 한다 — 「장소를 정하지 못했다」로 막히니 고정으로 둔다
    if place is not None and (place.get("latitude") is None or place.get("longitude") is None):
        return "no_place"
    return None


def _editable(item: Item, now: datetime) -> bool:
    return fixed_reason(item, now) is None


def _policy_locked(item: Item) -> bool:
    """`[2026-10-15 사용자 결정]` 잠금으로 들어오는 일정 — 숙소 · 항공 · 업체 예약 표에 묶인 일정. 고객이 잠근 것(`customer_pinned`)과 다르다:
    잠금을 풀기만 해서는 「바뀐 것」이 아니다(`_same`)."""
    return item.kind in LOCKED_KINDS or item.booking_id is not None


def frozen_entries(raw: Any) -> list[dict[str, Any]]:
    """저장된 고정 목록(`trip_intakes.reopen_frozen`) → `[{item_id, reason}]`. 이유를 담기 전(2026-10-15 이전)에 연 접수는 id 문자열뿐이라 `reason: None`."""
    return [{"item_id": str(entry), "reason": None} if not isinstance(entry, dict)
            else {"item_id": str(entry.get("item_id")), "reason": entry.get("reason")} for entry in (raw or [])]


def _place_value(place: dict[str, Any], kind: str) -> dict[str, Any]:
    """여행의 장소 행 → 접수의 장소 값(`_place_rows` 와 같은 모양). ★`place_id` 는 **이 여행의** 장소 행이다 — 운영시간 · 요식 원장을 그 행으로 다시 찾는다(`hours.facts_for`)."""
    attributes = place.get("attributes") or {}
    content_id = attributes.get("source_content_id") or attributes.get("license_mgt_no")
    value = {"name": place["name"], "kind": place.get("kind") or kind,
             "latitude": float(place["latitude"]), "longitude": float(place["longitude"]),
             "place_id": str(place["place_id"]), "content_id": str(content_id) if content_id else None,
             "content_type_id": attributes.get("source_content_type_id"),
             # 출처를 모르는 공용 장소 행(우리 장소 표)은 읽을 때와 같은 이름(`places`)
             "source": attributes.get("source") or "places"}
    if attributes.get("dining_place_uid"):
        value["dining_place_uid"] = str(attributes["dining_place_uid"])
    if attributes.get("pick_origin"):
        value["origin"] = str(attributes["pick_origin"])
    return value


def _claims_for(index: int, item: Item, evidence: dict[str, Any]) -> list[tuple[str, Any, dict[str, Any]]]:
    """일정 하나 → (칸, 값, 근거) 줄들."""
    when = item.starts_at.astimezone(KST)
    out: list[tuple[str, Any, dict[str, Any]]] = [
        ("title", item.title, evidence), ("date", when.date().isoformat(), evidence),
        ("starts_at", when.strftime("%H:%M"), evidence), ("kind", item.kind, evidence)]
    if item.ends_at is not None:
        out.append(("ends_at", item.ends_at.astimezone(KST).strftime("%H:%M"), evidence))
        if item.kind == "lodging" and item.ends_at.astimezone(KST).date() != when.date():
            out.append(("end_date", item.ends_at.astimezone(KST).date().isoformat(), evidence))   # `[2026-10-15]` 체크아웃 날
    if item.place is not None:
        out.append(("place", _place_value(item.place, item.kind), evidence))
    else:
        out.append(("place", None, {**evidence, "none": True}))        # 「장소 없음」으로 등록한 일정
    booking = (item.detail or {}).get("booking") or {}
    if booking.get("booking_no"):
        out.append(("booking_no", str(booking["booking_no"]), evidence))
    elif booking or item.booking_id is not None:
        # `[2026-10-14]` 「예약 완료」라고만 적어 등록한 일정(`declared_by: customer_plan`, 예약번호 없음)도 예약한 것으로 싣는다 — 안 그러면 확인 화면의 예약 줄 ·
        # 자동 추천 제외가 빠지고, 시각만 고쳐도 새 항목에서 예약 표시가 사라졌다(`itinerary_delay._fixed`). `[2026-10-15]` 업체 예약 표에 묶인 일정도 같다
        out.append(("booked", True, evidence))
    if item.booking_id is not None:
        out.append(("vendor_booking", True, evidence))    # `[2026-10-15]` 화면이 잠금을 풀 때 「업체 예약은 따로 취소 · 변경해야 해요」를 알린다
    if item.locked or (item.detail or {}).get("customer_pinned") or _policy_locked(item):
        out.append(("locked", True, evidence))
    return [(f"items[{index}].{name}", value, why) for name, value, why in out]


def _trip_modes(items: list[Item], editable: list[Item]) -> list[tuple[int, int, str]]:
    """`[2026-10-14]` 등록한 여행에 이미 정해 둔 이동 수단 → (앞 항목 번호, 뒤 항목 번호, 수단). 확인 화면의 수단 값 줄(`moves[0-i~0-j].mode`)로 싣는다.

    고칠 수 있는 이웃 두 일정(같은 날) 사이에 이동 항목이 하나 있고 그 경로가 계산기가 고른 수단일 때만 — 어림(`estimate`) 이동은 고른 수단이 아니다.
    ☆이것이 없을 때 다시 연 수정 화면은 저장된 수단(지하철) 대신 추천(도보)을 보였다(x600 실서버 확인 2026-10-14)."""
    from .moves import mode_of
    from .review import MOVE_MODES

    ordered = sorted(items, key=lambda i: i.seq)
    index_of = {i.item_id: n for n, i in enumerate(editable)}
    out: list[tuple[int, int, str]] = []
    for n, move in enumerate(ordered):
        if move.kind != "mobility":
            continue
        before = next((i for i in reversed(ordered[:n]) if i.kind != "mobility"), None)
        after = next((i for i in ordered[n + 1:] if i.kind != "mobility"), None)
        if before is None or after is None or before.item_id not in index_of or after.item_id not in index_of:
            continue
        a, b = index_of[before.item_id], index_of[after.item_id]
        if b != a + 1 or before.starts_at.astimezone(KST).date() != after.starts_at.astimezone(KST).date():
            continue
        detail = move.detail or {}
        route = detail.get("route_def") or {}
        options = route.get("options") or []
        option = next((o for o in options if o.get("id") == route.get("planned")), options[0] if options else None)
        if option is None or route.get("planned") == "estimate" or detail.get("route_basis") == "estimate":
            continue
        mode, _label = mode_of(option)
        if mode in MOVE_MODES:
            out.append((a, b, mode))
    return out


def _line(item: Item) -> str:
    when = item.starts_at.astimezone(KST)
    end = f"~{item.ends_at.astimezone(KST).strftime('%H:%M')}" if item.ends_at else ""
    return f"{when.date().isoformat()} {when.strftime('%H:%M')}{end} {item.title}"


def open_for_trip(conn, *, tenant_id: str, customer_id: UUID, trip: dict[str, Any], items: list[Item],
                  now: datetime) -> tuple[UUID, bool]:
    """(접수 id, 이미 열려 있던 것인가). `trip` · `items` = 여행의 **지금 판**(`TripStore.latest`). 판을 확인하는 것은 부르는 쪽이다."""
    trip_id, version = trip["trip_id"], int(trip["version"])
    with conn.transaction(), conn.cursor() as cur:
        # 같은 여행을 두 화면에서 동시에 열어도 하나만 만든다(열린 수정 접수 유일 색인이 마지막 방어선)
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{tenant_id}:reopen:{trip_id}",))
        cur.execute("SELECT intake_id, reopen_version FROM trip_intakes WHERE tenant_id=%s AND customer_id=%s "
                    "AND reopen_trip_id=%s AND status='review'", (tenant_id, customer_id, trip_id))
        row = cur.fetchone()
        if row is not None and row[1] == version:
            return row[0], True
        if row is not None:
            # 다시 연 뒤 여행이 바뀌었다(채팅 · 감시) — 옛 판 위에서 고친 값으로 새 판을 쓰지 못하게 닫는다. 값은 남긴다
            cur.execute("UPDATE trip_intakes SET status='closed', stage='closed', updated_at=now() "
                        "WHERE tenant_id=%s AND intake_id=%s", (tenant_id, row[0]))
        editable = sorted((i for i in items if _editable(i, now)), key=lambda i: (i.starts_at, i.seq))
        frozen = [{"item_id": str(i.item_id), "reason": fixed_reason(i, now)} for i in items
                  if i.kind != "mobility" and not _editable(i, now)]
        cur.execute("INSERT INTO trip_intakes (tenant_id, customer_id, status, stage, reopen_trip_id, reopen_version, "
                    "reopen_frozen) VALUES (%s,%s,'review','review',%s,%s,%s::jsonb) RETURNING intake_id",
                    (tenant_id, customer_id, trip_id, version, json.dumps(frozen)))
        intake_id = cur.fetchone()[0]
        # 원본 하나 — 줄마다 고칠 수 있는 일정 하나(확인 화면의 「원문 줄」 자리). 일정이 없어도 만든다: 새 일정은 원본에 붙는다(`pipeline._new_items`)
        transcript = "\n".join(_line(i) for i in editable)
        raw = transcript.encode("utf-8")
        cur.execute("INSERT INTO intake_sources (intake_id, tenant_id, position, kind, sha256, size_bytes, transcript) "
                    "VALUES (%s,%s,0,'trip',%s,%s,%s) RETURNING source_id",
                    (intake_id, tenant_id, hashlib.sha256(raw).hexdigest(), len(raw), transcript))
        source_id = cur.fetchone()[0]
        base = {"source": "trip", "trip_id": str(trip_id), "version": version, "source_id": str(source_id)}
        rows: list[tuple[str, Any, dict[str, Any]]] = [("trip.title", trip["title"], base)]
        if trip.get("party_size") is not None:
            rows.append(("trip.party_size", int(trip["party_size"]), base))
        for index, item in enumerate(editable):
            rows += _claims_for(index, item, {**base, "line": index + 1, "item_id": str(item.item_id)})
        for a, b, mode in _trip_modes(items, editable):
            rows.append((f"moves[0-{a}~0-{b}].mode", mode, base))       # 원본은 하나(위치 0) — 확인 화면의 구간 id 는 「0-번호」
        for field_name, value, evidence in rows:
            cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, source_id, field, value_json, method, "
                        "evidence, needs_review, note, created_at) VALUES (%s,%s,1,%s,%s,%s,'trip',%s,false,NULL,clock_timestamp())",
                        (intake_id, tenant_id, source_id, field_name, json.dumps(value, ensure_ascii=False),
                         json.dumps(evidence, ensure_ascii=False)))
    return intake_id, False


def cancel(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID) -> None:
    """`[2026-10-13 사용자 지시]` 수정 모드의 「취소」 — 열린 수정 접수를 닫는다(`closed`). 고친 값은 여행에 쓰지 않고 남겨만 두며, 다음 다시 열기는 새 접수다.
    남의 것 · 없는 것은 `LookupError`, 보통 접수 · 이미 「완료」한 것은 `IntakeConflict`. 이미 닫힌 것은 그대로 둔다."""
    from .pipeline import IntakeConflict

    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT status, reopen_trip_id FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s "
                    "FOR UPDATE", (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
        if row is None:
            raise LookupError("intake")
        status, trip_id = row
        if trip_id is None:
            raise IntakeConflict("intake_not_reopened", "등록한 여행을 고치는 접수가 아니에요")
        if status == "closed":
            return
        if status != "review":
            raise IntakeConflict("intake_not_editable", f"지금은 취소할 수 없습니다(상태 {status})", status=status)
        cur.execute("UPDATE trip_intakes SET status='closed', stage='closed', updated_at=now() WHERE tenant_id=%s AND intake_id=%s",
                    (tenant_id, intake_id))


def session(conn, *, tenant_id: str, intake_id: UUID) -> dict[str, Any] | None:
    """수정 접수면 `{trip_id, version, frozen_item_ids, frozen}` — 보통 접수는 None."""
    with conn.cursor() as cur:
        cur.execute("SELECT reopen_trip_id, reopen_version, reopen_frozen FROM trip_intakes "
                    "WHERE tenant_id=%s AND intake_id=%s", (tenant_id, intake_id))
        row = cur.fetchone()
    if row is None or row[0] is None:
        return None
    entries = frozen_entries(row[2])
    return {"trip_id": str(row[0]), "version": int(row[1]), "frozen_item_ids": [e["item_id"] for e in entries], "frozen": entries}


def origins(claims: list[dict[str, Any]]) -> dict[tuple[str, int], UUID]:
    """(원본, 항목 번호) → 원래 일정 id. ★값 줄 **전부**에서 찾는다 — 고객이 고친 칸은 마지막 값이 `customer` 라
    칸마다 하나만 남기면(`effective`) 근거가 사라질 수 있다. 다시 연 값은 판을 올려도 그대로 옮겨진다(`pipeline.edit`)."""
    out: dict[tuple[str, int], UUID] = {}
    for claim in claims:
        evidence = claim.get("evidence") or {}
        name = claim["field"]
        if claim.get("method") == "trip" and name.startswith("items[") and evidence.get("item_id"):
            out[(str(claim["source_id"]), int(name[6:name.index("]")]))] = UUID(str(evidence["item_id"]))
    return out


@dataclass
class EditPlan:
    """「완료」의 결과 — 새 판의 일정(순서대로 `seq` 를 다시 매김)과 무엇이 바뀌었나."""

    items: list[Item]
    #: 새 장소가 필요한 일정 id → 등록 몸통의 장소 모양(`name · kind · lat · lon · weather_sensitive · attributes`) + `place_id`(접수가 아는 행 번호, 없으면 None).
    #: 부르는 쪽이 그 행을 쓰거나(공용 · 이 여행의 행일 때만) 등록과 같은 규칙으로 넣어 `place_id` 를 채운다
    places: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    changed: list[str] = field(default_factory=list)
    changed_ids: list[UUID] = field(default_factory=list)
    added_ids: list[UUID] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    #: 이미 끝난 일정을 바꾸거나 빼거나 지난 때에 더한 것(제목) — 하나라도 있으면 쓰지 않는다
    past: list[str] = field(default_factory=list)
    #: 새 판 일정 id → 접수의 (원본, 항목 번호) — 확인 화면이 검증한 이동을 새 판 일정에 잇는 열쇠(`registered_moves.fill_edited_moves`)
    keys: dict[UUID, tuple[str, int]] = field(default_factory=dict)

    @property
    def unchanged(self) -> bool:
        return not (self.changed or self.added or self.removed)

    def summary(self) -> str:
        """변경 이력 · 알림에 싣는 고객 말 — 무엇을 몇 개 바꿨나."""
        parts = [f"{label} {', '.join(titles)}" for label, titles in
                 (("바꾼 일정", self.changed), ("추가한 일정", self.added), ("뺀 일정", self.removed)) if titles]
        return "일정을 직접 고쳤어요 — " + " · ".join(parts)


def _at(day: str, hhmm: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), time.fromisoformat(hhmm), tzinfo=KST)


def _same(origin: Item, row: dict[str, Any], starts: datetime, ends: datetime | None) -> bool:
    place = row["place"]
    same_place = (place is None and origin.place_id is None) or \
        (place is not None and origin.place_id is not None and str(place.get("place_id")) == str(origin.place_id))
    booking = ((origin.detail or {}).get("booking") or {}).get("booking_no")
    # 예약번호는 없어도 「예약 있음」으로 등록한 일정이 있다 — 그 표시가 달라졌으면 고친 것이다(`[2026-10-15]` 업체 예약 표에 묶인 일정도 예약한 것이다)
    same_booked = (bool(row["booking_no"]) or row["booked"] is True) == bool((origin.detail or {}).get("booking") or origin.booking_id)
    pinned = bool(origin.locked or (origin.detail or {}).get("customer_pinned"))
    # `[2026-10-15]` 정책으로 잠근 일정(숙소 · 항공 · 업체 예약)은 잠금 칸을 견주지 않는다 — 다시 열면 늘 잠금으로 들어오니 풀기만 해서는 바뀐 것이 아니다
    same_lock = _policy_locked(origin) or row["locked"] == pinned
    # 끝 시각 없이 등록한 일정은 확인 화면이 규칙으로 끝을 채운다(`assemble._fill_times`) — 끝 칸 값 줄이 없으면 고친 것이 아니다
    same_end = ends == origin.ends_at or (origin.ends_at is None and "ends_at" not in row["claims"])
    return ((row["title"] or "") == origin.title and row["kind"] == origin.kind and starts == origin.starts_at
            and same_end and same_place and (row["booking_no"] or None) == (booking or None) and same_booked
            and same_lock)


def plan_edit(*, rows: list[dict[str, Any]], origin_of: dict[tuple[str, int], UUID], base_items: list[Item],
              frozen_ids: set[str], intake_id: str, revision: int, now: datetime) -> EditPlan:
    """`rows` = 고친 접수의 항목 줄(`assemble.collect` — 뺀 항목은 없다), `base_items` = 다시 연 판의 일정 전부.

    - 안 바뀐 일정 · 고정 일정은 **같은 id 그대로**(같은 항목 객체 — 순번만 다시 매긴다)
    - 바뀐 일정은 새 id 가 원래 일정을 가리킨다(`replaces_item_id` — 채팅 변경과 같다). 세부(`detail`)는 등록 때와 같은 모양으로 새로 쓴다
    - ★`[2026-10-15 ST4F-490]` 숙소 · 항공 · 업체 예약 일정(정책 잠금)은 잠금을 풀어 고칠 수 있다 — 업체 예약 연결(`booking_id`)은 그대로 두고,
      같은 장소면 원래 세부(편명 · 숙소 정보 등)를 이어받는다(다른 곳으로 바꾸면 옛 곳의 세부를 남기지 않는다)
    - 이동 항목은 앞뒤 일정이 둘 다 그대로이고 여전히 이웃일 때만 남긴다(바뀐 일정 사이의 이동은 다시 계산할 대상이다)
    - ★`[2026-10-15 ST4F-490]` 이미 끝난 이동(끝 ≤ 지금)은 앞뒤가 바뀌어도 남긴다 — 지나온 기록이다(재검사도 지난 구간은 다시 세지 않는다)
    """
    by_id = {i.item_id: i for i in base_items}
    kept: set[UUID] = set()
    replaced: set[UUID] = set()
    plan = EditPlan(items=[])
    for row in rows:
        if not (row["date"] and row["start"]):
            continue                       # 등록과 같다 — 날짜 · 시작이 없는 줄은 `intake_incomplete` 로 이미 막혔다
        starts = _at(row["date"], row["start"])
        ends = _at(row.get("end_date") or row["date"], row["end"]) if row["end"] else None    # 숙소는 체크아웃 날(`end_date`)
        origin = by_id.get(origin_of.get((row["source_id"], row["index"])))
        if origin is not None and _same(origin, row, starts, ends):
            kept.add(origin.item_id)
            plan.items.append(origin)
            plan.keys[origin.item_id] = (str(row["source_id"]), row["index"])
            continue
        place = row["place"]
        same_spot = place is not None and origin is not None and origin.place_id is not None \
            and str(place.get("place_id")) == str(origin.place_id)
        # `[2026-10-15 ST4F-490]` 정책 잠금 일정을 같은 곳에서 고쳤으면 원래 세부(편명 · 숙소 정보 등)를 이어받는다 — 다시 정하는 칸만 새로 쓴다
        inherit = same_spot and _policy_locked(origin)
        inherited = {k: v for k, v in (origin.detail or {}).items()
                     if k not in ("provenance", "intake", "booking", "customer_pinned")} if inherit else {}
        detail: dict[str, Any] = {**inherited, "provenance": row["provenance"], "intake": {"intake_id": intake_id, "revision": revision}}
        vendor = origin is not None and origin.booking_id is not None
        if row["booking_no"] or row["booked"] is True:
            old_booking = dict((origin.detail or {}).get("booking") or {}) if inherit else {}
            if old_booking or not vendor or row["booking_no"]:
                # 업체 예약 일정은 예약 표(`booking_id`)가 예약을 말한다 — 고객이 적은 예약 표시를 새로 지어 붙이지 않는다
                detail["booking"] = {**(old_booking or {"declared_by": "customer_plan"}),
                                     **({"booking_no": row["booking_no"]} if row["booking_no"] else {})}
        if row["locked"] and not (row["kind"] in LOCKED_KINDS or vendor):
            detail["customer_pinned"] = True       # 정책 잠금 일정은 다시 열면 늘 잠금이다 — 고객 잠금으로 따로 적지 않는다
        title = row["title"] or "(제목 없음)"
        place_claim = row["claims"].get("place") or {}
        if place_claim.get("method") == "customer" and row["place"] and row["place"].get("name") and row["place"]["name"] != title:
            # 확인 화면 카드는 고객이 고른 곳(후보 · 검색 · 자동 추천)의 이름을 일정 이름으로 보인다(웹 `from-review.planItem`) — 새 판도
            # 그 이름으로 쓴다. 원래 적힌 말은 근거(`provenance.title`)에 남는다. ☆처음엔 원문을 그대로 써서 장소만 바뀌고 여행 화면엔 옛 이름이 남았다(실화면 확인)
            title = str(row["place"]["name"])
        # `[2026-10-15 사용자 결정 — 연결 유지]` 업체 예약 일정을 고쳐도 같은 업체 예약을 가리킨다 — 업체 예약은 서버가 바꾸지 않는다(화면이 따로 바꾸라고 알린다)
        item = Item(item_id=uuid4(), seq=0, kind=row["kind"], title=title, place_id=None, starts_at=starts, ends_at=ends,
                    replaces_item_id=origin.item_id if origin is not None else None, detail=detail,
                    booking_id=origin.booking_id if origin is not None else None)
        if same_spot:
            item.place_id, item.place = origin.place_id, origin.place          # 같은 곳 — 장소 행을 새로 만들지 않는다
        elif place is not None:
            # 등록 몸통과 같은 장소 모양(`assemble._place_in`) + 접수가 아는 장소 행 번호(공용 행 · 이 여행의 행이면 그것을 쓴다)
            plan.places[item.item_id] = {**_place_in("p", place, row["kind"]), "place_id": place.get("place_id")}
        if origin is not None:
            replaced.add(origin.item_id)
            plan.changed.append(title if title == origin.title else f"{origin.title} → {title}")
            plan.changed_ids.append(item.item_id)
            if _end(origin) <= now or _end(item) <= now:
                plan.past.append(title)
        else:
            plan.added.append(title)
            plan.added_ids.append(item.item_id)
            if _end(item) <= now:
                plan.past.append(title)
        plan.items.append(item)
        plan.keys[item.item_id] = (str(row["source_id"]), row["index"])
    for origin_id in dict.fromkeys(origin_of.values()):
        origin = by_id.get(origin_id)
        if origin is None or origin_id in kept or origin_id in replaced:
            continue
        plan.removed.append(origin.title)
        if _end(origin) <= now:
            plan.past.append(origin.title)
    fixed = [i for i in base_items if str(i.item_id) in frozen_ids]
    stays = kept | {i.item_id for i in fixed}
    stops = sorted([*plan.items, *fixed], key=lambda i: (i.starts_at, i.seq or 10_000))
    order = [i.item_id for i in stops]
    ordered_base = sorted(base_items, key=lambda i: i.seq)
    moves = []
    for n, move in enumerate(ordered_base):
        if move.kind != "mobility":
            continue
        before = next((i for i in reversed(ordered_base[:n]) if i.kind != "mobility"), None)
        after = next((i for i in ordered_base[n + 1:] if i.kind != "mobility"), None)
        if _end(move) <= now:
            moves.append(move)
        elif before is not None and after is not None and before.item_id in stays and after.item_id in stays \
                and before.item_id in order and after.item_id in order \
                and order.index(after.item_id) == order.index(before.item_id) + 1:
            moves.append(move)
    merged = sorted([*stops, *moves], key=lambda i: (i.starts_at, 0 if i.kind == "mobility" else 1, i.seq or 10_000))
    plan.items = [replace(item, seq=n) for n, item in enumerate(merged, start=1)]
    return plan


def prepare(conn, *, tenant_id: str, intake_id: UUID, revision: int, base_items: list[Item], frozen_ids: set[str],
            now: datetime) -> EditPlan:
    """그 판의 값 줄을 확인 화면 · 등록과 **같은 줄**(`collect`)로 세운 뒤 원래 판과 견준다(`plan_edit`)."""
    from . import registered_moves, review
    from .pipeline import _claims, _sources

    claims = _claims(conn, tenant_id, intake_id, revision)
    got = collect(sources=_sources(conn, tenant_id, intake_id), claims=claims)
    plan = plan_edit(rows=got.rows, origin_of=origins(claims), base_items=base_items, frozen_ids=frozen_ids,
                     intake_id=str(intake_id), revision=revision, now=now)
    # `[2026-10-14]` 바뀐 일정 옆 · 새로 이웃이 된 구간에 확인 화면이 검증한 이동을 넣고, 고객이 고른 수단은 옛 이동을 갈음한다.
    # 수단만 바꿔도 새 판이다(`changed`) — 그래야 고른 수단이 저장되고 출발 알림이 그 수단으로 나간다
    # `[2026-10-15 ST4F-490]` 고정 일정 옆 구간 · 아침 숙소 구간도 재검사가 검증한 이동으로 잇는다(`fixed_ids`)
    plan.items, picked = registered_moves.fill_edited_moves(plan.items, review.load(conn, tenant_id, intake_id, revision),
                                                            plan.keys, review.customer_mode_pairs(claims),
                                                            fixed_ids=frozenset(frozen_ids))
    plan.changed += picked
    return plan


__all__ = ["EDITABLE_KINDS", "EditPlan", "LOCKED_KINDS", "cancel", "fixed_reason", "frozen_entries", "open_for_trip", "origins",
           "plan_edit", "prepare", "session"]
