"""분류 검수 시트에서 사람이 확인한 대표 분류를 원장에 넣는다. `[2026-10-12]`

    python scripts/dining/make_category_sql.py      → datasets/dining/processed/_build/category.sql

왜.
    대표 분류(`dn_place.category`)는 `dining.refresh_category()`(214)가 관광공사 대표메뉴 · 상호 · 취급메뉴로 정한다.
    메뉴 칸이 없는 노포 · 비건 · 할랄 큐레이션 가게는 늘 「미상」이라(로컬 원장 257곳, 2026-10-12) 대체 후보를 같은 요리로 못 맞췄다.
    사람이 정한 분류를 넣는 길은 폐업 대조 시트의 「새 분류」뿐이었는데, 그 칸은 폐업 · 이전 같은 변경이 있는 줄에서만 들어간다 —
    분류만 고치는 길이 없었다.

시트는 datasets/dining/processed/category/분류_검수_*.csv (가장 최근 것). 초안은 인허가 자료의 업태로 채웠다(사업자가 신고한 값이라
    실제 요리와 다를 수 있다 — 초안만으로는 넣지 않는다). 확인일이 적힌 행만 넣는다(다른 검수 시트와 같은 규칙).

    [확인] 분류   한식 · 중식 · 일식 · 양식 · 카페디저트 · 기타  (214 의 칸과 같다. 「미상」은 넣지 않는다 — 비워 두면 규칙이 다시 본다)
    넣는 값       category = [확인] 분류, category_method = 'manual' — refresh_category 가 덮지 않는다(214)
    [확인] 결     `[2026-10-12]` 음식 결(231 의 칸 — 고기구이 · 국물요리 …). 칸이 없거나 비면 결은 건드리지 않는다.
                  「없음」은 사람이 보고 결이 없다고 정한 것이다(style = NULL, manual — 규칙이 다시 채우지 않는다)
    넣는 값       style = [확인] 결, style_method = 'manual' — refresh_style 이 덮지 않는다(231)
    한 줄에 분류 · 결 중 하나만 있어도 된다. 확인일이 있는데 둘 다 비면 멈춘다.

가게는 place_uid 로 찾는다. 칸 값이 틀리면 조용히 건너뛰지 않고 멈춘다.
"""
from __future__ import annotations

import csv
import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DINING_DATA = os.environ.get("DINING_DATA") or os.path.join(  # 데이터는 git 밖(datasets/dining/processed)
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "datasets", "dining", "processed")
SHEETS = os.path.join(DINING_DATA, "category", "분류_검수_[0-9]*.csv")   # 날짜 파일만
OUT = os.path.join(DINING_DATA, "_build", "category.sql")

#: 214 `dn_place_category_chk` 의 칸에서 「미상」을 뺀 것
ALLOWED = ("한식", "중식", "일식", "양식", "카페디저트", "기타")
#: 231 `dn_place_style_chk` 의 칸
STYLES = ("고기구이", "국물요리", "면", "해산물", "한상차림", "분식", "닭요리", "족발·보쌈", "초밥", "돈가스·튀김",
          "덮밥", "중식요리", "이탈리안", "버거·샌드위치", "브런치", "아시아요리", "베이커리·디저트", "커피·차", "술집")
#: 사람이 보고 결이 없다고 정한 값
NO_STYLE = "없음"


def q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def build(sheet: str) -> tuple[list[str], dict[str, int]]:
    lines = ["-- 분류 검수 반영. 만든 것: scripts/dining/make_category_sql.py", "BEGIN;"]
    n = {"분류": 0, "결": 0, "확인 전": 0}
    for row in csv.DictReader(open(sheet, encoding="utf-8-sig")):
        if not (row.get("확인일") or "").strip():
            n["확인 전"] += 1
            continue
        uid = (row.get("place_uid") or "").strip()
        cat = (row.get("[확인] 분류") or "").strip()
        style = (row.get("[확인] 결") or "").strip()
        if not uid:
            raise ValueError(f"place_uid 가 없다: {row.get('상호')!r}")
        if cat or not style:
            if cat not in ALLOWED:
                raise ValueError(f"[확인] 분류를 읽지 못함: {row.get('상호')!r} {cat!r} — {' · '.join(ALLOWED)} 중 하나")
            lines.append(f"UPDATE dining.dn_place SET category = {q(cat)}, category_method = 'manual', updated_at = now() "
                         f"WHERE place_uid = {q(uid)};")
            n["분류"] += 1
        if style:
            if style not in (*STYLES, NO_STYLE):
                raise ValueError(f"[확인] 결을 읽지 못함: {row.get('상호')!r} {style!r} — {' · '.join(STYLES)} · {NO_STYLE} 중 하나")
            value = "NULL" if style == NO_STYLE else q(style)
            lines.append(f"UPDATE dining.dn_place SET style = {value}, style_method = 'manual', updated_at = now() "
                         f"WHERE place_uid = {q(uid)};")
            n["결"] += 1
    lines += ["COMMIT;", ""]
    return lines, n


def main() -> None:
    sheets = sorted(glob.glob(SHEETS))
    lines, n = build(sheets[-1]) if sheets else (["-- 분류 검수 시트 없음", ""], {})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"분류 검수 {os.path.basename(sheets[-1]) if sheets else '-'}: {n} → {OUT}")


if __name__ == "__main__":
    main()
