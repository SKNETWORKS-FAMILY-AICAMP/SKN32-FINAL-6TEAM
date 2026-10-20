"""계획 확인에서도 감시와 같은 위험 근거와 검증한 실내 대안을 보여 준다."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import Item, weather_from_class
from app.domains.travel_ops.components.watch import risk_report

KST = ZoneInfo("Asia/Seoul")
SCHEMA_VERSION = 1
#: 고치기로 새 판을 만들 때 앞 판의 위험 점검 결과를 다시 쓰는 시간(초) — 바뀌지 않은 일정까지 바깥 조회를 다시 하지 않게(2026-10-20 「대안 적용 13.9초」).
#:  공유 캐시가 같은 값을 주는 정도의 짧은 시간만 쓴다. ★우리가 고른 값
REUSE_FRESH_S = 600
#: ★`[2026-10-18 현장 피드백 「여행 날짜와 상관없이 현재 재난경보를 기준으로 일정 확인하라고 나온다」]` 「지금 발령 중」인 특보 · 재난문자 · 교통 통제 · 대기질 · 지진을
#:  일정의 문제로 보이는 범위 — 시작이 지금부터 이 시간 안인 일정만. 그보다 먼 일정(예: 일주일 뒤 여행)에는 지금 경보가 그 날짜의 사실이 아니므로 문제로 세지 않고,
#:  출발이 가까워지면 감시가 다시 점검한다. 예보는 그 시각을 보는 값이라 이 범위와 상관없이 그대로 보인다. 우리가 고른 값.
CURRENT_ALERT_HOURS = 24
FAR_REASON = "여행 날짜가 아직 멀어 지금 발령된 기상 특보 · 재난문자 · 교통 통제는 반영하지 않았어요 — 출발이 가까워지면 다시 확인해요"


def check_for(mode: str) -> Callable[..., dict[str, Any]]:
    """최초 검증은 기존 공유 캐시·예산을 쓰고, 반복 조회는 캐시만 읽는다."""
    from app.core.settings import get_settings
    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck

    return DisruptionCheck(build_travel_sources(get_settings(), cache_only=mode == "cached", operation_snapshot=True)).check


def _risk_sig(item: dict[str, Any]) -> str:
    """위험 점검 결과를 정하는 일정 칸 — 이것이 같으면 같은 점검이다(종류 · 날짜 · 시각 · 고정 · 장소 이름과 좌표)."""
    place = item.get("place") or {}
    return json.dumps([item.get(k) for k in ("kind", "date", "end_date", "starts_at", "ends_at", "locked")]
                      + [place.get(k) for k in ("name", "latitude", "longitude", "content_id")], ensure_ascii=False, default=str)


def _reusable(previous: dict[str, Any] | None, now: datetime) -> dict[str, tuple[str, dict[str, Any]]]:
    """앞 판에서 `REUSE_FRESH_S` 안에 새로 점검한 일정의 결과 — {일정 id: (서명, 위험)}. 한도에 걸려 못 본 것 · 점검 오류는 다시 본다."""
    if not previous or previous.get("risk_schema_version") != SCHEMA_VERSION or previous.get("risk_mode") != "fresh":
        return {}
    try:
        at = datetime.fromisoformat(str(previous.get("risk_checked_at")))
    except ValueError:
        return {}
    if at.tzinfo is None or not timedelta(0) <= now - at <= timedelta(seconds=REUSE_FRESH_S):
        return {}
    return {str(it.get("id")): (_risk_sig(it), it["risk"]) for it in previous.get("items", [])
            if isinstance(it.get("risk"), dict) and it["risk"].get("code") not in ("item_limit", "check_error")}


def decorate(conn, *, tenant_id: str, review: dict[str, Any], mode: str,
             check: Callable[..., dict[str, Any]] | None = None, now: datetime | None = None,
             reuse: dict[str, Any] | None = None) -> dict[str, Any]:
    """위험을 덧붙인 사본. 일정·기존 검사 결과·등록 가능 판정은 바꾸지 않는다.

    `reuse` `[2026-10-20]` 앞 판의 검사(위험을 붙인 것) — 새로 점검(`fresh`)할 때 앞 판에서 방금(`REUSE_FRESH_S` 안) 점검한 일정이 그대로면
    그 결과를 쓴다(바깥 조회를 다시 하지 않는다). 그 결과의 점검 시각(`checked_at`)은 앞 판 값 그대로 남는다."""
    from app.core.settings import get_guardrails

    now = now or datetime.now(KST)
    earlier = _reusable(reuse, now) if mode == "fresh" else {}
    try:
        checker = check or check_for(mode)
    except Exception:  # noqa: BLE001 — 소스 조립 실패도 확인 불가로 보인다
        def checker(**kwargs):
            raise RuntimeError("risk check unavailable")
    guard = get_guardrails()
    limit = int(guard.get("travel.mcp.risk_check.max_items"))
    snapshot = float(guard.get("travel.mcp.risk_check.snapshot_hours"))
    items, checked = [], 0
    for item in review.get("items", []):
        shown = dict(item)
        if item.get("kind") == "mobility":
            items.append(shown)
            continue
        same = earlier.get(str(item.get("id")))
        if same is not None and same[0] == _risk_sig(item):
            shown["risk"] = same[1]
            checked += same[1].get("status") != "not_applicable" and same[1].get("code") != "no_time"   # 한도는 앞 판과 같은 일정에 걸리게 센다
            items.append(shown)
            continue
        parsed = to_item(conn, tenant_id, item)
        if parsed is None:
            risk = _unknown(item, "no_time", "방문 날짜·시각을 정하면 위험을 확인해요")
        elif parsed.ends_at is not None and parsed.ends_at <= now:
            risk = {**_unknown(item, "past", "끝난 일정이라 현재 위험을 다시 판단하지 않아요"), "status": "not_applicable"}
        elif checked >= limit:
            risk = _unknown(item, "item_limit", "한 번에 확인할 수 있는 일정 수에 닿았어요 · 이 일정은 아직 확인하지 못했어요")
        else:
            risk = risk_report.judge_item(checker, parsed, mode=mode, at=now, snapshot_hours=snapshot)
            risk = _for_trip_date(risk, far=parsed.starts_at - now > timedelta(hours=CURRENT_ALERT_HOURS))
            checked += 1
        shown["risk"] = _present(risk, mode, now)
        items.append(shown)
    return {**review, "items": items, "risk_schema_version": SCHEMA_VERSION, "risk_mode": mode,
            "risk_checked_at": now.isoformat(timespec="seconds")}


def to_item(conn, tenant_id: str, item: dict[str, Any], *, seq: int | None = None) -> Item | None:
    from .review import _dt

    start = _dt(item.get("date"), item.get("starts_at"))
    if start is None:
        return None
    end = _dt(item.get("end_date") or item.get("date"), item.get("ends_at"))
    place = dict(item["place"]) if item.get("place") else None
    if place is not None:
        place.setdefault("place_id", str(uuid5(NAMESPACE_URL, "intake-place:" + str(item.get("id")))))
        place.setdefault("kind", item.get("kind"))
        _sensitivity(conn, tenant_id, place)
    return Item(item_id=uuid5(NAMESPACE_URL, "intake-item:" + str(item.get("id"))), seq=seq or 1,
                kind=item["kind"], title=item.get("title") or "일정", starts_at=start, ends_at=end,
                place_id=place.get("place_id") if place else None, place=place,
                locked=bool(item.get("locked")), detail={"customer_pinned": bool(item.get("locked"))})


def alternatives(conn, *, tenant_id: str, review: dict[str, Any], item: dict[str, Any],
                 now: datetime | None = None, limit: int = 3, engine=None, use_engine: bool = True,
                 check: Callable[..., dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """위험 있는 활동의 안전 대안. 조회만 하고 고객 선택은 기존 edits가 처리한다."""
    from app.domains.travel_ops.components.itinerary.itinerary_changes import RELAX_ACTIVITY_RADII_M, relaxed_options
    from app.domains.travel_ops.components.places.catalog_pool import nearby_activities, reuse_hours
    from app.domains.travel_ops.components.planning.replan import WEATHER_LIKE
    from app.domains.travel_ops.components.watch.watch_relaxed import VerificationUnavailable, verified_options
    from . import candidates

    risk = item.get("risk") or {}
    if item.get("kind") != "activity" or risk.get("status") != "problem":
        return None
    now = now or datetime.now(KST)
    base = {"item": item["id"], "current": candidates.public_place(item.get("place")), "reference": {},
            "candidates": [], "notes": ["risk_alternatives"], "checked_at": now.isoformat()}
    if item.get("locked") or item.get("booked") or item.get("vendor_booking"):
        return {**base, "notes": ["risk_alternatives", "protected_schedule"]}
    current, parts = None, []
    for seq, row in enumerate(review.get("items", []), 1):
        parsed = to_item(conn, tenant_id, row, seq=seq)
        if parsed:
            parts.append(parsed)
            if row["id"] == item["id"]:
                current = parsed
    if current is None or not current.place or current.place.get("latitude") is None or current.place.get("longitude") is None:
        return {**base, "notes": ["risk_alternatives", "no_reference_point"]}
    if current.ends_at is not None and current.ends_at <= now:
        return {**base, "notes": ["risk_alternatives", "past_schedule"]}
    checker = check or check_for("fresh")
    causes = risk.get("problems") or []
    indoor_only = any(c.get("category") in WEATHER_LIKE for c in causes)
    trip = {"version": 1, "party_size": review.get("party_size"), "constraints": {}}
    previous, following = candidates.neighbours(review["items"], item)
    budget = engine
    if budget is None and use_engine:
        budget = candidates.default_engine(review.get("party_size"))
    budget = candidates._Budgeted(budget, candidates.ENGINE_BUDGET_S) if budget is not None else None
    seen = {str((row.get("place") or {}).get("name")) for row in review.get("items", [])}
    all_places, by_id, unavailable = [], {}, []
    for radius in RELAX_ACTIVITY_RADII_M:
        pool = nearby_activities(conn, tenant_id, latitude=float(current.place["latitude"]),
                                 longitude=float(current.place["longitude"]), radius_m=radius,
                                 exclude_names=seen, require_hours=True, indoor_only=indoor_only, now=now)
        reuse_hours(conn, tenant_id, pool, now)
        for cand in pool:
            seen.add(cand.name)
            spot = {"place_id": str(uuid5(NAMESPACE_URL, "intake-candidate:" + cand.key)), "name": cand.name,
                    "kind": "activity", "latitude": cand.lat, "longitude": cand.lon,
                    "weather_sensitive": cand.weather_sensitive, "attributes": dict(cand.attributes)}
            all_places.append(spot)
            by_id[spot["place_id"]] = (spot, cand)
        options = relaxed_options(trip=trip, items=parts, places=all_places, current=current, causes=causes,
                                  now=now, wide_radius_m=radius)
        try:
            options = verified_options(trip=trip, items=parts, places=all_places, current=current,
                                       options=options, check=checker)
        except VerificationUnavailable as exc:
            unavailable.extend(exc.categories)
            continue
        out = []
        for option in options:
            spot, cand = by_id[str(option["place_id"])]
            start, end = datetime.fromisoformat(option["starts_at"]), datetime.fromisoformat(option["ends_at"])
            if start.date() != end.date():
                continue  # 현재 활동 edits 계약은 끝 날짜를 수정하지 않는다
            selected = {**item, "date": start.date().isoformat(), "starts_at": start.strftime("%H:%M"),
                        "ends_at": end.strftime("%H:%M"), "end_date": end.date().isoformat() if end.date() != start.date() else None}
            public = candidates._place(cand.name, cand.lat, cand.lon, "tour_api", kind="activity",
                                       content_id=cand.attributes["source_content_id"],
                                       content_type_id=cand.attributes.get("source_content_type_id"),
                                       address=cand.attributes.get("address"), ref="tour:" + cand.attributes["source_content_id"])
            assessed = candidates.assess(conn, tenant_id, selected, public, previous, following, budget)
            if not assessed["fits"]:
                continue
            judged = risk_report.judge_item(checker, Item(item_id=current.item_id, seq=current.seq, kind="activity",
                title=cand.name, starts_at=start, ends_at=end, place_id=spot["place_id"], place=spot), mode="fresh", at=now)
            unknown = judged.get("unknown_categories") or []
            partial_traffic_only = bool(unknown) and all(
                r.get("category") == "traffic_control" and r.get("code") == "partial" for r in unknown)
            if judged["status"] != "clear" and not (judged["status"] == "unknown" and partial_traffic_only):
                unavailable.extend(x["category"] for x in judged.get("unknown_categories", []))
                continue
            note = option["note"]
            if partial_traffic_only:
                warning = "교통통제 자료 일부를 확인하지 못했어요 · 확인된 범위에서 위험은 발견되지 않았어요"
                assessed = {**assessed, "status": "warn", "rows": [*assessed["rows"], candidates._line("risk", "unknown", warning)]}
                note = "교통자료 일부 미확인 · " + note
            shown = candidates._present(public, assessed, previous, following, (current.place["latitude"], current.place["longitude"]))
            out.append({**shown, "rank": len(out) + 1, "reason": note, "reason_by": "template",
                        "date": selected["date"], "starts_at": selected["starts_at"], "ends_at": selected["ends_at"],
                        "end_date": selected["end_date"], "risk": _present(judged, "fresh", now)})
            if len(out) >= limit:
                break
        if out:
            coverage_warning = any(candidate["risk"]["status"] == "unknown" for candidate in out)
            label = "indoor_with_coverage_warning" if coverage_warning else "verified_indoor" if indoor_only else "verified_safe"
            return {**base, "candidates": out, "notes": ["risk_alternatives", label],
                    "radius_m": radius}
    return {**base, "notes": ["risk_alternatives", "verification_unavailable" if unavailable else "no_verified_alternative"],
            "unknown_categories": sorted(set(unavailable))}


def _sensitivity(conn, tenant_id: str, place: dict[str, Any]) -> None:
    if isinstance(place.get("weather_sensitive"), bool):
        return
    from .hours import _tenants

    try:
        with conn.transaction(), conn.cursor() as cur:
            if place.get("place_id"):
                cur.execute("SELECT weather_sensitive FROM places WHERE tenant_id=%s AND place_id=%s",
                            (tenant_id, place["place_id"]))
                found = cur.fetchone()
                if found is not None and isinstance(found[0], bool):
                    place["weather_sensitive"] = found[0]
                    return
            cur.execute("SELECT raw_json->>'lclsSystm1',raw_json->>'lclsSystm2' FROM place_catalog "
                        "WHERE tenant_id=ANY(%s) AND source='tour_api' AND content_id=%s LIMIT 1",
                        (_tenants(tenant_id), str(place.get("content_id") or "")))
            found = cur.fetchone()
            place["weather_sensitive"] = weather_from_class(*found) if found else None
    except Exception:  # noqa: BLE001 — 실내인지 모르면 점검기가 보수적으로 날씨를 점검한다
        place["weather_sensitive"] = None


def _for_trip_date(risk: dict[str, Any], *, far: bool) -> dict[str, Any]:
    """먼 일정이면 「지금 상태」 원인(`as_of_now` — 점검기가 시작이 먼 일정에 붙인다)을 문제에서 뺀다. 예보처럼 그 시각을 본 원인은 남긴다.

    뺀 원인이 있고 남은 문제가 없으면 「문제」가 아니라 「아직 확인 전」(`unknown` · `too_early`)이다 — 「문제 없음」이라고 말하지도 않는다(지금 상태 종류는 그 날짜를 확인하지 못했다).
    뺀 개수는 `deferred_current` 에 남긴다(조용히 버리지 않는다). 일정 · 등록 가능 판정은 바꾸지 않는다."""
    if not far:
        return risk
    problems = list(risk.get("problems") or [])
    dated = [p for p in problems if not p.get("as_of_now")]
    if len(dated) == len(problems):
        return risk
    out = {**risk, "problems": dated, "deferred_current": len(problems) - len(dated)}
    if dated:
        return out
    return {**out, "status": "unknown", "code": "too_early", "reason": FAR_REASON}


def _unknown(item: dict[str, Any], code: str, reason: str) -> dict[str, Any]:
    return {"item_id": item.get("id"), "status": "unknown", "problems": [], "categories": [],
            "unknown_categories": [], "cautions": [], "code": code, "reason": reason}


def _present(risk: dict[str, Any], mode: str, now: datetime) -> dict[str, Any]:
    from app.domains.travel_ops.components.planning.pending import _cause_text

    problems = [{**problem, "summary": _cause_text([problem])} for problem in risk.get("problems", [])]
    return {**risk, "problems": problems, "mode": mode, "checked_at": risk.get("checked_at") or now.isoformat(),
            "data_confirmed_at": risk.get("oldest_confirmed_at"),
            "stale": risk.get("status") == "unknown" and mode == "cached"}
