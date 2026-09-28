"""공휴일 달력 파일을 적재 SQL 로 바꾼다.

원본은 이동 쪽이 받아둔 한국천문연구원 특일 정보다.
  data/holidays_2026_2027.json

is_major 는 파일에 없다. 명칭으로 우리가 정한다.
설날과 추석만 앞뒤 날까지 영업에 영향을 주기 때문이고,
대체공휴일(설날)처럼 괄호가 붙은 것도 같은 연휴의 일부이므로 포함한다.

사용법:  python scripts/make_holiday_sql.py
출력:    holidays.sql
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))   # final_project_cs
DATA = os.path.join(ROOT, "data", "dining")     # 원본 데이터
OUT = os.path.join(ROOT, "data", "dining", "_build")  # 생성물

SRC = "holidays_2026_2027.json"

#: 앞뒤 날까지 영업이 달라지는 명절. 대체공휴일도 이름에 들어 있으면 같이 본다.
MAJOR_WORDS = ("설날", "추석")

#: 관공서는 쉬지 않지만 식당은 대체로 여는 날.
#: 여기 들어가면 적재는 하되 경고 대상에서 뺀다. 판단이 필요하면 목록을 고친다.
NOT_FOR_DINING = ("노동절",)


def is_major(name: str) -> bool:
    return any(word in name for word in MAJOR_WORDS)


def q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> None:
    path = os.path.join(DATA, SRC)
    doc = json.load(open(path, encoding="utf-8"))
    holidays = doc.get("holidays") or {}

    lines = [
        "-- 공휴일 달력 적재. 생성 파일이므로 직접 고치지 않는다.",
        f"-- 원본: data/{SRC}",
        f"-- 출처: {doc.get('source')} / 등급: {doc.get('grade')} / 받은 시각: {doc.get('fetched_at')}",
        f"-- 근거: {doc.get('근거')}",
        "",
        "BEGIN;",
        "",
        "INSERT INTO dining.dn_holiday_stub (holiday_date, name, is_major, note) VALUES",
    ]

    rows = []
    stat = Counter()
    for date in sorted(holidays):
        name = holidays[date]
        major = is_major(name)
        skip = any(word in name for word in NOT_FOR_DINING)
        note = "식당 영업에는 대체로 영향 없음" if skip else None
        rows.append(f"    ({q(date)}, {q(name)}, {str(major).lower()}, "
                    f"{q(note) if note else 'NULL'})")
        stat["전체"] += 1
        if major:
            stat["명절"] += 1
        if skip:
            stat["식당 영향 없음 표시"] += 1

    lines.append(",\n".join(rows))
    lines.append("ON CONFLICT (holiday_date) DO UPDATE")
    lines.append("   SET name = EXCLUDED.name,")
    lines.append("       is_major = EXCLUDED.is_major,")
    lines.append("       note = EXCLUDED.note;")
    lines.append("")
    lines.append("COMMIT;")

    out_path = os.path.join(OUT, "holidays.sql")
    open(out_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    years = sorted({d[:4] for d in holidays})
    print(f"연도 {', '.join(years)}")
    for key in ("전체", "명절", "식당 영향 없음 표시"):
        print(f"  {key:16s} {stat[key]:3d}")
    print("\n명절로 본 날")
    for date in sorted(holidays):
        if is_major(holidays[date]):
            print(f"  {date}  {holidays[date]}")
    print(f"\n저장: {out_path}")


if __name__ == "__main__":
    main()
