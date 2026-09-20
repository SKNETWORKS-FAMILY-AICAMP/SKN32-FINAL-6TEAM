# scripts/verify_time.py — 시각 검증기 v2 (지하철 분기)
#
# "그 구간 이동이 그 시각에 성립하는가" 를 코드가 판정한다. 이 모듈의 본체다.
# 실행: 저장소 루트에서
#   python scripts/verify_time.py --cases tests/mobility/synthetic_legs_v1.json --check-expect
#   python scripts/verify_time.py --cases tests/mobility/synthetic_legs_v1.json --case LT-03 --verbose
#   python scripts/verify_time.py --cases ... --timetable <경로> --json out.json
#
# v1 과 달라진 것 (2026-09-10)
#   ★ 시각을 **분 단위 정수**로 다룬다. strptime 을 쓰지 않는다 — 시간표 dep_time 에
#     '24:50:00'·'27:59:00' 이 들어온다. modules/mobility/timeutil.py 가 유일한 자다.
#   ★ 막차 후보를 셋으로 거른다 — dest_nm 없음(근거없음) · 종착 열차(그 역이 행선지) ·
#     단축운행(목적지 전에 내려줌). C4/C5 가 소스 간 대조로 잡아낸 것들이고
#     **하나도 축소 시간표의 가짜 시각으로는 안 나온다.**
#   ★ 방향은 dir(U/D) 이 아니라 dest_nm 으로 정한다. 인천2호선·신림선은 같은 dir 에
#     양 끝 행선지가 섞여 있다.
#   ★ 2호선 신정지선 토요일은 등급을 추정으로 내린다(rules last_train.신정지선_토요일_예외).
#
# 규칙 v0.4 (2026-09-19 · 19번 방 · 지하철↔버스 혼합 환승)
#   ★ 지하철↔버스 환승 도보를 정류장 좌표 ↔ 그 역 가장 가까운 출구(OSM, 추정) 직선 × 우회계수로 잰다.
#     직선이 limits.walk_m 를 넘으면 **불가**, 상한 ±20 m 면 근거없음(unknown). _stop_station_walk.
#   ★ 버스 구간이 불가이면 노선교체(같은 두 정류장의 다른 노선)·수단교체(정류장 근처 역끼리 지하철)를 연다.
#   ★ 시간표 부분 적재에 대안 후보 노선·정류장 근처 역을 포함한다 — 종전에는 ⓑ 노선교체가 회귀에서 죽어 있었다.
#
# 판정 값 넷
#   feasible          성립
#   infeasible        불가 (+완화 조건)
#   rejected_by_limit 성립하지만 동행 상한 초과로 탈락
#   unknown           근거 없음
#   ※ 탈락과 불가를 구분하는 게 핵심이다. 탈락은 "되지만 이 일행에게 무리", 불가는 "안 된다".
import argparse, json, math, sys, difflib, collections
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from modules.mobility.line_order import LineOrder                      # noqa: E402
from modules.mobility.transfer_walk import TransferWalk                 # noqa: E402
from modules.mobility.bus import BusRoutes                              # noqa: E402
from modules.mobility.geo import StationCoords, meters                  # noqa: E402
from modules.mobility.exits import StationExits                         # noqa: E402
from modules.mobility.timeutil import (to_min, to_service_min, fmt_min,  # noqa: E402
                                       fmt_wall, day_type_of, MIN_DAY)

VERDICTS = ("feasible", "infeasible", "rejected_by_limit", "unknown")
GRADE_ORDER = {"확정": 2, "추정": 1, "근거없음": 0}


def worst(*grades):
    gs = [g for g in grades if g]
    return min(gs, key=lambda g: GRADE_ORDER[g.split(":")[0]]) if gs else "근거없음"


# ── 시간표 ────────────────────────────────────────────────────────────────
@dataclass
class Dep:
    min: int          # 출발 시각(분, 24 시 이상 가능)
    dir: str          # 참고용. 방향의 정본이 아니다
    dest: str         # 행선지 — 방향의 정본


class Timetable:
    """processed/mobility/timetable_v1.jsonl 을 판정에 필요한 만큼만 올린다.

    46만 행을 통째로 dict 로 만들면 메모리가 아깝다. 케이스에 나오는 (노선, 역) 만
    골라 담는다. DB 전환(03번 방) 뒤에는 이 클래스가 조회로 바뀐다.
    """

    def __init__(self):
        self.by_key = collections.defaultdict(list)   # (line, station, day_type) → [Dep]
        self.stations = set()                         # (line, station) — 시간표에 존재하는가
        self.rows = 0
        self.skipped_no_dep = 0
        self.fetched_at = None

    @classmethod
    def load(cls, path, wanted=None):
        tt = cls()
        with open(path, encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                r = json.loads(raw)
                line, nm = r.get("line"), r.get("station_nm")
                if wanted is not None and (line, nm) not in wanted:
                    continue
                tt.stations.add((line, nm))
                if tt.fetched_at is None:
                    tt.fetched_at = r.get("fetched_at")
                m = to_min(r.get("dep_time"))
                if m is None:                     # 시·종착역은 출발이 없다
                    tt.skipped_no_dep += 1
                    continue
                tt.by_key[(line, nm, r.get("day_type"))].append(
                    Dep(m, r.get("dir"), r.get("dest_nm")))
                tt.rows += 1
        for v in tt.by_key.values():
            v.sort(key=lambda d: d.min)
        return tt

    def departures(self, line, station, day_type):
        return self.by_key.get((line, station, day_type), [])

    def has_station(self, line, station):
        return (line, station) in self.stations

    def similar(self, line, station, n=5):
        pool = [s for (l, s) in self.stations if l == line]
        return difflib.get_close_matches(station, pool, n=n, cutoff=0.5)


# ── 판정 결과 ─────────────────────────────────────────────────────────────
def dedup_warn(ws):
    """경고 중복 제거. ★ dict 는 해시가 안 되므로 dict.fromkeys 를 쓰면 터진다 — code 기준으로 거른다."""
    out, seen = [], set()
    for w in ws or []:
        k = w["code"] if isinstance(w, dict) else w
        if k in seen:
            continue
        seen.add(k)
        out.append(w)
    return out


@dataclass
class LegResult:
    idx: int
    label: str
    verdict: str
    reason: str
    grade: str = "확정"
    depart_min: int = None
    arrive_min: int = None
    wait_min: int = None
    ride_min: float = None
    ride_grade: str = "확정"
    relief: str = None                       # 완화 조건
    dropped: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    evidence: list = field(default_factory=list)


@dataclass
class CaseResult:
    id: str
    verdict: str
    reason: str
    grade: str
    legs: list = field(default_factory=list)
    arrive_min: int = None
    slack_min: float = None
    relief: str = None
    warnings: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    day_type: str = None
    alternatives: list = field(default_factory=list)
    alt_tried: list = field(default_factory=list)
    taxi: dict = None


# ── 검증기 ────────────────────────────────────────────────────────────────
class Verifier:
    def __init__(self, tt, lo, rules, holidays, tw=None, bus=None, sc=None, ex=None):
        self.tt, self.lo, self.R, self.tw, self.bus = tt, lo, rules, tw, bus
        self.sc = sc
        self.ex = ex            # 역 출구 좌표(OSM · 추정) — 지하철↔버스 환승에만 쓴다 (19번 방)
        self._lines_of = None
        self.holidays = holidays
        self.rules_src = rules.get("source_id", "mobility_rules")
        self.rules_at = rules.get("effective_date")
        self._passes_cache = {}
        self._origin_cache = {}
        self._dominant_cache = {}
        sj = rules["last_train"]["신정지선_토요일_예외"]["value"]
        self.sinjeong = (sj["line"], set(sj["stations"]))
        self.disr = []          # 이 케이스의 이슈 조건. verify_case 가 매 건 갈아 끼운다.

    # 규칙 값 꺼내기 — 값이 없으면 죽는다. 조용히 기본값을 쓰지 않는다.
    def rv(self, *path):
        n = self.R
        for k in path:
            n = n[k]
        return n["value"]

    # ── 경고 어휘 (rules warnings 절) ─────────────────────────────────
    # 경고는 문자열이 아니라 {code, class, text, to_answer} 다.
    # 문구를 고쳐도 코드가 안 바뀌므로 회귀(expect_warn_codes)와 계약(Evidence.value.warnings)이
    # 문장에 매이지 않는다. 접기 설계 v1 §17.
    # ★ 정의에 없는 코드나 인자가 모자라면 여기서 죽는다 — 조용히 넘어가지 않는다.
    def warn_msg(self, code, **kw):
        spec = self.R["warnings"][code]
        if "text_ref" in spec:
            node = self.R
            for seg in spec["text_ref"].split("."):
                node = node[seg]
            text = node
        else:
            text = spec["text"].format(**kw)
        return {"code": code, "class": spec["class"],
                "text": text, "to_answer": spec["to_answer"]}

    # ── 이슈 조건 (코어 current_state.replan) ────────────────────────────
    # ★ 우리가 관측한 게 아니다. 등급을 올리지 않는다 — 준 쪽의 등급을 그대로 싣는다.
    # ★ 이슈로 인한 불가는 시간표로 인한 불가와 **완화 조건이 다르다**.
    #   시간표 불가는 "더 일찍/늦게 출발", 이슈 불가는 "우회 또는 복구 대기"다.
    # ★ 대안 열거는 self.disr 을 그대로 물려받는다 — 대안으로 낸 노선이 같은 이슈에 걸리면 안 된다.
    #   alternatives() 가 verify_leg 을 다시 부르므로 인스턴스에 두면 저절로 상속된다.
    DISR_KINDS = ("line_closed", "station_skip", "edge_closed", "route_closed")

    def _disr(self, kind, **eq):
        for d in self.disr:
            if d.get("kind") != kind:
                continue
            if all(d.get(k) == v for k, v in eq.items()):
                return d
        return None

    def _disr_edges(self, line):
        """그 노선에서 끊긴 간선들. frozenset 쌍으로 돌려준다."""
        out = set()
        for d in self.disr:
            if d.get("kind") == "edge_closed" and d.get("line") == line:
                a, b = d["between"]
                out.add(frozenset((a, b)))
        return out

    def _ev_disr(self, d, claim):
        # source_type 은 'case_event' 다 — 03번 방 스키마의 CHECK 가
        # ('db','policy','case_event') 만 허용한다. 'external' 같은 새 값을 만들면
        # **판정 근거가 적재 단계에서 거부된다.** 그 CHECK 는 카카오 응답('tool_result')을
        # 막으려고 건 것이고, 좁게 두는 편이 맞다. 이슈는 케이스에 붙은 사건이다.
        return {"source_type": "case_event", "source_id": d.get("source", "core.current_state.replan"),
                "grade": d.get("grade", "추정"), "observed_at": d.get("observed_at"),
                "claim": claim}

    def _disr_label(self, d):
        return d.get("note") or {"line_closed": "노선 운행중단", "station_skip": "무정차 통과",
                                 "edge_closed": "구간 운행중단",
                                 "route_closed": "노선 운행중단"}[d["kind"]]

    def _passes(self, line, origin, dest, target, dir=None, origin_terminal=False,
                full_circuit=False):
        # dir 은 순환선에서만 쓰인다(2호선). 다른 노선은 행선지가 방향을 정한다.
        k = (line, origin, dest, target, dir, origin_terminal, full_circuit)
        if k not in self._passes_cache:
            self._passes_cache[k] = self.lo.passes(
                line, origin, dest, target, dir=dir,
                origin_terminal=origin_terminal, full_circuit=full_circuit)
        return self._passes_cache[k]

    def dominant_dest(self, line, station, day_type, dir):
        """그 (역, 요일, dir) 출발행의 **지배적 행선지** — 그 방향 순환 편성의 종착지.

        ★ 02호선은 본선 열차의 행선지가 거의 전부 '성수' 다(강변 평일 479편 중 457편).
          '행선지를 처음 만나면 종착' 으로 읽으면 왕십리 내선 성수행이 3정거장짜리 열차가 되어
          왕십리→잠실이 외선 35정거장(73분)으로 나온다. 실제는 내선 12정거장이다.
          지배적 행선지의 열차는 행선지를 지나쳐 **한 바퀴 도는 편성**으로 본다.
          점유율이 낮은 행선지(막차 근처 삼성·홍대입구 각 1편)는 진짜 단축운행이다.
        """
        k = (line, station, day_type, dir)
        if k not in self._dominant_cache:
            deps = [d for d in self.tt.departures(line, station, day_type) if d.dir == dir]
            c = collections.Counter(d.dest for d in deps if d.dest)
            top = c.most_common(1)
            thr = self.rv("last_train", "순환선_한바퀴_판별")
            self._dominant_cache[k] = (top[0][0] if top and deps
                                       and top[0][1] / len(deps) >= thr else None)
        return self._dominant_cache[k]

    def is_origin_station(self, line, station, day_type):
        """이 역이 **시발역**인가 — dest 가 역 자신인 행이 그 역 출발의 다수인가.

        02호선 성수는 유효 출발 592편이 전부 dest='성수' 다(05:30~24:51). 입고 열차가 아니라
        시발 열차이고, 소스가 시발 열차의 행선지를 역 자신으로 준다. 05호선 여의도의
        24:47 여의도행은 198편 중 1편이라 그쪽이 입고다. 규칙 last_train.시발열차_판별.
        """
        k = (line, station, day_type)
        if k not in self._origin_cache:
            deps = self.tt.departures(line, station, day_type)
            n = len(deps)
            self_n = sum(1 for d in deps
                         if d.dest and self.lo.resolve_dest(line, d.dest) == station)
            thr = self.rv("last_train", "시발열차_판별")
            self._origin_cache[k] = bool(n and self_n / n >= thr)
        return self._origin_cache[k]

    # ── 출발 후보 고르기 — 막차 4종이 전부 여기 있다 ──
    def candidates(self, line, origin, target, day_type):
        """그 역 출발행에서 **목적지까지 가는 열차**만 남긴다. 막차 4종이 전부 여기 있다."""
        deps = self.tt.departures(line, origin, day_type)
        is_origin = self.is_origin_station(line, origin, day_type)
        # ★ 한 바퀴 가정은 운행 시간대 안에서만 성립한다. 막차는 돌지 않는다.
        tdeps = self.tt.departures(line, target, day_type)
        last_at_target = tdeps[-1].min if tdeps else None
        margin = self.rv("last_train", "한바퀴_도착_여유_분")
        closed = self._disr_edges(line)      # 끊긴 간선 — 그 위를 지나는 편성은 쓸 수 없다
        out, drop = [], collections.Counter()
        for d in deps:
            if not d.dest:                                    # ② dest_nm 없음
                drop["행선지없음"] += 1
                continue
            self_dest = self.lo.terminates_here(line, origin, d.dest)
            if self_dest and not is_origin:                    # ③ 입고(종착) 열차
                drop["종착열차"] += 1
                continue
            full = (self.lo.is_loop(line)
                    and d.dest == self.dominant_dest(line, origin, day_type, d.dir))
            v = self._passes(line, origin, d.dest, target, d.dir,
                             origin_terminal=(self_dest and is_origin), full_circuit=full)
            if v.value is True:
                # ★ 무정차(station_skip)는 여기서 안 거른다 — 서지 않을 뿐 지나간다.
                #   끊긴 간선(edge_closed)은 지나가지도 못하므로 그 편성을 뺀다.
                if closed and self._path_blocked(v.path, target, closed):
                    drop["이슈_구간차단"] += 1
                    continue
                if full and last_at_target is not None:
                    ride = self.lo.travel_min_on_path(line, v.path, target)
                    if ride is not None and d.min + math.ceil(ride) > last_at_target + margin:
                        drop["운행종료후_한바퀴"] += 1        # 막차가 한 바퀴 돈다는 판정을 막는다
                        continue
                out.append((d, v, full))
            elif v.value is False:
                drop["단축운행"] += 1
            else:
                drop["행선지_해석불가"] += 1
        return out, drop, is_origin

    @staticmethod
    def _path_blocked(path, target, closed):
        """판정에 쓰는 경로가 끊긴 간선을 밟는가. **target 까지만** 본다(그 뒤는 안 탄다)."""
        if not path:
            return False
        for i in range(len(path) - 1):
            if frozenset((path[i], path[i + 1])) in closed:
                return True
            if path[i + 1] == target:
                return False
        return False

    def verify_leg(self, idx, leg, now_min, day_type, is_saturday):
        line = leg["line"]
        a, b = leg["from"], leg["to"]
        label = f"{line} {a}→{b}"
        ev, warn = [], []

        # 0-) 이슈 조건을 시간표보다 **먼저** 본다. 시간표에 열차가 있어도 오늘 안 서면 못 탄다.
        d = self._disr("line_closed", line=line)
        if d:
            return LegResult(idx, label, "infeasible",
                             f"{line} 이 운행중단이다 ({self._disr_label(d)})",
                             grade=d.get("grade", "추정"),
                             relief="다른 노선 또는 수단으로 우회. 복구 시각은 우리가 모른다",
                             evidence=[self._ev_disr(d, f"{line} 운행중단")])
        for nm, wh in ((a, "출발"), (b, "도착")):
            d = self._disr("station_skip", line=line, station=nm)
            if d:
                return LegResult(
                    idx, label, "infeasible",
                    f"{line} 열차가 {nm} 에 서지 않는다 ({self._disr_label(d)}) — "
                    f"{wh} 역으로 쓸 수 없다. 지나가기는 한다",
                    grade=d.get("grade", "추정"),
                    relief=f"{nm} 대신 앞뒤 역에서 타거나 내려 걷는다. 또는 다른 노선·수단으로 우회",
                    evidence=[self._ev_disr(d, f"{line} {nm} 무정차")])

        # 0) 시간표에 그 역이 있는가
        for nm in (a, b):
            if not self.tt.has_station(line, nm):
                sim = self.tt.similar(line, nm)
                hint = f" (비슷한 역명: {', '.join(sim)})" if sim else ""
                return LegResult(idx, label, "unknown",
                                 f"{line} 시간표에 '{nm}' 이 없다{hint}", grade="근거없음",
                                 dropped={},
                                 warnings=[self.warn_msg("MOB_W_STATION_NOT_IN_TIMETABLE",
                                                         line=line, station=nm, hint=hint)])
        if not self.tt.departures(line, a, day_type):
            return LegResult(idx, label, "unknown",
                             f"{line} {a} 의 {day_type} 시간표가 없다", grade="근거없음")

        # 1) 방향 = 행선지(+순환선은 dir). 목적지를 지나는 열차만 남긴다
        cands, drop, is_origin = self.candidates(line, a, b, day_type)
        if not cands:
            if drop.get("이슈_구간차단"):
                # ★ 이슈로 길이 끊긴 것과 원래 열차가 없는 것을 섞어 말하면 안 된다.
                #   완화 조건이 다르다 — 이쪽은 더 일찍 출발해도 안 된다.
                # ★ 끊긴 간선을 **전부** 말한다. 하나만 말하면 순환선에서
                #   "성수–건대입구만 끊겼는데 왜 반대로 못 도나" 가 된다 —
                #   실제로는 반대쪽 간선도 끊겨서 양방향이 막힌 것이다.
                dds = [x for x in self.disr
                       if x.get("kind") == "edge_closed" and x.get("line") == line]
                seg = " · ".join(f"{x['between'][0]}–{x['between'][1]}" for x in dds)
                both = (" 양방향이 다 막혔다." if len(dds) > 1 and self.lo.is_loop(line) else "")
                return LegResult(
                    idx, label, "infeasible",
                    f"{line} {seg} 구간이 끊겨 {a}→{b} 를 잇는 편성이 없다.{both} "
                    f"시간표에는 {drop['이슈_구간차단']}편이 있다",
                    grade=worst(*[x.get("grade", "추정") for x in dds]), dropped=dict(drop),
                    relief="다른 노선 또는 수단으로 우회. 더 일찍·늦게 출발해도 같다",
                    evidence=[self._ev_disr(x, f"{line} {x['between'][0]}–{x['between'][1]} 운행중단")
                              for x in dds])
            if drop and drop.most_common(1)[0][0] in ("행선지없음", "행선지_해석불가"):
                return LegResult(idx, label, "unknown",
                                 f"{a} 출발 열차의 행선지를 확인할 수 없어 {b} 까지 간다고 말할 수 없다",
                                 grade="근거없음", dropped=dict(drop))
            # ★ 반대 방향은 있는데 이쪽만 0편이면 운행이 없는 게 아니라 **수집이 빠진 것**이다.
            #   도림천→신도림 110편 / 신도림→도림천 0편 이 실제로 그랬다(지선 편성 누락).
            #   소스가 없는 구간을 정상으로 바꾸지 않는 것과 같은 이유로, 불가로도 바꾸지 않는다.
            rev, _, _ = self.candidates(line, b, a, day_type)
            if rev:
                return LegResult(
                    idx, label, "unknown",
                    f"{a}→{b} 편성이 {day_type} 시간표에 0편인데 반대 방향 {b}→{a} 는 "
                    f"{len(rev)}편 있다 — 운행이 없는 게 아니라 수집이 빠진 것으로 본다",
                    grade="근거없음", dropped=dict(drop),
                    warnings=[self.warn_msg("MOB_W_DIRECTION_NOT_COLLECTED",
                                            line=line, a=a, b=b)],
                    evidence=[self._ev_rule("service_window.왕복_비대칭_수집누락", "확정")])
            return LegResult(idx, label, "infeasible",
                             f"{a} 에서 {b} 방향으로 가는 열차가 {day_type} 시간표에 없다",
                             grade="확정", dropped=dict(drop),
                             relief="노선 교체 또는 반대 방향 확인이 필요하다")

        first, last = cands[0][0].min, cands[-1][0].min
        gap_max = self.rv("service_window", "gap_max_min")
        scan = self.rv("service_window", "candidate_scan_min")

        # 2) 첫차 이전 · 막차 이후
        after = [(d, v) for d, v, _f in cands if d.min >= now_min]
        if not after:
            roll = self._rollover_relief(now_min, first)
            if roll:
                wall, gap = roll
                return LegResult(
                    idx, label, "infeasible",
                    f"{fmt_wall(now_min)} 은 {line} {a} 의 {day_type} 첫차({fmt_min(first)}) 이전이다 "
                    f"(전날 막차 {fmt_min(last)} 는 이미 지났다)",
                    grade="확정", dropped=dict(drop),
                    relief=f"{gap}분 뒤 첫차 {fmt_min(first)} 를 기다리면 성립",
                    evidence=[self._ev_tt(line, a, day_type, f"그 방향 첫 출발 {fmt_min(first)}")])
            return LegResult(
                idx, label, "infeasible",
                f"{fmt_min(now_min)} 이후 {b} 까지 가는 열차가 없다 "
                f"(그 방향 마지막 출발 {fmt_min(last)} {cands[-1][0].dest}행)",
                grade="확정", dropped=dict(drop),
                relief=f"{fmt_min(last)} 까지 출발하면 성립. 이후는 수단 교체(버스·택시)",
                evidence=[self._ev_tt(line, a, day_type, f"그 방향 마지막 출발 {fmt_min(last)}")])
        if now_min < first:
            return LegResult(
                idx, label, "infeasible",
                f"{fmt_min(now_min)} 은 {line} {a} 의 {day_type} 첫차({fmt_min(first)}) 이전이다",
                grade="확정", dropped=dict(drop),
                relief=f"출발을 {fmt_min(first)} 로 미루면 성립",
                evidence=[self._ev_tt(line, a, day_type, f"그 방향 첫 출발 {fmt_min(first)}")])
        wait0 = after[0][0].min - now_min
        if wait0 > gap_max:
            return LegResult(
                idx, label, "infeasible",
                f"{fmt_min(now_min)} 이후 다음 출발이 {fmt_min(after[0][0].min)} 이라 "
                f"{wait0}분을 기다려야 한다 (공백 상한 {gap_max}분)",
                grade="추정", dropped=dict(drop),
                relief=f"{fmt_min(after[0][0].min)} 출발을 기다리면 성립")

        # 3) ★ 가장 이른 **도착**을 고른다. 가장 먼저 떠나는 열차가 가장 먼저 닿지 않는다 —
        #    02호선 강변 14:00 내선 성수행은 성수까지 40정거장, 14:02 외선 성수행은 3정거장이다.
        #    소요도 그 열차가 실제로 도는 경로 위에서 잰다(travel_min 은 최단경로라 순환선에서 틀린다).
        window = [(d, v) for d, v in after if d.min <= after[0][0].min + scan]
        best = None
        for d, v in window:
            ride = self.lo.travel_min_on_path(line, v.path, b)
            arr = d.min + math.ceil(ride) if ride is not None else None
            key = (arr is None, arr if arr is not None else d.min, d.min)
            if best is None or key < best[0]:
                best = (key, d, v, ride, arr)
        _, nxt, verd, ride, arrive = best
        wait = nxt.min - now_min
        ride_grade = "추정" if ride is not None else "근거없음"

        grade = worst(verd.grade, "확정")
        if is_origin:
            warn.append(self.warn_msg("MOB_W_ORIGIN_TERMINAL_DEST", station=a))
            ev.append(self._ev_rule("last_train.시발열차_판별", "추정"))
        if is_saturday and line == self.sinjeong[0] and (
                a in self.sinjeong[1] or b in self.sinjeong[1]):
            grade = worst(grade, "추정")
            warn.append(self.warn_msg("MOB_W_SINJEONG_SAT"))
            ev.append(self._ev_rule("last_train.신정지선_토요일_예외", "추정"))

        ev.append(self._ev_tt(line, a, day_type,
                              f"{fmt_min(nxt.min)} 출발 {nxt.dest}행 (그 방향 {len(cands)}편 중, "
                              f"{fmt_min(after[0][0].min)}~ 안에서 도착이 가장 이른 편)"))
        ev.append({"source_type": "db", "source_id": "line_station_order_v1",
                   "grade": verd.grade, "observed_at": self.lo.built_at, "claim": verd.reason})
        if drop.get("종착열차") or drop.get("단축운행") or drop.get("행선지없음"):
            ev.append(self._ev_rule("last_train.행선지_확인", "확정"))

        return LegResult(idx, label, "feasible",
                         f"{fmt_min(nxt.min)} {nxt.dest}행 승차 (대기 {wait}분)",
                         grade=grade, depart_min=nxt.min, arrive_min=arrive,
                         wait_min=wait, ride_min=ride, ride_grade=ride_grade,
                         dropped=dict(drop), warnings=warn, evidence=ev)


    # ── 버스 — 지하철과 판정 구조가 다르다 ──
    def verify_leg_bus(self, idx, leg, now_min, day_type):
        """버스는 노선 단위 소스다. '운행 구간 안인가 + 배차만큼 기다리는가' 로 본다.

        지하철처럼 '그 시각에 출발하는 차'를 찾을 수 없다 — 정류장별 시각이 없기 때문이다.
        그래서 대기가 추정이고, 승차 소요는 아예 내지 않는다(rules.bus.ride_model).
        """
        nm, a_nm, b_nm = str(leg["route"]), leg["from"], leg["to"]
        label = f"버스 {nm} {a_nm}→{b_nm}"
        d = self._disr("route_closed", route=nm)
        if d:
            return LegResult(idx, label, "infeasible",
                             f"버스 {nm} 이 운행중단이다 ({self._disr_label(d)})",
                             grade=d.get("grade", "추정"),
                             relief="다른 노선 또는 수단으로 우회. 복구 시각은 우리가 모른다",
                             evidence=[self._ev_disr(d, f"버스 {nm} 운행중단")])
        if self.bus is None:
            return LegResult(idx, label, "unknown", "버스 노선 데이터를 읽지 못했다", grade="근거없음")
        r = self.bus.route(nm)
        if r is None:
            return LegResult(idx, label, "unknown",
                             f"노선 '{nm}' 이 수집 범위에 없다 (수집된 {len(self.bus.by_id)}노선 밖)", grade="근거없음",
                             warnings=[self.warn_msg("MOB_W_BUS_ROUTE_NOT_COLLECTED", route=nm)])
        if r.route_type_nm in (self.rv("bus", "route_type_제외") or []):
            return LegResult(idx, label, "unknown",
                             f"{nm} 은 {r.route_type_nm} 버스라 일반 이동 수단으로 쓰지 않는다",
                             grade="근거없음",
                             warnings=[self.warn_msg("MOB_W_BUS_ROUTE_EXCLUDED",
                                                     route=nm, route_type=r.route_type_nm)],
                             evidence=[self._ev_rule("bus.route_type_제외", "확정")])

        seg = self.bus.segment(r.route_id, a_nm, b_nm)
        if seg is None:
            back = self.bus.segment(r.route_id, b_nm, a_nm)
            if back:
                return LegResult(idx, label, "infeasible",
                                 f"{nm} 은 {a_nm}→{b_nm} 방향으로 가지 않는다 (반대 방향 노선이다)",
                                 grade="확정", relief="반대 방향 정류장 또는 다른 노선")
            miss = [x for x, got in ((a_nm, self.bus.find_stops(r.route_id, a_nm)),
                                     (b_nm, self.bus.find_stops(r.route_id, b_nm))) if not got]
            return LegResult(idx, label, "unknown",
                             f"{nm} 정류장 목록에 {', '.join(miss) or '해당 구간'} 이 없다",
                             grade="근거없음")
        a, b, span = seg
        warn, ev = [], []
        if day_type != "weekday":
            warn.append(self.warn_msg("MOB_W_BUS_NO_DAYTYPE", route=nm, day_type=day_type))

        # 1) 운행 구간 — 여기만 확정이다
        if r.first_min is None or r.last_min is None:
            return LegResult(idx, label, "unknown", f"{nm} 의 첫차·막차가 없다", grade="근거없음")
        if now_min < r.first_min:
            return LegResult(idx, label, "infeasible",
                             f"{fmt_min(now_min)} 은 {nm} 첫차({fmt_min(r.first_min)}) 이전이다",
                             grade="확정", relief=f"출발을 {fmt_min(r.first_min)} 로 미루면 성립",
                             warnings=warn, evidence=[self._ev_bus(r, "운행 구간")])
        if now_min > r.last_min:
            roll = self._rollover_relief(now_min, r.first_min)
            if roll:
                wall, gap = roll
                return LegResult(
                    idx, label, "infeasible",
                    f"{fmt_wall(now_min)} 은 {nm} 첫차({fmt_min(r.first_min)}) 이전이다 "
                    f"(전날 막차 {fmt_min(r.last_min)} 는 이미 지났다)",
                    grade="확정", relief=f"{gap}분 뒤 첫차 {fmt_min(r.first_min)} 를 기다리면 성립",
                    warnings=warn, evidence=[self._ev_bus(r, "운행 구간")])
            return LegResult(idx, label, "infeasible",
                             f"{fmt_min(now_min)} 은 {nm} 막차({fmt_min(r.last_min)}) 이후다",
                             grade="확정", relief="수단 교체(지하철·택시)", warnings=warn,
                             evidence=[self._ev_bus(r, "운행 구간")])

        # 2) 대기 — 추정이다. 막차 근처는 배차 전부로 잡는다(놓치면 되돌릴 수 없다)
        if not r.term_min:
            return LegResult(idx, label, "unknown",
                             f"{nm} 의 배차가 0이다 — 배차 0분이 아니라 배차 개념 없음(예약제·출퇴근 전용)",
                             grade="근거없음", warnings=warn,
                             evidence=[self._ev_rule("bus.배차_0", "근거없음")])
        near_last = now_min >= r.last_min - self.rv("bus", "막차근처_기준_분")
        wait = r.term_min if near_last else math.ceil(r.term_min / 2)
        model = "배차 전부(막차 근처)" if near_last else "배차의 절반"
        ev.append(self._ev_bus(r, f"운행 {fmt_min(r.first_min)}~{fmt_min(r.last_min)} · 배차 {r.term_min}분"))
        ev.append(self._ev_rule("bus.wait_model" if not near_last else "bus.worst_case", "추정"))
        ev.append(self._ev_rule("bus.ride_model", "추정"))
        # ★ 왕복 노선에서 길 건너 짝을 놓치고 한 바퀴 도는 답이 나오는지 본다
        det = self.rv("bus", "우회_경고")
        if span > len(self.bus.stops[r.route_id]) * det["비율"]:
            alt = self.bus.shorter_pair(r.route_id, a, b, det["근접_m"])
            if alt and alt[2] < span:
                warn.append(self.warn_msg("MOB_W_BUS_DETOUR", span=span,
                                          alt_from=alt[0]["station_nm"],
                                          alt_to=alt[1]["station_nm"], alt_span=alt[2]))
                ev.append(self._ev_rule("bus.우회_경고", "추정"))

        # 3) 승차 소요 = 구간 거리 합 ÷ 표정속도
        dep = now_min + wait
        dist = self.bus.distance_m(r.route_id, a["seq"], b["seq"])
        speed, basis, sgrade, swarn = self.bus_speed(r, day_type)
        warn += swarn
        ride = arrive = None
        if dist is None:
            warn.append(self.warn_msg("MOB_W_BUS_DIST_MISSING", route=nm,
                                      from_stop=a["station_nm"], to_stop=b["station_nm"]))
        elif speed:
            ride = round(dist / 1000 / speed * 60, 1)
            arrive = dep + math.ceil(ride)
            ev.append(self._ev_bus(r, f"{a['station_nm']}→{b['station_nm']} {dist:,}m ({span}정거장)"))
            ev.append(self._ev_rule(f"bus.표정속도 — {basis} {speed} km/h", sgrade))
        else:
            ev.append(self._ev_rule("bus.표정속도 — 값 없음", "근거없음"))
        return LegResult(idx, label, "feasible",
                         f"{fmt_min(dep)} 승차 예상 (대기 {wait}분 — {model})"
                         + ("" if ride is not None else " · 승차 소요 근거없음")
                         + f" · {a['station_nm']}(seq {a['seq']}) → {b['station_nm']}(seq {b['seq']})",
                         grade="추정" if ride is not None else "근거없음",
                         depart_min=dep, arrive_min=arrive,
                         wait_min=wait, ride_min=ride, ride_grade=sgrade,
                         warnings=warn, evidence=ev)


    def _rollover_relief(self, now_min, first_min):
        """운행일 연장 시각(24 시 이상)이 실은 **그날 아침 첫차 이전**인 경우.

        03:50 요청은 to_service_min 이 27:50 으로 올린다 — 전날 운행분의 연장이라 맞다.
        그런데 그 값만 보면 '막차(22:20) 이후'가 되어 '수단 교체' 라는 답이 나간다.
        실제로는 20분 뒤 04:10 첫차를 타면 된다. 벽시계로 되돌려 첫차와 비교한다.

        ★ 단, 첫차까지 남은 시간이 공백 상한을 넘으면 이 틀을 쓰지 않는다.
          24:50 요청(막차 24:46 을 4분 놓친 것)에 "286분 뒤 첫차를 기다리면 성립" 은
          맞는 말이지만 쓸모없는 답이고, **막차 경과 신호를 지워서** 대안 열거(F3)의 입구를 막는다.
          그 경우는 '막차 이후 → 수단 교체' 가 맞다.
        """
        if now_min < MIN_DAY or first_min is None:
            return None
        wall = now_min - MIN_DAY
        gap = first_min - wall
        if 0 < gap <= self.rv("service_window", "gap_max_min"):
            return wall, gap
        return None


    def bus_speed(self, r, day_type):
        """노선의 표정속도(km/h). 값_우선순위: 노선별 실측 > 노선유형별 통계 > 근거없음.

        ★ 순환 통계값(21.3)은 남산 01A·01B 에 쓰지 않는다 — 실측 15.3/17.8 과 -28%/-16% 어긋난다.
          통계값을 쓰면 충무로→남산서울타워(4.66km)가 13.1분으로 나오는데 실측으로는 18.3분이다.
          규칙 bus.표정속도.통계_금지_노선. 노선별 값이 들어오면 자동으로 풀린다.
        """
        S = self.R["bus"]["표정속도"]
        per = (S.get("노선별", {}).get("value") or {}).get(r.route_nm)
        if isinstance(per, dict):
            per = per.get(day_type) or per.get("weekday")
        if per:
            return per, "노선별 실측", "추정", []
        if r.route_nm in (S.get("통계_금지_노선", {}).get("value") or []):
            return None, None, "근거없음", [
                self.warn_msg("MOB_W_BUS_SPEED_BLOCKED_ROUTE", route=r.route_nm)]
        warn, t = [], r.route_type_nm
        if t == "심야":
            t = S["대용_심야"]["value"]
            warn.append(self.warn_msg("MOB_W_BUS_SPEED_PROXY_NIGHT", route=r.route_nm, proxy=t))
        elif t == "공항":
            t = S["대용_공항"]["value"]
            warn.append(self.warn_msg("MOB_W_BUS_SPEED_PROXY_AIRPORT", route=r.route_nm, proxy=t))
            warn.append(self.warn_msg("MOB_W_AIRPORT_FARE"))
        key = "holiday" if day_type == "holiday" else "weekday"
        v = (S["value"].get(key) or {}).get(t)
        if not v:
            return None, None, "근거없음", [
                self.warn_msg("MOB_W_BUS_SPEED_MISSING", route_type=r.route_type_nm)]
        warn.append(self.warn_msg("MOB_W_SPEED_NO_PEAK"))
        return v, f"{t} 유형 통계({key})", "추정", warn

    def _ev_bus(self, r, claim):
        return {"source_type": "db", "source_id": self.bus.source_id, "grade": "확정",
                "observed_at": self.bus.fetched_at, "claim": f"{r.route_nm}({r.route_type_nm}): {claim}"}


    # ── 대안 열거(F3) ──────────────────────────────────────────────────
    def lines_with(self, station):
        """그 역이 있는 노선들. 노선 교체 후보를 만들 때 쓴다."""
        if self._lines_of is None:
            self._lines_of = collections.defaultdict(set)
            for ln, L in self.lo.doc["lines"].items():
                for st in L["stations"]:
                    self._lines_of[st["station_nm"]].add(ln)
        return self._lines_of.get(station, set())

    def alternatives(self, case, idx, leg, now_min, day_type, is_sat, failed):
        """불가·탈락 구간의 대안을 **규칙 순서로 열거하고 같은 검증기에 재통과**시킨다.

        LLM 을 쓰지 않는다 — 후보 공간이 노선·수단·시각·포기 넷으로 닫혀 있고,
        규칙으로 만든 후보는 시간표로 즉시 검증된다(rules alternatives.LLM_없음).

        ★ 순위를 매기지 않는다. 총소요 등급이 추정인데 두 안의 차이가 배차 불확실성보다 작으면
          **추정값으로 매긴 순위는 그 자체가 추정**이다(rules alternatives.순위_미부여).
        """
        maxn = self.rv("alternatives", "최대_제시")
        radius = self.rv("alternatives", "정류장_반경_m")
        party = case.get("party", {}) or {}
        wlim = self._walk_limit(party)
        line, a, b = leg.get("line"), leg["from"], leg["to"]
        is_bus = leg.get("mode") == "bus"
        out, tried = [], []
        excluded = self.rv("bus", "route_type_제외") or []

        speed = self.R["measured_baseline"]["kakao_walk_speed_mps"]["value"]
        walk_min = lambda m: math.ceil(m / speed / 60) if m else 0

        def take(axis, label, newleg, at=None, walk_in=0, walk_out=0, note=None):
            """★ 접근·이탈 도보를 시각에 **반드시 넣는다**.

            라벨에 '도보 157m' 라고 적어 놓고 계산에서 빼면 도착이 낙관적으로 나온다 —
            2026-09-10 에 실제로 그렇게 냈다(N73 대안이 6분 이르게 나왔다).
            판정 경로와 소요 경로가 달랐던 것과 같은 실수다.
            """
            t = (at if at is not None else now_min) + walk_min(walk_in)
            r = (self.verify_leg_bus(idx, newleg, t, day_type)
                 if newleg.get("mode") == "bus"
                 else self.verify_leg(idx, newleg, t, day_type, is_sat))
            tried.append((axis, label, r.verdict))
            if r.verdict == "feasible":
                arr = r.arrive_min + walk_min(walk_out) if r.arrive_min is not None else None
                out.append({"axis": axis, "label": label, "leg": newleg,
                            "depart_min": r.depart_min, "arrive_min": arr,
                            "walk_in_min": walk_min(walk_in), "walk_out_min": walk_min(walk_out),
                            "grade": r.grade, "reason": r.reason, "note": note,
                            "warnings": r.warnings, "at": t})
            return r

        # ★ 버스 구간의 대안 (규칙 v0.4 · 19번 방). v0.3.1 까지는 세 축이 전부 `line`(지하철) 조건이라
        #   버스 구간이 불가이면 택시 하나만 남았다(MIX-03). 요청한 두 정류장 행을 좌표로 쓴다.
        #   ⓐ 출발시각_이동은 버스에 없다 — 정류장별 시각표가 없어 '다음 차'를 특정할 수 없고,
        #      첫차 이전·막차 이후는 완화 조건이 이미 시각을 말한다.
        bx = by = None
        if is_bus:
            bx, by = self._bus_stop_row(leg, "from"), self._bus_stop_row(leg, "to")
            if bx is None or by is None or bx.get("lat") is None or by.get("lat") is None:
                tried.append(("노선교체", f"버스 {leg.get('route')} 정류장 좌표 없음 — 후보를 만들 수 없다", "unknown"))
                bx = by = None

        for axis in self.rv("alternatives", "후보축_순서"):
            if len(out) >= maxn:
                break

            # ⓑ' 버스 노선 교체 — 같은 두 정류장(동일 반경 안)을 잇는 다른 노선
            if axis == "노선교체" and is_bus and bx is not None:
                same_r = self.rv("alternatives", "정류장_동일_반경_m")
                for r, x, y, span, da, db in self.bus.routes_between(
                        bx["lat"], bx["lng"], by["lat"], by["lng"], same_r):
                    if len(out) >= maxn:
                        break
                    if r.route_nm == str(leg["route"]):          # 자기_자신_제외
                        continue
                    if r.route_type_nm in excluded:
                        continue
                    take(axis,
                         f"버스 {r.route_nm}({r.route_type_nm}) 로 교체 — "
                         f"{x['station_nm']} → {y['station_nm']} {span}정거장"
                         + (f" (정류장까지 {da}m · 하차 후 {db}m)" if da or db else ""),
                         {"mode": "bus", "route": r.route_nm,
                          "from": x["station_nm"], "to": y["station_nm"]},
                         walk_in=da, walk_out=db)

            # ⓒ' 버스 → 지하철 수단 교체 — 정류장 근처 역끼리 한 노선으로 이어지는가
            elif axis == "수단교체" and is_bus and bx is not None and self.sc:
                A = self.sc.stations_near(bx["lat"], bx["lng"], radius)
                B = self.sc.stations_near(by["lat"], by["lng"], radius)
                pairs = []
                for da, sa in A:
                    for db, sb in B:
                        if sa["station_nm"] == sb["station_nm"]:
                            continue
                        # 접근·이탈 도보는 역 좌표가 아니라 **가장 가까운 출구**까지로 잰다(있을 때)
                        ea = self.ex.nearest(sa["station_nm"], bx["lat"], bx["lng"]) if self.ex else None
                        eb = self.ex.nearest(sb["station_nm"], by["lat"], by["lng"]) if self.ex else None
                        da2 = round(ea[0]) if ea else round(da)
                        db2 = round(eb[0]) if eb else round(db)
                        for ln in sorted(self.lines_with(sa["station_nm"]) & self.lines_with(sb["station_nm"])):
                            pairs.append((da2 + db2, ln, sa["station_nm"], sb["station_nm"], da2, db2))
                for _tot, ln, sa, sb, da, db in sorted(pairs):
                    if len(out) >= maxn:
                        break
                    if max(da, db) > wlim:
                        tried.append((axis, f"{ln} {sa}→{sb} (도보 {max(da, db)}m > 상한 {wlim}m)",
                                      "rejected_by_limit"))
                        continue
                    take(axis,
                         f"{ln} {sa}→{sb} 로 교체 — {sa}역까지 도보 {da}m({walk_min(da)}분) · "
                         f"하차 후 {db}m({walk_min(db)}분)",
                         {"line": ln, "from": sa, "to": sb}, walk_in=da, walk_out=db)

            # ⓐ 출발 시각 이동 — 같은 노선을 다시 쓸 수 있는 유일한 축
            elif axis == "출발시각_이동" and line:
                cands, _, _ = self.candidates(line, a, b, day_type)
                nxt = next((d for d, _v, _f in cands if d.min > now_min), None)
                if nxt:
                    take(axis, f"{fmt_min(nxt.min)} 출발로 미룸", leg, at=nxt.min)

            # ⓑ 노선 교체 — 같은 두 역을 잇는 다른 노선
            elif axis == "노선교체" and line:
                for ln in sorted(self.lines_with(a) & self.lines_with(b)):
                    if ln == line or len(out) >= maxn:      # 자기_자신_제외
                        continue
                    take(axis, f"{ln} 로 교체", {"line": ln, "from": a, "to": b})

            # ⓒ 수단 교체 — 역 앞 정류장에서 한 노선으로 이어지는 버스
            elif axis == "수단교체" and self.bus and self.sc and line:
                pa, pb = self.sc.get(line, a), self.sc.get(line, b)
                if pa and pb:
                    for r, x, y, span, da, db in self.bus.routes_between(
                            pa["lat"], pa["lng"], pb["lat"], pb["lng"], radius):
                        if len(out) >= maxn:
                            break
                        if r.route_type_nm in excluded:
                            continue
                        # 도보 상한을 넘는 후보는 내지 않는다 — 성립해도 이 일행이 못 걷는다
                        if max(da, db) > wlim:
                            tried.append((axis, f"버스 {r.route_nm} (도보 {max(da, db)}m > 상한 {wlim}m)",
                                          "rejected_by_limit"))
                            continue
                        take(axis,
                             f"버스 {r.route_nm}({r.route_type_nm}) — "
                             f"{x['station_nm']}까지 도보 {da}m({walk_min(da)}분) · {span}정거장 · "
                             f"하차 후 {db}m({walk_min(db)}분)",
                             {"mode": "bus", "route": r.route_nm,
                              "from": x["station_nm"], "to": y["station_nm"]},
                             walk_in=da, walk_out=db)

        return out[:maxn], tried, self._taxi()

    def _ev_tt(self, line, station, day_type, claim):
        return {"source_type": "db", "source_id": f"timetable_v1@{self.tt.fetched_at}",
                "grade": "확정", "observed_at": self.tt.fetched_at,
                "claim": f"{line} {station} {day_type}: {claim}"}

    def _ev_rule(self, name, grade):
        return {"source_type": "policy", "source_id": self.rules_src, "grade": grade,
                "observed_at": self.rules_at, "claim": name}

    # ── 지하철↔버스 환승 (규칙 v0.4 · 19번 방) ──────────────────────────
    def _walk_limit(self, party):
        return self.rv("limits", "walk_m", "infant_or_luggage" if (
            party.get("infant") or party.get("luggage")) else "default")

    def _taxi(self):
        # 택시 — 후보에서 빼지 않는다. 검토해서 탈락시킨 게 아니라 **모르는** 것이다
        return {"axis": "수단교체", "label": "택시", "verdict": "unknown",
                "reason": self.rv("alternatives", "택시"), "grade": "근거없음"}

    def _bus_stop_row(self, leg, which):
        """버스 구간의 승차('from')/하차('to') 정류장 행. 노선·정류장을 못 찾으면 None."""
        if self.bus is None:
            return None
        r = self.bus.route(str(leg["route"]))
        if r is None:
            return None
        seg = self.bus.segment(r.route_id, leg["from"], leg["to"])
        if seg is None:
            return None
        return seg[0] if which == "from" else seg[1]

    def _stop_station_walk(self, prev_leg, leg, party):
        """정류장 ↔ 역 환승 도보와 근접 상한. rules.transfer.stop_station_walk.

        거리 = 정류장 좌표 ↔ **그 역에서 가장 가까운 출구**(OSM, 추정) 직선. 출구가 없는 역은 역 좌표.
        도보 분 = 직선 × 우회계수 ÷ 1.04 m/s.  상한 판정은 **직선거리**로 limits.walk_m 과 비교한다(13번 §4).
        ★ 상한 ±경계값(20 m) 안이면 출구 좌표 오차가 판정을 뒤집을 수 있어 **근거없음(unknown)** 으로 낸다.
        ★ 좌표가 없으면(수집 밖 노선·정류장) 도보 0분·근거없음 — 종전 fallback 과 같되 경고 코드로 드러낸다.
        """
        S = self.R["transfer"]["stop_station_walk"]
        factor = S["detour_factor"]["value"]
        margin = S["boundary_m"]["value"]
        speed = self.R["measured_baseline"]["kakao_walk_speed_mps"]["value"]
        wlim = self._walk_limit(party)
        if leg.get("mode") == "bus":                 # 지하철 → 버스
            stop, st_line, st_nm = self._bus_stop_row(leg, "from"), prev_leg.get("line"), prev_leg["to"]
        else:                                        # 버스 → 지하철
            stop, st_line, st_nm = self._bus_stop_row(prev_leg, "to"), leg.get("line"), leg["from"]
        stop_nm = stop["station_nm"] if stop else (leg["from"] if leg.get("mode") == "bus" else prev_leg["to"])
        label = f"환승 정류장 {stop_nm} ↔ {st_line} {st_nm}"
        src = {"source_type": "db", "source_id": (self.ex.source_id if self.ex else "osm_subway_entrance"),
               "grade": "추정", "observed_at": (self.ex.built_at if self.ex else None)}

        # 좌표
        pt = self.sc.get(st_line, st_nm) if self.sc else None
        if stop is None or stop.get("lat") is None or pt is None:
            why = ("정류장 좌표가 없다" if stop is None or stop.get("lat") is None
                   else f"{st_line} {st_nm} 역 좌표가 없다")
            return {"verdict": "feasible", "label": label, "walk_min": 0, "grade": "근거없음",
                    "dist_m": None, "walk_m": None, "factor": factor, "reason": why, "relief": None,
                    "warnings": [self.warn_msg("MOB_W_TRANSFER_COORD_MISSING", reason=why)],
                    "evidence": [{"source_type": "policy", "source_id": self.rules_src, "grade": "근거없음",
                                  "observed_at": self.rules_at,
                                  "claim": f"transfer.stop_station_walk — {why} → 도보 0분"}]}
        near = self.ex.nearest(st_nm, stop["lat"], stop["lng"]) if self.ex else None
        if near:
            dist, ex = near
            where = f"{st_nm}역 {ex.get('ref') or '?'}번 출구"
            src["claim"] = (f"정류장 {stop_nm} ↔ {where} 직선 {dist:,.0f}m "
                            f"(출구 귀속 {ex.get('attrib')})")
        else:
            dist = meters(stop["lat"], stop["lng"], pt["lat"], pt["lng"])
            where = f"{st_nm}역 (출구 없음 → 역 좌표)"
            src = {"source_type": "db", "source_id": "station_coords", "grade": "추정",
                   "observed_at": self.sc.built_at,
                   "claim": f"정류장 {stop_nm} ↔ {st_nm} 역 좌표 직선 {dist:,.0f}m (OSM 출구 없음)"}
        walk_m = dist * factor
        walk_min = round(walk_m / speed / 60, 1)
        rule_ev = self._ev_rule("transfer.stop_station_walk", "추정")

        # 근접 상한 — 직선거리로 본다
        if abs(dist - wlim) <= margin:
            why = (f"정류장 {stop_nm} ↔ {where} 직선 {dist:,.0f}m 가 도보 상한 {wlim:,}m 의 "
                   f"±{margin}m 안이다 — 출구 좌표 오차가 판정을 뒤집을 수 있어 판정하지 않는다")
            return {"verdict": "unknown", "label": label, "walk_min": walk_min, "grade": "근거없음",
                    "dist_m": dist, "walk_m": walk_m, "factor": factor, "reason": why,
                    "relief": "정류장 또는 역을 실제 위치로 다시 확인한다",
                    "warnings": [self.warn_msg("MOB_W_TRANSFER_NEAR_WALK_LIMIT", stop=stop_nm,
                                               station=st_nm, dist_m=round(dist), limit_m=wlim)],
                    "evidence": [dict(src, grade="근거없음"), rule_ev]}
        if dist > wlim:
            nearby = self.sc.stations_near(stop["lat"], stop["lng"],
                                           self.rv("alternatives", "정류장_반경_m")) if self.sc else []
            hint = " · ".join(f"{v['station_nm']}({v['line']}, {d:,.0f}m)" for d, v in nearby[:3])
            why = (f"정류장 {stop_nm} ↔ {where} 직선 {dist:,.0f}m — 도보 상한 {wlim:,}m 를 넘어 "
                   f"환승할 수 없다")
            return {"verdict": "infeasible", "label": label, "walk_min": walk_min, "grade": "추정",
                    "dist_m": dist, "walk_m": walk_m, "factor": factor, "reason": why,
                    "relief": (f"정류장 근처 역은 {hint} — 그 역에서 타는 구간으로 다시 잡는다"
                               if hint else f"정류장 {stop_nm} 반경 안에 역이 없다 — 수단을 바꾼다"),
                    "warnings": [], "evidence": [src, rule_ev]}
        return {"verdict": "feasible", "label": label, "walk_min": walk_min, "grade": "추정",
                "dist_m": dist, "walk_m": walk_m, "factor": factor, "reason": None, "relief": None,
                "warnings": [], "evidence": [src, rule_ev]}

    # ── 케이스 한 건 ──
    def verify_case(self, case):
        d = _date.fromisoformat(case["date"])
        day_type = day_type_of(d, self.holidays)
        is_sat = d.weekday() == 5
        stage = case.get("stage", "planning")
        buffer_min = self.rv("buffer", "by_stage", stage)
        party = case.get("party", {}) or {}
        first_visit = case.get("first_visit", True)

        # ★ 이슈 조건. 코어의 current_state.replan 자리이고 지금은 케이스 JSON 이 대신 준다.
        #   모르는 kind 를 조용히 무시하지 않는다 — 무시하면 "이슈를 넣었는데 판정이 그대로"가 된다.
        self.disr = case.get("disruptions") or []
        for d in self.disr:
            if d.get("kind") not in self.DISR_KINDS:
                raise SystemExit(f"[{case.get('id')}] 모르는 이슈 kind 다: {d.get('kind')!r} "
                                 f"(쓸 수 있는 것: {', '.join(self.DISR_KINDS)})")
            if d["kind"] == "edge_closed" and len(d.get("between") or []) != 2:
                raise SystemExit(f"[{case.get('id')}] edge_closed 는 between 에 두 역이 필요하다")

        now = to_service_min(case.get("depart_at"))
        if now is None:
            raise SystemExit(f"[{case.get('id')}] depart_at 이 없다. 도착 역산은 아직 미구현이다.")
        arrive_by = to_service_min(case.get("arrive_by"))

        legs, warns, ev = [], [], []
        transfers = 0
        large = set(self.R["transfer"]["large_station_addition_min"]["stations"])
        prev_line = None
        for i, leg in enumerate(case["legs"]):
            mode = leg.get("mode", "subway")
            if mode not in ("subway", "bus"):
                raise SystemExit(f"[{case.get('id')}] 모르는 수단이다: mode={mode}")
            if prev_line is not None:
                transfers += 1
                st = leg.get("from")
                # ★ 환승역이 무정차면 갈아탈 수 없다. 출발·도착역 검사(verify_leg)로는 안 잡힌다 —
                #   여기서는 그 역이 앞 구간의 '도착'이자 뒤 구간의 '출발'이라 둘 다 통과해 버린다.
                dsk = (self._disr("station_skip", line=prev_line, station=st)
                       or self._disr("station_skip", line=leg.get("line"), station=st))
                if dsk:
                    legs.append(LegResult(i, f"환승 {st}", "infeasible",
                                          f"{st} 에 서지 않는 열차가 있어 환승할 수 없다 "
                                          f"({self._disr_label(dsk)})",
                                          grade=dsk.get("grade", "추정")))
                    return self._finish(
                        case, day_type, legs, "infeasible",
                        f"{st} 환승이 무정차로 막힌다 ({self._disr_label(dsk)})",
                        dsk.get("grade", "추정"), None, None,
                        f"{st} 말고 다른 역에서 갈아타거나 수단을 바꾼다", warns,
                        ev + [self._ev_disr(dsk, f"{st} 무정차")])
                # 길찾기 가산은 **초행일 때만**이다(rules.transfer.wayfinding_addition_min.적용조건).
                # 1순위 고객이 첫 방문 인바운드라 기본값은 true 로 둔다.
                wf = self.rv("transfer", "wayfinding_addition_min") if first_visit else 0
                # ★ 환승 도보는 역별 실제 거리로 잰다(rules.transfer.walk_distance).
                #   13개 역 일괄 +2분은 superseded — 거리표에 없는 환승의 fallback 으로만 남는다.
                cur_line = leg.get("line") or f"버스{leg.get('route')}"
                prev_leg = case["legs"][i - 1]
                mixed = (mode == "bus") != (prev_leg.get("mode", "subway") == "bus")
                label, w, tg, twarn = f"환승 {st}", None, "추정", []
                if mixed:
                    # ★ 지하철↔버스 환승 (규칙 v0.4 · 19번 방 · rules.transfer.stop_station_walk).
                    #   v0.3.1 까지는 tw.lookup 이 지하철↔지하철만 타서 **도보 0분 + 길찾기 1분**으로
                    #   붙였고 정류장↔역 근접을 아예 보지 않았다 — MIX-04 가 성수 정류장 → 여의도역 환승을
                    #   1분으로 성립시켰다. 정류장 좌표 ↔ 그 역의 가장 가까운 출구(OSM, 추정) 직선거리로 잰다.
                    ss = self._stop_station_walk(prev_leg, leg, party)
                    label, tg, twarn, tev = ss["label"], ss["grade"], ss["warnings"], ss["evidence"]
                    if ss["verdict"] != "feasible":
                        warns += twarn
                        ev += tev
                        legs.append(LegResult(i, label, ss["verdict"], ss["reason"],
                                              grade=tg, warnings=twarn, evidence=list(tev)))
                        res = self._finish(case, day_type, legs, ss["verdict"], ss["reason"],
                                           worst(*[x.grade for x in legs]), None, None,
                                           ss["relief"], warns, ev)
                        if ss["verdict"] == "infeasible" and not case.get("no_alternatives"):
                            # 정류장과 역이 떨어져 있는 환승은 「이 구간의 대안」이 아니라 구간 자체를
                            # 다시 잡을 일이다 — 노선·시각을 바꿔도 같은 자리에서 막힌다. 택시만 남긴다(모르는 것).
                            res.alternatives, res.alt_tried, res.taxi = [], [], self._taxi()
                        return res
                    walk = ss["walk_min"]
                    dist_txt = (f"({ss['dist_m']:,.0f}m 직선×{ss['factor']:g} = {ss['walk_m']:,.0f}m)"
                                if ss["dist_m"] is not None else "")
                else:
                    # 버스↔버스 환승은 거리표에 없다 — 종전대로 0분·근거없음(MOB_W_TRANSFER_WALK_ZERO). 19번 범위 밖.
                    w = (self.tw.lookup(st, prev_line, cur_line)
                         if self.tw and leg.get("line") and not prev_line.startswith("버스") else None)
                    if w is not None and w.min is not None:
                        walk = w.min
                        tev = {"source_type": "db", "source_id": "transfer_walk_v1",
                               "grade": w.grade, "observed_at": w.checked_at, "claim": w.reason}
                        if w.basis == "station_max":
                            twarn.append(self.warn_msg("MOB_W_TRANSFER_WALK_STATION_MAX",
                                                       reason=w.reason))
                    else:
                        fb = self.rv("transfer", "large_station_addition_min")
                        walk = fb if st in large else 0
                        tg = "근거없음"
                        why = w.reason if w is not None else "환승 거리표를 읽지 못했다"
                        twarn.append(
                            self.warn_msg("MOB_W_TRANSFER_WALK_FALLBACK", reason=why, fallback_min=fb)
                            if st in large else
                            self.warn_msg("MOB_W_TRANSFER_WALK_ZERO", reason=why))
                        tev = {"source_type": "policy", "source_id": self.rules_src,
                               "grade": "근거없음", "observed_at": self.rules_at,
                               "claim": "transfer.walk_distance 조회 실패 → fallback"}
                    dist_txt = f"({w.distance_m:g}m)" if w and w.distance_m else ""
                    tev = [tev]
                add = math.ceil(walk + wf + int(leg.get("walk_min", 0)))
                now += add
                warns += twarn
                ev += tev
                legs.append(LegResult(
                    i, label, "feasible",
                    f"도보 {walk:g}분{dist_txt}"
                    + (f" + 길찾기 {wf}분" if wf else " (초행 아님)")
                    + f" = +{add}분", grade=tg, warnings=twarn))
            r = (self.verify_leg_bus(i, leg, now, day_type) if mode == "bus"
                 else self.verify_leg(i, leg, now, day_type, is_sat))
            legs.append(r)
            warns += r.warnings
            ev += r.evidence
            if r.verdict != "feasible":
                res = self._finish(case, day_type, legs, r.verdict, r.reason,
                                   worst(*[x.grade for x in legs]), None, None,
                                   r.relief, warns, ev)
                if r.verdict == "infeasible" and not case.get("no_alternatives"):
                    res.alternatives, res.alt_tried, res.taxi = self.alternatives(
                        case, i, leg, now, day_type, is_sat, r)
                return res
            if r.arrive_min is None:                        # 소요 판단 불가
                # 설계서: "카카오 실패 → 성립 여부는 내고 소요는 판단 불가".
                # 마지막 구간이고 도착 제약이 없으면 **성립**으로 내되 도착 시각을 만들지 않는다.
                # 뒤에 구간이 더 있거나 도착 시각을 대조해야 하면 그때는 근거없음이다.
                tail = (i == len(case["legs"]) - 1) and arrive_by is None
                return self._finish(
                    case, day_type, legs, "feasible" if tail else "unknown",
                    f"{r.label} 은 그 시각 편성이 있다({fmt_min(r.depart_min)} 출발) — "
                    f"승차 소요를 낼 수 없어 도착 시각은 내지 않는다"
                    if tail else
                    f"{r.label} 의 승차 소요를 낼 수 없어 이후 구간의 시각을 이어 갈 수 없다 "
                    f"(그 구간 편성은 있다: {fmt_min(r.depart_min)} 출발)",
                    "근거없음", None, None, None, warns, ev)
            now = r.arrive_min
            prev_line = leg.get("line") or f"버스{leg.get('route')}"

        # 동행 상한 — 성립하더라도 이 일행에게 무리인가
        lim = self.rv("limits", "transfers", "default")
        which = "default"
        for k in ("infant", "elderly", "fatigue_high"):
            if party.get(k):
                v = self.rv("limits", "transfers", k)
                if v < lim:
                    lim, which = v, k
        if transfers > lim:
            ev.append(self._ev_rule(f"limits.transfers.{which}", "추정"))
            return self._finish(case, day_type, legs, "rejected_by_limit",
                                f"환승 {transfers}회로 상한({which} {lim}회)을 넘는다 — "
                                f"성립하지만 이 일행에게는 무리다",
                                worst(*[x.grade for x in legs]), now, None,
                                "환승이 적은 노선으로 교체", warns, ev)

        slack = None
        if arrive_by is not None:
            slack = arrive_by - (now + buffer_min)
            ev.append(self._ev_rule(f"buffer.by_stage.{stage}", "추정"))
            if slack < 0:
                return self._finish(case, day_type, legs, "infeasible",
                                    f"도착 추정 {fmt_min(now)} + 버퍼 {buffer_min}분이 "
                                    f"필요 시각 {fmt_min(arrive_by)} 를 {-slack}분 넘긴다",
                                    worst(*[x.grade for x in legs]), now, slack,
                                    f"출발을 {-slack}분 당기면 성립", warns, ev)
        return self._finish(case, day_type, legs, "feasible",
                            f"도착 추정 {fmt_min(now)}" +
                            (f" · 여유 {slack}분(버퍼 {buffer_min}분 뒤)" if slack is not None else ""),
                            worst(*[x.grade for x in legs]), now, slack, None, warns, ev)

    def _finish(self, case, day_type, legs, verdict, reason, grade,
                arrive, slack, relief, warns, ev):
        return CaseResult(case.get("id", "?"), verdict, reason, grade, legs,
                          arrive, slack, relief, warns, ev, day_type)


# ── 출력 ──────────────────────────────────────────────────────────────────
MARK = {"feasible": "성립", "infeasible": "불가",
        "rejected_by_limit": "탈락", "unknown": "근거없음"}


def show(case, res, verbose=False):
    print(f"\n[{res.id}] {case.get('note','')}")
    print(f"  {case['date']}({res.day_type}) {case.get('depart_at')} 출발"
          + (f" · {case['arrive_by']} 도착 필요" if case.get("arrive_by") else ""))
    for d in case.get("disruptions") or []:
        w = {"line_closed": d.get("line"), "route_closed": f"버스 {d.get('route')}",
             "station_skip": f"{d.get('line')} {d.get('station')}",
             "edge_closed": f"{d.get('line')} {'–'.join(d.get('between') or [])}"}.get(d.get("kind"))
        print(f"  ◆ 이슈 {w} — {d.get('note') or d.get('kind')} "
              f"[{d.get('grade','추정')}] {d.get('source','core.current_state.replan')}")
    print(f"  판정 {MARK[res.verdict]} [{res.grade}] — {res.reason}")
    if res.relief:
        print(f"  완화 조건: {res.relief}")
    for w in dedup_warn(res.warnings):
        print(f"  ! [{w['code']}] {w['text']}")
    if res.taxi:
        print(f"  대안 {len(res.alternatives)}개 (순위 없음 — 총소요 등급이 추정이라 순위 자체가 추정이 된다)")
        for al in res.alternatives:
            arr = f" → 도착 {fmt_min(al['arrive_min'])}" if al["arrive_min"] is not None else " → 도착 미상"
            w = ""
            if al.get("walk_in_min") or al.get("walk_out_min"):
                w = f" (도보 {al.get('walk_in_min',0)}+{al.get('walk_out_min',0)}분 포함)"
            print(f"    · [{al['axis']}] {al['label']} — {fmt_min(al['depart_min'])} 출발{arr}{w} [{al['grade']}]")
            # 대안의 경고도 보인다 — 공항버스 별도 요금처럼 **그 대안을 고를지 바꾸는** 말이
            # 여기 있는데 안 찍혀 안 보였다(2026-09-10). 케이스 경고와 겹치는 줄은 뺀다.
            seen_codes = {x["code"] for x in res.warnings}
            for aw in dedup_warn(al.get("warnings")):
                if aw["code"] not in seen_codes:
                    print(f"      ! [{aw['code']}] {aw['text']}")
        if res.taxi:
            print(f"    · [수단교체] 택시 — {res.taxi['reason']} [근거없음]")
        if verbose and res.alt_tried:
            print("    열거한 후보: " + ", ".join(f"{lb}={MARK[v]}" for _ax, lb, v in res.alt_tried))
    if verbose:
        for l in res.legs:
            extra = ""
            if l.ride_min is not None:
                extra = f" · 승차 {l.ride_min:g}분[{l.ride_grade}] → 도착 {fmt_min(l.arrive_min)}"
            print(f"    - {l.label}: {MARK[l.verdict]} {l.reason}{extra}")
            if l.dropped:
                print(f"      거른 행: " + ", ".join(f"{k} {v}" for k, v in sorted(l.dropped.items())))
        for e in res.evidence:
            print(f"      · [{e['grade']}] {e['source_id']} — {e['claim']}")


def main():
    ap = argparse.ArgumentParser(description="이동 모듈 시각 검증기 v2 (지하철)")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--timetable")
    ap.add_argument("--order")
    ap.add_argument("--transfer-walk")
    ap.add_argument("--bus-route")
    ap.add_argument("--bus-stops")
    ap.add_argument("--station-coords")
    ap.add_argument("--station-exits")
    ap.add_argument("--rules", default=str(REPO / "config" / "mobility" / "rules_v0.3.json"))
    ap.add_argument("--holidays", default=str(REPO / "config" / "mobility" / "holidays_2026_2027.json"))
    ap.add_argument("--case", help="이 id 만 돌린다")
    ap.add_argument("--check-expect", action="store_true", help="expect 와 대조하고 MISS 면 종료코드 1")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--json", help="판정 결과를 이 경로에 저장")
    args = ap.parse_args()

    if not all((args.timetable, args.order, args.transfer_walk, args.bus_route,
                args.bus_stops, args.station_coords, args.station_exits)):
        from scripts.collect._paths import PROCESSED
        args.timetable = args.timetable or str(PROCESSED / "mobility" / "timetable_v1.jsonl")
        args.order = args.order or str(PROCESSED / "mobility" / "line_station_order_v1.json")
        args.transfer_walk = args.transfer_walk or str(PROCESSED / "mobility" / "transfer_walk_v1.json")
        args.bus_route = args.bus_route or str(PROCESSED / "mobility" / "bus_route_v1.jsonl")
        args.bus_stops = args.bus_stops or str(PROCESSED / "mobility" / "bus_stops_v1.jsonl")
        args.station_coords = args.station_coords or str(PROCESSED / "mobility" / "station_coords.json")
        args.station_exits = args.station_exits or str(PROCESSED / "mobility" / "station_exits_v1.json")

    doc = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    cases = doc["cases"] if isinstance(doc, dict) else doc
    if args.case:
        cases = [c for c in cases if c.get("id") == args.case]
        if not cases:
            raise SystemExit(f"케이스 {args.case} 가 없다")

    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    holidays = set(json.loads(Path(args.holidays).read_text(encoding="utf-8"))["holidays"])
    lo = LineOrder.load(args.order)
    tw = TransferWalk.load(args.transfer_walk,
                           rules["measured_baseline"]["kakao_walk_speed_mps"]["value"])
    bus = BusRoutes.load(args.bus_route, args.bus_stops)
    sc = StationCoords.load(args.station_coords)
    ex = StationExits.load(args.station_exits)

    # 시간표는 케이스에 나오는 (노선, 역) 만 올린다 — 46만 행을 통째로 들지 않는다.
    # ★ 19번 방(2026-09-19): 대안이 쓸 (노선, 역) 도 같이 올린다. 종전에는 케이스 구간의 노선만 올려서
    #   ⓑ 노선교체(다른 노선)와 버스 구간의 수단교체(지하철) 후보가 시간표 없음 → 근거없음으로 죽었다.
    #   런타임(runtime.py)은 전체를 상주시키므로 이 차이는 회귀에서만 있었다.
    wanted = {(l["line"], nm) for c in cases for l in c["legs"] if l.get("line")
              for nm in (l["from"], l["to"])}
    lines_of = collections.defaultdict(set)
    for ln, L in lo.doc["lines"].items():
        for st in L["stations"]:
            lines_of[st["station_nm"]].add(ln)
    radius = rules["alternatives"]["정류장_반경_m"]["value"]
    for c in cases:
        for l in c["legs"]:
            if l.get("line"):
                for ln in lines_of[l["from"]] & lines_of[l["to"]]:
                    wanted |= {(ln, l["from"]), (ln, l["to"])}
            elif l.get("mode") == "bus" and bus and sc:
                r = bus.route(str(l["route"]))
                seg = bus.segment(r.route_id, l["from"], l["to"]) if r else None
                if seg:
                    for row in seg[:2]:
                        for _d, v in sc.stations_near(row["lat"], row["lng"], radius):
                            wanted |= {(ln, v["station_nm"]) for ln in lines_of[v["station_nm"]]}
    tt = Timetable.load(args.timetable, wanted)
    print(f"시간표 {args.timetable}")
    print(f"  유효 출발 {tt.rows:,}행 · 출발없음 {tt.skipped_no_dep:,}행 · "
          f"역 {len(tt.stations)} · 수집 {tt.fetched_at}")
    print(f"역 순서 {lo.built_at} · 규칙 {rules['rules_version']}({rules['effective_date']})")
    if tw is None:
        print("  ! 환승 거리표(transfer_walk_v1.json)를 못 찾았다 — 환승 도보는 근거없음으로 낸다")
    else:
        print(f"환승 거리표 {tw.built_at} · {len(tw.pairs)}쌍 · {len(tw.stations)}역")
    if bus:
        print(f"버스 {bus.fetched_at} · {len(bus.by_id)}노선 · 정류장 {sum(len(x) for x in bus.stops.values()):,}행")
    if sc:
        print(f"역 좌표 {sc.built_at} · {len(sc.by_key)}역")
    if ex is None:
        print("  ! 역 출구표(station_exits_v1.json)를 못 찾았다 — 정류장↔역 환승은 역 좌표로 잰다")
    else:
        print(f"역 출구 {ex.built_at} · {len(ex.exits)}역명 · {sum(len(v) for v in ex.exits.values()):,}출구 [{ex.grade}]")
    v = Verifier(tt, lo, rules, holidays, tw, bus, sc, ex)
    results, miss = [], []
    for c in cases:
        r = v.verify_case(c)
        results.append(r)
        show(c, r, args.verbose)
        if args.check_expect:
            # ★ 판정값만 대조하면 부족하다. 2026-09-10 의 순환선 버그는 판정이 계속 '성립'이었고
            #   **도착 시각만** 73.3분으로 틀려 있었다. expect_arrive 가 그걸 잡는다.
            if c.get("expect") and c["expect"] != r.verdict:
                miss.append((c["id"], MARK[c["expect"]], MARK[r.verdict]))
                print(f"  >> MISS 기대 {MARK[c['expect']]} / 판정 {MARK[r.verdict]}")
            # ★ 완화 조건도 대조한다. 2026-09-10 에 24:50 요청이 '불가' 는 맞는데 완화 조건이
            #   "286분 뒤 첫차를 기다리면 성립" 으로 나간 적이 있다(막차를 4분 놓친 것인데).
            #   판정값만 보는 대조는 그걸 통과시켰다.
            am = c.get("expect_alt_min")
            if am is not None and len(r.alternatives) < am:
                miss.append((c["id"], f"대안 {am}개 이상", f"{len(r.alternatives)}개"))
                print(f"  >> MISS 대안 {am}개 이상 기대 / 실제 {len(r.alternatives)}개")
            # ★ 2026-09-14 신설 — 「없어야 한다」를 말할 축이 하나도 없었다.
            #   expect_alt_min/axis/arrive/warn_codes 는 전부 **있어야 한다**만 본다. 그래서
            #   `expect_alt_min: 0` 으로 잠근 척한 케이스 셋(ISSUE-06·ALT-03·ALT-04)은
            #   len < 0 이 영원히 거짓이라 **한 번도 검사된 적이 없다.**
            #   실제로 그 구멍으로 TOUR12 가 ISSUE-01 의 대안에 들어왔고 회귀 85건은 전부 통과했다.
            ax = c.get("expect_alt_max")
            if ax is not None and len(r.alternatives) > ax:
                got = [x["label"] for x in r.alternatives]
                miss.append((c["id"], f"대안 {ax}개 이하", f"{len(r.alternatives)}개: {got}"))
                print(f"  >> MISS 대안 {ax}개 이하 기대 / 실제 {len(r.alternatives)}개 — {got}")
            aar = c.get("expect_alt_arrive")
            if aar:
                got = [fmt_min(x["arrive_min"]) for x in r.alternatives]
                if fmt_min(to_service_min(aar)) not in got:
                    miss.append((c["id"], f"대안 도착 {aar}", str(got)))
                    print(f"  >> MISS 대안 도착 {aar} 가 없다 — 실제 {got}")
            aa = c.get("expect_alt_axis")
            if aa and aa not in [x["axis"] for x in r.alternatives]:
                miss.append((c["id"], f"대안 축 '{aa}'", str([x["axis"] for x in r.alternatives])))
                print(f"  >> MISS 대안 축 '{aa}' 가 없다")
            want = c.get("expect_relief_contains")
            if want and want not in (r.relief or ""):
                miss.append((c["id"], f"완화 조건에 '{want}'", f"'{r.relief}'"))
                print(f"  >> MISS 완화 조건에 '{want}' 가 없다 — 실제: {r.relief}")
            # ★ 경고 축(2026-09-13). 문장이 아니라 **코드**로 건다 — 문구를 다듬어도 회귀가 안 깨진다.
            #   케이스 경고와 대안 경고를 합쳐서 본다(공항 요금처럼 대안에만 붙는 것이 있다).
            wc = c.get("expect_warn_codes")
            if wc:
                got = {w["code"] for w in (r.warnings or [])}
                for al in (r.alternatives or []):
                    got |= {w["code"] for w in (al.get("warnings") or [])}
                lack = [x for x in wc if x not in got]
                if lack:
                    miss.append((c["id"], f"경고 {lack}", str(sorted(got))))
                    print(f"  >> MISS 경고 {lack} 가 없다 — 실제 {sorted(got)}")
            ea = to_service_min(c.get("expect_arrive")) if c.get("expect_arrive") else None
            if ea is not None and ea != r.arrive_min:
                miss.append((c["id"], f"도착 {fmt_min(ea)}", f"도착 {fmt_min(r.arrive_min)}"))
                print(f"  >> MISS 도착 기대 {fmt_min(ea)} / 판정 {fmt_min(r.arrive_min)}")

    tally = collections.Counter(r.verdict for r in results)
    print("\n" + "─" * 60)
    print("판정 " + " · ".join(f"{MARK[k]} {tally[k]}" for k in VERDICTS if tally[k]))
    if args.check_expect:
        print(f"기대 대조 — 케이스 {len(cases)}건 중 어긋남 {len(miss)}건")
        for i, e, g in miss:
            print(f"  MISS {i}: 기대 {e} → {g}")
    if args.json:
        Path(args.json).write_text(json.dumps(
            [r.__dict__ for r in results], ensure_ascii=False, default=lambda o: o.__dict__,
            indent=1), encoding="utf-8")
        print(f"판정 결과 → {args.json}")
    sys.exit(1 if miss else 0)


if __name__ == "__main__":
    main()
