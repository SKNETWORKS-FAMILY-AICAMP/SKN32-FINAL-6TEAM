# -*- coding: utf-8 -*-
"""역 ↔ 건물 지하 연결통로 표 — 서울교통공사 「지하철 연결통로 시설물정보」(2026-10-06 들임).

OSM 길 그래프에는 지하 통로·역 복합시설 연결이 없어, 지하철역과 이어진 건물(백화점·타워·지하상가)까지 걷는 값이 지상으로 크게
돌아가는 길로 나온다(걷기 모델 점검 2026-10-06). 이 표는 **어느 역과 어느 건물이 이어지는지**만 안다 — 좌표도 걷는 거리도 없다.
그래서 여기서는 「이어진다」를 사실로 쓰고(공식 표), 걷는 거리는 역~장소 직선 × CONNECTOR_FACTOR_PROPOSED 로 **추정**한다
(통로는 직선은 아니지만 지상 우회보다 짧다). 쓴 곳은 `plan.connector_used` 에 남는다 — 조용한 보정이 아니다.
"""
from __future__ import annotations

import json
import pathlib
import re

DATA = pathlib.Path(__file__).with_name("rules") / "metro_connectors_v1.json"

#: 시설 이름이 이 안에 들면 어느 건물인지 못 가린다(여러 역에 같은 이름이 있거나 일반 명사) — 장소 이름 맞대기에 쓰지 않는다.
GENERIC = {
    "지하보도", "보도육교", "지하상가", "민자역사", "복합환승센터", "환승 주차장", "양재 환승주차장", "터미널상가", "대학학원",
    "이마트", "홈플러스", "하이마트", "롯데쇼핑", "삼성 홈플러스", "현대상가", "대림상가", "송화쇼핑", "우성쇼핑", "방배동 근린생활시설",
    "사근동(육교)", "대우빌딩_보도", "삼성생명(지하보도)", "청진구역 지하보도", "산성공영주차장", "고덕2단지", "잠실1단지 상가", "잠실2단지 상가",
    "잠실3단지 상가", "그랜드 마트",
}

_STRIP = re.compile(r"[\s_·\-()（）‘’'\"]")


def _norm(s):
    return _STRIP.sub("", str(s or "")).lower()


def _station_key(nm):
    k = _norm(nm)
    return k[:-1] if k.endswith("역") and len(k) > 1 else k


class Connectors:
    """역마다 이어진 시설 이름 목록. `match(역, 장소이름)` → 시설 이름 또는 None."""

    def __init__(self, rows):
        self._by_station = {}
        for r in rows:
            fac = str(r.get("facility") or "").strip()
            if len(_norm(fac)) < 3 or fac in GENERIC:
                continue
            self._by_station.setdefault(_station_key(r.get("station")), []).append((_norm(fac), fac))

    @classmethod
    def load(cls, path=None):
        try:
            doc = json.loads(pathlib.Path(path or DATA).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls([])                 # 표가 없으면 연결통로 없이 — 종전 계산(조용한 거짓 연결은 만들지 않는다)
        return cls(doc.get("rows") or [])

    def match(self, station_nm, place_name):
        title = _norm(place_name)
        if not title:
            return None
        for key, fac in self._by_station.get(_station_key(station_nm), ()):
            if key in title:
                return fac
        return None

    def __len__(self):
        return sum(len(v) for v in self._by_station.values())
