# -*- coding: utf-8 -*-
"""급행이 있는 노선의 **열차 단위** 운행표 — 9호선 · 1호선 (서울 열린데이터광장 역별 시간표 OA-101, 2026-10-07 들임).

왜 필요했나(2026-10-07 카카오맵 대조): 통합 시간표(timetable_v1)에는 열차번호·급행 표시가 없다. 그래서 판정기는
  ① 9호선 모든 열차가 모든 역에 선다고 계산했다 — 급행 구간은 실제보다 늦게(여의도→봉은사 우리 28분 · 급행 실제 중앙값 19.8분),
  ② 급행이 서지 않는 역(샛강·흑석 등)에도 급행이 선다고 보았다 — 그 역 시간표가 실제 124편인데 239편으로 불어 있었다(배차 절반).
이 표는 열차 한 대의 **정차역과 역마다 도착·출발 시각**을 준다. 시간표 읽기(`Timetable.load`)가 이 노선은 표로 바꿔 읽고,
판정기는 열차가 도착역에 서는지 보고 승차 시간을 (도착역 도착 − 출발역 출발)로 잰다.

표가 없으면(파일 없음·읽기 실패) 그 노선은 종전 시간표 그대로 — 조용히 줄이지 않고 `AVAILABLE` 이 비어 있음이 드러난다.
"""
from __future__ import annotations

import gzip
import json
import pathlib

RULES = pathlib.Path(__file__).with_name("rules")
FILES = {"09호선": RULES / "express_runs_line09_v1.json.gz", "01호선": RULES / "express_runs_line01_v1.json.gz"}


class Run:
    """열차 한 대. stops = {역: (도착초|None, 출발초|None)} · order = {역: 순번}."""
    __slots__ = ("tno", "express", "dir", "stops", "order", "dest")

    def __init__(self, tno, express, dir_, seq, names):
        self.tno, self.express, self.dir = tno, bool(express), dir_
        self.stops = {names[s]: (a, d) for s, a, d in seq}
        self.order = {names[s]: i for i, (s, _a, _d) in enumerate(seq)}
        self.dest = names[seq[-1][0]]

    def serves(self, origin, target):
        """origin 에서 타 target 에서 내릴 수 있나 — 두 역에 다 서고 origin 이 먼저."""
        oi, ti = self.order.get(origin), self.order.get(target)
        return oi is not None and ti is not None and oi < ti and self.stops[origin][1] is not None

    def ride_min(self, origin, target):
        """(target 도착 − origin 출발) 분 — 소수. 못 구하면 None."""
        if not self.serves(origin, target):
            return None
        arr = self.stops[target][0]
        if arr is None:
            arr = self.stops[target][1]
        dep = self.stops[origin][1]
        if arr is None or arr < dep:
            return None
        return (arr - dep) / 60.0


_CACHE = {}


def load_line(line):
    """{day_type: [(역, 출발분, dir, 행선지, Run)]} 또는 None(표 없음). 프로세스 안에서 한 번만 읽는다."""
    if line in _CACHE:
        return _CACHE[line]
    path = FILES.get(line)
    out = None
    if path is not None and path.exists():
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                doc = json.load(f)
            names = doc["stations"]
            out = {}
            for day, runs in doc["runs"].items():
                rows = []
                for tno, ex, dr, seq in runs:
                    run = Run(tno, ex, dr, seq, names)
                    for s, _a, d in seq:
                        if d is not None:                    # 종착역은 출발이 없다
                            rows.append((names[s], d // 60, run))
                out[day] = rows
        except (OSError, ValueError, KeyError):
            out = None
    _CACHE[line] = out
    return out


def stations_of(line):
    """그 노선 열차 단위 표에 나오는 역 집합(없으면 None)."""
    d = load_line(line)
    if d is None:
        return None
    return {nm for rows in d.values() for nm, _m, _r in rows}


def available():
    """표가 읽히는 노선 목록."""
    return [ln for ln in FILES if load_line(ln) is not None]


def ride_of(lo, line, d, verdict, origin, target):
    """열차 d 를 origin 에서 타 target 에서 내릴 때 승차 분. 열차 단위 표가 있으면 (도착 − 출발) 실제 시각, 없으면 종전 —
    그 열차가 도는 경로 위 역간 평균(`LineOrder.travel_min_on_path`). 판정기·후보 설명·추정이 같은 값을 쓰게 한 곳에 둔다."""
    run = getattr(d, "run", None)
    if run is not None:
        r = run.ride_min(origin, target)
        if r is not None:
            return r
    return lo.travel_min_on_path(line, verdict.path, target)
