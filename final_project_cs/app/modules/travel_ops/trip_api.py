# -*- coding: utf-8 -*-
"""여행 API — 일정 등록 · 조회 · 고객 신고 · 재요청(다른 안 · 되돌림) · 계획서 링크.

★**왜 `app/modules/` 에 있나** — presentation 은 도메인을 import 하지 못한다
  (INV-CS-ARCH-001, `tests/architecture/test_basement_is_domain_free.py`). 라우터를
  여기서 만들고 `composition.build_domain_routers()` 가 앱에 넣는다. Composer 라우터를
  주입하는 것과 같은 모양이다.

★접점 둘(v11 §1):
    ① 개인 에이전트 API   `/v1/trips/*`            Bearer + scope(`trip:read`·`trip:write`)
    ② 여행계획서 링크      `/plan/{trip_id}?t=…`    로그인 없음 · 여행별 토큰(HMAC)

★`[2026-09-22]` ②와 **같은 모양의 링크가 하나 더** 있다 — 업체 예약 변경 링크
  `/booking-change/{booking_id}?t=…`(예약별 토큰, v11 §4-C · DoD-16·17). 접점을 늘린 것이
  아니라 ② 안의 한 장면이다: 우리 일정은 고쳐 두고 **업체 건만** 고객이 직접 진행하도록 넘긴다.

★**상태의 정본은 링크다.** 통지를 못 봐도 링크에서 맞는 것을 본다 — 링크는 매번
  최신 버전을 읽는다(DoD-25). 통지가 닿았는지는 사양에 넣지 않는다.

★**같은 요청을 두 번 받아 두 번 고치지 않는다.** 등록은 `request_id` 로 만든 멱등 키,
  신고·재요청은 원인 칸에 남긴 `request_id` 로 막는다(`TripStore.version_for_request`).

`[미구현]` 고객 **자유 문장**을 Case → 분류 → 여기로 잇는 배선. 지금 신고는
  **구조화된 몸통**(`type`·`minutes`·`products`)으로 들어온다 — 에이전트가 옮겨 보낸다.
`[미구현]` 계획서의 고객 언어 생성(결정 14). 지금은 한국어 원문을 보인다.
"""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import hmac
import html
import json
from typing import Any, Callable, Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core import settings as settings_module
from app.core.idempotency import idempotency_key

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


class PlanIn(BaseModel):
    """★`[2026-09-22]` **일정 생성 요청** — v11 §4-A(「계획 생성은 우리 일이 아니다」)를 뒤집는
    경로다. 사용자 지시로 만들었고, 계획서는 읽기 전용이라 고치지 않았다. 뒤집는다는 사실과
    이 생성기가 못 하는 것은 리포트에 적었다.

    ★**`register` 기본값은 `false` 다.** 등록은 여행 상태를 만들고 **통지를 내보낸다**(계획서
      링크가 처음 나가는 자리, v11 §6-B). 초안을 보자고 부른 요청이 조용히 고객에게 링크를
      보내면 안 된다 — 에이전트가 초안을 보고 **명시적으로** `register:true` 를 보낼 때만 등록한다.
    """

    #: ★칸 이름은 `register_now` 인데 **바깥 이름은 `register`** 다. 둘을 가르는 이유:
    #:  `register` 를 필드 이름으로 쓰면 `BaseModel` 의 이름을 가려 pydantic 이 경고하고,
    #:  `Field(alias=...)` 로 붙이면 FastAPI 가 몸통 모델을 다시 감쌀 때
    #:  `UnsupportedFieldAttributeWarning` 이 매 요청마다 뜬다(둘 다 실측). 그래서 **받기 전에
    #:  이름만 옮긴다** — 바깥 계약(`register`)은 그대로 두고 경고도 남기지 않는다.
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1)
    customer_id: UUID
    city: str = "서울"
    start_date: date
    days: int = Field(ge=1, le=7)
    party_size: int = Field(ge=1, le=4)
    locale: str | None = None
    title: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    #: 고객의 자유 문장. 예 「실내 위주, 아이 동반, 매운 음식 싫어요」
    preferences: str = ""
    register_now: bool = False

    @model_validator(mode="before")
    @classmethod
    def _accept_register(cls, data: Any) -> Any:
        if isinstance(data, dict) and "register" in data:
            # ★`{**data, ...}` 로 쓰면 `**data` 가 먼저 펴져 `register` 가 그대로 남고
            #   `extra="forbid"` 에 걸린다(실측 — 422 가 났다). 복사한 뒤 옮긴다.
            data = dict(data)
            data["register_now"] = data.pop("register")
        return data


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


def _place_view(key: str | None, places: list[Any]) -> dict[str, Any] | None:
    """등록 요청 안의 장소를 판정기가 읽는 모양으로. 저장 전이라 DB 를 보지 않는다."""
    if key is None:
        return None
    for place in places:
        if place.key == key:
            return {"name": place.name, "attributes": dict(place.attributes or {})}
    return None


def _error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status, {"error": {"code": code, "message": message, **extra}})


def _seoul(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment.replace(tzinfo=KST) if moment.tzinfo is None else moment


# ── 계획서 링크 ──────────────────────────────────────────────────
# ★`[2026-09-20]` 구현은 `plan_link.py` 로 옮겼다 — 통지·안내를 만드는 쪽이 FastAPI 를 끌고 오지
#   않고 링크를 붙일 수 있게. 여기서 다시 내보내므로 부르는 쪽은 안 바뀐다.
from .change_link import change_token, change_url, change_view, render_change  # noqa: E402
from .itinerary_checks import Part, check_itinerary, parts_from_items
from .density import measure_density
from .plan_link import plan_token, plan_url        # noqa: E402  (자리를 지켜 읽기 쉽게 둔다)
from .route_uses import route_problems  # noqa: E402


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
            "history": history, "plan_url": plan_url(store.tenant_id, trip["trip_id"]),
            **measure_density(parts_from_items(items), trip.get("constraints") or {})}


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
                      chat_factory: Callable[[], Any] | None = None,
                      place_factory: Callable[[], Any] | None = None) -> APIRouter:
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
        return _create_trip(principal.tenant_id, request)

    def _create_trip(tenant: str, request: CreateTrip) -> dict[str, Any]:
        """★등록의 **유일한** 본문이다. `/v1/trips` 도 `/v1/trips/plan?register=true` 도 여기로
        들어온다 — 생성기가 판정을 건너뛰는 길을 만들지 않으려고 하나로 둔다."""
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
        # ★`[2026-09-23]` `uses` 표기를 **받을 때** 본다. 이 값은 운행·통제 사건과 문자열로
        #   대조돼서, 표기가 다르면 사건이 있어도 못 잡고 오류도 안 난다 — 전에는 `잠실역`·
        #   `02호선`·`버스:성수동` 을 그대로 받아 두고 나중에 조용히 놓쳤다. 틀린 값을 **전부**
        #   이유와 함께 돌려준다. 계약 `wiki/external/rest-endpoints.md` 「options[].uses」 절.
        bad_uses = route_problems(request.routes)
        if bad_uses:
            raise _error(422, "invalid_route_uses",
                         f"routes 의 uses 표기 {len(bad_uses)}건이 계약과 다르다 — 이대로 받으면 "
                         "그 구간의 운행·통제 사건을 대조하지 못한다", problems=bad_uses)
        # ★`[2026-09-21]` 받을 때 **코드로 판정**한다(v11 §12 DoD-2). 불가능하면 이유와 완화 조건을
        #   붙여 거절한다(DoD-3) — 전에는 참조·순서만 보고 그대로 받아 감시가 뒤에서 고쳤다.
        violations = check_itinerary(
            [Part(seq=it.seq, kind=it.kind, title=it.title, starts_at=_seoul(it.starts_at),
                  ends_at=_seoul(it.ends_at),
                  place=_place_view(it.place, request.places), route=request.routes.get(str(it.route)),
                  detail=it.detail)
             for it in request.items],
            constraints=request.constraints, party_size=request.party_size)
        if violations:
            raise _error(422, "itinerary_infeasible",
                         "이 일정은 그대로 수행할 수 없습니다: "
                         + " / ".join(v.reason for v in violations),
                         violations=[v.as_dict() for v in violations])
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

    @router.post("/v1/trips/plan")
    def plan_draft(request: PlanIn, principal: Principal = Depends(require_scope("trip:write"))):
        """요청 → 초안 일정 → **판정 통과** → (원하면) 등록. v11 §4-A 를 뒤집는 경로다.

        ★**판정을 건너뛰는 길이 없다.** 생성기가 `check_itinerary` 로 스스로 판정해 고치고,
          등록하면 `_create_trip` 이 **같은 판정기를 한 번 더** 돌린다.
        ★**멱등** — 같은 `request_id` 로 등록까지 두 번 오면 모델도 부르지 않고 이미 만든
          여행을 그대로 돌려준다(`trips.request_key`).
        """
        from . import planner as planner_module

        tenant = principal.tenant_id
        store = TripStore(tenant)
        key = idempotency_key(tenant_id=tenant, request_id=request.request_id,
                              action_type="trip.create", business_subject=str(request.customer_id))
        if request.register_now:
            with get_connection() as conn:
                existing = store.by_request_key(conn, key)
                if existing is not None:
                    return {"status": "duplicate", "created": False,
                            "trip": _trip_view(conn, store, existing[0])}
        ask = planner_module.PlanRequest(
            city=request.city, start_date=request.start_date, days=request.days,
            party_size=request.party_size, constraints=request.constraints,
            preferences=request.preferences, title=request.title, locale=request.locale)
        try:
            with get_connection() as conn:
                outcome = planner_module.plan_trip(conn=conn, tenant_id=tenant, request=ask,
                                                   chat=_lazy("chat", chat_factory),
                                                   tour_api=_lazy("place", place_factory))
        except planner_module.PlanRefused as refused:
            raise _error(422, refused.code, refused.message, **refused.detail) from None
        result: dict[str, Any] = {"status": "drafted", **outcome.as_dict()}
        if request.register_now:
            body = outcome.draft.as_create_body(request_id=request.request_id,
                                                customer_id=request.customer_id)
            result = {**result, "status": "registered",
                      "trip": _create_trip(tenant, CreateTrip.model_validate(body))}
        return result

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
        """★로그인 없는 링크. 토큰이 틀리면 **있는지도 말하지 않는다**(404).

        ★`[2026-09-22]` 여행이 **어느 테넌트 것인지 먼저 찾아** 그 테넌트로 토큰을 맞춘다. 전에는
          설정된 테넌트 하나로만 맞춰서, 다른 테넌트의 여행(시나리오 모드의 전용 테넌트)은 통지에
          링크가 실려 나가도 **404** 였다 — 화면에서 링크를 눌러 보고 찾았다.
        ★이 한 줄만 테넌트 조건 없이 읽는다(`CLAUDE.md` §1 의 예외). 이 경로에서는 **링크가 곧
          자격**이고, 여기서 얻는 것은 테넌트 문자열 하나뿐이다. 그 뒤 모든 조회는 그 테넌트로 묶고,
          토큰이 틀리면 여행이 있든 없든 404 다.
        """
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT tenant_id FROM trips WHERE trip_id=%s", (trip_id,))
            row = cur.fetchone()
        tenant = row[0] if row else settings_module.get_settings().tenant_id
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

    @router.get("/booking-change/{booking_id}")
    def booking_change(booking_id: UUID, t: str = Query(...), format: str | None = Query(None)):
        """업체 예약 **변경 링크**(v11 §4-C · §12 DoD-16·17).

        ★계획서 링크와 같은 모양이다 — 로그인 없음 · 토큰이 틀리면 **있는지도 말하지 않는다**(404)
          · 예약이 **어느 테넌트 것인지 먼저 찾아** 그 테넌트로 토큰을 맞춘다.
        ★**아무것도 쓰지 않는다.** 그래서 승인도 scope 도 없다 — 업체 예약을 바꾸는 것은 고객이
          업체 쪽에서 하고, 우리는 무엇을·어떤 대안으로·얼마 차이로 바꿔야 하는지만 보인다.
        ★이 한 줄만 테넌트 조건 없이 읽는다(`CLAUDE.md` §1 의 예외 — 계획서 링크와 같은 이유).
          이 경로에서는 **링크가 곧 자격**이고 여기서 얻는 것은 테넌트 문자열 하나뿐이다.
        """
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT tenant_id FROM bookings WHERE booking_id=%s", (booking_id,))
            row = cur.fetchone()
        tenant = row[0] if row else settings_module.get_settings().tenant_id
        if not hmac.compare_digest(t, change_token(tenant, booking_id)):
            raise _error(404, "not_found", "resource not found")
        with get_connection() as conn:
            view = change_view(conn, tenant_id=tenant, booking_id=booking_id)
        if view is None:
            raise _error(404, "not_found", "resource not found")
        if format == "json":
            return JSONResponse(view)
        return HTMLResponse(render_change(view))

    return router


__all__ = ["build_trip_router", "change_token", "change_url", "plan_token", "plan_url"]
