"""요식 원장 가게가 **지금 카카오 지도에 같은 이름으로 있는지** 본다 — 폐업 의심 가게를 가리는 1차 체. `[2026-10-05 사용자 지시]`

왜.
    인허가 자료의 「영업」은 영업 중이라는 증거가 못 된다(신고가 늦다 — 사람이 폐업으로 확인한 46곳 중 22곳이 인허가엔 영업).
    카카오 지도는 폐업한 가게를 비교적 빨리 내린다. 같은 이름 가게가 **그 좌표 둘레에 없으면** 폐업 의심이다.
    ★의심일 뿐이다 — 카카오에 등록이 안 된 가게도 있다. 의심 가게는 사람(여기서는 Claude)이 지도 화면에서 하나씩 확인한다.

약관(카카오 운영정책). 이름 찾기 전용이라 **응답을 저장하지 않는다** — 결과 CSV 에는 「있음/없음 · 거리」 판정만 적는다. 호출은 프로젝트의
    호출 예산(`travel.kakao_budget`, 하루 1,000)을 지나간다.

사용법
    python scripts/dining/kakao_presence.py --new            관광공사 재수집으로 새로 붙은 가게만(609)
    python scripts/dining/kakao_presence.py --limit 50       앞에서 50곳만 시험
결과: datasets/dining/processed/closure/카카오존재_<날짜>.csv (git 밖). 이어 받기: 이미 적힌 가게는 건너뛴다.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import unicodedata
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.environ.get("DINING_DATA") or os.path.join(os.path.dirname(ROOT), "datasets", "dining", "processed")
OUT_DIR = os.path.join(DATA, "closure")
NEAR_M = 250          # 이 안에 같은 이름이 있어야 「있음」 — 좌표 오차 · 건물 안 위치 차이를 넉넉히 본다(우리가 고른 값)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def norm(text: str | None) -> str:
    text = re.sub(r"[\(\[（【].*?[\)\]）】]", "", unicodedata.normalize("NFKC", text or "")).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def same_name(a: str, b: str) -> bool:
    x, y = norm(a), norm(b)
    if not x or not y:
        return False
    if x == y:
        return True
    short, long_ = sorted((x, y), key=len)
    return len(short) >= 3 and short in long_


def distance_m(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742000 * math.asin(math.sqrt(a))


def targets(only_new: bool) -> list[dict]:
    sys.path.insert(0, HERE)
    sys.path.insert(0, ROOT)
    import core_db
    import psycopg

    new_ids: set[str] | None = None
    if only_new:
        backups = sorted(f for f in os.listdir(os.path.join(DATA, "_backup")) if f.endswith("목록_법정동_전"))
        old = {str(r["contentid"]) for r in json.load(open(os.path.join(DATA, "_backup", backups[0], "tourapi_서울_음식점_목록.json"), encoding="utf-8"))}
        now = {str(r["contentid"]) for r in json.load(open(os.path.join(DATA, "tourapi_서울_음식점_목록.json"), encoding="utf-8"))}
        new_ids = now - old
    with psycopg.connect(core_db.dsn()) as conn, conn.cursor() as cur:
        cur.execute("SELECT p.place_uid::text, p.name_ko, coalesce(p.road_address, p.jibun_address, ''), p.lat, p.lng, "
                    "p.record_status, (SELECT min(r.external_id) FROM dining.dn_source_record r WHERE r.place_uid = p.place_uid "
                    "AND r.source_code = 'tourapi_kor_food') FROM dining.dn_place p "
                    "WHERE NOT p.is_synthetic AND p.record_status <> 'closed' AND p.lat IS NOT NULL ORDER BY p.name_ko")
        rows = [dict(zip(("uid", "name", "addr", "lat", "lng", "status", "cid"), r)) for r in cur.fetchall()]
    return [r for r in rows if new_ids is None or r["cid"] in new_ids]


def kakao():
    sys.path.insert(0, ROOT)
    from app.core.settings import get_settings
    from app.infrastructure.db.session import get_connection
    from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget, kakao_caps
    from app.domains.travel_ops.ports.data_sources.kakao_local import KakaoLocal

    key = get_settings().kakao_rest_api_key
    if not key:
        sys.exit("카카오 키가 없다(ACOP_KAKAO_REST_API_KEY)")
    return KakaoLocal(api_key=key, budget=CallBudget(connection_factory=get_connection, caps=kakao_caps()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--new", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    shops = targets(args.new)
    if args.limit:
        shops = shops[:args.limit]
    os.makedirs(OUT_DIR, exist_ok=True)
    target = os.path.join(OUT_DIR, f"카카오존재_{date.today().strftime('%Y%m%d')}.csv")
    done: set[str] = set()
    if os.path.exists(target):
        with open(target, encoding="utf-8-sig") as fh:
            done = {r["place_uid"] for r in csv.DictReader(fh)}
    todo = [s for s in shops if s["uid"] not in done]
    print(f"대상 {len(shops)}곳 · 이미 확인 {len(done)} · 이번 {len(todo)}")
    client = kakao()
    fresh = not os.path.exists(target)
    with open(target, "a", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        if fresh:
            writer.writerow(["place_uid", "상호", "원장 주소", "카카오", "가장 가까운 같은 이름(m)"])
        for n, shop in enumerate(todo, 1):
            found = client.search(shop["name"], size=10, near=(shop["lat"], shop["lng"]))
            if found is None:                                   # 예산 소진 · 오류 — 멈춘다(이어 받기)
                print("멈춤: 조회를 못 했다(예산 소진 또는 오류) —", n - 1, "곳까지")
                break
            best = None
            for hit in found:
                try:
                    d = distance_m(shop["lat"], shop["lng"], float(hit.get("y") or hit.get("latitude")), float(hit.get("x") or hit.get("longitude")))
                except (TypeError, ValueError):
                    continue
                title = hit.get("place_name") or hit.get("name") or hit.get("title") or ""
                if same_name(shop["name"], title) and (best is None or d < best):
                    best = d
            ok = best is not None and best <= NEAR_M
            writer.writerow([shop["uid"], shop["name"], shop["addr"], "있음" if ok else "없음", "" if best is None else round(best)])
            if n % 50 == 0:
                fh.flush()
                print(f"  {n}/{len(todo)}")
    print("→", target)


if __name__ == "__main__":
    main()
