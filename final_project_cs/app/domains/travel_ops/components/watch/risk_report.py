# -*- coding: utf-8 -*-
"""일정 위험 점검 보고 — 「내 여행의 곧 시작할 일정에 외부 정보 6종이 문제를 가리키나」. `[2026-10-06 사용자 요청 — 개인 AI 입구(MCP) 읽기 도구]`

외부 정보 6종 = 날씨 예보 · 기상 특보 · 재난문자 · 교통 통제 · 대기질 · 지진(`DisruptionCheck.check`). 감시(3분 주기)가 돌리는 점검과 **같은 점검**이다 —
이 파일은 그 결과를 **사람(과 개인 AI)이 읽을 모양**으로 바꿀 뿐 새 판정을 만들지 않는다.

★항목마다 셋 중 하나다 — `problem`(문제 있음 · 원인) · `clear`(6종을 다 확인했고 문제 없음) · `unknown`(문제는 못 찾았지만 **못 확인한 종류가 있다**).
  ★**확인 불가를 「문제 없음」으로 말하지 않는다**(결정 15 · RULE §3.2). 6종 중 하나라도 소스가 못 답했거나(실패 · 미연결 · 캐시에 없음 · 응답에 없음) **일부만 답했거나**(`partial` — 교통은 ITS · UTIC 중 한쪽만)
  장소를 몰라 점검을 못 했으면 `clear` 가 아니다. 문제가 하나라도 찾아졌으면 못 확인한 종류가 있어도 `problem`(찾은 문제가 사실이다) — 못 확인한 종류는 `unknown_categories` 에 따로 적는다.
★「해당 없음」(실내 장소의 예보 · 특보)은 확인 불가가 아니다 — 볼 필요가 없다는 아는 사실이다. 그래서 `clear` 는 「**볼 필요가 있는 종류를 모두** 확인했다」는 뜻이다.
★`[2026-10-06 검토 반영]` **점검은 `max(항목 시작, 기준 시각)` 으로 한다** — 이미 시작한 항목을 시작 시각으로 점검하면 시작 뒤에 난 사건(재난문자 · 지진 · 교통)이 창 밖이라 안 보인 채 `clear` 가 된다.
  ★**아직 멀리 있는 항목**(시작이 기준 시각보다 `snapshot_hours` 이상 뒤)은 특보 · 대기질 · 교통 · 재난문자 · 지진이 **「지금 상태」만** 말한다(그 시각의 값이 아니다 — 대기질은 `at` 을 무시하고 지금 값을 준다) →
  그 종류는 `too_early`(확인 불가)로 두고 `clear` 로 말하지 않는다. 문제가 찾아졌으면 `problem` 이되 그 원인에 `as_of_now` 를 붙인다. 예보만 앞을 본다.
★확인 시각은 두 개다 — `checked_at`(이 보고를 만든 시각)과 종류마다 `confirmed_at`(그 소스 값을 **처음 받아 온** 시각 — 캐시에서 꺼낸 값이면 그때). 재사용한 값에 「지금 확인」을 찍지 않는다(`TravelSource.stamp`).
★`mode` — `cached`: 감시가 모아 둔 공유 응답 캐시만 읽는다(바깥으로 안 나간다 · 하루 한도를 안 쓴다 — 캐시에 없는 종류는 `unknown`). `fresh`: 캐시에 없으면 새로 부른다(낮은 우선순위 · 항목 수 · 횟수 제한).
★이유 문구는 **고정 문장**이다 — 점검기가 돌려준 `reason`(소스 미연결 사유에 환경변수 이름 · 파일 이름이 들어 있다)을 고객 · 개인 AI 에게 내보내지 않는다.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import UUID

from app.domains.travel_ops.components.itinerary.itinerary import Item

logger = logging.getLogger(__name__)

#: 점검 6종 — 부르는 이름 · 사람이 읽는 이름
CATEGORIES: dict[str, str] = {
    "forecast": "날씨 예보", "weather_warning": "기상 특보", "disaster_msg": "재난문자",
    "traffic_control": "교통 통제", "air_quality": "대기질", "earthquake": "지진",
}
#: 「지금 상태」만 말하는 종류 — 아직 먼 항목의 그 시각을 말하지 못한다(예보만 앞을 본다)
CURRENT_STATE = ("weather_warning", "air_quality", "traffic_control", "disaster_msg", "earthquake")
#: ★캐시만 읽는 호출은 「캐시에 없다」와 「소스가 실패했다」를 가르지 못한다(소스가 알려 주지 않는다) — 이유 문구가 둘을 다 말한다(캐시 부재로 단정하지 않는다)
NOT_CACHED = "캐시에서 읽지 못했어요 — 감시가 아직 확인하지 않았거나 확인한 지 오래됐거나 소스가 실패했을 수 있어요(새로 확인하려면 fresh)"
REASONS = {
    "not_cached": NOT_CACHED,
    "source_failed": "새로 확인했지만 값을 못 냈어요 — 소스가 실패했거나 낮은 우선순위 한도에 닿았을 수 있어요",
    "not_connected": "이 서버에 연결되지 않은 소스예요",
    "missing": "점검 결과에 이 종류가 없어요",
    "partial": "소스 일부만 답했어요 — 빠진 쪽이 알려 줄 사건(예: 집회 · 행사)을 놓쳤을 수 있어요",
    "too_early": "아직 시작까지 시간이 남은 일정이라 지금 상태만 확인돼요 — 시작이 가까워지면 다시 점검해 주세요",
}


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def _when(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _plain(value: Any) -> Any:
    """JSON 으로 그대로 나가게 — 시각은 글자로, 모르는 모양은 글자로."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return _iso(value) if isinstance(value, datetime) else str(value)


def _category_rows(report: dict[str, Any], mode: str, *, too_early: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """6종마다 한 줄 + 읽을 때 알아 둘 주의(`cautions`). 응답에 없는 종류는 확인 불가로 채우고, 일부만 답한 종류는 확인 불가로 내린다."""
    rows, notes = [], []
    checks = list(report.get("checks") or [])
    present = {str(c.get("category")) for c in checks}
    checks += [{"category": name, "status": "missing"} for name in CATEGORIES if name not in present]
    for check in checks:
        name = str(check.get("category"))
        label = CATEGORIES.get(name, name)
        status = check.get("status")
        row: dict[str, Any] = {"category": name, "label": label}
        if status == "ok":
            row.update(status="ok", source=check.get("source"), confirmed_at=_plain(check.get("confirmed_at")))
            if check.get("fell_back_from"):
                row["fell_back_from"] = _plain(check["fell_back_from"])
            partial = check.get("partial_from")
            if partial:                                              # 일부 소스만 답했다 — 「다 확인했다」가 아니다
                row.update(status="unknown", code="partial", reason=REASONS["partial"], answered_by=_plain(check.get("sources")), missing_from=_plain(partial))
            elif too_early and name in CURRENT_STATE:
                row.update(status="unknown", code="too_early", reason=REASONS["too_early"], as_of="now")
            unclassified = check.get("unclassified") or []
            if unclassified:                                         # 재해구분을 못 알아본 문자가 있다 — 사건일 수도 있다. 숨기지 않고 알린다
                row["unclassified_count"] = len(unclassified)
                notes.append({"category": name, "label": label, "note": f"재해구분을 알아보지 못한 재난문자가 {len(unclassified)}건 있어요"})
            if name == "air_quality" and str(check.get("mode") or "").lower() == "model":
                row["estimated"] = True
                notes.append({"category": name, "label": label, "note": "대기질이 측정값이 아니라 모델 추정이에요"})
        elif status == "not_applicable":
            row.update(status="not_applicable", reason=check.get("reason"))              # 해당 없음 — 확인 불가가 아니다(문구는 점검기의 고정 사유)
        else:
            code = "missing" if status == "missing" else "not_connected" if status == "not_connected" else "not_cached" if mode == "cached" else "source_failed"
            row.update(status="unknown", code=code, reason=REASONS[code])               # ★점검기의 reason 은 내보내지 않는다(환경변수 · 파일 이름이 들어 있다)
        rows.append(row)
    return rows, notes


def _problem(item: dict[str, Any], *, as_of_now: bool) -> dict[str, Any]:
    name = str(item.get("category"))
    out = {"label": CATEGORIES.get(name, name), **_plain(item)}
    text = out.get("text") or out.get("kind") or out.get("note") or out.get("source") or ""
    out["summary"] = f"{out['label']}: {text}" if text else out["label"]
    if as_of_now and name in CURRENT_STATE:
        out["as_of_now"] = True                                    # 아직 먼 일정 — 지금 일어나 있는 일이다(그 시각의 일이 아니다)
    return out


def judge_item(check: Callable[..., dict[str, Any]], item: Item, *, mode: str, at: datetime | None = None, snapshot_hours: float = 3.0) -> dict[str, Any]:
    """항목 하나를 점검해 보고 줄 하나로. ★점검이 죽어도 이 줄만 `unknown` 이 된다(다른 항목은 계속)."""
    base: dict[str, Any] = {"item_id": str(item.item_id), "seq": item.seq, "kind": item.kind, "title": item.title,
                            "starts_at": _iso(item.starts_at), "ends_at": _iso(item.ends_at),
                            "place": (item.place or {}).get("name")}
    if item.place is None or item.place.get("latitude") is None or item.place.get("longitude") is None:
        return {**base, "status": "unknown", "problems": [], "cautions": [], "unknown_categories": [],
                "categories": [], "reason": "장소(좌표)를 몰라 6종을 점검할 수 없어요", "code": "no_place"}
    moment = at or item.starts_at
    check_at = max(item.starts_at, moment)                           # 이미 시작한 항목은 지금 기준으로 점검한다(시작 뒤 사건이 창 밖이 되지 않게)
    too_early = (item.starts_at - moment) > timedelta(hours=snapshot_hours)
    try:
        report = check(place=item.place, starts_at=check_at)
    except Exception:                                                  # noqa: BLE001 — 한 항목의 실패가 다른 항목을 막지 않는다
        logger.exception("risk check failed item=%s", item.item_id)
        return {**base, "status": "unknown", "problems": [], "cautions": [], "unknown_categories": [],
                "categories": [], "reason": "점검 중 오류가 났어요", "code": "check_error"}
    rows, notes = _category_rows(report, mode, too_early=too_early)
    problems = [_problem(p, as_of_now=too_early) for p in report.get("disruptions") or []]
    unknown = [{"category": r["category"], "label": r["label"], "code": r["code"], "reason": r["reason"]} for r in rows if r["status"] == "unknown"]
    status = "problem" if problems else ("unknown" if unknown else "clear")
    confirmed = sorted((w, str(r["confirmed_at"])) for r in rows if r.get("confirmed_at") and (w := _when(r["confirmed_at"])) is not None)
    return {**base, "status": status, "problems": problems, "cautions": [_plain(a) for a in report.get("advisories") or []] + notes,
            "unknown_categories": unknown, "categories": rows, "checked_at": _plain(report.get("checked_at")), "checked_for": _iso(check_at),
            "oldest_confirmed_at": confirmed[0][1] if confirmed else None}


def pick_items(items: list[Item], *, at: datetime, horizon_hours: float, max_items: int, item_id: UUID | None) -> tuple[list[Item], list[dict[str, Any]]]:
    """점검할 항목과 건너뛴 항목(이유). 기본은 `at` 부터 `horizon_hours` 안에 시작하거나 지금 진행 중인 항목, 시작이 빠른 순 최대 `max_items`.

    ★끝나는 시각이 정확히 `at` 인 항목은 진행 중으로 본다. **끝 시각을 모르는 항목은 시작한 뒤에는 진행 중으로 보지 않는다**(끝을 지어내지 않는다).
    ★`item_id` 를 주면 그 항목 하나만(시간 범위를 보지 않는다 — 사용자가 짚었다). 여행에 없는 항목이면 `LookupError`."""
    if item_id is not None:
        found = next((i for i in items if i.item_id == item_id), None)
        if found is None:
            raise LookupError("item not found")
        return [found], []
    end = at + timedelta(hours=horizon_hours)
    window = sorted((i for i in items if (i.ends_at or i.starts_at) >= at and i.starts_at <= end), key=lambda i: (i.starts_at, i.seq))
    skipped: list[dict[str, Any]] = []
    chosen: list[Item] = []
    for item in window:
        if item.kind == "mobility":
            # 이동 항목은 장소가 없다 — 길 위 사건은 감시의 경로 점검(`trip_events`)이 본다. 이 점검의 6종은 장소 기준이다
            skipped.append({"item_id": str(item.item_id), "title": item.title, "reason": "mobility", "note": "이동 항목은 장소 기준 6종 점검 대상이 아니에요"})
        elif len(chosen) >= max_items:
            skipped.append({"item_id": str(item.item_id), "title": item.title, "reason": "over_limit", "note": f"한 번에 최대 {max_items}개까지 점검해요"})
        else:
            chosen.append(item)
    return chosen, skipped


def build_report(*, trip_id: UUID, version: int, items: list[Item], check: Callable[..., dict[str, Any]], at: datetime, horizon_hours: float,
                 max_items: int, item_id: UUID | None, mode: str, snapshot_hours: float = 3.0) -> dict[str, Any]:
    chosen, skipped = pick_items(items, at=at, horizon_hours=horizon_hours, max_items=max_items, item_id=item_id)
    rows = [judge_item(check, item, mode=mode, at=at, snapshot_hours=snapshot_hours) for item in chosen]
    summary = {"problem": 0, "clear": 0, "unknown": 0}
    for row in rows:
        summary[row["status"]] += 1
    notes = []
    if mode == "cached":
        notes.append("감시가 모아 둔 최근 결과만 읽었어요(바깥에 새로 묻지 않아요). 결과가 없는 종류는 확인 불가예요.")
    if any(u["code"] == "too_early" for row in rows for u in row.get("unknown_categories") or []):
        notes.append(f"시작까지 {snapshot_hours:g}시간 넘게 남은 일정은 특보 · 교통 · 재난 · 대기질 · 지진이 지금 상태만 말해 확인 불가로 두었어요(예보만 앞을 봐요).")
    if not rows and not skipped:
        notes.append(f"지금부터 {horizon_hours:g}시간 안에 시작하는 점검 대상 일정이 없어요.")
    return {"trip_id": str(trip_id), "version": version, "at": _iso(at), "mode": mode, "scope": "item" if item_id else "upcoming",
            "horizon_hours": horizon_hours, "snapshot_hours": snapshot_hours, "items": rows, "skipped": skipped,
            "summary": {**summary, "checked": len(rows)}, "notes": notes, "categories": [{"category": k, "label": v} for k, v in CATEGORIES.items()]}


__all__ = ["CATEGORIES", "CURRENT_STATE", "NOT_CACHED", "REASONS", "build_report", "judge_item", "pick_items"]
