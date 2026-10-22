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

from app.core.team_availability import TeamUnavailable

import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.domains.travel_ops.components.planning.replan import distance_m


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
    #: 등록 전후 지도·출발 재검증에 쓰는 내부 선택 문맥. 공개 검사 응답에는 싣지 않는다.
    departure_context: dict[str, Any] | None = None
    selected_option_id: str | None = None
    #: 어림으로 간 이유의 갈래 — `engine_off`(계산기 꺼짐) · `engine_error`(일시적 오류) · 계산기가 준 코드(`no_data` · `budget` 등). 시간표로 낸 값은 None.
    #: 부르는 쪽이 「다시 해 보면 풀릴 수 있는 것」과 「몇 번을 해도 같은 것」을 가르는 데 쓴다(응답에는 싣지 않는다)
    why_code: str | None = None
    #: `[2026-10-23 사용자 지시 — 경로 후보 먼저 3개 · 내리면 더]` 계산기가 같은 출발로 닿는다고 본 **경로 후보 전부**(`route_rows` 모양 · 계산기가 고른 것이 맨 앞).
    #: 화면은 앞의 `ROUTES_FIRST` 개를 검사와 함께 받고, 나머지는 「더 보기」(넓게 찾기)로 받는다. 어림 구간은 비어 있다
    routes: tuple[dict[str, Any], ...] = ()
    #: 보통 계산이 후보 상한(혼합 · 버스 직행)에 걸려 판정하지 않은 후보가 있다 — 넓게 찾으면 더 나올 수 있다
    routes_capped: bool = False
    #: 이 구간이 쓰는 경로 후보의 고르기 열쇠(`route_key`) — 고객이 고른 경로가 이 구간에 실렸는지 부르는 쪽이 본다
    route_key: str | None = None

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


def selected_context(context: Any, option_id: Any) -> dict[str, Any] | None:
    """저장 계산기의 선택 후보만 복사한다. 오래되거나 어긋난 문맥은 연결하지 않는다."""
    if (not isinstance(context, dict) or type(context.get('schema_version')) is not int
            or context['schema_version'] != 1 or not isinstance(option_id, str) or not option_id):
        return None
    options = context.get('options')
    option = options.get(option_id) if isinstance(options, dict) else None
    if not isinstance(option, dict) or option.get('option_id') != option_id:
        return None
    result = deepcopy(context)
    result['options'] = {option_id: deepcopy(option)}
    return result


def straight_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    return distance_m({"latitude": a["lat"], "longitude": a["lon"]}, {"latitude": b["lat"], "longitude": b["lon"]}) / 1000


#: 같은 곳으로 보는 거리(m) — 이름이 같고 이 안이면 같은 장소다. ★우리가 고른 값(2026-10-21): 같은 건물 안 출입구 차이를 넘기되 이웃 가게는 가른다
SAME_PLACE_M = 100.0


def same_place(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    """이웃한 두 칸의 장소가 같은 곳인가 — 같은 `place_id`, 또는 이름이 같고 좌표가 `SAME_PLACE_M` 안. 장소가 없거나 좌표를 모르면 같다고 하지 않는다.
    ★같은 곳 사이에는 이동 구간을 만들지 않는다(`review.build`) — 전에는 「도보 1분 · 0.0km」 구간이 붙었다(2026-10-21 사용자 지적)."""
    if not a or not b:
        return False
    if a.get("place_id") and a.get("place_id") == b.get("place_id"):
        return True
    if not a.get("name") or a.get("name") != b.get("name"):
        return False
    if None in (a.get("latitude"), a.get("longitude"), b.get("latitude"), b.get("longitude")):
        return False
    return distance_m(a, b) <= SAME_PLACE_M


def mode_of(option: dict[str, Any]) -> tuple[str, str]:
    """계산기가 고른 경로 후보 → (수단 코드, 화면 말). 타는 노선(`uses` — 「5호선:광화문」 · 「버스:103」)에서 읽는다."""
    if str(option.get("id")) == "taxi":
        return "taxi", "택시"                          # ☆`[2026-10-07]` 택시는 uses 가 비어 도보로 읽히던 것
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


#: `[2026-10-23]` 확인 화면이 검사와 함께 받는 경로 후보 수 — 나머지는 고객이 목록을 끝까지 내리면 받는다(`move_options.routes`)
ROUTES_FIRST = 3
#: 보통 계산이 상한 때문에 판정하지 않은 후보가 있다는 표시(계산기 `left_out` 코드) — 넓게 찾으면 후보가 더 나올 수 있다
CAPPED_CODES = frozenset({"mix_cap", "bus_cap", "bus_more", "mix_skipped"})


def route_key(option: dict[str, Any]) -> str:
    """경로 후보의 **고르기 열쇠** — 다시 세어도 같은 경로면 같은 값. 타는 노선 · 승차역(`uses`)으로 만든다(택시 · 도보는 그 이름).
    계산기의 `id` 는 같은 구간에서도 함께 나온 후보에 따라 달라질 수 있어(이름 겹침 피하기) 쓰지 않는다."""
    uses = [str(u) for u in option.get("uses") or ()]
    if str(option.get("id")) == "taxi":
        return "taxi"
    return "u:" + ">".join(uses) if uses else "walk"


def _ride_name(use: str) -> str:
    head, _, rest = str(use).partition(":")
    return f"버스 {rest}" if head == "버스" else head


def _starts(option: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(option["starts_at"])) if option.get("starts_at") else None
    except ValueError:
        return None


def route_rows(route: dict[str, Any], depart: datetime, b_start: datetime, more: Any = (),
               floor: datetime | None = None) -> list[dict[str, Any]]:
    """계산기 답의 경로 후보 → 화면 줄. `route.options` 는 모두 같은 출발(`depart`)에 떠나도 닿는 것, `more` 는 **조금 일찍 떠나면 닿는** 다른 경로
    (계산기 `more_options` — 후보마다 `starts_at`, `floor`(앞 일정 끝) 전에 떠나야 하면 뺀다 · `early: true`). 계산기가 고른 것(`planned`)이 맨 앞,
    나머지는 **빨리 닿는 순 · 환승 적은 순 · 덜 걷는 순**(화면에 보이는 순서일 뿐 — 계획 수단을 정하는 규칙은 계산기의 것 그대로다). 같은 열쇠는 한 줄."""
    planned = route.get("planned")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    early_rows = [(o, _starts(o)) for o in more or [] if isinstance(o, dict)]
    for option, start in [(o, depart) for o in route.get("options") or []] + early_rows:
        key = route_key(option)
        if key in seen or start is None or (floor is not None and start < floor):
            continue
        seen.add(key)
        code, label = mode_of(option)
        minutes = int(option.get("eta_min") or 0)
        arrive = start + timedelta(minutes=minutes)
        uses = [str(u) for u in option.get("uses") or ()]
        rides: list[str] = []
        for use in uses:
            name = _ride_name(use)
            if name and (not rides or rides[-1] != name):
                rides.append(name)
        rows.append({"key": key, "mode": code, "mode_label": label, "label": str(option.get("label") or label),
                     "minutes": minutes, "depart": start.strftime("%H:%M"), "arrive": arrive.strftime("%H:%M"),
                     "slack_min": int((b_start - arrive).total_seconds() // 60), "fare_krw": option.get("fare_krw"),
                     "walk_m": option.get("walk_m"), "transfers": max(len(rides) - 1, 0), "lines": rides,
                     "planned": option.get("id") == planned and not option.get("starts_at"), "early": start < depart})
    rows.sort(key=lambda r: (not r["planned"], r["minutes"], r["transfers"],
                             r["walk_m"] if r["walk_m"] is not None else float("inf"), r["key"]))
    return rows


def _estimate(a: dict[str, Any], b: dict[str, Any], a_end: datetime, b_start: datetime, why: str, code: str | None = None) -> Leg:
    from app.domains.travel_ops.components.planning.planner import Cand, _transfer_minutes

    here = Cand(a["key"], a["name"], "activity", a["lat"], a["lon"], {}, "intake")
    there = Cand(b["key"], b["name"], "activity", b["lat"], b["lon"], {}, "intake")
    minutes, _basis, _label = _transfer_minutes(here, there)
    arrive = a_end + timedelta(minutes=minutes)
    return Leg("estimate", "직선 어림", f"{a['name']} → {b['name']}", minutes, round(straight_km(a, b), 1), a_end, arrive,
               int((b_start - arrive).total_seconds() // 60), "estimate", why, why_code=code)


#: 「앞 일정이 끝난 뒤 떠나면 닿는 다른 경로」를 깊이 찾을 만큼 아슬아슬한 정도(분) — 가장 늦은 출발이 앞 일정 끝보다 이만큼 이르기까지.
#: 이보다 더 일찍 떠나야 하면 어느 경로로도 못 닿는다고 본다. ★우리가 고른 값 — 깊은 탐색은 못 닿는 구간에서 3~11초 걸렸다(2026-10-03 실측: 경복궁→강남 10.8초)
NEAR_MISS_MIN = 15


def leg_between(engine: Any, a: dict[str, Any], b: dict[str, Any], a_end: datetime, b_start: datetime, *,
                deep: bool = True, prefer: str | None = None) -> Leg:
    """`a`·`b` = `{"key","name","lat","lon"}`. `a_end` = 앞 일정이 끝나는 시각, `b_start` = 다음 일정 시작. `engine` 이 None 이면 어림값.

    ☆`[2026-10-03 실서버 실측]` 계산기는 닿는 구간이면 0.2~0.5초인데 **못 닿는 구간은 2.7~10.8초**였다(출발 제한을 건 탐색이 모든 경로를 훑는다).
      확인 화면은 못 닿는 구간을 가장 많이 만난다. 그래서 먼저 출발 제한 없이 한 번 묻는다(빠르다) — 가장 늦은 출발이 앞 일정 끝 뒤면 닿는다.
      끝보다 `NEAR_MISS_MIN` 넘게 이르면 어느 경로도 못 닿는다고 보고(늦음 · 걸리는 시간은 이 답으로 낸다), 아슬아슬하면(15분 안) 그때만
      「끝난 뒤 떠나서 닿는 다른 경로」를 깊이 찾는다. `deep=False` 면 깊은 탐색을 아예 안 한다 — 시각을 맞추려고 여러 번 묻는 쪽(자동 추천 ·
      후보)이 쓴다: 그쪽은 어차피 보수적으로(앞 일정이 끝나는 대로 떠난다고) 맞추고, 최종 판정은 깊은 탐색을 하는 검사가 다시 한다.
    `prefer` `[2026-10-23]` 고객이 고른 경로의 열쇠(`route_key`) — 계산기 답의 후보 가운데 그 경로가 있으면 계획 수단 대신 그것을 싣는다
      (없으면 계산기가 고른 것 · 실린 것은 `Leg.route_key` 로 본다)."""
    if engine is None:
        return _estimate(a, b, a_end, b_start, "이동 계산기가 꺼져 있어요", "engine_off")
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
    except TeamUnavailable:
        raise
    except Exception as exc:                          # noqa: BLE001 — 일반 계산 오류의 기존 화면 정책 유지
        return _estimate(a, b, a_end, b_start, f"이동 계산기 오류({type(exc).__name__})", "engine_error")
    if got is None:
        reason = str((why or {}).get("reason") or (why or {}).get("code") or "계산기가 이 구간을 못 채웠어요")
        return _estimate(a, b, a_end, b_start, reason, str((why or {}).get("code") or "unfilled"))
    route = got.get("route") or {}
    more = [o for o in got.get("more_options") or [] if isinstance(o, dict)]
    option = next((o for o in route.get("options") or [] if o.get("id") == route.get("planned")), {})
    mine = None
    if prefer:
        mine = next((o for o in route.get("options") or [] if route_key(o) == prefer), None)
        early = next((o for o in more if route_key(o) == prefer), None) if mine is None else None
        start = _starts(early) if early is not None else None
        if early is not None and start is not None and start >= a_end:
            mine, verified = early, True                # 조금 일찍 떠나는 경로 — 그 출발이 앞 일정이 끝난 뒤라 시간표로 확인한 값이다
    if mine is not None:
        option = mine
    code, label = mode_of(option)
    minutes = int((option.get("eta_min") if mine is not None else None) or got.get("eta_min") or option.get("eta_min") or 0)
    own = _starts(option) if mine is not None else None
    if own is not None:                               # 고른 경로가 자기 출발 시각을 가진다(조금 일찍 떠남)
        depart, arrive = own, own + timedelta(minutes=minutes)
    elif got["starts_at"] < a_end:                    # 검증 못 한 값 — 끝나는 대로 떠난다고 본다
        depart, arrive = a_end, a_end + timedelta(minutes=minutes)
    elif mine is not None:                            # 고른 경로도 같은 출발에 떠난다(계산기는 그 출발로 닿는 후보만 싣는다) — 도착은 그 경로의 소요로
        depart, arrive = got["starts_at"], got["starts_at"] + timedelta(minutes=minutes)
    else:
        depart, arrive = got["starts_at"], got["ends_at"]
    km = (option.get("walk_m") / 1000) if code == "walk" and option.get("walk_m") is not None else straight_km(a, b)
    # 끝나는 대로 떠나는 어림 시각으로 바꾼 경우에는 원래 편성·승차 시각을 재사용하지 않는다.
    context = (selected_context(got.get('departure_context'), option.get('id'))
               if verified and (own is not None or got['starts_at'] >= a_end) else None)
    if context is not None and own is not None:      # 문맥의 출발 분을 고른 경로의 것으로(등록 · 출발 재검증이 그 분을 읽는다)
        context['start_min'] = (context.get('options') or {}).get(option.get('id'), {}).get('start_min', context.get('start_min'))
    capped = any(str(e.get("code")) in CAPPED_CODES for e in got.get("left_out") or [] if isinstance(e, dict))
    return Leg(code, label, str(option.get("label") or f"{a['name']} → {b['name']}"), minutes, round(km, 1), depart, arrive,
               int((b_start - arrive).total_seconds() // 60), "timetable", None, option.get("fare_krw"), verified, latest,
               tuple(str(u) for u in option.get("uses") or ()), context, option.get('id') if context else None,
               routes=tuple(route_rows(route, got["starts_at"] if got["starts_at"] >= a_end else a_end, b_start, more, a_end)),
               routes_capped=capped, route_key=route_key(option) if option else None)


def late_text(slack: int) -> str:
    return f"일정보다 {-slack}분 늦어요" if slack < 0 else (f"{slack}분 여유" if slack else "딱 맞게 닿아요")


def ceil_to(minutes: float, step: int = 5) -> int:
    return int(math.ceil(minutes / step) * step)


__all__ = ["CAPPED_CODES", "Leg", "ROUTES_FIRST", "SAME_PLACE_M", "late_text", "leg_between", "mode_of", "route_key", "route_rows",
           "same_place", "straight_km"]
