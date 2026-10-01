# -*- coding: utf-8 -*-
"""고객의 **현재 위치**를 출발지로 답한다 — 「여기서 경복궁 어떻게 가」 · 「근처 식당」. `[2026-09-30 사용자 지시 — ui 세션 전달]`

사용자 지시: 「ui 상에서 위치정보가 필요하면 브라우저 Geolocation API 로 얻게」. 웹은 브라우저에서 위치를 얻어 채팅 요청의 `location` 에 싣는다.
★위치가 필요한 질문인지는 **판단 단위(모델)가 정한다**(`decision_unit` 의 사실 종류 `route_here` · `nearby_dining` · `nearby_activity`) —
  낱말로 추측하지 않는다. 위치가 필요한데 요청에 없으면 **일정을 바꾸지 않고** 「현재 위치를 알려 주시면」 한 문장과 `needs_location: true` 로 답한다.
★★개인정보 — **원 좌표는 이 요청을 처리하는 데만 쓴다.** 로그 · DB · 알림 · Case 기록 · 대화 기록 · 답 문장 어디에도 좌표를 남기지 않는다
  (답에는 거리 · 분 · 곳 이름만). 이 모듈은 좌표를 **받아서 계산하고 돌려주는 것이 전부**이고 어디에도 쓰지 않는다 — 시험이 저장소 전체를 훑어 검사한다.
★계산은 이미 있는 것을 쓴다 — 가는 길은 이동 계산기(`mobility.wiring.leg_planner`, 시간표 판정), 못 쓰면 직선 어림값 `[추정]`.
  근처 식당 · 볼거리는 「다른 데로 바꿔」와 같은 후보 계산(`itinerary_changes.plan_nearby`) — 그 시각에 여는 곳만.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from .replan import distance_m, walk_minutes

#: 서울 바깥 둘레를 감싸는 사각형 (위도 최소 · 최대 · 경도 최소 · 최대) — ★우리가 고른 근사값(서울시 행정구역보다 약간 넉넉히).
#:  상품 범위가 서울이라(루트 CLAUDE.md 「대상 도시」) 그 밖의 좌표는 이 여행의 곳으로 안내하지 않는다
SEOUL_BOX = (37.41, 37.72, 126.76, 127.19)
#: 위치 정확도(반경 m)가 이보다 나쁘면 답에 한 문장으로 알린다 · 이보다 나쁘면 쓰지 않는다 — ★우리가 고른 값.
#:  500m 는 도보 6분 거리라 「가까운 곳」이 어긋난다. 2km 는 역 두세 개 폭이라 출발지로 쓸 수 없다
POOR_ACCURACY_M = 500.0
UNUSABLE_ACCURACY_M = 2000.0
#: 현재 위치 사본은 이 시간(분)보다 오래되면 낡았다고 알린다 — 브라우저가 캐시한 옛 위치를 조용히 쓰지 않는다. ★우리가 고른 값
STALE_MINUTES = 10
NEARBY_RADII_M = {"dining": (700, 1500, 3000), "activity": (1500, 3000)}
NEARBY_SHOWN = 3
#: 현재 위치를 가짜 장소로 넣을 때의 자리표시 번호 — 원장 · DB 조회가 UUID 를 요구해 그 모양이어야 한다. 어느 행과도 겹치지 않는 0 번호
HERE_ID = "00000000-0000-0000-0000-000000000000"


@dataclass(frozen=True)
class Fix:
    """요청이 실어 온 위치 — 메모리에만 있다. `repr` 에 좌표가 안 찍히게 막는다(로그에 새지 않도록)."""
    lat: float
    lon: float
    accuracy_m: float | None = None
    at: datetime | None = None

    def __repr__(self) -> str:                       # 예외 · 로그 · 시험 실패 출력에 좌표가 실리지 않게
        return "Fix(<위치 — 좌표 가림>)"

    def as_place(self) -> dict[str, Any]:
        """이동 계산기가 받는 모양."""
        return {"key": "here", "name": "현재 위치", "kind": "activity", "lat": self.lat, "lon": self.lon,
                "weather_sensitive": None, "attributes": {}}

    def as_origin(self) -> dict[str, Any]:
        """후보 계산이 받는 모양(`replan` 은 `latitude`·`longitude` 를 읽는다)."""
        return {"place_id": HERE_ID, "name": "현재 위치", "kind": "activity", "latitude": self.lat,
                "longitude": self.lon, "attributes": {}}


def in_seoul(fix: Fix) -> bool:
    lat_min, lat_max, lon_min, lon_max = SEOUL_BOX
    return lat_min <= fix.lat <= lat_max and lon_min <= fix.lon <= lon_max


def assess(fix: Fix, *, now: datetime) -> tuple[bool, str | None, str | None]:
    """(쓸 수 있나, 답 앞에 붙일 한 문장, 못 쓸 때의 답). 좌표는 문장에 넣지 않는다."""
    if not in_seoul(fix):
        return False, None, ("지금 위치가 서울 밖으로 보여서 이 여행의 곳으로 안내하기 어려워요. "
                             "위치 권한이 켜져 있는지, 다른 곳의 위치가 잡힌 건 아닌지 확인해 주세요.")
    if fix.accuracy_m is not None and fix.accuracy_m > UNUSABLE_ACCURACY_M:
        return False, None, (f"위치 정확도가 ±{_km(fix.accuracy_m)}로 너무 낮아 출발지로 쓰기 어려워요. "
                             "실내라면 창가나 밖에서 다시 시도해 주세요.")
    notes = []
    if fix.accuracy_m is not None and fix.accuracy_m > POOR_ACCURACY_M:
        notes.append(f"위치 정확도가 ±{_km(fix.accuracy_m)}로 낮아 실제와 조금 다를 수 있어요.")
    if fix.at is not None and now - fix.at > timedelta(minutes=STALE_MINUTES):
        notes.append(f"받은 위치가 {int((now - fix.at).total_seconds() // 60)}분 전 것이라 지금과 다를 수 있어요.")
    return True, " ".join(notes) or None, None


def _km(meters: float) -> str:
    return f"{round(meters)}m" if meters < 1000 else f"{meters / 1000:.1f}km"


ASK = {"route_here": "지금 위치에서 가는 길을 알려 드리려면 현재 위치가 필요해요. 현재 위치를 알려 주시면 바로 알려 드릴게요.",
       "nearby_dining": "가까운 식당을 찾으려면 현재 위치가 필요해요. 현재 위치를 알려 주시면 지금 열려 있는 곳으로 찾아 드릴게요.",
       "nearby_activity": "가까운 볼거리를 찾으려면 현재 위치가 필요해요. 현재 위치를 알려 주시면 지금 갈 수 있는 곳으로 찾아 드릴게요."}


def ask_for_location(kind: str) -> str:
    """위치가 필요한 질문인데 요청에 없을 때의 한 문장 — 일정은 바꾸지 않는다."""
    return ASK[kind]


def _dest_place(item: Any) -> dict[str, Any]:
    place = item.place or {}
    return {"key": str(place.get("place_id")), "name": place.get("name") or item.title, "kind": item.kind,
            "lat": place.get("latitude"), "lon": place.get("longitude"), "weather_sensitive": None,
            "attributes": dict(place.get("attributes") or {})}


def route_here(fix: Fix, dest: Any, *, now: datetime, leg: Callable[..., Any] | None) -> str:
    """현재 위치 → 그 일정의 장소. 이동 계산기(`leg`)가 있으면 시간표로, 못 채우면 직선 어림값 `[추정]`."""
    name = (dest.place or {}).get("name") or dest.title
    if dest.place is None or dest.place.get("latitude") is None:
        return f"{name}은(는) 위치를 몰라 가는 길을 계산하지 못했어요."
    there = _dest_place(dest)
    direct = distance_m({"latitude": fix.lat, "longitude": fix.lon},
                        {"latitude": there["lat"], "longitude": there["lon"]})
    if leg is not None:
        got = _timetable_now(fix, there, now=now, leg=leg)
        if got is not None:
            return f"지금 위치에서 {name}까지 — {got}"
    walk = walk_minutes(direct)
    if walk <= 25:
        how = f"직선 {_km(direct)} — 걸어서 약 {walk}분 [추정]"
    else:
        how = (f"직선 {_km(direct)} — 걸으면 약 {walk}분이라 대중교통을 타는 게 좋아요 "
               "[추정 — 시간표 계산은 아직 못 했어요]")
    return f"지금 위치에서 {name}까지 — {how}"


def _timetable_now(fix: Fix, there: dict[str, Any], *, now: datetime, leg: Callable[..., Any]) -> str | None:
    """구간 계산기는 **도착 목표**에서 출발을 거꾸로 셈한다 — 「지금 출발하면」에 맞추려고 두 번 부른다(첫 번은 넉넉한 목표로 시간과
    여유를 알아내고, 둘째는 지금 떠나는 목표로). 둘째가 안 되면 첫 결과의 출발 시각을 그대로 알린다."""
    origin = fix.as_place()
    first, _ = leg(origin, there, now + timedelta(minutes=90), now)
    if first is None:
        return None
    buffer = int(round(((now + timedelta(minutes=90)) - first["ends_at"]).total_seconds() / 60)) \
        if first.get("ends_at") else 0
    second, _ = leg(origin, there, now + timedelta(minutes=first["eta_min"] + max(buffer, 0)), now)
    got = second or first
    route = got["route"]
    planned = next((o for o in route.get("options") or [] if o.get("id") == route.get("planned")), None) or {}
    label = planned.get("label") or "이동"
    depart = got["starts_at"].astimezone(now.tzinfo) if now.tzinfo else got["starts_at"]
    return f"{label} 약 {got['eta_min']}분 (시간표 기준, {depart:%H:%M} 출발)"


def nearby(kind: str, fix: Fix, *, found: list[Any], radius_m: int | None, sought: int) -> str:
    """가까운 곳 목록 문장. `found` = 후보(좋은 순) — `plan_nearby` 가 준 것. 좌표는 싣지 않는다."""
    label, ending = ("식당", "이에요") if kind == "nearby_dining" else ("볼거리", "예요")
    if not found:
        return (f"지금 위치 근처 {_km(radius_m or 0)} 안에서 지금 갈 수 있는 {label}을 찾지 못했어요"
                f"(살펴본 곳 {sought}곳 — 문을 닫았거나 영업시간을 몰라요).")
    lines = []
    for n, cand in enumerate(found[:NEARBY_SHOWN], start=1):
        name = cand.place["name"] if cand.place else cand.name
        minutes = cand.walk_min or (walk_minutes(cand.distance_m) if getattr(cand, "distance_m", None) else None)
        walk = f"도보 약 {minutes}분" if minutes else "가까워요"
        # ★가격 모름 경고는 「비용을 계산할 수 없다」는 바꾸기용 말이라 여기서는 뺀다 — 영업 · 마감 경고만 싣는다
        warnings = [w for w in (cand.warnings or []) if not w.startswith("가격을 몰라")]
        lines.append(f"{n}) {name} ({walk})" + (f" — {warnings[0]}" if warnings else ""))
    return f"지금 위치에서 가까운 {label}{ending} — " + " · ".join(lines)


__all__ = ["Fix", "assess", "ask_for_location", "in_seoul", "nearby", "route_here"]
