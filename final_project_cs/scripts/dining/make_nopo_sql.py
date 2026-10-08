"""노포 목록을 원장의 nopo 속성으로 넣는 SQL 을 만든다. `[2026-10-07]`

무엇을 읽는가.
    datasets/dining/processed/nopo/노포_서울_카카오맵.csv  (상호, 주소, 자치구) 173곳
    카카오맵 공개 즐겨찾기 폴더 「노포 지도」(만든 이 「노포탐방대장」, 200곳)에서 주소가 서울인 곳만
    화면에 보이는 그대로 옮겼다(2026-10-07). 목록은 사용자가 자기 기준의 노포로 확인했다.
    ★다른 사용자가 만든 목록이다 — 운영에 쓰기로 정했다(221, production_allowed = true). 화면에 출처를 밝힌다.

어떻게 잇는가. SQL 안에서 판정한다 — 생성할 때 DB 가 필요 없다(rebuild 가 원장보다 먼저 돌린다).
    1  자치구가 같고, 도로명 주소의 도로명 · 건물번호가 같고, 상호가 같다(띄어쓰기 · 기호를 뗀 뒤
       한쪽이 다른 쪽을 품어도 된다 — 「공평동꼼장어 본점」 ↔ 「공평동꼼장어」).
    2  ALIAS 에 적은 곳 — 주소는 같은데 원장 상호가 달라 1 에서 안 걸리는 곳. 사람이 같은 가게로 봤다.
    후보가 둘 이상이면 잇지 않는다. 주소가 다르면 이름이 같아도 잇지 않는다(이전 · 다른 지점일 수 있다).
    원장에 없는 가게는 만들지 않는다 — 좌표 · 영업시간이 없어 넣어도 판정이 「모름」이다.

무엇을 넣는가.
    잇는 가게마다 출처 레코드(nopo_kakao_curation) 하나와 속성 nopo = yes 하나. 없는 곳은 행을 만들지 않는다.

원장에 없던 가게 — 검수 시트에서 새로 만든다. `[2026-10-07]`
    검수 시트(--sheet 로 만든 것)에서 ①확인일이 있고 ②메모에 「폐업」이 없고 ③인허가 관리번호가 있는 행만.
    - 가게: 표시명 · 도로명주소 · 자치구 · 전화, 좌표는 인허가 원장의 좌표(EPSG:5174 → WGS84, tm5174.py).
      같은 관리번호의 가게가 이미 원장에 있으면(비건 · 할랄이 먼저 만든 곳) 새로 만들지 않고 그 가게에 붙인다.
    - 출처 레코드: 인허가(localdata_food · localdata_rest, external_id = 관리번호) 하나와 노포 목록 하나.
    - 속성 nopo = yes, 영업시간 · 휴무는 make_vegan_sql.hours_sql 이 시트를 읽어 넣는다(브레이크타임 칸 포함).
    관리번호가 없거나 인허가에 좌표가 없는 행은 브이월드 지오코더 좌표(--geocode 로 만든 노포_좌표_브이월드.csv)를 쓴다.
    그것도 없으면 만들지 않고 이름을 알린다. `[2026-10-08]`

원장에 없는 가게 — 영업시간 검수 시트(--sheet). `[2026-10-07]`
    원장에 이어지지 않은 곳을 서울시 인허가(일반 · 휴게음식점, datasets/dining/raw/)와 대 본다 — 도로명 주소가 같고
    상호가 서로를 품으면 같은 곳. 인허가에 있으나 영업 중이 아닌 곳(폐업 · 휴업)은 **시트에서 뺀다**(목록이 낡은 것).
    나머지(인허가 영업 중 + 인허가에서 못 찾은 곳)는 시트에 싣고, 사람이 영업시간을 적는다. 형식은 비건 · 미쉐린 검수
    시트와 같다(make_vegan_sql.hours_sql 이 읽는다). 「브레이크타임」 칸은 영업하는 모든 요일에서 그 구간을 뺀다
    (요일마다 다르면 요일 칸에 「11:30-15:00, 17:00-20:00」처럼 적는다). 인허가 관리번호는 가게를 만들 때 좌표를 찾는 열쇠다.
    ★이미 있는 시트는 덮어쓰지 않는다 — 사람이 적은 것을 지우지 않게. 칸이 바뀌면 --upgrade 로 적은 값을 옮겨 다시
      만든다(상호 · 주소가 같은 행끼리). --force 는 적은 것을 버리고 새로 만든다.

사용법:  python scripts/dining/make_nopo_sql.py [--dry]     SQL 생성
         python scripts/dining/make_nopo_sql.py --report    원장(DINING_DSN)과 짝짓기 결과 표 — 사람 확인용
         python scripts/dining/make_nopo_sql.py --sheet [--upgrade | --force]   원장에 없는 가게의 영업시간 검수 시트
         python scripts/dining/make_nopo_sql.py --geocode [--force]   좌표가 없는 행을 브이월드로 찾는다(ACOP_VWORLD_API_KEY)
출력:    datasets/dining/processed/_build/nopo.sql
         datasets/dining/processed/_build/nopo_match.csv  (--report, 엑셀용 BOM)
         datasets/dining/processed/nopo/노포_영업시간_검수.csv  (--sheet, 엑셀용 BOM)
"""
from __future__ import annotations

import collections
import csv
import json
import os
import re
import sys
import urllib.parse
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DINING_DATA = os.environ.get("DINING_DATA") or os.path.join(  # 데이터는 git 밖(datasets/dining/processed)
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "datasets", "dining", "processed")
LIST = os.path.join(DINING_DATA, "nopo", "노포_서울_카카오맵.csv")
SHEET = os.path.join(DINING_DATA, "nopo", "노포_영업시간_검수.csv")
#: 브이월드 지오코더 결과 — 공공데이터라 저장해도 된다. 생성기(rebuild)는 이 파일만 읽고 네트워크를 타지 않는다
GEOCODED = os.path.join(DINING_DATA, "nopo", "노포_좌표_브이월드.csv")
GEOCODE_SOURCE = "vworld_geocoder"
#: 이 적재가 지금까지 만든 가게 uid. 시트에서 주소 · 관리번호가 바뀌면 옛 가게가 남는데, 그것만 지우기 위해 적어 둔다 `[2026-10-08]`
#: (원장에는 「누가 만든 가게인가」 칸이 없다. 기록이 없는 가게를 모두 지우면 다른 적재의 가게까지 지운다)
MADE = os.path.join(DINING_DATA, "nopo", "노포_만든_가게.json")
RAW = os.path.join(os.path.dirname(DINING_DATA), "raw")
LOCALDATA = (("localdata_food", "서울시 일반음식점 인허가 정보.csv"),
             ("localdata_rest", "서울시 휴게음식점 인허가 정보.csv"))
OUT = os.path.join(DINING_DATA, "_build")
DSN = os.environ.get("DINING_DSN", "postgresql://postgres:postgres@127.0.0.1:5433/dining_rebuild")

NS = uuid.UUID("6f1c0d2e-0000-4000-8000-000000000005")
SOURCE = "nopo_kakao_curation"
LOADED = "2026-10-07"

#: 목록 상호 → 원장 상호. 주소가 같고 사람이 같은 가게로 본 곳만 적는다(2026-10-07).
ALIAS = {
    "망원동즉석우동돈까스": "망원동즉석우동 본점",      # 마포구 동교로 83
    "장군보쌈": "장군굴보쌈",                          # 종로구 수표로20길 22
    "아차산할아버지손두부": "원조할아버지손두부",       # 광진구 자양로 324
}

#: 검수 시트로 만든 가게의 영업시간 적재 묶음 이름(make_vegan_sql.hours_sql 의 tag)
HOURS_TAG = "nopo"
LOCALDATA_LABEL = {"localdata_food": "일반음식점", "localdata_rest": "휴게음식점"}

#: SQL 쪽 상호 정규화 — norm() 과 같은 규칙이다.
_NORM_SQL = "regexp_replace(lower(p.name_ko), '[^가-힣a-z0-9]', '', 'g')"


def norm(name: str | None) -> str:
    """한글 · 영문 · 숫자만 남긴다. make_michelin_sql.norm 과 같은 규칙이다."""
    return re.sub(r"[^가-힣a-z0-9]", "", (name or "").lower())


def addr_key(address: str | None) -> tuple[str, str, str] | None:
    """「서울 종로구 종로46길 1 1층 (창신동)」 → ("종로구", "종로46길", "1"). 층 · 호 · 괄호는 버린다.

    시 이름은 「서울」 · 「서울특별시」 둘 다 온다. 도로명이 아닌 주소(번지)는 None — 잇지 않는다.
    """
    words = re.sub(r"\(.*?\)|,", " ", address or "").split()     # 「동호로 249, 신라호텔」의 쉼표도 뗀다
    if words and words[0].startswith("서울"):
        words = words[1:]
    if len(words) < 3 or not words[0].endswith("구"):
        return None
    district, road, number = words[0], words[1], words[2]
    if not re.search(r"(로|길)$", road) or not re.match(r"^\d+(-\d+)?$", number):
        return None
    return district, road, number


def q(value) -> str:
    if value is None or str(value) == "":
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


#: make_vegan_sql 의 NS — 영업시간 적재(hours_sql)의 load_id 를 같은 규칙으로 계산한다
VEGAN_NS = uuid.UUID("6f1c0d2e-0000-4000-8000-000000000001")


def _own_loads() -> list[str]:
    """이 적재가 쓰는 load_id 전부 — 노포 목록 · 인허가(두 종류) · 영업시간(hours_sql, tag=nopo)."""
    return ([str(uuid.uuid5(NS, f"load:nopo:{LOADED}"))] + [_localdata_load(src) for src in LOCALDATA_LABEL]
            + [str(uuid.uuid5(VEGAN_NS, f"load:{HOURS_TAG}-hours:operator_check"))])


def match_sql(name: str, key: tuple[str, str, str], skip: tuple[str, ...] = ()) -> str:
    """그 가게의 place_uid 하나 — 후보가 하나일 때만. 자치구 · 도로명 · 건물번호 · 상호를 모두 본다.

    `skip` — 검수 시트로 이 적재가 만드는 가게. 다시 돌릴 때 그 가게에 「기존 가게」로 또 붙지 않게 뺀다.
    """
    district, road, number = key
    # 도로명 뒤에 건물번호가 오고, 번호 뒤는 끝 · 공백 · 쉼표 · 괄호다(「동교로 83」이 「동교로 830」에 걸리지 않게).
    pattern = rf"\s{re.escape(road)}\s+{re.escape(number)}([\s,(]|$)"
    alias = ALIAS.get(name)
    named = (f"p.name_ko = {q(alias)}" if alias else
             f"(strpos({_NORM_SQL}, {q(norm(name))}) > 0 OR strpos({q(norm(name))}, {_NORM_SQL}) > 0)")
    skipped = (" AND p.place_uid NOT IN (" + ", ".join(f"'{uid}'" for uid in skip) + ")") if skip else ""
    # ★이 적재가 예전에 만든 가게(시트에서 주소를 바꿔 버려진 것 포함)는 맨 앞 DELETE 로 레코드가 다 지워져 있다.
    #   기존 원장 가게는 늘 출처 레코드가 있으므로, 레코드가 남은 가게에만 붙인다 `[2026-10-08]`
    own = ", ".join(f"'{load}'" for load in _own_loads())
    skipped += (" AND EXISTS (SELECT 1 FROM dining.dn_source_record x WHERE x.place_uid = p.place_uid "
                f"AND x.load_id NOT IN ({own}))")
    return ("(SELECT min(p.place_uid::text)::uuid FROM dining.dn_place p "
            f"WHERE NOT p.is_synthetic AND p.area = {q(district)} AND p.road_address ~ {q(pattern)} "
            f"AND {named}{skipped} HAVING count(*) = 1)")


def _localdata_load(source: str) -> str:
    return str(uuid.uuid5(NS, f"load:nopo:{source}"))


def sql_lines(rows: list[dict], new_places: list[str] | None = None, skip: tuple[str, ...] = (),
              made: tuple[str, ...] = ()) -> list[str]:
    load_id = str(uuid.uuid5(NS, f"load:nopo:{LOADED}"))
    local_loads = ", ".join(f"'{_localdata_load(src)}'" for src in LOCALDATA_LABEL)
    lines = ["-- make_nopo_sql.py 결과. 생성 파일이므로 직접 고치지 않는다.",
             "BEGIN;", "",
             "-- 다시 넣어도 쌓이지 않게 이 출처의 것과 이 적재가 만든 인허가 레코드를 먼저 비운다.",
             "-- (가게 행은 남는다 — 같은 place_uid 로 다시 쓰고, 영업시간은 hours_sql 이 제 것을 비우고 다시 넣는다)",
             f"DELETE FROM dining.dn_attribute WHERE source_code = '{SOURCE}';",
             f"DELETE FROM dining.dn_source_record WHERE source_code = '{SOURCE}';",
             f"DELETE FROM dining.dn_source_record WHERE load_id IN ({local_loads});",
             f"DELETE FROM dining.dn_load_meta WHERE source_code = '{SOURCE}' OR load_id IN ({local_loads});", "",
             "INSERT INTO dining.dn_load_meta (load_id, source_code, fetched_at, schema_version, scope, "
             f"row_count, raw_uri, status) VALUES ('{load_id}', '{SOURCE}', '{LOADED} 12:00+09', "
             f"'nopo-{LOADED}', '카카오맵 「노포 지도」 서울', {len(rows)}, "
             f"'datasets/dining/processed/nopo/{os.path.basename(LIST)}', 'loaded');", ""]
    for row in rows:
        name, address = row["상호"].strip(), row["주소"].strip()
        key = addr_key(address)
        if key is None:
            continue                     # 도로명 주소가 아니면 잇지 않는다
        rec_id = str(uuid.uuid5(NS, f"record:nopo:{name}:{address}"))
        attr_id = str(uuid.uuid5(NS, f"attr:nopo:{name}:{address}"))
        basis = {"기준": "주소 대조 · 별칭" if name in ALIAS else "주소 · 상호 일치"}
        lines.append(
            "INSERT INTO dining.dn_source_record (record_id, load_id, source_code, external_id, "
            f"place_uid, match_status, match_basis, raw_json) SELECT '{rec_id}', '{load_id}', '{SOURCE}', "
            f"{q(name)}, m.uid, 'confirmed', $j${json.dumps(basis, ensure_ascii=False)}$j$::jsonb, "
            f"$j${json.dumps({'상호': name, '주소': address}, ensure_ascii=False)}$j$::jsonb "
            f"FROM (SELECT {match_sql(name, key, skip)} AS uid) m WHERE m.uid IS NOT NULL;")
        lines.append(
            "INSERT INTO dining.dn_attribute (attr_id, place_uid, source_code, record_id, attr_code, "
            "value_state, value_detail, source_text, extract_method, valid_from) "
            f"SELECT '{attr_id}', sr.place_uid, '{SOURCE}', sr.record_id, 'nopo', 'yes', NULL, "
            f"{q('카카오맵 노포 지도')}, 'manual', '{LOADED}' "
            f"FROM dining.dn_source_record sr WHERE sr.record_id = '{rec_id}';")
    if new_places:
        lines += ["", "-- 원장에 없던 가게 — 검수 시트에서 새로 만든다"] + new_places
    if made:
        lines += ["", "-- 시트에서 주소 · 관리번호를 바꾸면 옛 가게 행이 아무 기록 없이 남는다. 이 적재가 만든 가게 중",
                  "-- 어디에서도 가리키지 않는 것만 지운다. `[2026-10-08]`", orphan_sql(made)]
    lines += ["", "COMMIT;", ""]
    return lines


#: dn_place 를 가리키는 표 전부(외래 키 10곳) — 하나라도 가리키면 지우지 않는다
PLACE_REFERRERS = ("dn_source_record", "dn_hours_rule", "dn_closure_rule", "dn_core_place_link", "dn_attribute",
                   "dn_live_check", "dn_notice", "dn_truth", "dn_closure_coverage", "dn_external_ref")


def orphan_sql(made: tuple[str, ...]) -> str:
    """이 적재가 만든 가게(`made`) 중 기록이 하나도 남지 않은 것을 지운다."""
    uids = ", ".join(f"'{uid}'" for uid in sorted(made))
    return (f"DELETE FROM dining.dn_place p WHERE p.place_uid IN ({uids}) "
            + " ".join(f"AND NOT EXISTS (SELECT 1 FROM dining.{t} x WHERE x.place_uid = p.place_uid)"
                       for t in PLACE_REFERRERS) + ";")


def remember_made(uids: list[str]) -> tuple[str, ...]:
    """만든 가게 uid 를 MADE 에 더해 두고, 지금까지 만든 것 전부를 돌려준다."""
    seen = set(json.load(open(MADE, encoding="utf-8"))) if os.path.exists(MADE) else set()
    seen |= set(uids)
    os.makedirs(os.path.dirname(MADE), exist_ok=True)
    json.dump(sorted(seen), open(MADE, "w", encoding="utf-8"), indent=1)
    return tuple(sorted(seen))


# ── 검수 시트 → 새 가게 ───────────────────────────────────────────────
def _licenses() -> dict[str, tuple[str, dict]]:
    """인허가 관리번호 → (출처, 행). 원본이 없으면 빈 dict(데이터는 git 밖이다)."""
    out: dict[str, tuple[str, dict]] = {}
    for source, name in LOCALDATA:
        path = os.path.join(RAW, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="cp949", errors="replace") as f:
            for row in csv.DictReader(f):
                out[row["관리번호"].strip()] = (source, row)
    return out


def _vegan():
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_vegan_sql", os.path.join(HERE, "make_vegan_sql.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: 메모에 이 말이 있으면 노포 목록에서 뺀다(사람이 노포가 아니라고 본 곳)
NOT_NOPO = ("노포가 아니", "노포 아님", "목록 제외")


def closure_text(cell: str | None) -> str:
    """정기휴무 외 칸을 적재기가 읽는 「 / 」 구분으로 고친다. `[2026-10-08]`

    「일요일 및 공휴일」 → 「일요일 / 공휴일」, 「매월 1,3번째 일요일, 2,4번째 월요일」 →
    「매월 1,3번째 일요일 / 매월 2,4번째 월요일」. 「1,3번째」 안의 쉼표는 나누지 않는다.
    ★고치지 않으면 적재기가 첫 항목만 읽고 나머지를 말없이 버린다(2026-10-08 시트에서 4행).
    """
    parts: list[str] = []
    for chunk in re.split(r"\s*(?:및|/)\s*", (cell or "").strip()):
        for piece in re.split(r",\s*(?=\D)", chunk):
            piece = piece.strip()
            if re.match(r"^\d", piece) and parts and parts[-1].startswith("매월"):
                piece = "매월 " + piece
            if piece:
                parts.append(piece)
    return " / ".join(parts)


def tidy(row: dict) -> dict:
    """사람이 적은 행을 적재기가 읽는 모양으로 — 「24시간」 → 「00:00-24:00」, 정기휴무 외 구분. 원본 시트는 그대로 둔다."""
    out = dict(row)
    for day in DAYS:
        if out.get(day, "").strip() == "24시간":
            out[day] = "00:00-24:00"
    out["정기휴무 외"] = closure_text(out.get("정기휴무 외"))
    return out


def _geocoded_uid(label: str, address: str) -> str:
    return str(uuid.uuid5(NS, f"place:nopo:addr:{label}|{address.strip()}"))


def _geocoded_place(row: dict, label: str, point: tuple[float, float], load_id: str) -> list[str]:
    """인허가 없이 브이월드 좌표로 만드는 가게 — 가게 · 노포 목록 레코드 · 속성. 레코드가 곧 영업시간이 가리킬 자리다."""
    uid = _geocoded_uid(label, row["주소"])
    list_id = str(uuid.uuid5(NS, f"record:nopo:list:addr:{label}|{row['주소'].strip()}"))
    attr_id = str(uuid.uuid5(NS, f"attr:nopo:addr:{label}|{row['주소'].strip()}"))
    name = (row.get("표시명") or label).strip()
    address = re.sub(r"^서울\s", "서울특별시 ", row["주소"].strip())
    lat, lng = point
    return [
        "INSERT INTO dining.dn_place (place_uid, name_ko, road_address, lat, lng, coord_source, area, phone, "
        f"record_status) VALUES ('{uid}', {q(name)}, {q(address)}, {lat:.7f}, {lng:.7f}, '{GEOCODE_SOURCE}', "
        f"{q(row.get('자치구'))}, {q(row.get('전화'))}, 'active') "
        "ON CONFLICT (place_uid) DO UPDATE SET name_ko = EXCLUDED.name_ko, road_address = EXCLUDED.road_address, "
        "lat = EXCLUDED.lat, lng = EXCLUDED.lng, coord_source = EXCLUDED.coord_source, phone = EXCLUDED.phone, "
        "updated_at = now();",
        "INSERT INTO dining.dn_source_record (record_id, load_id, source_code, external_id, place_uid, match_status, "
        f"match_basis, raw_json) VALUES ('{list_id}', '{load_id}', '{SOURCE}', {q(label)}, '{uid}', 'confirmed', "
        f"$j${json.dumps({'기준': '검수 시트 · 브이월드 좌표'}, ensure_ascii=False)}$j$::jsonb, "
        f"$j${json.dumps({'상호': label, '주소': row['주소']}, ensure_ascii=False)}$j$::jsonb) "
        "ON CONFLICT (record_id) DO NOTHING;",
        "INSERT INTO dining.dn_attribute (attr_id, place_uid, source_code, record_id, attr_code, value_state, "
        f"value_detail, source_text, extract_method, valid_from) VALUES ('{attr_id}', '{uid}', '{SOURCE}', '{list_id}', "
        f"'nopo', 'yes', NULL, {q('카카오맵 노포 지도')}, 'manual', '{LOADED}') ON CONFLICT (attr_id) DO NOTHING;",
    ]


def read_geocoded() -> dict[tuple[str, str], tuple[float, float]]:
    if not os.path.exists(GEOCODED):
        return {}
    out = {}
    for row in csv.DictReader(open(GEOCODED, encoding="utf-8-sig")):
        if row.get("결과") == "OK" and row.get("위도") and row.get("경도"):
            out[(row["상호(목록)"].strip(), row["주소"].strip())] = (float(row["위도"]), float(row["경도"]))
    return out


def _vworld(address: str, key: str) -> tuple[str, float | None, float | None, str]:
    """(결과, 위도, 경도, 정제주소). 도로명으로 먼저, 안 되면 지번으로 한 번 더."""
    import httpx

    for kind in ("road", "parcel"):
        response = httpx.get("https://api.vworld.kr/req/address", timeout=15, params={
            "service": "address", "request": "getcoord", "version": "2.0", "crs": "epsg:4326", "address": address,
            "refine": "true", "simple": "false", "format": "json", "type": kind, "key": key})
        body = response.json().get("response") or {}
        if body.get("status") == "OK":
            point = (body.get("result") or {}).get("point") or {}
            return "OK", float(point["y"]), float(point["x"]), (body.get("refined") or {}).get("text") or ""
        if body.get("status") == "ERROR":
            return "ERROR " + str((body.get("error") or {}).get("text")), None, None, ""
    return "NOT_FOUND", None, None, ""


def geocode(sheet_rows: list[dict]) -> None:
    """좌표가 없을 행을 브이월드로 찾아 GEOCODED 에 적는다. 이미 OK 인 행은 다시 부르지 않는다(--force 로만)."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
    from app.core.settings import get_settings

    key = get_settings().vworld_api_key
    if not key:
        sys.exit("ACOP_VWORLD_API_KEY 가 없다(.env.apikeys)")
    licenses = _licenses()
    done = {} if "--force" in sys.argv else {
        (r["상호(목록)"].strip(), r["주소"].strip()): r for r in csv.DictReader(open(GEOCODED, encoding="utf-8-sig"))
        if r.get("결과") == "OK"} if os.path.exists(GEOCODED) else {}
    out, called = [], 0
    for row in sheet_rows:
        if row.get("번호") == "예시" or "폐업" in (row.get("메모") or ""):
            continue
        number = (row.get("인허가 관리번호") or "").strip()
        lic = licenses.get(number, (None, {}))[1]
        if number and (lic.get("좌표정보(X)") or "").strip() and (lic.get("좌표정보(Y)") or "").strip():
            continue                                   # 인허가 좌표가 있다
        label, address = row["상호(목록)"].strip(), row["주소"].strip()
        if (label, address) in done:
            out.append(done[(label, address)])
            continue
        key3 = addr_key(address)
        query = f"서울특별시 {key3[0]} {key3[1]} {key3[2]}" if key3 else re.sub(r"\(.*?\)", "", address)
        result, lat, lng, refined = _vworld(query, key)
        called += 1
        out.append({"상호(목록)": label, "주소": address, "위도": f"{lat:.7f}" if lat else "",
                    "경도": f"{lng:.7f}" if lng else "", "정제주소": refined, "결과": result})
    with open(GEOCODED, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["상호(목록)", "주소", "위도", "경도", "정제주소", "결과"])
        writer.writeheader()
        writer.writerows(out)
    bad = [r for r in out if r["결과"] != "OK"]
    print(f"브이월드 좌표 {len(out)}행 (이번에 부른 것 {called}) · 못 찾음 {len(bad)}: "
          + ", ".join(f"{r['상호(목록)']}({r['결과']})" for r in bad))
    print(f"→ {GEOCODED}")


def new_place_lines(sheet_rows: list[dict], licenses: dict[str, tuple[str, dict]],
                    geocoded: dict[tuple[str, str], tuple[float, float]] | None = None) -> tuple[list[str], dict]:
    """검수 시트의 확인된 행 → (가게 · 인허가 레코드 · 노포 속성 · 영업시간 SQL, 센 것).

    좌표 — 인허가 좌표가 먼저, 없으면 `geocoded`(브이월드, (상호, 주소) → (위도, 경도)).
    """
    geocoded = geocoded or {}
    source_of: dict[str, str | None] = {}
    from tm5174 import to_wgs84

    load_id = str(uuid.uuid5(NS, f"load:nopo:{LOADED}"))
    counts = {"만든다": [], "uids": [], "안 봄": 0, "폐업": [], "노포 아님": [], "요일 비어 있음": [], "관리번호 없음": [],
              "인허가에 없음": [], "좌표 없음": []}
    lines: list[str] = []
    used_sources: set[str] = set()
    place_of: dict[str, str] = {}
    records: dict[str, str] = {}
    keep: list[dict] = []
    for row in sheet_rows:
        if row.get("번호") == "예시":
            continue
        label = row["상호(목록)"].strip()
        if not (row.get("확인일") or "").strip():
            counts["안 봄"] += 1
            continue
        if "폐업" in (row.get("메모") or ""):
            counts["폐업"].append(label)
            continue
        if any(word in (row.get("메모") or "") for word in NOT_NOPO):
            counts["노포 아님"].append(label)
            continue
        row = tidy(row)
        if not any((row.get(day) or "").strip() for day in DAYS):
            # 확인일만 있고 요일이 모두 비었다 — 아직 안 본 것으로 둔다. 영업시간 없이 만들면 판정이 「모름」이라
            # 일정 생성기가 거의 쓰지 않는다. 다 모르면 요일 칸에 「모름」을 적으면 들어간다.
            counts["요일 비어 있음"].append(label)
            continue
        number = (row.get("인허가 관리번호") or "").strip()
        licensed = None
        if number and number in licenses:
            source, lic = licenses[number]
            x, y = (lic.get("좌표정보(X)") or "").strip(), (lic.get("좌표정보(Y)") or "").strip()
            if x and y:
                licensed = to_wgs84(float(x), float(y))
        if licensed is None:
            point = geocoded.get((label, row["주소"].strip()))
            if point is None:
                reason = "관리번호 없음" if not number else ("인허가에 없음" if number not in licenses else "좌표 없음")
                counts[reason].append(label)
                continue
            lines += _geocoded_place(row, label, point, load_id)
            uid = _geocoded_uid(label, row["주소"])
            place_of[label] = uid
            records[label] = str(uuid.uuid5(NS, f"record:nopo:list:addr:{label}|{row['주소'].strip()}"))
            source_of[label] = None
            keep.append(row)
            counts["만든다"].append(label)
            counts["uids"].append(uid)
            counts.setdefault("브이월드 좌표", []).append(label)
            continue
        lat, lng = licensed
        uid = str(uuid.uuid5(NS, f"place:nopo:{number}"))
        rec_id = str(uuid.uuid5(NS, f"record:nopo:{source}:{number}"))
        list_id = str(uuid.uuid5(NS, f"record:nopo:list:{number}"))
        attr_id = str(uuid.uuid5(NS, f"attr:nopo:new:{number}"))
        # 같은 관리번호로 다른 적재(비건 · 할랄)가 이미 만든 가게가 있으면 그 가게다
        match = ("(SELECT min(r.place_uid::text)::uuid FROM dining.dn_source_record r "
                 f"WHERE r.source_code IN ('localdata_food', 'localdata_rest') AND r.external_id = {q(number)} "
                 f"AND r.load_id <> '{_localdata_load(source)}')")
        name = (row.get("표시명") or label).strip()
        address = re.sub(r"^서울\s", "서울특별시 ", row["주소"].strip())
        lines.append(
            "INSERT INTO dining.dn_place (place_uid, name_ko, road_address, lat, lng, coord_source, area, phone, "
            f"record_status) SELECT '{uid}', {q(name)}, {q(address)}, {lat:.7f}, {lng:.7f}, '{source}', "
            f"{q(row.get('자치구'))}, {q(row.get('전화'))}, 'active' WHERE {match} IS NULL "
            "ON CONFLICT (place_uid) DO UPDATE SET name_ko = EXCLUDED.name_ko, road_address = EXCLUDED.road_address, "
            "lat = EXCLUDED.lat, lng = EXCLUDED.lng, phone = EXCLUDED.phone, updated_at = now();")
        raw = {"사업장명": lic.get("사업장명"), "영업상태명": lic.get("영업상태명"),
               "인허가일자": (lic.get("인허가일자") or "").strip(), "데이터갱신일자": lic.get("데이터갱신일자")}
        lines.append(
            "INSERT INTO dining.dn_source_record (record_id, load_id, source_code, external_id, place_uid, "
            f"match_status, match_basis, raw_json) SELECT '{rec_id}', '{_localdata_load(source)}', '{source}', "
            f"{q(number)}, coalesce({match}, '{uid}'::uuid), 'confirmed', "
            f"$j${json.dumps({'기준': '검수 시트의 인허가 관리번호'}, ensure_ascii=False)}$j$::jsonb, "
            f"$j${json.dumps(raw, ensure_ascii=False)}$j$::jsonb ON CONFLICT (record_id) DO NOTHING;")
        lines.append(
            "INSERT INTO dining.dn_source_record (record_id, load_id, source_code, external_id, place_uid, "
            f"match_status, raw_json) SELECT '{list_id}', '{load_id}', '{SOURCE}', {q(label)}, sr.place_uid, "
            f"'confirmed', $j${json.dumps({'상호': label, '주소': row['주소']}, ensure_ascii=False)}$j$::jsonb "
            f"FROM dining.dn_source_record sr WHERE sr.record_id = '{rec_id}' ON CONFLICT (record_id) DO NOTHING;")
        lines.append(
            "INSERT INTO dining.dn_attribute (attr_id, place_uid, source_code, record_id, attr_code, value_state, "
            f"value_detail, source_text, extract_method, valid_from) SELECT '{attr_id}', sr.place_uid, '{SOURCE}', "
            f"sr.record_id, 'nopo', 'yes', NULL, {q('카카오맵 노포 지도')}, 'manual', '{LOADED}' "
            f"FROM dining.dn_source_record sr WHERE sr.record_id = '{list_id}';")
        used_sources.add(source)
        source_of[label] = source
        place_of[label], records[label] = uid, rec_id
        keep.append(row)
        counts["만든다"].append(label)
        counts["uids"].append(uid)
    counts["시트 오류"] = []
    if keep:
        # hours_sql 은 시트의 확인된 행을 모두 읽고 첫 오류에서 멈춘다 — 사람이 적는 시트라 한 행의 실수로 전부가
        # 멈추면 안 된다. 행마다 먼저 읽어 보고, 못 읽는 행은 「시트 오류」로 알리고 그 가게는 이번에 넣지 않는다.
        vegan = _vegan()
        os.makedirs(OUT, exist_ok=True)
        filtered = os.path.join(OUT, "nopo_hours_sheet.csv")

        def write(rows_: list[dict]) -> None:
            with open(filtered, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(keep[0]))
                writer.writeheader()
                writer.writerows(rows_)

        good = []
        for row in keep:
            write([row])
            try:
                vegan.hours_sql(place_of, set(), filtered, tag=HOURS_TAG, place_records=records)
                good.append(row)
            except ValueError as exc:
                counts["시트 오류"].append(f"{row['번호']}번 {row['상호(목록)']} — {exc}")
        bad = {row["상호(목록)"].strip() for row in keep} - {row["상호(목록)"].strip() for row in good}
        if bad:
            lines = [line for line in lines if not any(f"'{place_of[label]}'" in line or f"'{records[label]}'" in line
                                                       for label in bad)]
            counts["만든다"] = [label for label in counts["만든다"] if label not in bad]
            counts["uids"] = [place_of[label] for label in counts["만든다"]]
            used_sources = {source_of[r["상호(목록)"].strip()] for r in good} - {None}
            keep = good
        if good:
            write(good)
            hours, counts["영업시간"] = vegan.hours_sql(place_of, set(), filtered, tag=HOURS_TAG,
                                                     scope="노포 가게 영업시간 검수", folder="nopo",
                                                     place_records=records)
            lines += ["", "-- 영업시간 · 휴무 (검수 시트)"] + hours
    head = []
    for source in sorted(used_sources):
        head.append(
            "INSERT INTO dining.dn_load_meta (load_id, source_code, fetched_at, schema_version, scope, row_count, "
            f"raw_uri, status) VALUES ('{_localdata_load(source)}', '{source}', now(), 'nopo-sheet-v1', "
            f"{q('노포 검수 시트 — ' + LOCALDATA_LABEL[source] + ' 인허가')}, "
            f"{sum(1 for r in keep if source_of[r['상호(목록)'].strip()] == source)}, "
            f"{q('datasets/dining/raw/' + dict(LOCALDATA)[source])}, 'loaded') ON CONFLICT (load_id) DO NOTHING;")
    return head + lines, counts


# ── 사람 확인용 표 (--report) ─────────────────────────────────────
def _same_name(a: str, b: str) -> bool:
    x, y = norm(a), norm(b)
    return bool(x and y) and (x == y or x in y or y in x)


def _match(row: dict, by_addr: dict, by_name: dict) -> tuple[str, list[dict]]:
    key = addr_key(row["주소"])
    at = by_addr.get(key, []) if key else []
    alias = ALIAS.get(row["상호"])
    named = [p for p in at if (p["name_ko"] == alias if alias else _same_name(row["상호"], p["name_ko"]))]
    if len(named) == 1:
        return ("별칭" if alias else "확정"), named
    if len(named) > 1:
        return "여럿", named
    if at:
        return "주소만", at
    same = [p for p in by_name.get(norm(row["상호"]), []) if p["area"] == row["자치구"]]
    if len(same) == 1:
        return "이름만", same
    return ("여럿" if same else "없음"), same


def _ledger_index():
    import psycopg

    with psycopg.connect(DSN) as conn:
        cols = ("place_uid", "name_ko", "area", "road_address", "record_status")
        places = [dict(zip(cols, r)) for r in conn.execute(
            "SELECT place_uid, name_ko, area, road_address, record_status FROM dining.dn_place "
            "WHERE NOT is_synthetic AND road_address IS NOT NULL").fetchall()]
    by_addr, by_name = collections.defaultdict(list), collections.defaultdict(list)
    for p in places:
        key = addr_key(p["road_address"])
        if key:
            by_addr[key].append(p)
        by_name[norm(p["name_ko"])].append(p)
    return places, by_addr, by_name


def report(rows: list[dict]) -> None:
    places, by_addr, by_name = _ledger_index()
    order = "확정 별칭 주소만 이름만 여럿 없음".split()
    results = []
    for row in rows:
        verdict, found = _match(row, by_addr, by_name)
        first = found[0] if found else {}
        results.append({"판정": verdict, "상호": row["상호"], "주소": row["주소"],
                        "원장_상호": " | ".join(p["name_ko"] for p in found),
                        "원장_주소": first.get("road_address") or "",
                        "place_uid": str(first["place_uid"]) if len(found) == 1 else ""})
    path = os.path.join(OUT, "nopo_match.csv")
    os.makedirs(OUT, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(sorted(results, key=lambda r: (order.index(r["판정"]), r["상호"])))
    counts = collections.Counter(r["판정"] for r in results)
    print(f"노포 {len(rows)}곳 · 원장 가게 {len(places)}곳 — 들어가는 것 = 확정 + 별칭")
    for verdict in order:
        print(f"  {verdict:<4} {counts.get(verdict, 0):>4}")
    print(f"→ {path}")


# ── 원장에 없는 가게의 영업시간 검수 시트 (--sheet) ─────────────────────
DAYS = ["월", "화", "수", "목", "금", "토", "일"]
SHEET_COLUMNS = (["번호", "상호(목록)", "표시명", "자치구", "주소", "네이버"] + DAYS +
                 ["브레이크타임", "라스트오더", "정기휴무 외", "확인일", "메모", "전화", "인허가 구분", "인허가 관리번호"])
#: 사람이 적는 칸 — --upgrade 가 옛 시트에서 옮긴다
HUMAN_COLUMNS = ["표시명"] + DAYS + ["브레이크타임", "라스트오더", "정기휴무 외", "확인일", "메모"]
EXAMPLE = {"번호": "예시", "상호(목록)": "(적는 법)", "네이버": "이 줄은 지우지 말고 두세요 — 적재기가 건너뜁니다",
           "월": "휴무", "화": "11:30-20:00", "수": "11:30-15:00, 17:00-20:00", "목": "11:30-15:00, 17:00-20:00",
           "금": "11:30-15:00, 17:00-24:30", "토": "모름", "일": "11:30-17:00", "브레이크타임": "15:00-17:00  또는  없음",
           "라스트오더": "마감 30분 전  또는  20:30", "정기휴무 외": "매월 둘째 주 화요일 / 명절 당일",
           "확인일": "2026-10-07",
           "메모": "브레이크타임은 모든 영업일에 같으면 그 칸에, 요일마다 다르면 요일 칸에 구간 둘로. 자정 넘기면 24:30처럼. "
                   "모르면 모름(비워두지 말 것). 폐업이면 메모에 폐업"}


def phone_text(raw: str | None) -> str:
    """「025167992」 → 「02-516-7992」. ★엑셀이 숫자로 읽어 앞자리 0 을 지우지 않게 하이픈을 넣는다."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    if digits.startswith("02"):
        head, rest = "02", digits[2:]
    else:
        head, rest = digits[:3], digits[3:]
    if len(rest) < 7:
        return digits
    return f"{head}-{rest[:-4]}-{rest[-4:]}"


def _localdata() -> dict[tuple[str, str, str], list[tuple[str, dict]]]:
    """인허가 원본 — 도로명 주소 열쇠 → [(출처, 행)]. 원본은 CP949 이고 깨진 글자가 섞여 있어 바꿔 읽는다."""
    index: dict[tuple[str, str, str], list[tuple[str, dict]]] = collections.defaultdict(list)
    for source, name in LOCALDATA:
        with open(os.path.join(RAW, name), encoding="cp949", errors="replace") as f:
            for row in csv.DictReader(f):
                key = addr_key(row.get("도로명주소"))
                if key:
                    index[key].append((source, row))
    return index


def _licensed(row: dict, index) -> tuple[str, tuple[str, dict] | None]:
    """(「영업」 · 「영업아님」 · 「없음」, 고른 인허가 행). 같은 주소에 같은 상호가 여럿이면 영업 중인 것을 먼저."""
    key = addr_key(row["주소"])
    found = [(source, r) for source, r in index.get(key, []) if _same_name(row["상호"], r.get("사업장명"))] if key else []
    if not found:
        return "없음", None
    live = [pair for pair in found if str(pair[1].get("영업상태명", "")).startswith("영업")]
    return ("영업", live[0]) if live else ("영업아님", found[0])


def sheet(rows: list[dict]) -> None:
    kept: dict[tuple[str, str], dict] = {}
    if os.path.exists(SHEET) and "--force" not in sys.argv:
        old = [r for r in csv.DictReader(open(SHEET, encoding="utf-8-sig")) if r.get("번호") != "예시"]
        if "--upgrade" not in sys.argv:
            filled = sum(1 for r in old if any((r.get(c) or "").strip() for c in HUMAN_COLUMNS[1:]))
            print(f"이미 있다 — 덮어쓰지 않는다: {SHEET} (적은 행 {filled}). 칸을 바꿔 옮기려면 --upgrade, 버리려면 --force")
            return
        kept = {(r["상호(목록)"], r["주소"]): {c: r.get(c, "") for c in HUMAN_COLUMNS if r.get(c) is not None}
                for r in old}
    _, by_addr, by_name = _ledger_index()
    index = _localdata()
    out, dropped = [], []
    for row in rows:
        if _match(row, by_addr, by_name)[0] in ("확정", "별칭"):
            continue                                  # 이미 원장 가게에 붙었다
        state, pick = _licensed(row, index)
        if state == "영업아님":
            dropped.append((row["상호"], pick[1].get("영업상태명")))
            continue
        source, lic = pick if pick else ("", {})
        query = urllib.parse.quote(f"{row['상호']} {row['자치구']}")
        line = {"상호(목록)": row["상호"], "표시명": row["상호"], "자치구": row["자치구"], "주소": row["주소"],
                "네이버": f"https://map.naver.com/p/search/{query}",
                "인허가 구분": {"localdata_food": "일반음식점", "localdata_rest": "휴게음식점"}.get(source, "못 찾음"),
                "인허가 관리번호": lic.get("관리번호", ""), "전화": phone_text(lic.get("전화번호"))}
        line.update({c: v for c, v in kept.get((row["상호"], row["주소"]), {}).items() if v.strip()})
        out.append(line)
    out.sort(key=lambda r: (r["인허가 구분"] == "못 찾음", r["자치구"], r["상호(목록)"]))
    for number, row in enumerate(out, start=1):
        row["번호"] = str(number)
    os.makedirs(os.path.dirname(SHEET), exist_ok=True)
    with open(SHEET, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerow({column: EXAMPLE.get(column, "") for column in SHEET_COLUMNS})
        writer.writerows([{column: row.get(column, "") for column in SHEET_COLUMNS} for row in out])
    found = sum(1 for r in out if r["인허가 구분"] != "못 찾음")
    if kept:
        moved = sum(1 for r in out if any(r.get(c, "").strip() for c in HUMAN_COLUMNS[1:]))
        print(f"옛 시트에서 적은 값을 옮겼다: {moved}행")
    print(f"검수 시트 {len(out)}곳 (인허가 영업 중 {found} · 인허가에서 못 찾음 {len(out) - found}) "
          f"— 영업 중이 아니라 뺀 곳 {len(dropped)}: {', '.join(f'{n}({s})' for n, s in dropped)}")
    print(f"→ {SHEET}")


def main() -> None:
    rows = list(csv.DictReader(open(LIST, encoding="utf-8-sig")))
    if "--report" in sys.argv:
        report(rows)
        return
    if "--sheet" in sys.argv:
        sheet(rows)
        return
    if "--geocode" in sys.argv:
        geocode(list(csv.DictReader(open(SHEET, encoding="utf-8-sig"))))
        return
    extra, counts = [], {}
    if os.path.exists(SHEET):
        sheet_rows = list(csv.DictReader(open(SHEET, encoding="utf-8-sig")))
        licenses = _licenses()
        if licenses:
            extra, counts = new_place_lines(sheet_rows, licenses, read_geocoded())
        else:
            print(f"!! 인허가 원본이 없다({RAW}) — 검수 시트의 새 가게는 이번에 넣지 않는다")
    made = remember_made(counts.get("uids", [])) if counts else ()
    lines = sql_lines(rows, extra, tuple(counts.get("uids", ())), made)
    print(f"카카오맵 노포 지도 서울: {len(rows)}곳 (별칭 {len(ALIAS)}곳 — 기존 가게 연결은 SQL 에서 판정)")
    if counts:
        print(f"검수 시트 새 가게: 만든다 {len(counts['만든다'])} · 아직 안 봄 {counts['안 봄']} · "
              f"요일 비어 있음 {len(counts['요일 비어 있음'])} · 폐업 {len(counts['폐업'])} · "
              f"노포 아님 {len(counts['노포 아님'])} · "
              f"영업시간 {counts.get('영업시간', {})}")
        if counts.get("브이월드 좌표"):
            print(f"  브이월드 좌표로 만든다 {len(counts['브이월드 좌표'])}: {', '.join(counts['브이월드 좌표'])}")
        for key in ("관리번호 없음", "인허가에 없음", "좌표 없음"):
            if counts[key]:
                print(f"  {key} — 만들지 않았다: {', '.join(counts[key])}")
        for error in counts.get("시트 오류", []):
            print(f"  시트 오류 — 고치면 다음에 들어간다: {error}")
    if "--dry" in sys.argv:
        return
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "nopo.sql")
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    print(f"→ {path}")


if __name__ == "__main__":
    main()
