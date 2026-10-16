"""운영자가 고른 여행·항목에만 재난 시험 입력을 공급한다. 공유 소스 캐시는 건드리지 않는다."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.application.admin_service import AdminServiceError, audit
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection

KIND = "watch_simulation"
MARKER = "_watch_simulation"
CATEGORIES = {
    "forecast": "날씨 예보", "weather_warning": "기상 특보", "disaster_msg": "재난문자",
    "traffic_control": "교통 통제", "air_quality": "대기질", "earthquake": "지진",
}
SOURCE = "[시뮬레이션] 관리자 시험 입력"


def state(conn, tenant: str, trip_id: UUID, *, now: datetime | None = None) -> dict:
    # 226 이전 DB의 일반 여행 읽기는 계속 허용한다. 시험 기능 쓰기는 226이 필요하다.
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT r.revision,r.value,t.latest_version FROM admin_records r "
                        "JOIN trips t ON t.tenant_id=r.tenant_id AND t.trip_id::text=r.id "
                        "WHERE r.tenant_id=%s AND r.kind=%s AND r.id=%s", (tenant, KIND, str(trip_id)))
            row = cur.fetchone()
    except Exception as exc:
        if type(exc).__name__ != "UndefinedTable":
            raise
        row = None
    if row is None:
        return {"revision": 0, "active": False, "categories": []}
    return _state_of(*row, now=now)


def _state_of(revision, value, version, *, now: datetime | None = None) -> dict:
    active = bool(value.get("categories") and datetime.fromisoformat(value["expires_at"]) > (now or datetime.now(UTC))
                  and value["base_version"] == version)
    return {**value, "revision": int(revision), "active": active}


def states(conn, tenant: str, trip_ids: list, *, now: datetime | None = None) -> dict[str, dict]:
    """여러 여행의 시험 상태를 **한 번에** 읽는다(`[2026-10-14]` — 감시가 여행마다 따로 묻지 않게). 시험이 없는 여행은 빠진다(`state` 의 빈 값과 같은 뜻)."""
    ids = [str(trip_id) for trip_id in trip_ids]
    if not ids:
        return {}
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT r.id,r.revision,r.value,t.latest_version FROM admin_records r "
                        "JOIN trips t ON t.tenant_id=r.tenant_id AND t.trip_id::text=r.id "
                        "WHERE r.tenant_id=%s AND r.kind=%s AND r.id = ANY(%s)", (tenant, KIND, ids))
            rows = cur.fetchall()
    except Exception as exc:
        if type(exc).__name__ != "UndefinedTable":
            raise
        rows = []
    return {row[0]: _state_of(*row[1:], now=now) for row in rows}


def attach(conn, tenant: str, trip_id: UUID, version: int, items: list) -> None:
    _mark(state(conn, tenant, trip_id), tenant, trip_id, version, items)


def attach_many(conn, tenant: str, versions: dict, items_by_trip: dict) -> None:
    """`attach` 의 여러 여행 판 — 시험 상태를 한 번에 읽고 여행마다 같은 규칙으로 표시를 붙인다."""
    found = states(conn, tenant, list(items_by_trip))
    for trip_id, items in items_by_trip.items():
        current = found.get(str(trip_id))
        if current is not None:
            _mark(current, tenant, trip_id, versions[trip_id], items)


def _mark(current: dict, tenant: str, trip_id: UUID, version: int, items: list) -> None:
    if not current["active"] or current["base_version"] != version:
        return
    for item in items:
        if item.place and str(item.item_id) == current["item_id"]:
            body = {"tenant": tenant, "trip_id": str(trip_id), "revision": current["revision"],
                    "item_id": str(item.item_id), "place_id": str(item.place_id)}
            item.place = {**item.place, MARKER: {**body, "signature": _signature(body)}}


def _signature(body: dict) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, ("watch-simulation:" + json.dumps(body, sort_keys=True)).encode(), hashlib.sha256).hexdigest()


def resolve(place: dict) -> dict | None:
    marker = place.get(MARKER)
    if not isinstance(marker, dict):
        return None
    body = {k: v for k, v in marker.items() if k != "signature"}
    if not hmac.compare_digest(_signature(body), str(marker.get("signature", ""))):
        return None
    if str(place.get("place_id")) != body.get("place_id"):
        return None
    with get_connection() as conn:
        current = state(conn, body["tenant"], UUID(body["trip_id"]))
    if (not current["active"] or current["revision"] != body["revision"]
            or current["item_id"] != body["item_id"]):
        return None
    return {**current, "tenant": body["tenant"], "trip_id": body["trip_id"]}


def record_result(current: dict, report: dict, *, safety_only: bool) -> None:
    """실제 점검 결과를 실행별로 남긴다. 입력 저장을 처리 성공으로 표시하지 않는다."""
    key = f"{current['run_id']}:{'safety' if safety_only else 'full'}"
    if not safety_only:
        # 안전정지가 먼저 걸려 방문 점검에서 빠져도, 실제로 수행한 N종 전체 점검 이력을 남긴다.
        from app.domains.travel_ops.components.watch.monitoring import record
        record('simulation_full', trip_id=current['trip_id'], item_id=current['item_id'],
               target_title=current.get('item_title'), report=report)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO admin_records(tenant_id,kind,id,value,customer_id) "
                    "SELECT %s,'watch_simulation_result',%s,%s,customer_id FROM trips WHERE tenant_id=%s AND trip_id=%s "
                    "ON CONFLICT(tenant_id,kind,id) DO UPDATE SET value=EXCLUDED.value,updated_at=now()",
                    (current["tenant"], key, Jsonb(report), current["tenant"], UUID(current["trip_id"])))


def configure(conn, tenant: str, trip_id: UUID, *, actor: str, expected_revision: int,
              expected_version: int, item_id: UUID | None, categories: list[str], duration_minutes: int, reason: str,
              now: datetime | None = None) -> dict:
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore

    now = now or datetime.now(UTC)
    if len(categories) != len(set(categories)) or set(categories) - CATEGORIES.keys():
        raise AdminServiceError(422, "시험 종류는 6종 안에서 중복 없이 골라 주세요.")
    if not 1 <= duration_minutes <= 60 or not reason.strip():
        raise AdminServiceError(422, "시험 시간과 변경 사유를 확인해 주세요.")
    with conn.cursor() as cur:
        cur.execute("SELECT customer_id,latest_version,status FROM trips WHERE tenant_id=%s AND trip_id=%s FOR NO KEY UPDATE", (tenant, trip_id))
        trip = cur.fetchone()
    if not trip:
        raise AdminServiceError(404, "여행을 찾을 수 없습니다.")
    before = state(conn, tenant, trip_id, now=now)
    if before["revision"] != expected_revision or trip[1] != expected_version:
        raise AdminServiceError(409, "다른 변경이 먼저 저장됐습니다. 현재 여행과 설정을 다시 읽어 주세요.")
    items = TripStore(tenant).items(conn, trip_id, trip[1])
    if categories:
        _require_watched(conn, tenant, trip_id)
        if trip[2] != "active" or not any((i.ends_at or i.starts_at) > now for i in items):
            raise AdminServiceError(422, "끝나지 않은 활성 여행에서만 시험할 수 있습니다.")
        target = next((i for i in items if i.item_id == item_id), None)
        if (target is None or target.kind not in ("activity", "dining") or not target.place
                or target.place.get("latitude") is None or target.place.get("longitude") is None
                or (target.ends_at or target.starts_at) <= now):
            raise AdminServiceError(422, "끝나지 않은 방문 일정 중 위치가 있는 항목을 골라 주세요.")
        value = {"categories": [k for k in CATEGORIES if k in categories], "item_id": str(target.item_id),
                 "item_title": target.title, "base_version": trip[1], "run_id": str(uuid4()),
                 "started_at": now.isoformat(), "expires_at": (now + timedelta(minutes=duration_minutes)).isoformat()}
    else:
        value = {**before, "categories": [], "expires_at": now.isoformat()}
        value.pop("revision", None)
        value.pop("active", None)
    if before.get("run_id"):
        with conn.cursor() as cur:
            cur.execute("UPDATE pending_changes SET status='superseded',decided_at=now(),chosen_by='operator:simulation_changed' "
                        "WHERE tenant_id=%s AND trip_id=%s AND status='open' AND cause_json @> %s::jsonb",
                        (tenant, trip_id, json.dumps([{"mode":"simulation", "simulation_id":before["run_id"]}])))
    with conn.cursor() as cur:
        cur.execute("INSERT INTO admin_records(tenant_id,kind,id,value,customer_id) VALUES(%s,%s,%s,%s,%s) "
                    "ON CONFLICT(tenant_id,kind,id) DO UPDATE SET value=EXCLUDED.value,customer_id=EXCLUDED.customer_id,"
                    "revision=admin_records.revision+1,updated_at=now()", (tenant, KIND, str(trip_id), Jsonb(value), trip[0]))
    after = state(conn, tenant, trip_id, now=now)
    audit(conn, tenant, actor, "watch-simulation", str(trip_id), before, after, reason)
    return after


def _require_watched(conn, tenant: str, trip_id: UUID) -> None:
    """감시가 보지 않는 여행에는 시험을 걸지 않는다 — 저장만 되고 점검 결과 · 알림이 영영 안 생긴다. `[2026-10-16]`

    감시 대상(`TripStore._open_trips`)과 같은 두 조건: 대상 좁히기(게스트 여행 빼기 — `trip_scope`) · 재난 정지 없음."""
    from app.domains.travel_ops.components.itinerary.trip_scope import extra_sql

    with conn.cursor() as cur:
        cur.execute("SELECT " + extra_sql("t") + ", EXISTS (SELECT 1 FROM trip_safety_pauses p WHERE p.tenant_id=t.tenant_id "
                    "AND p.trip_id=t.trip_id AND p.resumed_at IS NULL) FROM trips t WHERE t.tenant_id=%s AND t.trip_id=%s", (tenant, trip_id))
        row = cur.fetchone()
    if row and not row[0]:
        raise AdminServiceError(422, "로그인하지 않은 손님(게스트) 여행은 감시 대상이 아니라 시험 입력이 반영되지 않습니다. "
                                     "소셜 로그인으로 연결한 회원의 여행을 골라 주세요.")
    if row and row[1]:
        raise AdminServiceError(409, "재난 정지 중인 여행은 감시가 쉬고 있어 시험 입력이 반영되지 않습니다. "
                                     "고객 앱에서 「다시 시작」한 뒤 시험해 주세요.")


def inputs(current: dict, place: dict, *, safety_only: bool = False) -> dict[str, dict]:
    """실제로 선택한 종류만 대체한다. 예보는 기존 수치→주의 판정기를 이용한다."""
    from app.domains.travel_ops.ports.data_sources.disruptions import forecast_advisories, _default_limits

    stamp = current["started_at"]
    common = {"source": SOURCE, "mode": "simulation", "simulation_id": current["run_id"]}
    sensitive = place.get("weather_sensitive") is not False
    causes = {
        "weather_warning": {"kind": "[시뮬레이션] 호우주의보", "areas": ["대상 일정 지역"], "announced_at": stamp},
        "disaster_msg": {"kind": "화재", "step": "긴급재난", "text": "[시뮬레이션] 대상 일정 주변 화재 발생. 시험용 상황입니다.", "created_at": stamp},
        "traffic_control": {"kind": "[시뮬레이션] 전면 통제", "road": "대상 장소 진입 도로", "distance_m": 0, "message": "[시뮬레이션] 통행 중단"},
        "air_quality": {"kind": "[시뮬레이션] PM2.5 경보 기준 초과", "value": 150, "limit": 75, "station": "시험 측정소"},
        "earthquake": {"kind": "[시뮬레이션] 규모 5 지진", "magnitude": 5.0, "distance_km": 0, "location": "[시뮬레이션] 대상 일정 지역", "at": stamp},
    }
    rows = {}
    for category in current["categories"]:
        if safety_only and category not in ("disaster_msg", "earthquake"):
            continue
        base = {"category": category, "status": "ok", "confirmed_at": stamp, **common}
        if category in ("forecast", "weather_warning", "air_quality") and not sensitive:
            rows[category] = {**base, "status": "not_applicable", "reason": "실내 일정에는 적용되지 않는 시험 입력"}
        elif category == "forecast":
            value = {"precipitation_probability": 100, "wind_speed_kmh": 100, **common}
            pop, wind = _default_limits()
            notes = forecast_advisories(value, pop_limit=pop, wind_limit=wind)
            rows[category] = {**base, "value": value, "_advisories": [{**n, **common} for n in notes]}
        else:
            rows[category] = {**base, "_disruptions": [{"category": category, **causes[category], **common}]}
    return rows


def mark_notice(conn, tenant: str, trip_id: UUID, payload: dict) -> dict:
    current = state(conn, tenant, trip_id)
    causes = list(payload.get("causes") or [])
    if payload.get("pause_id"):
        with conn.cursor() as cur:
            cur.execute("SELECT event_json FROM trip_safety_pauses WHERE tenant_id=%s AND trip_id=%s AND pause_id=%s",
                        (tenant, trip_id, payload["pause_id"]))
            row = cur.fetchone()
            if row:
                causes.append(row[0])
    if payload.get("version") is not None:
        with conn.cursor() as cur:
            cur.execute("SELECT cause_json FROM itinerary_versions WHERE tenant_id=%s AND trip_id=%s AND version=%s",
                        (tenant, trip_id, payload["version"]))
            row = cur.fetchone()
            causes += (row[0] or []) if row else []
    simulated = next((c for c in causes if isinstance(c, dict) and c.get("mode") == "simulation"), None)
    if not (current["active"] or simulated):
        return payload
    return stamp_notice(payload, (simulated or {}).get("simulation_id") or current.get("run_id"))


def stamp_notice(payload: dict, run_id: str | None) -> dict:
    text = str(payload.get("text") or "")
    return {**payload, "simulation": True, "simulation_id": run_id,
            "text": text if text.startswith("[시뮬레이션]") else "[시뮬레이션] " + text}


def case_place(conn, *, tenant: str, customer_id: UUID, case_id: UUID, place: dict) -> dict:
    """도구 호출의 여행 범위는 모델 인자가 아닌, 확인된 접수의 대상으로부터 얻는다."""
    with conn.cursor() as cur:
        cur.execute("SELECT state_json->'subject_ref'->>'id' FROM customer_cases "
                    "WHERE tenant_id=%s AND customer_id=%s AND case_id=%s", (tenant, customer_id, case_id))
        row = cur.fetchone()
    if not row or not row[0]:
        return place
    try:
        trip_id = UUID(row[0])
    except ValueError:
        return place
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    try:
        trip, items = TripStore(tenant).latest(conn, trip_id)
    except KeyError:
        return place
    if str(trip['customer_id']) != str(customer_id):
        return place
    return next((i.place for i in items if i.place and str(i.place_id) == str(place.get("place_id")) and MARKER in i.place), place)
