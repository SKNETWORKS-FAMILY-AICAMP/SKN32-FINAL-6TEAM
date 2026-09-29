# -*- coding: utf-8 -*-
"""일정이 꼬였을 때 **바꿀지 · 물을지 · 알리기만 할지**를 가르고, 묻는 동안 안을 들고 있는다. `[2026-09-24]` D-020

★★판정(`decide`) — 위에서부터 먼저 걸리는 것이 이긴다.

    ① 「변경 안 할 일정」(고객 고정 `customer_pinned` · 잠긴 예약 `locked`) → ask (15번 답과 상관없이 묻는다)
    ② 설문 15번 「먼저 물어봐줘」 + 안전 사건            → safety_alert (바꾸지 않고, 「안전」이 분명한 알림)
    ③ 설문 15번 「먼저 물어봐줘」                       → ask      (바꾸지 않고 안 1·2·3을 보이고 기다린다)
    ④ 그 밖(15번이 없거나 「비슷한 곳으로」)             → apply    (지금까지처럼 최고 안을 바로 적용하고 알린다)

  ★「먼저 물어봐줘」가 아닌 여행은 안전 사건도 **바로 바꾼다** — 사용자 결정(2026-09-24 새벽).
  ★「변경 안 할 일정」이 안전 사건에 걸리면 ①이다 — 바꾸지 않되 알림의 머리는 「안전」이다(`safety` 칸).
  ★돈이 걸렸는지(예약 연결)는 **따로 따지지 않는다** — 사용자 결정(2026-09-24). 바꾸기 싫은 일정은
    사용자가 「변경 안 할 일정」으로 적는다.

★무응답 — 그 일정이 **끝날 때까지** 기다렸다가 `expired` 로 닫는다. **바꾸지 않는다.**
  그 뒤로 알림은 일정 순서대로 다음 일정으로 이어 간다(여러 건을 묶어 묻지 않는다).

★고르면 — 기존 「다른 안으로 바꾸기」(`plan_swap`)를 **그대로 탄다.** 계산한 뒤로 시간이 흘렀으니
  그 시각에 다시 점검하고, 그 사이 일정이 바뀌었으면(`stale`) 고르지 못한다. 한 건은 한 번만 닫힌다 —
  일행이 동시에 누르면 **먼저 닫은 쪽**이 이기고 나중 쪽은 `already_decided`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from .itinerary import Item, StaleItinerary, TripStore
from .itinerary_changes import ItineraryChange, NoChange, applied_record, plan_swap
from .survey import on_disruption

#: 안전 사건 — 몸이 다칠 수 있는 것만. 기상특보는 「경보」만(주의보 제외). 사용자와 합의(2026-09-24).
SAFETY_CATEGORIES = frozenset({"earthquake", "disaster_msg"})


def is_safety(report: dict[str, Any] | None) -> bool:
    for event in (report or {}).get("disruptions") or []:
        category = event.get("category")
        if category in SAFETY_CATEGORIES:
            return True
        if category == "weather_warning" and "경보" in str(event.get("kind") or ""):
            return True
    return False


def protected_reason(item: Item) -> str | None:
    """「변경 안 할 일정」인가. ★항목에 이미 있는 표시만 본다 — 돈이 걸렸는지는 따지지 않는다."""
    if item.detail.get("customer_pinned"):
        return "customer_pinned"
    if item.locked:
        return "locked"
    if item.detail.get("booking"):
        # ★`[2026-09-27]` 고객 계획에서 읽은 예약번호(`intake/assemble.py`). 업체 확인 전이라 예약 표(`bookings`)에는
        #   없지만, 돈이 걸렸을 수 있는 일정을 묻지 않고 바꾸지 않는다.
        return "booked"
    return None


@dataclass(frozen=True)
class Decision:
    action: str                    # apply · ask · safety_alert
    reason: str | None             # ask_first · protected · safety_alert (apply 면 None)
    protected_by: str | None
    safety: bool


def decide(*, constraints: dict[str, Any] | None, item: Item,
           report: dict[str, Any] | None = None) -> Decision:
    safety = is_safety(report)
    protected = protected_reason(item)
    if protected:
        return Decision("ask", "protected", protected, safety)
    if on_disruption(constraints) == "ask_first":
        if safety:
            return Decision("safety_alert", "safety_alert", None, True)
        return Decision("ask", "ask_first", None, False)
    return Decision("apply", None, None, safety)


#: 실내로 옮기면 원인이 사라지는 사건 — 실내·야외를 모를 때 **먼저 묻는** 대상(`replan.WEATHER_LIKE` 와 같은 뜻)
WEATHER_ONLY = frozenset({"forecast", "weather_warning", "air_quality"})
#: 「바꿀까요?」에 「바꿔 줘」로 답하는 키 — 이 키로 고르면 **그때** 대체안을 계산한다
CONSENT_KEY = "change"
CONSENT_REASON = "indoor_unknown"


def weather_only(report: dict[str, Any] | None) -> bool:
    """안전 사건 없이 **날씨 사건만** 걸렸나(예보·특보·대기질) — 실내로 옮기면 원인이 사라지는 경우."""
    report = report or {}
    if is_safety(report):
        return False
    categories = {event.get("category") for event in report.get("disruptions") or []}
    return bool(categories) and categories <= WEATHER_ONLY


def needs_consent(report: dict[str, Any] | None, constraints: dict[str, Any] | None = None) -> bool:
    """★`[2026-09-29]` 활동에 **날씨 사건만** 걸렸다 — 대체안을 계산하지 말고 먼저 「바꿀까요?」를 묻는가.

    사용자 결정(2026-09-29 두 번):
      ① 실내·야외를 **모르면** 설문과 상관없이 먼저 묻는다.
      ② 아는 곳이라도 비 올 때 대체안은 **제안**으로 나간다 — 고객이 설문에서 **직접** 「비슷한 곳으로 바꿔줘」를
         고른 경우만(`survey.auto_on_disruption`) 자동으로 바꾸고 되돌리기를 보인다.
    「바꿔 줘」라고 하면 **그때** 대체안을 계산해 보인다(대체안 계산은 후보마다 바깥 점검을 불러 비용이 든다).
    안전 사건(지진·재난문자·기상 「경보」)이 섞이면 이 길이 아니다 — 지금 규칙(`decide`)이 먼저다.
    날씨 밖 사건(교통 통제 등)은 실내외와 상관없어 그대로 간다.
    `constraints` 를 안 주면 ①만 본다(옛 호출과 같다).
    """
    from .survey import auto_on_disruption

    report = report or {}
    if not weather_only(report):
        return False
    if report.get("indoor_unknown"):
        return True
    return constraints is not None and not auto_on_disruption(constraints)


def consent_notice(*, item: Item, causes: list[dict[str, Any]], proposal_id: UUID,
                   indoor_unknown: bool = True) -> dict[str, Any]:
    """「바꿀까요?」 알림. ★대체안이 없다(아직 계산하지 않았다). 무응답의 결과를 **반드시** 적는다."""
    why = " 이 장소가 실내인지 확인하지 못했어요." if indoor_unknown else ""
    text = (f"{item.title} — {_cause_text(causes)}.{why} "
            f"일정을 바꿀까요? 「바꿔 줘」를 누르면 그때 다른 곳을 찾아 보여 드려요. "
            f"답이 없으면 원래 일정을 그대로 둡니다.")
    return {"type": "proposal_request", "text": text, "language": "ko", "causes": causes,
            "proposal_id": str(proposal_id), "item_id": str(item.item_id), "reason": CONSENT_REASON,
            "protected_by": None, "consent": True, "consent_key": CONSENT_KEY, "options": [],
            "replay": False}


def ask_consent(conn, *, store: TripStore, trip_id: UUID, item: Item, base_version: int,
                causes: list[dict[str, Any]], indoor_unknown: bool = True) -> dict[str, Any]:
    """「바꿀까요?」 보류 제안을 연다(안 없이). 이미 물었으면 다시 알리지 않는다. 부르는 쪽이 트랜잭션을 연다."""
    pending = PendingStore(store.tenant_id)
    decision = Decision("ask", CONSENT_REASON, None, False)
    proposal_id = pending.open(conn, trip_id=trip_id, item=item, base_version=base_version,
                               decision=decision, causes=causes, options=[])
    if proposal_id is None:
        return {"status": "asked", "already": True, "reason": CONSENT_REASON, "item": item.title}
    store.enqueue_message(conn, trip_id=trip_id, key=f"proposal:{proposal_id}",
                          payload=consent_notice(item=item, causes=causes, proposal_id=proposal_id,
                                                 indoor_unknown=indoor_unknown))
    return {"status": "asked", "already": False, "proposal_id": str(proposal_id), "reason": CONSENT_REASON,
            "safety": False, "item": item.title}


def options_from(plan: ItineraryChange, item: Item) -> list[dict[str, Any]]:
    """계산된 안을 **적용에 필요한 값 그대로** 1위부터 적는다(다시 계산하지 않게)."""
    best = plan.replacements.get(item.item_id)
    return [] if best is None else options_for(best)


def options_for(best: Item) -> list[dict[str, Any]]:
    """최고 안(바꿔 넣을 항목) 하나와 그것이 들고 있는 「다른 안」을 1위부터."""
    first = applied_record(best)
    if best.place and (best.place.get("attributes") or {}).get("catalog_pending"):
        first["catalog_place"] = best.place      # ★1위도 관광공사 목록 후보면 고를 때 등록할 원본을 싣는다
    ranked = [first] + list(best.detail.get("alternates") or [])
    return [{**record, "rank": rank} for rank, record in enumerate(ranked, start=1)]


def _cause_text(causes: list[dict[str, Any]]) -> str:
    for cause in causes:
        for field in ("summary", "kind", "reason", "type", "category"):
            if cause.get(field):
                return str(cause[field])
    return "일정에 문제가 생겼어요"


def proposal_notice(*, item: Item, decision: Decision, causes: list[dict[str, Any]],
                    options: list[dict[str, Any]], proposal_id: UUID) -> dict[str, Any]:
    """묻는 알림. ★「답이 없으면 원래 일정을 그대로 둡니다」를 **반드시** 적는다 — 무응답의 결과다."""
    head = "⚠️ 안전 알림 — " if decision.safety else ""
    why = _cause_text(causes)
    listed = " · ".join(f"{o['rank']}) {o.get('option_label') or o['name']}" for o in options[:3])
    if decision.reason == "protected":
        body = (f"{item.title} — {why}. 변경하지 않기로 한 일정이라 **바꾸지 않았어요.** "
                f"어떻게 할까요? {listed}")
    elif decision.reason == "safety_alert":
        body = (f"{item.title} — {why}. 일정은 **바꾸지 않았어요.** 안전을 먼저 살펴 주세요."
                + (f" 다른 안: {listed}" if listed else ""))
    else:
        body = f"{item.title} — {why}. 어떻게 할까요? {listed}"
    text = f"{head}{body} 답이 없으면 원래 일정을 그대로 둡니다."
    return {"type": "safety_alert" if decision.safety else "proposal_request",
            "text": text, "language": "ko", "causes": causes, "proposal_id": str(proposal_id),
            "item_id": str(item.item_id), "reason": decision.reason,
            "protected_by": decision.protected_by,
            "options": [{"key": o["key"], "rank": o["rank"],
                         "name": o.get("option_label") or o["name"],
                         "starts_at": o.get("starts_at")} for o in options[:3]],
            "replay": False}


class PendingStore:
    """보류 제안을 쓰고 · 읽고 · 닫는다. ★모든 쿼리에 `tenant_id` — 조건 없는 조회는 보안 결함이다."""

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id

    def open(self, conn, *, trip_id: UUID, item: Item, base_version: int, decision: Decision,
             causes: list[dict[str, Any]], options: list[dict[str, Any]]) -> UUID | None:
        """새로 열었으면 id, **이미 같은 제안이 있으면 None**(감시가 3분마다 같은 것을 만들지 않게)."""
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pending_changes (tenant_id, trip_id, item_id, base_version, reason, "
                "protected_by, safety, cause_json, options_json, expires_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id, trip_id, item_id, base_version) DO NOTHING "
                "RETURNING proposal_id",
                (self.tenant_id, trip_id, item.item_id, base_version, decision.reason,
                 decision.protected_by, decision.safety,
                 json.dumps(causes, ensure_ascii=False, default=str),
                 json.dumps(options, ensure_ascii=False, default=str),
                 item.ends_at or item.starts_at))
            row = cur.fetchone()
        return row[0] if row else None

    _COLUMNS = ("proposal_id", "trip_id", "item_id", "base_version", "reason", "protected_by",
                "safety", "cause_json", "options_json", "status", "expires_at", "chosen_key",
                "chosen_by", "chosen_version", "decided_at", "created_at")

    def list(self, conn, trip_id: UUID, *, only_open: bool = False) -> list[dict[str, Any]]:
        where = " AND status='open'" if only_open else ""
        with conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(self._COLUMNS)} FROM pending_changes "
                        f"WHERE tenant_id=%s AND trip_id=%s{where} ORDER BY created_at",
                        (self.tenant_id, trip_id))
            return [dict(zip(self._COLUMNS, row)) for row in cur.fetchall()]

    def get(self, conn, trip_id: UUID, proposal_id: UUID, *, lock: bool = False) -> dict[str, Any] | None:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(self._COLUMNS)} FROM pending_changes "
                        f"WHERE tenant_id=%s AND trip_id=%s AND proposal_id=%s"
                        + (" FOR UPDATE" if lock else ""),
                        (self.tenant_id, trip_id, proposal_id))
            row = cur.fetchone()
        return dict(zip(self._COLUMNS, row)) if row else None

    def close(self, conn, proposal_id: UUID, *, status: str, key: str | None = None,
              by: str | None = None, version: int | None = None) -> bool:
        """★`open` 인 것만 닫는다 — 이미 닫혔으면 False(먼저 닫은 쪽이 이긴다)."""
        with conn.cursor() as cur:
            cur.execute("UPDATE pending_changes SET status=%s, chosen_key=%s, chosen_by=%s, "
                        "chosen_version=%s, decided_at=now() "
                        "WHERE tenant_id=%s AND proposal_id=%s AND status='open'",
                        (status, key, by, version, self.tenant_id, proposal_id))
            return cur.rowcount == 1

    def set_options(self, conn, proposal_id: UUID, *, options: list[dict[str, Any]], reason: str) -> bool:
        """★`[2026-09-29]` 「바꿀까요?」에 「바꿔 줘」 — 같은 제안에 **그때 계산한 안**을 채운다. `open` 인 것만.

        새 제안을 따로 열지 않는다 — 같은 항목·같은 기준 버전은 제안 하나다(`open` 의 UNIQUE)."""
        with conn.cursor() as cur:
            cur.execute("UPDATE pending_changes SET options_json=%s, reason=%s "
                        "WHERE tenant_id=%s AND proposal_id=%s AND status='open'",
                        (json.dumps(options, ensure_ascii=False, default=str), reason,
                         self.tenant_id, proposal_id))
            return cur.rowcount == 1

    def expire(self, conn, *, now: datetime) -> list[dict[str, Any]]:
        """무응답 — 그 일정이 끝난 제안을 닫는다. ★바꾸지 않는다. 닫은 것을 돌려준다(조용히 닫지 않는다)."""
        with conn.cursor() as cur:
            cur.execute("UPDATE pending_changes SET status='expired', decided_at=now() "
                        "WHERE tenant_id=%s AND status='open' AND expires_at <= %s "
                        "RETURNING proposal_id, trip_id, item_id",
                        (self.tenant_id, now))
            return [dict(zip(("proposal_id", "trip_id", "item_id"), row)) for row in cur.fetchall()]


class ProposalRefused(Exception):
    def __init__(self, code: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code, self.detail = code, detail or {}


def choose(*, conn, store: TripStore, pending: PendingStore, trip_id: UUID, proposal_id: UUID,
           key: str | None, by: str, places_by_id: dict[str, dict[str, Any]],
           check: Callable[..., dict[str, Any]] | None) -> dict[str, Any]:
    """고객이 안을 고른다. `key=None` 이면 **원래 일정을 그대로 둔다**(kept).

    ★한 트랜잭션 안에서 제안을 잠그고(`FOR UPDATE`) → 기존 「다른 안」 경로(`plan_swap`)로 다시 점검 →
      새 버전을 쓰고 → 제안을 닫는다. 어느 단계든 실패하면 **아무것도 안 바뀐다.**
    """
    proposal = pending.get(conn, trip_id, proposal_id, lock=True)
    if proposal is None:
        raise ProposalRefused("not_found")
    if proposal["status"] != "open":
        raise ProposalRefused("already_decided", {"status": proposal["status"],
                                                  "chosen_key": proposal["chosen_key"]})
    if key is None:
        pending.close(conn, proposal_id, status="kept", by=by)
        return {"status": "kept"}
    trip, items = store.latest(conn, trip_id)
    options = list(proposal["options_json"] or [])
    current = next((i for i in items if i.item_id == proposal["item_id"]), None)
    if current is None or trip["version"] != proposal["base_version"]:
        raise ProposalRefused("stale", {"version": trip["version"],
                                        "base_version": proposal["base_version"]})
    if proposal["reason"] == CONSENT_REASON:
        if key != CONSENT_KEY:
            raise ProposalRefused("unknown_option", {"expected": CONSENT_KEY})
        return _consented(conn, store=store, pending=pending, trip_id=trip_id, proposal=proposal,
                          current=current, items=items, places_by_id=places_by_id, check=check)
    # ★`[2026-09-29]` 고른 안이 관광공사 목록 후보면 **지금** 그 여행 전용 장소로 등록한다(같은 트랜잭션 — 실패하면 되돌아간다)
    picked = next((o for o in options if o.get("key") == key), None)
    if picked is not None and picked.get("catalog_place"):
        added = store.add_catalog_place(conn, trip_id, picked["catalog_place"])
        places_by_id = {**places_by_id, str(picked["place_id"]): added}
    # ★기존 경로를 그대로 탄다 — 보관한 안을 「다른 안」 자리에 놓고 고른다
    probe = [i if i.item_id != current.item_id else _with_alternates(i, options) for i in items]
    plan = plan_swap(trip_version=trip["version"], base_version=proposal["base_version"], items=probe,
                     places_by_id=places_by_id, item_id=current.item_id, choice=key,
                     message=None, request_id=f"proposal:{proposal_id}", check=check)
    if isinstance(plan, NoChange):
        raise ProposalRefused(plan.status, plan.detail)
    try:
        version = store.append_version(conn, trip_id=trip_id, base_version=trip["version"],
                                       items=plan.new_items(probe), reason="customer_choice",
                                       causes=plan.causes)
    except StaleItinerary as exc:
        raise ProposalRefused("stale", {"message": str(exc)}) from None
    store.enqueue_notice(conn, trip_id=trip_id, version=version,
                         payload={**plan.notice, "type": "change_notice", "version": version,
                                  "proposal_id": str(proposal_id)})
    pending.close(conn, proposal_id, status="chosen", key=key, by=by, version=version)
    return {"status": "chosen", "version": version, "summary": plan.summary}


def _consented(conn, *, store: TripStore, pending: "PendingStore", trip_id: UUID, proposal: dict[str, Any],
               current: Item, items: list[Item], places_by_id: dict[str, dict[str, Any]],
               check: Callable[..., dict[str, Any]] | None) -> dict[str, Any]:
    """「바꿔 줘」 — **이제** 대체안을 계산해 같은 제안에 안 1·2·3을 채우고 다시 묻는다. 일정은 아직 안 바꾼다.

    ★계산은 감시와 같은 것(`plan_activity_adjustment` — 실내 후보 · 그 시각 영업 · 후보마다 재점검 · 비슷한 곳 순).
    ★점검기가 없으면(`check=None`) 계산하지 않는다 — 재점검 없이 고른 곳을 내밀지 않는다.
    """
    from .activity.similarity import preference_of, score
    from .itinerary_changes import plan_activity_adjustment

    causes = list(proposal["cause_json"] or [])
    if check is None or current.kind != "activity" or current.place is None:
        pending.close(conn, proposal["proposal_id"], status="kept", by="system:no_check")
        return {"status": "no_alternate", "reason": "대체안을 계산할 수 없는 일정이에요"}
    from datetime import datetime as _dt
    from functools import partial
    from zoneinfo import ZoneInfo

    from .itinerary import catalog_activity_places

    trip = store.latest(conn, trip_id)[0]
    registered = list(places_by_id.values())
    names = {str(p.get("name")) for p in registered}
    plan = NoChange("unresolved", {})
    # ★`[2026-09-29]` 등록된 장소 + **관광공사 목록**(가상 행 — 고르면 그때 등록). 재점검은 앞 순위 6곳만(바깥 호출 비용).
    #   600m 에서 못 찾으면 1.5km 까지 넓힌다(채팅 「다른 곳으로 바꿔 줘」와 같은 생각)
    for radius in (600, 1500):
        pool = registered + catalog_activity_places(conn, store.tenant_id, trip_id, near=current.place,
                                                    radius_m=radius, exclude_names=names)
        plan = plan_activity_adjustment(
            item=current, report={"disruptions": causes}, places=pool, check=check,
            now=_dt.now(ZoneInfo("Asia/Seoul")), items=items,
            similarity=partial(score, preference=preference_of(trip.get("constraints"))),
            proposal=True, limit=6, radius_m=radius)
        if not isinstance(plan, NoChange):
            break
    if isinstance(plan, NoChange):
        pending.close(conn, proposal["proposal_id"], status="kept", by="system:no_alternate")
        return {"status": "no_alternate", "reason": "바꿀 수 있는 다른 곳을 찾지 못했어요 — 원래 일정을 그대로 둡니다",
                "detail": plan.detail}
    options = options_from(plan, current)
    pending.set_options(conn, proposal["proposal_id"], options=options, reason=f"{CONSENT_REASON}_options")
    decision = Decision("ask", f"{CONSENT_REASON}_options", None, False)
    store.enqueue_message(conn, trip_id=trip_id, key=f"proposal:{proposal['proposal_id']}:options",
                          payload=proposal_notice(item=current, decision=decision, causes=causes,
                                                  options=options, proposal_id=proposal["proposal_id"]))
    return {"status": "options", "proposal_id": str(proposal["proposal_id"]),
            "options": [{"key": o["key"], "rank": o["rank"], "name": o.get("option_label") or o["name"],
                         "starts_at": o.get("starts_at")} for o in options[:3]]}


def apply_or_ask(conn, *, store: TripStore, trip_id: UUID, item_id: UUID, plan: ItineraryChange,
                 report: dict[str, Any] | None = None) -> dict[str, Any]:
    """★바꾸는 **한 문**(감시 · 새벽 확인) — 판정(`decide`)을 거쳐 새 버전을 쓰거나, 묻는다.

    돌려주는 `status`:
        adjusted  새 버전과 변경 통지를 썼다(같은 트랜잭션)
        asked     바꾸지 않고 보류 제안 + 묻는 알림(이미 물은 것이면 `already: True`, 알림은 다시 안 낸다)
        gone      그 사이 다른 쪽이 이 항목을 바꿨다 — 옛 계산을 밀어 넣지 않는다
        stale     기준 버전이 움직였다
    부르는 쪽이 트랜잭션을 연다.
    """
    trip, items = store.latest(conn, trip_id)
    current = next((i for i in items if i.item_id == item_id), None)
    if current is None:
        return {"status": "gone"}
    decision = decide(constraints=trip.get("constraints"), item=current, report=report)
    if decision.action != "apply":
        options = options_from(plan, current)
        pending = PendingStore(store.tenant_id)
        proposal_id = pending.open(conn, trip_id=trip_id, item=current, base_version=trip["version"],
                                   decision=decision, causes=plan.causes, options=options)
        if proposal_id is None:
            return {"status": "asked", "already": True, "reason": decision.reason, "item": current.title}
        store.enqueue_message(conn, trip_id=trip_id, key=f"proposal:{proposal_id}",
                              payload=proposal_notice(item=current, decision=decision, causes=plan.causes,
                                                      options=options, proposal_id=proposal_id))
        return {"status": "asked", "already": False, "proposal_id": str(proposal_id),
                "reason": decision.reason, "safety": decision.safety, "item": current.title}
    try:
        version = store.append_version(conn, trip_id=trip_id, base_version=trip["version"],
                                       items=plan.new_items(items), reason=plan.reason, causes=plan.causes)
    except StaleItinerary:
        return {"status": "stale"}
    # ★`[2026-09-29]` 자동으로 바꿨으면 **되돌리기**를 싣는다 — 화면이 버튼을 띄우고 `POST /v1/web/trips/{id}/rollback`
    #   (base_version = 이 판, to_version = 바꾸기 전 판)으로 돌린다. 사용자 지시: 자동이면 안내 + 되돌리기 버튼
    store.enqueue_notice(conn, trip_id=trip_id, version=version,
                         payload={**plan.notice, "version": version,
                                  "type": "change_notice", "safety": decision.safety,
                                  "rollback": rollback_offer(version=version, previous=trip["version"])})
    return {"status": "adjusted", "version": version, "safety": decision.safety}


def rollback_offer(*, version: int, previous: int) -> dict[str, Any]:
    """변경 알림에 싣는 「되돌리기」 — 버튼이 부를 값. `request_id` 는 같은 버튼을 두 번 눌러도 한 번만 되게."""
    return {"base_version": int(version), "to_version": int(previous),
            "request_id": f"rollback:v{int(version)}->v{int(previous)}",
            "label": "되돌리기", "path": "/rollback"}


def _with_alternates(item: Item, options: list[dict[str, Any]]) -> Item:
    return Item(item_id=item.item_id, seq=item.seq, kind=item.kind, title=item.title,
                place_id=item.place_id, starts_at=item.starts_at, ends_at=item.ends_at,
                locked=item.locked, booking_id=item.booking_id,
                replaces_item_id=item.replaces_item_id,
                detail={**item.detail, "alternates": [
                    {k: v for k, v in o.items() if k != "rank"} for o in options]},
                place=item.place)


__all__ = ["CONSENT_KEY", "CONSENT_REASON", "Decision", "PendingStore", "ProposalRefused", "SAFETY_CATEGORIES",
           "apply_or_ask", "ask_consent", "choose", "consent_notice", "decide",
           "is_safety", "needs_consent", "options_for", "options_from", "proposal_notice", "protected_reason"]
