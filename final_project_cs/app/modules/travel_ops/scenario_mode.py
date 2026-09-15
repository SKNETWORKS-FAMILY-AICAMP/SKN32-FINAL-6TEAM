# -*- coding: utf-8 -*-
"""시나리오 모드 — 확정 시나리오 하루를 **실제 시스템으로** 돌린다(운영콘솔 스위치로 켠다).

`team_branch/jh/확정_시나리오_액티비티_수정_버전.md` 의 하루를 장면 11개로 나눠, 장면마다
재생 시계를 옮기고 **제품 코드가 실제로** 판단하게 한다:

    시스템 사건(액-02 · 이동-B1 · 이동-A6)  감시 루프(`TripWatcher`) + 재생 소스
    고객 사건(요식-P3 · 요식-P7 · 액-08)     사용자 화면 채팅 → Gemma 4 → Case → 여행 창구
    「다른 안으로 바꿔 줘」                  재요청(`TripDesk.swap_alternate`)
    하루 시작·출발·하루 정리 안내            일정·버전 이력에서 만든 안내(v11 §6-B ②·③)

★사건은 **사후에 정한 재생 입력**이다 — 통지에 `[재생]` 이 붙고 `mode="replay"` 가 따라간다
  (v11 §8-A). 대응(대안 고르기·문구·버전·Case)은 전부 실제 코드가 만든다. 채팅의 답은
  통지·Case 답에서 온다 — 이 파일은 문장을 지어내지 않는다(안내 셋은 일정 값으로 만든다).
★**전용 테넌트**에서 돈다. 운영 데이터를 건드리지 않고, 끄면 그 테넌트를 통째로 지운다.
★설정 `scenario_mode_enabled` 가 꺼져 있으면 모든 경로가 404 다 — 릴리즈에 열리지 않게.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import threading
from typing import Any, Callable
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core import settings as settings_module
from app.infrastructure.db.session import get_connection

from .itinerary import Item, TripStore

KST = ZoneInfo("Asia/Seoul")
HERE = Path(__file__).resolve().parent
SCENARIO_PATH = HERE / "scenarios" / "seoul_day_taiwan_friends.json"
STATIC_PAGE = HERE / "static" / "tripilot.html"

#: 장면 — 시각·이름·하는 일. 시각은 확정 시나리오와 재생 타임라인에 맞춘다.
SCENES: tuple[dict[str, Any], ...] = (
    {"time": "08:00", "label": "하루 일정 안내", "kind": "day_start"},
    {"time": "09:00", "label": "잠실 스카이타워 · 1시간 전 기상 악화 감지", "kind": "watch", "code": "액-02"},
    {"time": "10:45", "label": "성수역 무정차 · 경로 변경", "kind": "watch", "code": "이동-B1"},
    {"time": "11:15", "label": "성수동 쇼핑", "kind": "watch"},
    {"time": "13:00", "label": "점심 · 70분 지연 (고객 신고)", "kind": "customer", "report": "delay", "code": "요식-P3"},
    {"time": "15:00", "label": "경복궁 이동 · 출발 안내", "kind": "departure"},
    {"time": "15:30", "label": "경복궁 · 한복과 사진", "kind": "watch"},
    {"time": "17:10", "label": "세종대로 통제 · 이동 경로 변경", "kind": "watch", "code": "이동-A6"},
    {"time": "18:00", "label": "저녁 · 당일 임시휴무 (고객 신고)", "kind": "customer", "report": "closed", "code": "요식-P7"},
    {"time": "19:40", "label": "마트 · 품절 상품 대안 (고객 문의)", "kind": "customer", "report": "stock_out", "code": "액-08"},
    {"time": "20:30", "label": "오늘의 변경 내역", "kind": "summary"},
)


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _enabled() -> None:
    if not getattr(settings_module.get_settings(), "scenario_mode_enabled", False):
        raise HTTPException(404, {"error": {"code": "not_found", "message": "resource not found"}})


def _hm(moment: datetime | None) -> str:
    return moment.astimezone(KST).strftime("%H:%M") if moment else ""


class ScenarioSession:
    """시나리오 한 판. ★메모리에 한 판만 산다(시연용). 데이터는 전용 테넌트 DB 에 있다."""

    def __init__(self, *, classifier: Any, chat: Any) -> None:
        from app.infrastructure.travel.base import TravelSources
        from app.infrastructure.travel.disruptions import DisruptionCheck
        from app.infrastructure.travel.replay import (ReplayAir, ReplayRouteEvents, ReplayTimeline,
                                                      ReplayWarning, ReplayWeather)
        from .trip_desk import TripDesk
        from .trip_watch import TripWatcher

        self.data = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
        self.day = self.data["trip"]["date"]
        self.tenant = "scenario-live-" + uuid4().hex[:8]
        self.clock = Clock(self.at("07:59"))
        self.timeline = ReplayTimeline(self.data["timeline"], self.clock)
        self.store = TripStore(self.tenant)
        check = DisruptionCheck(TravelSources(weather=ReplayWeather(self.timeline),
                                              warning=ReplayWarning(self.timeline),
                                              air=ReplayAir(self.timeline)),
                                limits=lambda: (60, 30), quake_rules=lambda: (4.0, 100.0, 24.0)).check
        self.check = check
        self.watcher = TripWatcher(store=self.store, check=check, connection_factory=get_connection,
                                   clock=self.clock, routes=None,
                                   route_events=ReplayRouteEvents(self.timeline))
        self.desk = TripDesk(store=self.store, connection_factory=get_connection, check=check)
        self.classifier, self.chat = classifier, chat
        self.scene = -1
        self.log: list[dict[str, Any]] = []
        self.seen: set[str] = set()
        self.reported: set[int] = set()
        self.trip_id: UUID | None = None
        self._seed()

    # ── 준비 ────────────────────────────────────────────────────
    def at(self, hhmm: str) -> datetime:
        return datetime.fromisoformat(f"{self.day}T{hhmm}:00").replace(tzinfo=KST)

    def _seed(self) -> None:
        data = self.data
        with get_connection() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)",
                            (self.tenant, "scenario mode"))
                cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) "
                            "RETURNING customer_id", (self.tenant, "taiwan-friends"))
                customer = cur.fetchone()[0]
                ids = {}
                for place in data["places"]:
                    cur.execute(
                        "INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,"
                        "attributes) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING place_id",
                        (self.tenant, place["name"], place["kind"], place["lat"], place["lon"],
                         place["weather_sensitive"],
                         json.dumps(place["attributes"], ensure_ascii=False)))
                    ids[place["key"]] = cur.fetchone()[0]
            items = [Item(item_id=uuid4(), seq=it["seq"], kind=it["kind"], title=it["title"],
                          place_id=ids.get(it.get("place")), starts_at=self.at(it["start"]),
                          ends_at=self.at(it["end"]),
                          detail={**it.get("detail", {}),
                                  **({"route": it["route"], "route_def": data["routes"][it["route"]]}
                                     if "route" in it else {})})
                     for it in data["items"]]
            with conn.transaction():
                self.trip_id, _ = self.store.create_trip(
                    conn, customer_id=customer, title=data["trip"]["title"],
                    locale=data["trip"]["locale"], party_size=data["trip"]["party_size"],
                    items=items, constraints=data["trip"].get("constraints"))
        # 생성 통지는 이 모드에서 채팅에 싣지 않는다 — 하루 안내가 대신한다.
        self._collect(show=False)

    def cleanup(self) -> None:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            for sql in ("DELETE FROM action_requests WHERE tenant_id=%s",
                        "DELETE FROM case_events WHERE tenant_id=%s",
                        "DELETE FROM customer_cases WHERE tenant_id=%s",
                        "DELETE FROM outbox WHERE tenant_id=%s",
                        "DELETE FROM trips WHERE tenant_id=%s",
                        "DELETE FROM places WHERE tenant_id=%s",
                        "DELETE FROM customers WHERE tenant_id=%s",
                        "DELETE FROM tenants WHERE tenant_id=%s"):
                cur.execute(sql, (self.tenant,))

    # ── 채팅 기록 ───────────────────────────────────────────────
    def _say(self, role: str, text: str, **meta: Any) -> None:
        self.log.append({"role": role, "text": text, "time": _hm(self.clock()), **meta})

    def _collect(self, *, show: bool = True) -> int:
        """새 통지(바깥함)를 채팅에 싣는다. ★문장은 통지 그대로다 — 여기서 만들지 않는다."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT dedupe_key, payload_json FROM outbox WHERE tenant_id=%s "
                        "AND topic='trip.notice' ORDER BY available_at, dedupe_key", (self.tenant,))
            rows = cur.fetchall()
        added = 0
        for key, payload in rows:
            if key in self.seen:
                continue
            self.seen.add(key)
            if not show:
                continue
            added += 1
            self._say("assistant", payload.get("text") or "", notice=True,
                      version=payload.get("version"), replay=bool(payload.get("replay")),
                      other_options=payload.get("other_options") or [],
                      changed=payload.get("changed"), kind=payload.get("kind", "change"),
                      causes=[{k: c.get(k) for k in ("category", "type", "kind", "summary")
                               if c.get(k)} for c in payload.get("causes") or []])
        return added

    # ── 장면 ────────────────────────────────────────────────────
    def next(self) -> None:
        if self.scene >= len(SCENES) - 1:
            return
        self.scene += 1
        scene = SCENES[self.scene]
        self.clock.now = self.at(scene["time"])
        self._say("system", f"DAY 1 · {scene['time']} · {scene['label']}")
        kind = scene["kind"]
        if kind == "day_start":
            self._day_start()
        elif kind in ("watch", "departure"):
            result = self.watcher.tick()
            if kind == "departure":
                self._departure()
            if result.fatal:
                self._say("assistant", f"점검 소스가 답하지 않은 항목이 {len(result.fatal)}개 있어 "
                                       "일정을 바꾸지 않고 사람에게 넘겼어요(결정 15).", kind="fatal")
        elif kind == "summary":
            self._summary()
        self._collect()

    def _items(self):
        with get_connection() as conn:
            return self.store.latest(conn, self.trip_id)

    def _day_start(self) -> None:
        trip, items = self._items()
        stops = [f"{_hm(i.starts_at)} {i.title}" for i in items if i.kind != "mobility"]
        text = ("좋은 아침이에요! 오늘 일정을 안내해 드릴게요.\n" + " → ".join(stops) +
                "\n\n일정에 영향을 주는 변동이 확인되면 먼저 조정하고 알려드릴게요.")
        with get_connection() as conn, conn.transaction():
            self.store.enqueue_message(conn, trip_id=self.trip_id, key="day_start",
                                       payload={"text": text, "kind": "day_start",
                                                "version": trip["version"]})

    def _departure(self) -> None:
        trip, items = self._items()
        now = self.clock()
        move = next((i for i in items if i.kind == "mobility" and i.starts_at >= now), None)
        if move is None:
            return
        after = next((i for i in items if i.seq > move.seq), None)
        text = (f"{_hm(move.starts_at)} 출발 — {move.title} ({_hm(move.starts_at)}–{_hm(move.ends_at)})."
                + (f"\n다음 일정: {_hm(after.starts_at)} {after.title}." if after else ""))
        with get_connection() as conn, conn.transaction():
            self.store.enqueue_message(conn, trip_id=self.trip_id, key=f"departure:{move.seq}",
                                       payload={"text": text, "kind": "departure",
                                                "version": trip["version"]})

    def _summary(self) -> None:
        from .trip_api import _REASON_LABELS, _cause_label

        with get_connection() as conn:
            history = self.store.versions(conn, self.trip_id)
        lines = [f"v{h['version']} · {_REASON_LABELS.get(h['reason'], h['reason'])}"
                 + "".join(f" · {_cause_label(c)}" for c in h["causes"] or [])
                 for h in history if h["version"] > 1]
        text = (f"오늘 일정이 {len(lines)}번 바뀌었어요.\n" + "\n".join(lines) +
                "\n\n기존 점심 예약의 변경·취소와 판매점 재고는 따로 확인이 필요해요.")
        with get_connection() as conn, conn.transaction():
            self.store.enqueue_message(conn, trip_id=self.trip_id, key="summary",
                                       payload={"text": text, "kind": "summary",
                                                "version": history[-1]["version"]})

    # ── 고객 ────────────────────────────────────────────────────
    def message(self, text: str) -> dict[str, Any]:
        from .trip_messages import handle_trip_message

        self._say("user", text)
        result = handle_trip_message(
            tenant=self.tenant, trip_id=self.trip_id, request_id=f"chat-{len(self.log)}-{uuid4().hex[:6]}",
            message=text, at=self.clock(), classifier=self.classifier, chat=self.chat,
            desk=self.desk, actor_id="scenario")
        if self.scene >= 0 and SCENES[self.scene]["kind"] == "customer":
            self.reported.add(self.scene)
        added = self._collect()
        outcome = result.get("outcome") or {}
        meta = {"case_id": result.get("case_id"), "case_status": result.get("case_status"),
                "classification": result.get("classification"), "report": result.get("report")}
        if outcome.get("status") == "answered":
            self._say("assistant", outcome.get("text", ""), kind="answer", **meta)
        elif result.get("status") == "escalated":
            self._say("assistant", "말씀하신 내용으로는 일정을 바꿀 근거를 찾지 못했어요. "
                                   "상담원에게 넘겼어요 — 추측으로 일정을 바꾸지 않았어요.",
                      kind="escalated", **meta)
        elif not added:
            self._say("assistant", {"still_fits": "지금 일정 그대로도 괜찮아요 — 바꾸지 않았어요.",
                                    "no_meal": "그 시각 뒤에는 식사 일정이 없어요.",
                                    "no_alternate": "바꿀 수 있는 다른 안이 없어요."}.get(
                str(outcome.get("status")), f"처리 결과: {outcome.get('status')}"), kind="answer", **meta)
        elif self.log and self.log[-1].get("notice"):
            self.log[-1].update(meta)
        return result

    def alternate(self, item_id: UUID, choice: str | None) -> dict[str, Any]:
        trip, _ = self._items()
        outcome = self.desk.swap_alternate(trip_id=self.trip_id, item_id=item_id,
                                           base_version=trip["version"], choice=choice,
                                           message="화면에서 다른 안 선택",
                                           request_id=f"swap-{uuid4().hex[:8]}")
        self._collect()
        return outcome

    # ── 운영콘솔이 읽는 것 ──────────────────────────────────────
    def ops(self) -> dict[str, Any]:
        """이 판(전용 테넌트)의 Case · 상태 전이 · 일정 버전 · 바깥함. **읽기만 한다.**

        ★운영콘솔의 Case 목록은 설정 테넌트(`settings.tenant_id`)만 본다 — 시나리오 테넌트의
          Case 가 거기 안 뜬다. 그래서 스위치 화면이 이것을 따로 읽는다(2026-09-15).
        """
        from .trip_api import _REASON_LABELS, _cause_label

        with get_connection() as conn:
            trip, _ = self.store.latest(conn, self.trip_id)
            history = self.store.versions(conn, self.trip_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT c.case_id, c.status::text, c.intent, c.issue_code, c.owner_team_id, "
                    "c.version, c.subject, "
                    "array_agg(e.event_type::text ORDER BY e.aggregate_version) "
                    "FROM customer_cases c JOIN case_events e "
                    "ON e.tenant_id = c.tenant_id AND e.case_id = c.case_id "
                    "WHERE c.tenant_id = %s "
                    "GROUP BY c.case_id, c.status, c.intent, c.issue_code, c.owner_team_id, "
                    "c.version, c.subject ORDER BY min(e.created_at)", (self.tenant,))
                cases = cur.fetchall()
                cur.execute("SELECT status::text, count(*) FROM outbox WHERE tenant_id = %s "
                            "AND topic = 'trip.notice' GROUP BY status", (self.tenant,))
                outbox = {status: count for status, count in cur.fetchall()}
        scene = SCENES[self.scene] if self.scene >= 0 else None
        return {
            "active": True, "tenant": self.tenant, "scene": self.scene, "scenes": len(SCENES),
            "label": scene["label"] if scene else None, "clock": self.clock().strftime("%H:%M"),
            "version": trip["version"],
            "history": [{"version": h["version"],
                         "reason": _REASON_LABELS.get(h["reason"], h["reason"]),
                         "causes": [_cause_label(c) for c in h["causes"] or []]} for h in history],
            "cases": [{"case_id": str(case_id), "status": status, "intent": intent,
                       "issue_code": issue_code, "owner_team": owner, "version": version,
                       "subject": subject, "events": list(events)}
                      for case_id, status, intent, issue_code, owner, version, subject, events
                      in cases],
            "outbox": outbox,
        }

    # ── 화면이 읽는 것 ──────────────────────────────────────────
    def feed(self) -> dict[str, Any]:
        from .trip_api import _REASON_LABELS, _cause_label

        with get_connection() as conn:
            trip, items = self.store.latest(conn, self.trip_id)
            original = {i.seq: i for i in self.store.items(conn, self.trip_id, 1)}
            history = self.store.versions(conn, self.trip_id)
        scene = SCENES[self.scene] if self.scene >= 0 else None
        pending = None
        if scene and scene["kind"] == "customer" and self.scene not in self.reported:
            report = next(r for r in self.data["customer_reports"] if r["type"] == scene["report"])
            pending = report["message"]
        return {
            "active": True, "tenant": self.tenant, "trip_id": str(self.trip_id),
            "title": trip["title"], "locale": trip["locale"], "party_size": trip["party_size"],
            "version": trip["version"], "clock": self.clock().strftime("%H:%M"),
            "scene": self.scene, "scenes": [{"time": s["time"], "label": s["label"],
                                             "kind": s["kind"], "code": s.get("code")} for s in SCENES],
            "awaiting_customer": pending is not None, "suggestion": pending
            or ("다른 안으로 바꿔줘" if trip["version"] > 1 else None),
            "items": [{
                "item_id": str(i.item_id), "seq": i.seq, "kind": i.kind, "title": i.title,
                "place": (i.place or {}).get("name"),
                "latitude": (i.place or {}).get("latitude"),
                "longitude": (i.place or {}).get("longitude"),
                "starts_at": _hm(i.starts_at), "ends_at": _hm(i.ends_at),
                "changed": i.replaces_item_id is not None,
                "before": (original[i.seq].title if i.seq in original
                           and original[i.seq].title != i.title else None),
                "other_options": [{"key": a["key"], "name": a.get("option_label") or a["name"]}
                                  for a in i.detail.get("alternates") or []],
                "customer_pinned": bool(i.detail.get("customer_pinned")),
                "current": bool(i.starts_at <= self.clock() < (i.ends_at or i.starts_at)),
                "past": bool((i.ends_at or i.starts_at) <= self.clock()),
            } for i in items],
            "history": [{"version": h["version"],
                         "reason": _REASON_LABELS.get(h["reason"], h["reason"]),
                         "causes": [_cause_label(c) for c in h["causes"] or []]} for h in history],
            "chat": self.log,
        }


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=600)


class AlternateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: UUID
    choice: str | None = None


def build_scenario_router(*, classifier_factory: Callable[[], Any] | None = None,
                          chat_factory: Callable[[], Any] | None = None) -> APIRouter:
    router = APIRouter(tags=["scenario-mode"])
    holder: dict[str, ScenarioSession | None] = {"session": None}
    lock = threading.Lock()

    def _session() -> ScenarioSession:
        if holder["session"] is None:
            raise HTTPException(409, {"error": {"code": "scenario_off",
                                                "message": "시나리오 모드가 꺼져 있다"}})
        return holder["session"]

    @router.get("/tripilot", response_class=HTMLResponse)
    def page():
        _enabled()
        return HTMLResponse(STATIC_PAGE.read_text(encoding="utf-8"))

    @router.get("/scenario/status")
    def status():
        _enabled()
        session = holder["session"]
        if session is None:
            return {"active": False, "scenes": len(SCENES)}
        return {"active": True, "scene": session.scene, "scenes": len(SCENES),
                "label": SCENES[session.scene]["label"] if session.scene >= 0 else None,
                "clock": session.clock().strftime("%H:%M"), "trip_id": str(session.trip_id),
                "tenant": session.tenant}

    @router.post("/scenario/start")
    def start():
        _enabled()
        with lock:
            if holder["session"] is not None:
                holder["session"].cleanup()
            session = ScenarioSession(
                classifier=classifier_factory() if classifier_factory else None,
                chat=chat_factory() if chat_factory else None)
            holder["session"] = session
            session.next()                              # 08:00 하루 안내부터
            return session.feed()

    @router.post("/scenario/stop")
    def stop():
        _enabled()
        with lock:
            if holder["session"] is not None:
                holder["session"].cleanup()
            holder["session"] = None
        return {"active": False}

    @router.get("/scenario/feed")
    def feed():
        _enabled()
        if holder["session"] is None:
            return {"active": False}
        return holder["session"].feed()

    @router.get("/scenario/ops")
    def operations():
        _enabled()
        if holder["session"] is None:
            return {"active": False}
        return holder["session"].ops()

    @router.post("/scenario/next")
    def advance():
        _enabled()
        with lock:
            session = _session()
            session.next()
            return session.feed()

    @router.post("/scenario/message")
    def message(request: MessageIn):
        _enabled()
        with lock:
            session = _session()
            session.message(request.message.strip())
            return session.feed()

    @router.post("/scenario/alternate")
    def alternate(request: AlternateIn):
        _enabled()
        with lock:
            session = _session()
            outcome = session.alternate(request.item_id, request.choice)
            if outcome.get("status") not in ("adjusted",):
                raise HTTPException(409, {"error": {"code": str(outcome.get("status")),
                                                    "message": "다른 안으로 바꾸지 못했다"}})
            return session.feed()

    return router


__all__ = ["SCENES", "ScenarioSession", "build_scenario_router"]
