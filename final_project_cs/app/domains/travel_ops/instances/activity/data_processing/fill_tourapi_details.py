# -*- coding: utf-8 -*-
"""activity_total_data.csv 의 빈 칸을 TourAPI 상세(detailCommon2 · detailIntro2)로 채운다.

★컬럼 정의의 정본은 `wiki/teams/db_column.md` 다(`[2026-10-12]` 30개). 이 파일의 표는 그 문서를 옮긴 것이다.

사용(키를 가진 사람이 **자기 PC 에서** 실행한다. 최종 실행 위치: final_project_cs):
    python -m app.domains.travel_ops.instances.activity.data_processing.fill_tourapi_details --dry-run
    # 쇼핑(38)을 빼고 나머지만: ... fill_tourapi_details --types 12 14 28 15 --max-calls 900
    python -m app.domains.travel_ops.instances.activity.data_processing.fill_tourapi_details --max-calls 900
    # 하루 한도에 걸려 멈추면 다음 날 같은 명령을 다시 돌린다(캐시에 있는 건 부르지 않는다)

★대상은 TourAPI 행(contentid 가 숫자) 전부다 — 장소마다 detailCommon2 · detailIntro2 를 한 번씩 부른다.
  캐시(`tourapi_details_cache.jsonl`)에 있는 호출은 다시 부르지 않는다.
★**빈 칸만 채운다.** 이미 값이 있는 칸은 새 응답으로 덮어쓰지 않는다. 값은 원문 그대로 옮기고 파싱하지 않는다.
  같은 뜻의 필드가 둘 이상이면 ` / ` 로 이어 붙인다(예: 행사 예약처 / 예약 링크).
★순서는 사람이 볼 가치가 큰 타입부터다 — 관광지(12)·문화시설(14)·레포츠(28)·행사(15) 다음에
  쇼핑(38, 대부분 체인 매장). 한도가 모자라면 뒤쪽이 남는다.
★키·호출·캐시·멈춤 규칙은 `tourapi_client.py` 와 같다(그 함수를 가져다 쓴다) — 오류·한도 초과는
  「없음」으로 굳히지 않고 그 자리에서 멈추며, 받은 것까지는 CSV 에 반영한다.
★`indoor_outdoor` · `indoor_outdoor_source` 는 건드리지 않는다(`fill_indoor_outdoor.py` 와 사람이 채운다).
★`[2026-10-12 사용자]` `field_sources`(JSON) — 사람이 TourAPI 밖(공식 홈페이지 등)에서 채운 칸의 출처.
  그 칸은 TourAPI 응답에 값이 있으면 **TourAPI 값으로 바꾸고 출처를 지운다**(빈 칸만 채운다는 규칙의 유일한 예외).
  형식이 틀리면(허용 밖 컬럼 · 빈 칸의 출처 · url/checked 오류) 호출도 쓰기도 하지 않고 멈춘다.

`[2026-10-11]` 컬럼 옮기기(`migrate`) — 옛 헤더를 읽으면 문서의 29개로 바꿔 쓴다. 다시 돌려도 같다.
    info_center → tel · reservation → reservation_info · spend_time → spendtime
    sigungucode → 지운다(옛 시군구 코드는 `lDongSignguCd`(법정동 시군구)와 체계가 달라 옮기지 않는다)
  모르는 컬럼이 있으면 조용히 버리지 않고 멈춘다.

detailCommon2 — 필드 이름 = 컬럼 이름: overview · tel · homepage · modifiedtime · lDongSignguCd · addr2
detailIntro2 — 타입별(– 는 그 타입 응답에 필드가 없어 비운다):
    컬럼              12 관광지     14 문화시설        15 행사                       28 레포츠           38 쇼핑
    business_hours    usetime       usetimeculture     playtime                      usetimeleports      opentime
    closed_days       restdate      restdateculture    –                             restdateleports     restdateshopping
    fee               –             usefee             usetimefestival               usefeeleports       –
    capacity          accomcount    accomcountculture  –                             accomcountleports   –
    reservation_info  –             –                  bookingplace / eventhomepage  reservation         –
    spendtime         –             spendtime          spendtimefestival             –                   –
    eventstartdate    –             –                  eventstartdate                –                   –
    eventenddate      –             –                  eventenddate                  –                   –
    pet               chkpet        chkpetculture      –                             chkpetleports       chkpetshopping
    age_limit         expagerange   –                  agelimit                      expagerangeleports  –
    experience_guide  expguide      –                  –                             –                   –
    tel(common 이 빌 때만) infocenter infocenterculture sponsor1tel / sponsor2tel   infocenterleports   infocentershopping

브랜드 행(contentid 가 숫자가 아님)은 TourAPI 에 없어 부르지 않는다. `lDongSignguCd` 만 **같은 구**(주소의
「○○구」) TourAPI 행의 코드로 채운다 — 한 구에 코드가 둘 이상 보이면 한 코드가 `BRAND_CODE_SHARE`(95%) 이상일 때만
그 코드를 쓰고, 아니면 채우지 않고 센다.
`[2026-10-11 사용자 결정 A]` 처음엔 둘 이상이면 무조건 비웠다. 중구에서 「서울로 7017」 한 곳(주소는 중구, 코드는
용산구 170 — 서울역 쪽)이 끼어 41:1 이 되자 명동 브랜드 매장 32곳이 막혀 다수 규칙으로 바꿨다.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from .tourapi_client import (CALL_INTERVAL_SECONDS, StopFetching, append_cache, call_tourapi,
                             load_cache, load_service_key)

CSV_PATH = Path(__file__).resolve().parent / "activity_total_data.csv"

#: `wiki/teams/db_column.md` 의 30개 — 이 순서로 쓴다.
COLUMNS = ("contentid", "contenttypeid", "title", "addr1", "addr2", "lDongSignguCd", "mapx", "mapy",
           "lclsSystm1", "lclsSystm2", "lclsSystm3", "overview", "business_hours", "closed_days", "fee", "brand",
           "tel", "homepage", "modifiedtime", "capacity", "reservation_info", "spendtime",
           "eventstartdate", "eventenddate", "pet", "age_limit", "experience_guide",
           "indoor_outdoor", "indoor_outdoor_source", "field_sources")
#: 옛 이름 → 새 이름(`[2026-10-01]` 판에서 `[2026-10-11]` 판으로).
RENAMED = {"info_center": "tel", "reservation": "reservation_info", "spend_time": "spendtime"}
#: 옮기지 않고 지우는 칸 — 옛 시군구 코드는 법정동 코드와 체계가 다르다.
DROPPED = ("sigungucode",)

#: detailCommon2 — 필드 이름이 곧 컬럼 이름이다.
#: `[2026-10-12]` `addr2` 추가 — 응답에 있는데 안 옮겨 비어 있던 곳이 있었다(별마당도서관 「스타필드 코엑스몰 B1」 등).
COMMON_COLUMNS = ("overview", "tel", "homepage", "modifiedtime", "lDongSignguCd", "addr2")

#: 타입 → {컬럼: detailIntro2 필드(같은 뜻이 둘이면 튜플)}. 없는 컬럼은 그 타입 응답에 필드가 없다.
INTRO_FIELDS: dict[str, dict[str, str | tuple[str, ...]]] = {
    "12": {"business_hours": "usetime", "closed_days": "restdate", "capacity": "accomcount",
           "pet": "chkpet", "age_limit": "expagerange", "experience_guide": "expguide"},
    "14": {"business_hours": "usetimeculture", "closed_days": "restdateculture", "fee": "usefee",
           "capacity": "accomcountculture", "spendtime": "spendtime", "pet": "chkpetculture"},
    "15": {"business_hours": "playtime", "fee": "usetimefestival",
           "reservation_info": ("bookingplace", "eventhomepage"), "spendtime": "spendtimefestival",
           "eventstartdate": "eventstartdate", "eventenddate": "eventenddate", "age_limit": "agelimit"},
    "28": {"business_hours": "usetimeleports", "closed_days": "restdateleports", "fee": "usefeeleports",
           "capacity": "accomcountleports", "reservation_info": "reservation", "pet": "chkpetleports",
           "age_limit": "expagerangeleports"},
    "38": {"business_hours": "opentime", "closed_days": "restdateshopping", "pet": "chkpetshopping"},
}
#: `tel` 이 detailCommon2 에서 비었을 때만 쓰는 문의처 필드.
TEL_FALLBACK: dict[str, str | tuple[str, ...]] = {
    "12": "infocenter", "14": "infocenterculture", "15": ("sponsor1tel", "sponsor2tel"),
    "28": "infocenterleports", "38": "infocentershopping",
}
#: 사람이 볼 가치가 큰 타입부터.
PRIORITY = ["12", "14", "28", "15", "38"]
BOTH_OPERATIONS = ("detailCommon2", "detailIntro2")
#: 사람이 TourAPI 밖에서 채운 칸의 출처를 담는 컬럼(JSON `{컬럼: {by, url, checked}}`).
SOURCES_COLUMN = "field_sources"
#: `field_sources` 에 적어도 되는 컬럼 — 식별자·좌표·분류는 목록 수집이 정본, 소개글·체험 안내는 남의 글이라 뺀다.
HUMAN_FILLABLE = ("business_hours", "closed_days", "fee", "tel", "homepage", "reservation_info", "spendtime",
                  "capacity", "pet", "age_limit")
#: `[2026-10-12 사용자]` `claude` — Claude 가 공식 페이지 본문을 열어 확인한 값(근거 문구 `quote` 필수). 사람이 검토하면 `human`.
SOURCE_BY = ("human", "claude")
#: `[2026-10-14 사용자]` 출처의 `from` — 값을 페이지가 아니라 같은 행 `overview`(관광공사 소개글)에서 뽑았을 때.
FROM_OVERVIEW = "overview"
#: 한 구에 코드가 여럿일 때 브랜드 행에 쓰려면 한 코드가 이만큼 이상이어야 한다(경계에 걸친 장소 한두 곳은 넘긴다).
BRAND_CODE_SHARE = 0.95


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _joined(item: dict[str, Any], spec: str | tuple[str, ...]) -> str:
    """필드 하나, 또는 같은 뜻의 필드 여럿(예: 주최자 연락처 둘)을 ` / ` 로 이어 붙인다. 빈 값·중복은 뺀다."""
    names = (spec,) if isinstance(spec, str) else spec
    parts: list[str] = []
    for name in names:
        value = _text(item.get(name))
        if value and value not in parts:
            parts.append(value)
    return " / ".join(parts)


def migrate(rows: list[dict[str, str]], fieldnames: list[str]) -> Counter:
    """옛 헤더의 행을 `COLUMNS` 모양으로 바꾼다(제자리). 모르는 컬럼이 있으면 멈춘다 — 조용히 버리지 않는다."""
    unknown = [c for c in fieldnames if c not in COLUMNS and c not in RENAMED and c not in DROPPED]
    if unknown:
        raise SystemExit(f"모르는 컬럼이 있다 — db_column.md 와 이 파일의 COLUMNS 를 먼저 맞춘다: {unknown}")
    stats: Counter = Counter()
    for row in rows:
        for old, new in RENAMED.items():
            if old in row:
                value = row.pop(old)
                if value and not (row.get(new) or "").strip():
                    row[new] = value
                    stats[f"{old}→{new}"] += 1
        for old in DROPPED:
            if (row.pop(old, "") or "").strip():
                stats[f"{old} 지움"] += 1
        for column in COLUMNS:
            row.setdefault(column, "")
    return stats


def operations_for(row: dict[str, str]) -> tuple[str, ...]:
    """이 행에 필요한 호출. TourAPI 행(숫자 id · 아는 타입)이면 둘 다 — 캐시에 있는 것은 `fetch` 가 건너뛴다."""
    if not row["contentid"].isdigit() or row["contenttypeid"] not in INTRO_FIELDS:
        return ()
    return BOTH_OPERATIONS


def targets(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    todo = [r for r in rows if operations_for(r)]
    return sorted(todo, key=lambda r: PRIORITY.index(r["contenttypeid"]))


def _plain(text: str) -> str:
    """quote 대조용 — `<br>` 과 공백 차이만 없앤다."""
    return re.sub(r"\s+", " ", re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)).strip()


def read_sources(row: dict[str, str]) -> dict[str, dict[str, str]]:
    text = (row.get(SOURCES_COLUMN) or "").strip()
    return json.loads(text) if text else {}


def source_errors(rows: list[dict[str, str]]) -> list[str]:
    """`field_sources` 형식 검사. 틀린 곳을 모두 돌려준다 — 하나라도 있으면 `main` 이 멈춘다."""
    errors: list[str] = []
    for row in rows:
        where = f"{row['contentid']} {row['title']}"
        try:
            sources = read_sources(row)
        except json.JSONDecodeError as error:
            errors.append(f"{where}: JSON 이 아니다 ({error})")
            continue
        if not isinstance(sources, dict):
            errors.append(f"{where}: {{컬럼: 출처}} 모양이 아니다")
            continue
        for column, source in sources.items():
            if column not in HUMAN_FILLABLE:
                errors.append(f"{where}: {column} 은 field_sources 에 적을 수 없는 컬럼이다")
                continue
            if isinstance(source, dict) and source.get("na") is True:      # 「해당 없음」 — 빈 칸에만, url 없이
                if (row.get(column) or "").strip():
                    errors.append(f"{where}: {column} 칸에 값이 있는데 「해당 없음」 표시가 있다")
                if not {"by", "na", "checked"} <= set(source) <= {"by", "na", "checked", "note"}:
                    errors.append(f"{where}: {column} 「해당 없음」은 by · na · checked (+ 선택 note) 키여야 한다")
                elif source["by"] not in SOURCE_BY:
                    errors.append(f"{where}: {column} by={source['by']!r} (허용 {SOURCE_BY})")
                else:
                    try:
                        date.fromisoformat(str(source["checked"]))
                    except ValueError:
                        errors.append(f"{where}: {column} checked 가 YYYY-MM-DD 가 아니다")
                continue
            if not (row.get(column) or "").strip():
                errors.append(f"{where}: {column} 칸이 비었는데 출처만 있다")
            # ★`[2026-10-12 사용자]` url 은 claude 에만 필수 — 사람이 직접 확인해 값만 준 경우(`human`)는 url 없이 note 로 남긴다
            if not isinstance(source, dict) or not {"by", "checked"} <= set(source) <= {"by", "url", "checked", "quote", "note", "from"}:
                errors.append(f"{where}: {column} 출처는 by · checked (+ url · quote · note · from) 키여야 한다")
                continue
            if source["by"] == "claude" and not str(source.get("quote") or "").strip():
                errors.append(f"{where}: {column} by=claude 는 근거 문구(quote)가 있어야 한다")
            if source["by"] not in SOURCE_BY:
                errors.append(f"{where}: {column} by={source['by']!r} (허용 {SOURCE_BY})")
            if "from" in source:
                # ★`[2026-10-14 사용자]` 같은 행 소개글에서 뽑은 값 — url 대신 quote 가 그 소개글에 글자 그대로 있어야 한다
                if source["from"] != FROM_OVERVIEW:
                    errors.append(f"{where}: {column} from={source['from']!r} (허용 {FROM_OVERVIEW!r})")
                elif _plain(str(source.get("quote") or "")) not in _plain(row.get("overview") or ""):
                    errors.append(f"{where}: {column} quote 가 이 행 overview 에 없다")
            elif "url" in source or source["by"] == "claude":
                if not re.match(r"https?://\S+$", str(source.get("url") or "")):
                    errors.append(f"{where}: {column} url 이 http(s) 주소가 아니다")
            elif not str(source.get("note") or "").strip():
                errors.append(f"{where}: {column} url 이 없으면 어떻게 확인했는지 note 를 적어야 한다")
            try:
                date.fromisoformat(str(source["checked"]))
            except ValueError:
                errors.append(f"{where}: {column} checked 가 YYYY-MM-DD 가 아니다")
    return errors


def apply_cache(rows: list[dict[str, str]], cache: dict[tuple[str, str], dict[str, Any] | None]) -> Counter:
    """캐시에 든 응답을 CSV 행에 옮긴다. 이미 값이 있는 칸은 건드리지 않는다.

    ★예외 — `field_sources` 에 출처가 있는 칸(사람이 TourAPI 밖에서 채운 값)은 TourAPI 값으로 바꾸고 출처를 지운다.
    """
    stats: Counter = Counter()
    for row in rows:
        common = cache.get((row["contentid"], "detailCommon2"))
        intro = cache.get((row["contentid"], "detailIntro2"))
        new: dict[str, str] = {}
        if common:
            new.update({column: _text(common.get(column)) for column in COMMON_COLUMNS})
        if intro:
            ctype = row["contenttypeid"]
            new.update({column: _joined(intro, spec) for column, spec in INTRO_FIELDS.get(ctype, {}).items()})
            if not new.get("tel") and ctype in TEL_FALLBACK:      # common 의 tel 이 비었을 때만
                new["tel"] = _joined(intro, TEL_FALLBACK[ctype])
        sources = read_sources(row)
        for column, value in new.items():
            if not value:
                continue
            if not (row.get(column) or "").strip():
                row[column] = value
                stats[column] += 1
                if sources.pop(column, None) is not None:           # 「해당 없음」 표시 → TourAPI 값
                    stats[f"{column}(해당 없음→TourAPI)"] += 1
            elif column in sources:                                  # 사람 값 → TourAPI 값
                row[column] = value
                del sources[column]
                stats[f"{column}(사람 값→TourAPI)"] += 1
        row[SOURCES_COLUMN] = json.dumps(sources, ensure_ascii=False) if sources else ""
    return stats


def gu_of(address: str) -> str | None:
    """주소의 「○○구」. `scripts/merge_tourapi_new.py` 의 `gu_of` 와 같은 규칙(「서울특별 광진구」 같은 오타도 읽는다)."""
    match = re.match(r"\s*(?:서울(?:특별시|특별)?\s+)+(\S+구)", address or "")
    return match.group(1) if match else None


def fill_brand_signgu(rows: list[dict[str, str]]) -> Counter:
    """브랜드 행의 빈 `lDongSignguCd` 를 같은 구 TourAPI 행의 코드로 채운다.

    한 구에 코드가 둘 이상이면 가장 많은 코드가 `BRAND_CODE_SHARE` 이상일 때만 쓴다(다수 규칙). 아니면 채우지 않는다.
    """
    codes: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        gu, code = gu_of(row["addr1"]), (row.get("lDongSignguCd") or "").strip()
        if row["contentid"].isdigit() and gu and code:
            codes[gu][code] += 1
    stats: Counter = Counter()
    for row in rows:
        if row["contentid"].isdigit() or (row.get("lDongSignguCd") or "").strip():
            continue
        gu = gu_of(row["addr1"])
        seen = codes.get(gu or "")
        if not seen:
            stats["브랜드 구 코드 모름"] += 1
        else:
            code, count = seen.most_common(1)[0]
            if count / sum(seen.values()) < BRAND_CODE_SHARE:
                stats["브랜드 구 코드 여럿(안 채움)"] += 1
                continue
            row["lDongSignguCd"] = code
            stats["브랜드 lDongSignguCd"] += 1
            if len(seen) > 1:
                stats["브랜드 lDongSignguCd(다수 규칙)"] += 1
    return stats


def fetch(todo: list[dict[str, str]], service_key: str, max_calls: int | None) -> int:
    cache = load_cache()
    calls = 0
    for row in todo:
        cid, ctype = row["contentid"], row["contenttypeid"]
        wanted = operations_for(row)
        for operation, params in (("detailCommon2", {"contentId": cid}),
                                  ("detailIntro2", {"contentId": cid, "contentTypeId": ctype})):
            if operation not in wanted or (cid, operation) in cache:
                continue
            if max_calls is not None and calls >= max_calls:
                return calls
            item = call_tourapi(operation, params, service_key)
            append_cache(cid, operation, item)
            cache[(cid, operation)] = item
            calls += 1
            time.sleep(CALL_INTERVAL_SECONDS)
    return calls


def read_csv() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    moved = migrate(rows, fieldnames)
    if moved:
        print(f"컬럼 옮김: {dict(moved)}")
    return rows


def write_csv(rows: list[dict[str, str]]) -> None:
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def remaining_calls(rows: list[dict[str, str]], cache: dict) -> int:
    return sum(1 for r in targets(rows) for op in operations_for(r) if (r["contentid"], op) not in cache)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max-calls", type=int, default=None, help="이번 실행에서 부를 최대 횟수(장소당 2번)")
    ap.add_argument("--dry-run", action="store_true", help="호출 없이 대상 건수만 본다(CSV 도 쓰지 않는다)")
    ap.add_argument("--types", nargs="+", choices=sorted(INTRO_FIELDS), default=None,
                    help="이 타입만 받는다(예: --types 12 14 28 15). 안 주면 전부. 쇼핑(38)이 호출의 대부분이라 먼저 빼고 받을 때 쓴다")
    args = ap.parse_args(argv)

    rows = read_csv()
    errors = source_errors(rows)
    if errors:
        raise SystemExit("field_sources 형식 오류 — 고친 뒤 다시 돌린다(호출 · CSV 쓰기 안 함):\n  " + "\n  ".join(errors))
    todo = [r for r in targets(rows) if not args.types or r["contenttypeid"] in args.types]
    cache = load_cache()
    remaining = sum(1 for r in todo for op in operations_for(r) if (r["contentid"], op) not in cache)
    print(f"대상 {len(todo)}행 {dict(Counter(r['contenttypeid'] for r in todo))} · 아직 안 부른 호출 {remaining}건")
    if args.dry_run:
        return

    try:
        calls = fetch(todo, load_service_key(), args.max_calls)
        print(f"이번 실행 호출 {calls}건")
    except StopFetching as stop:
        print(f"멈춤: {stop}\n→ 받은 것까지는 캐시에 남아 있다. 원인을 확인한 뒤 같은 명령을 다시 돌리면 이어서 받는다")

    cache = load_cache()
    filled = apply_cache(rows, cache)
    filled.update(fill_brand_signgu(rows))
    write_csv(rows)
    print(f"CSV 반영: {dict(filled)} · 아직 안 부른 호출 {remaining_calls(rows, cache)}건")


if __name__ == "__main__":
    sys.exit(main())
