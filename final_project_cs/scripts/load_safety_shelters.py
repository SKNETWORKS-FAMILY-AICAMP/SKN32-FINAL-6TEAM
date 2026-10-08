"""공공 대피 장소 파일을 `safety_shelters` 표에 적재한다. `[결정 2026-10-06 사용자 — 재난 시 피난 안내]`

    python -m scripts.load_safety_shelters --type civil_defense --csv <파일.csv> --source "행정안전부 전국민방위대피시설표준데이터" [--source-date 2025-11-27] [--region 서울] [--replace] [--dry-run]
    python -m scripts.load_safety_shelters --type quake_outdoor  --csv <파일.csv> --source "서울시 지진옥외대피소" --region 서울

★받아 둔 **공공 자료 파일**에서만 적재한다 — 이 스크립트는 인터넷에서 받지 않고, 표에 없는 대피 장소를 만들지도 않는다.
  (자료: 공공데이터포털 「전국민방위대피시설표준데이터」 — 이용허락범위 제한 없음 · 「행정안전부 지진옥외대피장소」 — 이용허락범위 제한 없음 · 서울 열린데이터광장 「서울시 지진옥외대피소」 — 공공누리 1유형 출처표시. `[2026-10-06 조사]`)
★열 이름은 자료마다 다르다 — 아래 `COLUMNS` 의 후보 중 **있는 것**을 쓴다. 이름 · 좌표(위도 · 경도)를 못 찾으면 **적재하지 않고** 파일의 열 이름을 보여 주며 멈춘다(추측으로 열을 고르지 않는다).
★좌표는 WGS84 위도 · 경도여야 한다(한국 범위 33~39 / 124~132). 범위 밖이거나 숫자가 아니면 그 줄은 **건너뛰고 센다**(조용히 버리지 않는다). TM 같은 다른 좌표계 열은 쓰지 않는다.
★출력에는 건수만 낸다 — 파일 경로 · 접속 정보를 싣지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

#: 자료마다 다른 열 이름의 후보 — 공백 · 대소문자를 무시하고 비교한다. 앞의 것이 먼저다.
COLUMNS: dict[str, tuple[str, ...]] = {
    "name": ("시설명", "수용시설명", "대피시설명", "대피소명", "대피장소명", "대피장소", "시설이름", "이름", "명칭"),
    "address": ("소재지도로명주소", "도로명주소", "상세주소", "소재지지번주소", "지번주소", "주소", "소재지", "위치"),
    "latitude": ("위도", "위도(wgs84)", "latitude", "lat", "ycoord", "y"),
    "longitude": ("경도", "경도(wgs84)", "longitude", "lon", "lng", "xcoord", "x"),
    "underground": ("지하여부", "지상지하구분", "시설위치(지상지하)", "시설위치", "지하"),
    "capacity": ("최대수용인원", "수용인원", "수용가능인원", "수용능력"),
    "ref": ("관리번호", "시설코드", "대피소코드", "대피장소코드", "대피소id"),
}
REQUIRED = ("name", "latitude", "longitude")
#: 한국 범위 — 벗어나면 위도 · 경도가 아니라 다른 좌표계(TM 등)일 가능성이 크다
LAT_RANGE, LON_RANGE = (33.0, 39.0), (124.0, 132.0)


def _norm(text: str) -> str:
    return "".join(str(text).split()).lower()


def pick_columns(header: Iterable[str]) -> dict[str, str]:
    """파일의 열 이름 → 우리 칸. 후보 중 **있는 것**만. 못 찾은 칸은 없다."""
    by_norm = {_norm(h): h for h in header}
    found: dict[str, str] = {}
    for field_name, candidates in COLUMNS.items():
        for candidate in candidates:
            if _norm(candidate) in by_norm:
                found[field_name] = by_norm[_norm(candidate)]
                break
    return found


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _underground(value: Any) -> bool | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "지하" in text or text.upper() in ("Y", "예", "TRUE", "1"):
        return True
    if "지상" in text or text.upper() in ("N", "아니오", "FALSE", "0"):
        return False
    return None


@dataclass
class ParseResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    read: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    columns: dict[str, str] = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1


class MissingColumns(ValueError):
    def __init__(self, missing: list[str], header: list[str]) -> None:
        super().__init__(f"필수 열을 못 찾았다: {missing} — 파일의 열: {header}")
        self.missing, self.header = missing, header


def parse(text: str, *, region: str | None = None) -> ParseResult:
    """CSV 글자 → 적재할 줄. 필수 열(이름 · 위도 · 경도)이 없으면 `MissingColumns`. `region` 이 있으면 주소에 그 글자가 든 줄만."""
    reader = csv.DictReader(io.StringIO(text))
    header = list(reader.fieldnames or [])
    columns = pick_columns(header)
    missing = [name for name in REQUIRED if name not in columns]
    if missing:
        raise MissingColumns(missing, header)
    if region and "address" not in columns:
        raise MissingColumns(["address(--region 을 쓰려면 주소 열이 있어야 한다)"], header)
    result = ParseResult(columns=columns)
    for raw in reader:
        result.read += 1
        name = str(raw.get(columns["name"]) or "").strip()
        lat, lon = _number(raw.get(columns["latitude"])), _number(raw.get(columns["longitude"]))
        if not name:
            result.skip("no_name")
            continue
        if lat is None or lon is None:
            result.skip("no_coordinates")
            continue
        if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
            result.skip("not_wgs84_korea")                 # 위도 · 경도가 뒤바뀌었거나 다른 좌표계 — 지어서 고치지 않는다
            continue
        address = str(raw.get(columns["address"]) or "").strip() if "address" in columns else None
        if region and region not in (address or ""):
            result.skip("other_region")
            continue
        capacity = _number(raw.get(columns["capacity"])) if "capacity" in columns else None
        result.rows.append({
            "name": name, "address": address or None, "latitude": lat, "longitude": lon,
            "underground": _underground(raw.get(columns["underground"])) if "underground" in columns else None,
            "capacity": int(capacity) if capacity is not None and capacity >= 0 else None,
            "source_ref": (str(raw.get(columns["ref"])).strip() or None) if "ref" in columns else None})
    return result


def read_text(path: Path) -> str:
    """UTF-8(BOM 허용) → 안 되면 CP949(공공데이터 CSV 의 흔한 인코딩)."""
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("UTF-8 도 CP949 도 아닌 인코딩이다 — 파일을 UTF-8 로 저장해 다시 시도한다")


def load(conn, *, shelter_type: str, source: str, source_date: date | None, rows: list[dict[str, Any]], replace: bool) -> dict[str, int]:
    """한 트랜잭션으로 적재한다(호출자가 `conn.transaction()`). 돌려주는 값 = 건수."""
    counts = {"deleted": 0, "upserted": 0}
    with conn.cursor() as cur:
        if replace:
            cur.execute("DELETE FROM safety_shelters WHERE shelter_type=%s AND source=%s", (shelter_type, source))
            counts["deleted"] = cur.rowcount
        for row in rows:
            args = {**row, "type": shelter_type, "source": source, "source_date": source_date}
            if row["source_ref"] is not None:
                cur.execute(
                    "INSERT INTO safety_shelters (shelter_type, name, address, latitude, longitude, underground, capacity, source, source_ref, source_date) "
                    "VALUES (%(type)s,%(name)s,%(address)s,%(latitude)s,%(longitude)s,%(underground)s,%(capacity)s,%(source)s,%(source_ref)s,%(source_date)s) "
                    "ON CONFLICT (shelter_type, source, source_ref) WHERE source_ref IS NOT NULL DO UPDATE SET "
                    "name=EXCLUDED.name, address=EXCLUDED.address, latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude, "
                    "underground=EXCLUDED.underground, capacity=EXCLUDED.capacity, source_date=EXCLUDED.source_date, loaded_at=now()", args)
            else:
                cur.execute(
                    "INSERT INTO safety_shelters (shelter_type, name, address, latitude, longitude, underground, capacity, source, source_ref, source_date) "
                    "VALUES (%(type)s,%(name)s,%(address)s,%(latitude)s,%(longitude)s,%(underground)s,%(capacity)s,%(source)s,NULL,%(source_date)s) "
                    "ON CONFLICT (shelter_type, source, name, latitude, longitude) WHERE source_ref IS NULL DO UPDATE SET "
                    "address=EXCLUDED.address, underground=EXCLUDED.underground, capacity=EXCLUDED.capacity, source_date=EXCLUDED.source_date, loaded_at=now()", args)
            counts["upserted"] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--type", required=True, choices=("civil_defense", "quake_outdoor"))
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--source", required=True, help="자료 이름(출처 표시용 — 알림에 「자료: …」로 실린다)")
    parser.add_argument("--source-date", type=date.fromisoformat, default=None, help="자료 기준일 YYYY-MM-DD")
    parser.add_argument("--region", default=None, help="주소에 이 글자가 든 줄만(예: 서울). 안 주면 파일 전체")
    parser.add_argument("--replace", action="store_true", help="같은 종류 · 같은 출처의 옛 줄을 먼저 지운다")
    parser.add_argument("--dry-run", action="store_true", help="읽어서 건수만 보고 적재하지 않는다")
    args = parser.parse_args(argv)
    try:
        parsed = parse(read_text(args.csv), region=args.region)
    except MissingColumns as exc:
        print(f"적재하지 않았다 — {exc}", file=sys.stderr)
        return 2
    print(f"읽은 줄 {parsed.read} · 적재 대상 {len(parsed.rows)} · 건너뜀 {parsed.skipped or 0} · 쓴 열 {parsed.columns}")
    if args.dry_run or not parsed.rows:
        print("dry-run — 적재하지 않았다" if args.dry_run else "적재할 줄이 없다 — 지역 · 열 이름을 확인한다")
        return 0 if args.dry_run else 3
    from app.infrastructure.db.session import get_connection

    with get_connection() as conn, conn.transaction():
        counts = load(conn, shelter_type=args.type, source=args.source, source_date=args.source_date, rows=parsed.rows, replace=args.replace)
    print(f"적재 완료 — {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
