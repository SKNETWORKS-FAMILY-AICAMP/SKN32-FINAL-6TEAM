# -*- coding: utf-8 -*-
"""TourAPI 검색 응답(JSON)에서 **서울 주소인 행만** 골라 CSV 로 저장한다.

사용:
    python -m app.modules.travel_ops.activity.data_processing.filter_tourapi_seoul 응답1.json [응답2.json ...] \
        --out app/modules/travel_ops/activity/data_processing/tourapi_oliveyoung_seoul.csv

입력: 브라우저 등으로 직접 호출해 저장한 `searchKeyword2` 응답 JSON.
      페이지가 여러 개면(totalCount > numOfRows) 페이지별 파일을 모두 넘긴다.

★왜 `areaCode=1` 로 받지 않고 주소로 거르는가(2026-09-26 확인). TourAPI 의 올리브영
  행은 `areacode` 가 비어 있거나 서울이 아닌 값이 들어 있어, `areaCode=1` 로 검색하면
  0건이 나왔다. 그래서 지역 조건 없이 전국을 받고, **`addr1` 이 "서울특별시"로
  시작하는 행만** 남긴다(담당자 결정 — addr2 는 층수 같은 상세 주소라 기준이 아니다).

★버린 행을 조용히 버리지 않는다. "서울특별시"로 시작하지는 않지만 `addr1` 에 "서울"이
  들어 있는 행(예: "서울 중구 …" 처럼 줄여 쓴 주소)은 따로 세어 출력한다 — 표기 차이로
  서울 매장이 빠지는지 사람이 확인할 수 있게 하려는 것이다. 기준을 넓힐지는 그걸 보고 정한다.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

SEOUL_PREFIX = "서울특별시"


def response_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """응답 JSON 에서 항목 목록만 꺼낸다.

    ★TourAPI 는 결과가 0건이면 `items` 를 빈 문자열("")로, 1건이면 `item` 을 리스트가
      아닌 dict 하나로 준다. 세 경우를 모두 리스트로 맞춘다.
    """
    header = payload.get("response", {}).get("header", {})
    if header.get("resultCode") not in (None, "0000"):
        raise SystemExit(f"TourAPI 오류 응답: {header.get('resultCode')} {header.get('resultMsg')}")
    items = payload.get("response", {}).get("body", {}).get("items") or {}
    item = items.get("item") if isinstance(items, dict) else None
    if item is None:
        return []
    return item if isinstance(item, list) else [item]


def is_seoul(row: dict[str, Any]) -> bool:
    return str(row.get("addr1") or "").strip().startswith(SEOUL_PREFIX)


def load_items(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        for row in response_items(json.loads(path.read_text(encoding="utf-8-sig"))):
            # ★같은 페이지 파일을 두 번 넘기는 실수로 행이 불어나지 않게 contentid 로 한 번만 센다.
            content_id = str(row.get("contentid") or "")
            if content_id and content_id in seen:
                continue
            seen.add(content_id)
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    # 응답 필드를 가공하지 않고 그대로 쓴다. 행마다 필드가 다를 수 있어 합집합을 컬럼으로 삼는다.
    columns: list[str] = []
    for row in rows:
        columns += [key for key in row if key not in columns]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("responses", type=Path, nargs="+")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent
                    / "oliveyoung_tourapi_seoul.csv")
    args = ap.parse_args(argv)

    rows = load_items(args.responses)
    seoul = [row for row in rows if is_seoul(row)]
    near_miss = [row for row in rows if not is_seoul(row) and "서울" in str(row.get("addr1") or "")]
    write_csv(args.out, seoul)
    print(f"전체 {len(rows)}건 → 서울({SEOUL_PREFIX}…) {len(seoul)}건 저장 → {args.out}")
    if near_miss:
        print(f"확인 필요: '서울'이 들어 있지만 '{SEOUL_PREFIX}'로 시작하지 않아 뺀 {len(near_miss)}건")
        for row in near_miss:
            print(f"  {row.get('contentid')} {row.get('title')} | {row.get('addr1')}")


if __name__ == "__main__":
    sys.exit(main())
