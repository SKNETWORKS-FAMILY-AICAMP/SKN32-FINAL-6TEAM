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

사용법:  python scripts/dining/make_nopo_sql.py [--dry]     SQL 생성
         python scripts/dining/make_nopo_sql.py --report    원장(DINING_DSN)과 짝짓기 결과 표 — 사람 확인용
출력:    datasets/dining/processed/_build/nopo.sql
         datasets/dining/processed/_build/nopo_match.csv  (--report, 엑셀용 BOM)
"""
from __future__ import annotations

import collections
import csv
import json
import os
import re
import sys
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DINING_DATA = os.environ.get("DINING_DATA") or os.path.join(  # 데이터는 git 밖(datasets/dining/processed)
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "datasets", "dining", "processed")
LIST = os.path.join(DINING_DATA, "nopo", "노포_서울_카카오맵.csv")
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


def match_sql(name: str, key: tuple[str, str, str]) -> str:
    """그 가게의 place_uid 하나 — 후보가 하나일 때만. 자치구 · 도로명 · 건물번호 · 상호를 모두 본다."""
    district, road, number = key
    # 도로명 뒤에 건물번호가 오고, 번호 뒤는 끝 · 공백 · 쉼표 · 괄호다(「동교로 83」이 「동교로 830」에 걸리지 않게).
    pattern = rf"\s{re.escape(road)}\s+{re.escape(number)}([\s,(]|$)"
    alias = ALIAS.get(name)
    named = (f"p.name_ko = {q(alias)}" if alias else
             f"(strpos({_NORM_SQL}, {q(norm(name))}) > 0 OR strpos({q(norm(name))}, {_NORM_SQL}) > 0)")
    return ("(SELECT min(p.place_uid::text)::uuid FROM dining.dn_place p "
            f"WHERE NOT p.is_synthetic AND p.area = {q(district)} AND p.road_address ~ {q(pattern)} "
            f"AND {named} HAVING count(*) = 1)")


def sql_lines(rows: list[dict]) -> list[str]:
    load_id = str(uuid.uuid5(NS, f"load:nopo:{LOADED}"))
    lines = ["-- make_nopo_sql.py 결과. 생성 파일이므로 직접 고치지 않는다.",
             "BEGIN;", "",
             "-- 다시 넣어도 쌓이지 않게 이 출처의 것을 먼저 비운다.",
             f"DELETE FROM dining.dn_attribute WHERE source_code = '{SOURCE}';",
             f"DELETE FROM dining.dn_source_record WHERE source_code = '{SOURCE}';",
             f"DELETE FROM dining.dn_load_meta WHERE source_code = '{SOURCE}';", "",
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
            f"FROM (SELECT {match_sql(name, key)} AS uid) m WHERE m.uid IS NOT NULL;")
        lines.append(
            "INSERT INTO dining.dn_attribute (attr_id, place_uid, source_code, record_id, attr_code, "
            "value_state, value_detail, source_text, extract_method, valid_from) "
            f"SELECT '{attr_id}', sr.place_uid, '{SOURCE}', sr.record_id, 'nopo', 'yes', NULL, "
            f"{q('카카오맵 노포 지도')}, 'manual', '{LOADED}' "
            f"FROM dining.dn_source_record sr WHERE sr.record_id = '{rec_id}';")
    lines += ["", "COMMIT;", ""]
    return lines


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


def report(rows: list[dict]) -> None:
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


def main() -> None:
    rows = list(csv.DictReader(open(LIST, encoding="utf-8-sig")))
    if "--report" in sys.argv:
        report(rows)
        return
    lines = sql_lines(rows)
    print(f"카카오맵 노포 지도 서울: {len(rows)}곳 (별칭 {len(ALIAS)}곳 — 기존 가게 연결은 SQL 에서 판정)")
    if "--dry" in sys.argv:
        return
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "nopo.sql")
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    print(f"→ {path}")


if __name__ == "__main__":
    main()
