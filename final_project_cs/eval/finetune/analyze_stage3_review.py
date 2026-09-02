"""stage3 holdout 비교 결과에서 **echo 율**과 grounded 를 갈라 센다.

★v8 까지 이 분석을 손으로 했다. 손으로 세면 재현이 안 되고, 무엇보다
  "mismatch 만 따로"라는 가장 중요한 구분을 매번 다시 눈으로 골라야 한다.

이 실험이 재는 것은 하나다 — **모델이 draft 를 그대로 돌려주는(echo) 지름길을
쓰는가, 아니면 evidence 를 보고 판단하는가.** 그래서 두 부류를 갈라 센다:

    mismatch      evidence 를 draft 와 어긋나게 **일부러** 조작한 케이스.
                  여기서 echo 하면 틀린 답을 그대로 내보낸 것이다.
    non-mismatch  draft 와 evidence 가 원래 일치하는 케이스.
                  여기서는 echo 가 오히려 **정답**일 수 있다.

두 부류를 합쳐서 세면 아무 말도 못 한다 — non-mismatch 가 훨씬 많아서
"대체로 echo 한다"가 늘 참으로 보인다. v7 이 그렇게 보였다.

    python -m eval.finetune.analyze_stage3_review --input eval/reports/2026-09-02_stage3_v9_review.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MISMATCH_SUFFIX = "-mismatch"


def _normalize(text: str) -> str:
    """비교용 정규화 — 공백과 문장부호 차이로 echo 를 놓치지 않는다."""
    return re.sub(r"[\s.,!?~…]+", "", str(text or "")).strip()


def _response_text(candidate: object) -> str:
    if isinstance(candidate, dict):
        return str(candidate.get("final_response_text") or "")
    return str(candidate or "")


def _summarize(rows: list[dict], arm: str) -> dict:
    graded, echoes, errors = [], 0, 0
    grounded_values: list[int] = []
    for row in rows:
        entry = row.get(arm) or {}
        if "error" in entry:
            errors += 1
            continue
        text = _response_text(entry.get("candidate"))
        judge = entry.get("judge") or {}
        grounded = judge.get("grounded")
        if isinstance(grounded, (int, float)):
            grounded_values.append(int(grounded))
        # ★echo 판정은 **완전 일치**(정규화 후)로 한다. "비슷하게 고쳤다"를
        #   echo 로 세면 재작성을 시도한 것까지 지름길로 몰아 실제보다 나쁘게 보인다.
        if text and _normalize(text) == _normalize(row.get("draft")):
            echoes += 1
        graded.append(row)
    n = len(graded)
    return {
        "n": n,
        "errors": errors,
        "echo": echoes,
        "echo_rate": round(echoes / n, 3) if n else None,
        "grounded_mean": round(sum(grounded_values) / len(grounded_values), 3) if grounded_values else None,
        "grounded_values": grounded_values,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="stage3 holdout 비교 결과 분석 (echo/grounded)")
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    path = ROOT / args.input if not Path(args.input).is_absolute() else Path(args.input)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    mismatch = [r for r in rows if str(r.get("case_id", "")).endswith(MISMATCH_SUFFIX)]
    consistent = [r for r in rows if not str(r.get("case_id", "")).endswith(MISMATCH_SUFFIX)]

    report = {"input": args.input, "total": len(rows)}
    for label, subset in (("all", rows), ("mismatch", mismatch), ("non_mismatch", consistent)):
        report[label] = {arm: _summarize(subset, arm) for arm in ("local_ft", "openai")}

    print(json.dumps(report, ensure_ascii=False, indent=2))

    m = report["mismatch"]["local_ft"]
    if m["n"] == 0:
        print("\n★mismatch 케이스가 0건이다 — 이 실행으로는 지름길 여부를 말할 수 없다.")
    else:
        print(f"\n★핵심: mismatch {m['n']}건 중 local_ft 가 draft 를 그대로 돌려준 것 "
              f"{m['echo']}건 ({m['echo_rate']}). grounded 평균 {m['grounded_mean']}.")
        print(f"  같은 케이스에서 OpenAI: echo {report['mismatch']['openai']['echo']}건, "
              f"grounded 평균 {report['mismatch']['openai']['grounded_mean']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
