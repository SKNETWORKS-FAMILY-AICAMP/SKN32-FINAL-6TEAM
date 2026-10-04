"""폐업 대조 시트에서 사람이 확인한 폐업 · 이전을 원장에 반영한다.

    python scripts/dining/make_closure_sql.py      → datasets/dining/processed/_build/closure.sql

시트는 datasets/dining/processed/closure/폐업대조_*.csv (가장 최근 것). 인허가 자료(일반음식점, 정상영업)와
원장을 대조하고 카카오맵으로 다시 본 결과다. 대조만으로는 넣지 않는다.
확인일이 적힌 행만 넣는다(다른 검수 시트와 같은 규칙).

    [확인] 영업 여부  폐업 → record_status = 'closed'. 판정 · 대안에서 빠진다
                      이전 → 새 주소 · 새 위도 · 새 경도로 바꾼다. 좌표가 없으면 주소만
                      상호 변경 → 새 상호로 바꾼다. 같은 자리에서 이름만 바뀐 영업 중인 가게
                      지점 추가 → 원장에 없던 다른 지점을 새 가게로 만든다. 대표 분류는 적재 뒤 refresh_category 가 붙이고
                                  인허가 관리번호(새 관리번호)를 근거 레코드로 남긴다
                      이전 · 지점 추가에 새 상호가 있으면 상호도 바꾼다(「덕후선생」→「덕후선생 강남점」)
                      주소 보완 → 이전과 같이 새 주소로 바꾼다. 가게는 그대로이고 층 · 호수 같은 상세만 더한 것
                      중복 → 같은 가게가 원장에 두 줄. 「본점 place_uid」에 남길 줄을 적는다.
                             이 줄의 속성 · 출처 기록 · 외부 링크를 남길 줄로 옮기고(남길 줄에 없는 것만)
                             이 줄은 closed 로 닫는다. 영업시간은 옮기지 않는다 — 두 벌이 겹치면 판정이 엉킨다
                      영업 · 빈칸 → 아무것도 하지 않는다
    새 분류           적혀 있으면 대표 분류를 그 값으로 고정한다(manual)

가게를 지우지 않는다. 닫힌 가게도 원장에 남아야 「왜 대안에서 빠졌는지」를 설명할 수 있다.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
DINING_DATA = os.environ.get("DINING_DATA") or os.path.join(  # 데이터는 git 밖(datasets/dining/processed)
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "datasets", "dining", "processed")
ROOT = os.path.dirname(os.path.dirname(HERE))
SHEETS = os.path.join(DINING_DATA, "closure", "폐업대조_[0-9]*.csv")   # 날짜 파일만
OUT = os.path.join(DINING_DATA, "_build", "closure.sql")
NS = uuid.UUID("6f1c0d2e-0000-4000-8000-000000000007")
SOURCE = "localdata_food"          # 지점 추가의 근거: 지방행정 인허가(일반음식점)
CHECKED = "2026-09-28"


def q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def build(sheet: str) -> tuple[list[str], dict[str, int]]:
    load_id = str(uuid.uuid5(NS, f"load:closure:{os.path.basename(sheet)}"))
    lines = ["-- 폐업 대조 반영. 만든 것: scripts/dining/make_closure_sql.py", "BEGIN;",
             "INSERT INTO dining.dn_load_meta (load_id, source_code, fetched_at, schema_version, scope, "
             f"row_count, raw_uri, status) VALUES ('{load_id}', '{SOURCE}', '{CHECKED} 12:00+09', "
             f"'closure-check', '폐업 대조로 찾은 지점', 0, "
             f"{q('datasets/dining/processed/closure/' + os.path.basename(sheet))}, 'loaded') "
             "ON CONFLICT (load_id) DO NOTHING;"]
    cats: list[str] = []
    n = {"폐업": 0, "이전": 0, "주소 보완": 0, "상호 변경": 0, "지점 추가": 0, "중복": 0, "건너뜀": 0}
    with open(sheet, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            verdict = (row.get("[확인] 영업 여부") or "").strip()
            if not (row.get("확인일") or "").strip() or verdict not in n or verdict == "건너뜀":
                continue
            uid = (row.get("place_uid") or "").strip()
            name = (row.get("새 상호") or "").strip()
            addr = (row.get("새 주소") or "").strip()
            lat, lng = (row.get("새 위도") or "").strip(), (row.get("새 경도") or "").strip()
            if verdict == "폐업":
                lines.append("UPDATE dining.dn_place SET record_status = 'closed', updated_at = now() "
                             f"WHERE place_uid = {q(uid)};")
            elif verdict == "중복":
                keep = (row.get("본점 place_uid") or "").strip()
                if not keep or keep == uid:
                    n["건너뜀"] += 1
                    continue
                k, d = q(keep), q(uid)
                lines += [
                    f"UPDATE dining.dn_attribute a SET place_uid = {k} WHERE a.place_uid = {d} AND a.retired_at IS NULL "
                    f"AND NOT EXISTS (SELECT 1 FROM dining.dn_attribute b WHERE b.place_uid = {k} "
                    "AND b.attr_code = a.attr_code AND b.retired_at IS NULL);",
                    f"UPDATE dining.dn_source_record SET place_uid = {k} WHERE place_uid = {d};",
                    f"UPDATE dining.dn_external_ref r SET place_uid = {k} WHERE r.place_uid = {d} AND r.retired_at IS NULL "
                    f"AND NOT EXISTS (SELECT 1 FROM dining.dn_external_ref x WHERE x.place_uid = {k} "
                    "AND x.kind = r.kind AND x.retired_at IS NULL);",
                    f"UPDATE dining.dn_place SET record_status = 'closed', updated_at = now() WHERE place_uid = {d};",
                ]
            elif verdict == "상호 변경":
                if not name:
                    n["건너뜀"] += 1
                    continue
                lines.append(f"UPDATE dining.dn_place SET name_ko = {q(name)}, record_status = 'active', "
                             f"updated_at = now() WHERE place_uid = {q(uid)};")
            elif verdict in ("이전", "주소 보완"):
                if not addr:
                    n["건너뜀"] += 1
                    continue
                sets = [f"road_address = {q(addr)}", "updated_at = now()"]
                if name:
                    sets.append(f"name_ko = {q(name)}")
                if lat and lng:
                    sets += [f"lat = {float(lat)}", f"lng = {float(lng)}", "coord_source = 'operator_check'"]
                lines.append(f"UPDATE dining.dn_place SET {', '.join(sets)} WHERE place_uid = {q(uid)};")
            else:                                   # 지점 추가
                licence = (row.get("새 관리번호") or "").strip()
                parent = (row.get("본점 place_uid") or "").strip()
                name = name or (row.get("상호") or "").strip()
                if not (licence and addr and lat and lng and name):
                    n["건너뜀"] += 1
                    continue
                new_uid = str(uuid.uuid5(NS, f"place:branch:{licence}"))
                rec_id = str(uuid.uuid5(NS, f"record:branch:{licence}"))
                lines.append(
                    "INSERT INTO dining.dn_place (place_uid, name_ko, road_address, lat, lng, coord_source, "
                    "area, record_status) "
                    f"VALUES ('{new_uid}', {q(name)}, {q(addr)}, {float(lat)}, {float(lng)}, '{SOURCE}', "
                    f"{q((row.get('자치구') or '').strip())}, 'active') ON CONFLICT (place_uid) DO NOTHING;")
                raw = {"관리번호": licence, "상호": name, "주소": addr, "본점": parent, "확인일": row["확인일"]}
                lines.append(
                    "INSERT INTO dining.dn_source_record (record_id, load_id, source_code, external_id, "
                    f"place_uid, match_status, match_basis, raw_json) VALUES ('{rec_id}', '{load_id}', "
                    f"'{SOURCE}', {q(licence)}, '{new_uid}', 'confirmed', "
                    f"$j${json.dumps({'기준': '폐업 대조 중 사람이 확인한 지점'}, ensure_ascii=False)}$j$::jsonb, "
                    f"$j${json.dumps(raw, ensure_ascii=False)}$j$::jsonb) ON CONFLICT DO NOTHING;")
            n[verdict] += 1
            cat = (row.get("새 분류") or "").strip()
            if cat:
                # 사람이 정한 분류. manual 은 refresh_category 가 덮지 않는다(214).
                target = f"'{new_uid}'" if verdict == "지점 추가" else q(uid)
                cats.append(f"UPDATE dining.dn_place SET category = {q(cat)}, category_method = 'manual' "
                            f"WHERE place_uid = {target};")
    lines += cats + ["COMMIT;", ""]
    return lines, n


def main() -> None:
    sheets = sorted(glob.glob(SHEETS))
    lines, n = build(sheets[-1]) if sheets else (["-- 폐업 대조 시트 없음", ""], {})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"폐업 대조 {os.path.basename(sheets[-1]) if sheets else '-'}: {n} → {OUT}")


if __name__ == "__main__":
    main()
