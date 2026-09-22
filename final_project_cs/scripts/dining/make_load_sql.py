"""parse_hours.py 결과를 요식 원장에 넣는 SQL 을 만든다.

psycopg 없이 psql 로 넣을 수 있게 파일로 뽑는다. 같은 파일을 다시 돌려도
결과가 같도록 장소와 레코드의 UUID 는 contentid 에서 만든다.

사용법:  python make_load_sql.py
출력:    load_200.sql
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))   # final_project_cs
DATA = os.path.join(ROOT, "data", "dining")     # 원본 데이터
OUT = os.path.join(ROOT, "data", "dining", "_build")  # 생성물

NS = uuid.UUID("6f1c0d2e-0000-4000-8000-000000000001")
LOAD_ID = str(uuid.uuid5(NS, "load:tourapi:2026-09-21"))
SOURCE = "tourapi_kor_food"
VALID_FROM = date(2026, 9, 21).isoformat()


def rules_version() -> str:
    """파서 내용에서 버전을 만든다.

    손으로 적어 두면 안 바뀐다. 파서를 일곱 번 고치는 동안 v1 그대로였고,
    그래서 어제 결과와 오늘 결과를 구분할 방법이 없었다.
    파일 내용이 바뀌면 값이 바뀌어야 한다. 그래야 품질 비교가 성립한다.
    """
    src = os.path.join(HERE, "parse_hours.py")
    digest = hashlib.sha256(open(src, "rb").read()).hexdigest()[:8]
    return f"parse_hours-{digest}"


RULES_VERSION = rules_version()


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
           "BEGIN;", "",
           "-- 파서를 고친 뒤 다시 돌리면 고친 결과가 반영되어야 한다.",
           "-- 규칙 id 는 차례로 매기므로 규칙 수가 줄면 남은 옛 행이 그대로 살아남는다.",
           "-- 「명절당일」이 유령 일요일 휴무로 남아 있던 것이 그래서였다.",
           "-- 이 출처가 만든 것만 지운다. operator_check 처럼 사람이 넣은 것은 건드리지 않는다.",
           f"DELETE FROM dining.dn_closure_coverage WHERE source_code = '{SOURCE}';",
           f"DELETE FROM dining.dn_closure_rule WHERE source_code = '{SOURCE}';",
           f"DELETE FROM dining.dn_hours_rule   WHERE source_code = '{SOURCE}';",
           "-- 구간은 규칙에 ON DELETE CASCADE 로 달려 있어 함께 지워진다.",
           ""]

    out.append("INSERT INTO dining.dn_load_meta "
               "(load_id, source_code, fetched_at, schema_version, scope, row_count, raw_uri, status)")
    out.append(f"VALUES ('{LOAD_ID}', '{SOURCE}', now(), 'KorService2/detailIntro2', "
               f"'성수, 경복궁, 잠실, 서울역', {len(parsed)}, "
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

        # 휴무를 어디까지 아는가. 규칙이 없는 것과 쉬는 날이 없는 것은 다르다.
        out.append(
            "INSERT INTO dining.dn_closure_coverage (place_uid, source_code, record_id, "
            "state, source_text, valid_from) VALUES ("
            f"'{place_uid}', '{SOURCE}', '{record_id}', "
            f"'{row.get('closure_state', 'unknown')}', {q(row['rest_text'][:400])}, "
            f"'{VALID_FROM}')"
            " ON CONFLICT (place_uid, source_code) DO UPDATE SET state = EXCLUDED.state,"
            " source_text = EXCLUDED.source_text;")

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
