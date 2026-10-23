"""golden/holdout 평가 데이터셋 인수 검사 (S-EVAL-DATASETS).

★Codex 산출물을 그대로 신뢰하지 않는다(RULE.md §3.6-3). 이 스크립트가
스키마·라우팅 가능 intent·문서 인용 정확성·한국어 여부·커버리지를 기계적으로 대조한다.

    python -m scripts.verify_eval_datasets
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "eval/datasets/golden.jsonl"
HOLDOUT = ROOT / "eval/datasets/holdout.jsonl"
DOC_INDEX = ROOT / "wiki/records/handoff/_prompts/_doc_index.json"

ALLOWED_INTENTS = {"order", "shipping", "return", "exchange"}
ALLOWED_CHANNELS = {"web", "chat", "email", "phone"}
ALLOWED_SENTIMENTS = {"positive", "neutral", "negative", "frustrated", "worried", "confused"}
ALLOWED_NEXT_ACTIONS = {"continue", "wait_for_input", "wait_for_approval", "call_tool", "handoff", "respond", "escalate"}
REQUIRED_FIELDS = {"case_id", "message", "channel", "expected_intent", "expected_issue_code",
                    "expected_sentiment", "expected_next_action", "doc_ref", "notes"}
INTENT_TO_SCOPE = {"order": "order", "shipping": "shipping", "return": "return", "exchange": "exchange"}

failures: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def note(msg: str) -> None:
    notes.append(msg)


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        fail(f"파일 없음: {path}")
        return []
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            fail(f"{path.name}:{i} JSON 파싱 실패 — {exc}")
    return rows


def korean_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 1.0
    korean = sum(1 for c in letters if "가" <= c <= "힣")
    return korean / len(letters)


def check_schema(name: str, rows: list[dict], expected_count: int) -> None:
    if len(rows) != expected_count:
        fail(f"{name}: 건수 {len(rows)} != {expected_count}")
    for row in rows:
        cid = row.get("case_id", "<no case_id>")
        missing = REQUIRED_FIELDS - row.keys()
        extra = row.keys() - REQUIRED_FIELDS
        if missing:
            fail(f"{name}:{cid} 필드 누락 {missing}")
        if extra:
            fail(f"{name}:{cid} 정의되지 않은 필드 {extra}")
        if row.get("expected_intent") not in ALLOWED_INTENTS:
            fail(f"{name}:{cid} expected_intent={row.get('expected_intent')!r} 이 라우팅 불가 값이다 (허용: {sorted(ALLOWED_INTENTS)})")
        if row.get("channel") not in ALLOWED_CHANNELS:
            fail(f"{name}:{cid} channel={row.get('channel')!r} 이 허용 목록 밖")
        if row.get("expected_sentiment") not in ALLOWED_SENTIMENTS:
            fail(f"{name}:{cid} expected_sentiment={row.get('expected_sentiment')!r} 이 허용 목록 밖")
        if row.get("expected_next_action") not in ALLOWED_NEXT_ACTIONS:
            fail(f"{name}:{cid} expected_next_action={row.get('expected_next_action')!r} 이 NextAction 열거값 밖")
        message = row.get("message", "")
        if not isinstance(message, str) or not message.strip():
            fail(f"{name}:{cid} message 가 비어 있다")
        elif korean_ratio(message) < 0.5:
            fail(f"{name}:{cid} message 가 한국어로 보이지 않는다 (한글 비율 낮음): {message[:60]!r}")


def check_case_id_convention(name: str, rows: list[dict], prefix: str) -> None:
    per_intent: dict[str, list[str]] = defaultdict(list)
    pattern = re.compile(rf"^{prefix}-(order|shipping|return|exchange)-(\d{{2}})$")
    for row in rows:
        cid = row.get("case_id", "")
        m = pattern.match(cid)
        if not m:
            fail(f"{name}: case_id {cid!r} 가 '{prefix}-<intent>-NN' 형식이 아니다")
            continue
        intent, seq = m.group(1), m.group(2)
        if intent != row.get("expected_intent"):
            fail(f"{name}:{cid} case_id 의 intent({intent}) != expected_intent({row.get('expected_intent')})")
        per_intent[intent].append(seq)
    for intent, seqs in per_intent.items():
        if len(seqs) != len(set(seqs)):
            dup = [s for s, c in Counter(seqs).items() if c > 1]
            fail(f"{name}: intent={intent} 안에서 번호 중복 {dup}")


def check_doc_refs(name: str, rows: list[dict], doc_sections: dict[str, set[str]], doc_scope: dict[str, str]) -> None:
    for row in rows:
        cid = row.get("case_id", "<no case_id>")
        ref = row.get("doc_ref", "")
        if "#" not in ref:
            fail(f"{name}:{cid} doc_ref={ref!r} 형식이 'doc_NN#섹션제목' 이 아니다")
            continue
        doc_id, _, section = ref.partition("#")
        if doc_id not in doc_sections:
            fail(f"{name}:{cid} doc_ref 의 문서 {doc_id!r} 가 _doc_index.json 에 없다 (지어낸 문서)")
            continue
        if section not in doc_sections[doc_id]:
            fail(f"{name}:{cid} doc_ref 의 섹션 {section!r} 이 {doc_id} 의 실제 섹션 제목과 완전일치하지 않는다")
        scope = doc_scope.get(doc_id)
        if scope and scope != row.get("expected_intent"):
            fail(f"{name}:{cid} doc_ref={doc_id}(scope={scope}) 가 expected_intent={row.get('expected_intent')!r} 와 안 맞는다")


def check_coverage(rows: list[dict], docs_by_scope: dict[str, list[str]]) -> None:
    doc_counts: Counter[str] = Counter()
    for row in rows:
        ref = row.get("doc_ref", "")
        doc_id = ref.split("#", 1)[0]
        doc_counts[doc_id] += 1
    for scope, doc_ids in docs_by_scope.items():
        for doc_id in doc_ids:
            count = doc_counts.get(doc_id, 0)
            if count < 2:
                fail(f"golden 커버리지 부족: {doc_id}({scope}) 가 doc_ref 로 {count}번만 등장 (요구 >=2)")
    note(f"golden 문서별 인용 횟수: {dict(sorted(doc_counts.items()))}")


def check_diversity(rows: list[dict]) -> None:
    wait_approval = sum(1 for r in rows if r.get("expected_next_action") == "wait_for_approval")
    degraded = sum(1 for r in rows if "degraded" in str(r.get("notes", "")).lower()
                   or "unavailable" in str(r.get("expected_issue_code", "")).lower())
    negative = sum(1 for r in rows if r.get("expected_sentiment") in {"negative", "frustrated"})
    note(f"golden 다양성: wait_for_approval={wait_approval} degraded/unavailable={degraded} negative/frustrated={negative}")
    if wait_approval < 3:
        fail(f"golden: wait_for_approval 케이스 {wait_approval}건 < 3")
    if degraded < 3:
        fail(f"golden: degraded/unavailable 케이스 {degraded}건 < 3")
    if negative < 5:
        fail(f"golden: negative/frustrated 케이스 {negative}건 < 5")


def check_no_id_overlap(golden: list[dict], holdout: list[dict]) -> None:
    golden_ids = {r.get("case_id") for r in golden}
    holdout_ids = {r.get("case_id") for r in holdout}
    overlap = golden_ids & holdout_ids
    if overlap:
        fail(f"golden/holdout case_id 중복: {overlap}")
    golden_msgs = {r.get("message", "").strip() for r in golden}
    holdout_msgs = {r.get("message", "").strip() for r in holdout}
    msg_overlap = golden_msgs & holdout_msgs
    if msg_overlap:
        fail(f"golden/holdout message 완전 중복 (holdout 이 오염됨): {msg_overlap}")


def main() -> int:
    if not DOC_INDEX.is_file():
        fail(f"문서 색인 없음: {DOC_INDEX} (scripts/verify_eval_datasets.py 를 실행하기 전에 생성한다)")
        print("\n".join(f"[FAIL] {m}" for m in failures))
        return 1

    index = json.loads(DOC_INDEX.read_text(encoding="utf-8"))
    doc_sections = {d["document_id"]: set(d["sections"]) for d in index}
    doc_scope = {d["document_id"]: d["scope"] for d in index}
    docs_by_scope: dict[str, list[str]] = defaultdict(list)
    for d in index:
        if d["scope"] in ALLOWED_INTENTS:
            docs_by_scope[d["scope"]].append(d["document_id"])

    golden = load_jsonl(GOLDEN)
    holdout = load_jsonl(HOLDOUT)

    check_schema("golden", golden, 60)
    check_schema("holdout", holdout, 20)
    check_case_id_convention("golden", golden, "g")
    check_case_id_convention("holdout", holdout, "h")
    check_doc_refs("golden", golden, doc_sections, doc_scope)
    check_doc_refs("holdout", holdout, doc_sections, doc_scope)
    if golden:
        check_coverage(golden, docs_by_scope)
        check_diversity(golden)
    check_no_id_overlap(golden, holdout)

    print("=" * 70)
    print("golden/holdout 데이터셋 인수 검사")
    print("=" * 70)
    for n in notes:
        print(f"  · {n}")
    print("-" * 70)
    if failures:
        for f in failures:
            print(f"  [FAIL] {f}")
        print("-" * 70)
        print(f"실패 {len(failures)}건 — 인수 불가")
        return 1
    print("전 항목 통과 — 인수 가능")
    return 0


if __name__ == "__main__":
    sys.exit(main())
