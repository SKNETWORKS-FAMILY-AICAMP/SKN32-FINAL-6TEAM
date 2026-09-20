# modules/mobility/geo.py — 좌표 조회와 거리. 대안 열거가 '역 앞 정류장'을 찾을 때 쓴다.
# 소스: processed/mobility/station_coords.json (지하철 793역)
#       processed/mobility/bus_stops_v1.jsonl 의 lat/lng (버스 정류장 906개)
import json, math
from pathlib import Path


def meters(lat1, lng1, lat2, lng2):
    """평면 근사. 서울 규모(수십 km)에서 오차가 무시할 만하다."""
    dy = (lat2 - lat1) * 111_320
    dx = (lng2 - lng1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


class StationCoords:
    def __init__(self, doc):
        self.doc = doc
        self.by_key = doc.get("stations", {})
        self.built_at = doc.get("built_at") or doc.get("data_basis_date")
        self.by_name = {}
        for k, v in self.by_key.items():
            self.by_name.setdefault(v["station_nm"], v)     # 환승역은 아무 노선 것이나 — 좌표는 같다

    @classmethod
    def load(cls, path=None):
        if path is None:
            from scripts.collect._paths import PROCESSED
            path = PROCESSED / "mobility" / "station_coords.json"
        p = Path(path)
        if not p.exists():
            return None
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def get(self, line, station):
        """(노선, 역) → 좌표. 그 노선 것이 없으면 역명으로 찾는다(환승역은 좌표가 같다)."""
        return self.by_key.get(f"{line}|{station}") or self.by_name.get(station)

    def stations_near(self, lat, lng, within_m):
        """좌표 근처의 역. 역명 단위로 (거리 m, 역 레코드) 가까운 순 — 환승역은 한 번만.

        19번 방(2026-09-19): 버스 구간의 수단교체 대안이 '정류장 근처 역'을 찾을 때 쓴다.
        """
        best = {}
        for v in self.by_key.values():
            if v.get("lat") is None:
                continue
            d = meters(lat, lng, v["lat"], v["lng"])
            if d <= within_m and (v["station_nm"] not in best or d < best[v["station_nm"]][0]):
                best[v["station_nm"]] = (d, v)
        return sorted(best.values(), key=lambda t: t[0])
