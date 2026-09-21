# -*- coding: utf-8 -*-
"""TourAPI 장소 목록을 place_catalog에 적재한다.

★왜 필요한가. `watch.py`가 `read.place_search`로 장소를 찾을 때
  TourAPI를 직접 부르면 콜 수가 사용자 수에 비례해 늘어난다.
  여기서 지역 단위로 한 번 받아 DB에 두면, 그 다음부터는
  DB 조회만 하고 외부 콜을 안 쓴다.

★**재실행 안전.** ON CONFLICT DO UPDATE 로 덮어쓴다.
  bootstrap이 중간에 끊겨도 `source_sync_state`에 진행 위치가
  남아 있어 다음 실행이 이어받는다.

사용법:
    # 서울(1) 부트스트랩 — 한 번에 최대 5페이지(500건)
    python -m scripts.sync_place_catalog --area 1

    # 여러 지역
    python -m scripts.sync_place_catalog --area 1 2 39

    # 전체 대조(delta 신뢰도 검증)
    python -m scripts.sync_place_catalog --area 1 --mode audit

    # 페이지 제한 늘리기
    python -m scripts.sync_place_catalog --area 1 --max-pages 20

지역 코드:
    1 서울  2 인천  3 대전  4 대구  5 광주  6 부산  7 울산  8 세종
    31 경기  32 강원  33 충북  34 충남  35 경북  36 경남
    37 전북  38 전남  39 제주
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

AREA_NAMES = {
    "1": "서울", "2": "인천", "3": "대전", "4": "대구",
    "5": "광주", "6": "부산", "7": "울산", "8": "세종",
    "31": "경기", "32": "강원", "33": "충북", "34": "충남",
    "35": "경북", "36": "경남", "37": "전북", "38": "전남", "39": "제주",
}


def _load_source():
    from app.core.settings import get_settings
    from app.infrastructure.travel.tour_api import TourApiPlace
    key = getattr(get_settings(), "tour_api_key", "") or ""
    if not key:
        print("[FAIL] ACOP_TOUR_API_KEY 가 없다 — .env.apikeys 확인", file=sys.stderr)
        sys.exit(1)
    return TourApiPlace(service_key=key)


def _make_syncer(source, tenant_id: str, page_size: int):
    from app.infrastructure.travel.catalog_sync import PlaceCatalogSync
    from app.infrastructure.db.session import get_connection
    return PlaceCatalogSync(
        source=source,
        connection_factory=get_connection,
        tenant_id=tenant_id,
        page_size=page_size,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="TourAPI → place_catalog 적재")
    parser.add_argument("--area", nargs="+", default=["1"],
                        metavar="CODE", help="지역 코드 (기본값: 1=서울)")
    parser.add_argument("--mode", choices=["bootstrap", "delta", "audit"],
                        default="bootstrap",
                        help="bootstrap=전체, delta=변경분, audit=대조 (기본값: bootstrap)")
    parser.add_argument("--max-pages", type=int, default=5,
                        help="한 번에 처리할 최대 페이지 수 (기본값: 5 = 500건)")
    parser.add_argument("--tenant", default="demo",
                        help="테넌트 ID (기본값: demo)")
    parser.add_argument("--page-size", type=int, default=100,
                        help="페이지당 행 수 (기본값: 100)")
    args = parser.parse_args()

    source = _load_source()
    syncer = _make_syncer(source, args.tenant, args.page_size)

    total_written = 0
    failed: list[str] = []

    print(f"모드: {args.mode}  테넌트: {args.tenant}  "
          f"최대 {args.max_pages}페이지/지역  페이지크기: {args.page_size}")
    print("=" * 60)

    for code in args.area:
        name = AREA_NAMES.get(code, f"지역{code}")
        print(f"\n[{code}] {name} …", flush=True)
        try:
            if args.mode == "audit":
                outcome = syncer.audit(code, max_pages=args.max_pages)
            elif args.mode == "delta":
                outcome = syncer._delta(code, syncer._load_state(code))
            else:
                outcome = syncer.run(code, max_pages=args.max_pages)

            total_written += outcome.rows_written
            status = "완료" if outcome.finished else "진행중"
            print(f"  → {status}  페이지 {outcome.pages_fetched}  "
                  f"행 {outcome.rows_written}")
            if outcome.note:
                print(f"     {outcome.note}")
            if outcome.delta_trusted is not None:
                trusted = "신뢰" if outcome.delta_trusted else "미신뢰"
                print(f"     델타 {trusted}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
            failed.append(f"{code}({name}): {exc}")

    print("\n" + "=" * 60)
    print(f"합계: {total_written}행 저장  실패 지역: {len(failed)}건")
    if failed:
        for f in failed:
            print(f"  FAIL  {f}")
        return 1

    # ── DB 건수 확인 ──────────────────────────────────────────
    try:
        from app.infrastructure.db.session import get_connection
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT large_class_code, large_class_name, count(*) "
                "FROM place_catalog WHERE tenant_id=%s "
                "  AND large_class_code IS NOT NULL "
                "GROUP BY 1, 2 ORDER BY 3 DESC",
                (args.tenant,))
            rows = cur.fetchall()
            cur.execute("SELECT count(*) FROM place_catalog WHERE tenant_id=%s",
                        (args.tenant,))
            total = cur.fetchone()[0]
        print(f"\n[place_catalog] tenant={args.tenant}  전체 {total}행")
        if rows:
            print("  대분류별 건수:")
            for code, name, cnt in rows:
                print(f"    {code:3s}  {(name or '?'):8s}  {cnt:>5}건")
    except Exception as exc:  # noqa: BLE001
        print(f"  건수 조회 실패: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
