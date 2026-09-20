# -*- coding: utf-8 -*-
"""전처리에서 개인정보 마스킹이 **몇 건** 치환했는지 유형별로 센다.

    python -m ml.pii_audit

★전처리 통계는 「정규화로 글이 바뀐 수」만 적었다 — 그 안에 반복 글자 축약·공백
  정리가 섞여 있어 **마스킹 건수로 읽으면 안 된다.** 그래서 원문에 같은 규칙을
  하나씩 대 보고 따로 센다.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import REPO_ROOT, artifact_dir                     # noqa: E402
from ml.build_intent_pool import FILES, RAW, TRAVEL_ITEMS, _column   # noqa: E402
from ml.preprocess import DEFAULT_SOURCE, _EXTRA_PII       # noqa: E402

#: 제품 마스킹(`app/core/redaction.py::masked`)의 규칙을 이름 붙여 다시 적는다 — 세려고.
PRODUCT_RULES = (
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]+\b")),
    ("payment_id", re.compile(r"\bpay_[A-Za-z0-9_-]+\b")),
    ("phone_3_4_4", re.compile(r"(?<!\d)(\d{3})-(\d{4})-(\d{4})(?!\d)")),
    ("card_4x4", re.compile(r"(?<!\d)(\d{4})[ -](\d{4})[ -](\d{4})[ -](\d{4})(?!\d)")),
    ("email", re.compile(r"\b([^\s@]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")),
)
EXTRA_NAMES = ("rrn", "mobile", "account_like")


def count(texts) -> dict:
    hits, rows_with_hit, total = Counter(), 0, 0
    for text in texts:
        total += 1
        text = unicodedata.normalize("NFKC", text)
        found = False
        # ★전처리와 **같은 순서로 치환하면서** 센다. 규칙마다 원문에 따로 대면 한 번호가
        #   「3-4-4 전화」와 「휴대폰」에 이중으로 세인다(2026-09-17 첫 집계에서 그랬다).
        for name, pattern in PRODUCT_RULES:
            text, n = pattern.subn("[MASKED]", text)
            if n:
                hits[name] += n
                found = True
        for name, (pattern, replacement) in zip(EXTRA_NAMES, _EXTRA_PII):
            text, n = pattern.subn(replacement, text)
            if n:
                hits[name] += n
                found = True
        rows_with_hit += found
    return {"rows": total, "rows_with_pii": rows_with_hit,
            "replacements_total": sum(hits.values()), "by_type": dict(hits)}


def review_texts():
    with DEFAULT_SOURCE.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)["text"]


def complaint_titles():
    seen = set()
    for name in FILES:
        with (RAW / name).open(encoding="cp949", errors="replace", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader)
            id_col, item_col, title_col = (_column(header, "ACCIDENT_NO"), _column(header, "ITEM_NAME"),
                                           _column(header, "ACCIDENT_TITLE"))
            for row in reader:
                if len(row) <= max(id_col, item_col, title_col) or row[item_col].strip() not in TRAVEL_ITEMS:
                    continue
                if row[id_col] in seen:
                    continue
                seen.add(row[id_col])
                yield row[title_col]


def main() -> int:
    result = {"note": "원문(정규화 전)에 마스킹 규칙을 하나씩 대 본 건수",
              "sentiment_reviews": count(review_texts()),
              "travel_complaint_titles": count(complaint_titles())}
    out = artifact_dir() / "pii_audit.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
