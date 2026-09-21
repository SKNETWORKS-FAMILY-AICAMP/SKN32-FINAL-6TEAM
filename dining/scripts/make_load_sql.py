"""parse_hours.py 결과를 요식 원장에 넣는 SQL 을 만든다.

psycopg 없이 psql 로 넣을 수 있게 파일로 뽑는다. 같은 파일을 다시 돌려도
결과가 같도록 장소와 레코드의 UUID 는 contentid 에서 만든다.

사용법:  python make_load_sql.py
출력:    load_200.sql
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")   # 원본 데이터
OUT = ROOT                          # 생성물은 저장소 뿌리에 둔다

NS = uuid.UUID("6f1c0d2e-0000-4000-8000-000000000001")
LOAD_ID = str(uuid.uuid5(NS, "load:tourapi:2026-09-21"))
SOURCE = "tourapi_kor_food"
RULES_VERSION = "2026-09-21-parse_hours-v1"
VALID_FROM = date(2026, 9, 21).isoformat()


def q(value) -> str:
    """작은따옴표 문자열. None 은 NULL."""
    if value is None or value == "":
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def jq(obj) -> str:
    """jsonb 리터럴. 달러 인용으로 따옴표 걱정을 없앤다."""
    return "$j$" + json.dumps(obj, ensure_ascii=False) + "$j$::jsonb"


def main() -> None:
    parsed = json.load(open(os.path.join(OUT, "parsed_hours.json"), encoding="utf-8"))
    intro = {r["contentid"]: r for r in
             json.load(open(os.path.join(DATA, "tourapi_음식점_소개정보.json"), encoding="utf-8"))}
    listing = {r["contentid"]: r for r in
               json.load(open(os.path.join(DATA, "tourapi_서울_음식점_목록.json"), encoding="utf-8"))}

    out = ["-- parse_hours.py 결과 적재. 생성 파일이므로 직접 고치지 않는다.",
           "BEGIN;", ""]

    out.append("INSERT INTO dining.dn_load_meta "
               "(load_id, source_code, fetched_at, schema_version, scope, row_count, raw_uri, status)")
    out.append(f"VALUES ('{LOAD_ID}', '{SOURCE}', now(), 'KorService2/detailIntro2', "
               f"'성수, 경복궁, 잠실, 서울역, 명동', {len(parsed)}, "
               f"'travel-data/tourapi_음식점_소개정보.json', 'loaded')")
    out.append("ON CONFLICT (load_id) DO NOTHING;\n")

    n_place = n_rule = n_interval = n_closure = 0

    for row in parsed:
        cid = row["content_id"]
        place_uid = str(uuid.uuid5(NS, f"place:tourapi:{cid}"))
        record_id = str(uuid.uuid5(NS, f"record:tourapi:{cid}"))
        src = intro.get(cid, {})
        lst = listing.get(cid, {})

        lat = lst.get("mapy") or None
        lng = lst.get("mapx") or None
        phone = (src.get("infocenterfood") or lst.get("tel") or "").strip() or None

        out.append(
            "INSERT INTO dining.dn_place (place_uid, name_ko, road_address, lat, lng, "
            "coord_source, area, phone, record_status) VALUES ("
            f"'{place_uid}', {q(row['title'])}, {q(lst.get('addr1') or src.get('_addr'))}, "
            f"{lat or 'NULL'}, {lng or 'NULL'}, '{SOURCE}', {q(row['area'])}, {q(phone)}, 'unknown')"
            " ON CONFLICT (place_uid) DO NOTHING;")
        n_place += 1

        out.append(
            "INSERT INTO dining.dn_source_record (record_id, load_id, source_code, external_id, "
            "place_uid, match_status, raw_json) VALUES ("
            f"'{record_id}', '{LOAD_ID}', '{SOURCE}', {q(cid)}, '{place_uid}', 'auto', {jq(src)})"
            " ON CONFLICT (record_id) DO NOTHING;")

        day_notes = {note[0]: note for note in row["notes"] if note and note[0].isdigit()}

        for day_str, rule in sorted(row["rules"].items()):
            day = int(day_str)
            if rule["coverage"] != "intervals" or not rule["intervals"]:
                continue
            rule_id = str(uuid.uuid5(NS, f"rule:tourapi:{cid}:{day}"))
            confidence = 0.6 if str(day) in day_notes else 0.9
            out.append(
                "INSERT INTO dining.dn_hours_rule (rule_id, place_uid, source_code, record_id, "
                "rule_kind, weekday, coverage, break_state, source_text, extract_method, "
                "extract_confidence, rules_version, valid_from) VALUES ("
                f"'{rule_id}', '{place_uid}', '{SOURCE}', '{record_id}', 'weekly', {day}, "
                f"'{rule['coverage']}', '{rule['break_state']}', {q(row['hours_text'][:900])}, "
                f"'regex', {confidence}, '{RULES_VERSION}', '{VALID_FROM}')"
                " ON CONFLICT (rule_id) DO NOTHING;")
            n_rule += 1

            for iv in rule["intervals"]:
                lo = iv["last_order_min"]
                out.append(
                    "INSERT INTO dining.dn_hours_interval (rule_id, seq, open_min, close_min, "
                    "last_order_min, last_order_state) VALUES ("
                    f"'{rule_id}', {iv['seq']}, {iv['open_min']}, {iv['close_min']}, "
                    f"{lo if lo is not None else 'NULL'}, '{iv['last_order_state']}')"
                    " ON CONFLICT (rule_id, seq) DO NOTHING;")
                n_interval += 1

        for idx, closure in enumerate(row["closures"], 1):
            closure_id = str(uuid.uuid5(NS, f"closure:tourapi:{cid}:{idx}"))
            nth = closure.get("nth")
            nth_sql = ("ARRAY[" + ",".join(str(n) for n in nth) + "]::smallint[]") if nth else "NULL"
            out.append(
                "INSERT INTO dining.dn_closure_rule (closure_id, place_uid, source_code, record_id, "
                "pattern_kind, weekday, nth, holiday_name, holiday_scope, closed_date, source_text, "
                "extract_method, extract_confidence, valid_from) VALUES ("
                f"'{closure_id}', '{place_uid}', '{SOURCE}', '{record_id}', "
                f"'{closure['pattern_kind']}', {closure.get('weekday') or 'NULL'}, {nth_sql}, "
                f"{q(closure.get('holiday_name'))}, {q(closure.get('holiday_scope'))}, "
                f"{q(closure.get('closed_date'))}, {q(row['rest_text'][:400])}, 'regex', 0.9, "
                f"'{VALID_FROM}')"
                " ON CONFLICT (closure_id) DO NOTHING;")
            n_closure += 1

    out += ["", "COMMIT;"]
    path = os.path.join(OUT, "load_200.sql")
    open(path, "w", encoding="utf-8").write("\n".join(out))

    print(f"장소 {n_place}, 영업 규칙 {n_rule}, 구간 {n_interval}, 휴무 규칙 {n_closure}")
    print(f"저장: {path}")


if __name__ == "__main__":
    main()
