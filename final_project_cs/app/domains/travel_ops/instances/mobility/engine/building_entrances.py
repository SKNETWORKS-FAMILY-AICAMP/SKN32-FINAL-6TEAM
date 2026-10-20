"""건물 안 장소의 보행 진입점 — 도로명주소 건물 도형의 출입구 → 도로 연결선 끝 (2026-10-19).

☆왜. 장소 좌표가 큰 건물(역사 · 대형마트 · 복합시설) 한가운데에 있으면 보행 길까지 30 m 넘게 떨어져 서울 보행 중계 라우터가
  「낙관 가능」을 내고 플래너가 걷기 후보를 「보행 접근 미검증」으로 뺀다. 사람은 건물 출입구로 나와 길에 오른다.
  서울 장소 32곳 측정에서 30 m 넘게 떨어진 10곳 중 7곳이 출입구 연결선 끝에서 30 m 안에 보행 길이 있었다
  (records/reports/2026-10-19_building_entrance_access/REPORT.md).

자료 — `processed/mobility/building_entrance_seoul_v1/buildings.jsonl.gz`(datasets/mobility/scripts/build_building_entrance_seoul_v1.py).
  한 줄 = 건물 하나: `k` 건물 키 · `bb` 상자 · `r` 고리들(1e-6 도 정수 lon,lat 이어 붙임) · `e` 출입구들
  [출입구 lon, lat, 연결선 끝 lon, lat(1e-6 도 정수), 연결선 길이 m, 출입구 구분].
  보행 길에서 멀 수 없는 작은 건물과 쓸 수 있는 출입구가 없는 건물은 자료에 없다(빌더 규칙) — 없으면 지금처럼 「미검증」으로 남는다.

규칙 — 점이 든 건물(짝홀 고리 판정)의 출입구를 모두 후보로 돌려준다. 고르는 일은 라우터가 한다.
  자료 파일이 없으면 `available()` 이 False — 이 기능 전과 같은 동작(거리를 만들지 않는다).
  처음 물을 때 한 번 올린다(서울 밖 · 가까운 장소만 다루는 판정기는 올리지 않는다).
"""
from __future__ import annotations

import array
import gzip
import json
import threading
from pathlib import Path

from .car import hav

Q = 1e6
ENTRANCES_DIRNAME = "building_entrance_seoul_v1"             # processed/mobility/ 아래 — 서울 보행 그래프 옆
CELL = 0.002                                               # 격자 칸(도) — 상자가 걸친 칸마다 건물 번호를 단다
_SHARED: dict[str, "BuildingEntrances"] = {}
_SHARED_LOCK = threading.Lock()


def _in_rings(x, y, rings):
    """짝홀 판정 — 구멍(안뜰) 고리도 같은 목록에 있다. 좌표는 정수(1e-6 도)."""
    inside = False
    for ring in rings:
        n = len(ring) // 2
        j = n - 1
        for i in range(n):
            xi, yi, xj, yj = ring[2 * i], ring[2 * i + 1], ring[2 * j], ring[2 * j + 1]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-300) + xi:
                inside = not inside
            j = i
    return inside


class BuildingEntrances:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.path = self.folder / "buildings.jsonl.gz"
        self._lock = threading.Lock()
        self._loaded = False
        self.keys, self.bbox, self.rings, self.ents, self.grid = [], [], [], [], {}
        self.version = None

    @classmethod
    def shared(cls, folder):
        key = str(Path(folder).resolve())
        with _SHARED_LOCK:
            r = _SHARED.get(key)
            if r is None:
                r = _SHARED[key] = cls(folder)
            return r

    def available(self):
        return self.path.exists()

    @property
    def source_id(self):
        return self.version or self.folder.name

    def _load(self):
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            man = self.folder / "MANIFEST.json"
            if man.exists():
                self.version = json.loads(man.read_text(encoding="utf-8")).get("version")
            with gzip.open(self.path, "rt", encoding="utf-8") as f:
                for line in f:
                    b = json.loads(line)
                    i = len(self.keys)
                    self.keys.append(b["k"])
                    x0, y0, x1, y1 = b["bb"]
                    self.bbox.append((x0, y0, x1, y1))
                    self.rings.append([array.array("i", r) for r in b["r"]])
                    self.ents.append(b["e"])
                    for ci in range(int(x0 / Q // CELL), int(x1 / Q // CELL) + 1):
                        for cj in range(int(y0 / Q // CELL), int(y1 / Q // CELL) + 1):
                            self.grid.setdefault((ci, cj), []).append(i)
            self._loaded = True

    def candidates(self, lng, lat):
        """점이 든 건물의 출입구 후보 — [{building, kind, entrance(lng,lat), road_end(lng,lat), inner_m, connect_m}].

        inner_m = 장소 → 출입구 직선(건물 안 실제 동선은 이보다 길 수 있다 — 근거에 그대로 적는다)."""
        if not self.available():
            return []
        self._load()
        x, y = lng * Q, lat * Q
        out = []
        for i in self.grid.get((int(lng // CELL), int(lat // CELL)), ()):
            x0, y0, x1, y1 = self.bbox[i]
            if not (x0 <= x <= x1 and y0 <= y <= y1) or not _in_rings(x, y, self.rings[i]):
                continue
            for elon, elat, rlon, rlat, conn_m, kind in self.ents[i]:
                ent = (elon / Q, elat / Q)
                out.append({"building": self.keys[i], "kind": kind, "entrance": ent, "road_end": (rlon / Q, rlat / Q),
                            "inner_m": round(hav((lng, lat), ent), 1), "connect_m": float(conn_m)})
        return out
