"""서울 안 걸음은 서울시 도보 네트워크 그래프와 기존 라우터로 함께 찾아 검증된 짧은 길을 고르는 중계 라우터 (2026-10-13).

☆왜. OSM 도로 그래프의 걸음 길은 골목·광장 입구 연결이 빠진 곳이 많아, 카카오 웹 같은 좌표 대조에서 4쌍 모두 제품이 길었다
  (+8~+37%). 서울시 「자치구별 도보 네트워크 공간정보」(공공누리 1유형)로 만든 그래프는 같은 4쌍 중 3쌍이 크게 나아졌다
  (records/reports/2026-10-12_mobility_no_fallback/REPORT-claude-20261013-v1.md). 사용자 결정(2026-10-13): 서울에 한해 이 자료를 쓴다.

규칙 — ☆`[2026-10-13 개정]` 서울시 그래프만 쓰는 판(백업 walk_router_seoul_only_v1.py)은 제품 계산 전에 고정한 독립 12쌍에서
  카카오 ±10% 안이 4/12 로 OSM(9/12)보다 나빴다(남산·보도 없는 길·공원 길 누락). 그래서 서울 안 걸음은 **두 자료로 모두** 찾는다.
  · 걸음(foot)이고 출발·도착이 모두 서울시 경계 안이면 서울시 도보 그래프와 기존 라우터(OSM 등)로 각각 찾는다.
  · 접근이 검증된(낙관 표시가 아닌) 경로 중 **거리가 짧은 것**을 고른다. 둘 다 낙관이면 짧은 쪽을 낙관 표시 그대로 돌려준다
    (플래너가 「보행 접근 미검증」으로 막는다). 둘 다 실패하면 두 이유를 묶어 RouterDown — 거리를 지어내지 않는다.
  · 고른 자료와 두 후보(거리 · 낙관 · 실패 이유)를 경로의 `walk_candidates` 에 남긴다 — 「조용한 대체」가 아니라 기록된 선택이다.
  · 그 밖(서울 밖 끝점 · 자동차 · 자전거)은 기존 라우터 그대로.
  · 응답 경로에 어느 자료로 찾았는지(`source_id` · `basis`)를 싣는다 — BikeRouter 가 근거 칸에 옮긴다.
"""
from __future__ import annotations

import json
from pathlib import Path

SEOUL_WALK_BASIS = "서울시 도보 네트워크"


def _rings_of(geom):
    """GeoJSON Polygon/MultiPolygon → [(바깥 고리, [구멍 고리…])…] — 좌표 (lng, lat)."""
    t, c = geom["type"], geom["coordinates"]
    polys = [c] if t == "Polygon" else c if t == "MultiPolygon" else None
    if polys is None:
        raise ValueError(f"경계 도형이 다각형이 아니다: {t}")
    return [(p[0], p[1:]) for p in polys]


def _in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-300) + xi:
            inside = not inside
        j = i
    return inside


class Boundary:
    """점이 경계 다각형 안인지(구멍 제외). 외부 라이브러리 없이 고리 판정."""

    def __init__(self, polys):
        self.polys = polys
        xs = [p[0] for outer, _h in polys for p in outer]
        ys = [p[1] for outer, _h in polys for p in outer]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))

    @classmethod
    def from_geojson(cls, path):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        feats = doc["features"] if doc.get("type") == "FeatureCollection" else [doc]
        polys = []
        for f in feats:
            polys.extend(_rings_of(f["geometry"]))
        return cls(polys)

    def contains(self, lng, lat):
        x0, y0, x1, y1 = self.bbox
        if not (x0 <= lng <= x1 and y0 <= lat <= y1):
            return False
        for outer, holes in self.polys:
            if _in_ring(lng, lat, outer) and not any(_in_ring(lng, lat, h) for h in holes):
                return True
        return False


class SeoulWalkRouter:
    """`GraphRouter`/`GraphHopperClient` 와 같은 `route((lng,lat),(lng,lat), profile)` 모양. 기존 라우터를 감싼다."""

    def __init__(self, base, seoul, boundary):
        self.base, self.seoul, self.boundary = base, seoul, boundary
        self.seoul_calls = 0

    # BikeRouter·플래너가 읽는 속성은 기존 라우터 것을 그대로 보인다(역 접근 길 재기 여부 등 동작을 바꾸지 않는다)
    @property
    def is_local(self):
        return bool(getattr(self.base, "is_local", False))

    @property
    def url(self):
        return getattr(self.base, "url", None)

    @property
    def basis(self):
        return getattr(self.base, "basis", "graphhopper")

    @property
    def source_id(self):
        return getattr(self.base, "source_id", None)

    def available(self):
        return bool(self.base.available()) if hasattr(self.base, "available") else True

    def info(self):
        got = self.base.info() if hasattr(self.base, "info") else None
        if got is None:
            return None
        return dict(got, seoul_walk=self.seoul.info() if hasattr(self.seoul, "info") else None)

    def warm(self, profiles=("car", "foot", "bike")):
        if hasattr(self.base, "warm"):
            self.base.warm(profiles)
        self.seoul.warm(("foot",))

    def uses_seoul(self, s, e, profile):
        return profile == "foot" and self.boundary.contains(s[0], s[1]) and self.boundary.contains(e[0], e[1])

    def _try(self, router, s, e, profile, label):
        from .car import RouterDown
        try:
            doc = router.route(s, e, profile=profile)
        except (RouterDown, OSError, ValueError) as ex:
            return None, {"source": label, "error": f"{type(ex).__name__}: {str(ex)[:100]}"}
        paths = (doc or {}).get("paths") or []
        p = paths[0] if paths and isinstance(paths[0], dict) else None
        if p is None or not isinstance(p.get("distance"), (int, float)):
            return None, {"source": label, "error": "no_path"}
        q = p.get("quality") or {}
        return doc, {"source": label, "distance_m": round(float(p["distance"]), 1), "optimistic": bool(q.get("optimistic"))}

    def route(self, s, e, profile="car", via=None):
        from .car import RouterDown
        if not self.uses_seoul(s, e, profile) or via:
            doc = self.base.route(s, e, profile=profile, via=via) if via else self.base.route(s, e, profile=profile)
            return self._tag(doc, getattr(self.base, "source_id", None), getattr(self.base, "basis", None))
        self.seoul_calls += 1
        seoul_doc, seoul_c = self._try(self.seoul, s, e, "foot", "seoul_walk_network")
        base_doc, base_c = self._try(self.base, s, e, "foot", "base")
        cands = [c for c in (seoul_c, base_c)]
        got = [(c, d) for c, d in ((seoul_c, seoul_doc), (base_c, base_doc)) if d is not None]
        if not got:
            raise RouterDown("no_path: 서울시 도보 그래프·기존 보행망 모두 경로 없음 — "
                             + " / ".join(f"{c['source']}: {c.get('error')}" for c in cands))
        verified = [x for x in got if not x[0]["optimistic"]]
        pick_c, pick_doc = min(verified or got, key=lambda x: x[0]["distance_m"])
        if pick_c["source"] == "seoul_walk_network":
            pick_doc = self._tag(pick_doc, self.seoul.source_id, SEOUL_WALK_BASIS)
        else:
            pick_doc = self._tag(pick_doc, getattr(self.base, "source_id", None), getattr(self.base, "basis", None))
        pick_doc["paths"][0]["walk_candidates"] = {"chosen": pick_c["source"], "rule": "검증된 경로 중 짧은 것",
                                                   "candidates": cands}
        return pick_doc

    @staticmethod
    def _tag(doc, source_id, basis):
        for p in (doc or {}).get("paths") or []:
            if isinstance(p, dict):
                if source_id is not None:
                    p.setdefault("source_id", source_id)
                if basis is not None:
                    p.setdefault("basis", basis)
        return doc

def seoul_walk_dir():
    from .paths import PROCESSED
    return Path(PROCESSED) / "mobility" / "walk_graph_seoul_v2"


def wrap_with_seoul_walk(base, graph_dir=None):
    """서울시 도보 그래프를 쓸 수 있으면 감싼 라우터, 아니면 (base, 이유) — 걸음도 기존 라우터(이 기능 전과 같은 동작).

    ☆`[2026-10-13]` 경계 파일이 없을 때 앞 판은 멈췄다(FileNotFoundError) — 자료를 부분 복사한 시험 환경에서 이동 계산 전체가
    서지 않았다. 경계 없이는 「서울 안」을 가를 수 없으니 그래프를 쓰지 않고, 경고 로그로 드러낸다(거리를 만들지는 않는다)."""
    d = Path(graph_dir) if graph_dir else seoul_walk_dir()
    if not ((d / "nodes.jsonl.gz").exists() and (d / "edges.jsonl.gz").exists()):
        return base, f"서울시 도보 그래프 없음({d.name})"
    bpath = d / "seoul_boundary.geojson"
    if not bpath.exists():
        import logging
        logging.getLogger(__name__).warning("서울시 도보 그래프에 경계 파일이 없어 쓰지 않는다: %s", bpath)
        return base, f"서울시 도보 그래프 경계 파일 없음({d.name}/seoul_boundary.geojson)"
    from .graph_router import GraphRouter
    return SeoulWalkRouter(base, GraphRouter.shared(d), Boundary.from_geojson(bpath)), None
