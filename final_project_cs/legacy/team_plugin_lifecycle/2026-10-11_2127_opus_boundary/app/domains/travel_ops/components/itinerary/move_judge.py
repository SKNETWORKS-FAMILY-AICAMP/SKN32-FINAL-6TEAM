# -*- coding: utf-8 -*-
"""이동 판정 — 「두 장소 사이를 몇 시에 떠나 · 어떤 경로로 · 얼마나 걸리나」. `[2026-10-06 사용자 요청 — 개인 AI 입구(MCP) 읽기 도구]`

계산은 이미 있는 **이동 판정기**(`team_hooks.legs.leg_planner`)가 한다. 이 파일은 그 결과를 사람(과 개인 AI)이 읽을 모양으로 바꾸고
**못 하는 경우를 그대로 말한다** — 새 판정 · 새 어림 공식을 만들지 않는다.

★결과마다 `grade`(근거 등급)가 붙는다 — **고른 경로가 무엇에 근거하나**로 가른다(`[2026-10-06 코덱스 검토]` 앞 판은 판정기가 경로를 냈다는 이유만으로 모두 시간표라고 했다).
    `timetable`  고른 경로가 **열차(지하철 · 철도)**다(`uses` 에 노선이 있고 버스가 없다 — 열차 단위 시간표로 판정한 것). 어느 시간표 판으로 냈는지(`basis`)와 시간표가 낡았는지(`timetable_stale`)를 같이 싣는다.
                 ★「시간표 판정」이지 **실시간 운행 확정이 아니다**(지연 · 사고는 반영하지 않는다).
    `estimate`   ①고른 경로가 **도보 · 택시 · 버스**(버스가 하나라도 낀 경로)다 — 열차 시간표가 아니다: 도보 · 택시는 거리 · 도로 길찾기로, 버스는 노선 단위 첫차 · 막차 · 배차 **추정**으로 셈한 값이다
                 (도보는 보행망 길찾기가 없으면 직선 거리 × 우회계수 — 어느 쪽인지 판정기가 알려 주지 않는다).
                 ②판정기가 꺼져 있거나 닿지 않아 **직선 거리 어림값**만 낸다(`status=unavailable` — 경로 · 출발 시각은 없다. 지어내지 않는다).
    `none`       판정기가 「이 시각엔 갈 방법이 없다」(막차 뒤 · 첫차 전 …)고 답했다(`status=no_route`) **또는 판단하지 못했다**(`status=undetermined` — 데이터 없음 · 확인 못 함 · 택시 길찾기 불통: 「갈 방법이 없다」는 뜻이 아니다).
                 판정기의 이유를 싣고 **어림값을 덧붙이지 않는다**(판정기가 안 된다고 한 것을 직선 거리로 되살리지 않는다). 이유 문구에서 주소 · 환경변수 · 파일 경로는 가린다(`_scrub`).
  ★대안(`alternatives[]`)에도 경로마다 `grade` 가 붙는다.
★우리 서비스 범위는 서울이다 — 서울 둘레 사각형 밖 좌표는 판정하지 않는다(`status=out_of_scope`, `grade=none`). 이 검사는 판정기 · 근거 조회보다 **먼저** 한다.
★판정기가 예외를 던지거나 이상한 모양을 돌려주면 500 이 아니라 `status=unavailable`(`reason.code=engine_error`) + 직선 어림이다 — 이유는 로그에만 남는다(내부 오류 문구를 내보내지 않는다).
★출발 시각(`depart_at`)을 주면 판정기는 **도착 목표에서 거꾸로** 셈하므로 도착 목표를 `출발 + 90분 → 180분 → 360분` 으로 **최대 셋** 넓혀 가며 첫 성립 경로를 찾는다(앞 판은 90분 하나였다 — 그 안에 도착할 수 없으면 가는 길이 있어도 `no_route`).
  못 찾으면 `no_route` 에 `searched`(어디까지 봤나)를 싣는다 — 6시간 넘게 걸리는 길은 「없다」가 아니라 「안 찾았다」다. 찾은 뒤에는 그 소요에 맞춘 목표로 한 번 더 판정해 출발 시각을 앞으로 당긴다(둘째가 안 되면 첫 결과 — 그것이 가장 이른 출발이라는 보장은 없다).
  `depart_at` 결과에는 `requested_depart_at` 과 `wait_min`(요청 시각 → 판정기가 고른 출발 시각까지 분)이 붙는다. ★둘째 판정이 안 돼 첫 결과를 쓴 경우 `earliest_not_guaranteed=true` —
  판정기는 「가장 늦게 떠나도 되는 후보」를 고르므로 그 출발이 **가장 이른 출발이라는 보장이 없고** `wait_min` 이 첫차 대기가 아니라 탐색 방식 때문에 커졌을 수 있다. 도착 시각(`arrive_by`)이면 한 번만 부른다. 둘 다 안 주면 지금 출발이다.
★바깥 **유료** 소스(Places · Route Matrix)는 이 경로에 없다 — 판정기는 이 서버의 시간표 · 도로 그래프와 **자체 길찾기 서버**(GraphHopper — 설정한 주소를 부른다)만 쓴다(2026-10-06 코드 확인: 이동 판정기 폴더에 Google 호출 없음).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Callable

from app.domains.travel_ops.components.conversation.trip_here import SEOUL_BOX
from app.domains.travel_ops.components.planning.replan import distance_m, walk_minutes
from app.domains.travel_ops.components.team_hooks import legs

logger = logging.getLogger(__name__)

GRADE_LABELS = {"timetable": "시간표 기준 판정", "estimate": "어림(시간표 아님)", "none": "근거 없음"}
#: 출발 시각을 줬을 때 도착 목표를 넓혀 가는 단계(분) — 마지막이 「어디까지 봤나」다. ★우리가 고른 값
_TARGET_STEPS_MIN = (90, 180, 360)
#: 판정기가 「판단하지 못했다」는 이유 코드 — 「갈 방법이 없다」가 아니다(데이터 없음 · 확인 못 함 · 택시 길찾기 불통 · 앞당긴 탐색을 못 끝냄)
_UNDETERMINED = frozenset({"no_data", "not_confirmed", "taxi_unavailable", "earliest_unconfirmed"})
#: 주소 · 환경변수 · 파일 경로 — 판정기가 오류 문구에 싣는 내부 정보(GraphHopper 주소 등)가 개인 AI 에게 새지 않게 가린다
_LEAK = re.compile(r"https?://\S+|\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b|ACOP_\w+|\.env\S*|[A-Za-z]:\\\S+|localhost\S*", re.IGNORECASE)


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return _LEAK.sub("<가림>", value)
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    return value


class InvalidPlace(ValueError):
    """장소를 못 읽었다 — 이름 · 좌표가 없다."""


def as_place(raw: dict[str, Any], *, key: str) -> dict[str, Any]:
    """판정기가 받는 장소 모양(`{key, name, kind, lat, lon, weather_sensitive, attributes}`). 좌표가 숫자가 아니면 `InvalidPlace`."""
    try:
        lat, lon = float(raw["lat"]), float(raw["lon"])
    except (KeyError, TypeError, ValueError):
        raise InvalidPlace("lat · lon 이 필요해요") from None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise InvalidPlace("좌표 범위가 맞지 않아요")
    return {"key": key, "name": str(raw.get("name") or "이름 없음")[:80], "kind": "activity", "lat": lat, "lon": lon,
            "weather_sensitive": None, "attributes": {}}


def _in_seoul(place: dict[str, Any]) -> bool:
    lat_min, lat_max, lon_min, lon_max = SEOUL_BOX
    return lat_min <= place["lat"] <= lat_max and lon_min <= place["lon"] <= lon_max


def _grade_of(option: dict[str, Any]) -> str:
    """경로 하나가 무엇에 근거하나 — **열차**(`uses` 에 노선이 있고 버스가 없다)면 시간표, 도보 · 택시 · 버스가 낀 경로면 어림(버스는 노선 단위 배차 추정)."""
    uses = option.get("uses") or []
    if not uses or any(str(u).startswith("버스") for u in uses):
        return "estimate"
    return "timetable"


def _option(option: dict[str, Any]) -> dict[str, Any]:
    return {**{k: option[k] for k in ("id", "label", "eta_min", "walk_m", "fare_krw", "uses") if k in option}, "grade": _grade_of(option)}


def _safe_basis() -> dict[str, Any] | None:
    """판정 근거 — 읽다가 죽어도 판정 자체를 막지 않는다(근거를 모르면 `None`)."""
    try:
        return legs.basis()
    except Exception:                                                  # noqa: BLE001
        logger.exception("move judge: basis unreadable")
        return None


def _valid(got: Any) -> bool:
    """판정기 결과의 모양 — 이상하면 경계에서 거른다."""
    return (isinstance(got, dict) and isinstance(got.get("route"), dict) and isinstance(got.get("starts_at"), datetime)
            and isinstance(got.get("ends_at"), datetime) and isinstance(got.get("eta_min"), (int, float)))


def _judged(got: dict[str, Any], *, tz: Any) -> dict[str, Any]:
    route = got["route"]
    options = [o for o in route.get("options") or [] if isinstance(o, dict)]
    planned = next((o for o in options if o.get("id") == route.get("planned")), None)
    if planned is None:
        raise ValueError("판정기 결과에 고른 경로가 없다")
    local = (lambda m: m.astimezone(tz)) if tz is not None else (lambda m: m)
    grade = _grade_of(planned)
    out = {"status": "judged", "grade": grade, "grade_label": GRADE_LABELS[grade],
           "depart_at": local(got["starts_at"]).isoformat(), "arrive_at": local(got["ends_at"]).isoformat(),
           "eta_min": int(got["eta_min"]), "route": _option(planned),
           "alternatives": [_option(o) for o in options if o.get("id") != route.get("planned")],
           "left_out": [_left_out(e) for e in got.get("left_out") or [] if isinstance(e, dict)]}
    if grade == "estimate":
        out["grade_note"] = "고른 경로가 열차 시간표가 아니라 도보 · 택시(거리 · 도로 길찾기)나 버스(배차 추정)라 어림에 가까운 값이에요"
    return out


def _left_out(entry: dict[str, Any]) -> dict[str, Any]:
    """판정기가 뺀 후보 — 이름 · 코드 · (가린) 이유만 내보낸다."""
    return {k: _scrub(entry[k]) for k in ("label", "code", "reason") if k in entry}


def _estimate(origin: dict[str, Any], dest: dict[str, Any]) -> dict[str, Any]:
    meters = distance_m({"latitude": origin["lat"], "longitude": origin["lon"]}, {"latitude": dest["lat"], "longitude": dest["lon"]})
    return {"straight_line_m": int(round(meters)), "walk_minutes_estimate": walk_minutes(meters),
            "note": "직선 거리로 어림한 값이에요(실제 길 · 시간표가 아니에요)"}


def judge(*, origin: dict[str, Any], dest: dict[str, Any], now: datetime, depart_at: datetime | None = None, arrive_by: datetime | None = None,
          party_size: int | None = None, constraints: dict[str, Any] | None = None) -> dict[str, Any]:
    """두 장소 사이 이동을 판정한다. `origin` · `dest` 는 `as_place` 가 만든 모양. 시각은 시간대가 있는 값이어야 한다(`depart_at` · `arrive_by` 중 하나만 — 없으면 `now` 출발).

    ★이 함수는 어디에도 쓰지 않는다 — 읽기다. 판정기를 못 쓰는 이유는 결과의 `reason` 에 그대로 남는다."""
    if depart_at is not None and arrive_by is not None:
        raise ValueError("depart_at 과 arrive_by 는 둘 중 하나만 줄 수 있다")
    tz = (depart_at or arrive_by or now).tzinfo
    head = {"from": origin["name"], "to": dest["name"], "checked_at": now.isoformat(), "mode": "arrive_by" if arrive_by is not None else "depart_at"}
    if not (_in_seoul(origin) and _in_seoul(dest)):                    # ★판정기 · 근거에 닿기 전에 거른다
        return {**head, "basis": None, "status": "out_of_scope", "grade": "none", "grade_label": GRADE_LABELS["none"],
                "reason": {"code": "out_of_scope", "reason": "이 서비스는 서울만 다뤄요 — 서울 밖 장소는 판정하지 않아요"}}
    basis = _safe_basis()
    head["basis"] = basis
    try:
        leg = legs.leg_planner(party_size, constraints or {})
    except Exception:                                                  # noqa: BLE001 — 판정기를 못 만들면 「못 쓴다」
        logger.exception("move judge: leg planner could not be built")
        return _unavailable(head, origin, dest, "engine_error", "이동 판정기를 쓰는 중 오류가 났어요")
    if leg is None:
        why = f"이동 판정기가 꺼져 있거나 쓸 수 없어요(상태: {(basis or {}).get('mode', '알 수 없음')})"
        return _unavailable(head, origin, dest, "engine_unavailable", why)
    try:
        if arrive_by is not None:
            got, why = leg(origin, dest, arrive_by, None)
            searched, fallback = None, False
        else:
            got, why, searched, fallback = _depart_at(leg, origin, dest, depart_at or now)
        if got is not None:
            if not _valid(got):
                raise ValueError("판정기가 이상한 모양을 돌려줬다")
            out = _judged(got, tz=tz)
    except Exception:                                                  # noqa: BLE001 — 판정기 오류는 500 이 아니라 「못 쓴다」
        logger.exception("move judge: engine failed")
        return _unavailable(head, origin, dest, "engine_error", "이동 판정 중 오류가 났어요")
    if got is None:
        reason = _reason(why)
        undetermined = reason["code"] in _UNDETERMINED
        if undetermined:
            reason["reason"] = f"{reason['reason']} (판정기가 판단하지 못했다는 뜻이에요 — 갈 방법이 없다는 뜻이 아니에요)"
        return {**head, "status": "undetermined" if undetermined else "no_route", "grade": "none", "grade_label": GRADE_LABELS["none"], "reason": reason,
                **({"searched": searched} if searched else {})}
    if depart_at is not None or arrive_by is None:
        requested = depart_at or now
        out["requested_depart_at"] = requested.isoformat()
        out["wait_min"] = max(0, int(round((got["starts_at"] - requested).total_seconds() / 60)))
        if fallback:
            out["earliest_not_guaranteed"] = True
    return {**head, **out}


def _unavailable(head: dict[str, Any], origin: dict[str, Any], dest: dict[str, Any], code: str, reason: str) -> dict[str, Any]:
    return {**head, "status": "unavailable", "grade": "estimate", "grade_label": GRADE_LABELS["estimate"],
            "reason": {"code": code, "reason": reason}, "estimate": _estimate(origin, dest)}


def _depart_at(leg: Callable[..., Any], origin: dict[str, Any], dest: dict[str, Any], start: datetime) -> tuple[Any, Any, str | None, bool]:
    """도착 목표를 넓혀 가며(`_TARGET_STEPS_MIN`) 첫 성립 경로를 찾고, 그 소요에 맞춘 목표로 한 번 더 판정해 출발을 당긴다. → `(결과, 이유, 어디까지 봤나, 첫 결과로 대신했나)`."""
    first, why = None, None
    for minutes in _TARGET_STEPS_MIN:
        first, why = leg(origin, dest, start + timedelta(minutes=minutes), start)
        if first is not None:
            break
    if first is None:
        return None, why, f"출발 후 {_TARGET_STEPS_MIN[-1]}분 안에 도착하는 목표까지만 확인했어요", False
    target = start + timedelta(minutes=minutes)
    buffer = max(0, int(round((target - first["ends_at"]).total_seconds() / 60))) if isinstance(first.get("ends_at"), datetime) else 0
    second, _ = leg(origin, dest, start + timedelta(minutes=first["eta_min"] + buffer), start)
    return (second or first), None, None, second is None


def _reason(why: Any) -> dict[str, Any]:
    if isinstance(why, dict):
        return _scrub({"code": str(why.get("code") or "no_route"), "reason": why.get("reason") or "판정기가 경로를 내지 못했어요",
                       **({"earliest": why["earliest"]} if why.get("earliest") else {})})
    return {"code": "no_route", "reason": "판정기가 경로를 내지 못했어요"}


__all__ = ["GRADE_LABELS", "InvalidPlace", "as_place", "judge"]
