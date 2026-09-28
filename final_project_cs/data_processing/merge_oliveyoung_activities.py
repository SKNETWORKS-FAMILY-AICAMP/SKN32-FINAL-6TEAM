# -*- coding: utf-8 -*-
"""Activity 후보 장소 CSV(805건) + 올리브영 매장 CSV(368건) → 통합 CSV 하나.

사용:
    python -m data_processing.merge_oliveyoung_activities

입력(둘 다 **읽기만** 한다 — 원본은 고치지 않는다):
    scripts/activities_candidates_seoul_enriched.csv   TourAPI 기반 805건, 20개 컬럼
    data_processing/oliveyoung_seoul.csv               올리브영 서울 매장 368건, 10개 컬럼(한글)
출력:
    data_processing/activities_candidates_seoul_merged.csv  805건 컬럼 + `data_source`

★통합 규칙(2026-09-26 담당자 결정). 여기 없는 변환은 하지 않는다.
  - 컬럼은 **805건 CSV 기준**이다. 올리브영 전용 컬럼은 만들지 않는다
    (그래서 올리브영 `태그`는 통합본에 들어가지 않는다 — 원본 파일에는 남아 있다).
  - `data_source` 로 행의 출처를 남긴다: `tour_api` / `oliveyoung`.
    나중에 `place_catalog` 에 적재할 때 `source` 를 가르는 근거가 된다.
  - 올리브영 매핑:
        매장명 → title("올리브영 " 을 앞에 붙인다. 이미 들어 있으면 그대로), 주소 → addr1
        평일·금·토·일·휴일_영업시간 → business_hours (같은 시간인 연속 요일끼리 묶는다)
        정기휴무일·명절휴무 → closed_days
        식별자가 없으므로 contentid = "OY" + sha256(매장명|주소) 앞 5자리
  - 값은 **원문 그대로** 둔다. '오늘 휴무'·'-'·'10:30 ~ 00:00' 같은 예외 값도
    해석하지 않는다 — 해석은 이 데이터를 쓰는 판정 쪽에서 정할 일이다.
  - 좌표(mapx·mapy)·sigungucode·분류(contenttypeid·lclsSystm1~3)는 올리브영 원본에
    없으므로 **비워 둔다**(모름). TourAPI 매칭으로 채우는 단계는 아직 없다 — 매칭
    기준은 TourAPI 실제 응답을 본 뒤 정하기로 했다. 매칭되면 contentid 도 TourAPI
    값으로 바뀐다(담당자 결정).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

#: 805건 원본은 `scripts/`(적재기가 쓰는 자리), 작업용 데이터는 이 폴더(`data_processing/`)에 있다.
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
DATA_DIR = Path(__file__).resolve().parent
ACTIVITY_CSV = SCRIPTS / "activities_candidates_seoul_enriched.csv"
OLIVEYOUNG_CSV = DATA_DIR / "oliveyoung_seoul.csv"
MERGED_CSV = DATA_DIR / "activities_candidates_seoul_merged.csv"

#: 올리브영 요일별 영업시간 컬럼과, 합칠 때 앞에 붙일 요일 이름. ★순서가 곧 출력 순서이고
#: "연속 요일" 판단 기준이다 — 평일 다음이 금, 그다음이 토·일·휴일이다.
HOURS_COLUMNS = (
    ("평일_영업시간", "평일"),
    ("금_영업시간", "금"),
    ("토_영업시간", "토"),
    ("일_영업시간", "일"),
    ("휴일_영업시간", "휴일"),
)

#: 올리브영 ID 접두어. ★TourAPI contentid 는 숫자뿐이라, 문자로 시작하는 이 ID 는
#: 실제 TourAPI ID 와 절대 겹치지 않는다. 접두어 2자 + 해시 5자 = 기존 ID(6~7자리)와 비슷한 길이.
OLIVEYOUNG_ID_PREFIX = "OY"
OLIVEYOUNG_ID_HASH_LEN = 5


def oliveyoung_content_id(store_name: str, address: str) -> str:
    """매장명+주소로 고정 길이 ID 를 만든다. 같은 입력이면 항상 같은 ID 다(재실행 안전).

    ★구분자 `|` 를 넣는 이유: 넣지 않으면 ("A", "BC") 와 ("AB", "C") 가 같은 문자열이 되어
      같은 해시가 나온다.
    """
    digest = hashlib.sha256(f"{store_name.strip()}|{address.strip()}".encode("utf-8")).hexdigest()
    return OLIVEYOUNG_ID_PREFIX + digest[:OLIVEYOUNG_ID_HASH_LEN]


def merge_business_hours(row: dict[str, str]) -> str:
    """요일별 영업시간 다섯 칸을 한 칸으로. 같은 시간인 **연속 요일**을 묶는다.

    예) 모두 같으면        "평일·금·토·일·휴일 10:00 ~ 22:30"
        주중·주말이 다르면 "평일·금 08:00 ~ 22:00 / 토·일·휴일 10:30 ~ 20:00"

    ★떨어진 요일끼리는 값이 같아도 묶지 않는다("평일·토 …" 처럼 순서가 섞이면 읽는 사람이
      요일 순서를 다시 맞춰야 한다). 값은 원문 그대로 쓴다. 빈 칸은 건너뛴다.
    """
    groups: list[tuple[list[str], str]] = []
    for column, label in HOURS_COLUMNS:
        value = (row.get(column) or "").strip()
        if not value:
            continue
        if groups and groups[-1][1] == value:
            groups[-1][0].append(label)
        else:
            groups.append(([label], value))
    return " / ".join(f"{'·'.join(labels)} {value}" for labels, value in groups)


def merge_closed_days(row: dict[str, str]) -> str:
    """정기휴무일·명절휴무를 한 칸으로. 둘 다 비면 빈 문자열(모름).

    ★명절휴무 값('당일 휴무', '전일~익일 휴무' 등)은 그것만 보면 무엇의 당일인지 알 수 없어
      앞에 "명절"을 붙인다 — 예) "명절 당일 휴무". 정기휴무일은 원문 그대로 쓴다.
    """
    parts = []
    regular = (row.get("정기휴무일") or "").strip()
    holiday = (row.get("명절휴무") or "").strip()
    if regular:
        parts.append(regular)
    if holiday:
        parts.append(f"명절 {holiday}")
    return " / ".join(parts)


def oliveyoung_title(store_name: str) -> str:
    """매장명 앞에 브랜드명을 붙인다. 예) "명동점" → "올리브영 명동점".

    ★원본 368건 중 355건이 "명동점"처럼 브랜드 없이 지점명만 있어, 다른 장소와 섞인
      목록에서 무엇인지 알 수 없다(2026-09-26 담당자 결정). 이미 "올리브영"이 들어 있는
      13건("올리브영 명동 타운", "트렌드팟 바이 올리브영홍대" 등)은 중복되지 않게 그대로 둔다.
    """
    name = store_name.strip()
    return name if "올리브영" in name else f"올리브영 {name}"


def oliveyoung_to_activity_row(src: dict[str, str], columns: list[str]) -> dict[str, str]:
    """올리브영 한 행을 805건 CSV 의 컬럼 모양으로. 원본에 없는 칸은 빈 값(모름)이다."""
    row = {column: "" for column in columns}
    row.update({
        # ★ID 는 **원본 매장명**으로 만든다 — 표시용 title 규칙이 바뀌어도 ID 는 그대로여야 한다.
        "contentid": oliveyoung_content_id(src["매장명"], src["주소"]),
        "title": oliveyoung_title(src["매장명"]),
        "addr1": src["주소"].strip(),
        "business_hours": merge_business_hours(src),
        "closed_days": merge_closed_days(src),
        "data_source": "oliveyoung",
    })
    return row


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    # ★두 원본 모두 BOM 이 붙은 UTF-8 이다(2026-09-26 확인). utf-8-sig 로 읽어야 첫 컬럼명에
    #   BOM 문자가 섞이지 않는다.
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def build_merged(activity_path: Path = ACTIVITY_CSV,
                 oliveyoung_path: Path = OLIVEYOUNG_CSV) -> tuple[list[str], list[dict[str, str]]]:
    activity_columns, activity_rows = read_csv(activity_path)
    _, oliveyoung_rows = read_csv(oliveyoung_path)
    columns = activity_columns + ["data_source"]

    # ★805건은 값을 하나도 바꾸지 않는다 — 출처 표시만 붙인다.
    merged = [{**row, "data_source": "tour_api"} for row in activity_rows]
    merged += [oliveyoung_to_activity_row(row, columns) for row in oliveyoung_rows]

    # ★contentid 가 겹치면 나중에 적재할 때 한 행이 다른 행을 조용히 덮어쓴다(upsert 키).
    #   해시를 5자리로 줄였으니 데이터가 바뀌면 충돌할 수 있다 — 그때는 멈추고 알린다.
    seen: dict[str, str] = {}
    for row in merged:
        content_id = row["contentid"]
        if content_id in seen:
            raise SystemExit(f"contentid 충돌: {content_id} — '{seen[content_id]}' 와 "
                             f"'{row['title']}'. 해시 길이 또는 ID 규칙을 다시 정해야 한다")
        seen[content_id] = row["title"]
    return columns, merged


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    # 원본과 같은 인코딩(BOM 포함 UTF-8)으로 쓴다 — 엑셀에서 열어도 한글이 깨지지 않는다.
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--activity", type=Path, default=ACTIVITY_CSV)
    ap.add_argument("--oliveyoung", type=Path, default=OLIVEYOUNG_CSV)
    ap.add_argument("--out", type=Path, default=MERGED_CSV)
    args = ap.parse_args(argv)

    columns, rows = build_merged(args.activity, args.oliveyoung)
    write_csv(args.out, columns, rows)
    by_source: dict[str, int] = {}
    for row in rows:
        by_source[row["data_source"]] = by_source.get(row["data_source"], 0) + 1
    print(f"통합 {len(rows)}건 ({', '.join(f'{k} {v}' for k, v in by_source.items())}) · "
          f"컬럼 {len(columns)}개 → {args.out}")


if __name__ == "__main__":
    sys.exit(main())
