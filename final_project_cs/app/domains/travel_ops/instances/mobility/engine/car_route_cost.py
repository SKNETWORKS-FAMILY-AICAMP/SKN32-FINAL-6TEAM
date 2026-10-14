"""자동차 길 선택 비용을 TOPIS 시간대 속도로 매긴다 (2026-10-13).

☆왜. 앞 판은 길을 도로급 고정 속도(graph_router.HW_KMH · OSM maxspeed)로 고르고, 고른 뒤에만 TOPIS 로 소요를 쟀다.
  막히는 짧은 길을 고르기 쉬워 택시 미터가 체계적으로 낮게 나왔다 — 카카오 공개 비교 193쌍에서 제품 경로 거리 중앙값이
  카카오의 0.93배, 미터 추정이 낮은 쌍 165/193. 길을 고를 때도 소요 계산(CarGraph.compute)과 **같은 속도 규칙**을 쓰면
  학습 153쌍 평균 절대오차 2,026→1,698원, 계산 전 고정한 검증 40쌍 1,812→1,450원, 새로 고정한 카카오 웹 12쌍 1,583→767원이었다
  (records/reports/2026-10-13_taxi_route_cost/REPORT.md).

규칙
  · 간선 속도 = TOPIS 링크의 (요일형, 시) 평균 속도 → 없으면 도로급 계수(topis_class_factor) → 없으면 골목 정적 속도(DEFAULT_KMH).
    CarGraph.compute 의 순서·값 그대로다. 간선 → 링크 대응은 car_edge_link_v1(datasets/mobility/scripts/build_car_edge_topis_link_v1.py).
  · 양방향 링크가 다 있으면 느린 쪽 속도(검증한 규칙 그대로 — 방향별 비용은 아직 검증 안 함).
  · 출발 시각의 (요일형, 시) 하나로 길 전체를 매긴다. 시간대를 넘는 소요는 고른 뒤 compute 가 시각별로 다시 잰다.
  · 대응표의 입력 도로 그래프 md5 가 지금 라우터 그래프와 다르면 쓰지 않는다(이유를 근거에 남기고 고정 속도로 고른다 — 조용히 바꾸지 않는다).
"""
from __future__ import annotations

import array
import gzip
import hashlib
import json
import logging
import threading
from collections import OrderedDict
from pathlib import Path

from .car import CLASS_MAP, DEFAULT_KMH

log = logging.getLogger(__name__)
CACHE_BUCKETS = 6                    # (요일형, 시) 가중치 배열 보관 수 — 하나에 약 3MB
VERSION = "car_edge_link_v1"


class TopisRouteCost:
    def __init__(self, graph, router, link_dir):
        self.g, self.router, self.dir = graph, router, Path(link_dir)
        man = json.loads((self.dir / "MANIFEST.json").read_text(encoding="utf-8"))
        router._load()
        want = (man.get("inputs") or {}).get("road_graph_v2/edges.jsonl.gz")
        have = hashlib.md5((Path(router.dir) / "edges.jsonl.gz").read_bytes()).hexdigest()
        if want != have:
            raise ValueError(f"간선-링크 대응표의 도로 그래프({want})가 지금 라우터 그래프({have})와 다르다")
        table = {}
        with gzip.open(self.dir / "edge_link.jsonl.gz", "rt", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                table[(r["u"], r["v"], r["way"])] = (r["lf"], r["lb"])
        inv = {v: k for k, v in router.nid.items()}
        self.elink = [table.get((inv[router.eu[e]], inv[router.ev[e]], router.eway[e])) for e in range(len(router.eu))]
        self.version = man.get("version") or VERSION
        self._w = OrderedDict()
        self._lock = threading.Lock()

    @classmethod
    def try_load(cls, graph, router):
        """(비용 객체 또는 None, 안 쓰는 이유 또는 None). 라우터가 로컬 그래프가 아니면 쓰지 않는다."""
        if graph is None or not hasattr(router, "_adjacency") or not getattr(router, "dir", None):
            return None, "로컬 도로 그래프 라우터가 아니다"
        d = Path(graph.dir).parent / VERSION
        if not (d / "edge_link.jsonl.gz").exists():
            return None, f"간선-링크 대응표 없음({d.name})"
        try:
            return cls(graph, router, d), None
        except (OSError, ValueError, KeyError) as ex:
            log.warning("자동차 길 선택에 TOPIS 속도를 쓰지 않는다: %s", ex)
            return None, f"대응표 사용 불가: {type(ex).__name__}: {str(ex)[:120]}"

    def _speed(self, link, hw, dtp, h):
        v = self.g.prof.get((link, dtp, h)) if link else None
        if v is not None:
            return v
        if hw in CLASS_MAP:
            return self.g.cf[CLASS_MAP[hw]]["mean_kmh"][dtp][h]
        return DEFAULT_KMH.get(hw, 20)

    def edge_seconds(self, e, bucket):
        dtp, h = bucket
        r = self.router
        hw = r.hw_name[r.ehw[e]]
        lf, lb = self.elink[e] or (None, None)
        if lf and lb:
            v = min(self._speed(lf, hw, dtp, h), self._speed(lb, hw, dtp, h))
        else:
            v = self._speed(lf or lb, hw, dtp, h)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not v > 0:
            raise ValueError(f"도로 속도가 양수가 아니다: {v!r}")
        return r.elen[e] / (v / 3.6)

    def weights(self, bucket):
        """라우터 `_adjacency('car')` 의 호 순서와 같은 가중치 배열(초)."""
        with self._lock:
            got = self._w.get(bucket)
            if got is not None:
                self._w.move_to_end(bucket)
                return got
        _deg, _to, pe, _w = self.router._adjacency("car")
        sec = {}
        out = array.array("f", [0.0]) * len(pe)
        for k, code in enumerate(pe):
            e = code >> 1
            s = sec.get(e)
            if s is None:
                s = sec[e] = self.edge_seconds(e, bucket)
            out[k] = s
        with self._lock:
            self._w[bucket] = out
            while len(self._w) > CACHE_BUCKETS:
                self._w.popitem(last=False)
        return out

    def at(self, depart):
        """출발 시각에 묶인 비용 — GraphRouter.route(car_cost=…) 에 넘긴다."""
        return BucketCost(self, (self.g.daytype(depart), depart.hour))


class BucketCost:
    def __init__(self, rc, bucket):
        self.rc, self.bucket = rc, bucket

    def cost(self, e):
        return self.rc.edge_seconds(e, self.bucket)

    def weights(self):
        return self.rc.weights(self.bucket)

    def evidence(self):
        return {"kind": "topis_profile", "day_type": self.bucket[0], "hour": self.bucket[1], "edge_link": self.rc.version}
