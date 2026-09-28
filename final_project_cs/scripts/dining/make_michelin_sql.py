"""미쉐린 가이드 서울 목록을 원장의 michelin 속성으로 넣는 SQL 을 만든다.

무엇을 읽는가.
    data/dining/michelin/미쉐린_서울_2026.csv  (상호, 등급) 180곳
    guide.michelin.com 의 서울 목록(별 · 빕 구르망 · 셀렉티드)에서 이름과 등급만 옮겼다.

어떻게 잇는가.
    1  상호가 같다(띄어쓰기·괄호·기호를 뗀 뒤). 한 곳만 걸릴 때만 잇는다.
    2  ALIAS 에 적은 곳. 원장 상호가 달라 1 에서 안 걸리지만, 가이드 페이지의 주소와
       원장 주소를 사람이 맞춰 본 곳이다.
    이름만 비슷한 곳은 잇지 않는다. 「오레노 라멘」은 원장에 「오레노라멘 본점」이 있지만
    가이드 주소(독막로8길 16)와 달라 뺐다.

무엇을 넣는가.
    잇는 가게마다 출처 레코드(michelin_guide) 하나와 속성 michelin = yes 하나.
    상세는 「1스타 (2026)」처럼 등급과 에디션. 가이드에 없는 곳은 행을 만들지 않는다.

사용법:  python scripts/dining/make_michelin_sql.py [--dry]
출력:    data/dining/_build/michelin.sql
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "data", "dining")
OUT = os.path.join(DATA, "_build")
LIST = os.path.join(DATA, "michelin", "미쉐린_서울_2026.csv")

NS = uuid.UUID("6f1c0d2e-0000-4000-8000-000000000004")
SOURCE = "michelin_guide"
EDITION = "2026"
LOADED = "2026-09-28"

#: 가이드 상호 → 원장 상호. 가이드 페이지 주소와 원장 주소가 같은 것만 적는다(2026-09-28).
ALIAS = {
    "무오키": "무오키(MUOKI)",          # 강남구 학동로55길 12-12
    "버드나무집": "버드나무집 본점",     # 서초구 효령로 434
    "봉밀가": "봉밀가 강남구청점",       # 강남구 선릉로 664
}


def norm(name: str | None) -> str:
    """한글·영문·숫자만 남긴다. SQL 쪽 regexp_replace 와 같은 규칙이다."""
    return re.sub(r"[^가-힣a-z0-9]", "", (name or "").lower())


def q(value) -> str:
    if value is None or str(value) == "":
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def main() -> None:
    rows = list(csv.DictReader(open(LIST, encoding="utf-8")))
    load_id = str(uuid.uuid5(NS, f"load:michelin:{EDITION}"))
    lines = ["-- make_michelin_sql.py 결과. 생성 파일이므로 직접 고치지 않는다.",
             "BEGIN;", "",
             "-- 같은 에디션을 다시 넣어도 쌓이지 않게 이 출처의 것을 먼저 비운다.",
             f"DELETE FROM dining.dn_attribute WHERE source_code = '{SOURCE}';",
             f"DELETE FROM dining.dn_source_record WHERE source_code = '{SOURCE}';",
             f"DELETE FROM dining.dn_load_meta WHERE source_code = '{SOURCE}';", "",
             "INSERT INTO dining.dn_load_meta (load_id, source_code, fetched_at, schema_version, scope, "
             f"row_count, raw_uri, status) VALUES ('{load_id}', '{SOURCE}', '{LOADED} 12:00+09', "
             f"'michelin-{EDITION}', '미쉐린 가이드 서울 {EDITION}', {len(rows)}, "
             f"'data/dining/michelin/{os.path.basename(LIST)}', 'loaded');", ""]
    for row in rows:
        name, grade = row["상호"].strip(), row["등급"].strip()
        target = ALIAS.get(name)
        # 원장 상호로 찾는다. 같은 이름이 둘 이상이면 잇지 않는다(어느 지점인지 모른다).
        match = (f"(SELECT place_uid FROM dining.dn_place WHERE name_ko = {q(target)})" if target else
                 "(SELECT min(place_uid::text)::uuid FROM dining.dn_place "
                 "WHERE regexp_replace(lower(name_ko), '[^가-힣a-z0-9]', '', 'g') = "
                 f"{q(norm(name))} HAVING count(*) = 1)")
        rec_id = str(uuid.uuid5(NS, f"record:michelin:{EDITION}:{name}"))
        attr_id = str(uuid.uuid5(NS, f"attr:michelin:{EDITION}:{name}"))
        raw = {"상호": name, "등급": grade, "에디션": EDITION}
        lines.append(
            "INSERT INTO dining.dn_source_record (record_id, load_id, source_code, external_id, "
            f"place_uid, match_status, match_basis, raw_json) SELECT '{rec_id}', '{load_id}', '{SOURCE}', "
            f"{q(name)}, m.uid, 'confirmed', "
            f"$j${json.dumps({'기준': '주소 대조' if target else '상호 일치'}, ensure_ascii=False)}$j$::jsonb, "
            f"$j${json.dumps(raw, ensure_ascii=False)}$j$::jsonb "
            f"FROM (SELECT {match} AS uid) m WHERE m.uid IS NOT NULL;")
        lines.append(
            "INSERT INTO dining.dn_attribute (attr_id, place_uid, source_code, record_id, attr_code, "
            "value_state, value_detail, source_text, extract_method, valid_from) "
            f"SELECT '{attr_id}', sr.place_uid, '{SOURCE}', sr.record_id, 'michelin', 'yes', "
            f"{q(f'{grade} ({EDITION})')}, {q(f'미쉐린 가이드 서울 {EDITION} · {grade}')}, 'manual', '{LOADED}' "
            f"FROM dining.dn_source_record sr WHERE sr.record_id = '{rec_id}';")
    lines += ["", "COMMIT;", ""]
    print(f"미쉐린 가이드 서울 {EDITION}: {len(rows)}곳 (주소로 맞춘 별칭 {len(ALIAS)}곳)")
    if "--dry" in sys.argv:
        return
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "michelin.sql")
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    print(f"→ {path}")


if __name__ == "__main__":
    main()
