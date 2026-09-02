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


#: 합성 shipment 케이스가 쓰는 상태 어휘. mismatch 판정은 이 값의 일치로 한다.
SHIPMENT_STATUS = re.compile(r"(delivered|delayed|in_transit|out_for_delivery|pending|returned)")


def _adopted_evidence_status(rows: list[dict], holdout_path: Path) -> dict | None:
    """★judge 를 거치지 않고 **상태값이 실제로 바뀌었는지**를 직접 센다.

    이 실험의 정답은 명확하다 — evidence 를 조작해 draft 와 어긋나게 만들었으니,
    올바른 응답은 **조작된 evidence 쪽 상태값**을 말하는 것이다. 그러면 문자열
    비교만으로 맞고 틀림을 가릴 수 있고, 채점자(LLM)의 판단이 끼어들지 않는다.

    ★실제로 그게 필요했다. v9 실행에서 judge 가 local_ft 를 이렇게 깎았다:

        local_ft: "배송 상태는 delayed입니다."   (evidence 가 delayed — 정답)
        judge:    grounded=0, "states 'delayed', which contradicts the draft
                  that incorrectly states 'delivered'"

      judge 프롬프트는 "evidence 가 유일한 진실"이라고 적어 두었는데도 채점은
      draft 를 기준으로 했다. 틀린 draft 를 올바르게 고친 것을 벌한 것이다.
      그래서 mismatch 케이스에서 `grounded` 는 쓸 수 없다.
    """
    if not holdout_path.exists():
        return None
    holdout = {}
    for line in holdout_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            holdout[row["case_id"]] = row

    per_arm = {"local_ft": 0, "openai": 0}
    cases = []
    for row in rows:
        source = holdout.get(row["case_id"])
        if source is None:
            continue
        user_content = json.loads(source["messages"][0]["content"])
        found = SHIPMENT_STATUS.findall(
            json.dumps(user_content["context"].get("evidence", []), ensure_ascii=False))
        if not found:
            continue
        expected = found[0]
        entry = {"case_id": row["case_id"], "evidence": expected,
                 "draft": (SHIPMENT_STATUS.search(row.get("draft") or "") or [None])
                 and (SHIPMENT_STATUS.search(row.get("draft") or "").group(1)
                      if SHIPMENT_STATUS.search(row.get("draft") or "") else None)}
        for arm in ("local_ft", "openai"):
            said = SHIPMENT_STATUS.search(_response_text((row.get(arm) or {}).get("candidate")))
            value = said.group(1) if said else None
            entry[arm] = value
            if value == expected:
                per_arm[arm] += 1
        cases.append(entry)

    total = len(cases)
    return {
        "n": total,
        "local_ft_correct": per_arm["local_ft"],
        "openai_correct": per_arm["openai"],
        "local_ft_rate": round(per_arm["local_ft"] / total, 3) if total else None,
        "openai_rate": round(per_arm["openai"] / total, 3) if total else None,
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="stage3 holdout 비교 결과 분석 (echo/grounded)")
    parser.add_argument("--input", required=True)
    parser.add_argument("--holdout", default=None,
                        help="주면 judge 를 거치지 않고 상태값 채택 여부를 직접 센다 (권장)")
    args = parser.parse_args()

    path = ROOT / args.input if not Path(args.input).is_absolute() else Path(args.input)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    mismatch = [r for r in rows if str(r.get("case_id", "")).endswith(MISMATCH_SUFFIX)]
    consistent = [r for r in rows if not str(r.get("case_id", "")).endswith(MISMATCH_SUFFIX)]

    report = {"input": args.input, "total": len(rows)}
    for label, subset in (("all", rows), ("mismatch", mismatch), ("non_mismatch", consistent)):
        report[label] = {arm: _summarize(subset, arm) for arm in ("local_ft", "openai")}

    adopted = None
    if args.holdout:
        holdout_path = ROOT / args.holdout if not Path(args.holdout).is_absolute() else Path(args.holdout)
        adopted = _adopted_evidence_status(mismatch, holdout_path)
        report["evidence_status_adopted"] = adopted

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if adopted and adopted["n"]:
        print(f"\n★judge 없이 직접 대조 (mismatch {adopted['n']}건): "
              f"local_ft {adopted['local_ft_correct']}/{adopted['n']} "
              f"({adopted['local_ft_rate']:.0%}) · "
              f"openai {adopted['openai_correct']}/{adopted['n']} "
              f"({adopted['openai_rate']:.0%})")
        print("  ★mismatch 에서는 이 수치를 쓴다 — `grounded` 는 judge 가 draft 를 "
              "기준으로 채점해 정답을 벌하는 것이 관측됐다(docstring 참고).")

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
