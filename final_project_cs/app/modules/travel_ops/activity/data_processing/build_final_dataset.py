# -*- coding: utf-8 -*-
"""Activity 최종 장소 데이터셋: 기존 805건 + 올리브영(매칭 확정분) + 다이소 + 아트박스.

사용:
    python -m app.modules.travel_ops.activity.data_processing.build_final_dataset

입력:
    app/modules/travel_ops/activity/data_processing/tourapi_oliveyoung_seoul_enriched.csv  TourAPI 올리브영 371건
    app/modules/travel_ops/activity/data_processing/oliveyoung_seoul.csv                   올리브영 매장 CSV 368건 (매칭 기준으로만 쓴다)
    app/modules/travel_ops/activity/data_processing/tourapi_daiso_seoul_enriched.csv       TourAPI 다이소 54건
    app/modules/travel_ops/activity/data_processing/tourapi_artbox_seoul_enriched.csv      TourAPI 아트박스 24건
출력:
    scripts/activity_seoulplace_final.csv                     20컬럼(enriched.csv 와 같은 형식)

★올리브영은 **올리브영 CSV 와 매장명·주소가 둘 다 일치한 TourAPI 행만** 넣는다(2026-09-26
  담당자 결정, 326건). 값은 TourAPI 쪽을 쓴다 — contentid·좌표·분류·영업시간(opentime) 모두.
  한쪽만 일치한 18건과 둘 다 안 맞은 24건은 **여기서 넣지 않는다.** 판단·큐레이션 후 추가한다
  (목록: oliveyoung_match_review.csv · oliveyoung_unmatched_curation.csv · oliveyoung_tourapi_only.csv).

★일치 판정은 표기만 맞춘다 — 뜻을 추측하지 않는다.
    매장명  올리브영 CSV 는 "올리브영 " 을 붙인 title(merge 스크립트와 같은 규칙), 공백 무시
    주소    "서울특별시 ○○구 도로명 건물번호" 까지만 비교(층·건물명·괄호 속 동 이름 무시)
  그래서 "신내로72"(붙여 씀)처럼 표기가 다른 매장은 일치로 보지 않고 판단 목록에 남아 있다.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from .fetch_tourapi_details import BASE_COLUMNS
from .merge_oliveyoung_activities import oliveyoung_title

DATA_DIR = Path(__file__).resolve().parent
SCRIPTS = DATA_DIR.parents[4] / "scripts"
BASE_CSV = SCRIPTS / "activities_candidates_seoul_enriched.csv"
TOURAPI_OLIVEYOUNG_CSV = DATA_DIR / "tourapi_oliveyoung_seoul_enriched.csv"
OLIVEYOUNG_CSV = DATA_DIR / "oliveyoung_seoul.csv"
TOURAPI_DAISO_CSV = DATA_DIR / "tourapi_daiso_seoul_enriched.csv"
TOURAPI_ARTBOX_CSV = DATA_DIR / "tourapi_artbox_seoul_enriched.csv"
FINAL_CSV = SCRIPTS / "activity_seoulplace_final.csv"

#: "서울특별시 중구 명동길 53 1~2층" → ("중구", "명동길", 지하 여부, "53").
#: ★도로명 주소의 건물번호까지만 잡는다. 그 뒤(층·호·건물명)는 두 출처가 제각각 적는다.
ROAD_ADDRESS = re.compile(r"^서울특별시\s+(\S+구)\s+(.+?)\s+(지하\s*)?(\d+(?:-\d+)?)(?=\s|,|\(|$)")


def name_key(name: str) -> str:
    return re.sub(r"\s+", "", name)


def address_key(address: str) -> tuple[str, str, bool, str] | None:
    """비교용 주소 키. 형식을 못 읽으면 None — None 끼리는 일치로 보지 않는다."""
    match = ROAD_ADDRESS.match(address.strip())
    if match is None:
        return None
    district, road, underground, number = match.groups()
    return district, name_key(road), bool(underground), number


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def matched_oliveyoung(tourapi_rows: list[dict[str, str]],
                       store_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """올리브영 CSV 매장과 매장명·주소가 **둘 다** 같은 TourAPI 행만 돌려준다(TourAPI 순서 유지)."""
    store_keys = set()
    for store in store_rows:
        address = address_key(store["주소"])
        if address is not None:
            store_keys.add((name_key(oliveyoung_title(store["매장명"])), address))
    return [row for row in tourapi_rows
            if (name_key(row["title"]), address_key(row["addr1"])) in store_keys]


def build(base_path: Path = BASE_CSV) -> tuple[list[dict[str, str]], dict[str, int]]:
    base = read_csv(base_path)
    oliveyoung = matched_oliveyoung(read_csv(TOURAPI_OLIVEYOUNG_CSV), read_csv(OLIVEYOUNG_CSV))
    daiso, artbox = read_csv(TOURAPI_DAISO_CSV), read_csv(TOURAPI_ARTBOX_CSV)
    parts = {"기존 805건": base, "올리브영(매칭 확정)": oliveyoung, "다이소": daiso, "아트박스": artbox}

    rows: list[dict[str, str]] = []
    seen: dict[str, str] = {}
    for label, part in parts.items():
        for row in part:
            # ★contentid 는 적재 키다. 겹치면 한 장소가 다른 장소를 조용히 덮어쓰므로 멈춘다.
            if row["contentid"] in seen:
                raise SystemExit(f"contentid 중복: {row['contentid']} ({seen[row['contentid']]} · {label}) "
                                 f"'{row['title']}'")
            seen[row["contentid"]] = label
            rows.append({column: row.get(column, "") for column in BASE_COLUMNS})
    return rows, {label: len(part) for label, part in parts.items()}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=FINAL_CSV)
    args = ap.parse_args(argv)

    rows, counts = build()
    with args.out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=BASE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(" + ".join(f"{label} {count}" for label, count in counts.items())
          + f" = {len(rows)}건 → {args.out}")


if __name__ == "__main__":
    sys.exit(main())
