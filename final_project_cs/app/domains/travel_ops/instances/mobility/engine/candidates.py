# modules/mobility/candidates.py — k-후보 생성기 (규칙 v0.5 · 20번 방 · 2026-09-20)
#
# 역 순서 777간선(line_station_order_v1) 위에서 **기준별 대표안**을 만든다.
#   최단     : Σ간선 소요 + Σ환승 비용(도보 + 길찾기 + 대기 추정)  이 가장 작은 길
#   최소환승 : 환승 횟수 → 그 다음 시간
#   최소도보 : 환승 도보 분 → 그 다음 시간
# 최단을 먼저 구하고, 최소환승·최소도보는 **최단 × 허용_소요_배수 안에서** 파레토 라벨 탐색으로 찾는다.
# (도보만 줄이려고 열 배를 도는 길은 대표안이 아니다 — rules candidates.허용_소요_배수)
#
# ★ 이 모듈은 **판정하지 않는다.** 후보의 소요·환승·도보는 생성기의 추정치일 뿐이고,
#   시각은 verify_time.py 가 시간표로 확정한다(각 후보를 같은 판정기에 넣는다).
# ★ 순위를 매기지 않는다 — 후보 목록의 순서는 규칙 candidates.기준 의 순서지 우열이 아니다
#   (rules alternatives.순위_미부여). 어느 후보가 낫다고 말하는 필드는 없다.
# ★ 이슈(운행중단 등)를 모른다 — 대안 열거와 같은 원칙으로 판정기가 거른다.
# ★ 환승은 **같은 역명이 두 노선에 있으면** 가능한 것으로 본다 — 단 규칙 station_names.환승_제외_역명(양평 · 신촌)은
#   같은 이름의 **다른 역**이라 잇지 않는다(55 ② · 2026-09-28). 종전 주석(「같은 역명 좌표 차 전부 400 m 안」)은 역명으로
#   좌표를 붙인 판에서 잰 것이라 동명이역을 못 가렸다 — 57 재생성 뒤 양평 53,610 m · 신촌 702 m(54 발견 · 원덕→영등포구청).
#   그 역명이 출발·도착이면 노선(origin_lines · dest_lines)을 같이 받아야 후보를 만든다 — 안 받으면 None(한쪽을 조용히 안 집는다).
import heapq, collections
from dataclasses import dataclass, field

CRITERIA = ("최단", "최소환승", "최소도보")


@dataclass
class Candidate:
    legs: list                      # [{"line","from","to"}]  — 판정기 입력 그대로
    criteria: list                  # 이 후보가 대표하는 기준들(중복 제거 결과)
    est_min: float                  # 생성기 추정 총소요(분) — 판정기가 확정하기 전 값
    transfers: int
    walk_min: float                 # 환승 도보 분 합(길찾기 제외)
    grade: str                      # 추정 / 근거없음(소요 없는 간선을 대체값으로 메운 경우)
    fallback_edges: list = field(default_factory=list)   # 대체값을 쓴 간선
    path: list = field(default_factory=list)              # [(line, station)] — 설명용

    def key(self):
        return tuple((l["line"], l["from"], l["to"]) for l in self.legs)


class CandidateGraph:
    """(노선, 역) 노드 그래프. 간선 = 같은 노선 인접역(소요) · 같은 역명의 노선 갈아타기(환승 비용)."""

    def __init__(self, lo, tw, rules, first_visit=True):
        self.lo, self.tw, self.R = lo, tw, rules
        C = rules["candidates"]
        self.edge_fallback = C["간선_소요_대체_분"]["value"]
        self.transfer_wait = C["환승_대기_추정_분"]["value"]
        self.walk_unknown = C["환승_도보_미상_분"]["value"]
        self.wayfinding = rules["transfer"]["wayfinding_addition_min"]["value"] if first_visit else 0
        self.large_add = rules["transfer"]["large_station_addition_min"]["value"]
        self.large = set(rules["transfer"]["large_station_addition_min"]["stations"])
        self.speed = rules["measured_baseline"]["kakao_walk_speed_mps"]["value"]
        self.no_transfer = set(rules["station_names"]["환승_제외_역명"]["value"])   # 55 ② — 같은 이름의 다른 역
        # 노선 간선
        self.adj = collections.defaultdict(list)     # (line, st) → [((line, st2), ride_min, fallback)]
        self.lines_of = collections.defaultdict(set)
        for ln, L in lo.doc["lines"].items():
            for s in L["stations"]:
                self.lines_of[s["station_nm"]].add(ln)
            for e in L["edges"]:
                t = e.get("travel_min")
                fb = t is None
                w = self.edge_fallback if fb else t
                self.adj[(ln, e["a"])].append(((ln, e["b"]), w, fb))
                self.adj[(ln, e["b"])].append(((ln, e["a"]), w, fb))

    def transfer_walk_min(self, station, from_line, to_line):
        """환승 도보 분(길찾기 제외). 거리표 → 역 최대값 → 대형역 고정값 → **미상값**.

        ★ 판정기의 사다리와 마지막 단만 다르다. 판정기는 거리표에 없으면 0분(근거없음)으로 두지만,
          생성기가 0으로 치면 최소도보 기준이 거리표 밖 역으로 몰린다(rules candidates.환승_도보_미상_분).
        """
        if self.tw is not None:
            w = self.tw.lookup(station, from_line, to_line)
            if w is not None and w.min is not None:
                return w.min
            # ☆`[2026-09-29 문제목록 #8]` 거리표에 없는 환승은 판정기와 **같은 대체 출처**(측정 분포 상위 10%)를 쓴다.
            #   앞 판은 근거없음 고정값(3분 · 대형역 2분)을 써서 생성기와 판정기가 다른 값을 봤다.
            nf = self.tw.network_fallback()
            if nf is not None:
                return nf.min
        return self.large_add if station in self.large else self.walk_unknown

    def transfer_cost(self, station, from_line, to_line):
        walk = self.transfer_walk_min(station, from_line, to_line)
        return walk, walk + self.wayfinding + self.transfer_wait

    # ── 라벨 설정 탐색 (기준별 목적 쌍 · 시간 상한) ──
    @staticmethod
    def _obj(criterion, time, transfers, walk):
        """기준별 (1차 목적, 시간). 1차 목적이 같으면 시간이 짧은 쪽."""
        if criterion == "최단":
            return (time, time)
        if criterion == "최소환승":
            return (transfers, time)
        if criterion == "최소도보":
            return (round(walk, 3), time)
        raise ValueError(criterion)

    def search(self, origin, dest, criterion, max_transfers=None, time_bound=None, origin_lines=None, dest_lines=None,
               avoid_lines=None):
        """origin → dest 대표안 하나. 상태 = ((line, station), 환승 횟수).

        **파레토 라벨 설정** — 상태마다 (1차 목적, 시간) 비지배 라벨을 여럿 둔다. 최소환승·최소도보는
        시간 상한(time_bound = 최단 추정 × candidates.허용_소요_배수) 안에서만 찾는다.
        ★ 사전식 다익스트라(1차 목적 우선)로 하면 최소도보가 「도보 0 인 환승역」(도봉산·까치산)으로
          몰려 최단의 10배짜리 길이 나온다(2026-09-20 무작위 3,000쌍 중 1,304쌍). 시간 상한을 걸면
          상태당 라벨 하나로는 최적성이 깨진다 — 도보는 작지만 시간이 큰 라벨이 뒤에서 상한에 막힌다.
          그래서 라벨을 여럿 둔다. 그래프가 작아(노드 ~900 · 환승 ≤3) 비용은 무시할 만하다.
        ★ 환승 상한(limits.transfers)도 여기서 지킨다 — 넘는 후보는 판정기가 탈락시키므로 대표안이 못 된다.
        ☆`[2026-10-01 87]` avoid_lines — 이 노선은 타지 않는다(혼합 후보 생성기가 사고로 **운행 중단**인 노선을 피할 때만 ·
          기본 None = 앞 판과 같다). 판정은 여전히 판정기가 한다 — 피하지 않아도 판정기가 떨어뜨리지만, 혼합 후보는 끊는
          지점마다 지하철 잔여 소요 추정으로 고르므로 막힌 노선으로 잰 추정이 고르는 순서를 흐리지 않게 한다.
        """
        if origin not in self.lines_of or dest not in self.lines_of:
            return None
        avoid = frozenset(avoid_lines or ())
        # 55 ② — 환승 제외 역명(동명이역)이 끝점이면 노선이 있어야 한다. 노선은 그 역명에 실제로 있는 것만 쓴다.
        o_lines = (self.lines_of[origin] & set(origin_lines) if origin_lines else self.lines_of[origin]) - avoid
        d_lines = (self.lines_of[dest] & set(dest_lines) if dest_lines else self.lines_of[dest]) - avoid
        # 같은 역이면 후보가 없다 — 단 동명이역(경의선 양평 → 5호선 양평)은 노선군이 겹치지 않으면 다른 역이다(55 GPT #2)
        if origin == dest and (origin not in self.no_transfer or o_lines & d_lines):
            return None
        if ((origin in self.no_transfer and not origin_lines) or (dest in self.no_transfer and not dest_lines)
                or not o_lines or not d_lines):
            return None
        cap = max_transfers if max_transfers is not None else 99
        bound = time_bound if time_bound is not None else float("inf")
        labels = collections.defaultdict(list)     # state → [(obj, time, tr, walk, fbs, prev_state, prev_label_idx)]
        pq, tick = [], 0

        def push(state, t, tr, wk, fbs, prev):
            nonlocal tick
            if t > bound:
                return
            obj = self._obj(criterion, t, tr, wk)
            L = labels[state]
            for o, *_ in L:                      # 지배당하면 버린다
                if o[0] <= obj[0] and o[1] <= obj[1]:
                    return
            L[:] = [x for x in L if not (obj[0] <= x[0][0] and obj[1] <= x[0][1])]   # 내가 지배하는 것 제거
            L.append((obj, t, tr, wk, fbs, prev))
            tick += 1
            heapq.heappush(pq, (obj, tick, state, len(L) - 1, obj))

        for ln in sorted(o_lines):
            push(((ln, origin), 0), 0.0, 0, 0.0, [], None)
        goal = None
        while pq:
            obj, _, state, idx, _o = heapq.heappop(pq)
            L = labels[state]
            if idx >= len(L) or L[idx][0] != obj:          # 지배로 지워진 라벨
                cur = next((x for x in L if x[0] == obj), None)
                if cur is None:
                    continue
            else:
                cur = L[idx]
            (line, st), tr = state
            if st == dest and line in d_lines:
                goal = (state, cur)
                break
            _, t, _tr, wk, fbs, _prev = cur
            for v, w, fb in self.adj[(line, st)]:          # 같은 노선 다음 역
                push((v, tr), t + w, tr, wk, fbs + ([f"{line} {st}–{v[1]}"] if fb else []), (state, obj))
            # 환승 — 같은 역명의 다른 노선. 출발역·제외 역명에서는 안 갈아탄다(출발역에서 갈아타면 그 노선에서 출발한 것과 같다 ·
            #   동명이역 출발은 no_transfer 라 어차피 막힌다 — 55 GPT #2 점검)
            if st != origin and tr < cap and st not in self.no_transfer:
                for ln in self.lines_of[st]:
                    if ln == line or ln in avoid:
                        continue
                    walk, cost = self.transfer_cost(st, line, ln)
                    push(((ln, st), tr + 1), t + cost, tr + 1, wk + walk, fbs, (state, obj))
        if goal is None:
            return None
        # 경로 복원 — (state, obj) 를 따라 올라간다
        path, cur = [], goal
        while cur is not None:
            state, lab = cur
            path.append(state[0])
            prev = lab[5]
            if prev is None:
                break
            pstate, pobj = prev
            plab = next(x for x in labels[pstate] if x[0] == pobj)
            cur = (pstate, plab)
        path.reverse()
        _, t, tr, wk, fbs, _ = goal[1]
        return Candidate(self._legs(path), [criterion], round(t, 1), tr, round(wk, 1),
                         "근거없음" if fbs else "추정", fbs, path)

    @staticmethod
    def _legs(path):
        legs, cur_line, start = [], path[0][0], path[0][1]
        last = path[0][1]
        for ln, st in path[1:]:
            if ln != cur_line:                      # 환승 노드(같은 역명)
                legs.append({"line": cur_line, "from": start, "to": last})
                cur_line, start = ln, st
            last = st
        legs.append({"line": cur_line, "from": start, "to": last})
        return [l for l in legs if l["from"] != l["to"]]

    def candidates(self, origin, dest, criteria=CRITERIA, max_transfers=None, ratio=None,
                   origin_lines=None, dest_lines=None):
        """기준별 대표안. 최단을 먼저 구해 시간 상한(× ratio)을 정하고, 나머지 기준은 그 안에서 찾는다.
        같은 구간열이면 하나로 합치고 기준을 모은다. **순위 없음.**"""
        ratio = ratio if ratio is not None else self.R["candidates"]["허용_소요_배수"]["value"]
        out, seen = [], {}
        kw = {"origin_lines": origin_lines, "dest_lines": dest_lines}
        shortest = self.search(origin, dest, "최단", max_transfers, **kw)
        if shortest is None:
            return out
        bound = shortest.est_min * ratio
        for c in criteria:
            cand = shortest if c == "최단" else self.search(origin, dest, c, max_transfers, bound, **kw)
            if cand is None:
                continue
            k = cand.key()
            if k in seen:
                if c not in seen[k].criteria:
                    seen[k].criteria.append(c)
                continue
            cand.criteria = [c]
            seen[k] = cand
            out.append(cand)
        return out


# ── 지하철+버스 혼합 후보(환승 1회) · 87번 방 2026-10-01 ─────────────────────────────
#
# 두 모양만 만든다(12 전달 §2 · 87):
#   A. 버스 → 지하철 — 출발점 근처 정류장(정류장_반경_m)에서 타는 노선이 **역 앞**(정류장↔그 역 가장 가까운 출구 직선
#      ≤ 정류장_반경_m)을 지나면 거기서 내려 그 역에서 목적지 역까지 지하철(이 파일의 최단 탐색).
#   B. 지하철 → 버스 — 출발 역에서 지하철로 **역 앞 정류장이 있는 역**까지 간 뒤, 그 정류장에서 목적지 근처 정류장까지
#      한 노선 버스.
# 안 하는 것: 환승 2회 이상 혼합(버스·지하철을 두 번 이상 바꾸기) · 버스→버스 · 통합 그래프 탐색기(12 §3).
# 지하철 구간 안의 지하철↔지하철 환승은 있을 수 있다 — 총 환승(버스↔지하철 1 + 지하철 안) ≤ 환승 상한(limits.transfers).
#
# ★ 이 생성기도 **판정하지 않는다**(위 다목적 후보와 같다). 끊는 지점 고르기·순서만 정하고, 시각·성립·환승 도보·근접 상한은
#   판정기(verify_case · 19 환승 도보 · 39 best/worst)가 그대로 본다. est_min 은 고르는 순서용 추정이다.
# ★ 끊는 지점은 **노선당 최대 N**(규칙 candidates.혼합_끊는_지점_최대 · 변경안) — 출발에서 가까운 순이 아니라 **지하철 쪽
#   소요 추정이 짧은 순**(A = 끊는 역 → 목적지 역 · B = 출발 역 → 끊는 역). 같은 노선이 역 앞을 열 번 지나도 셋만 본다.
# ★ 공항버스: A 에서만, **공항 정류장에서 타는** 노선 단위로(공항 → 시내). 공항으로 가는 공항버스는 만들지 않는다 — 도착점이
#   공항인 B(공항행)는 skipped_airport 에 노선만 적어 부르는 쪽이 no_data 로 밝힌다(37 정본 공항행 시각 목록이 판정기에 아직 없음 ·
#   12 §2 · 37). 시내 정류장에서 타고 내리는 공항버스 구간(A 의 공항 아닌 승차 · B 의 시내 하차)은 조용히 뺀다.
# ★ 가상 정류장(이름에 「(가상)」 — 노선 형상용 점 · 영종대교(가상) 등)은 끊는 지점이 아니다.
#: 혼합 후보 상한 — 규칙 candidates.혼합_최대 **변경안** 값(27 규칙 32 · 규칙 파일은 모아서 한 번에). 규칙에 들어가면 규칙 값.
MIX_MAX_PROPOSED = 3
#: 노선당 끊는 지점 상한 — 규칙 candidates.혼합_끊는_지점_최대 **변경안** 값.
MIX_CUTS_PER_ROUTE_PROPOSED = 3
MIX_SHAPES = ("A", "B")
AIRPORT_TYPE = "공항"

# ☆`[2026-10-06 구글 대조]` 버스 → 버스 환승 후보(모양 C)의 규칙 변경안 — 우리가 고른 값이다(측정으로 나온 값 아님).
#   구글은 17구간 중 3구간(북촌→석관동 · 망원시장→연남동 · 성북동→서촌)에서 버스+버스를 골랐고, 우리는 그 모양을 못 만들어
#   +9~12분 느리게 나왔다(앞 둘). 판정기는 버스↔버스 환승을 이미 판정한다(v0.9.2 `_bus_bus_walk`) — 생성기만 비어 있었다.
BUS_LINK_MAX_M_PROPOSED = 250         # 갈아탈 두 정류장 직선 상한(m) — 최종 상한은 판정기가 limits.walk_m 로 본다. 같은 정류장·길 건너 맞은편 수준만 후보로 올린다
BUS_FROM_ROUTES_MAX = 12              # 출발 쪽 노선 수 상한(가까운 순) — 환승점 탐색 비용을 묶는다
BUS_BUS_MAX_PROPOSED = 6              # 모양 C 후보로 내놓는 수(추정 소요 순) — 판정 개수 상한(MIX_VERIFY_MAX)은 부르는 쪽이 건다
BUS_ACCESS_REACH_M_PROPOSED = 900     # 모양 C 의 승·하차 정류장을 찾는 반경(m) — 정류장 반경(500)보다 넓다: 구글은 북촌→석관동에서 874 m 를 걸어 탔다. 도보 상한(limits.walk_m)은 따로 넘지 않는다
BUS_DETOUR_SLACK_M_PROPOSED = 1500    # 환승점이 도착점에서 출발점보다 이만큼까지 멀어져도 본다(m) — 마을버스·순환 노선은 일단 멀어졌다가 큰길 노선으로 갈아탄다(성북동→서촌)
_VIRTUAL = "(가상)"


def mix_rule(rules, key, proposed):
    """규칙 candidates.<key> — 칸이 없으면 변경안 값(proposed). 1 이상 정수가 아니면 ValueError(85 _station_k 와 같은 규칙)."""
    n = ((rules or {}).get("candidates") or {}).get(key)
    k = n["value"] if n and n.get("value") is not None else proposed
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError(f"candidates.{key} 는 1 이상 정수 — 받은 값 {k!r}")
    return k


def is_airport_stop(row):
    return "공항" in str(row.get("station_nm") or "")


@dataclass
class MixedCandidate:
    shape: str                      # "A"(버스→지하철) / "B"(지하철→버스) / "C"(버스→버스 · 2026-10-06)
    legs: list                      # 판정기 입력 그대로 — 버스 {"mode":"bus","route","from","to"} · 지하철 {"line","from","to"}
    est_min: float                  # 고르는 순서용 추정(접근 도보 + 대기 + 승차 + 환승 + 지하철 + 이탈 도보) — 판정 아님
    transfers: int                  # 버스↔지하철 1 + 지하철 안 환승
    walk_in_m: float                # 출발점 → 첫 승차 지점 직선(A = 정류장 · B = 부르는 쪽이 준 출발 역 도보)
    walk_out_m: float               # 마지막 하차 지점 → 도착점 직선(A = 부르는 쪽이 준 도착 역 도보 · B = 정류장)
    link_m: float                   # 정류장 ↔ 끊는 역 가장 가까운 출구(없으면 역 좌표) 직선
    route_nm: str
    cut_station: str                # 끊는 역(A = 내려서 타는 역 · B = 내려서 버스로 가는 역)
    end_station: str                # 지하철 쪽 다른 끝(A = 도착 역 · B = 출발 역)
    sub_walk_min: float             # 지하철 안 환승 도보 분(생성기 값)
    grade: str                      # 추정 / 근거없음(지하철 쪽이 대체 간선을 밟음)
    fallback_edges: list = field(default_factory=list)

    def key(self):
        return tuple((l.get("route") or l.get("line"), l["from"], l["to"]) for l in self.legs)


class _PointIndex:
    """좌표 목록의 근처 찾기 — numpy 가 있으면 한 번에, 없으면 파이썬 반복(같은 식 · geo.meters 평면 근사)."""

    def __init__(self, items, lat_of, lng_of):
        self.items = [x for x in items if lat_of(x) is not None and lng_of(x) is not None]
        try:
            import numpy as np
            self.np = np
            self.lat = np.array([float(lat_of(x)) for x in self.items])
            self.lng = np.array([float(lng_of(x)) for x in self.items])
        except Exception:          # pragma: no cover — numpy 는 팀 목록에 있다
            self.np = None
            self._ll = [(float(lat_of(x)), float(lng_of(x))) for x in self.items]

    def near(self, lat, lng, within_m):
        """(거리 m, item) 가까운 순."""
        if not self.items:
            return []
        if self.np is not None:
            np = self.np
            dy = (self.lat - lat) * 111_320
            dx = (self.lng - lng) * 111_320 * np.cos(np.radians((self.lat + lat) / 2))
            d = np.hypot(dx, dy)
            idx = np.nonzero(d <= within_m)[0]
            out = [(float(d[i]), self.items[i]) for i in idx]
        else:
            import math
            out = []
            for (a, b), x in zip(self._ll, self.items):
                dy = (a - lat) * 111_320
                dx = (b - lng) * 111_320 * math.cos(math.radians((a + lat) / 2))
                dd = math.hypot(dx, dy)
                if dd <= within_m:
                    out.append((dd, x))
        out.sort(key=lambda t: t[0])
        return out


import weakref as _weakref
_IDX = _weakref.WeakKeyDictionary()       # 정류장·역 표 객체 → 색인(표가 같으면 요청마다 다시 안 만든다)


def _stop_index(bus):
    ix = _IDX.get(bus)
    if ix is None:
        rows = [s for rs in bus.stops.values() for s in rs]
        ix = _IDX[bus] = _PointIndex(rows, lambda s: s.get("lat"), lambda s: s.get("lng"))
    return ix


def _station_index(sc):
    """역 좌표표의 **노선 레코드 전부**(GPT 87 #6 — 물리적 역의 대표 하나만 두면 대표 좌표에서 먼 출구를 놓친다). 부르는 쪽이
    물리적 역(phys_key)으로 묶는다."""
    ix = _IDX.get(sc)
    if ix is None:
        recs = [v for v in sc.by_key.values() if v.get("lat") is not None]
        ix = _IDX[sc] = _PointIndex(recs, lambda v: v.get("lat"), lambda v: v.get("lng"))
    return ix


def exit_reach_m(sc, ex):
    """출구 ↔ 그 역 레코드 좌표의 가장 먼 거리(m) — 역 좌표로 「정류장 근처 역」을 고를 때 넉넉히 볼 여유(GPT 87 #6 · 근거 없는
    300 m 고정값 대신 출구표에서 잰다). 출구마다 같은 역명 레코드 중 가장 가까운 것까지의 거리, 그 최대. 출구표가 없으면 0."""
    if ex is None or sc is None:
        return 0.0
    import math
    by_nm = collections.defaultdict(list)
    for v in sc.by_key.values():
        if v.get("lat") is not None:
            by_nm[v["station_nm"]].append(v)
    reach = 0.0
    for nm, exits in (getattr(ex, "exits", None) or {}).items():
        recs = by_nm.get(nm)
        if not recs:
            continue
        for e in exits:
            d = min(math.hypot((r["lat"] - e["lat"]) * 111_320,
                               (r["lng"] - e["lng"]) * 111_320 * math.cos(math.radians((r["lat"] + e["lat"]) / 2)))
                    for r in recs)
            reach = max(reach, d)
    return reach


_NEAR_ST = _weakref.WeakKeyDictionary()   # 역 좌표표 객체 → {(near_m, 정류장 키): [(출구 직선 m, 역 레코드)]}


class MixedGenerator:
    """혼합 후보 생성기(A·B). 부르는 쪽(판정기 verify_multi · plan.Planner)이 끝점과 역 목록을 주고, 후보를 판정기에 넣는다.

    인자
      cg            CandidateGraph(지하철 최단 탐색)        bus · sc · ex   버스 노선·정류장 / 역 좌표 / 역 출구
      radius_m      출발·도착점 근처 정류장 반경(alternatives.정류장_반경_m · 버스 직행과 같은 값)
      near_m        정류장이 「역 앞」인 거리(정류장 ↔ 그 역 가장 가까운 출구 직선 · 같은 규칙 값 — 「같은 지점으로 볼 수 있는
                    거리」. 도보 상한 limits.walk_m 은 판정기가 정류장↔역 환승에서 따로 본다)
      cuts          노선당 끊는 지점 상한 N          tlim   총 환승 상한(limits.transfers · 동행별)
      excluded      버스 유형 제외(bus.route_type_제외)
      ride_min      (route, 타는 행, 내리는 행) → 승차 분 추정 또는 None(속도 근거 없음 → 그 노선은 안 쓴다)
      wayfinding    환승 길찾기 가산 분 · walk_speed · detour  도보 분 식(직선 × 우회 ÷ 속도)
      avoid_lines   사고로 운행 중단인 노선(지하철 탐색에서 피함)   skip_at  {(노선, 역)} 사고로 서지 않는 역(끊는 역 노선에서 뺌)

    순서: ① 끝점 근처 정류장의 노선마다 역 앞 정류장(끊는 지점)을 모은다 ② 지하철 쪽 소요는 **한 번의 최단 거리 표**(목적지
    역에서 거꾸로 · 출발 역에서 앞으로 — 같은 그래프 비용)로 끊는 역마다 잰다 ③ 노선마다 지하철 쪽이 짧은 N 개 ④ 전체를 추정
    소요 순으로. 지하철 구간열(legs)은 **부르는 쪽이 판정에 넣을 후보만** materialize() 로 채운다(그때 환승 상한도 본다).
    """

    def __init__(self, cg, bus, sc, ex, *, radius_m, near_m, cuts, tlim, excluded=(), ride_min=None,
                 wayfinding=0, walk_speed=1.04, detour=1.4, avoid_lines=(), skip_at=()):
        self.cg, self.bus, self.sc, self.ex = cg, bus, sc, ex
        self.radius_m, self.near_m, self.cuts, self.tlim = radius_m, near_m, cuts, tlim
        self.excluded = set(excluded or ())
        self.ride_min = ride_min
        self.wayfinding, self.walk_speed, self.detour = wayfinding, walk_speed, detour
        self.avoid = frozenset(avoid_lines or ())
        self.skip_at = frozenset(skip_at or ())
        self.skipped_airport = []          # 공항행 공항버스(만들지 않음 · 부르는 쪽이 no_data 로 밝힌다)
        self.no_cut = []                   # 역 앞을 한 번도 안 지나 끊지 못한 노선(근접 밖)

    # ── 조각 ──
    def _walk_min(self, m):
        return (m or 0) * self.detour / self.walk_speed / 60

    def _lines(self, rec):
        """역 레코드 → 지하철 탐색에 쓸 노선(동명이역은 그 물리적 역 노선만) · 그 역에서 서지 않는 노선 · 운행 중단 노선은 뺀다."""
        nm = rec["station_nm"]
        ls = set(self.sc.group_lines(rec)) - {None}
        if not ls:
            ls = {rec.get("line")}
        return {l for l in ls if (l, nm) not in self.skip_at and l not in self.avoid and l in self.cg.lines_of.get(nm, ())}

    def _dist(self, seeds):
        """지하철 최단 거리 표 — seeds = [(역명, 노선 집합, 시작 비용 분)]. {(노선, 역): 분}. 비용은 탐색(search)과 같다
        (간선 소요 · 환승 = 도보 + 길찾기 + 대기 추정). 간선·환승 비용이 방향과 무관해(환승 도보 거리표만 방향별 · 차이 작음)
        「목적지에서 거꾸로」 잰 값을 「끊는 역 → 목적지」 추정으로 쓴다 — 고르는 순서용이고 실제 구간열은 materialize 가 다시 찾는다."""
        cg, dist, pq, tick = self.cg, {}, [], 0
        for nm, lines, c0 in seeds:
            for ln in lines:
                heapq.heappush(pq, (c0, tick, (ln, nm)))
                tick += 1
        while pq:
            d, _, node = heapq.heappop(pq)
            if node in dist:
                continue
            dist[node] = d
            line, st = node
            for v, w, _fb in cg.adj[node]:
                if v not in dist:
                    tick += 1
                    heapq.heappush(pq, (d + w, tick, v))
            if st not in cg.no_transfer:
                for ln in cg.lines_of[st]:
                    if ln == line or ln in self.avoid or (ln, st) in dist:
                        continue
                    tick += 1
                    heapq.heappush(pq, (d + cg.transfer_cost(st, line, ln)[1], tick, (ln, st)))
        return dist

    @staticmethod
    def _best(dist, nm, lines):
        vals = [dist[(l, nm)] for l in lines if (l, nm) in dist]
        return min(vals) if vals else None

    def _link(self, row, rec):
        """정류장 행 ↔ 역 — 그 역에서 정류장에 가장 가까운 출구(없으면 역 좌표) 직선. 판정기 _stop_station_walk 와 같은 기준."""
        nm = rec["station_nm"]
        if self.ex is not None:
            e = self.ex.nearest(nm, row["lat"], row["lng"], rec.get("line"))
            if e is not None:
                return e[0]
        import math
        dy = (rec["lat"] - row["lat"]) * 111_320
        dx = (rec["lng"] - row["lng"]) * 111_320 * math.cos(math.radians((rec["lat"] + row["lat"]) / 2))
        return math.hypot(dx, dy)

    def _stations_by(self, row):
        """정류장 행 → 역 앞으로 볼 역들 [(출구 직선 m, 역 레코드)] — 역 좌표로 넉넉히(근접 + 출구표에서 잰 출구 최대 거리) 고른 뒤
        출구 거리로 near_m 안만 · 물리적 역마다 하나.
        정류장(ID · 없으면 좌표)마다 한 번만 잰다(표 객체에 붙은 캐시 — 같은 표면 요청이 달라도 값이 같다)."""
        # ☆(GPT 87 #3) 칸 = 역 좌표표(약한 키) 아래 (출구표 · 반경 · 정류장 ID · 정류장 좌표) — 출구표가 다르거나 같은 ID 의 좌표가
        #   바뀐 표면 다른 칸. 출구표 객체는 칸에 같이 붙잡아 둔다(id 재사용 방지).
        per_sc = _NEAR_ST.setdefault(self.sc, {})
        slot = per_sc.get(id(self.ex))
        if slot is None or slot[0] is not self.ex:
            slot = per_sc[id(self.ex)] = (self.ex, {}, exit_reach_m(self.sc, self.ex))
        cache, reach = slot[1], slot[2]
        k = (self.near_m, row.get("station_id"), row["lat"], row["lng"])
        got = cache.get(k)
        if got is None:
            best = {}
            for _d, rec in _station_index(self.sc).near(row["lat"], row["lng"], self.near_m + reach + 1):
                m = self._link(row, rec)
                pk = self.sc.phys_key(rec)
                if m <= self.near_m and (pk not in best or m < best[pk][0]):
                    best[pk] = (m, rec)               # 물리적 역마다 하나(그 역의 출구 중 정류장에 가장 가까운 쪽)
            got = cache[k] = sorted(best.values(), key=lambda t: (t[0], t[1]["station_nm"]))
        return got

    def _boards(self, lat, lng, walk_lim):
        """점 근처 정류장 행 [(m, row, route)] — 반경·도보 상한·유형 제외."""
        out = []
        for d, s in _stop_index(self.bus).near(lat, lng, self.radius_m):
            if d > walk_lim:
                continue
            r = self.bus.by_id.get(s["route_id"])
            if r is None or r.route_type_nm in self.excluded:
                continue
            out.append((d, s, r))
        return out

    def _ride(self, r, x, y):
        if self.ride_min is None:
            return None
        return self.ride_min(r, x, y)

    @staticmethod
    def _walkable(rec, lat, lng, excl_m):
        if not excl_m:
            return False
        import math
        dy = (rec["lat"] - lat) * 111_320
        dx = (rec["lng"] - lng) * 111_320 * math.cos(math.radians((rec["lat"] + lat) / 2))
        return math.hypot(dx, dy) <= excl_m

    def _ends(self, ends):
        out = []
        for nm, lines, w in ends:
            rec = self.sc.resolve(nm, lines) if self.sc else None
            if rec is None:
                continue
            ls = self._lines(rec)
            if ls:
                out.append((nm, ls, w))
        return out

    # ── A: 버스 → 지하철 ──
    def bus_to_subway(self, lat, lng, targets, walk_lim, excl_m=None, excl_st=None):
        """출발점(lat, lng) → 버스 → 끊는 역 → 지하철 → targets 중 하나. 구간열의 지하철 쪽은 materialize() 가 채운다.
        targets = [(역명, 노선 목록 또는 None, 도착 역 → 도착점 직선 m)] — 부르는 쪽이 도보 상한 안 역(막힌 역 뺌)을 준다.
        excl_m: 출발점에서 이 거리(역 좌표 직선) 안의 역은 끊지 않는다 — 걸어서 갈 수 있는 역까지 버스를 타는 후보는
        그 역에서 타는 지하철 후보와 같다(역 기준 verify_multi 는 정류장 반경 · None = 같은 역만 뺌).
        excl_st: 끊지 않을 물리적 역(phys_key) — 장소 기준 plan 은 **지하철 후보가 실제로 본 역**(장소마다 가까운 역 최대 k)만 준다
        (GPT 87 #6 — 도보 상한 안이라는 것만으로 지하철 후보가 그 역을 봤다고 할 수 없다)."""
        tg = self._ends(targets)
        if not tg:
            return []
        dist = self._dist([(nm, ls, self._walk_min(w)) for nm, ls, w in tg])
        tnames = {(nm, frozenset(ls)) for nm, ls, _w in tg}
        per_route = collections.defaultdict(dict)     # route_id → {끊는 역 물리 키: 후보}
        for d, x, r in self._boards(lat, lng, walk_lim):
            if r.route_type_nm == AIRPORT_TYPE and not is_airport_stop(x):
                continue                                  # 공항이 아닌 곳에서 타는 공항버스 = 공항행 — A(→지하철)에는 안 쓴다
            any_cut = False
            for y in self.bus.stops.get(r.route_id, []):
                if y["seq"] <= x["seq"] or _VIRTUAL in str(y.get("station_nm")) or y.get("lat") is None:
                    continue
                if r.route_type_nm == AIRPORT_TYPE and is_airport_stop(y):
                    continue                              # 공항 → 공항(돌아가는 끝) 은 끊는 지점이 아니다
                for link, rec in self._stations_by(y):
                    any_cut = True
                    if self._walkable(rec, lat, lng, excl_m) or (excl_st and self.sc.phys_key(rec) in excl_st):
                        continue
                    s_lines = self._lines(rec)
                    if not s_lines or any(rec["station_nm"] == nm and (s_lines & ls) for nm, ls in tnames):
                        continue                          # 서는 노선이 없거나 끊는 역이 도착 역(그건 버스 직행의 몫)
                    sub = self._best(dist, rec["station_nm"], s_lines)
                    if sub is None:
                        continue
                    ride = self._ride(r, x, y)
                    if ride is None:
                        continue
                    est = (self._walk_min(d) + (r.term_min or 0) / 2 + ride + self._walk_min(link) + self.wayfinding
                           + self.cg.transfer_wait + sub)
                    c = MixedCandidate("A", [{"mode": "bus", "route": r.route_nm, "from": x["station_nm"],
                                              "to": y["station_nm"]}], round(est, 1), 1, d, None, link, r.route_nm,
                                       rec["station_nm"], None, 0.0, "추정")
                    c._rank, c._sub_lines, c._tg = sub, sorted(s_lines), tg
                    c.route_id, c.board = r.route_id, x
                    pk = self.sc.phys_key(rec)
                    cur = per_route[r.route_id].get(pk)
                    if cur is None or c.est_min < cur.est_min:
                        per_route[r.route_id][pk] = c     # 같은 노선·같은 역은 추정 소요가 짧은 정류장 하나로
            if not any_cut and r.route_nm not in self.no_cut:
                self.no_cut.append(r.route_nm)
        return self._finish(per_route)

    # ── B: 지하철 → 버스 ──
    def subway_to_bus(self, sources, lat, lng, walk_lim, excl_m=None, excl_st=None):
        """sources 중 하나 → 지하철 → 끊는 역 → 버스 → 도착점(lat, lng). 구간열의 지하철 쪽은 materialize() 가 채운다.
        sources = [(역명, 노선 목록 또는 None, 출발점 → 출발 역 직선 m)] · excl_m · excl_st 는 A 와 같다(도착점 기준)."""
        sr = self._ends(sources)
        if not sr:
            return []
        dist = self._dist([(nm, ls, self._walk_min(w)) for nm, ls, w in sr])
        snames = {(nm, frozenset(ls)) for nm, ls, _w in sr}
        per_route = collections.defaultdict(dict)
        seen_air = set()
        for d, y, r in self._boards(lat, lng, walk_lim):
            if r.route_type_nm == AIRPORT_TYPE:
                if (is_airport_stop(y) and r.route_nm not in seen_air        # 도착점이 공항 = 공항행 — 37 정본 전 no_data 로 밝힌다
                        and any(s["seq"] < y["seq"] for s in self.bus.stops.get(r.route_id, []))):
                    seen_air.add(r.route_nm)
                    self.skipped_airport.append(r.route_nm)
                continue                                  # 시내에서 내리는 공항버스 구간은 B 에 안 쓴다(공항버스는 A 의 공항 → 시내만)
            any_cut = False
            for x in self.bus.stops.get(r.route_id, []):
                if x["seq"] >= y["seq"] or _VIRTUAL in str(x.get("station_nm")) or x.get("lat") is None:
                    continue
                for link, rec in self._stations_by(x):
                    any_cut = True
                    if self._walkable(rec, lat, lng, excl_m) or (excl_st and self.sc.phys_key(rec) in excl_st):
                        continue
                    s_lines = self._lines(rec)
                    if not s_lines or any(rec["station_nm"] == nm and (s_lines & ls) for nm, ls in snames):
                        continue                          # 끊는 역이 출발 역이면 지하철이 없다
                    sub = self._best(dist, rec["station_nm"], s_lines)
                    if sub is None:
                        continue
                    ride = self._ride(r, x, y)
                    if ride is None:
                        continue
                    est = (sub + self._walk_min(link) + self.wayfinding + (r.term_min or 0) / 2 + ride + self._walk_min(d))
                    c = MixedCandidate("B", [{"mode": "bus", "route": r.route_nm, "from": x["station_nm"],
                                              "to": y["station_nm"]}], round(est, 1), 1, None, d, link, r.route_nm,
                                       rec["station_nm"], None, 0.0, "추정")
                    c._rank, c._sub_lines, c._tg = sub, sorted(s_lines), sr
                    c.route_id, c.board = r.route_id, x
                    pk = self.sc.phys_key(rec)
                    cur = per_route[r.route_id].get(pk)
                    if cur is None or c.est_min < cur.est_min:
                        per_route[r.route_id][pk] = c
            if not any_cut and r.route_nm not in self.no_cut:
                self.no_cut.append(r.route_nm)
        return self._finish(per_route)

    # ── C: 버스 → 버스 ──
    def bus_to_bus(self, a_lat, a_lng, b_lat, b_lng, walk_lim, link_lim=None, top=None, reach_m=None, slack_m=None):
        """출발점 근처 정류장 → 버스 r1 → 환승 정류장 → 버스 r2 → 도착점 근처 정류장(2026-10-06 · 구글이 쓰는 「버스+버스」 모양).
        구간열은 이미 다 채워 있다(지하철이 없다) — materialize 할 일이 없다. 환승 정류장 한 쌍은 같은 노선쌍에서 **추정 소요가 짧은 것 하나**.

        환승점 찾기: r1 의 승차 이후 정류장 s 중 도착점에서 너무 멀어지지 않는 것(도착점까지 직선이 출발점까지 직선 + slack_m 안)만 보고,
        s 둘레 `link_lim` 안의 정류장 t 가 도착점 근처에서 내리는 노선 r2 위에 있고 승차→하차 순서(seq)가 맞으면 후보다.
        r1 이 혼자 도착점 근처까지 가면(버스 직행의 몫) 쓰지 않는다. 같은 노선 이름·공항버스·승차 분 추정이 없는 노선은 쓰지 않는다
        (추정을 못 내는 노선을 조용히 끼우지 않는다 — 혼합 A·B 와 같은 규칙)."""
        import math
        link_lim = BUS_LINK_MAX_M_PROPOSED if link_lim is None else link_lim
        top = BUS_BUS_MAX_PROPOSED if top is None else top
        reach_m = BUS_ACCESS_REACH_M_PROPOSED if reach_m is None else reach_m
        slack_m = BUS_DETOUR_SLACK_M_PROPOSED if slack_m is None else slack_m
        reach = min(reach_m, walk_lim)

        def near_by_route(lat, lng):
            best = {}
            for d, x in _stop_index(self.bus).near(lat, lng, reach):
                r = self.bus.by_id.get(x["route_id"])
                if r is None or r.route_type_nm in self.excluded or r.route_type_nm == AIRPORT_TYPE:
                    continue                                   # 유형 제외 · 공항버스는 A·B 규칙대로 환승 후보에 안 쓴다
                cur = best.get(r.route_id)
                if cur is None or d < cur[0]:
                    best[r.route_id] = (d, x, r)
            return best

        board_a, alight_b = near_by_route(a_lat, a_lng), near_by_route(b_lat, b_lng)
        if not board_a or not alight_b or self.ride_min is None:
            return []

        def m(lat1, lng1, lat2, lng2):
            dy = (lat2 - lat1) * 111_320
            dx = (lng2 - lng1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
            return math.hypot(dx, dy)

        ab = m(a_lat, a_lng, b_lat, b_lng)
        index = _stop_index(self.bus)
        best = {}
        for rid1, (da, x, r1) in sorted(board_a.items(), key=lambda kv: kv[1][0])[:BUS_FROM_ROUTES_MAX]:
            if rid1 in alight_b:
                continue                                       # r1 이 도착점 근처까지 간다 — 버스 직행(_bus_direct)의 몫
            for sp in self.bus.stops.get(rid1, []):
                if sp["seq"] <= x["seq"] or _VIRTUAL in str(sp.get("station_nm")) or sp.get("lat") is None:
                    continue
                if m(sp["lat"], sp["lng"], b_lat, b_lng) >= ab + slack_m:
                    continue                                   # 도착점에서 너무 멀어지는 지점은 환승점이 아니다(slack_m 까지는 돌아가는 노선을 봐준다)
                for dl, t in index.near(sp["lat"], sp["lng"], link_lim):
                    rid2 = t["route_id"]
                    if rid2 == rid1 or rid2 not in alight_b or _VIRTUAL in str(t.get("station_nm")):
                        continue
                    db, y, r2 = alight_b[rid2]
                    if t["seq"] >= y["seq"] or r2.route_nm == r1.route_nm:
                        continue
                    ride1, ride2 = self._ride(r1, x, sp), self._ride(r2, t, y)
                    if ride1 is None or ride2 is None:
                        continue
                    est = (self._walk_min(da) + (r1.term_min or 0) / 2 + ride1 + self._walk_min(dl) + self.wayfinding
                           + (r2.term_min or 0) / 2 + ride2 + self._walk_min(db))
                    key = (rid1, rid2)
                    cur = best.get(key)
                    if cur is not None and cur.est_min <= est:
                        continue
                    c = MixedCandidate(
                        "C", [{"mode": "bus", "route": r1.route_nm, "from": x["station_nm"], "to": sp["station_nm"]},
                              {"mode": "bus", "route": r2.route_nm, "from": t["station_nm"], "to": y["station_nm"]}],
                        round(est, 1), 1, da, db, dl, f"{r1.route_nm}→{r2.route_nm}", sp["station_nm"], y["station_nm"],
                        0.0, "추정")
                    c._rank, c._sub_lines, c._tg, c._done = est, [], [], True      # 지하철 구간이 없다 — 채울 것이 없다
                    c.route_id, c.board = r1.route_id, x
                    best[key] = c
        return sorted(best.values(), key=lambda c: (c.est_min, c.route_nm))[:top]

    def materialize(self, c):
        """후보 c 의 지하철 구간열을 채운다(최단 탐색 · 총 환승 상한 − 1). 성공하면 True — legs·transfers·est·도보·등급을 실제
        구간열 값으로 고친다. A 는 도착 역 후보 중 (지하철 + 이탈 도보)가 가장 짧은 쪽, B 는 출발 역 후보 중 (접근 도보 + 지하철)."""
        if getattr(c, "_done", False):
            return True
        cap = self.tlim - 1
        if cap < 0:
            return False
        best = None
        for nm, ls, w in c._tg:
            if c.shape == "A":
                sub = self.cg.search(c.cut_station, nm, "최단", cap, origin_lines=c._sub_lines, dest_lines=sorted(ls),
                                     avoid_lines=self.avoid)
            else:
                sub = self.cg.search(nm, c.cut_station, "최단", cap, origin_lines=sorted(ls), dest_lines=c._sub_lines,
                                     avoid_lines=self.avoid)
            if sub is None or not sub.legs:
                continue
            v = sub.est_min + self._walk_min(w)
            if best is None or v < best[0]:
                best = (v, sub, nm, w)
        if best is None:
            return False
        v, sub, nm, w = best
        bus = c.legs[0]
        c.legs = ([bus] + [dict(x) for x in sub.legs]) if c.shape == "A" else ([dict(x) for x in sub.legs] + [bus])
        c.est_min = round(c.est_min - c._rank + v, 1)
        c.transfers = 1 + sub.transfers
        c.end_station = nm
        if c.shape == "A":
            c.walk_out_m = w
        else:
            c.walk_in_m = w
        c.sub_walk_min, c.grade, c.fallback_edges = sub.walk_min, sub.grade, list(sub.fallback_edges)
        c._done = True
        return True

    def _finish(self, per_route):
        """노선마다 지하철 쪽 추정이 짧은 순 N개 → 전체를 추정 소요 순(같으면 노선·역 순)."""
        out = []
        for rid in sorted(per_route):
            out.extend(sorted(per_route[rid].values(), key=lambda c: (c._rank, c.cut_station))[:self.cuts])
        out.sort(key=lambda c: (c.est_min, c.route_nm, c.cut_station))
        return out


_RIDE = _weakref.WeakKeyDictionary()      # 버스 표 객체 → {route_id: (누적 분 {seq: 분}, 빈 구간 수 {seq: n})}


def ride_estimator(v, hour=12):
    """혼합 후보의 **버스 승차 분 추정**(고르는 순서용 · 판정 아님) — v = 판정기(bus · bus_prof · bus_speed · R).
    구간마다 버스 구간 프로파일(41 · 평일 hour 시 p50 · min_days 이상)이 있으면 그 값, 없으면 판정기 종전 모델(거리 ÷ 표정속도 ·
    평일)로 누적한다. 공항버스처럼 표정속도 대용(간선 통계)이 실제보다 크게 느린 노선도 프로파일이 있으면 실제에 가깝다
    (인천공항→서울역 6001: 대용 속도 272분 · 판정기 판정 약 90분). 노선마다 한 번만 만든다. 값을 못 내는 구간이 끼면 None."""
    bus, prof = v.bus, getattr(v, "bus_prof", None)
    md = None
    if prof is not None:
        try:
            md = v.rv("bus", "구간_프로파일", "min_days")
        except Exception:      # noqa: BLE001 — 규칙 칸이 없으면 프로파일을 안 쓴다(종전 모델만)
            prof = None
    # ☆(GPT 87 #3) 캐시 칸 = 버스 표 객체(약한 키) 아래 **값을 정하는 입력 전부** — 프로파일 표 · 규칙(표정속도) · 시각 · min_days.
    #   객체 id 는 그 객체를 칸 안에 같이 붙잡아 둬서(살아 있는 동안 id 가 다른 객체에 다시 쓰이지 않게) 키로 쓴다.
    #   요청마다 판정기를 얕은 복사해도 이 셋은 같은 객체라 칸이 공유되고, 설정이 다른 판정기는 다른 칸을 쓴다.
    per_bus = _RIDE.setdefault(bus, {})
    ck = (id(prof), id(v.R), hour, md)
    slot = per_bus.get(ck)
    if slot is None or slot[0] is not prof or slot[1] is not v.R:
        slot = per_bus[ck] = (prof, v.R, {})
    cache = slot[2]

    def build(r):
        sp = v.bus_speed(r, "weekday")[0]
        stops = bus.stops.get(r.route_id, [])
        cum, nil, tot, miss = {}, {}, 0.0, 0
        for k, st in enumerate(stops):
            if k:
                prev = stops[k - 1]
                m = None
                if prof is not None:
                    i, _bad = prof.row(r.route_id, prev, st)
                    if i is not None:
                        c = prof.cell(i, "weekday", hour, "p50", md)
                        m = None if c is None else c / 60.0
                if m is None:
                    dd = st.get("sect_dist_m")
                    m = None if (dd is None or not sp) else dd / 1000 / sp * 60
                if m is None:
                    miss += 1
                else:
                    tot += m
            cum[st["seq"]], nil[st["seq"]] = tot, miss
        return cum, nil

    def ride(r, x, y):
        c = cache.get(r.route_id)
        if c is None:
            c = cache[r.route_id] = build(r)
        cum, nil = c
        a, b = x["seq"], y["seq"]
        if a not in cum or b not in cum or nil[b] != nil[a]:
            return None
        return cum[b] - cum[a]
    return ride


def interleave(*lists):
    """모양별 후보를 번갈아(각자 추정 소요 순) — 판정 개수 상한 안에서 한 모양만 보지 않게(87). 앞 목록(A) 먼저.
    ☆`[2026-10-06]` 두 목록(A·B)에서 여럿(A·B·C 버스→버스)으로 일반화했다 — 둘만 줘도 종전과 같다."""
    out = []
    for i in range(max((len(x) for x in lists), default=0)):
        for x in lists:
            if i < len(x):
                out.append(x[i])
    return out
