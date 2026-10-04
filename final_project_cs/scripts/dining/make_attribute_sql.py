"""관광공사 매장 속성을 적재 SQL 로 바꾼다.

왜 필요한가. 같은 일정이라도 사용자 조건에 따라 판정이 달라져야 한다.
카드만 쓰는 여행자에게 현금만 받는 집은 못 가는 곳이다.

표본 200곳의 값 분포는 이랬다.
  카드 결제  가능 51, 없음 4, 언급 없음 145
  주차       가능 78, 불가 73, 언급 없음 49
  포장       가능 111, 불가 1, 언급 없음 88

언급이 없는 것을 가능으로 바꾸지 않는다. unknown 으로 둔다.

아이 동반(kids_allowed)은 따로 본다(kids_state).
  관광공사에는 「아이 동반 가능」 칸이 없다. kidsfacility 는 「어린이 놀이방이 있는가」다.
  989곳 중 1 이 4곳, 0 이 985곳이다(2026-09-28).
    1  놀이방이 있다 → 아이와 가도 된다. yes
    0  놀이방이 없다 → 아이를 받지 않는다는 뜻이 아니다. 행을 만들지 않는다(모름)
  메뉴에 「아동 요금」이 있으면 아이를 받는 집이다. yes
  「노키즈」가 적혀 있으면 no. 지금 원문에는 한 곳도 없다.

  노키즈존 검수 시트(datasets/dining/processed/kids/노키즈존_검수.csv)에서 사람이 확인한 행이 원문보다 앞선다.
    [확인] 아이 동반  가능 → yes · 노키즈 → no · 일부 → limited(조건을 상세에) · 모름·빈칸 → 넣지 않음
    확인일이 적힌 행만 넣는다. 원문 판정이 있던 가게는 시트 판정으로 바꾼다.
  노키즈존을 한꺼번에 알 수 있는 공개 자료는 없다(2026-09-28 조사). 가게마다 네이버·캐치테이블의
  편의시설에서 사람이 본다. 노키즈존이 몰린 동네(성수·이태원·한남·압구정·청담·신사·홍대권) 218곳이 시트에 있다.
「가능(일부 메뉴)」처럼 단서가 붙은 것은 limited 로 두고 원문을 함께 남긴다.

사용법:  python scripts/dining/make_attribute_sql.py
출력:    datasets/dining/processed/_build/attributes.sql
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
DINING_DATA = os.environ.get("DINING_DATA") or os.path.join(  # 데이터는 git 밖(datasets/dining/processed)
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "datasets", "dining", "processed")
ROOT = os.path.dirname(os.path.dirname(HERE))   # final_project_cs
DATA = DINING_DATA
OUT = os.path.join(DINING_DATA, "_build")

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


RE_NO_KIDS = re.compile(r"노\s*키즈")
RE_KIDS_PRICE = re.compile(r"(아동|어린이|키즈)\s*(이용\s*)?(가격|요금|메뉴)")


def kids_state(row: dict) -> tuple[str, str | None, str]:
    """(값 상태, 상세, 근거 원문). 근거가 없으면 unknown — 놀이방이 없다는 것은 근거가 아니다."""
    for field in ("infocenterfood", "restdatefood", "treatmenu", "firstmenu", "opentimefood"):
        text = norm(row.get(field))
        if RE_NO_KIDS.search(text):
            return "no", "노키즈", text[:300]
    if str(row.get("kidsfacility") or "").strip() == "1":
        return "yes", "어린이 놀이방", "kidsfacility=1"
    menu = norm(row.get("treatmenu"))
    if RE_KIDS_PRICE.search(menu):
        return "yes", "아동 요금이 있다", menu[:300]
    return "unknown", None, ""


KIDS_SHEET = os.path.join(DATA, "kids", "노키즈존_검수.csv")
KIDS_STATE = {"가능": "yes", "노키즈": "no", "일부": "limited"}


def kids_sheet(path: str = KIDS_SHEET) -> dict[str, tuple[str, str | None, str]]:
    """검수 시트에서 사람이 확인한 행. place_uid → (값 상태, 상세, 확인일)."""
    import csv
    if not os.path.exists(path):
        return {}
    out = {}
    for row in csv.DictReader(open(path, encoding="utf-8-sig")):
        state = KIDS_STATE.get((row.get("[확인] 아이 동반") or "").strip())
        checked = (row.get("확인일") or "").strip()
        if (row.get("번호") or "").strip() == "예시" or not state or not checked:
            continue
        detail = (row.get("[확인] 조건") or "").strip() or None
        out[row["place_uid"].strip()] = (state, detail, checked)
    return out


def q(value) -> str:
    if value is None or value == "":
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def main() -> None:
    rows = json.load(open(os.path.join(DATA, "tourapi_음식점_소개정보.json"), encoding="utf-8"))

    lines = ["-- 매장 속성 적재. 생성 파일이므로 직접 고치지 않는다.",
             "-- 원본: datasets/dining/processed/tourapi_음식점_소개정보.json",
             "BEGIN;", "",
             "-- 같은 적재를 다시 돌려도 쌓이지 않게 이 출처의 것을 먼저 비운다.",
             f"DELETE FROM dining.dn_attribute WHERE source_code = '{SOURCE}';", ""]

    sheet = kids_sheet()
    stat: dict[str, Counter] = {code: Counter() for code in [*FIELDS.values(), "kids_allowed"]}
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

        if place_uid in sheet:
            state, detail, checked = sheet.pop(place_uid)
            stat["kids_allowed"][state] += 1
            attr_id = str(uuid.uuid5(NS, f"attr:tourapi:{cid}:kids_allowed"))
            values.append(
                f"    ('{attr_id}', '{place_uid}', '{SOURCE}', '{record_id}', "
                f"'kids_allowed', '{state}', {q(detail)}, {q('노키즈존 검수 ' + checked)}, 'manual', 1.0, "
                f"'{VALID_FROM}')")
            continue
        state, detail, text = kids_state(row)
        stat["kids_allowed"][state] += 1
        if state != "unknown":
            attr_id = str(uuid.uuid5(NS, f"attr:tourapi:{cid}:kids_allowed"))
            values.append(
                f"    ('{attr_id}', '{place_uid}', '{SOURCE}', '{record_id}', "
                f"'kids_allowed', '{state}', {q(detail)}, {q(text)}, 'regex', 0.9, '{VALID_FROM}')")

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
