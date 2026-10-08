# -*- coding: utf-8 -*-
"""관광공사 장소 목록을 `place_catalog` 에 적재한다. `[2026-10-05]`

    # 서울(1) 부트스트랩 — 한 번에 최대 5페이지(500건)
    python -m scripts.sync_place_catalog --area 1
    # 변경분만 / 전체 대조
    python -m scripts.sync_place_catalog --area 1 --mode delta
    python -m scripts.sync_place_catalog --area 1 --mode audit --max-pages 30

★출처: 활동 팀(조직 develop `scripts/sync_place_catalog.py`)의 실행 껍데기. 우리 `PlaceCatalogSync`(`domains/travel_ops/ports/data_sources/catalog_sync.py`)는
  이미 있었는데 **돌리는 길이 없었다** — 장소 목록을 새로 받거나 이어받을 방법이 코드로는 없었다. 이 스크립트가 그 길이다.
★우리 표에는 대분류 칸(`large_class_code`)이 없다 — 팀 판의 마지막 「대분류별 건수」는 `raw_json` 의 `lclsSystm1` 로 센다.
★**재실행 안전.** `ON CONFLICT DO UPDATE` 로 덮어쓰고(키 · 목록 응답 값만 바뀐다 — 우리가 덧붙인 `brand` 같은 키는 남는다),
  중간에 끊겨도 `source_sync_state` 의 진행 위치에서 이어받는다.
★관광공사 하루 호출 한도(개발 계정 1,000건)를 쓴다 — 낮에 사용자 요청과 나눠 쓴다. 부트스트랩은 되도록 새벽에 돌린다.

지역 코드: 1 서울 2 인천 3 대전 4 대구 5 광주 6 부산 7 울산 8 세종 31 경기 32 강원 33 충북 34 충남 35 경북 36 경남 37 전북 38 전남 39 제주
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

AREA_NAMES = {
    "1": "서울", "2": "인천", "3": "대전", "4": "대구", "5": "광주", "6": "부산", "7": "울산", "8": "세종",
    "31": "경기", "32": "강원", "33": "충북", "34": "충남", "35": "경북", "36": "경남",
    "37": "전북", "38": "전남", "39": "제주",
}


def _load_source():
    from app.core.settings import get_settings
    from app.domains.travel_ops.ports.data_sources.tour_api import TourApiPlace

    key = getattr(get_settings(), "tour_api_key", "") or ""
    if not key:
        print("[FAIL] 관광공사 키(ACOP_TOUR_API_KEY)가 없다 — .env.apikeys 확인", file=sys.stderr)
        raise SystemExit(1)
    return TourApiPlace(service_key=key)


def _make_syncer(source, tenant_id: str, page_size: int):
    from app.infrastructure.db.session import get_connection
    from app.domains.travel_ops.ports.data_sources.catalog_sync import PlaceCatalogSync

    return PlaceCatalogSync(source=source, connection_factory=get_connection, tenant_id=tenant_id,
                            page_size=page_size)


def _class_counts(tenant_id: str) -> tuple[int, list[tuple[str, int]]]:
    """전체 건수와 대분류별 건수 — `raw_json` 의 `lclsSystm1` 로 센다."""
    from app.infrastructure.db.session import get_connection

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM place_catalog WHERE tenant_id=%s AND source='tour_api'", (tenant_id,))
        total = cur.fetchone()[0]
        cur.execute("SELECT raw_json->>'lclsSystm1', count(*) FROM place_catalog WHERE tenant_id=%s "
                    "AND source='tour_api' GROUP BY 1 ORDER BY 2 DESC", (tenant_id,))
        return total, [(row[0] or "(없음)", row[1]) for row in cur.fetchall()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="관광공사 → place_catalog 적재")
    parser.add_argument("--area", nargs="+", default=["1"], metavar="CODE", help="지역 코드 (기본값: 1=서울)")
    parser.add_argument("--mode", choices=["bootstrap", "delta", "audit"], default="bootstrap",
                        help="bootstrap=전체, delta=변경분, audit=대조 (기본값: bootstrap)")
    parser.add_argument("--max-pages", type=int, default=5, help="한 번에 처리할 최대 페이지 수 (기본값: 5 = 500건)")
    parser.add_argument("--tenant", default=None, help="테넌트 ID (기본값: 설정의 기본 테넌트)")
    parser.add_argument("--page-size", type=int, default=100, help="페이지당 행 수 (기본값: 100)")
    args = parser.parse_args(argv)

    from app.core.settings import get_settings

    tenant = args.tenant or get_settings().tenant_id
    syncer = _make_syncer(_load_source(), tenant, args.page_size)
    total_written, failed = 0, []
    print(f"모드: {args.mode}  테넌트: {tenant}  최대 {args.max_pages}페이지/지역  페이지 크기: {args.page_size}")
    for code in args.area:
        name = AREA_NAMES.get(code, f"지역{code}")
        print(f"[{code}] {name} …", flush=True)
        try:
            if args.mode == "audit":
                outcome = syncer.audit(code, max_pages=args.max_pages)
            elif args.mode == "delta":
                outcome = syncer._delta(code, syncer._load_state(code))
            else:
                outcome = syncer.run(code, max_pages=args.max_pages)
        except Exception as exc:  # noqa: BLE001 — 지역 하나가 죽어도 나머지를 돌리고, 끝에 센다
            print(f"  [FAIL] {type(exc).__name__}", file=sys.stderr)
            failed.append(f"{code}({name}): {type(exc).__name__}")
            continue
        total_written += outcome.rows_written
        print(f"  → {'완료' if outcome.finished else '진행중'}  페이지 {outcome.pages_fetched}  행 {outcome.rows_written}")
        if outcome.note:
            print(f"     {outcome.note}")
        if outcome.delta_trusted is not None:
            print(f"     델타 {'신뢰' if outcome.delta_trusted else '미신뢰'}")
    print(f"합계: {total_written}행 저장  실패 지역: {len(failed)}건")
    for entry in failed:
        print(f"  FAIL  {entry}")
    if failed:
        return 1
    total, by_class = _class_counts(tenant)
    print(f"[place_catalog] tenant={tenant}  관광공사 {total}행")
    for large, count in by_class:
        print(f"  {large}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
