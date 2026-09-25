# -*- coding: utf-8 -*-
"""이동 값 내놓기 — 32번 방(2026-09-25). 팀장이 꽂을 수 있는 **함수 하나 + CLI**.

    from app.modules.travel_ops.mobility_engine.plan import plan
    out = plan(places, items, party_size=2, constraints={"first_visit": True})
    body["items"] = out["items"]                                     # CreateTrip 의 기존 칸 그대로
    body["routes"] = {**body.get("routes", {}), **out["routes"]}     # 합친다(남겨 둔 입력 이동 항목의 route 보존)

    python -m app.modules.travel_ops.mobility_engine.plan --in trip_in.json --out trip_out.json

입력 = CreateTrip 의 기존 칸(`places[]`·`items[]`·`party_size`·`constraints`) — 새 칸 없음.
출력 = 출력 스펙 v1.3 의 기존 칸만 — 새 키 0.
  items[kind=mobility]  seq · kind · title · starts_at · ends_at · route
  routes{<키>}          from · to · planned · options[{id, label, eta_min, uses}]
  그 밖에 봉투에 `skipped`(이동 항목을 못 만든 구간과 이유)·`basis`(어느 판으로 냈나)를 같이 준다 —
  **코어 몸통에는 `items`·`routes` 두 칸만 옮긴다**(CreateTrip 은 extra=forbid).

값의 뜻 (39 인계 §1-2 · 스펙 v1.3 §5)
  starts_at = 도착 목표(다음 항목 starts_at) − (eta_min + margin_min) − slack_min   (slack_min ≥ 0)
              = **그 구간이 성립하는 마지막 출발**(판정기의 worst 역산 · 버퍼 포함).
              slack_min 은 시간표가 분 단위로 연속이 아니라서 남는 몫이다 — 지하철은 「그 다음 편」이 늦으면
              출발을 더 미룰 수 없다. slack 을 빼고 식 그대로 쓰면 편성을 놓치는 시각이 나온다(결정 1).
  ends_at   = starts_at + eta_min
  eta_min   = 문→문 예정 소요(중앙값 · 버퍼 안 섞음 — 팀 density.py 가 자기 버퍼를 더한다)
  다음 항목까지 남는 간격(= margin_min + slack_min)이 곧 여유다. 여유 분은 따로 안 낸다(v1.3).

안 내는 것: last_feasible_depart_min · 등급 · 내부 판정 넷 · p90·slack·verdict·reason·modes·walk_m 등 상세 값
            (계획서 작성 콜이 오면 `out` 에서 뽑는다 — 스펙 v1.3).

시각·날짜 (45 계약)
  `case.date` 는 **운행일**이다 — 04:00 전 시각은 그 운행일의 연장(00:30 → 전날 24:30).
  입력 시각은 ISO 8601. 오프셋이 없으면 서울 시각으로 읽는다(trip_api._seoul 과 같은 규칙).
  출력 시각은 항상 `+09:00`, 초 `:00`.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from .timeutil import MIN_DAY, SERVICE_DAY_START_MIN
from .verify_time import leg_mode

KST = timezone(timedelta(hours=9))
PLAN_VERSION = "plan-v1"

# uses 노선명 — 팀장 확정 표기(9/24): 1~9호선은 `N호선`, 그 밖은 공식 이름.
# 시간표의 노선명이 공식 이름과 다른 것 중 **확인된 것만** 바꾼다. 나머지는 시간표 이름 그대로(확인 안 한 것 §).
_LINE_OFFICIAL = {"경의선": "경의중앙선"}


# ── 시각 ────────────────────────────────────────────────────────────────
def _parse_dt(v):
    """ISO 문자열·datetime → 서울 시각 aware datetime. 오프셋 없으면 서울로 읽는다."""
    if v is None:
        return None
    if isinstance(v, datetime):
        dt = v
    else:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def service_day(dt):
    """서울 시각 → (운행일, 운행일 분). 04:00 전은 전날 운행일의 24:xx(45 계약)."""
    m = dt.hour * 60 + dt.minute
    d = dt.date()
    if m < SERVICE_DAY_START_MIN:
        return d - timedelta(days=1), m + MIN_DAY
    return d, m


def iso_of(service_date, minute):
    """(운행일, 운행일 분) → 'YYYY-MM-DDTHH:MM:00+09:00'. 24:xx 는 다음 날 벽시계로."""
    dt = datetime.combine(service_date, time(0, 0), tzinfo=KST) + timedelta(minutes=int(minute))
    return dt.strftime("%Y-%m-%dT%H:%M:00+09:00")


# ── 표기 ────────────────────────────────────────────────────────────────
def line_name(line):
    """시간표 노선명 → uses·label 노선명. '02호선' → '2호선'."""
    if line and len(line) == 4 and line.endswith("호선") and line[:2].isdigit():
        return f"{int(line[:2])}호선"
    return _LINE_OFFICIAL.get(line, line)


def station_name(nm):
    """uses 역명 — 괄호 병기와 끝의 「역」을 뺀다. 이름 자체가 「서울역」이면 그대로(9/24 표기)."""
    s = str(nm).split("(")[0].strip()
    if s == "서울역":
        return s
    return s[:-1] if s.endswith("역") and len(s) > 1 else s


def uses_of(legs):
    """탄 역·갈아탄 역·내린 역만(환승역은 두 노선 각각) · 버스는 `버스:<노선번호>` · 도보·자전거는 안 적는다.
    ★ 버스가 지나는 `도로:` 는 아직 못 채운다 — 노선별 경유 도로 표가 없다(확인 안 한 것)."""
    out = []
    for leg in legs:
        m = leg_mode(leg)
        if m == "subway":
            ln = line_name(leg["line"])
            out += [f"{ln}:{station_name(leg['from'])}", f"{ln}:{station_name(leg['to'])}"]
        elif m == "bus":
            out.append(f"버스:{leg['route']}")
    seen, uniq = set(), []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def label_of(legs):
    parts = []
    for leg in legs:
        m = leg_mode(leg)
        if m == "subway":
            parts.append(f"{line_name(leg['line'])} {leg['from']}→{leg['to']}")
        elif m == "bus":
            parts.append(f"버스 {leg['route']} {leg['from']}→{leg['to']}")
        else:
            parts.append(f"{m} {leg.get('from')}→{leg.get('to')}")
    return " → ".join(parts)


# ── 입력 정리 ────────────────────────────────────────────────────────────
def _as_dict(x):
    if hasattr(x, "model_dump"):
        return x.model_dump()
    return dict(x)


def party_of(party_size, constraints):
    """판정기 party — 기존 칸에서만 만든다.
    constraints.mobility_ease == "needs_rest"(팀 density.py 가 읽는 값) → fatigue_high(환승 상한 1).
    party_size 는 지금 판정에 쓰는 자리가 없다(따릉이 인원 등은 22 규칙이 party 플래그로만 본다) — 그대로 싣기만 한다."""
    c = constraints or {}
    p = {}
    if party_size:
        p["size"] = int(party_size)
    if c.get("mobility_ease") == "needs_rest":
        p["fatigue_high"] = True
    return p


# ── 본체 ─────────────────────────────────────────────────────────────────
class Planner:
    def __init__(self, runtime, *, stage="planning", modes=None):
        self.rt = runtime
        self.modes = set(modes) if modes else None       # 후보 수단 거르기(예: {"subway"}) — None 이면 전부
        self.trace = None                                 # 시험·대조용 — 리스트를 주면 구간마다 내부 값을 적는다
        self.v = runtime._v
        self.stage = stage
        self.speed = self.v.R["measured_baseline"]["kakao_walk_speed_mps"]["value"]

    def _walk_limit(self, party):
        return self.v._walk_limit(party)

    def _walk(self, straight_m):
        """장소 도보 분 = 직선 × 우회계수 ÷ 1.04 m/s (rules transfer.stop_station_walk — 정류장↔역과 같은 식)."""
        f = self.v.R["transfer"]["stop_station_walk"]["detour_factor"]["value"]
        return math.ceil(straight_m * f / self.speed / 60) if straight_m else 0

    def _near_station(self, place, limit_m):
        """장소 → 가장 가까운 역(역 좌표 직선 · 도보 상한 안). 거리는 그 역에서 장소에 가장 가까운 출구까지
        (출구표가 없으면 역 좌표) — 정류장↔역 환승(19번)과 같은 방식. (역명, 직선 m) 또는 None."""
        sc = self.v.sc
        if sc is None:
            return None
        near = sc.stations_near(place["lat"], place["lon"], limit_m)
        if not near:
            return None
        d, rec = near[0]
        nm = rec["station_nm"]
        if self.v.ex is not None:
            e = self.v.ex.nearest(nm, place["lat"], place["lon"])
            if e is not None:
                d = e[0]
        return nm, d

    def leg(self, a_place, b_place, arrive_dt, party, first_visit, case_id, not_before_dt=None):
        """장소 a → 장소 b, 도착 목표 arrive_dt. ((route_def, 시작 분, 끝 분, 운행일), None) 또는 (None, 이유 dict).

        분은 **도착 목표의 운행일 축**이다. 역 도착 목표가 04:00 을 넘어 앞 운행일로 넘어가면(04:00 목표 − 도보 2분)
        판정기에는 그 운행일·그 분으로 넘기고 결과를 이 축으로 되돌린다 — 정수 분을 그대로 넘기면 판정기가
        240 미만을 +24h 로 읽어 그날 밤 막차로 간다(자체 대조 #1).
        not_before_dt: 앞 항목이 끝나는 시각. 이보다 먼저 떠나야 하는 후보는 싣지 않는다(겹치면 코어 등록이 거절한다)."""
        from .geo import meters
        sdate, arrive_by = service_day(arrive_dt)
        nb = None
        if not_before_dt is not None:
            nd, nm_ = service_day(not_before_dt)
            nb = nm_ + (nd - sdate).days * MIN_DAY
        wlim = self._walk_limit(party)
        buf = self.v.rv("buffer", "by_stage", self.stage)
        opts, dropped_early = [], 0

        # ① 도보 직행 — 두 장소 직선이 도보 상한 안이면 후보. 여유는 정책 버퍼(수단 무관 · 39 결정 2).
        direct = meters(a_place["lat"], a_place["lon"], b_place["lat"], b_place["lon"])
        if direct <= wlim and (self.modes is None or "walk" in self.modes):
            eta = max(1, self._walk(direct))
            opts.append({"id": "walk", "label": "도보", "eta_min": eta, "uses": [],
                         "_start": arrive_by - eta - buf, "_transfers": 0, "_n": 0,
                         "_margin": buf, "_slack": 0})

        # ② 대중교통 — 가까운 역끼리 다목적 후보(판정기 verify_multi) → 후보마다 마지막 성립 출발로 다시 판정
        oa, ob = self._near_station(a_place, wlim), self._near_station(b_place, wlim)
        why = None
        if oa is None or ob is None:
            why = {"code": "no_data", "reason": "도보 상한 안에 지하철역이 없다"
                   + (f"({a_place['name']})" if oa is None else f"({b_place['name']})")}
        elif oa[0] == ob[0]:
            why = {"code": "no_data", "reason": f"두 장소의 가장 가까운 역이 같다({oa[0]}) — 도보만 본다"}
        else:
            wa, wb = self._walk(oa[1]), self._walk(ob[1])
            st_date, by_station = service_day(arrive_dt - timedelta(minutes=wb))
            off = (st_date - sdate).days * MIN_DAY            # 역 운행일 축 → 도착 목표 축 (0 또는 −1440)
            probe = {"id": case_id, "date": st_date.isoformat(), "stage": self.stage,
                     "depart_at": max(SERVICE_DAY_START_MIN, by_station - 180), "arrive_by": by_station,
                     "multi": {"from": oa[0], "to": ob[0]}, "party": party, "first_visit": first_visit}
            r = self.v.verify_case(probe)
            n_mode = 0
            for c in r.candidates or []:
                if self.modes is not None and any(leg_mode(x) not in self.modes for x in c["legs"]):
                    continue
                n_mode += 1
                lfd = (c.get("out") or {}).get("last_feasible_depart_min")
                sub_by = by_station - c["walk_out_min"]
                if lfd is None or sub_by < SERVICE_DAY_START_MIN:
                    continue
                sub = {"id": f"{case_id}/{c['n']}", "date": st_date.isoformat(), "stage": self.stage,
                       "legs": c["legs"], "depart_at": lfd + c["walk_in_min"], "arrive_by": sub_by,
                       "party": party, "first_visit": first_visit, "no_alternatives": True}
                o2 = self.v.verify_case(sub).out or {}
                if o2.get("verdict") != "feasible" or o2.get("eta_min") is None or (o2.get("slack_min") or 0) < 0:
                    continue          # 역산 시각으로 다시 봐도 성립이 아니면 싣지 않는다(모르면 뺀다)
                eta = int(wa + c["walk_in_min"] + o2["eta_min"] + c["walk_out_min"] + wb)
                start = lfd - wa + off
                margin, slack = o2.get("margin_min") or 0, o2.get("slack_min") or 0
                if start + eta + margin + slack != arrive_by:
                    continue          # 식이 안 맞으면 어딘가 축이 어긋난 것 — 내지 않는다(늦은 출발을 조용히 내지 않게)
                opts.append({"id": f"opt{c['n']}", "label": label_of(c["legs"]), "eta_min": eta,
                             "uses": uses_of(c["legs"]), "_start": start,
                             "_transfers": c.get("transfers") or 0, "_n": c["n"],
                             "_margin": margin, "_slack": slack})
            if not any(o["id"] != "walk" for o in opts):
                if r.candidates and n_mode == 0:
                    why = {"code": "no_data", "reason": f"고른 수단({', '.join(sorted(self.modes))}) 안의 후보가 없다"}
                else:
                    why = {"code": (r.out or {}).get("code") or "no_data",
                           "reason": (r.out or {}).get("reason") or r.reason}

        if nb is not None:
            keep = [o for o in opts if o["_start"] >= nb]
            dropped_early = len(opts) - len(keep)
            opts = keep
        if not opts:
            if dropped_early:
                return None, {"code": "arrive_late",
                              "reason": f"앞 항목이 끝난 뒤({not_before_dt.astimezone(KST):%H:%M}) 떠나서는 "
                                        f"{arrive_dt.astimezone(KST):%H:%M} 도착에 맞는 후보가 없다"}
            return None, why or {"code": "no_data", "reason": "성립하는 후보가 없다"}
        # 계획 수단 — **가장 늦게 떠나도 되는 후보**(동률은 환승 적은 · 소요 짧은 · 생성 순). 순위가 아니라
        #   「일정대로 움직이게」 하나를 고르는 규칙이다. 나머지는 options 에 순위 없이 남는다(23 이 이유를 붙인다).
        planned = max(opts, key=lambda o: (o["_start"], -o["_transfers"], -o["eta_min"], -o["_n"]))
        start = planned["_start"]
        end = start + planned["eta_min"]
        if self.trace is not None:
            self.trace.append({"case": case_id, "date": sdate.isoformat(), "arrive_by_min": arrive_by,
                               "planned": planned["id"],
                               "options": [{"id": o["id"], "start_min": o["_start"], "eta_min": o["eta_min"],
                                            "margin_min": o.get("_margin"), "slack_min": o.get("_slack"),
                                            "transfers": o["_transfers"]} for o in opts]})
        route = {"from": a_place["name"], "to": b_place["name"], "planned": planned["id"],
                 "options": [{k: v for k, v in o.items() if not k.startswith("_")} for o in opts]}
        return (route, start, end, sdate), None


def _key_time(it):
    return (_parse_dt(it["starts_at"]), it.get("seq", 0))


def plan(places, items, party_size=None, constraints=None, *, runtime=None, stage="planning",
         modes=None, trace=None):
    """places·items(·party_size·constraints) → {"items", "routes", "skipped", "basis"}.

    items : 입력 항목 중 이동이 아닌 것을 시각 순으로 두고, **장소가 다른 이웃 둘 사이마다** 이동 항목을 끼운다.
            그 구간에 입력 이동 항목(kind=mobility)이 있었으면 우리 값으로 바꾼다 — 이동 시각의 정본은 우리다.
            우리가 그 구간을 못 만들면(skipped) 입력 이동 항목을 그대로 남긴다.
            seq 는 합친 순서대로 1부터 다시 매긴다. 입력 항목의 다른 칸은 손대지 않는다.
            장소가 없는 항목(자유 시간 등)을 사이에 두면 그 앞뒤는 잇지 않는다 — 어디서 떠나는지 모른다.
            앞 항목이 끝나기 전에 떠나야 하는 후보는 싣지 않는다(코어 등록의 overlap 을 미리 피한다).
    routes: 이번에 만든 이동 항목의 경로 정의만 — **호출 쪽 routes 에 합친다**(update). 통째로 바꾸면
            남겨 둔 입력 이동 항목의 route 키가 사라진다.
    skipped: 이동 항목을 못 만든 구간 [{from, to, code, reason}] — 그 구간은 **값을 빼고** 낸다(모르면 뺀다).
    modes  : 후보 수단 거르기 — None(기본)이면 전부. 예시 파일은 {"subway", "walk"} 로 뽑았다(노트북 버스 데이터가 옛 판).
    trace  : 리스트를 주면 구간마다 내부 값(시작 분·@·slack·환승)을 적는다 — 코어로는 안 나간다.
    """
    if runtime is None:
        from .runtime import get_verifier
        runtime = get_verifier(quiet=True)
    P = Planner(runtime, stage=stage, modes=modes)
    P.trace = trace
    constraints = dict(constraints or {})
    party = party_of(party_size, constraints)
    first_visit = constraints.get("first_visit", True)

    pl = {p["key"]: p for p in (_as_dict(x) for x in places)}
    its = [_as_dict(x) for x in items]
    stay = sorted((it for it in its if it.get("kind") != "mobility"), key=_key_time)
    moves_in = sorted((it for it in its if it.get("kind") == "mobility"), key=_key_time)

    def moves_between(a, b):
        """입력에 있던 이동 항목 중 a 시작 ~ b 시작 사이의 것 — 우리가 그 구간을 못 만들면 그대로 남긴다."""
        lo, hi = _parse_dt(a["starts_at"]), _parse_dt(b["starts_at"])
        return [dict(m) for m in moves_in if lo <= _parse_dt(m["starts_at"]) < hi]

    merged, routes, skipped = [], {}, []

    def skip(a, b, entry):
        skipped.append(entry)
        merged.extend(moves_between(a, b))

    for i, a in enumerate(stay):
        merged.append(dict(a))
        if i + 1 >= len(stay):
            merged.extend(dict(m) for m in moves_in if _parse_dt(m["starts_at"]) >= _parse_dt(a["starts_at"]))
            break
        b = stay[i + 1]
        pa, pb = pl.get(a.get("place")), pl.get(b.get("place"))
        if pa is None or pb is None:
            skip(a, b, {"from": a.get("title"), "to": b.get("title"), "code": "no_data",
                        "reason": "장소가 없는 항목이다 — 어디서 떠나는지(어디로 가는지) 모른다"})
            continue
        if a.get("place") == b.get("place"):
            merged.extend(moves_between(a, b))
            continue
        if pa.get("lat") is None or pb.get("lat") is None:
            skip(a, b, {"from": pa["name"], "to": pb["name"], "code": "no_data", "reason": "좌표가 없다"})
            continue
        got, why = P.leg(pa, pb, _parse_dt(b["starts_at"]), party, first_visit,
                         case_id=f"{a.get('place')}_to_{b.get('place')}",
                         not_before_dt=_parse_dt(a.get("ends_at") or a["starts_at"]))
        if got is None:
            skip(a, b, {"from": pa["name"], "to": pb["name"], **why})
            continue
        route, start, end, sdate = got
        key = f"{a.get('place')}_to_{b.get('place')}"
        n = 2
        while key in routes:
            key = f"{a.get('place')}_to_{b.get('place')}_{n}"
            n += 1
        routes[key] = route
        if trace is not None and trace:
            trace[-1]["route"] = key
        merged.append({"seq": 0, "kind": "mobility", "title": f"{pa['name']} → {pb['name']}",
                       "starts_at": iso_of(sdate, start), "ends_at": iso_of(sdate, end), "route": key})
    for n, it in enumerate(merged, 1):
        it["seq"] = n
    return {"items": merged, "routes": routes, "skipped": skipped,
            "basis": {"timetable_built_at": runtime.timetable_built_at, "rules_version": runtime.rules_version,
                      "plan_version": PLAN_VERSION,
                      "decided_at": datetime.now(KST).strftime("%Y-%m-%dT%H:%M:00+09:00")}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="이동 값 내놓기 — places·items → 이동 항목 + routes (출력 스펙 v1.3)")
    ap.add_argument("--in", dest="inp", required=True, help="입력 JSON {places, items, party_size?, constraints?}")
    ap.add_argument("--out", help="출력 JSON 경로(없으면 표준출력)")
    ap.add_argument("--stage", default="planning", choices=("planning", "pre_departure", "in_progress"))
    ap.add_argument("--no-basis", action="store_true", help="basis 를 빼고 낸다(예시 파일을 판 바뀔 때마다 안 흔들리게)")
    ap.add_argument("--modes", nargs="*", help="후보 수단 거르기(subway bus walk bike) — 없으면 전부")
    ap.add_argument("--trace", help="구간마다 내부 값(시작 분·@·slack)을 이 JSON 에 적는다 — 대조용")
    a = ap.parse_args(argv)
    doc = json.loads(Path(a.inp).read_text(encoding="utf-8"))
    from .runtime import build_verifier
    rt = build_verifier(quiet=True)
    tr = [] if a.trace else None
    res = plan(doc.get("places") or [], doc.get("items") or [], doc.get("party_size"), doc.get("constraints"),
               runtime=rt, stage=a.stage, modes=a.modes, trace=tr)
    if a.trace:
        Path(a.trace).write_text(json.dumps(tr, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if a.no_basis:
        res.pop("basis", None)
    txt = json.dumps(res, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(txt + "\n", encoding="utf-8")
        print(f"[plan] 이동 {sum(1 for x in res['items'] if x['kind'] == 'mobility')} · "
              f"못 만든 구간 {len(res['skipped'])} → {a.out}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
