# -*- coding: utf-8 -*-
"""재난 시 **일정 정지** · **피난 안내** · **다시 시작**. `[결정 2026-10-06 사용자]`

    ① 재난이 난 시각에 그 지역에 여행객이 있었다 → **그날(KST) 남은 일정을 정지**한다. ★`[결정 2026-10-06 사용자]` **자정이 지나도 저절로 풀리지 않는다** — 사용자가 다시 시작해야 푼다.
    ② 전쟁 · 활화산 폭발처럼 아주 심각하다 → **여행 일정 전체를 정지**하고 근처 대피 장소로 안내한다 — 안전을 위한 이동과 목적지를 알리는 안전 알림.
    ③ 공식 **해제**가 오면 「해제됐어요 — 다시 시작할까요?」를 알린다. **다시 시작은 사용자가 정한다**(서버는 사용자가 이미 안전한 곳에 있는지 모른다).
    ④ ★`[결정 2026-10-06 사용자]` **정지 중에는 관련 안내를 계속 보낸다** — 일정 간격(`travel.safety.reminder`)으로, 해제 전에는 처음 안내(공식 안내 · 가까운 대피 장소)를 다시, 해제 뒤에는 「아직 정지 중이에요」를 보낸다. 횟수에 상한이 있다.

★정지는 **일정을 고치거나 지우지 않는다.** `trip_safety_pauses` 에 표시를 쓸 뿐이고, 감시 · 안내 반복(`TripStore.active_trip_ids` · `due`)이 그 여행(또는 그날)을 건너뛴다. 다시 시작 = 표시를 닫는 것.
★**여행객이 그 지역에 있었는가**는 일정으로 판단한다 — 오늘이 여행 기간 안이고, 오늘 일정에 적힌 장소(진행 중 → 다음 → 마지막)에서 사건을 점검한다. 실제 위치는 모른다(위치 수집은 아직 없다).
  그래서 대피 장소 안내는 「일정에 적힌 장소 기준」이라고 밝힌다 — 지금 계신 곳과 다를 수 있다.
★`[결정 2026-10-06 사용자]` **아직 시작하지 않은 여행도 심각한 사건(여행 전체 정지 단계)이면 정지한다** — 가기 전에 현지 상황을 모르니 사용자가 다시 시작할 때까지 멈춘다.
  대피 장소는 안내하지 않는다(그곳에 있는 사람이 아니다) — 여행 전에 공식 안내를 확인하라는 글이다. **「그날 정지」 단계 사건은 시작 전 여행을 멈추지 않는다**(오늘 그곳에 있는 사람의 일이다).
★정하는 것(분류)은 `planning/safety.py`, 이 파일은 **쓰고 · 알리고 · 푼다.** 사건을 못 읽으면(`fatal`) 정지하지 않는다 — 조회 실패를 정지 사유로 쓰지 않는다(결정 15).
★같은 사건(`event_key`)으로 두 번 열지 않는다 — 사용자가 다시 시작한 뒤에 같은 재난문자가 조회 창에 남아 있어도 다시 멈추지 않는다.
★대피 장소는 표(`safety_shelters`)에 있는 것만 알린다. 표가 비었으면 「자료를 아직 못 불러왔어요 + 공식 안내」다 — 지어내지 않는다.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Callable
from uuid import UUID
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.components.itinerary.trip_scope import extra_sql as scope_sql
from app.domains.travel_ops.components.places import shelters as shelters_module
from app.domains.travel_ops.components.planning.safety import SafetyEvent, SafetyRules, classify

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

#: 알림이 부르는 「다시 시작」 — 웹이 이 경로로 요청한다(`POST /v1/web/trips/{id}/safety/resume`)
RESUME_LABEL = "일정 다시 시작"
EMERGENCY_CALL = "119"
PORTAL = "국민재난안전포털"


def day_end(moment: datetime) -> datetime:
    """그 시각이 속한 날(KST)의 **끝** = 다음 날 0시."""
    local = moment.astimezone(KST)
    return datetime.combine(local.date() + timedelta(days=1), time.min, tzinfo=KST)


# ── 읽기 · 쓰기 ─────────────────────────────────────────────────────
class SafetyPauses:
    """정지 표시를 쓰고 읽고 닫는다. ★모든 쿼리에 `tenant_id`."""

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id

    def active(self, conn, trip_id: UUID, *, now: datetime | None = None) -> list[dict[str, Any]]:
        """지금 유효한 정지 — 다시 시작하지 않았고 끝나는 시각이 안 지났다."""
        with conn.cursor() as cur:
            cur.execute("SELECT pause_id, level, event_key, event_json, day, from_at, until_at, guidance_json, created_at, release_notified_at "
                        "FROM trip_safety_pauses WHERE tenant_id=%s AND trip_id=%s AND resumed_at IS NULL "
                        "AND (until_at IS NULL OR until_at > COALESCE(%s, now())) ORDER BY seq", (self.tenant_id, trip_id, now))
            return [dict(zip(("pause_id", "level", "event_key", "event", "day", "from_at", "until_at", "guidance", "created_at", "release_notified_at"), row))
                    for row in cur.fetchall()]

    def open(self, conn, *, trip_id: UUID, event: SafetyEvent, day: date | None, from_at: datetime, until_at: datetime | None,
             guidance: dict[str, Any], opened_at: datetime | None = None) -> UUID | None:
        """정지를 연다. **같은 사건으로 이미 열었으면 None**(다시 시작한 것이어도 — 같은 사건으로 두 번 멈추지 않는다)."""
        with conn.cursor() as cur:
            cur.execute("INSERT INTO trip_safety_pauses (tenant_id, trip_id, level, event_key, event_json, day, from_at, until_at, guidance_json, created_at) "
                        "VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb,COALESCE(%s, now())) ON CONFLICT (tenant_id, trip_id, level, event_key) DO NOTHING "
                        "RETURNING pause_id",
                        (self.tenant_id, trip_id, event.level, event.key, json.dumps(event.evidence(), ensure_ascii=False), day, from_at, until_at,
                         json.dumps(guidance, ensure_ascii=False, default=str), opened_at))   # opened_at = 점검 시계(재안내 간격의 시작 — 시험의 고정 시계도 따른다)
            row = cur.fetchone()
        return row[0] if row else None

    def resume(self, conn, *, trip_id: UUID, via: str, by: UUID | None = None, now: datetime | None = None) -> int:
        """다시 시작 — 열려 있는 정지를 닫는다. 돌려주는 값 = 닫은 수. `now` 는 부르는 쪽 시계(시험 · 재생) — 없으면 DB 의 지금."""
        with conn.cursor() as cur:
            cur.execute("UPDATE trip_safety_pauses SET resumed_at=now(), resumed_via=%s, resumed_by=%s "
                        "WHERE tenant_id=%s AND trip_id=%s AND resumed_at IS NULL AND (until_at IS NULL OR until_at > COALESCE(%s, now()))",
                        (via, by, self.tenant_id, trip_id, now))
            return cur.rowcount

    def mark_release_notified(self, conn, pause_id: UUID) -> bool:
        with conn.cursor() as cur:
            cur.execute("UPDATE trip_safety_pauses SET release_notified_at=now() WHERE tenant_id=%s AND pause_id=%s AND release_notified_at IS NULL",
                        (self.tenant_id, pause_id))
            return cur.rowcount == 1


def view(conn, *, tenant_id: str, trip_id: UUID, now: datetime | None = None) -> dict[str, Any]:
    """여행 조회의 `safety` — 상단이 「정지 중」을 보인다. 정지가 없으면 `{paused: false}`.

    정지가 여럿이면(그날 정지 + 여행 전체 정지) **여행 전체가 앞선다**."""
    try:
        with conn.transaction():
            rows = SafetyPauses(tenant_id).active(conn, trip_id, now=now)
    except Exception:                                      # noqa: BLE001 — 마이그레이션 052 가 안 올라간 DB 에서도 여행 조회는 된다. 경고를 남긴다
        logger.warning("safety pause view unreadable trip=%s (migration 052?)", trip_id, exc_info=True)
        return {"paused": False}
    if not rows:
        return {"paused": False}
    top = sorted(rows, key=lambda r: (r["level"] != "trip",))[0]
    event = top["event"] or {}
    return {"paused": True, "level": top["level"], "label": event.get("label"), "since": top["from_at"].isoformat(),
            "until": top["until_at"].isoformat() if top["until_at"] else None, "day": top["day"].isoformat() if top["day"] else None,
            "released": top["release_notified_at"] is not None, "phase": (top["guidance"] or {}).get("phase") or "in_progress",
            "resume": {"label": RESUME_LABEL, "path": "/safety/resume"}}


# ── 안내 만들기 ─────────────────────────────────────────────────────
def _cfg() -> dict[str, Any]:
    from app.core.settings import get_guardrails

    guard = get_guardrails()
    return {"max_listed": int(guard.get("travel.safety.shelters.max_listed")),
            "radius_km": float(guard.get("travel.safety.shelters.search_radius_km")),
            "speed_kmh": float(guard.get("travel.safety.shelters.walk_speed_kmh")),
            "official_max": int(guard.get("travel.safety.official_text_max_chars"))}


def _excerpt(text: str | None, limit: int) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def build_guidance(conn, *, event: SafetyEvent, place: dict[str, Any] | None, upcoming: bool = False) -> dict[str, Any]:
    """알림에 싣는 안내 — 공식 안내를 앞세우고, 표에 있는 가까운 대피 장소를 붙인다. ★표에 없는 것은 지어내지 않는다.

    `upcoming` = 아직 시작하지 않은 여행 — 그곳에 있는 사람이 아니라서 **대피 장소를 안내하지 않고** 여행 전에 공식 안내를 확인하라고 한다."""
    cfg = _cfg()
    source = "기상청 지진정보" if event.category == "earthquake" else "행정안전부 긴급재난문자"
    guidance: dict[str, Any] = {
        "level": event.level, "label": event.label,
        "official": {"source": source, "text": _excerpt(event.text, cfg["official_max"]), "at": event.at.isoformat() if event.at else None},
        "emergency_call": EMERGENCY_CALL, "portal": PORTAL, "phase": "upcoming" if upcoming else "in_progress",
        "reference": None, "shelters": [], "shelter_status": "not_applicable", "shelter_source": None,
        "resume": {"label": RESUME_LABEL, "path": "/safety/resume"}}
    if upcoming or event.shelter_type is None:
        return guidance
    lat, lon = (place or {}).get("latitude"), (place or {}).get("longitude")
    if lat is None or lon is None:
        guidance["shelter_status"] = "no_reference_place"
        return guidance
    guidance["reference"] = {"basis": "planned_place", "place": (place or {}).get("name"), "latitude": float(lat), "longitude": float(lon),
                             "note": "일정에 적힌 장소 기준이에요 — 지금 계신 곳과 다를 수 있어요"}
    types = (event.shelter_type,)
    if not shelters_module.has_data(conn, types):
        guidance["shelter_status"] = "no_data"
        return guidance
    found = shelters_module.nearest(conn, latitude=float(lat), longitude=float(lon), types=types, limit=cfg["max_listed"],
                                    radius_km=cfg["radius_km"], speed_kmh=cfg["speed_kmh"])
    origin = (float(lat), float(lon))
    for shelter in found:
        # ★「안전을 위한 이동」 — 일정에 적힌 장소에서 그 대피 장소까지 걸어서 가는 길을 지도 앱으로 연다(서버가 길을 계산하지 않는다 · 실제 위치가 아니라 일정 장소 기준)
        shelter["map_url"] = shelters_module.walking_directions_url(origin, (shelter["latitude"], shelter["longitude"]))
    guidance["shelters"] = found
    guidance["shelter_status"] = "ok" if found else "none_nearby"
    guidance["shelter_radius_km"] = cfg["radius_km"]
    guidance["shelter_source"] = sorted({s["source"] for s in found}) if found else None
    return guidance


def compose_text(guidance: dict[str, Any]) -> str:
    """고객에게 갈 글(한국어 원문). 안전을 앞세운다 — 일정 이야기는 그 뒤다."""
    level, label = guidance["level"], guidance["label"]
    if guidance.get("phase") == "upcoming":
        # ★아직 시작하지 않은 여행 — 그곳에 있는 사람이 아니다. 현지 상황을 모르니 멈추고, 가기 전에 공식 안내를 확인하라고 한다(대피 장소 목록 없음)
        lines = [f"⚠️ 안전 알림 — {label}. 아직 시작하지 않은 여행이지만 지금 현지 상황을 정확히 알 수 없어, 안전을 위해 여행 일정 전체를 정지했어요(일정은 지우지 않았어요).",
                 f"가기 전에 재난문자와 공식 안내({guidance['portal']})로 현지 상황을 먼저 확인해 주세요. 위급하면 {guidance['emergency_call']}에 연락하세요."]
        if guidance["official"].get("text"):
            lines.append(f"{guidance['official']['source']}: {guidance['official']['text']}")
        lines.append(f"상황을 확인하셨다면 웹에서 「{guidance['resume']['label']}」을 눌러 주세요.")
        return "\n".join(lines)
    scope = "여행 일정 전체를 정지했어요" if level == "trip" else "오늘 남은 일정을 정지했어요"
    lines = [f"⚠️ 안전 알림 — {label}. {scope}(일정은 지우지 않았어요).",
             f"지금은 일정보다 안전이 먼저예요. 재난문자와 공식 안내({guidance['portal']})의 행동 요령을 먼저 따라 주세요. 위급하면 {guidance['emergency_call']}에 연락하세요."]
    official = guidance["official"].get("text")
    if official:
        lines.append(f"{guidance['official']['source']}: {official}")
    status = guidance["shelter_status"]
    if status == "ok":
        reference = guidance["reference"] or {}
        lines.append("가까운 대피 장소(일정에 적힌 장소" + (f" {reference['place']}" if reference.get("place") else "") + " 기준 직선거리 · 걷는 시간은 추정이에요):")
        for number, shelter in enumerate(guidance["shelters"], start=1):
            where = f" — {shelter['address']}" if shelter.get("address") else ""
            ground = " · 지하" if shelter.get("underground") else ""
            lines.append(f"{number}) {shelter['name']}{where} · 약 {shelter['distance_m']}m(걸어서 약 {shelter['walk_minutes_estimate']}분){ground}")
            if shelter.get("map_url"):
                lines.append(f"   길찾기(걸어서): {shelter['map_url']}")
        lines.append("자료: " + ", ".join(guidance["shelter_source"] or []))
    elif status == "none_nearby":
        lines.append(f"일정에 적힌 장소 {guidance['shelter_radius_km']:g}km 안에서 대피 장소를 찾지 못했어요. 재난문자와 공식 안내를 따라 주세요.")
    elif status == "no_data":
        lines.append("가까운 대피 장소 자료를 아직 불러오지 못했어요. 재난문자와 공식 안내를 따라 주세요.")
    elif status == "no_reference_place":
        lines.append("일정의 장소 좌표를 몰라 가까운 대피 장소를 찾지 못했어요. 재난문자와 공식 안내를 따라 주세요.")
    lines.append(f"상황이 정리되면 웹에서 「{guidance['resume']['label']}」을 눌러 주세요."
                 + (" 다시 시작하시기 전까지는 내일 일정도 멈춰 있어요." if level == "day" else ""))
    return "\n".join(lines)


def notice_payload(guidance: dict[str, Any], event: SafetyEvent, pause_id: UUID) -> dict[str, Any]:
    return {"type": "safety_alert", "kind": f"safety_pause_{event.level}", "reason": "safety_pause", "text": compose_text(guidance), "language": "ko",
            "causes": [event.evidence()], "safety": True, "pause_id": str(pause_id), "options": [], "replay": False, "guidance": guidance}


def release_payload(event: dict[str, Any], release_text: str | None, pause_id: UUID, level: str, phase: str = "in_progress") -> dict[str, Any]:
    label = event.get("label") or "재난"
    scope = "여행 일정" if level == "trip" else "일정"
    greeting = "" if phase == "upcoming" else "다치신 곳은 없으신가요? "          # ★`[결정 2026-10-06 사용자]` 안부가 먼저다(아직 시작하지 않은 여행은 그곳에 있는 사람이 아니라 뺀다)
    text = (f"{greeting}{label} 상황이 해제됐다는 공식 안내가 나왔어요. 아직 {scope}은 정지돼 있어요. 안전하게 계시다면 웹에서 「{RESUME_LABEL}」을 눌러 주세요. 누르시기 전까지는 계속 멈춰 있어요."
            + (f"\n재난문자: {_excerpt(release_text, 200)}" if release_text else ""))
    return {"type": "guidance", "kind": "safety_release", "reason": "safety_release", "text": text, "language": "ko", "safety": True,
            "pause_id": str(pause_id), "guidance": {"level": level, "label": label, "resume": {"label": RESUME_LABEL, "path": "/safety/resume"}}}


def reminder_text(pause: dict[str, Any], *, released: bool) -> str:
    """정지가 이어지는 동안 다시 보내는 글. 해제 전 = 처음 안내를 다시(대피 장소 목록 포함), 해제 뒤 = 「아직 정지 중」."""
    guidance = pause.get("guidance") or {}
    event = pause.get("event") or {}
    # ★`[결정 2026-10-06 사용자]` 안부가 먼저다 — 다친 분께 일정 이야기부터 하지 않는다(아직 시작하지 않은 여행은 그곳에 있는 사람이 아니라 뺀다)
    greeting = "" if guidance.get("phase") == "upcoming" else "다치신 곳은 없으신가요? "
    if released:
        label = event.get("label") or guidance.get("label") or "재난"
        scope = "여행 일정" if pause["level"] == "trip" else "일정"
        return (f"🔔 {greeting}{label} 상황은 해제됐지만 {scope}은 아직 정지돼 있어요. 안전한 곳에 계시다면 웹에서 「{RESUME_LABEL}」을 눌러 주세요. "
                "누르시기 전까지는 계속 멈춰 있어요(일정은 지우지 않았어요).")
    return f"🔔 {greeting}아직 일정이 멈춰 있어서 안내를 다시 드려요.\n" + compose_text(guidance)


def morning_ask_payload(pause: dict[str, Any]) -> dict[str, Any]:
    """멈춘 날의 **다음 날 아침** 한 번. 저절로 재개하지 않고 **묻기만** 한다 — 누르면 이어지고, 안 누르면 그대로 멈춰 있다."""
    guidance = pause.get("guidance") or {}
    event = pause.get("event") or {}
    label = event.get("label") or guidance.get("label") or "재난"
    released = pause["release_notified_at"] is not None
    scope = "여행 일정" if pause["level"] == "trip" else "일정"
    greeting = "" if guidance.get("phase") == "upcoming" else "좋은 아침이에요. 지금은 괜찮으신가요? "
    cause = f"{label} 상황은 해제됐지만" if released else f"{label} 때문에"
    text = (f"{greeting}{cause} {scope}이 아직 멈춰 있어요. 안전한 곳에 계시고 다시 일정을 이어가고 싶으시면 웹에서 「{RESUME_LABEL}」을 눌러 주세요. "
            "누르시기 전까지는 계속 멈춰 있어요(일정은 지우지 않았어요). 위급하면 " + EMERGENCY_CALL + "에 연락하세요.")
    return {"type": "guidance", "kind": "safety_morning_ask", "reason": "safety_release" if released else "safety_pause", "text": text, "language": "ko",
            "safety": True, "pause_id": str(pause["pause_id"]), "options": [], "replay": False,
            "guidance": {"level": pause["level"], "label": label, "phase": guidance.get("phase") or "in_progress", "resume": {"label": RESUME_LABEL, "path": "/safety/resume"}}}


def reminder_payload(pause: dict[str, Any], *, released: bool, number: int) -> dict[str, Any]:
    guidance = pause.get("guidance") or {}
    return {"type": "guidance" if released else "safety_alert",
            "kind": "safety_release_reminder" if released else "safety_pause_reminder",
            "reason": "safety_release" if released else "safety_pause", "text": reminder_text(pause, released=released), "language": "ko",
            "causes": [pause["event"]] if pause.get("event") and not released else [], "safety": True, "pause_id": str(pause["pause_id"]),
            "options": [], "replay": False, "reminder": number, "guidance": guidance}


# ── 감시 ────────────────────────────────────────────────────────────
@dataclass
class SweepResult:
    trips: int = 0
    upcoming: int = 0                  # 이 회차에 본 시작 전 여행 수(trips 에 포함)
    checked: int = 0
    opened: list[dict[str, Any]] = field(default_factory=list)
    already: int = 0
    no_place: int = 0
    fatal: list[dict[str, Any]] = field(default_factory=list)
    released: list[dict[str, Any]] = field(default_factory=list)
    reminded: list[dict[str, Any]] = field(default_factory=list)
    asked: list[dict[str, Any]] = field(default_factory=list)          # 다음 날 아침 「이어갈까요?」를 물은 정지

    def counts(self) -> dict[str, int]:
        return {"trips": self.trips, "upcoming": self.upcoming, "checked": self.checked, "opened": len(self.opened), "already": self.already,
                "no_place": self.no_place, "fatal": len(self.fatal), "released": len(self.released), "reminded": len(self.reminded), "asked": len(self.asked)}


def _reference_place(items: list[Item], now: datetime) -> dict[str, Any] | None:
    """오늘 일정에서 **여행객이 있을 만한 장소** — 진행 중 → 곧 시작 → 마지막으로 끝난 것 → 다른 날의 가장 가까운 시각. 좌표가 있는 장소만."""
    placed = [i for i in items if i.place is not None and i.place.get("latitude") is not None and i.place.get("longitude") is not None]
    if not placed:
        return None
    today = now.astimezone(KST).date()

    def end(item: Item) -> datetime:
        return item.ends_at or item.starts_at

    todays = [i for i in placed if i.starts_at.astimezone(KST).date() == today]
    pool = todays or placed
    ongoing = [i for i in pool if i.starts_at <= now <= end(i)]
    upcoming = sorted((i for i in pool if i.starts_at > now), key=lambda i: i.starts_at)
    past = sorted((i for i in pool if end(i) < now), key=end, reverse=True)
    chosen = (ongoing or upcoming or past or [None])[0]
    if chosen is None:
        return None
    return {**chosen.place, "name": chosen.place.get("name") or chosen.title}


class SafetySweep:
    """진행 중이거나 **아직 시작하지 않은** 여행마다 **재난 · 지진 사건**을 점검해 정지하고 알린다(시작 전 여행은 여행 전체 정지만). 한 회차 = `tick()`.

    `check(place=, starts_at=, region=)` 은 `DisruptionCheck.check_safety`(또는 같은 모양의 흉내)다. `release(place=, since=, at=)` 은 공식 해제 문자 목록을 돌려준다(없으면 None)."""

    def __init__(self, *, store: TripStore, check: Callable[..., dict[str, Any]], connection_factory: Callable[[], Any],
                 clock: Callable[[], datetime], release: Callable[..., list[dict[str, Any]] | None] | None = None,
                 rules: SafetyRules | None = None) -> None:
        self.store, self.check, self._connect, self.clock = store, check, connection_factory, clock
        self.release, self.rules = release, rules or SafetyRules.from_guardrails()
        self.pauses = SafetyPauses(store.tenant_id)

    def _candidates(self, conn, now: datetime) -> list[tuple[UUID, str]]:
        """점검할 여행 `(여행, 단계)` — `in_progress`(오늘이 여행 기간 안 · 쉬는 날 포함) · `upcoming`(아직 시작하지 않았고 끝나지도 않았다). 끝난 여행은 뺀다. 게스트 제외는 감시와 같다(`trip_scope`)."""
        today = now.astimezone(KST).date()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT t.trip_id, (min(i.starts_at) AT TIME ZONE 'Asia/Seoul')::date FROM trips t "
                "JOIN itinerary_items i ON i.tenant_id=t.tenant_id AND i.trip_id=t.trip_id AND i.version=t.latest_version "
                "WHERE t.tenant_id=%s AND t.status='active' AND " + scope_sql("t") + " GROUP BY t.trip_id "
                "HAVING (max(COALESCE(i.ends_at, i.starts_at)) AT TIME ZONE 'Asia/Seoul')::date >= %s ORDER BY t.trip_id",
                (self.store.tenant_id, today))
            return [(trip_id, "upcoming" if first > today else "in_progress") for trip_id, first in cur.fetchall()]

    def tick(self) -> SweepResult:
        result = SweepResult()
        now = self.clock()
        with self._connect() as conn:
            candidates = self._candidates(conn, now)
        for trip_id, phase in candidates:
            result.trips += 1
            result.upcoming += phase == "upcoming"
            try:
                self._one(trip_id, phase, now, result)
            except Exception:                              # noqa: BLE001 — 한 여행의 실패가 다른 여행의 정지를 막지 않는다. 세어서 남긴다
                logger.exception("safety sweep failed trip=%s", trip_id)
                result.fatal.append({"trip_id": str(trip_id), "error": "exception"})
        return result

    def _one(self, trip_id: UUID, phase: str, now: datetime, result: SweepResult) -> None:
        upcoming = phase == "upcoming"
        with self._connect() as conn:
            _, items = self.store.latest(conn, trip_id)
            active = self.pauses.active(conn, trip_id, now=now)
        place = _reference_place(items, now)
        if place is None:
            result.no_place += 1
            return
        if active:
            self._release_notice(trip_id, active, place, now, result)
            self._remind(trip_id, active, now, result)
            self._ask_in_the_morning(trip_id, active, now, result)
        if any(p["level"] == "trip" for p in active):
            return                                         # 이미 여행 전체가 멈춰 있다 — 더 올릴 단계가 없다
        result.checked += 1
        report = self.check(place=place, starts_at=now, region="서울")
        if report.get("verdict") == "fatal":
            result.fatal.append({"trip_id": str(trip_id), "failed_categories": report.get("failed_categories")})
            return                                         # 조회 실패는 정지 사유가 아니다(결정 15)
        event = classify(report.get("disruptions") or [], self.rules)
        if event is None:
            return
        if upcoming and event.level != "trip":
            return                                         # 그날 정지는 오늘 그곳에 있는 사람의 일이다 — 아직 시작하지 않은 여행은 멈추지 않는다
        if event.level == "day" and any(p["level"] == "day" for p in active):
            return                                         # 이미 그날이 멈춰 있다
        today = now.astimezone(KST).date()
        if event.level == "day" and event.at is not None and event.at.astimezone(KST).date() != today:
            return                                         # 어제 난 사건 — 오늘 일정을 멈출 이유가 아니다
        from_at = min(now, event.at) if event.at else now
        until_at = None                                    # ★`[결정 2026-10-06 사용자]` 그날 정지도 자정에 풀리지 않는다 — 사용자가 다시 시작할 때까지(`day` 칸은 난 날을 기록할 뿐)
        with self._connect() as conn, conn.transaction():
            guidance = build_guidance(conn, event=event, place=place, upcoming=upcoming)
            pause_id = self.pauses.open(conn, trip_id=trip_id, event=event, day=today if event.level == "day" else None,
                                        from_at=from_at, until_at=until_at, guidance=guidance, opened_at=now)
            if pause_id is None:
                result.already += 1
                return
            self.store.enqueue_message(conn, trip_id=trip_id, key=f"safety:{pause_id}", payload=notice_payload(guidance, event, pause_id))
        result.opened.append({"trip_id": str(trip_id), "level": event.level, "kind": event.kind, "label": event.label, "phase": phase,
                              "pause_id": str(pause_id), "shelters": len(guidance["shelters"]), "shelter_status": guidance["shelter_status"]})

    def _remind(self, trip_id: UUID, active: list[dict[str, Any]], now: datetime, result: SweepResult) -> None:
        """정지가 이어지는 동안 **일정 간격마다** 안내를 다시 보낸다 — 간격 칸(`n`) 하나에 한 번만(`outbox` UNIQUE 가 같은 칸의 두 번째를 막는다).

        ★처음 안내가 나간 시각(`created_at`)부터 센다: 간격 1칸이 지나면 1번째 · 2칸이면 2번째 … `reminder.max_count` 번째까지. 점검이 한동안 멈췄다 돌아오면
          지난 칸은 건너뛰고 **지금 칸 하나만** 보낸다(밀린 것을 한꺼번에 쏟지 않는다). 사용자가 다시 시작하면 `active` 에서 빠져 더는 안 나간다."""
        if not self.rules.reminder_enabled or self.rules.reminder_interval_hours <= 0:
            return
        interval = timedelta(hours=self.rules.reminder_interval_hours)
        for pause in active:
            number = int((now - pause["created_at"]) / interval)
            if number < 1 or number > self.rules.reminder_max_count:
                continue
            released = pause["release_notified_at"] is not None
            with self._connect() as conn, conn.transaction():
                added = self.store.enqueue_message(conn, trip_id=trip_id, key=f"safety-remind:{pause['pause_id']}:{number}",
                                                   payload=reminder_payload(pause, released=released, number=number))
            if added:
                result.reminded.append({"trip_id": str(trip_id), "pause_id": str(pause["pause_id"]), "number": number, "released": released})

    def _ask_in_the_morning(self, trip_id: UUID, active: list[dict[str, Any]], now: datetime, result: SweepResult) -> None:
        """멈춘 날의 **다음 날 아침**(KST, `morning_ask_hour` 이후 첫 점검)에 「이어갈까요?」를 **정지마다 한 번** 묻는다. 저절로 재개하지 않는다.

        ★왜: 재안내(`_remind`)는 처음 안내 뒤 24시간에서 끊는다. 그 뒤 사용자가 화면을 안 열면 일정 안내가 조용히 멈춘 채 남는다 — 그 구멍을 한 번의 질문으로 메운다."""
        if not self.rules.morning_ask_enabled:
            return
        local = now.astimezone(KST)
        for pause in active:
            if local.date() <= pause["created_at"].astimezone(KST).date() or local.hour < self.rules.morning_ask_hour:
                continue
            with self._connect() as conn, conn.transaction():
                added = self.store.enqueue_message(conn, trip_id=trip_id, key=f"safety-morning:{pause['pause_id']}", payload=morning_ask_payload(pause))
            if added:
                result.asked.append({"trip_id": str(trip_id), "pause_id": str(pause["pause_id"]), "released": pause["release_notified_at"] is not None})

    def _release_notice(self, trip_id: UUID, active: list[dict[str, Any]], place: dict[str, Any], now: datetime, result: SweepResult) -> None:
        """공식 해제가 왔으면 **한 번만** 알린다(다시 시작은 사용자가 정한다)."""
        if self.release is None:
            return
        for pause in active:
            if pause["release_notified_at"] is not None or (pause["event"] or {}).get("category") != "disaster_msg":
                continue                                   # 지진은 「해제」가 없다 — 정지는 사용자가 푼다(그 대신 다시 안내가 계속 나간다)
            rows = self.release(place=place, since=pause["from_at"], at=now)
            matched = _matching_release(pause["event"] or {}, rows or [], self.rules)
            if matched is None:
                continue
            with self._connect() as conn, conn.transaction():
                if self.pauses.mark_release_notified(conn, pause["pause_id"]):
                    self.store.enqueue_message(conn, trip_id=trip_id, key=f"safety-release:{pause['pause_id']}",
                                               payload=release_payload(pause["event"] or {}, matched.get("text"), pause["pause_id"], pause["level"],
                                                                         (pause["guidance"] or {}).get("phase") or "in_progress"))
                    result.released.append({"trip_id": str(trip_id), "pause_id": str(pause["pause_id"])})


def _matching_release(event: dict[str, Any], rows: list[dict[str, Any]], rules: SafetyRules) -> dict[str, Any] | None:
    """정지를 건 사건과 **같은 사건의 해제**인가 — 재해구분이 같거나, 사건 본문의 심각 낱말이 해제 본문에도 있다."""
    kind, text = str(event.get("kind") or ""), str(event.get("text") or "")
    words = [w for w in rules.trip_keywords if w in text]
    for row in rows:
        body = str(row.get("text") or "")
        if "해제" not in body:
            continue
        if (kind and str(row.get("kind") or "") == kind) or any(w in body for w in words):
            return row
    return None


__all__ = ["EMERGENCY_CALL", "PORTAL", "RESUME_LABEL", "SafetyPauses", "SafetySweep", "SweepResult", "build_guidance", "compose_text", "day_end",
           "notice_payload", "release_payload", "view"]
