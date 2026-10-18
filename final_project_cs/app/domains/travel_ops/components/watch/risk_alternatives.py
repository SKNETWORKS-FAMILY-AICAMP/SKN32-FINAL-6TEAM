"""고객이 누른 위험 대안 요청을 정상 보류 제안 경로로 보낸다."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Callable
from uuid import UUID
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.components.planning.pending import PendingStore
from app.domains.travel_ops.components.watch import risk_report, watch_relaxed

KST = ZoneInfo("Asia/Seoul")


def request(connect: Callable[[], Any], *, tenant_id: str, customer_id: UUID, trip_id: UUID, item_id: UUID,
            check: Callable[..., dict[str, Any]], now: datetime | None = None,
            store_factory: Callable[[str], TripStore] = TripStore,
            may_notify: Callable[[Any, str, UUID], bool] | None = None) -> dict[str, Any]:
    """검증과 제안만 한다. 남의 여행·항목은 LookupError로 동일하게 숨긴다."""
    fixed_now = now is not None
    now = now or datetime.now(KST)
    store = store_factory(tenant_id)
    with connect() as conn:
        gate = _state(conn, tenant_id, trip_id, customer_id)
        if denied := _denied(gate):
            return denied
        trip, items = store.latest(conn, trip_id)
        item = _item(items, item_id)
        if denied := _item_denied(item, now):
            return denied
        snapshot = (int(trip["version"]), _snapshot(item), deepcopy(trip.get("constraints")), trip.get("party_size"))
    if not watch_relaxed.enabled():
        return {"status": "unavailable", "reason": "feature_disabled", "message": "대안 제안 기능이 꺼져 있어요", "options": []}
    try:
        report = check(place=item.place, starts_at=max(now, item.starts_at))
    except Exception:  # noqa: BLE001 — 조회 오류는 대안 없음과 구분한다
        return {"status": "unavailable", "reason": "verification_failed", "message": "현재 위험 정보를 확인하지 못했어요", "options": []}
    if not isinstance(report, dict):
        return {"status": "unavailable", "reason": "verification_failed", "options": []}
    public = risk_report.judge_item(lambda **kw: report, item, mode="fresh", at=now)
    if report.get("verdict") not in {"clear", "disrupted"}:
        return {"status": "unavailable", "reason": "verification_failed", "message": "일부 위험 정보를 확인하지 못했어요", "options": [], "report": public}
    causes = report.get("disruptions") or []
    if not causes:
        status = "unavailable" if public["status"] == "unknown" else "no_risk"
        return {"status": status, "reason": "no_current_risk" if status == "no_risk" else "verification_failed",
                "message": "현재 확인된 위험이 없어요" if status == "no_risk" else "위험 정보를 모두 확인하지 못했어요",
                "options": [], "report": public}
    try:
        with connect() as conn, conn.transaction():
            gate = _state(conn, tenant_id, trip_id, customer_id, lock=True)
            if denied := _denied(gate):
                return {**denied, "report": public}
            latest, latest_items = store.latest(conn, trip_id)
            current = _item(latest_items, item_id)
            current_now = now if fixed_now else datetime.now(KST)
            if denied := _item_denied(current, current_now):
                return {**denied, "report": public}
            current_snapshot = (int(latest["version"]), _snapshot(current), latest.get("constraints"), latest.get("party_size"))
            if current_snapshot != snapshot:
                return {"status": "stale", "reason": "확인하는 동안 일정이 바뀌었어요 · 다시 확인해 주세요", "options": [], "report": public}
            notice_allowed = (may_notify or _may_notify)(conn, tenant_id, customer_id)
            offered = watch_relaxed.offer_relaxed(conn, store=_NoticeStore(store, notice_allowed),
                        trip_id=trip_id, item_id=item_id, causes=causes, check=check, now=current_now)
            if offered is None:
                return {"status": "no_alternate", "reason": "안전과 운영시간·이동 조건을 모두 만족하는 대안을 찾지 못했어요",
                        "options": [], "report": public}
            if offered.get("already"):
                opened = next((p for p in PendingStore(tenant_id).list(conn, trip_id, only_open=True)
                               if str(p.get("item_id")) == str(item_id) and p.get("base_version") == latest["version"]), None)
                if opened is None:
                    return {"status": "unavailable", "reason": "closed_proposal", "message": "이 일정의 앞선 제안이 이미 닫혔어요",
                            "options": [], "report": public}
                return {**offered, "status": "already", "proposal_id": str(opened["proposal_id"]),
                        "options": opened.get("options_json") or offered.get("options") or [], "report": public}
            return {**offered, "status": "offered", "reason": "customer_choice", "message": "고르시면 일정을 바꿀게요", "report": public}
    except watch_relaxed.VerificationUnavailable as exc:
        return {"status": "unavailable", "reason": "verification_failed", "message": "대안의 안전 정보를 확인하지 못했어요", "options": [],
                "failed_categories": exc.categories, "report": public}


class _NoticeStore:
    def __init__(self, store, may_notify):
        self.store, self.may_notify = store, may_notify

    def __getattr__(self, name):
        return getattr(self.store, name)

    def enqueue_message(self, *args, **kwargs):
        return self.store.enqueue_message(*args, **kwargs) if self.may_notify else False


def _state(conn, tenant_id, trip_id, customer_id, *, lock=False):
    with conn.cursor() as cur:
        cur.execute("SELECT t.customer_id,t.status,EXISTS (SELECT 1 FROM trip_safety_pauses p "
                    "WHERE p.tenant_id=t.tenant_id AND p.trip_id=t.trip_id AND p.resumed_at IS NULL) "
                    "FROM trips t WHERE t.tenant_id=%s AND t.trip_id=%s" + (" FOR UPDATE OF t" if lock else ""),
                    (tenant_id, trip_id))
        row = cur.fetchone()
    if row is None or row[0] != customer_id:
        raise LookupError("trip")
    return row


def _denied(gate):
    if gate[1] != "active":
        return {"status": "unavailable", "reason": "inactive", "message": "현재 관리 중인 여행에서만 대안을 요청할 수 있어요", "options": []}
    if gate[2]:
        return {"status": "unavailable", "reason": "paused", "message": "재난으로 정지된 여행이에요 · 먼저 재개 여부를 확인해 주세요", "options": []}
    return None


def _item(items, item_id):
    found = next((item for item in items if item.item_id == item_id), None)
    if found is None:
        raise LookupError("item")
    return found


def _item_denied(item: Item, now: datetime):
    if (item.ends_at or item.starts_at) <= now:
        return {"status": "ended", "reason": "이미 끝난 일정에는 새 대안을 열지 않아요", "options": []}
    if item.kind not in {"activity", "dining"} or not item.place or item.place.get("latitude") is None or item.place.get("longitude") is None:
        return {"status": "unavailable", "reason": "장소가 확인된 활동·식사 일정에서 대안을 요청해 주세요", "options": []}
    return None


def _snapshot(item):
    return deepcopy((item.item_id, item.kind, item.title, item.starts_at, item.ends_at, item.place, item.locked, item.detail))


def _may_notify(conn, tenant_id, customer_id):
    return False  # 웹 입구가 채널 권한 검사를 주입하지 않으면 외부 알림을 만들지 않는다.
