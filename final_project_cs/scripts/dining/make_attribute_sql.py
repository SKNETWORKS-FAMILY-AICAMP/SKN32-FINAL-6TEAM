"""관광공사 매장 속성을 적재 SQL 로 바꾼다.

왜 필요한가. 같은 일정이라도 사용자 조건에 따라 판정이 달라져야 한다.
카드만 쓰는 여행자에게 현금만 받는 집은 못 가는 곳이다.

표본 200곳의 값 분포는 이랬다.
  카드 결제  가능 51, 없음 4, 언급 없음 145
  주차       가능 78, 불가 73, 언급 없음 49
  포장       가능 111, 불가 1, 언급 없음 88

언급이 없는 것을 가능으로 바꾸지 않는다. unknown 으로 둔다.
「가능(일부 메뉴)」처럼 단서가 붙은 것은 limited 로 두고 원문을 함께 남긴다.

사용법:  python scripts/dining/make_attribute_sql.py
출력:    data/dining/_build/attributes.sql
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from collections import Counter
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))   # final_project_cs
DATA = os.path.join(ROOT, "data", "dining")
OUT = os.path.join(ROOT, "data", "dining", "_build")

NS = uuid.UUID("6f1c0d2e-0000-4000-8000-000000000001")
SOURCE = "tourapi_kor_food"
VALID_FROM = date(2026, 9, 21).isoformat()

#: 관광공사 칸 이름과 우리 속성 코드의 대응
FIELDS = {
    "chkcreditcardfood": "card_payment",
    "parkingfood": "parking",
    "packing": "takeout",
}

RE_NO = re.compile(r"불가|없음|안\s*됨|불가능")
RE_YES = re.compile(r"가능|됩니다|있음|가능합니다")
#: 단서가 붙은 가능. 「가능(일부 메뉴)」, 「가능 (2시간 무료)」
RE_LIMITED = re.compile(r"가능\s*[(（]")


def norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def classify(text: str) -> tuple[str, str | None]:
    """값 상태와 단서를 돌려준다. 해석하지 못하면 unknown 이다."""
    if not text:
        return "unknown", None
    # 부정이 먼저다. 「불가능 (인근 공영주차장 이용)」 에서 괄호만 보고 가능으로 읽으면 안 된다.
    if RE_NO.search(text):
        return "no", text if len(text) > 4 else None
    if RE_LIMITED.search(text):
        return "limited", text
    if RE_YES.search(text):
        return "yes", text if len(text) > 4 else None
    return "unknown", text


def q(value) -> str:
    if value is None or value == "":
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def main() -> None:
    rows = json.load(open(os.path.join(DATA, "tourapi_음식점_소개정보.json"), encoding="utf-8"))

    lines = ["-- 매장 속성 적재. 생성 파일이므로 직접 고치지 않는다.",
             "-- 원본: data/dining/tourapi_음식점_소개정보.json",
             "BEGIN;", "",
             "-- 같은 적재를 다시 돌려도 쌓이지 않게 이 출처의 것을 먼저 비운다.",
             f"DELETE FROM dining.dn_attribute WHERE source_code = '{SOURCE}';", ""]

    stat: dict[str, Counter] = {code: Counter() for code in FIELDS.values()}
    values = []

    for row in rows:
        cid = row.get("contentid")
        place_uid = str(uuid.uuid5(NS, f"place:tourapi:{cid}"))
        record_id = str(uuid.uuid5(NS, f"record:tourapi:{cid}"))
        for field, code in FIELDS.items():
            text = norm(row.get(field))
            state, detail = classify(text)
            stat[code][state] += 1
            if state == "unknown":
                # 주장이 없는 것은 행을 만들지 않는다. 조회 함수가 unknown 을 돌려준다.
                continue
            attr_id = str(uuid.uuid5(NS, f"attr:tourapi:{cid}:{code}"))
            values.append(
                f"    ('{attr_id}', '{place_uid}', '{SOURCE}', '{record_id}', "
                f"'{code}', '{state}', {q(detail)}, {q(text[:300])}, 'regex', 0.9, '{VALID_FROM}')")

    lines.append("INSERT INTO dining.dn_attribute "
                 "(attr_id, place_uid, source_code, record_id, attr_code, value_state, "
                 "value_detail, source_text, extract_method, extract_confidence, valid_from) VALUES")
    lines.append(",\n".join(values))
    lines.append("ON CONFLICT (attr_id) DO NOTHING;")
    lines += ["", "COMMIT;"]

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "attributes.sql")
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    total = len(rows)
    print(f"표본 {total}곳\n")
    print(f"{'속성':14s} {'가능':>6s} {'조건부':>7s} {'없음':>6s} {'모름':>6s}")
    for code, c in stat.items():
        print(f"{code:14s} {c['yes']:6d} {c['limited']:7d} {c['no']:6d} {c['unknown']:6d}")
    print(f"\n만든 행 {len(values)}개")
    print(f"저장: {path}")


if __name__ == "__main__":
    main()
