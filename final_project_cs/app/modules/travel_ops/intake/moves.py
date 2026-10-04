# -*- coding: utf-8 -*-
"""확인 화면의 **장소 사이 이동** — 같은 날 앞뒤 장소를 몇 분에 어떻게 가나, 다음 일정에 닿나. `[2026-10-02 사용자 지시 — 계획 확인 시나리오 목업]`

★왜. 「10:00 강남 올리브영 → 10:20 명동 다이소」처럼 20분에 못 가는 구간이 확인 화면에서 한 번도 걸리지 않았다(2026-10-01 사용자 지적) —
  읽은 일정은 이동 시간을 계산하지 않았고 등록 판정은 이동 항목이 없으면 「간격 0분」만 봤다. 이 모듈이 구간마다 **이동 계산기**(시간표 판정,
  `mobility.wiring.leg_planner`)로 이동 시간을 내고, 앞 일정이 끝난 뒤 떠나 다음 일정 시작 안에 닿는지(`slack_min` — 음수면 늦는다) 알린다.
★계산기가 꺼져 있거나 그 구간을 못 채우면 **직선거리 어림값**(`planner._transfer_minutes` — 도보 80m/분, 60분 상한)으로 간다. 조용히 바꾸지 않는다 —
  `basis = estimate` 와 이유(`why`)를 싣고 화면 문장에 「어림」이라고 적는다(근거 없는 값 금지).
★출발 시각: 시간표로 닿는 구간은 계산기가 낸 출발 · 도착 시각을 쓴다(열차를 기다리는 시간이 들어 있다). 못 닿는 구간은 **앞 일정이 끝나는 시각에 곧바로 떠난다**고
  보고 얼마나 늦는지를 보인다(목업의 「11:30에 나서면 11:42 도착 · 일정보다 42분 늦어요」).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ..replan import distance_m


@dataclass
class Leg:
    mode: str                    # walk | subway | bus | transit | estimate
    mode_label: str              # 도보 · 지하철 5호선→1호선 · 버스 103 · 직선 어림
    route: str                   # 경로 한 줄(계산기 라벨 · 어림이면 「A → B」)
    minutes: int                 # 이동 시간
    km: float
    depart: datetime
    arrive: datetime
    slack_min: int               # 다음 일정 시작까지 남는 분 — 음수면 늦다
    basis: str                   # timetable | estimate
    why: str | None = None       # 어림으로 간 이유(계산기가 못 채움 · 꺼짐)
    fare_krw: int | None = None
    #: 시간표로 **앞 일정이 끝난 뒤 떠나서 정책 여유까지 두고** 닿는 경로를 확인했나. 거짓이면 도착은 「끝나는 대로 떠난다」는 계산(이동 시간만 더한 값)이라
    #: 열차 · 버스를 기다리는 시간이 빠져 있다 — 늦지는 않아도(`slack_min ≥ 0`) 빠듯할 수 있다(`tight`)
    verified: bool = True
    #: 계산기가 낸 「다음 일정에 닿는 가장 늦은 출발」 — 시각을 맞추는 쪽(자동 추천)이 얼마나 미룰지 알 때 쓴다
    latest_depart: datetime | None = None
    #: 계산기가 고른 경로 후보의 `uses`(「2호선:을지로입구」 · 「버스:103」) — 지도에 경로선을 그릴 때 탄 역을 알려고 저장한다(응답에는 안 싣는다)
    uses: tuple[str, ...] = ()

    @property
    def tight(self) -> bool:
        """시간표 구간인데 검증을 못 해 이동 시간만 더한 값이고, 여유가 정책 여유(모자라도 늦지는 않음) 안이다 — 열차를 놓치면 늦을 수 있다."""
        return self.basis == "timetable" and not self.verified and self.mode != "walk" and self.slack_min >= 0

    @property
    def ok(self) -> bool:
        return self.slack_min >= 0 and not self.tight


def _place(key: str, name: str, lat: float, lon: float) -> dict[str, Any]:
    return {"key": key, "name": name, "kind": "activity", "lat": lat, "lon": lon, "weather_sensitive": None,
            "attributes": {}}


def straight_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    return distance_m({"latitude": a["lat"], "longitude": a["lon"]}, {"latitude": b["lat"], "longitude": b["lon"]}) / 1000


def mode_of(option: dict[str, Any]) -> tuple[str, str]:
    """계산기가 고른 경로 후보 → (수단 코드, 화면 말). 타는 노선(`uses` — 「5호선:광화문」 · 「버스:103」)에서 읽는다."""
    if str(option.get("id")) == "walk" or not option.get("uses"):
        return "walk", "도보"
    lines: list[str] = []
    buses: list[str] = []
    for use in option.get("uses") or []:
        head, _, rest = str(use).partition(":")
        if head == "버스":
            if rest and rest not in buses:
                buses.append(rest)
        elif head and head not in lines:
            lines.append(head)
    if lines and not buses:
        return "subway", "지하철 " + "→".join(lines)
    if buses and not lines:
        return "bus", "버스 " + "·".join(buses)
    return "transit", "대중교통"


def _estimate(a: dict[str, Any], b: dict[str, Any], a_end: datetime, b_start: datetime, why: str) -> Leg:
    from ..planner import Cand, _transfer_minutes

    here = Cand(a["key"], a["name"], "activity", a["lat"], a["lon"], {}, "intake")
    there = Cand(b["key"], b["name"], "activity", b["lat"], b["lon"], {}, "intake")
    minutes, _basis, _label = _transfer_minutes(here, there)
    arrive = a_end + timedelta(minutes=minutes)
    return Leg("estimate", "직선 어림", f"{a['name']} → {b['name']}", minutes, round(straight_km(a, b), 1), a_end, arrive,
               int((b_start - arrive).total_seconds() // 60), "estimate", why)


#: 「앞 일정이 끝난 뒤 떠나면 닿는 다른 경로」를 깊이 찾을 만큼 아슬아슬한 정도(분) — 가장 늦은 출발이 앞 일정 끝보다 이만큼 이르기까지.
#: 이보다 더 일찍 떠나야 하면 어느 경로로도 못 닿는다고 본다. ★우리가 고른 값 — 깊은 탐색은 못 닿는 구간에서 3~11초 걸렸다(2026-10-03 실측: 경복궁→강남 10.8초)
NEAR_MISS_MIN = 15


def leg_between(engine: Any, a: dict[str, Any], b: dict[str, Any], a_end: datetime, b_start: datetime, *,
                deep: bool = True) -> Leg:
    """`a`·`b` = `{"key","name","lat","lon"}`. `a_end` = 앞 일정이 끝나는 시각, `b_start` = 다음 일정 시작. `engine` 이 None 이면 어림값.

    ☆`[2026-10-03 실서버 실측]` 계산기는 닿는 구간이면 0.2~0.5초인데 **못 닿는 구간은 2.7~10.8초**였다(출발 제한을 건 탐색이 모든 경로를 훑는다).
      확인 화면은 못 닿는 구간을 가장 많이 만난다. 그래서 먼저 출발 제한 없이 한 번 묻는다(빠르다) — 가장 늦은 출발이 앞 일정 끝 뒤면 닿는다.
      끝보다 `NEAR_MISS_MIN` 넘게 이르면 어느 경로도 못 닿는다고 보고(늦음 · 걸리는 시간은 이 답으로 낸다), 아슬아슬하면(15분 안) 그때만
      「끝난 뒤 떠나서 닿는 다른 경로」를 깊이 찾는다. `deep=False` 면 깊은 탐색을 아예 안 한다 — 시각을 맞추려고 여러 번 묻는 쪽(자동 추천 ·
      후보)이 쓴다: 그쪽은 어차피 보수적으로(앞 일정이 끝나는 대로 떠난다고) 맞추고, 최종 판정은 깊은 탐색을 하는 검사가 다시 한다."""
    if engine is None:
        return _estimate(a, b, a_end, b_start, "이동 계산기가 꺼져 있어요")
    pa, pb = _place(a["key"], a["name"], a["lat"], a["lon"]), _place(b["key"], b["name"], b["lat"], b["lon"])
    try:
        got, why = engine(pa, pb, b_start, None)
        verified = True
        latest = got["starts_at"] if got is not None else None
        if got is not None and got["starts_at"] < a_end:
            verified = False
            route0 = got.get("route") or {}
            walking = next((o for o in route0.get("options") or [] if o.get("id") == route0.get("planned")), {}).get("id") == "walk"
            # 앞 일정이 끝나기 전에 떠나야 하는 경로 — 도보처럼 이어지는 이동이면 끝나는 대로 떠나면 되지만, 열차 · 버스는 **그 뒤 편이 있는지** 시간표로 다시 봐야 한다.
            # 아슬아슬하면(`NEAR_MISS_MIN` 안) 깊이 찾는다. 못 찾으면 이동 시간만 더한 값으로 알리되 검증하지 못했다고 적는다(`tight`)
            if deep and not walking and (a_end - got["starts_at"]).total_seconds() <= NEAR_MISS_MIN * 60:
                later, _ = engine(pa, pb, b_start, a_end)
                if later is not None and later["starts_at"] >= a_end:            # 계산기 답도 믿기만 하지 않고 출발이 정말 끝난 뒤인지 본다
                    got, verified = later, True
            elif walking:
                verified = True
    except Exception as exc:                          # noqa: BLE001 — 계산기 하나의 오류가 확인 화면을 막지 않는다
        return _estimate(a, b, a_end, b_start, f"이동 계산기 오류({type(exc).__name__})")
    if got is None:
        reason = str((why or {}).get("reason") or (why or {}).get("code") or "계산기가 이 구간을 못 채웠어요")
        return _estimate(a, b, a_end, b_start, reason)
    route = got.get("route") or {}
    option = next((o for o in route.get("options") or [] if o.get("id") == route.get("planned")), {})
    code, label = mode_of(option)
    minutes = int(got.get("eta_min") or option.get("eta_min") or 0)
    if got["starts_at"] < a_end:                      # 검증 못 한 값 — 끝나는 대로 떠난다고 본다
        depart, arrive = a_end, a_end + timedelta(minutes=minutes)
    else:
        depart, arrive = got["starts_at"], got["ends_at"]
    km = (option.get("walk_m") / 1000) if code == "walk" and option.get("walk_m") is not None else straight_km(a, b)
    return Leg(code, label, str(option.get("label") or f"{a['name']} → {b['name']}"), minutes, round(km, 1), depart, arrive,
               int((b_start - arrive).total_seconds() // 60), "timetable", None, option.get("fare_krw"), verified, latest,
               tuple(str(u) for u in option.get("uses") or ()))


def late_text(slack: int) -> str:
    return f"일정보다 {-slack}분 늦어요" if slack < 0 else (f"{slack}분 여유" if slack else "딱 맞게 닿아요")


def ceil_to(minutes: float, step: int = 5) -> int:
    return int(math.ceil(minutes / step) * step)


__all__ = ["Leg", "late_text", "leg_between", "mode_of", "straight_km"]
