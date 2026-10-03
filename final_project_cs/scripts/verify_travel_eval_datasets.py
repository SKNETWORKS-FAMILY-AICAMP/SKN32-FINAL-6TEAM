# -*- coding: utf-8 -*-
"""여행 인라인 분류 평가 자료(golden · holdout) 인수 검사. `[2026-10-03]`

    python -m scripts.verify_travel_eval_datasets

쇼핑몰 시절 검사기(`verify_eval_datasets.py`)를 대체한다 — 그쪽은 주문 · 배송 · 반품 · 교환 어휘를 허용 목록으로 갖고 있었다. 여기는 **서버가 실제로 쓰는 어휘**
(`app/modules/travel_ops/feedback.py` 의 `INTENTS` · `ISSUE_CODES` · `SENTIMENTS` · `SEVERITIES`)를 그대로 불러와 대조한다 — 따로 적은 목록은 어긋난다.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from app.modules.travel_ops.feedback import INTENTS, ISSUE_CODES, SENTIMENTS, SEVERITIES

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "eval/datasets/travel_golden.jsonl"
HOLDOUT = ROOT / "eval/datasets/travel_holdout.jsonl"

REQUIRED = {"case_id", "message", "channel", "locale", "expected_intent", "expected_issue_code", "expected_sentiment",
            "expected_severity", "label_by", "notes"}
CHANNELS = {"web", "chat", "email", "phone"}
LOCALES = {"ko", "en", "zh-TW", "ja"}
LABEL_BY = {"claude-draft", "human"}
#: 쇼핑몰 시절 낱말 — 여행 자료에 섞이면 안 된다(전역 규칙: 쇼핑몰 시절 자료를 쓰지 않는다)
COMMERCE_WORDS = ("주문번호", "택배", "송장", "반품", "장바구니", "쿠팡", "네이버쇼핑", "배송완료", "환불 신청")
#: 일정 제출은 채팅이 아니라 API · 접수로 온다 — 이 자료에 넣지 않는다
EXCLUDED_INTENTS = {"itinerary_submit"}
GOLDEN_MIN_PER_CODE = 3
GOLDEN_MIN_OTHER = 6
GOLDEN_MIN_PER_INTENT = 8


def _load(path: Path) -> tuple[list[dict], list[str]]:
    if not path.is_file():
        return [], [f"파일 없음: {path.name}"]
    rows, problems = [], []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            problems.append(f"{path.name}:{number} JSON 파싱 실패 — {exc}")
    return rows, problems


def _korean_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(1 for c in letters if "가" <= c <= "힣") / len(letters) if letters else 1.0


def check_rows(name: str, rows: list[dict], *, prefix: str, size: int) -> list[str]:
    problems: list[str] = []
    if len(rows) != size:
        problems.append(f"{name}: 건수 {len(rows)} != {size}")
    ids = Counter(row.get("case_id") for row in rows)
    problems += [f"{name}: case_id 중복 {cid}" for cid, count in ids.items() if count > 1]
    pattern = re.compile(rf"^{prefix}-(activity|dining|mobility|booking|lodging|flight|other)-(\d{{2}})$")
    for row in rows:
        cid = row.get("case_id", "<no case_id>")
        missing, extra = REQUIRED - row.keys(), row.keys() - REQUIRED
        if missing:
            problems.append(f"{name}:{cid} 필드 누락 {sorted(missing)}")
        if extra:
            problems.append(f"{name}:{cid} 정의되지 않은 필드 {sorted(extra)}")
        intent, code = row.get("expected_intent"), row.get("expected_issue_code")
        if intent not in INTENTS or intent in EXCLUDED_INTENTS:
            problems.append(f"{name}:{cid} expected_intent={intent!r} (허용: {sorted(INTENTS - EXCLUDED_INTENTS)})")
        if code not in ISSUE_CODES:
            problems.append(f"{name}:{cid} expected_issue_code={code!r} 이 서버 어휘에 없다")
        if row.get("expected_sentiment") not in SENTIMENTS:
            problems.append(f"{name}:{cid} expected_sentiment={row.get('expected_sentiment')!r}")
        if row.get("expected_severity") not in SEVERITIES:
            problems.append(f"{name}:{cid} expected_severity={row.get('expected_severity')!r}")
        if row.get("channel") not in CHANNELS:
            problems.append(f"{name}:{cid} channel={row.get('channel')!r}")
        if row.get("locale") not in LOCALES:
            problems.append(f"{name}:{cid} locale={row.get('locale')!r}")
        if row.get("label_by") not in LABEL_BY:
            problems.append(f"{name}:{cid} label_by={row.get('label_by')!r}")
        # `other` 코드와 `other` 의도는 한 쌍이다 — 어긋난 라벨은 정답이 아니다
        if (code == "other") != (intent == "other"):
            problems.append(f"{name}:{cid} intent={intent!r} 와 issue_code={code!r} 가 어긋난다(other 는 한 쌍이다)")
        match = pattern.match(cid) if isinstance(cid, str) else None
        group = "other" if code == "other" else str(code).split("_")[0]
        if not match or match.group(1) != group:
            problems.append(f"{name}:{cid} case_id 가 '{prefix}-<{group}>-NN' 형식이 아니다")
        message = row.get("message")
        if not isinstance(message, str) or not message.strip():
            problems.append(f"{name}:{cid} message 가 비어 있다")
            continue
        if row.get("locale") == "ko" and _korean_ratio(message) < 0.3:
            problems.append(f"{name}:{cid} locale=ko 인데 한글이 거의 없다: {message[:40]!r}")
        if row.get("locale") != "ko" and _korean_ratio(message) > 0.3:
            problems.append(f"{name}:{cid} locale={row.get('locale')} 인데 한글이 많다: {message[:40]!r}")
        banned = [word for word in COMMERCE_WORDS if word in message]
        if banned:
            problems.append(f"{name}:{cid} 쇼핑몰 시절 낱말 {banned} — 여행 문장이어야 한다")
    return problems


def check(golden: list[dict], holdout: list[dict]) -> list[str]:
    problems = check_rows("golden", golden, prefix="tg", size=72) + check_rows("holdout", holdout, prefix="th", size=24)
    codes = Counter(row.get("expected_issue_code") for row in golden)
    for code in sorted(ISSUE_CODES):
        need = GOLDEN_MIN_OTHER if code == "other" else GOLDEN_MIN_PER_CODE
        if codes[code] < need:
            problems.append(f"golden 커버리지 부족: {code} {codes[code]}건 (요구 ≥{need})")
    held = {row.get("expected_issue_code") for row in holdout}
    problems += [f"holdout 에 {code} 가 없다" for code in sorted(ISSUE_CODES - held)]
    intents = Counter(row.get("expected_intent") for row in golden)
    for intent in sorted(INTENTS - EXCLUDED_INTENTS):
        if intents[intent] < GOLDEN_MIN_PER_INTENT:
            problems.append(f"golden 의도 커버리지 부족: {intent} {intents[intent]}건 (요구 ≥{GOLDEN_MIN_PER_INTENT})")
    overlap = {row.get("message") for row in golden} & {row.get("message") for row in holdout}
    problems += [f"golden 과 holdout 에 같은 문장: {message[:40]!r}" for message in sorted(overlap)]
    return problems


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    (golden, p1), (holdout, p2) = _load(GOLDEN), _load(HOLDOUT)
    problems = p1 + p2 + (check(golden, holdout) if not (p1 or p2) else [])
    print(f"golden {len(golden)} · holdout {len(holdout)} · 라벨 출처 {dict(Counter(r.get('label_by') for r in golden + holdout))}")
    for problem in problems:
        print("FAIL", problem)
    print("통과" if not problems else f"실패 {len(problems)}건")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
