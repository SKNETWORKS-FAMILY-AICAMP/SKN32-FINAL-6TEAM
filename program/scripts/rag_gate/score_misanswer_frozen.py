"""고정 제품 회귀 자료를 집계한다. 실패·미완료와 중복 문장도 원래 행 분모에 남긴다."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CHANGE_ACTIONS = {"apply_change", "propose_alternatives", "rollback", "redo", "report_delay", "report_closed"}


def score(pool: list[dict], decisions: dict, replies: dict | None = None) -> dict:
    groups = {"unrelated_conversation": [x for x in pool if x["src"] in
               ("일상 대화(AI Hub)", "구어체 대화(KoCulture)")],
              "answerable_policy": [x for x in pool if x["src"].startswith("합성") and x["label"] == "answerable"]}
    result = {}
    for name, rows in groups.items():
        counts = dict(planned=len(rows), completed=0, failed=0, unfinished=0,
                      pinned=0, attempted_change_with_target=0, recognized_policy=0, correct_policy_source=0)
        for row in rows:
            decision = decisions.get(row["q"])
            if decision is None:
                counts["unfinished"] += 1
                continue
            if decision.get("error") or decision.get("failed") or not decision.get("action"):
                counts["failed"] += 1
                continue
            counts["completed"] += 1
            pinned = decision.get("item") not in (None, "none", "")
            counts["pinned"] += int(pinned)
            counts["attempted_change_with_target"] += int(pinned and decision["action"] in CHANGE_ACTIONS)
            counts["recognized_policy"] += int(decision["action"] == "ask_policy")
            reply = (replies or {}).get(row["q"]) or {}
            counts["correct_policy_source"] += int(decision["action"] == "ask_policy" and
                bool(set(reply.get("sources") or []) & set(row.get("gold") or [])))
        counts["unresolved"] = counts["failed"] + counts["unfinished"]
        counts["denominator"] = counts["planned"]
        result[name] = counts
    result["limits"] = ["Repeated text retains the original row denominator; unique text shares its cached decision.",
                         "Unresolved requests are not counted as correct refusals.",
                         "Source correctness requires replies from the same recorded corpus; decision recognition is separate.",
                         "This is a development regression, not independent product acceptance."]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("pool", type=Path)
    parser.add_argument("decisions", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--replies", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("기존 집계 덮어쓰기 금지: 새 출력 이름을 지정하세요")
    inputs = {"pool": args.pool, "decisions": args.decisions, **({"replies": args.replies} if args.replies else {})}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in inputs.items()}
    result = score(data["pool"]["pool"], data["decisions"], data.get("replies"))
    result["input_sha256"] = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in inputs.items()}
    result["scorer_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k: result[k] for k in ("unrelated_conversation", "answerable_policy")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
