"""judge 가 근거 없는 답변에 점수를 주는지 기계적으로 검사한다.

★왜 이것인가 — v5 §15-4 는 judge agreement 를 **사람 라벨 20건**과의 일치율로 정의한다.
  1인 환경이라 사람 라벨을 만들 수 없다. 그래서 **사람 없이 확인 가능한 것**을 대신 잰다.

이 프로젝트를 이미 한 번 태운 실패가 정확히 이것이었다:
  > judge 가 환각 인용에 점수 — A 군이 `doc_06 §1` 을 지어냈고 실재 확인이 없었다
  > (docs/reports/debugs/2026-08-13_1200_평가가_환각인용에_점수를_준다.md)

`rescore` 가 인용을 코퍼스와 대조해 `citations.valid` / `citations.invalid` 를 남긴다.
그 사실과 judge 의 `policy_grounding` 점수가 어긋나는 행을 센다.

★이것은 judge agreement 가 **아니다.** judge 가 사람과 얼마나 맞는지는 여전히 모른다.
  다만 **judge 가 대놓고 틀리는 경우**는 잡는다.

    python -m eval.check_judge
"""
from __future__ import annotations

import glob
import json
import os
import sys

REPORTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval", "reports")


def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def audit(rows: list[dict]) -> dict:
    """근거 사실과 judge 점수가 어긋나는 행을 센다."""
    n = len(rows)
    # ★유효 인용이 하나도 없는데 grounding 점수를 준 행 = judge 가 지어낸 근거에 점수를 준 것
    ungrounded_but_scored = []
    # ★유효 인용이 있는데 grounding 0 을 준 행.
    #   ★이것을 "judge 오류" 로 세면 안 된다 — 두 지표가 서로 다른 것을 본다:
    #     - rescore.citations : prediction 의 `policy_evidence` **필드**를 코퍼스와 대조
    #     - judge.policy_grounding : **답변 본문**이 근거를 대고 있는지
    #   필드에 doc id 를 8개 담아 두고 본문에는 한 줄도 인용하지 않은 답변이 여기 걸린다.
    #   CLAUDE.md §0.1("모든 핵심 주장에 Evidence 가 붙어야 한다")로 보면
    #   **judge 쪽이 계약에 더 가깝다.** 그래서 이 값은 경고로만 낸다.
    grounded_but_zero = []
    invalid_citation_rows = 0

    for row in rows:
        cites = row.get("citations") or {}
        valid = cites.get("valid") or []
        invalid = cites.get("invalid") or []
        grounding = (row.get("judge") or {}).get("policy_grounding", 0) or 0
        if invalid:
            invalid_citation_rows += 1
        if not valid and grounding > 0:
            ungrounded_but_scored.append({"case_id": row.get("case_id"), "grounding": grounding,
                                          "claimed": cites.get("claimed") or [], "invalid": invalid})
        if valid and grounding == 0:
            grounded_but_zero.append({"case_id": row.get("case_id"), "valid": len(valid)})

    return {
        "rows": n,
        "rows_with_invalid_citations": invalid_citation_rows,
        # ★이것만이 결함이다 — 실재하지 않는 근거에 점수를 준 경우
        "ungrounded_but_scored": len(ungrounded_but_scored),
        # ★경고. 필드에만 근거가 있고 본문에는 없는 답변 (지표 정의 차이)
        "field_only_evidence": len(grounded_but_zero),
        "samples": ungrounded_but_scored[:5],
    }


def main() -> int:
    files = sorted(glob.glob(os.path.join(REPORTS, "rescored_*.jsonl")))
    if not files:
        print("rescored_*.jsonl 이 없다. 먼저 eval.rescore 를 돌려라.", file=sys.stderr)
        return 1

    total_bad = 0
    for path in files:
        arm = os.path.basename(path).replace("rescored_", "").replace(".jsonl", "")
        result = audit(load(path))
        total_bad += result["ungrounded_but_scored"]
        print(f"\n=== {arm} ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    print("\n" + "-" * 60)
    if total_bad:
        # ★실패로 끝낸다. 이 값이 0 이 아니면 평가 수치를 믿을 수 없다.
        print(f"★근거 없이 grounding 점수를 받은 행 {total_bad}건 — 평가 수치를 신뢰할 수 없다")
        return 1
    print("근거 없이 grounding 점수를 받은 행 0건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
