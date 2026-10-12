"""관광공사 원문이 바뀐 활동 장소만 운영시간 · 휴무를 다시 받는다 — 매일 밤. `[2026-10-12]` D-CS-015 개정 2 「원문 바뀜 알아채기」.

    1. 관광공사 목록(전국 → 주소가 서울인 행, `scripts/fetch_tourapi_list.fetch_category`)의 `modifiedtime` 을 받는다
       ★`areaCode=1` 로 받으면 서울 행의 대부분이 빠진다(서울 주소인데 지역코드가 빈 행 87% — 2026-09-29 확인)
    2. 활동 원장에 처음 적는 장소는 **기준점**으로만 적는다(다시 받지 않는다 — CSV 가 그 무렵 받은 원문이다)
    3. 기준점과 다른 장소만 `detailIntro2` 로 운영시간 · 휴무를 다시 받아 적는다 — 원문이 바뀌었으면 요일표를 비운다
       → 다음 `read_hours.py` 가 그 장소만 다시 편다
    4. 목록에 있지만 원장에 없는 서울 장소는 **수만 센다** — 새 장소를 넣을지는 데이터 결정이다(`merge_tourapi_new.py`)
브랜드 매장(OY · DS · AB · MS …)은 관광공사에 없어 보지 않는다. 매일 밤 돌리는 것(예약)은 운영 쪽 일이다(코어 sweeper · 작업 스케줄러).

사용법
    python scripts/activity/refresh_places.py --dry-run          받기만 하고 쓰지 않는다(무엇이 바뀌었나)
    python scripts/activity/refresh_places.py --max-calls 300    상세 호출 상한(개발 계정 하루 1,000건 — 목록 호출 몫을 남긴다)
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Callable, Iterable

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for path in (ROOT, HERE, os.path.dirname(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CATEGORIES = ("EV", "EX", "HS", "LS", "NA", "VE", "SH")

#: 목록 받기 — 분류 → 그 분류의 서울 행(`contentid` · `contenttypeid` · `modifiedtime` …)
ListFetcher = Callable[[str], "list[dict[str, Any]]"]
#: 상세 받기 — (contentid, contenttypeid) → detailIntro2 항목 | None
IntroFetcher = Callable[[str, str], "dict[str, Any] | None"]


def hours_from_intro(intro: dict[str, Any] | None, type_id: str) -> tuple[str | None, str | None]:
    """detailIntro2 → (운영시간 원문, 휴무 원문) — 종류별 필드는 `fill_tourapi_details.INTRO_FIELDS` 그대로."""
    from app.domains.travel_ops.instances.activity.data_processing.fill_tourapi_details import INTRO_FIELDS

    use_field, rest_field, _ = INTRO_FIELDS.get(str(type_id), (None, None, None))
    def pick(field):
        value = str((intro or {}).get(field) or "").strip() if field else ""
        return value or None
    return pick(use_field), pick(rest_field)


def refresh(conn, listed: Iterable[dict[str, Any]], fetch_intro: IntroFetcher, *, max_calls: int | None = None,
            dry_run: bool = False) -> dict[str, int]:
    """목록 행들로 원장을 맞춘다. 반환 — 기준점 · 그대로 · 바뀜 · 다시 받음 · 원문 바뀜 · 원장에 없음 · 상한에 걸림."""
    rows = {str(r.get("contentid")): r for r in listed if str(r.get("contentid") or "").isdigit()}
    with conn.cursor() as cur:
        cur.execute("SELECT content_id, source_modified_at, usetime_text, restdate_text FROM activity.ac_place "
                    "WHERE content_id = ANY(%s)", (list(rows),))
        stored = {cid: (mod, use, rest) for cid, mod, use, rest in cur.fetchall()}
    out = {"baseline": 0, "same": 0, "changed": 0, "refetched": 0, "text_changed": 0,
           "not_in_ledger": len(set(rows) - set(stored)), "over_limit": 0}
    calls = 0
    for cid, (mod, use, rest) in stored.items():
        listed_mod = str(rows[cid].get("modifiedtime") or "") or None
        if mod is None:
            out["baseline"] += 1
            if not dry_run:
                with conn.cursor() as cur:
                    cur.execute("UPDATE activity.ac_place SET source_modified_at = %s, source_checked_at = now() "
                                "WHERE content_id = %s", (listed_mod, cid))
            continue
        if listed_mod == mod:
            out["same"] += 1
            continue
        out["changed"] += 1
        if max_calls is not None and calls >= max_calls:
            out["over_limit"] += 1
            continue
        calls += 1
        new_use, new_rest = hours_from_intro(fetch_intro(cid, str(rows[cid].get("contenttypeid") or "")),
                                             str(rows[cid].get("contenttypeid") or ""))
        out["refetched"] += 1
        text_changed = (new_use, new_rest) != (use, rest)
        out["text_changed"] += int(text_changed)
        if dry_run:
            continue
        with conn.cursor() as cur:
            cur.execute("UPDATE activity.ac_place SET usetime_text = %s, restdate_text = %s, source_modified_at = %s, "
                        "source_checked_at = now(), "
                        "hours_week = CASE WHEN %s THEN NULL ELSE hours_week END, "
                        "hours_read = CASE WHEN %s THEN NULL ELSE hours_read END WHERE content_id = %s",
                        (new_use, new_rest, listed_mod, text_changed, text_changed, cid))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-calls", type=int, default=300, help="상세(detailIntro2) 호출 상한")
    parser.add_argument("--only", default=None, help="한 분류만(시험) — 예: HS")
    args = parser.parse_args()
    import psycopg
    from fetch_tourapi_list import fetch_category, load_key
    from load_places import dsn

    from app.domains.travel_ops.instances.activity.data_processing.tourapi_client import call_tourapi

    key = load_key()
    listed: list[dict[str, Any]] = []
    for cat in ([args.only] if args.only else CATEGORIES):
        _, seoul = fetch_category(key, cat)
        listed.extend(seoul)
    fetch_intro = lambda cid, type_id: call_tourapi("detailIntro2", {"contentId": cid, "contentTypeId": type_id}, key)  # noqa: E731
    with psycopg.connect(dsn(), autocommit=True) as conn:
        result = refresh(conn, listed, fetch_intro, max_calls=args.max_calls, dry_run=args.dry_run)
    print(f"목록 서울 {len(listed):,}행 → 기준점 {result['baseline']:,} · 그대로 {result['same']:,} · 바뀜 {result['changed']:,}"
          f"(다시 받음 {result['refetched']:,} · 원문 바뀜 {result['text_changed']:,} · 상한에 걸림 {result['over_limit']:,})"
          f" · 원장에 없음 {result['not_in_ledger']:,}" + (" — dry-run, 쓰지 않았다" if args.dry_run else ""))
    if result["text_changed"] and not args.dry_run:
        print("→ 원문이 바뀐 곳은 요일표를 비웠다. python scripts/activity/read_hours.py 로 다시 편다")


if __name__ == "__main__":
    main()
