# -*- coding: utf-8 -*-
"""`routes{}.options[]` 한 칸씩 채우기 — 23번 방(2026-09-25). plan.py 가 부른다.

무엇을 채우나 (전부 기존 칸 · 새 키 0 · 스펙 v1.4)
  id        수단 태그를 **접두로** 싣는다 — `subway_1` · `bus_7022` · `walk` · `bike`(◆선호: 지하철/버스 구분).
            팀 시나리오도 id 를 이렇게 쓴다(`subway_direct` · `bus_sejong` · `taxi` · `walk`). 새 키 `modes` 를 안 만든다.
  label     경로 + **이유**(축별 사실 · 순위 아님). 예 「3호선 경복궁→을지로3가 → 2호선 을지로3가→성수 — 소요 가장 짧음」
  walk_m    경로 안 도보 합(m · 정수) — 소요 분과 **같은 모델**의 미터. 한 조각이라도 모르면 키를 뺀다
  fare_krw  1인 요금 — **규칙 파일에 요금 근거가 있는 수단만**(도보 0 · 자전거 이용권). 지하철·버스는 뺀다(결정 3)
  uses      plan.uses_of 그대로 + 팀 `route_uses.problem()` 자가 검사(불통과 후보는 싣지 않는다)

표시 전용(◆칸 답 전 — 만들어만 둔다 · 기본 off)
  transfer_car  환승 칸. 46 조회 규칙 그대로 — **판정기가 고른 실제 역열로만** · 정확 일치 · 폴백 없음 · 없으면 키 없음
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from ..route_uses import problem as uses_problem
from .verify_time import leg_mode, leg_txt

# uses·label 노선명 — 팀장 확정 표기(9/24): 1~9호선은 `N호선`, 그 밖은 `route_uses.OTHER_LINES` 의 이름.
# 시간표 이름 → 계약 이름. 역 목록(시·종점)으로 같은 노선임을 확인한 것만 적는다(결정 5).
LINE_OFFICIAL = {
    "경의선": "경의중앙선",          # 용산·이촌·서빙고 … 서울역 (32 확인)
    "인천선": "인천1호선",           # 검단호수공원 … 송도달빛축제공원 — 인천도시철도 1호선
    "우이신설경전철": "우이신설선",   # 북한산우이 … 신설동
    "김포도시철도": "김포골드라인",   # 양촌 … 김포공항
}

MODE_PREFIX = {"subway": "subway", "bus": "bus", "bike": "bike", "walk": "walk"}
CAVEAT_LINE9 = "9호선은 일반열차 혼잡 값 — 급행은 더 붐빌 수 있다"


def line_name(line):
    """시간표 노선명 → uses·label 노선명. '02호선' → '2호선'."""
    if line and len(line) == 4 and line.endswith("호선") and line[:2].isdigit():
        return f"{int(line[:2])}호선"
    return LINE_OFFICIAL.get(line, line)


def station_name(nm):
    """uses 역명 — 괄호 병기와 끝의 「역」을 뺀다. 이름 자체가 「서울역」이면 그대로(9/24 표기)."""
    s = str(nm).split("(")[0].strip()
    if s == "서울역":
        return s
    return s[:-1] if s.endswith("역") and len(s) > 1 else s


def modes_of(legs):
    return [leg_mode(x) for x in legs] or ["walk"]


def kind_of(legs):
    """후보 하나의 수단 태그 — 지하철만 · 버스만 · 자전거 · 도보. 섞이면 탄 순서대로 `_` 로 잇는다."""
    ms = []
    for m in modes_of(legs):
        if not ms or ms[-1] != m:
            ms.append(m)
    return "_".join(MODE_PREFIX.get(m, m) for m in ms)


def make_id(legs, taken):
    """route 안에서 유일한 id. 버스는 노선번호를 붙인다(`bus_7022`) — 팀 시나리오 모양."""
    kind = kind_of(legs)
    if kind in ("walk", "bike") and kind not in taken:
        return kind
    if kind == "bus" and len(legs) == 1:
        base = f"bus_{legs[0]['route']}"
        if base not in taken:
            return base
        n = 2                        # 같은 노선의 다른 승하차 — `bus_405_2` (GPT 23 #9 · id 로 노선번호를 복원하지 않는다)
        while f"{base}_{n}" in taken:
            n += 1
        return f"{base}_{n}"
    n = 1
    while f"{kind}_{n}" in taken:
        n += 1
    return f"{kind}_{n}"


def uses_problems(uses):
    """팀 route_uses.problem() 을 전부 — [(값, 이유)]. 빈 목록이면 통과."""
    return [(u, p) for u in uses if (p := uses_problem(u)) is not None]


# ── 도보 미터 ─────────────────────────────────────────────────────────────
def transfer_walk_m(v, legs):
    """지하철 후보의 환승 도보 m 합(환승 없으면 0). 지하철 밖 구간이 있거나 거리표에 없는 환승이 하나라도 있으면
    None(모르면 뺀다 — 판정기는 거리표 밖 환승을 0분·근거없음으로 두지만 미터는 지어내지 않는다)."""
    if not legs or any(leg_mode(x) != "subway" for x in legs):
        return None
    tot = 0.0
    for a, b in zip(legs, legs[1:]):
        w = v.tw.lookup(a["to"], a["line"], b["line"]) if v.tw is not None else None
        if w is None or w.distance_m is None:
            return None
        tot += w.distance_m
    return tot


# ── 요금 ────────────────────────────────────────────────────────────────
def fare_of(v, legs, legs_result):
    """1인 요금 — 규칙 파일에 근거가 있는 것만. 도보 0 · 자전거는 규칙 bike.ddareungi.fare(이용권 + 초과).
    지하철·버스는 요금 규칙이 없어 None(키를 뺀다 · 결정 3)."""
    ms = set(modes_of(legs))
    if ms == {"walk"}:
        return 0
    if ms == {"bike"}:
        from .bike import fare as bike_fare
        ride = sum((lr.ride_min or 0) for lr in (legs_result or []))
        if not ride:
            return None
        return int(bike_fare(v.R["bike"]["ddareungi"]["fare"], ride)["total_won"])
    return None


# ── 혼잡(33 · @ 부품의 경고를 이유로 옮긴다) ─────────────────────────────────
def severe_hits(warnings):
    """판정기 경고 중 극심 혼잡(MOB_W_CONGESTION_SEVERE) — [문구]. 판정기가 이미 낸 사실만 옮긴다."""
    return [w["text"].split(" — ")[0] for w in (warnings or []) if isinstance(w, dict)
            and w.get("code") == "MOB_W_CONGESTION_SEVERE"]


def ride_results(legs, legs_result):
    """판정기 구간 결과에서 「환승 …」 줄만 빼고, 남은 탄 구간이 legs 와 **개수·순서·표기 모두** 같을 때만 짝지어 준다
    (같은 표기가 두 번이어도 순서로 · GPT 23 #5 · 2차 #5 — 예상 밖 승차 결과를 건너뛰어 맞추지 않는다). 아니면 None."""
    rides = [lr for lr in (legs_result or []) if not str(lr.label).startswith("환승 ")]
    if len(rides) != len(legs) or any(lr.label != leg_txt(leg) for lr, leg in zip(rides, legs)):
        return None
    return rides


def chosen_departures(v, leg, lr, day_type):
    """판정기가 고른 편성 후보 — 그 승차 분에 떠나 그 도착 분에 닿는 (출발, 경로 판정) 목록.
    판정기와 같은 `Verifier.candidates()`·`LineOrder.travel_min_on_path()` 로 다시 찾는다(판정기 무수정)."""
    if lr is None or lr.verdict != "feasible" or lr.depart_min is None or lr.arrive_min is None:
        return []
    line, a, b = leg["line"], leg["from"], leg["to"]
    cands, _drop, _o = v.candidates(line, a, b, day_type)
    out = []
    for d, verd, _f in cands:
        if d.min != lr.depart_min:
            continue
        ride = v.lo.travel_min_on_path(line, verd.path, b)
        if ride is None or d.min + math.ceil(ride) != lr.arrive_min:
            continue
        out.append((d, verd))
    return out


def congestion_checked(v, legs, legs_result, date, day_type):
    """후보의 **실제 탄 편성**마다 승차역 혼잡 셀(노선·승차역·방향·요일·30분)이 있고 극심이 아닌가 — 전부면 True(GPT 23 #1 · 2차 #4).
    승차역 셀만 본다 — 승차 뒤 지나는 역 구간의 혼잡은 확인하지 않는다(문구도 「확인한 승차역」으로 한정).
    역이 자료에 있다는 것만으로는 안 된다(그 요일·방향·시간대 셀이 없으면 극심 경고가 안 나온 것뿐이다).
    지하철 밖 구간 · 편성 방향이 하나로 안 모임 · 셀 없음(값 null 포함) → False."""
    cg = getattr(v, "cg_data", None)
    if not cg or not legs or any(leg_mode(x) != "subway" for x in legs):
        return False
    lrs = ride_results(legs, legs_result)
    if lrs is None:
        return False
    levels = v.R["congestion"]["levels"]
    is_hol = date is not None and date.isoformat() in v.holidays
    for leg, lr in zip(legs, lrs):
        dirs = {d.dir for d, _verd in chosen_departures(v, leg, lr, day_type)}
        if len(dirs) != 1:
            return False
        hit = cg.lookup(leg["line"], leg["from"], dirs.pop(), day_type, date, lr.depart_min, levels,
                        is_holiday=is_hol)
        if hit is None or hit[1] == "극심":        # 셀이 없거나 그 셀이 극심이면 「극심 없음」이라 말할 수 없다(2차 #4)
            return False
    return True


# ── 이유 문장 ───────────────────────────────────────────────────────────
def add_reasons(opts):
    """축별 사실을 label 뒤에 붙인다 — **순위가 아니다**(rules candidates.순위_없음). 비교는 실린 후보끼리만.
    opts[i] 는 `_route`(경로 문구) · `eta_min` · `_transfers` · `_walk_min` · `_severe` · `_covered` · `_legs` 를 가진다."""
    many = len(opts) > 1
    etas = [o["eta_min"] for o in opts]
    trs = [o["_transfers"] for o in opts]
    wks = [o["_walk_min"] for o in opts]
    wms = [o.get("_walk_m") for o in opts]
    by_m = None not in wms                         # 전부 미터를 알면 거리로, 아니면 분 모델로(GPT 23 #7)
    wkey = [round(x) for x in wms] if by_m else wks
    any_severe = any(o["_severe"] for o in opts)
    for o in opts:
        facts = []
        if many and min(etas) != max(etas) and o["eta_min"] == min(etas):
            facts.append("소요 가장 짧음")
        if many and min(trs) != max(trs) and o["_transfers"] == min(trs):
            facts.append("환승 없음" if o["_transfers"] == 0 else f"환승 가장 적음({o['_transfers']}회)")
        i = opts.index(o)
        if many and None not in wkey and min(wkey) != max(wkey) and wkey[i] == min(wkey):
            facts.append("도보 거리 가장 짧음" if by_m else "도보 시간 가장 짧음")
        if o["_severe"]:
            facts.append("극심 혼잡 구간 있음(" + " · ".join(o["_severe"]) + ")")
        elif any_severe and o["_covered"]:
            facts.append("확인한 승차역 혼잡 자료에서 극심 없음")
        if (o["_severe"] or (any_severe and o["_covered"])) and any(x.get("line") == "09호선" for x in o["_legs"]):
            facts.append(CAVEAT_LINE9)
        o["label"] = o["_route"] + (" — " + " · ".join(facts) if facts else "")
    return opts


# ── 환승 칸(표시 전용 · ◆칸 · 기본 off) ─────────────────────────────────────
class TransferCar:
    """46 `transfer_car_v1.json` 조회 — `scripts/collect/check_transfer_car_v1.lookup()` 과 같은 규칙.
    키 = (환승역, 타고 온 노선, 그 역열의 환승역 직전 역, 환승 노선, 환승 역열의 둘째 역) · prev 가 None 인 항목은 색인 안 함."""

    def __init__(self, doc):
        self.built_at = doc.get("built_at")
        self.by_prev, self.ambiguous = {}, set()
        for e in doc["entries"].values():
            if e.get("prev_nm") is None:
                continue
            k = (e["station_nm"], e["line"], e["prev_nm"], e["to_line"], e["to_next_nm"])
            if k in self.ambiguous:
                continue
            old = self.by_prev.get(k)
            if old is not None and old["positions"] != e["positions"]:
                # 조회 키가 같은데 칸이 다르다 — 어느 쪽인지 모른다. 키를 뺀다(순서에 따라 값이 바뀌면 안 된다 · GPT 23 #6)
                del self.by_prev[k]
                self.ambiguous.add(k)
                continue
            self.by_prev[k] = e

    @classmethod
    def load(cls, path=None):
        if path is None:
            from .paths import PROCESSED
            path = PROCESSED / "mobility" / "transfer_car_v1.json"
        p = Path(path)
        if not p.exists():
            return None
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def lookup(self, line_a, path_a, line_b, path_b):
        if len(path_a) < 2 or len(path_b) < 2:
            return None
        e = self.by_prev.get((path_a[-1], line_a, path_a[-2], line_b, path_b[1]))
        if e is None or e["to_station_nm"] != path_b[0]:
            return None
        return e["positions"]


def ridden_path(v, leg, lr, day_type):
    """판정기가 고른 편성의 실제 역열(a…b). 그 승차 분·도착 분과 맞는 편성들의 경로가 하나로 모일 때만 — 아니면 None."""
    b = leg["to"]
    paths = set()
    for _d, verd in chosen_departures(v, leg, lr, day_type):
        p = list(verd.path)
        if b in p:
            paths.add(tuple(p[: p.index(b) + 1]))
    return list(paths.pop()) if len(paths) == 1 else None


def transfer_cars(v, tc, legs, legs_result, day_type):
    """후보의 환승마다 칸 — 찾은 것만 [{station, from_line, to_line, car_door}]. 하나도 없으면 None(키 없음)."""
    if tc is None or len(legs) < 2 or any(leg_mode(x) != "subway" for x in legs):
        return None
    lrs = ride_results(legs, legs_result)              # 탄 구간만 순서대로(같은 표기가 두 번이어도 · GPT 23 #5)
    if lrs is None:
        return None
    paths = [ridden_path(v, leg, lr, day_type) for leg, lr in zip(legs, lrs)]
    out = []
    for i in range(len(legs) - 1):
        pa, pb = paths[i], paths[i + 1]
        if not pa or not pb:
            continue
        pos = tc.lookup(legs[i]["line"], pa, legs[i + 1]["line"], pb)
        if not pos:
            continue
        out.append({"station": station_name(pa[-1]), "from_line": line_name(legs[i]["line"]),
                    "to_line": line_name(legs[i + 1]["line"]), "car_door": pos[0]["car_door"]})
    return out or None
