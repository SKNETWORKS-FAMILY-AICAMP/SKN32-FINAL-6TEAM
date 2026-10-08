# modules/mobility/transfer_walk.py — 환승역 도보 거리표 조회 계층
# 소스: processed/mobility/transfer_walk_v1.json (서울교통공사 환승역거리, 145쌍·74역)
# 규칙: rules.transfer.walk_distance
#
# ★ 13개 역 일괄 +2분(large_station_addition_min)을 대체한다. 그 목록은 '큰 역'을 고른 것이지
#   '통로가 긴 역'을 고른 것이 아니었다 — 실제 거리는 7m ~ 355m 로 50배 흩어진다.
#   충무로 17m(0.3분)·사당 74m 는 가산할 이유가 없고, 서울역 323m(5.2분)·종로3가 312m 는 2분으로 모자란다.
#   인바운드 첫 환승인 홍대입구(02호선↔공항철도 355m, 5.7분, 전체 1위)는 아예 목록에 없었다.
#
# ★ 소스의 `src_min` 은 쓰지 않는다. 보행속도 1.2 m/s 기준으로 계산된 남의 값이다.
#   우리 기준선은 실측 1.04 m/s 이므로 **거리만 받아서 우리가 환산한다.**
import json
import math
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SPEED_MPS = 1.04          # rules.measured_baseline.kakao_walk_speed_mps
FALLBACK_QUANTILE = 0.9           # 거리표에 없는 환승의 대체값 — 측정된 환승 거리 분포의 상위 10%(보수적)


def ceil1(x):
    """소수 첫째 자리 **올림**. ☆`[2026-09-29 문제목록 #2]` 앞 판은 round(…, 1) 뒤 math.ceil 을 해
    61초(1.017분) → 1.0 → 1분으로 시간이 줄었다. 먼저 올리면 1.1 → 2분이다."""
    return math.ceil(x * 10 - 1e-9) / 10


@dataclass
class Walk:
    min: float                    # 도보 분. None 이면 근거없음
    grade: str                    # 추정 / 근거없음
    basis: str                    # pair / station_max / none
    reason: str
    distance_m: float = None
    checked_at: str = ""


class TransferWalk:
    def __init__(self, doc, speed_mps=DEFAULT_SPEED_MPS):
        self.doc = doc
        self.speed = speed_mps
        self.built_at = doc.get("built_at", "")
        self.source_id = doc.get("source_id") or "seoul_metro_transfer_distance"
        self.pairs = doc.get("pairs", {})
        self.stations = doc.get("stations", {})

    @classmethod
    def load(cls, path=None, speed_mps=DEFAULT_SPEED_MPS):
        if path is None:
            from .paths import PROCESSED
            path = PROCESSED / "mobility" / "transfer_walk_v1.json"
        p = Path(path)
        if not p.exists():
            return None                       # 소스가 아직 없으면 호출 쪽이 근거없음으로 처리한다
        return cls(json.loads(p.read_text(encoding="utf-8")), speed_mps)

    def _min(self, distance_m):
        return ceil1(distance_m / self.speed / 60)

    def network_fallback(self):
        """거리표에 없는 환승의 **대체 출처** — 측정된 환승 거리(쌍) 분포의 상위 10% 값.

        ☆`[2026-09-29 문제목록 #1]` 앞 판은 거리표에 없으면 0분(큰 역만 +2분)으로 채우고 성립시켰다 —
          모르는 값을 지어낸 것이다(결정 15). 이 값은 지어낸 수가 아니라 같은 거리표의 실측 분포에서 나온다.
          쌍이 하나도 없으면 None — 부르는 쪽이 근거없음(판정 불가)으로 올린다.
        """
        if getattr(self, "_nf", False) is not False:
            return self._nf                                  # 거리표는 적재 뒤 바뀌지 않는다 — 한 번만 센다
        ds = sorted(r["distance_m"] for r in self.pairs.values() if r.get("distance_m") is not None)
        if not ds:
            self._nf = None
            return None
        d = ds[min(len(ds) - 1, math.ceil(FALLBACK_QUANTILE * len(ds)) - 1)]
        self._nf = Walk(self._min(d), "추정", "network_p90",
                        f"환승 거리표에 없는 환승 — 측정된 {len(ds)}쌍의 상위 10% 거리 {d:g}m 로 보수적으로 잡았다",
                        d, self.built_at)
        return self._nf

    def lookup(self, station, from_line, to_line):
        """(역, 타던 노선, 갈아탈 노선) → 도보 분. 못 찾으면 사다리를 내려간다."""
        rec = self.pairs.get(f"{station}|{from_line}|{to_line}") \
            or self.pairs.get(f"{station}|{to_line}|{from_line}")
        if rec and rec.get("distance_m") is not None:
            d = rec["distance_m"]
            return Walk(self._min(d), "추정", "pair",
                        f"{station} {from_line}↔{to_line} {d:g}m ÷ {self.speed} m/s",
                        d, self.built_at)
        st = self.stations.get(station)
        if st and st.get("distance_m") is not None:
            d = st["distance_m"]
            return Walk(self._min(d), "추정", "station_max",
                        f"{station} 의 노선쌍({from_line}↔{to_line})이 거리표에 없어 "
                        f"그 역 최대값 {d:g}m({st.get('worst_pair','')})로 보수적으로 잡았다",
                        d, self.built_at)
        return Walk(None, "근거없음", "none",
                    f"{station} {from_line}↔{to_line} 환승 거리가 거리표에 없다 "
                    f"(서울교통공사 관할 밖 — 코레일·공항철도끼리의 환승 등)",
                    None, self.built_at)
