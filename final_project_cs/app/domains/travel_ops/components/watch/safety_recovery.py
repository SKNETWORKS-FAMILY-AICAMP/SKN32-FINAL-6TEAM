# -*- coding: utf-8 -*-
"""재난 뒤 **다시 시작** — 상황 꾸러미(사실 · 모르는 것) · 사용자의 선택 · 선택 기록 · 대체 후보 제안. `[결정 2026-10-06 사용자]`

흐름: 사용자가 「일정 다시 시작」을 누르면(`safety_pause.SafetyPauses.resume`) 이 모듈이 **그 재난의 상황 꾸러미**를 만든다. 사용자는 셋 중 하나를 고른다.
  keep               그대로 이어가기 — 일정은 안 바뀐다
  replace_affected   영향받은 것만 바꾸기(추천) — 영향 **확정** 항목마다 대신 갈 곳을 **제안**한다(고르면 바뀐다 · 안 고르면 그대로)
  replan_all         남은 일정 새로 받기 — 개인 AI(에이전트)에게 이 꾸러미를 넘겨 다시 짜게 한다(`tripilot_get_recovery_brief`)

★근거(조사 2026-10-06 · 뉴스와 연구 요약, 사례 수준): 아직 출발하지 않은 사람은 취소 · 연기가 크고, 여행 중인 사람은 「피해 지역만 빼고 계속」과 「일찍 귀가」로 갈린다. 그래서
  기본을 정하지 않고 **선택지를 열어 두며, 선택을 기록**해 나중에 기본값을 정한다(`user_activity_events`).
★**영향 판정은 세 가지**다 — 확정(affected) · 불명(unknown) · 없음(unaffected). **모르면 불명**이다.
  · 재난문자가 **구(區)를 지정**했으면: 그 구 안의 항목 = 확정, 구 밖 = 없음(공식 문자 기준이라고 밝힌다), 항목의 구를 모르면 불명
  · 문자에 구가 없다 · 지진이다 → **전부 불명**(범위를 지어내지 않는다 — 지진은 건물 · 시설 점검 공지를 확인하라고 한다)
★밀도를 우리가 마음대로 낮추지 않는다 — 「오늘은 가볍게」는 사용자가 고르는 선택(`lighter_day`)이고 **기록하고 에이전트에게 제약으로 전달**할 뿐이다. 낮추는 근거 연구가 없다.
★우리는 일정(시간표)만 조정한다 — 업체 예약 · 날짜 연기 · 취소는 다루지 않는다.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID

from app.domains.travel_ops.components.itinerary import activity_log
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.planning.planner import _district_of

#: 다시 시작한 뒤 이 시간 안에만 꾸러미를 만든다 — ★우리가 고른 값(측정하지 않았다)
WINDOW_HOURS = 72
CHOICES = ("keep", "replace_affected", "replan_all")
KIND = "safety_recovery_choice"
SEOUL_DISTRICTS = ("종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구", "노원구", "은평구", "서대문구",
                   "마포구", "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구")
_OTHER_CITIES = ("부산", "대구", "인천", "광주", "대전", "울산", "세종", "제주")
_DISTRICT_RE = re.compile("(?<![가-힣])(" + "|".join(SEOUL_DISTRICTS) + ")")


def districts_in(text: str | None) -> list[str]:
    """재난문자 글에서 서울 자치구 이름을 **나온 순서대로**(중복 없이). 다른 광역시 이름만 있고 「서울」이 없으면 빈 목록(같은 이름의 다른 도시 구를 서울로 읽지 않는다)."""
    if not text:
        return []
    if "서울" not in text and any(city in text for city in _OTHER_CITIES):
        return []
    return list(dict.fromkeys(_DISTRICT_RE.findall(text)))


def _item_district(item: Item) -> str | None:
    place = item.place or {}
    attributes = place.get("attributes") or {}
    found = place.get("district") or attributes.get("district")
    return str(found) if found else _district_of(place.get("address") or attributes.get("address"))


def classify(event: dict[str, Any], items: list[Item], *, now: datetime) -> tuple[list[str], list[dict[str, Any]]]:
    """`(지정된 구, 항목별 판정)` — 아직 안 끝난 장소 항목만. 판정마다 이유 한 줄(지어낸 이유 없음)."""
    districts = districts_in(event.get("text")) if event.get("category") == "disaster_msg" else []
    rows: list[dict[str, Any]] = []
    for item in items:
        if item.kind not in ("activity", "dining", "lodging") or not item.place:
            continue
        if (item.ends_at or item.starts_at) < now:
            continue
        district = _item_district(item)
        if event.get("category") == "earthquake":
            status, reason = "unknown", "지진은 영향 범위를 단정하지 않아요 — 건물 · 시설의 점검 공지를 확인해 주세요"
        elif not districts:
            status, reason = "unknown", "공식 재난문자에 지역이 적혀 있지 않아 범위를 알 수 없어요"
        elif district is None:
            status, reason = "unknown", "이 장소의 구를 알 수 없어요"
        elif district in districts:
            status, reason = "affected", f"공식 재난문자가 {district}를 지정했어요"
        else:
            status, reason = "unaffected", f"공식 재난문자가 지정한 구({', '.join(districts)}) 밖이에요"
        rows.append({"item_id": str(item.item_id), "title": item.title, "kind": item.kind, "starts_at": item.starts_at.isoformat(),
                     "place_name": (item.place or {}).get("name"), "district": district, "status": status, "reason": reason})
    return districts, rows


def latest_resumed(conn, tenant_id: str, trip_id: UUID, *, now: datetime) -> dict[str, Any] | None:
    """가장 최근에 **다시 시작한** 정지(`WINDOW_HOURS` 안). 없으면 None."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT pause_id, level, event_json, guidance_json, resumed_at, release_notified_at FROM trip_safety_pauses "
                    "WHERE tenant_id=%s AND trip_id=%s AND resumed_at IS NOT NULL AND resumed_at > %s ORDER BY resumed_at DESC LIMIT 1",
                    (tenant_id, trip_id, now - timedelta(hours=WINDOW_HOURS)))
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(("pause_id", "level", "event", "guidance", "resumed_at", "release_notified_at"), row))


def _excerpt(text: str | None, limit: int = 200) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def build_brief(conn, *, store, tenant_id: str, trip_id: UUID, now: datetime | None = None) -> dict[str, Any] | None:
    """재난 뒤 상황 꾸러미. 다시 시작한 정지가 없으면 None. 읽기 전용이다(고르는 것은 `record_choice`)."""
    now = now or datetime.now(timezone.utc)
    try:
        pause = latest_resumed(conn, tenant_id, trip_id, now=now)
    except Exception:                                   # noqa: BLE001 — 마이그레이션 052 가 없는 DB 에서도 여행 조회는 된다
        return None
    if pause is None:
        return None
    _, items = store.latest(conn, trip_id)
    event = pause["event"] or {}
    districts, rows = classify(event, items, now=now)
    counts = {key: sum(1 for r in rows if r["status"] == key) for key in ("affected", "unknown", "unaffected")}
    phase = (pause["guidance"] or {}).get("phase") or "in_progress"
    source = "기상청 지진정보" if event.get("category") == "earthquake" else "행정안전부 긴급재난문자"
    facts = [f"{source}: {_excerpt(event.get('text')) or event.get('label') or '재난'}"]
    if event.get("at"):
        facts.append(f"사건 시각: {event['at']}")
    if pause["release_notified_at"] is not None:
        facts.append("공식 해제 안내가 나왔어요")
    unknowns = ["지금 계신 곳 · 숙소 · 귀가 경로의 상태는 우리가 알 수 없어요", "공식 해제가 나왔는지는 재난문자 조회 기준이에요(놓칠 수 있어요)"]
    if not districts:
        unknowns.append("피해 범위(어느 구인지)를 공식 문자에서 알 수 없어요")
    previous = activity_log.latest(conn, tenant_id=tenant_id, trip_id=trip_id, kind=KIND)
    chosen = previous if previous and previous.get("pause_id") == str(pause["pause_id"]) else None
    options = [
        {"key": "keep", "label": "그대로 이어가기", "detail": "일정은 바꾸지 않아요"},
        {"key": "replace_affected", "label": "영향받은 것만 바꾸기", "recommended": True,
         "detail": ("영향이 확정된 곳마다 대신 갈 곳을 제안해요. 고르시면 바뀌고, 안 고르시면 그대로예요" if counts["affected"]
                    else "영향이 확정된 곳이 없어요 — 범위를 몰라 바꿀 곳을 가르지 못해요. 바꾸고 싶은 곳은 채팅으로 말씀해 주세요")},
        {"key": "replan_all", "label": "남은 일정 새로 받기", "detail": "개인 AI에게 이 상황을 넘겨 남은 일정을 다시 짜게 해요"},
    ]
    return {
        "pause_id": str(pause["pause_id"]), "phase": phase, "level": pause["level"], "resumed_at": pause["resumed_at"].isoformat(),
        "event": {"label": event.get("label"), "kind": event.get("kind"), "category": event.get("category"), "at": event.get("at"),
                  "official_text": _excerpt(event.get("text"))},
        "facts": facts, "unknowns": unknowns, "affected_districts": districts, "items": rows, "counts": counts,
        "options": options,
        "extras": [{"key": "lighter_day", "label": "오늘은 가볍게", "default": False,
                    "detail": "하루를 덜 채워 달라는 선택이에요. 우리가 임의로 낮추지 않고, 고르시면 기록하고 에이전트에게 전해요"}],
        "questions": [{"key": "lodging", "text": "숙소와 귀가 경로는 이용할 수 있나요?", "answers": ["yes", "no", "unknown"]},
                      {"key": "companions", "text": "함께하는 분(아이 · 어르신)이 있나요?", "answers": ["yes", "no"]}],
        "constraints": {"avoid_districts": districts, "affected_item_ids": [r["item_id"] for r in rows if r["status"] == "affected"],
                        "unknown_item_ids": [r["item_id"] for r in rows if r["status"] == "unknown"],
                        "lighter_day": bool(chosen and chosen.get("lighter_day"))},
        "scope_note": ("우리는 일정(시간표)만 조정해요. 아직 시작하지 않은 여행의 날짜 연기 · 취소와 업체 예약은 예약처에서 직접 하셔야 해요."
                       if phase == "upcoming" else "우리는 일정(시간표)만 조정해요. 업체 예약은 바꾸지 않아요."),
        "chosen": chosen,
    }


def record_choice(conn, *, tenant_id: str, trip_id: UUID, customer_id: UUID, pause_id: UUID, choice: str, lighter_day: bool,
                  answers: dict[str, str] | None) -> dict[str, Any]:
    """사용자의 선택을 **기록**한다(append-only). 이 정지가 이 여행의 다시 시작한 정지가 아니면 `LookupError`."""
    if choice not in CHOICES:
        raise ValueError(f"unknown choice {choice!r}")
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT 1 FROM trip_safety_pauses WHERE tenant_id=%s AND trip_id=%s AND pause_id=%s AND resumed_at IS NOT NULL",
                    (tenant_id, trip_id, pause_id))
        if cur.fetchone() is None:
            raise LookupError("no such resumed pause")
    payload = {"pause_id": str(pause_id), "choice": choice, "lighter_day": bool(lighter_day), "answers": answers or {}}
    payload["recorded"] = activity_log.record(conn, tenant_id=tenant_id, trip_id=trip_id, customer_id=customer_id, kind=KIND, payload=payload)
    return payload


def make_district_filter(conn_factory: Callable[[], Any], tenant_id: str, avoid: list[str]) -> Callable[[list[dict[str, Any]]], list[dict[str, Any]]]:
    """대체 후보에서 **피해 구의 곳을 뺀다.** 구를 알 수 없는 후보는 빼지 않고 「구를 확인하지 못했어요」를 붙여 둔다(모르는 것을 없는 것으로 처리하지 않는다)."""
    avoid_set = set(avoid)

    def keep(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ids = [o["place_id"] for o in options if o.get("place_id")]
        found: dict[str, str | None] = {}
        if ids:
            with conn_factory() as conn, conn.cursor() as cur:
                cur.execute("SELECT place_id::text, attributes->>'district' FROM places WHERE tenant_id=%s AND place_id::text = ANY(%s)",
                            (tenant_id, ids))
                found = {pid: district for pid, district in cur.fetchall()}
        kept: list[dict[str, Any]] = []
        for option in options:
            district = found.get(str(option.get("place_id"))) or (((option.get("catalog_place") or {}).get("attributes") or {}).get("district"))
            if district and district in avoid_set:
                continue
            kept.append({**option, "note": option.get("note") or (None if district else "이 곳의 구를 확인하지 못했어요")})
        return kept

    return keep


def suggest_replacements(desk, store, *, tenant_id: str, trip_id: UUID, brief: dict[str, Any], conn_factory: Callable[[], Any]) -> list[dict[str, Any]]:
    """영향 **확정** 항목마다 대신 갈 곳을 **제안**한다(기존 「후보만 알아봐 줘」 길 — 고르면 바뀐다, 안 고르면 그대로). 항목별 결과를 돌려준다."""
    keep = make_district_filter(conn_factory, tenant_id, brief["affected_districts"])
    out: list[dict[str, Any]] = []
    for row in brief["items"]:
        if row["status"] != "affected":
            continue
        with conn_factory() as conn:
            trip, _ = store.latest(conn, trip_id)
        result = desk.propose_alternatives(trip_id=trip_id, item_id=UUID(row["item_id"]), base_version=trip["version"],
                                           request_id=f"recovery:{brief['pause_id']}:{row['item_id']}", keep=keep)
        out.append({"item_id": row["item_id"], "title": row["title"], "status": result.get("status"),
                    "proposal_id": result.get("proposal_id"), "options": [o.get("name") for o in (result.get("options") or [])]})
    return out


__all__ = ["CHOICES", "KIND", "SEOUL_DISTRICTS", "WINDOW_HOURS", "build_brief", "classify", "districts_in", "latest_resumed", "make_district_filter",
           "record_choice", "suggest_replacements"]
