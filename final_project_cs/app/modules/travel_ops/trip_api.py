# -*- coding: utf-8 -*-
"""여행 API — 일정 등록 · 조회 · 고객 신고 · 재요청(다른 안 · 되돌림) · 계획서 링크.

★**왜 `app/modules/` 에 있나** — presentation 은 도메인을 import 하지 못한다
  (INV-CS-ARCH-001, `tests/architecture/test_basement_is_domain_free.py`). 라우터를
  여기서 만들고 `composition.build_domain_routers()` 가 앱에 넣는다. Composer 라우터를
  주입하는 것과 같은 모양이다.

★접점 둘(v11 §1):
    ① 개인 에이전트 API   `/v1/trips/*`            Bearer + scope(`trip:read`·`trip:write`)
    ② 여행계획서 링크      `/plan/{trip_id}?t=…`    로그인 없음 · 여행별 토큰(HMAC)

★**상태의 정본은 링크다.** 통지를 못 봐도 링크에서 맞는 것을 본다 — 링크는 매번
  최신 버전을 읽는다(DoD-25). 통지가 닿았는지는 사양에 넣지 않는다.

★**같은 요청을 두 번 받아 두 번 고치지 않는다.** 등록은 `request_id` 로 만든 멱등 키,
  신고·재요청은 원인 칸에 남긴 `request_id` 로 막는다(`TripStore.version_for_request`).

`[미구현]` 고객 **자유 문장**을 Case → 분류 → 여기로 잇는 배선. 지금 신고는
  **구조화된 몸통**(`type`·`minutes`·`products`)으로 들어온다 — 에이전트가 옮겨 보낸다.
`[미구현]` 계획서의 고객 언어 생성(결정 14). 지금은 한국어 원문을 보인다.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
import html
import json
from typing import Any, Callable, Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core import settings as settings_module
from app.core.idempotency import idempotency_key
import json

from app.infrastructure.db.session import get_connection
from app.presentation.security import Principal, require_scope

from .itinerary import Item, TripStore
from .trip_desk import TripDesk

#: ★대상 도시는 서울 하나다(v11 §1). 시간대 없이 온 시각은 서울 시각으로 읽는다.
KST = ZoneInfo("Asia/Seoul")

CheckFactory = Callable[[], Callable[..., dict[str, Any]]]


class PlaceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    lat: float
    lon: float
    weather_sensitive: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seq: int
    kind: str = Field(min_length=1)
    title: str = Field(min_length=1)
    place: str | None = None          # places[].key
    starts_at: datetime
    ends_at: datetime | None = None
    route: str | None = None          # routes 의 키 — 이동 항목
    detail: dict[str, Any] = Field(default_factory=dict)


class CreateTrip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1)
    customer_id: UUID
    title: str = Field(min_length=1)
    locale: str | None = None
    party_size: int | None = Field(default=None, ge=1)
    constraints: dict[str, Any] = Field(default_factory=dict)
    places: list[PlaceIn] = Field(default_factory=list)
    items: list[ItemIn] = Field(min_length=1)
    routes: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1)
    type: Literal["delay", "closed", "stock_out"]
    message: str = Field(min_length=1)
    at: datetime | None = None
    minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    products: list[str] = Field(default_factory=list)


class AlternateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1)
    base_version: int = Field(ge=1)
    choice: str | None = None
    message: str | None = None


class MessageIn(BaseModel):
    """고객 **자유 문장** — 에이전트가 옮기지 않고 그대로 보낸다."""
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    at: datetime | None = None


class RollbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1)
    base_version: int = Field(ge=1)
    to_version: int = Field(ge=1)
    message: str | None = None


def _error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status, {"error": {"code": code, "message": message, **extra}})


def _seoul(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment.replace(tzinfo=KST) if moment.tzinfo is None else moment


# ── 계획서 링크 ──────────────────────────────────────────────────
def plan_token(tenant_id: str, trip_id: UUID | str) -> str:
    """여행별 토큰. ★저장하지 않는다 — 비밀 키로 매번 다시 계산해 맞춰 본다."""
    secret = settings_module.get_settings().secret_key.encode()
    return hmac.new(secret, f"plan:{tenant_id}:{trip_id}".encode(), hashlib.sha256).hexdigest()[:32]


def plan_url(tenant_id: str, trip_id: UUID | str) -> str:
    base = settings_module.get_settings().public_base_url.rstrip("/")
    return f"{base}/plan/{trip_id}?t={plan_token(tenant_id, trip_id)}"


# ── 보기 ────────────────────────────────────────────────────────
def _item_view(item: Item) -> dict[str, Any]:
    return {"item_id": str(item.item_id), "seq": item.seq, "kind": item.kind,
            "title": item.title, "place": (item.place or {}).get("name"),
            "starts_at": item.starts_at.isoformat(),
            "ends_at": item.ends_at.isoformat() if item.ends_at else None,
            "changed": item.replaces_item_id is not None,
            "other_options": [{"key": a["key"], "name": a.get("option_label") or a["name"]}
                              for a in item.detail.get("alternates") or []],
            "customer_pinned": bool(item.detail.get("customer_pinned"))}


_CAUSE_FIELDS = ("category", "type", "kind", "summary", "message", "to_version", "mode")


def _trip_view(conn, store: TripStore, trip_id: UUID) -> dict[str, Any]:
    trip, items = store.latest(conn, trip_id)
    history = [{"version": row["version"], "reason": row["reason"],
                "causes": [{k: cause.get(k) for k in _CAUSE_FIELDS if cause.get(k) is not None}
                           for cause in (row["causes"] or [])],
                "at": row["created_at"].isoformat()}
               for row in store.versions(conn, trip_id)]
    return {"trip_id": str(trip["trip_id"]), "customer_id": str(trip["customer_id"]),
            "title": trip["title"], "locale": trip["locale"], "party_size": trip["party_size"],
            "version": trip["version"], "items": [_item_view(item) for item in items],
            "history": history, "plan_url": plan_url(store.tenant_id, trip["trip_id"])}


#: ★고객이 보는 화면에 내부 이름(`customer_report · delay`)을 그대로 싣지 않는다 —
#:  브라우저로 열어 보고 고쳤다(2026-09-14). 모르는 값은 원래 이름을 그대로 보인다.
_REASON_LABELS = {"created": "등록", "auto_adjusted": "자동 변경", "customer_report": "고객 신고",
                  "customer_request": "고객 요청", "rollback": "되돌림"}
_CAUSE_LABELS = {"delay": "늦어짐", "closed_today": "당일 휴무", "stock_out": "품절",
                 "alternate": "다른 안으로 교체", "rollback": "옛 버전으로",
                 "air_quality": "대기질", "weather_warning": "기상특보", "forecast": "날씨",
                 "route_event": "교통 통제·운행 변경", "disaster_msg": "재난문자",
                 "traffic_control": "교통 통제"}


def _cause_label(cause: dict[str, Any]) -> str:
    if cause.get("summary"):
        return str(cause["summary"])
    for key in ("type", "category"):
        if cause.get(key) in _CAUSE_LABELS:
            return _CAUSE_LABELS[cause[key]]
    return str(cause.get("kind") or cause.get("type") or cause.get("category") or "")


def _render_plan(view: dict[str, Any]) -> str:
    esc = lambda value: html.escape(str(value or ""))  # noqa: E731
    rows = []
    for item in view["items"]:
        start = item["starts_at"][11:16]
        end = (item["ends_at"] or "")[11:16]
        badge = '<span class="badge">변경됨</span>' if item["changed"] else ""
        others = ""
        if item["other_options"]:
            others = ('<div class="others">다른 안: '
                      + ", ".join(esc(o["name"]) for o in item["other_options"]) + "</div>")
        rows.append(f'<li><div class="time">{start}–{end}</div><div><div class="title">'
                    f'{esc(item["title"])} {badge}</div>{others}</div></li>')
    changes = "".join(
        f"<li>버전 {h['version']} · {esc(_REASON_LABELS.get(h['reason'], h['reason']))}"
        + "".join(f" · {esc(_cause_label(c))}" for c in h["causes"]) + "</li>"
        for h in reversed(view["history"]))
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(view['title'])}</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6b66;--line:#e4e1d8;--accent:#2f6f4f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161614;--fg:#ecebe6;--muted:#a3a29b;--line:#34332f;--accent:#7cc4a0}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:40rem;margin:0 auto;padding:1.25rem}}
h1{{font-size:1.3rem;margin:.2rem 0}} .meta{{color:var(--muted);font-size:.85rem}}
ul{{list-style:none;padding:0;margin:1rem 0}}
.plan li{{display:grid;grid-template-columns:6.5rem 1fr;gap:.5rem;padding:.6rem 0;border-bottom:1px solid var(--line)}}
.time{{font-variant-numeric:tabular-nums;color:var(--muted)}}
.badge{{font-size:.72rem;border:1px solid var(--accent);color:var(--accent);border-radius:.3rem;padding:0 .3rem}}
.others{{color:var(--muted);font-size:.85rem}} h2{{font-size:1rem;margin-top:1.5rem}}
.hist li{{color:var(--muted);font-size:.85rem;padding:.15rem 0}}
</style></head><body><main>
<h1>{esc(view['title'])}</h1>
<div class="meta">일정 버전 {view['version']} · 이 페이지가 최신 일정입니다</div>
<ul class="plan">{''.join(rows)}</ul>
<h2>바뀐 기록</h2><ul class="hist">{changes}</ul>
</main></body></html>"""


# ── 결과 → HTTP ─────────────────────────────────────────────────
_CONFLICTS = {"stale": "stale_itinerary", "no_alternate": "no_alternate",
              "unknown_choice": "unknown_choice", "conflicts_next": "conflicts_next",
              "alternate_invalid": "alternate_invalid", "invalid_version": "invalid_version"}


def _outcome(outcome: dict[str, Any]) -> dict[str, Any]:
    status = outcome.get("status")
    if status == "not_found":
        raise _error(404, "not_found", "resource not found")
    if status in _CONFLICTS:
        details = {k: v for k, v in outcome.items() if k in ("version", "choices", "next", "verdict")}
        raise _error(409, _CONFLICTS[status], f"request not applied: {status}", **details)
    return outcome


def build_trip_router(*, check_factory: CheckFactory | None = None,
                      classifier_factory: Callable[[], Any] | None = None,
                      chat_factory: Callable[[], Any] | None = None) -> APIRouter:
    """★점검기·분류기·추출용 LLM 은 **처음 쓸 때** 만든다 — 앱 기동이 기다리지 않게."""
    router = APIRouter()
    cache: dict[str, Any] = {}

    def _lazy(name: str, factory: Callable[[], Any] | None):
        if factory is None:
            return None
        if name not in cache:
            cache[name] = factory()
        return cache[name]

    def _check():
        return _lazy("check", check_factory)

    def _desk(store: TripStore) -> TripDesk:
        return TripDesk(store=store, connection_factory=get_connection, check=_check())

    def _trip_or_404(conn, store: TripStore, trip_id: UUID, customer_id: UUID | None = None):
        try:
            trip, _ = store.latest(conn, trip_id)
        except KeyError:
            raise _error(404, "not_found", "resource not found") from None
        if customer_id is not None and trip["customer_id"] != customer_id:
            raise _error(404, "not_found", "resource not found")
        return trip

    def _already(store: TripStore, trip_id: UUID, request_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            _trip_or_404(conn, store, trip_id)
            done = store.version_for_request(conn, trip_id, request_id)
        return None if done is None else {"status": "duplicate", "version": done}

    @router.post("/v1/trips", status_code=201)
    def create(request: CreateTrip, principal: Principal = Depends(require_scope("trip:write"))):
        tenant = principal.tenant_id
        store = TripStore(tenant)
        keys = [p.key for p in request.places]
        if len(set(keys)) != len(keys):
            raise _error(422, "duplicate_place_key", "places[].key must be unique")
        if len({it.seq for it in request.items}) != len(request.items):
            raise _error(422, "duplicate_seq", "items[].seq must be unique")
        for it in request.items:
            if it.place is not None and it.place not in keys:
                raise _error(422, "unknown_place", f"item {it.seq} refers to unknown place")
            if it.route is not None and it.route not in request.routes:
                raise _error(422, "unknown_route", f"item {it.seq} refers to unknown route")
        key = idempotency_key(tenant_id=tenant, request_id=request.request_id,
                              action_type="trip.create", business_subject=str(request.customer_id))
        body_sha = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    # ★동시에 온 같은 등록 둘이 둘 다 「없다」를 보지 않게 잠근다(cases.py 와 같다).
                    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{tenant}:{key}",))
                existing = store.by_request_key(conn, key)
                if existing is not None:
                    trip_id, stored_sha = existing
                    if stored_sha != body_sha:
                        raise _error(409, "idempotency_key_reused",
                                     "same request_id was used for a different body")
                    created = False
                else:
                    trip_id = _insert(conn, store, request, key, body_sha)
                    created = True
            view = _trip_view(conn, store, trip_id)
        return {**view, "created": created}

    def _insert(conn, store: TripStore, request: CreateTrip, key: str, body_sha: str) -> UUID:
        tenant = store.tenant_id
        ids: dict[str, UUID] = {}
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM customers WHERE tenant_id=%s AND customer_id=%s",
                        (tenant, request.customer_id))
            if cur.fetchone() is None:
                raise _error(404, "not_found", "customer not found")
            for place in request.places:
                # ★장소는 테넌트 안에서 (이름, 종류)로 하나다(UNIQUE). 이미 있으면 **그것을 쓴다.**
                #   ☆2026-09-14 — 처음엔 무조건 INSERT 해서, 두 번째 여행이 경복궁을 적자
                #     500 이 났다(개발 서버에서 발견. 시험은 여행마다 테넌트를 새로 만들어
                #     못 잡았다). 보낸 속성은 **빈 칸만 채운다** — 카탈로그 값을 고객 한 명의
                #     제출이 덮어쓰지 않게(`EXCLUDED || places` 는 오른쪽이 이긴다).
                cur.execute(
                    "INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,"
                    "attributes) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (tenant_id, name, kind) DO UPDATE "
                    "SET attributes = EXCLUDED.attributes || places.attributes "
                    "RETURNING place_id",
                    (tenant, place.name, place.kind, place.lat, place.lon, place.weather_sensitive,
                     json.dumps(place.attributes, ensure_ascii=False)))
                ids[place.key] = cur.fetchone()[0]
        items = [Item(item_id=uuid4(), seq=it.seq, kind=it.kind, title=it.title,
                      place_id=ids.get(it.place) if it.place else None,
                      starts_at=_seoul(it.starts_at), ends_at=_seoul(it.ends_at),
                      detail={**it.detail,
                              **({"route": it.route, "route_def": request.routes[it.route]}
                                 if it.route else {})})
                 for it in request.items]
        trip_id, version = store.create_trip(
            conn, customer_id=request.customer_id, title=request.title, locale=request.locale,
            party_size=request.party_size, items=items, constraints=request.constraints,
            request_key=key, request_sha256=body_sha)
        # ★알림 ① 은 **생성도 포함**한다 — 링크가 처음 나가는 자리다(v11 §6-B).
        url = plan_url(tenant, trip_id)
        store.enqueue_notice(conn, trip_id=trip_id, version=version, payload={
            "text": f"여행 일정이 준비되었습니다 — {request.title}. 계획서: {url}",
            "language": "ko", "causes": [], "changed": None, "other_options": [],
            "replay": False, "version": version, "plan_url": url})
        return trip_id

    @router.get("/v1/trips/{trip_id}")
    def detail(trip_id: UUID, customer_id: UUID | None = Query(None),
               principal: Principal = Depends(require_scope("trip:read"))):
        store = TripStore(principal.tenant_id)
        with get_connection() as conn:
            _trip_or_404(conn, store, trip_id, customer_id)
            return _trip_view(conn, store, trip_id)

    @router.post("/v1/trips/{trip_id}/reports")
    def report(trip_id: UUID, request: ReportIn,
               principal: Principal = Depends(require_scope("trip:write"))):
        store = TripStore(principal.tenant_id)
        duplicate = _already(store, trip_id, request.request_id)
        if duplicate:
            return duplicate
        desk = _desk(store)
        at = _seoul(request.at) or datetime.now(KST)
        if request.type == "delay":
            if request.minutes is None:
                raise _error(422, "validation_error", "delay needs minutes")
            outcome = desk.report_delay(trip_id=trip_id, at=at, minutes=request.minutes,
                                        message=request.message, request_id=request.request_id)
        elif request.type == "closed":
            outcome = desk.report_closed(trip_id=trip_id, at=at, message=request.message,
                                         request_id=request.request_id)
        else:
            if not request.products:
                raise _error(422, "validation_error", "stock_out needs products")
            outcome = desk.ask_nearby_store(trip_id=trip_id, at=at, products=request.products,
                                            message=request.message, request_id=request.request_id)
        return _outcome(outcome)

    @router.post("/v1/trips/{trip_id}/messages")
    def message(trip_id: UUID, request: MessageIn,
                principal: Principal = Depends(require_scope("trip:write"))):
        """고객 자유 문장 → **Case → 분류 → 추출 → 여행 창구 → Case 닫기**(v11 §5 경로).

        ★처리 규칙은 `trip_messages.handle_trip_message` 한 곳에 있다 — 시나리오 모드도
          같은 것을 쓴다(한 규칙이 두 벌로 갈라지지 않게).
        """
        from .trip_messages import TripNotFound, handle_trip_message

        store = TripStore(principal.tenant_id)
        try:
            return handle_trip_message(
                tenant=principal.tenant_id, trip_id=trip_id, request_id=request.request_id,
                message=request.message, at=_seoul(request.at) or datetime.now(KST),
                classifier=_lazy("classifier", classifier_factory),
                chat=_lazy("chat", chat_factory), desk=_desk(store), actor_id=principal.key_id)
        except TripNotFound:
            raise _error(404, "not_found", "resource not found") from None

    @router.post("/v1/trips/{trip_id}/items/{item_id}/alternate")
    def alternate(trip_id: UUID, item_id: UUID, request: AlternateIn,
                  principal: Principal = Depends(require_scope("trip:write"))):
        store = TripStore(principal.tenant_id)
        duplicate = _already(store, trip_id, request.request_id)
        if duplicate:
            return duplicate
        return _outcome(_desk(store).swap_alternate(
            trip_id=trip_id, item_id=item_id, base_version=request.base_version,
            choice=request.choice, message=request.message, request_id=request.request_id))

    @router.post("/v1/trips/{trip_id}/rollback")
    def rollback(trip_id: UUID, request: RollbackIn,
                 principal: Principal = Depends(require_scope("trip:write"))):
        store = TripStore(principal.tenant_id)
        duplicate = _already(store, trip_id, request.request_id)
        if duplicate:
            return duplicate
        return _outcome(_desk(store).rollback(
            trip_id=trip_id, base_version=request.base_version, to_version=request.to_version,
            message=request.message, request_id=request.request_id))

    @router.get("/plan/{trip_id}")
    def plan(trip_id: UUID, t: str = Query(...), format: str | None = Query(None)):
        """★로그인 없는 링크. 토큰이 틀리면 **있는지도 말하지 않는다**(404)."""
        tenant = settings_module.get_settings().tenant_id
        if not hmac.compare_digest(t, plan_token(tenant, trip_id)):
            raise _error(404, "not_found", "resource not found")
        store = TripStore(tenant)
        with get_connection() as conn:
            _trip_or_404(conn, store, trip_id)
            view = _trip_view(conn, store, trip_id)
        view.pop("customer_id", None)          # ★링크를 받은 사람에게 내부 id 를 보이지 않는다
        if format == "json":
            return JSONResponse(view)
        return HTMLResponse(_render_plan(view))

    return router


__all__ = ["build_trip_router", "plan_token", "plan_url"]
