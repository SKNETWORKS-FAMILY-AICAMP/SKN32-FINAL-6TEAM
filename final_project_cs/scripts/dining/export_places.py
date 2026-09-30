"""요식 원장의 가게 전체를 CSV 한 장으로 뽑는다. 팀원이 DB 없이 보거나 시험 데이터로 쓸 때.

    python scripts/dining/export_places.py            → data/dining/export/요식_원장_가게.csv

원장이 원본이다. 이 파일은 사본이며 rebuild.py 를 다시 돌리면 다시 뽑는다.
비건 · 할랄 · 아이 동반은 사람이 확인한 값만 「예/아니오」, 나머지는 빈칸(모름)이다.
"""
from __future__ import annotations

import csv
import os

import psycopg

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "data", "dining", "export", "요식_원장_가게.csv")
DSN = os.environ.get("DINING_DSN", "postgresql://postgres@localhost:5433/dining_rebuild")

SQL = """
SELECT p.place_uid, p.name_ko, p.area, p.road_address, p.lat, p.lng, p.phone, p.category,
       (SELECT string_agg(DISTINCT s.source_code, '|' ORDER BY s.source_code)
          FROM dining.dn_source_record s WHERE s.place_uid = p.place_uid) AS sources,
       EXISTS (SELECT 1 FROM dining.dn_hours_rule h WHERE h.place_uid = p.place_uid) AS has_hours,
       dining.meets_condition(p.place_uid, 'vegetarian_menu'),
       dining.meets_condition(p.place_uid, 'halal'),
       dining.meets_condition(p.place_uid, 'kids_allowed'),
       (SELECT a.value_detail::text FROM dining.dn_attribute a
         WHERE a.place_uid = p.place_uid AND a.attr_code = 'michelin' AND a.retired_at IS NULL LIMIT 1),
       EXISTS (SELECT 1 FROM dining.dn_core_place_link l WHERE l.place_uid = p.place_uid) AS core_linked,
       g.provider_id, g.url, g.status
FROM dining.dn_place p
LEFT JOIN dining.dn_external_ref g
       ON g.place_uid = p.place_uid AND g.kind = 'google_place' AND g.retired_at IS NULL
ORDER BY p.area, p.name_ko
"""

HEAD = ["place_uid", "상호", "자치구", "주소", "위도", "경도", "전화", "대표 분류", "출처",
        "영업시간 있음", "비건·채식", "할랄", "아이 동반", "미쉐린", "코어 장소 연결",
        "구글 place_id", "구글 지도", "구글 연결 상태"]


def yn(v: bool | None) -> str:
    return "" if v is None else ("예" if v else "아니오")


def main() -> None:
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(SQL)
        rows = cur.fetchall()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEAD)
        for (uid, name, area, addr, lat, lng, phone, cat, src, hours,
             veg, halal, kids, star, linked, gid, gurl, gstate) in rows:
            w.writerow([uid, name, area, addr, lat, lng, phone, cat, src,
                        yn(hours), yn(veg), yn(halal), yn(kids),
                        (star or "").strip('"'), yn(linked), gid or "", gurl or "",
                        {"candidate": "확인 전", "valid": "확인됨", "dead": "끊김"}.get(gstate, "")])
    print(f"{len(rows):,}곳 → {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
