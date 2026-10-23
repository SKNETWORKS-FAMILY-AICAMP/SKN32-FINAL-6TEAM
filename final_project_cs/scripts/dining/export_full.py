"""요식 원장의 모든 칸을 가게 한 줄로 펼쳐 CSV 한 장으로 뽑는다. 눈으로 보고 검수할 때.

    python scripts/dining/export_full.py        → datasets/dining/processed/export/요식_원장_전체.csv

요식_원장_가게.csv 는 팀원이 시험에 쓰는 요약본이다. 이 파일은 원장 표 여러 개를 가게마다 합친다.
    가게(dn_place)의 모든 칸
    요일별 영업시간 — 「11:30-15:00, 17:00-21:00 (LO 20:30)」 · 휴무 · 빈칸(모름). 살아 있는 규칙만
    휴무 규칙(매주 · 매월 n째 · 명절)과 명절 확인 상태(dn_closure_coverage)
    속성(카드 · 주차 · 포장 · 비건 · 할랄 · 아이 동반 · 미쉐린) — yes / no / limited, 빈칸은 모름
    출처 · 출처 번호 · 코어 장소 연결 · 외부 참조(구글 등)
원장이 원본이다. 이 파일을 고쳐도 원장은 바뀌지 않는다. 고칠 것은 검수 시트에 적는다.
"""
from __future__ import annotations

import csv
import os
from collections import defaultdict

import psycopg

HERE = os.path.dirname(os.path.abspath(__file__))
DINING_DATA = os.environ.get("DINING_DATA") or os.path.join(  # 데이터는 git 밖(datasets/dining/processed)
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "datasets", "dining", "processed")
OUT = os.path.join(DINING_DATA, "export", "요식_원장_전체.csv")
DSN = os.environ.get("DINING_DSN", "postgresql://postgres@localhost:5433/dining_rebuild")
DAYS = "월화수목금토일"
ATTRS = ["card_payment", "parking", "takeout", "vegetarian_menu", "halal", "kids_allowed", "michelin"]
ATTR_KO = {"card_payment": "카드", "parking": "주차", "takeout": "포장", "vegetarian_menu": "비건·채식",
           "halal": "할랄", "kids_allowed": "아이 동반", "michelin": "미쉐린"}


def hm(m: int | None) -> str:
    return "" if m is None else f"{m // 60:02d}:{m % 60:02d}"


def main() -> None:
    with psycopg.connect(DSN) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM dining.dn_place ORDER BY area, name_ko")
        place_cols = [d.name for d in cur.description]
        places = cur.fetchall()

        hours: dict = defaultdict(dict)
        hours_src: dict = defaultdict(set)
        hours_text: dict = {}
        brk: dict = defaultdict(set)
        cur.execute("""
            SELECT h.place_uid, h.weekday, h.coverage, h.break_state, h.source_code, h.source_text,
                   i.seq, i.open_min, i.close_min, i.last_order_min, i.last_order_state
            FROM dining.v_hours_rule_active h
            LEFT JOIN dining.dn_hours_interval i USING (rule_id)
            WHERE h.rule_kind = 'weekly'
            ORDER BY h.place_uid, h.weekday, i.seq""")
        for uid, wd, cov, bstate, src, text, seq, o, c, lo, lostate in cur:
            day = hours[uid].setdefault(wd, [])
            hours_src[uid].add(src)
            brk[uid].add(bstate)
            hours_text.setdefault(uid, text or "")
            if cov == "closed":
                day.append("휴무")
            elif o is not None:
                day.append(f"{hm(o)}-{hm(c)}" + (f" (LO {hm(lo)})" if lo is not None else
                                                  " (LO 없음)" if lostate == "none" else ""))

        closures: dict = defaultdict(list)
        cur.execute("""SELECT place_uid, pattern_kind, weekday, nth, holiday_name, closed_date
                       FROM dining.v_closure_rule_active ORDER BY place_uid, pattern_kind, weekday, nth""")
        for uid, kind, wd, nth, hol, date in cur:
            if kind == "weekly":
                closures[uid].append(f"매주 {DAYS[wd - 1]}")
            elif kind == "monthly_nth":
                closures[uid].append(f"매월 {nth}째 {DAYS[wd - 1] if wd else ''}".strip())
            elif kind == "named_holiday":
                closures[uid].append(hol or "명절")
            else:
                closures[uid].append(f"{kind} {date or ''}".strip())

        coverage = {uid: state for uid, state in conn.execute(
            "SELECT place_uid, string_agg(DISTINCT state, '|') FROM dining.dn_closure_coverage "
            "WHERE retired_at IS NULL GROUP BY 1")}

        attrs: dict = defaultdict(dict)
        for uid, code, state, detail in conn.execute(
                "SELECT place_uid, attr_code, value_state, value_detail::text FROM dining.dn_attribute "
                "WHERE retired_at IS NULL ORDER BY verified_at NULLS LAST"):
            attrs[uid][code] = f"{state} {detail.strip(chr(34))}" if code == "michelin" and detail else state

        sources = {uid: (s, e) for uid, s, e in conn.execute(
            "SELECT place_uid, string_agg(DISTINCT source_code, '|' ORDER BY source_code), "
            "string_agg(DISTINCT source_code || ':' || external_id, '|') FROM dining.dn_source_record "
            "WHERE place_uid IS NOT NULL GROUP BY 1")}
        links = {uid: v for uid, v in conn.execute(
            "SELECT place_uid, string_agg(tenant_id || ':' || core_place_id, '|') "
            "FROM dining.dn_core_place_link GROUP BY 1")}
        refs = {uid: v for uid, v in conn.execute(
            "SELECT place_uid, string_agg(kind || ':' || coalesce(provider_id, url, ''), '|') "
            "FROM dining.dn_external_ref WHERE retired_at IS NULL GROUP BY 1")}

    head = (place_cols + [f"영업 {d}" for d in DAYS] +
            ["영업시간 출처", "브레이크", "영업시간 원문(예시 한 줄)", "휴무 규칙", "명절·휴무 확인"] +
            [ATTR_KO[a] for a in ATTRS] + ["출처", "출처 번호", "코어 장소 연결", "외부 참조(구글 등)"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(head)
        for row in places:
            uid = row[place_cols.index("place_uid")]
            days = [", ".join(hours[uid].get(wd, [])) for wd in range(1, 8)]
            b = brk.get(uid, set())
            src, ext = sources.get(uid, ("", ""))
            w.writerow(list(row) + days + [
                "|".join(sorted(hours_src.get(uid, ()))),
                "있음" if "present" in b else "없음" if b == {"none"} else "모름" if b else "",
                (hours_text.get(uid) or "")[:200],
                " · ".join(dict.fromkeys(closures.get(uid, []))),
                coverage.get(uid, ""),
            ] + [attrs[uid].get(a, "") for a in ATTRS] + [src, ext, links.get(uid, ""), refs.get(uid, "")])
    print(f"{len(places):,}곳 · {len(head)}칸 → {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
