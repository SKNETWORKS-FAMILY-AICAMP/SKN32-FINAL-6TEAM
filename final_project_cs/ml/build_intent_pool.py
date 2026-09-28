# -*- coding: utf-8 -*-
"""`intent`·`issue_code` 학습용 **실제 글** 풀 — 공정위 소비자상담 제목 중 여행 서비스 품목.

    python -m ml.build_intent_pool --per-item 400

★**왜 이 데이터인가.** 여행 CS 메시지에 우리 라벨이 붙은 공개 데이터는 없다. 대신
  **실제 소비자가 여행 서비스(항공·해외여행·숙박·공연·외식·철도·버스)에 대해 쓴 상담
  제목**이 있다. 여기에 교사 모델(Gemma)로 제품 어휘 라벨을 붙인다. 순수 합성보다
  글이 실제에 가깝다.

★**품목은 허용 목록으로 고른다.** 낱말 검색으로 고르면 「택배화물운송」「여행용가방」
  「운동기구」가 섞여 들어온다(2026-09-17 실측). 여행 서비스가 아닌 품목은 명시적으로
  뺀다 — 무엇을 뺐는지 세어 남긴다.

★**열 이름을 문자 그대로 믿지 않는다.** 헤더가 `품목명(ITEM_NAME)` 모양이다.
  `ITEM_NAME` 으로 찾았다가 **0건**이 나와 「여행 품목 없음」으로 읽을 뻔했다
  (2026-09-17). 그래서 **포함** 검사로 칸을 찾고, 못 찾으면 그 파일을 실패로 센다.

★**같은 상담이 두 파일에 겹친다**(온라인 상거래 · 지역별). 사건번호로 한 번만 센다.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import REPO_ROOT, artifact_dir          # noqa: E402
from ml.preprocess import normalise              # noqa: E402  ★감정 쪽과 같은 정규화·PII 마스킹

RAW = REPO_ROOT.parent / "datasets" / "voc" / "data_go_kr_consumer_complaints" / "raw"
FILES = ("15098340_online_commerce_complaints.csv", "15098349_regional_complaints.csv")

#: 여행 서비스 품목 — 이것만 쓴다.
TRAVEL_ITEMS = frozenset({
    "항공여객운송서비스", "항공기", "국외여행", "국내여행", "기타여행",
    "호텔", "펜션", "콘도", "기타숙박시설",
    "각종공연관람", "레저시설이용",
    "외식", "기타음식관련서비스",
    "철도여객운송서비스", "버스여객운송서비스", "택시여객운송서비스",
    "자동차대여", "렌터카",
})

MIN_CHARS, MAX_CHARS = 8, 150


def _column(header: list[str], key: str) -> int | None:
    return next((index for index, name in enumerate(header) if key in name), None)


def main() -> int:
    parser = argparse.ArgumentParser(description="intent·issue_code 실제 글 풀 만들기")
    parser.add_argument("--per-item", type=int, default=400, help="품목마다 최대 몇 건")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    counts: Counter = Counter()
    other_items: Counter = Counter()
    seen_ids: set[str] = set()
    seen_texts: set[str] = set()
    by_item: dict[str, list[dict]] = defaultdict(list)
    failed_files: list[str] = []

    for name in FILES:
        path = RAW / name
        if not path.exists():
            failed_files.append(f"{name}: 파일 없음")
            continue
        with path.open(encoding="cp949", errors="replace", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader)
            id_col, item_col, title_col = (_column(header, "ACCIDENT_NO"),
                                           _column(header, "ITEM_NAME"),
                                           _column(header, "ACCIDENT_TITLE"))
            if None in (id_col, item_col, title_col):
                failed_files.append(f"{name}: 필요한 칸을 못 찾음 {header}")
                continue
            for row in reader:
                counts["rows_read"] += 1
                if len(row) <= max(id_col, item_col, title_col):
                    counts["dropped_short_row"] += 1
                    continue
                item = row[item_col].strip()
                if item not in TRAVEL_ITEMS:
                    other_items[item] += 1
                    continue
                counts["travel_rows"] += 1
                accident = row[id_col].strip()
                if accident in seen_ids:
                    counts["dropped_same_case_other_file"] += 1
                    continue
                seen_ids.add(accident)
                text = normalise(row[title_col])
                if not (MIN_CHARS <= len(text) <= MAX_CHARS):
                    counts["dropped_length"] += 1
                    continue
                if text in seen_texts:
                    counts["dropped_duplicate_text"] += 1
                    continue
                seen_texts.add(text)
                by_item[item].append({"id": f"kca-{accident}", "text": text, "item": item,
                                      "source": "kca_complaint_title"})

    rng = random.Random(args.seed)
    pool: list[dict] = []
    per_item_kept = {}
    for item, rows in sorted(by_item.items()):
        rng.shuffle(rows)
        chosen = rows[:args.per_item]
        per_item_kept[item] = {"available": len(rows), "kept": len(chosen)}
        pool += chosen
    rng.shuffle(pool)

    out = artifact_dir("intent_ko", "data")
    with (out / "pool_real.jsonl").open("w", encoding="utf-8") as handle:
        for row in pool:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stats = {
        "files": list(FILES), "failed_files": failed_files, "seed": args.seed,
        "per_item_cap": args.per_item, "counts": dict(counts),
        "unique_travel_cases_after_filters": sum(len(rows) for rows in by_item.values()),
        "pool_size": len(pool), "per_item": per_item_kept,
        "travel_items_allowlist": sorted(TRAVEL_ITEMS),
        "excluded_item_examples_top20": other_items.most_common(20),
    }
    (out / "pool_real_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    print(json.dumps({key: value for key, value in stats.items()
                      if key not in ("excluded_item_examples_top20", "travel_items_allowlist")},
                     ensure_ascii=False, indent=2))
    print(f"\n산출물: {out / 'pool_real.jsonl'}")
    return 1 if failed_files else 0


if __name__ == "__main__":
    raise SystemExit(main())
