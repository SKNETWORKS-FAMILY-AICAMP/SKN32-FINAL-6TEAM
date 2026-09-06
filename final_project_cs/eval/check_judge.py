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

import collections
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

    groundings: list[int] = []
    for row in rows:
        cites = row.get("citations") or {}
        valid = cites.get("valid") or []
        invalid = cites.get("invalid") or []
        grounding = (row.get("judge") or {}).get("policy_grounding", 0) or 0
        groundings.append(grounding)
        if invalid:
            invalid_citation_rows += 1
        if not valid and grounding > 0:
            ungrounded_but_scored.append({"case_id": row.get("case_id"), "grounding": grounding,
                                          "claimed": cites.get("claimed") or [], "invalid": invalid})
        if valid and grounding == 0:
            grounded_but_zero.append({"case_id": row.get("case_id"), "valid": len(valid)})

    # ★2026-09-06 추가 — **이 검사는 한 방향만 보고 있었다.**
    #   "근거가 없는데 점수를 줬나" 는 봤지만 "근거가 있을 때 점수가 늘 만점인가" 는
    #   아무도 안 봤다. 그래서 `policy_grounding` 이 **분산 0 인 상수**가 된 것을
    #   오래 못 잡았다 — 인용이 있으면 답변이 그것을 쓰든 말든 4 가 나온다.
    #   근거: docs/reports/debugs/2026-09-06_judge의_policy_grounding이_상수다.md
    #
    #   ★상수 축은 지표가 아니다. 그 축의 kappa 는 1.0 아니면 0.0 두 값만 나오고
    #   (agreement.py 가 0/0 을 완전일치로 특례 처리한다) 총점에는 늘 같은 값을
    #   더한다. DoD-15 는 이 축을 **못 잰다.**
    #   ★처음엔 "값이 딱 한 종류" 로만 봤다가 **정작 중요한 arm 을 놓쳤다.**
    #   proposed 는 180행 중 176행이 4 이고 4행만 3 이라 "상수 아님" 으로 빠졌다.
    #   사실상 상수인데 몇 행이 섞였다고 못 보면 검사가 의미 없다 — 그래서
    #   **한 값이 95% 이상을 차지하면** 상수로 본다.
    graded = [g for g in groundings if g > 0]
    distinct_when_graded = sorted(set(graded))
    dominant_share = 0.0
    if graded:
        dominant_share = collections.Counter(graded).most_common(1)[0][1] / len(graded)

    return {
        "rows": n,
        "rows_with_invalid_citations": invalid_citation_rows,
        # ★이것만이 결함이다 — 실재하지 않는 근거에 점수를 준 경우
        "ungrounded_but_scored": len(ungrounded_but_scored),
        # ★경고. 필드에만 근거가 있고 본문에는 없는 답변 (지표 정의 차이)
        "field_only_evidence": len(grounded_but_zero),
        # ★경고. 점수를 준 행들의 값이 한 종류뿐이면 이 축은 재고 있는 게 없다
        "grounding_values_when_scored": distinct_when_graded,
        "grounding_dominant_share": round(dominant_share, 3),
        "grounding_is_constant_when_scored": len(graded) >= 10 and dominant_share >= 0.95,
        "samples": ungrounded_but_scored[:5],
    }


def main() -> int:
    files = sorted(glob.glob(os.path.join(REPORTS, "rescored_*.jsonl")))
    if not files:
        print("rescored_*.jsonl 이 없다. 먼저 eval.rescore 를 돌려라.", file=sys.stderr)
        return 1

    total_bad = 0
    constant_axes: list[str] = []
    for path in files:
        arm = os.path.basename(path).replace("rescored_", "").replace(".jsonl", "")
        result = audit(load(path))
        total_bad += result["ungrounded_but_scored"]
        if result["grounding_is_constant_when_scored"]:
            constant_axes.append(
                f"{arm}: 값 {result['grounding_values_when_scored']} 중 한 값이 "
                f"{result['grounding_dominant_share']:.0%} ({result['rows']}행)")
        print(f"\n=== {arm} ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    print("\n" + "-" * 60)
    if constant_axes:
        # ★exit 1 로 끝내지 **않는다.** judge 를 바꾸면 지금까지의 모든 수치와
        #   비교가 끊기는데, 그 결정은 이 검사기가 내릴 일이 아니다. 대신 눈에
        #   띄게 적는다 — 조용한 경고는 이 결함이 오래 살아남은 이유였다.
        print("★policy_grounding 이 상수다 — 점수를 준 행들의 값이 한 종류뿐이다:")
        for line in constant_axes:
            print(f"    {line}")
        print("  이 축은 '근거의 질' 이 아니라 '인용이 붙었나' 를 재고 있다.")
        print("  그 축의 kappa 는 1.0 아니면 0.0 만 나온다 — DoD-15 는 이 축을 못 잰다.")
        print("  근거: docs/reports/debugs/2026-09-06_judge의_policy_grounding이_상수다.md")
        print("-" * 60)
    if total_bad:
        # ★실패로 끝낸다. 이 값이 0 이 아니면 평가 수치를 믿을 수 없다.
        print(f"★근거 없이 grounding 점수를 받은 행 {total_bad}건 — 평가 수치를 신뢰할 수 없다")
        return 1
    print("근거 없이 grounding 점수를 받은 행 0건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
