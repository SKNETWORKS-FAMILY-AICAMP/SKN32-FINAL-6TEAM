"""장소 이름을 **직접 입력해서** 활동 팀의 이름 찾기 · 같은 장소 판정을 확인하는 도구. `[2026-10-20]`

대체 장소 추천 안의 같은 장소 판정은 알아서 도는 로직이라 화면 입력으로는 확인할 수 없다 — 여기서 이름을 넣어 판정과 **이유**를 본다.
읽기만 한다(활동 원장 · 별칭 표 · 시드 파일). 카카오 · OpenAI 를 부르지 않고, 아무것도 저장하지 않는다. DB(Docker)가 떠 있어야 한다.

사용법
  1) 이 이름이 원장의 어느 장소로 읽히나 (별칭 · 어순 · 오타)
       python scripts/activity/try_place_names.py find 남산타워
       python scripts/activity/try_place_names.py find 남산서울타위 --fuzzy        오타 · 어순 보정까지
  2) 일정에 있는 이름 A 와 원장 후보 B 가 같은 곳으로 읽히나 (대체 후보에서 빠지나)
       python scripts/activity/try_place_names.py same N서울타워 남산서울타워
       python scripts/activity/try_place_names.py same 남산서울타우 남산서울타워 --distance-m 60
       python scripts/activity/try_place_names.py same N서울타워 남산서울타워 --distance-m 5000     같은 이름의 먼 곳

  `same` 의 B 는 원장 이름(별칭 포함)이다. A 의 좌표는 기본으로 모른다 — `--distance-m N`(B 에서 북쪽으로 N미터)이나
  `--lat/--lon` 으로 준다. 좌표를 모르면 별칭은 믿고, 이름 닮음 규칙은 「다름」으로 둔다.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))                       # final_project_cs
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LABEL = {"same": "같은 곳 (대체 후보에서 빠진다)", "ambiguous": "애매함 (후보에 남기고 경고만 남긴다)",
         "different": "다른 곳 (후보에 그대로 남는다)"}


def _db_aliases():
    """DB 별칭 표의 행들 — 표가 없으면 빈 목록(시드 파일만 쓴다)."""
    from app.domains.travel_ops.instances.activity.db_search.place_candidates import ALIAS_EXISTS_SQL, ALIAS_SQL
    from app.infrastructure.db.session import get_connection

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(ALIAS_EXISTS_SQL)
        if not cur.fetchone()[0]:
            return []
        cur.execute(ALIAS_SQL)
        return [{"alias": a, "content_id": c} for a, c in cur.fetchall()]


def cmd_find(args) -> int:
    from app.domains.travel_ops.instances.activity.db_search.place_by_name import find_place_by_name
    from app.infrastructure.db.session import get_connection

    found = find_place_by_name(get_connection, "", args.name, fuzzy=args.fuzzy)
    print(f"입력: {args.name!r}  (오타·어순 보정 {'켬' if args.fuzzy else '끔'})")
    print(f"결과: {found['status']}")
    if found["status"] == "found":
        how = {"alias": "별칭", "typo": "오타 보정", "word_order": "어순 보정"}.get(found.get("match"), "이름 일치")
        print(f"  → {found['matched_title']}  (contentid {found['content_id']}, {how})")
        if found.get("needs_review"):
            print("  ※ 짐작한 결과라 확인 필요(needs_review)로 다뤄야 한다")
        if found.get("note"):
            print(f"  {found['note']}")
    elif found["status"] == "ambiguous":
        print(f"  같은 이름이 {found.get('match_count')}곳 — 고르지 않는다: " + ", ".join(c["title"] for c in found["candidates"]))
    else:
        print("  원장에서 못 찾았다" + ("" if args.fuzzy else " — 오타·어순이면 --fuzzy 로 다시 본다"))
    return 0


def cmd_same(args) -> int:
    from app.domains.travel_ops.instances.activity import place_aliases, place_identity as pi
    from app.domains.travel_ops.instances.activity.db_search.place_by_name import find_place_by_name
    from app.infrastructure.db.session import get_connection

    found = find_place_by_name(get_connection, "", args.candidate)
    if found["status"] != "found":
        print(f"후보 {args.candidate!r} 이 원장에서 한 곳으로 정해지지 않는다({found['status']}) — 원장 이름(또는 별칭)으로 넣어 주세요")
        return 1
    candidate = pi.Spot(found["matched_title"], found["latitude"], found["longitude"], str(found["content_id"]))
    if args.lat is not None and args.lon is not None:
        lat, lon = args.lat, args.lon
    elif args.distance_m is not None and candidate.latitude is not None:
        lat, lon = candidate.latitude + args.distance_m / 111_320.0, candidate.longitude
    else:
        lat = lon = None
    item = pi.Spot(args.item, lat, lon)
    aliases = place_aliases.merged(_db_aliases())
    verdict, why = pi.explain(item, candidate, aliases)
    where = "모름" if lat is None else f"({lat:.4f}, {lon:.4f})"
    print(f"일정에 있는 이름 : {args.item!r}   좌표 {where}")
    print(f"원장 후보        : {candidate.name}  (contentid {candidate.content_id})")
    print(f"판정             : {verdict} — {LABEL[verdict]}")
    print(f"이유             : {why}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    find = sub.add_parser("find", help="이 이름이 원장의 어느 장소로 읽히나")
    find.add_argument("name")
    find.add_argument("--fuzzy", action="store_true", help="오타 · 어순 보정까지(결과는 확인 필요)")
    find.set_defaults(run=cmd_find)
    same = sub.add_parser("same", help="일정에 있는 이름과 원장 후보가 같은 곳으로 읽히나")
    same.add_argument("item", help="일정에 있는 장소 이름(고객이 쓴 말 · 카카오로 찾은 이름)")
    same.add_argument("candidate", help="원장 후보 이름(별칭 가능)")
    same.add_argument("--distance-m", type=float, default=None, help="일정 장소가 후보에서 북쪽으로 N미터 떨어져 있다고 본다")
    same.add_argument("--lat", type=float, default=None)
    same.add_argument("--lon", type=float, default=None)
    same.set_defaults(run=cmd_same)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
