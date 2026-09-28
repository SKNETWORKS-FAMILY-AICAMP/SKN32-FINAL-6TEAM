"""요식이 제 기능을 하는지 한 번에 본다 — 점검표.

왜 만드는가.
    시험 1,000여 건이 초록이어도 「그래서 식당 판정이 되는가」는 한눈에 안 보인다.
    플로우의 단계마다 실제 원장에 물어 보고, 되는지 안 되는지를 한 줄씩 적는다.

무엇을 보는가 (플로우 순서)
    1  데이터         가게·좌표·영업시간·분류가 찼는가, 정답셋 정확도
    1-2 넣은 데이터   파일(관광공사 · 비건 목록 · 정답셋 · 공휴일 · 검수)이 원장에 다 들어갔는가
    2  판정           그 시각에 여는가 — 영업 중 · 영업 전 · 브레이크 · 정기휴무 · 모름 · 마감 임박
    3  코어 연결      코어 장소로 물으면 우리 가게로 이어지는가, 모르는 장소는 「모름」인가
    4  대체 장소      문 닫은 집의 대안이 나오는가, 대안은 그 시각에 여는가
    5  확인 시점      방문 60분·20분 전에만 물을 때라고 하는가
    6  알림 중복      같은 방문에 같은 알림을 두 번 만들지 않는가
    7  식이 조건      비건 · 할랄 식당이 있는가, 조건을 걸고 찾은 대안이 그 조건에 맞는가
    8  자동 시험      요식 unit · integration 시험

가게는 원장에서 조건에 맞는 곳을 골라 쓴다. 이름을 박지 않는다 — 데이터가 바뀌어도 돈다.
쓰기는 6 한 가지이며 되돌린다(ROLLBACK). 원장을 바꾸지 않는다.

    python scripts/dining/check_dining.py                 rebuild.py 가 세운 dining_rebuild 를 본다
    python scripts/dining/check_dining.py --no-tests      시험은 빼고 원장만
    python scripts/dining/check_dining.py --save          data/dining/_build/점검표.md 로도 남긴다
    DINING_DSN=postgresql://postgres@localhost:5433/다른DB   다른 DB 를 본다
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone

import psycopg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # final_project_cs
sys.path.insert(0, ROOT)

DSN = os.environ.get("DINING_DSN", "postgresql://postgres@localhost:5433/dining_rebuild")
KST = timezone(timedelta(hours=9))
SAVE = os.path.join(ROOT, "data", "dining", "_build", "점검표.md")

#: 기준. 넘으면 통과다. 숫자를 바꿀 때는 이유를 같이 적는다.
MIN_PLACES = 1000
MIN_COORD = 0.99
MIN_HOURS = 0.95
MIN_ACCURACY = 0.95


class Sheet:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, str]] = []   # (단계, 표시, 항목, 근거)

    def add(self, step: str, ok: bool | None, item: str, detail: str = "") -> None:
        mark = "✅" if ok is True else "❌" if ok is False else "⚠️"
        self.rows.append((step, mark, item, detail))

    def counts(self) -> tuple[int, int, int]:
        marks = [r[1] for r in self.rows]
        return marks.count("✅"), marks.count("❌"), marks.count("⚠️")


def next_weekday(weekday: int, start: date) -> date:
    """start 다음부터 그 요일(월=1 … 일=7)의 첫 날."""
    d = start + timedelta(days=1)
    while d.isoweekday() != weekday:
        d += timedelta(days=1)
    return d


def at(d: date, minute: int) -> datetime:
    return datetime.combine(d, time(0), KST) + timedelta(minutes=minute)


def hhmm(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def plain_day(cur, start: date) -> date:
    """공휴일이 아닌 평일(수요일). 명절 규칙이 판정에 끼지 않게."""
    d = next_weekday(3, start)
    while True:
        cur.execute("SELECT 1 FROM dining.dn_holiday_stub WHERE holiday_date = %s", (d,))
        if cur.fetchone() is None:
            return d
        d = next_weekday(3, d)


# ──────────────────────────────────────────────────────────────
# 1 데이터
# ──────────────────────────────────────────────────────────────

def check_data(cur, s: Sheet) -> None:
    step = "1 데이터"
    cur.execute("SELECT count(*), count(lat), count(category) FROM dining.dn_place")
    total, coord, cat = cur.fetchone()
    # 영업시간은 관광공사 가게로 잰다. 비건 목록은 검수 시트로 들어오며 1-2 에서 따로 본다.
    cur.execute("""SELECT count(DISTINCT sr.place_uid),
                          count(DISTINCT sr.place_uid) FILTER (WHERE EXISTS (
                              SELECT 1 FROM dining.dn_hours_rule r
                              WHERE r.place_uid = sr.place_uid AND r.retired_at IS NULL))
                   FROM dining.dn_source_record sr WHERE sr.source_code = 'tourapi_kor_food'""")
    tour, hours = cur.fetchone()
    s.add(step, total >= MIN_PLACES, "가게 수", f"{total:,}곳 (기준 {MIN_PLACES:,})")
    s.add(step, total and coord / total >= MIN_COORD, "좌표",
          f"{coord:,}/{total:,} = {coord / total:.1%} (기준 {MIN_COORD:.0%})")
    s.add(step, tour and hours / tour >= MIN_HOURS, "영업시간 규칙 (관광공사 가게)",
          f"{hours:,}/{tour:,} = {hours / tour:.1%} (기준 {MIN_HOURS:.0%})")
    s.add(step, cat == total, "대표 분류", f"{cat:,}/{total:,}곳에 붙음")

    cur.execute("""SELECT verdict, count(*) FROM dining.dn_quality_result
                   WHERE run_id = (SELECT run_id FROM dining.dn_quality_run
                                   ORDER BY started_at DESC LIMIT 1)
                   GROUP BY 1""")
    v = dict(cur.fetchall())
    judged = v.get("match", 0) + v.get("mismatch", 0)
    if judged == 0:
        s.add(step, None, "정답셋 정확도", "채점 기록이 없다 — rebuild.py 를 먼저 돌린다")
    else:
        acc = v.get("match", 0) / judged
        s.add(step, acc >= MIN_ACCURACY, "정답셋 정확도",
              f"맞음 {v.get('match', 0)} · 틀림 {v.get('mismatch', 0)} · 모름 {v.get('unknown', 0)}"
              f" → {acc:.1%} (기준 {MIN_ACCURACY:.0%})")


# ──────────────────────────────────────────────────────────────
# 1-2 넣은 데이터 — 파일에 있는 것이 원장에 다 들어갔는가
# ──────────────────────────────────────────────────────────────

def csv_rows(path: str, skip_example: bool = False) -> int:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if skip_example:
        rows = [r for r in rows if (r.get("번호") or "").strip() != "예시"]
    return len(rows)


def check_loaded(cur, s: Sheet) -> None:
    step = "1-2 넣은 데이터"
    data = os.path.join(ROOT, "data", "dining")
    cur.execute("SELECT source_code, count(*) FROM dining.dn_source_record GROUP BY 1")
    rec = dict(cur.fetchall())

    with open(os.path.join(data, "tourapi_음식점_소개정보.json"), encoding="utf-8") as f:
        n = len(json.load(f))
    s.add(step, rec.get("tourapi_kor_food") == n, "관광공사 소개정보",
          f"파일 {n:,}건 → 원장 {rec.get('tourapi_kor_food', 0):,}건")

    n = csv_rows(os.path.join(data, "vegan", "비건식당_2026-09-23.csv"))
    s.add(step, rec.get("vegan_curated") == n, "비건 식당 목록",
          f"파일 {n}곳 → 원장 {rec.get('vegan_curated', 0)}곳")

    halal = os.path.join(data, "halal", "할랄식당_검수.csv")
    with open(halal, encoding="utf-8-sig", newline="") as f:
        # make_halal_sql 과 같은 기준: 영업 · 좌표 있음 · 관리번호 또는 원장 「없음(운영자 확인)」
        n = sum(1 for r in csv.DictReader(f)
                if (r.get("판정") or "").strip() == "영업"
                and (r.get("위도") or "").strip() and (r.get("경도") or "").strip()
                and ((r.get("관리번호") or "").strip()
                     or (r.get("원장") or "").strip().startswith("없음")))
    s.add(step, rec.get("halal_curated") == n, "할랄 식당 목록",
          f"시트의 영업 중인 곳 {n}곳 → 원장 {rec.get('halal_curated', 0)}곳")

    cur.execute("SELECT count(*) FROM dining.dn_truth WHERE retired_at IS NULL")
    truth = cur.fetchone()[0]
    n = csv_rows(os.path.join(data, "truth", "대조표100_검수_2026-09-21.csv"))
    s.add(step, truth >= 100, "정답셋 (검수 대조표)", f"대조표 {n}행 → 정답 {truth}건")

    with open(os.path.join(data, "holidays_2026_2027.json"), encoding="utf-8") as f:
        hol = json.load(f)
    n = len(hol["holidays"])
    cur.execute("SELECT count(*) FROM dining.dn_holiday_stub")
    got = cur.fetchone()[0]
    s.add(step, got == n, "공휴일", f"파일 {n}일 → 원장 {got}일")

    cur.execute("SELECT count(*) FROM dining.dn_hours_rule "
                "WHERE source_code = 'operator_check' AND retired_at IS NULL")
    op = cur.fetchone()[0]
    s.add(step, op > 0, "운영자 확인 영업시간", f"규칙 {op}건 (관광공사 규칙보다 앞선다)")

    n = csv_rows(os.path.join(data, "vegan", "비건식당_영업시간_검수.csv"), skip_example=True)
    cur.execute("""SELECT count(DISTINCT r.place_uid) FROM dining.dn_hours_rule r
                   JOIN dining.dn_source_record sr USING (place_uid)
                   WHERE sr.source_code = 'vegan_curated' AND r.retired_at IS NULL""")
    got = cur.fetchone()[0]
    s.add(step, None if got == 0 else True, "비건 식당 영업시간",
          f"검수 시트 {n}곳 중 영업시간이 들어간 곳 {got}곳"
          + (" — 시트에 확인일이 아직 없다. 채우면 들어간다" if got == 0 else ""))


# ──────────────────────────────────────────────────────────────
# 7 식이 조건 — 비건 · 할랄
# ──────────────────────────────────────────────────────────────

#: 화면에 쓰는 이름 → 원장 속성. ledger.DIETARY 와 같은 값이다.
CONDITIONS = [("비건·채식", "vegetarian_menu"), ("할랄", "halal")]
#: 조건마다 그 조건의 식당 목록 출처
LIST_OF = {"vegetarian_menu": "vegan_curated", "halal": "halal_curated"}


def check_dietary(cur, s: Sheet, day: date) -> None:
    step = "7 식이 조건"
    for label, code in CONDITIONS:
        cur.execute("""SELECT count(*) FILTER (WHERE dining.meets_condition(place_uid, %s) IS TRUE),
                              count(*) FILTER (WHERE dining.meets_condition(place_uid, %s) IS FALSE),
                              count(*)
                       FROM dining.dn_place""", (code, code))
        yes, no, total = cur.fetchone()
        if yes == 0:
            # 목록은 들어왔는데 사람이 아직 확인하지 않은 것과, 목록조차 없는 것은 다르다.
            cur.execute("""SELECT count(*) FROM dining.dn_source_record
                           WHERE source_code = %s""", (LIST_OF.get(code, ""),))
            listed = cur.fetchone()[0]
            if listed:
                s.add(step, None, f"{label} 식당이 있다",
                      f"목록 {listed}곳은 들어왔고 확인된 곳 0곳 — 검수 시트의 [확인] 칸을 채우면 붙는다."
                      f" 그 전까지 {label} 조건은 「모름」으로 답한다")
            else:
                s.add(step, False, f"{label} 식당이 있다",
                      f"맞다고 확인된 곳 0곳 — 데이터가 없어 {label} 조건은 전부 「모름」으로 답한다")
            continue
        s.add(step, True, f"{label} 식당이 있다",
              f"맞음 {yes}곳 · 아님 {no}곳 · 모름 {total - yes - no}곳")

        # 조건을 걸고 대안을 찾으면 조건이 맞는 곳만 나오는가
        cur.execute("""SELECT place_uid, name_ko FROM dining.dn_place
                       WHERE dining.meets_condition(place_uid, %s) IS TRUE AND lat IS NOT NULL
                       ORDER BY name_ko LIMIT 1""", (code,))
        uid, name = cur.fetchone()
        cur.execute("""SELECT axis_label, place_uid, name_ko
                       FROM dining.suggest_alternatives(%s, %s, NULL, %s)
                       WHERE place_uid IS NOT NULL""", (uid, at(day, 12 * 60), [code]))
        alts = cur.fetchall()
        # 대안 후보는 「아니라고 확인된 곳」만 뺀다(027). 그래서 모르는 곳이 섞일 수 있다.
        # 조건이 식이 제한이면 모르는 곳을 권하는 것은 위험하므로 따로 드러낸다.
        wrong, unknown = [], []
        for _, auid, aname in alts:
            cur.execute("SELECT dining.meets_condition(%s, %s)", (auid, code))
            meets = cur.fetchone()[0]
            if meets is False:
                wrong.append(aname)
            elif meets is None:
                unknown.append(aname)
        s.add(step, bool(alts) and not wrong, f"{label} 조건으로 찾은 대안에 「아닌 곳」이 없다",
              f"{name} 대안 → " + (", ".join(a[2] for a in alts) or "없음")
              + (f" · 아닌 곳: {', '.join(wrong)}" if wrong else ""))
        s.add(step, bool(alts) and not unknown, f"{label} 조건으로 찾은 대안이 {label}로 확인된 곳이다",
              "모두 확인된 곳" if not unknown else
              f"확인 안 된 곳이 섞였다: {', '.join(unknown)} — 조건을 모르는 곳도 대안으로 낸다")


# ──────────────────────────────────────────────────────────────
# 2 판정
# ──────────────────────────────────────────────────────────────

def open_at(cur, place_uid, starts_at, ends_at=None):
    cur.execute("SELECT dining.open_at_slot(%s, %s, %s)", (place_uid, starts_at, ends_at))
    return cur.fetchone()[0]


def pick_one_interval(cur, day: date):
    """그날 쉬지 않고 구간이 하나뿐인 집 하나 — (uid, 이름, 여는 분, 닫는 분)."""
    cur.execute("""
        SELECT p.place_uid, p.name_ko, i.open_min, i.close_min
        FROM dining.dn_place p, LATERAL dining.day_intervals(p.place_uid, %s) i
        WHERE NOT coalesce(dining.is_closed_on(p.place_uid, %s), false)
          AND i.open_min >= 120 AND i.close_min <= 1380 AND i.close_min - i.open_min >= 180
          AND (SELECT count(*) FROM dining.day_intervals(p.place_uid, %s)) = 1
        ORDER BY p.name_ko LIMIT 1""", (day, day, day))
    return cur.fetchone()


def check_judgment(cur, s: Sheet, day: date) -> tuple | None:
    step = "2 판정"
    one = pick_one_interval(cur, day)
    if one is None:
        s.add(step, None, "영업 중 · 영업 전", f"{day} 에 구간 하나인 가게를 못 찾았다")
    else:
        uid, name, o, c = one
        mid = o + (c - o) // 2
        got = open_at(cur, uid, at(day, mid))
        s.add(step, got is True, "영업 중이면 연다",
              f"{name} {hhmm(o)}~{hhmm(c)} · {day} {hhmm(mid)} → {got}")
        got = open_at(cur, uid, at(day, o - 60))
        s.add(step, got is False, "영업 전이면 닫혀 있다",
              f"{name} · {hhmm(o - 60)} → {got}")

    cur.execute("""
        SELECT p.place_uid, p.name_ko, a.close_min, b.open_min
        FROM dining.dn_place p,
             LATERAL dining.day_intervals(p.place_uid, %s) a,
             LATERAL dining.day_intervals(p.place_uid, %s) b
        WHERE a.seq = 1 AND b.seq = 2 AND b.open_min - a.close_min >= 60
          AND NOT coalesce(dining.is_closed_on(p.place_uid, %s), false)
        ORDER BY p.name_ko LIMIT 1""", (day, day, day))
    brk = cur.fetchone()
    if brk is None:
        s.add(step, None, "브레이크타임이면 닫혀 있다", "브레이크가 있는 가게를 못 찾았다")
    else:
        uid, name, a_close, b_open = brk
        mid = a_close + (b_open - a_close) // 2
        got = open_at(cur, uid, at(day, mid))
        s.add(step, got is False, "브레이크타임이면 닫혀 있다",
              f"{name} 쉬는 시간 {hhmm(a_close)}~{hhmm(b_open)} · {hhmm(mid)} → {got}")

    cur.execute("""
        SELECT p.place_uid, p.name_ko, r.weekday
        FROM dining.dn_closure_rule r JOIN dining.dn_place p USING (place_uid)
        WHERE r.pattern_kind = 'weekly' AND r.retired_at IS NULL AND r.weekday BETWEEN 1 AND 7
        ORDER BY p.name_ko LIMIT 1""")
    closed = cur.fetchone()
    closed_case = None
    if closed is None:
        s.add(step, None, "정기휴무 요일이면 닫혀 있다", "매주 휴무 규칙이 있는 가게를 못 찾았다")
    else:
        uid, name, wd = closed
        cday = next_weekday(wd, day)
        got = open_at(cur, uid, at(cday, 12 * 60))
        s.add(step, got is False, "정기휴무 요일이면 닫혀 있다",
              f"{name} 매주 {'월화수목금토일'[wd - 1]} 휴무 · {cday} 12:00 → {got}")
        closed_case = (uid, name, at(cday, 12 * 60))

    cur.execute("""
        SELECT p.place_uid, p.name_ko FROM dining.dn_place p
        WHERE NOT EXISTS (SELECT 1 FROM dining.dn_hours_rule r
                          WHERE r.place_uid = p.place_uid AND r.retired_at IS NULL)
        ORDER BY p.name_ko LIMIT 1""")
    unknown = cur.fetchone()
    if unknown is None:
        s.add(step, None, "규칙이 없으면 「모름」", "영업 규칙이 없는 가게가 없다")
    else:
        uid, name = unknown
        got = open_at(cur, uid, at(day, 12 * 60))
        s.add(step, got is None, "규칙이 없으면 「모름」(닫힘이 아니다)",
              f"{name} · 12:00 → {got}")

    # 마지막 주문 시각을 모르는 집에 마감 직전에 있으면 「확인이 필요하다」.
    # 마지막 주문을 아는 집은 판정이 이미 그 시각으로 하므로 확인을 부르지 않는다.
    cur.execute("""
        SELECT p.place_uid, p.name_ko, i.close_min
        FROM dining.dn_place p, LATERAL dining.day_intervals(p.place_uid, %s) i
        WHERE i.last_order_state <> 'present' AND i.close_min BETWEEN 1140 AND 1380
          AND i.close_min - i.open_min >= 360
          AND NOT coalesce(dining.is_closed_on(p.place_uid, %s), false)
        ORDER BY p.name_ko LIMIT 1""", (day, day))
    lo = cur.fetchone()
    if lo is None:
        s.add(step, None, "마감 임박이면 확인이 필요하다", "마지막 주문을 모르는 가게를 못 찾았다")
    else:
        uid, name, close = lo
        cur.execute("SELECT dining.needs_last_order_check(%s, %s, %s)",
                    (uid, at(day, close - 70), at(day, close - 10)))
        near = cur.fetchone()[0]
        cur.execute("SELECT dining.needs_last_order_check(%s, %s, %s)",
                    (uid, at(day, close - 300), at(day, close - 240)))
        early = cur.fetchone()[0]
        s.add(step, near is True and early is False, "마감 임박이면 확인이 필요하다",
              f"{name} {hhmm(close)} 마감·마지막 주문 모름 · "
              f"{hhmm(close - 70)}~{hhmm(close - 10)} → {near}, "
              f"{hhmm(close - 300)}~{hhmm(close - 240)} → {early}")
    return closed_case


# ──────────────────────────────────────────────────────────────
# 3 코어 연결
# ──────────────────────────────────────────────────────────────

def check_core(conn, cur, s: Sheet, day: date) -> None:
    step = "3 코어 연결"
    cur.execute("SELECT to_regclass('public.places') IS NOT NULL")
    if not cur.fetchone()[0]:
        s.add(step, None, "코어 places 가 있다", "이 DB 에는 코어가 없다 — rebuild.py 를 --no-core 없이")
        return
    from app.modules.travel_ops.dining.ledger import dining_state

    cur.execute("""SELECT l.tenant_id, l.core_place_id, p.name
                   FROM dining.dn_core_place_link l JOIN public.places p ON p.place_id = l.core_place_id
                   LIMIT 1""")
    link = cur.fetchone()
    if link is None:
        s.add(step, None, "코어 장소가 우리 가게로 이어진다", "연결이 0건 — 코어에 식당이 없거나 매칭 실패")
    else:
        tenant, core_id, name = link
        got = dining_state(conn, tenant, str(core_id), at(day, 12 * 60))
        s.add(step, bool(got and got["linked"]), "코어 장소가 우리 가게로 이어진다",
              f"코어 「{name}」 → linked={got and got['linked']}, 12:00 open={got and got['open_at_slot']}")
        tenant_any = tenant
        got = dining_state(conn, tenant_any, str(uuid.uuid4()), at(day, 12 * 60))
        s.add(step, bool(got) and got["linked"] is False and got["open_at_slot"] is None,
              "모르는 장소는 「모름」(닫힘이 아니다)",
              f"없는 장소 → linked={got and got['linked']}, open={got and got['open_at_slot']}")


# ──────────────────────────────────────────────────────────────
# 4 대체 장소
# ──────────────────────────────────────────────────────────────

def check_alternatives(cur, s: Sheet, closed_case) -> None:
    step = "4 대체 장소"
    if closed_case is None:
        s.add(step, None, "문 닫은 집의 대안이 나온다", "휴무 가게가 없어 볼 수 없다")
        return
    uid, name, when = closed_case
    cur.execute("SELECT axis_label, place_uid, name_ko FROM dining.suggest_alternatives(%s, %s)",
                (uid, when))
    alts = cur.fetchall()
    filled = [a for a in alts if a[1] is not None]
    s.add(step, len(filled) > 0, "문 닫은 집의 대안이 나온다",
          f"{name} 휴무일 → " + " · ".join(
              f"{a[0]}: {a[2] or '비어 있음(다음 일정 좌표를 받지 않음)'}" for a in alts))
    alts = filled
    if not alts:
        return
    s.add(step, all(a[1] != uid for a in alts), "대안에 원래 가게가 섞이지 않는다", "")
    states = [(a[2], open_at(cur, a[1], when)) for a in alts]
    closed = [n for n, st in states if st is False]
    s.add(step, not closed, "대안은 그 시각에 닫혀 있지 않다",
          "모두 열림 또는 모름" if not closed else f"닫힌 대안: {', '.join(closed)}")


# ──────────────────────────────────────────────────────────────
# 5 확인 시점 · 6 알림 중복
# ──────────────────────────────────────────────────────────────

def check_watch(cur, s: Sheet) -> None:
    step = "5 확인 시점"
    now = datetime.now(KST)
    got = {}
    for label, minutes in (("60분 전", 60), ("20분 전", 20), ("3시간 전", 180)):
        cur.execute("SELECT dining.watch_window(%s, %s)", (now + timedelta(minutes=minutes), now))
        got[label] = cur.fetchone()[0]
    s.add(step, got["60분 전"] is not None and got["20분 전"] is not None and got["3시간 전"] is None,
          "방문 60분·20분 전에만 물을 때다",
          " · ".join(f"{k} → {v}" for k, v in got.items()))


def check_notice(conn, cur, s: Sheet, day: date) -> None:
    step = "6 알림 중복"
    cur.execute("SELECT place_uid FROM dining.dn_place ORDER BY name_ko LIMIT 1")
    uid = cur.fetchone()[0]
    target = at(day, 12 * 60)
    try:
        cur.execute("SELECT dining.record_notice(%s, %s, 'closed', '점검표', 'check_dining')",
                    (uid, target))
        cur.execute("SELECT dining.record_notice(%s, %s, 'closed', '점검표', 'check_dining')",
                    (uid, target))
        cur.execute("SELECT count(*) FROM dining.dn_notice WHERE place_uid = %s AND target_at = %s",
                    (uid, target))
        n = cur.fetchone()[0]
        s.add(step, n == 1, "같은 방문에 같은 알림은 한 번만", f"두 번 적었더니 {n}건")
    except psycopg.Error as exc:
        s.add(step, False, "같은 방문에 같은 알림은 한 번만", f"오류: {str(exc).splitlines()[0]}")
    finally:
        conn.rollback()                                  # 원장을 바꾸지 않는다


# ──────────────────────────────────────────────────────────────
# 8 자동 시험
# ──────────────────────────────────────────────────────────────

def check_tests(s: Sheet) -> None:
    step = "8 자동 시험"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    for label, args in (("요식 unit 시험", ["tests/unit/travel", "-k", "dining"]),
                        ("요식 integration 시험 (실제 DB)", ["tests/integration/dining"])):
        done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
        last = [line for line in done.stdout.strip().splitlines() if line.strip()]
        summary = last[-1] if last else done.stderr.strip()[-200:]
        s.add(step, done.returncode == 0, label, summary)


# ──────────────────────────────────────────────────────────────

def render(s: Sheet, day: date) -> str:
    ok, bad, warn = s.counts()
    lines = ["# 요식 기능 점검표", "",
             f"- DB: `{DSN.rsplit('/', 1)[-1]}` · 기준일 {day} · 만든 시각 {datetime.now(KST):%Y-%m-%d %H:%M}",
             f"- 결과: ✅ {ok} · ❌ {bad} · ⚠️ {warn}", ""]
    step = None
    for st, mark, item, detail in s.rows:
        if st != step:
            lines += ["", f"## {st}", ""]
            step = st
        lines.append(f"- {mark} **{item}**" + (f" — {detail}" if detail else ""))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="요식 기능 점검표")
    ap.add_argument("--no-tests", action="store_true", help="자동 시험은 돌리지 않는다")
    ap.add_argument("--save", action="store_true", help=f"{SAVE} 로도 남긴다")
    args = ap.parse_args(argv)

    s = Sheet()
    try:
        conn = psycopg.connect(DSN)
    except psycopg.OperationalError as exc:
        print(f"DB 에 붙지 못했다: {DSN}\n  {str(exc).splitlines()[0]}\n"
              "  DB 를 켠다: python scripts/dining/dev_up.py --check", file=sys.stderr)
        return 2
    with conn:
        cur = conn.cursor()
        day = plain_day(cur, datetime.now(KST).date())
        check_data(cur, s)
        check_loaded(cur, s)
        closed_case = check_judgment(cur, s, day)
        check_core(conn, cur, s, day)
        check_alternatives(cur, s, closed_case)
        check_watch(cur, s)
        check_notice(conn, cur, s, day)
        check_dietary(cur, s, day)
    if not args.no_tests:
        check_tests(s)

    text = render(s, day)
    print(text)
    if args.save:
        os.makedirs(os.path.dirname(SAVE), exist_ok=True)
        with open(SAVE, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"저장: {SAVE}")
    return 1 if s.counts()[1] else 0


if __name__ == "__main__":
    raise SystemExit(main())
