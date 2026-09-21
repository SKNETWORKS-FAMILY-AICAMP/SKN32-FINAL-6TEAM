# modules/mobility/exits.py — 역 출구 좌표 조회 계층 (19번 방 · 2026-09-19)
# 소스: processed/mobility/station_exits_v1.json (OSM railway=subway_entrance · ODbL · 등급 **추정**)
# 규칙: rules.transfer.stop_station_walk
#
# ★ 쓰는 곳은 둘뿐이다 — 정류장↔역 환승 도보(지하철↔버스)와 그 근접 상한 판정.
#   시각을 확정하는 데는 쓰지 않는다(13번 인계 §4 적용 원칙). 시각 확정은 시간표로만.
# ★ 출구가 없는 역(광명·인천공항2터미널 등 7역명)은 호출 쪽이 역 좌표로 대신한다.
import json
from pathlib import Path

from .geo import meters


class StationExits:
    def __init__(self, doc):
        self.doc = doc
        self.exits = doc.get("exits", {})          # 역명 → [ {lat,lng,ref,desc,attrib,...} ]
        self.built_at = doc.get("built_at")
        self.source_id = doc.get("source_id", "osm_subway_entrance")
        self.grade = doc.get("grade", "추정")

    @classmethod
    def load(cls, path=None):
        if path is None:
            from .paths import PROCESSED
            path = PROCESSED / "mobility" / "station_exits_v1.json"
        p = Path(path)
        if not p.exists():
            return None                               # 없으면 호출 쪽이 역 좌표로 대신한다
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def exits_of(self, station_nm):
        return self.exits.get(station_nm, [])

    def nearest(self, station_nm, lat, lng):
        """그 역의 출구 중 (lat, lng) 에 가장 가까운 것. (거리 m, 출구) — 출구가 없으면 None."""
        best = None
        for e in self.exits_of(station_nm):
            d = meters(lat, lng, e["lat"], e["lng"])
            if best is None or d < best[0]:
                best = (d, e)
        return best
