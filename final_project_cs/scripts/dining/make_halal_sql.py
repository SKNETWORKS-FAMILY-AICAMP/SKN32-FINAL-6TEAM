"""운영자가 모은 할랄 식당 검수 시트를 원장에 넣는 SQL 로 바꾼다.

무엇을 읽는가.
    data/dining/halal/할랄식당_검수.csv
    판정이 「영업」이고 인허가 관리번호와 좌표가 있는 행만 가게로 넣는다.
    확인 필요 · 폐업 기록만 · 원장에 없음 · 제외 는 넣지 않는다(개수만 알린다).

가게마다 출처 레코드가 둘 붙는다(make_vegan_sql 과 같다).
    근거 레코드    localdata_food. 인허가로 영업을 확인했다. 관리번호가 external_id 다.
    목록 레코드    halal_curated. 「이 목록에 올라 있다」와 웹 근거 등급·출처를 raw_json 에 둔다.

할랄이라고 언제 말하는가.
    웹 근거는 주장이다. KMF 인증이 만료됐거나 목록에서 빠진 곳이 섞여 있다.
    그래서 halal 속성은 사람이 [확인] 등급과 확인일을 채운 행에만 붙인다.

        [확인] 등급                          halal
        KMF 인증 · 타기관 인증 (유효기간 안)   yes
        KMF 인증 · 타기관 인증 (유효기간 지남) 붙이지 않는다 — 모름
        무슬림 자가인증 · 무슬림 프렌들리      limited (조건부 — 상세에 등급)
        포크프리                              limited
        할랄 아님                             no
        모름 · 빈칸                           붙이지 않는다 — 모름

    [확인] 돼지고기가 「있음」이면 등급과 상관없이 no 다.
    술은 판정에 쓰지 않고 상세에 적는다.

이미 있는 가게.
    같은 관리번호로 이미 들어온 가게(비건 목록 등), 또는 60m 안에 이름이 비슷한 가게가 있으면
    새로 만들지 않고 그 가게에 붙인다. 같은 가게가 두 행이 되면 판정이 둘로 갈린다.

사용법:  python scripts/dining/make_halal_sql.py [--dry] [--sheet 시트.csv] [--out 출력.sql] [--today 2026-09-28]
출력:    data/dining/_build/halal.sql
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import uuid
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SHEET = os.path.join(ROOT, "data", "dining", "halal", "할랄식당_검수.csv")
OUT = os.path.join(ROOT, "data", "dining", "_build")

NS = uuid.UUID("6f1c0d2e-0000-4000-8000-000000000003")
LIST_SOURCE = "halal_curated"
EVIDENCE_SOURCE = "localdata_food"
LOADED = "2026-09-27"                 # 시트를 만든 날. load_id 가 재구축해도 같게

#: 같은 가게로 볼 거리와 이름 유사도. 022 매칭기(80m · 0.75)보다 이름을 느슨하게 본다 —
#: 시트 상호(「양국 (Yang Good)」)와 원장 상호(「양국」)가 괄호·영문으로 갈린다.
SAME_PLACE_M = 60
SAME_PLACE_SIM = 0.6

CERTIFIED = {"KMF 인증", "타기관 인증"}
LIMITED = {"무슬림 자가인증", "무슬림 프렌들리", "포크프리"}


def q(value) -> str:
    if value is None or str(value).strip() == "":
        return "NULL"
    return "'" + str(value).strip().replace("'", "''") + "'"


def jq(obj) -> str:
    return "$j$" + json.dumps(obj, ensure_ascii=False) + "$j$::jsonb"


def arg(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def full_address(addr: str) -> str:
    return re.sub(r"^서울\s", "서울특별시 ", addr.strip())


def halal_state(row: dict, today: date) -> tuple[str | None, str | None]:
    """[확인] 칸 → (value_state, 상세). 붙이지 않을 때는 (None, 이유)."""
    grade = (row.get("[확인] 등급") or "").strip()
    checked = (row.get("확인일") or "").strip()
    if not grade or not checked:
        return None, "아직 확인하지 않음"
    pork = (row.get("[확인] 돼지고기") or "").strip()
    alcohol = (row.get("[확인] 술") or "").strip()
    extra = [f"술 {alcohol}"] if alcohol and alcohol != "모름" else []

    if pork == "있음":
        return "no", " · ".join([f"{grade}", "돼지고기 있음", *extra])
    if grade == "할랄 아님":
        return "no", " · ".join([grade, *extra])
    if grade in CERTIFIED:
        until = (row.get("[확인] 인증 유효기간") or "").strip()[:10]
        try:
            if until and date.fromisoformat(until) < today:
                return None, f"{grade} 만료({until})"
        except ValueError:
            pass
        return "yes", " · ".join([f"{grade}" + (f" ~{until}" if until else ""), *extra])
    if grade in LIMITED:
        return "limited", " · ".join([grade, *extra])
    return None, f"등급 「{grade}」 — 모름으로 둔다"


def main() -> None:
    sheet = arg("--sheet", SHEET)
    today = date.fromisoformat(arg("--today", date.today().isoformat()))
    rows = [r for r in csv.DictReader(open(sheet, encoding="utf-8-sig"))
            if (r.get("번호") or "").strip() != "예시"]

    load_list = str(uuid.uuid5(NS, f"load:halal:{LIST_SOURCE}:{LOADED}"))
    load_ev = str(uuid.uuid5(NS, f"load:halal:{EVIDENCE_SOURCE}:{LOADED}"))
    body: list[str] = []
    skipped: dict[str, int] = {}
    attrs: dict[str, int] = {}
    taken = 0

    for row in rows:
        verdict = (row.get("판정") or "").strip()
        mgmt = (row.get("관리번호") or "").strip()
        lat, lng = (row.get("위도") or "").strip(), (row.get("경도") or "").strip()
        if verdict != "영업" or not mgmt or not lat or not lng:
            skipped[verdict or "빈칸"] = skipped.get(verdict or "빈칸", 0) + 1
            continue
        taken += 1
        label = row["식당"].strip()
        name_ko = (row.get("원장상호") or label).strip()
        new_uid = str(uuid.uuid5(NS, f"place:halal:{mgmt}"))
        # 이미 있는 가게를 찾는다 — 같은 관리번호가 먼저, 없으면 가깝고 이름이 비슷한 곳.
        pick = (f"pg_temp.halal_place('{new_uid}'::uuid, {q(mgmt)}, {q(name_ko)}, {q(label)}, "
                f"{lat}, {lng})")

        body.append(
            "INSERT INTO dining.dn_place (place_uid, name_ko, road_address, lat, lng, coord_source, "
            "area, phone, record_status) "
            f"SELECT '{new_uid}', {q(name_ko)}, {q(full_address(row['주소']))}, {lat}, {lng}, "
            f"'{EVIDENCE_SOURCE}', {q(row['자치구'])}, {q(row.get('전화'))}, 'active' "
            f"WHERE {pick} = '{new_uid}'::uuid "
            "ON CONFLICT (place_uid) DO NOTHING;")

        ev_id = str(uuid.uuid5(NS, f"record:halal:{EVIDENCE_SOURCE}:{mgmt}"))
        body.append(
            "INSERT INTO dining.dn_source_record (record_id, load_id, source_code, external_id, "
            "place_uid, match_status, match_basis, raw_json) "
            f"SELECT '{ev_id}', '{load_ev}', '{EVIDENCE_SOURCE}', {q(mgmt)}, {pick}, 'auto', "
            f"{jq({'기준': '인허가 관리번호'})}, {jq({'원장상호': name_ko, '원장': row.get('원장'), '대조일': LOADED})} "
            f"WHERE NOT EXISTS (SELECT 1 FROM dining.dn_source_record "
            f"WHERE source_code = '{EVIDENCE_SOURCE}' AND external_id = {q(mgmt)}) "
            "ON CONFLICT (record_id) DO NOTHING;")

        list_id = str(uuid.uuid5(NS, f"record:halal:list:{mgmt}"))
        raw = {"목록": os.path.basename(sheet), "번호": row["번호"], "상호": label,
               "웹 근거 등급": row.get("웹 근거 등급(초안)") or None,
               "근거 출처": row.get("근거 출처") or None, "메모": row.get("메모") or None}
        body.append(
            "INSERT INTO dining.dn_source_record (record_id, load_id, source_code, external_id, "
            "place_uid, match_status, raw_json) "
            f"SELECT '{list_id}', '{load_list}', '{LIST_SOURCE}', {q(mgmt)}, {pick}, 'confirmed', {jq(raw)} "
            "ON CONFLICT (record_id) DO NOTHING;")

        state, detail = halal_state(row, today)
        key = state or "붙이지 않음"
        attrs[key] = attrs.get(key, 0) + 1
        if state:
            attr_id = str(uuid.uuid5(NS, f"attr:halal:{mgmt}"))
            body.append(
                "INSERT INTO dining.dn_attribute (attr_id, place_uid, source_code, record_id, attr_code, "
                "value_state, value_detail, extract_method, valid_from) "
                f"SELECT '{attr_id}', {pick}, '{LIST_SOURCE}', '{list_id}', 'halal', "
                f"'{state}', {q(detail)}, 'manual', {q(row['확인일'])} "
                "ON CONFLICT (attr_id) DO UPDATE SET value_state = EXCLUDED.value_state, "
                "value_detail = EXCLUDED.value_detail, valid_from = EXCLUDED.valid_from;")

    head = [
        "-- make_halal_sql.py 결과. 생성 파일이므로 직접 고치지 않는다.",
        "BEGIN;", "",
        "-- 이미 있는 가게면 그 place_uid, 없으면 새 place_uid.",
        "CREATE OR REPLACE FUNCTION pg_temp.halal_place(p_new uuid, p_mgmt text, p_name text,",
        "                                               p_label text, p_lat float8, p_lng float8)",
        "RETURNS uuid LANGUAGE sql STABLE AS $f$",
        "    SELECT coalesce(",
        "        (SELECT sr.place_uid FROM dining.dn_source_record sr",
        "          WHERE sr.external_id = p_mgmt AND sr.source_code IN ('localdata_food', 'localdata_rest')",
        "          LIMIT 1),",
        "        (SELECT p.place_uid FROM dining.dn_place p",
        "          WHERE p.place_uid <> p_new AND p.lat IS NOT NULL",
        f"            AND dining.distance_m(p.lat, p.lng, p_lat, p_lng) <= {SAME_PLACE_M}",
        "            AND greatest(dining.name_sim(dining.norm_name(p.name_ko), dining.norm_name(p_name)),",
        f"                         dining.name_sim(dining.norm_name(p.name_ko), dining.norm_name(p_label))) >= {SAME_PLACE_SIM}",
        "          ORDER BY dining.distance_m(p.lat, p.lng, p_lat, p_lng) LIMIT 1),",
        "        p_new)",
        "$f$;", "",
        "INSERT INTO dining.dn_load_meta (load_id, source_code, fetched_at, schema_version, scope, "
        "row_count, raw_uri, status) VALUES "
        f"('{load_list}', '{LIST_SOURCE}', '{LOADED} 12:00+09', 'halal-sheet-v1', '서울 할랄 식당 검수 시트', "
        f"{taken}, 'data/dining/halal/{os.path.basename(sheet)}', 'loaded'), "
        f"('{load_ev}', '{EVIDENCE_SOURCE}', '{LOADED} 12:00+09', 'halal-sheet-v1', '할랄 목록의 인허가 대조', "
        f"{taken}, 'data/dining/halal/{os.path.basename(sheet)}', 'loaded') "
        "ON CONFLICT (load_id) DO NOTHING;", ""]
    sql = "\n".join(head + body + ["", "COMMIT;", ""])

    print(f"할랄 시트 {len(rows)}행 → 가게 {taken}곳 / 넣지 않음 {dict(sorted(skipped.items()))}"
          f" / 할랄 속성 {dict(sorted(attrs.items()))}")
    if "--dry" in sys.argv:
        return
    os.makedirs(OUT, exist_ok=True)
    path = arg("--out", os.path.join(OUT, "halal.sql"))
    open(path, "w", encoding="utf-8").write(sql)
    print(f"→ {path}")


if __name__ == "__main__":
    main()
