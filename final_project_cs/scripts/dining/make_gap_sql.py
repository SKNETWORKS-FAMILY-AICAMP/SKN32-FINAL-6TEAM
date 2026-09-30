"""빈칸 검수 시트에서 사람이 확인한 영업시간 · 전화 · 좌표를 원장에 넣는다.

    python scripts/dining/make_gap_sql.py      → datasets/dining/processed/_build/gaps.sql

시트는 datasets/dining/processed/gaps/빈칸_검수_*.csv (가장 최근 것). 원장에서 영업시간 · 전화 · 좌표가
빈 가게를 뽑아 카카오맵으로 초안을 채운 것이다. 초안만으로는 넣지 않는다.
확인일이 적힌 행만 넣는다(다른 검수 시트와 같은 규칙).

    요일 칸 · 라스트오더 · 정기휴무 외   비건 · 미쉐린 시트와 같은 형식. make_vegan_sql.hours_sql 로 넣는다
                                    관광공사 규칙이 있던 가게는 그 규칙을 지우지 않고 물러나게 한다
    전화                            원장 전화가 비어 있을 때만 채운다
    위도 · 경도                      원장 좌표가 비어 있을 때만 채운다(coord_source = operator_check)

가게는 place_uid 로 찾는다. 상호가 같은 가게가 여럿이어도 헷갈리지 않게.
"""
from __future__ import annotations

import csv
import glob
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DINING_DATA = os.environ.get("DINING_DATA") or os.path.join(  # 데이터는 git 밖(datasets/dining/processed)
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "datasets", "dining", "processed")
ROOT = os.path.dirname(os.path.dirname(HERE))
SHEETS = os.path.join(DINING_DATA, "gaps", "빈칸_검수_*.csv")
OUT = os.path.join(DINING_DATA, "_build", "gaps.sql")


def q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def load_vegan():
    spec = importlib.util.spec_from_file_location("make_vegan_sql", os.path.join(HERE, "make_vegan_sql.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(sheet: str) -> tuple[list[str], dict]:
    rows = [r for r in csv.DictReader(open(sheet, encoding="utf-8-sig")) if (r.get("확인일") or "").strip()]
    place_of = {r["상호(목록)"].strip(): r["place_uid"].strip() for r in rows}
    if len(place_of) != len(rows):
        raise ValueError("상호(목록)이 겹친다. 같은 상호면 뒤에 (자치구)를 붙인다")
    has_hours = [r for r in rows if any((r.get(d) or "").strip() for d in "월화수목금토일")]
    lines = ["-- 빈칸 검수 반영. 만든 것: scripts/dining/make_gap_sql.py", "BEGIN;"]
    n: dict = {"식당": 0}
    if has_hours:
        # 관광공사 규칙이 있을 수 있는 가게는 모두 물러나게 할 대상으로 준다. 없으면 UPDATE 가 0행이다.
        hours, n = load_vegan().hours_sql(place_of, set(place_of.values()), sheet, tag="gaps",
                                          scope="원장 빈칸 영업시간 검수", folder="gaps")
        lines += hours
    n["전화"] = n["좌표"] = 0
    for r in rows:
        uid = q(r["place_uid"].strip())
        phone = (r.get("전화") or "").strip()
        lat, lng = (r.get("위도") or "").strip(), (r.get("경도") or "").strip()
        if phone:
            lines.append(f"UPDATE dining.dn_place SET phone = {q(phone)}, updated_at = now() "
                         f"WHERE place_uid = {uid} AND coalesce(phone, '') = '';")
            n["전화"] += 1
        if lat and lng:
            lines.append(f"UPDATE dining.dn_place SET lat = {float(lat)}, lng = {float(lng)}, "
                         f"coord_source = 'operator_check', updated_at = now() WHERE place_uid = {uid} AND lat IS NULL;")
            n["좌표"] += 1
    lines += ["COMMIT;", ""]
    return lines, n


def main() -> None:
    sheets = sorted(glob.glob(SHEETS))
    lines, n = build(sheets[-1]) if sheets else (["-- 빈칸 검수 시트 없음", ""], {})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"빈칸 검수 {os.path.basename(sheets[-1]) if sheets else '-'}: {n} → {OUT}")


if __name__ == "__main__":
    main()
