"""검토·승인 1건에 실제로 몇 분 걸리는지 잰다.

    python -m eval.timing.measure_review_time --n 20
    python -m eval.timing.measure_review_time --n 20 --action wait_for_approval

★왜 이걸 재나
  `wiki/business/unit-economics.md` 의 72% 절감이 이 숫자에 통째로 달려 있다.
  지금은 검토 2분·승인 3분이 전부 [추정] 이고 아무도 안 쟀다.
  검토가 4분이면 절감이 72% → 50% 로 떨어진다.

★무엇을 재나
  화면을 읽고 판단하는 시간만 잰다. 타이핑·수정 시간은 안 잰다 —
  그건 사람마다·건마다 편차가 커서 다른 실험이 필요하다.

★쓰는 데이터
  eval/reports/2026-08-28_reeval_Proposed_v3.jsonl — 실제 Proposed 실행 결과.
  지어낸 초안이 아니라 모델이 실제로 낸 답이다.

결과: eval/timing/_review_times.jsonl (append)
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = os.path.join(ROOT, "eval/reports/2026-08-28_reeval_Proposed_v3.jsonl")
GOLDEN = os.path.join(ROOT, "eval/datasets/golden.jsonl")
OUT = os.path.join(ROOT, "eval/timing/_review_times.jsonl")

#: ★고정 seed. 누가 재도 같은 순서로 같은 건을 본다.
#:   사람이 바뀌어도 비교할 수 있어야 한다.
SEED = 20260903

CHOICES = {
    "1": ("send", "그대로 보낸다"),
    "2": ("edit", "고쳐서 보낸다"),
    "3": ("reject", "못 쓴다 — 처음부터 다시"),
    "s": ("skip", "판단 보류 (시간에서 뺀다)"),
}


def load(action: str, n: int) -> list[dict]:
    rows = [json.loads(l) for l in open(SOURCE, encoding="utf-8")]
    msgs = {}
    for l in open(GOLDEN, encoding="utf-8"):
        g = json.loads(l)
        msgs[g["case_id"]] = g["message"]

    pool, seen = [], set()
    for r in rows:
        p = r.get("prediction") or {}
        if p.get("next_action") != action:
            continue
        cid = r.get("case_id")
        if cid in seen:          # 같은 case 3회 반복분 중 하나만
            continue
        seen.add(cid)
        pool.append({
            "case_id": cid,
            "message": msgs.get(cid, "(골든셋에 원문 없음)"),
            "answer": p.get("answer"),
            "evidence": p.get("policy_evidence") or [],
            "intent": p.get("intent"),
            "issue_code": p.get("issue_code"),
        })
    random.Random(SEED).shuffle(pool)
    return pool[:n]


def show(i: int, total: int, item: dict, action: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {i}/{total}   {item['case_id']}   [{item['intent']} / {item['issue_code']}]")
    print("=" * 72)
    print("\n[고객 문의]")
    print("  " + item["message"])
    if action == "respond":
        print("\n[모델이 만든 답변 초안]")
        print("  " + (item["answer"] or "(없음)"))
    else:
        print("\n[승인 대기 — 모델은 답을 만들지 않았다]")
    ev = item["evidence"]
    print(f"\n[근거 {len(ev)}건]")
    print("  " + (", ".join(ev[:8]) if ev else "없음"))
    print("\n" + "-" * 72)
    for k, (_, label) in CHOICES.items():
        print(f"  {k}) {label}")
    print("-" * 72)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--action", choices=("respond", "wait_for_approval"), default="respond")
    ap.add_argument("--who", default=os.environ.get("USERNAME", "unknown"),
                    help="누가 쟀는지. 사람마다 다르므로 반드시 남긴다")
    args = ap.parse_args()

    items = load(args.action, args.n)
    if not items:
        print("★대상이 없다. --action 을 확인해라.")
        return 1

    print(f"""
검토·승인 소요시간 측정
  대상   {args.action}   {len(items)}건
  측정자 {args.who}

★읽고 판단하는 시간만 잰다. 고칠 문장을 실제로 쓰지는 않는다.
★모르겠으면 s(보류). 억지로 고르면 숫자가 망가진다.
★중간에 끊어도 된다. 여기까지가 기록된다 (Ctrl+C).

Enter 를 누르면 첫 건이 뜨고 그때부터 시간을 잰다.""")
    input()

    done = []
    try:
        for i, item in enumerate(items, 1):
            show(i, len(items), item, args.action)
            started = time.monotonic()
            choice = ""
            while choice not in CHOICES:
                choice = input("  > ").strip().lower()
            elapsed = time.monotonic() - started
            verdict, label = CHOICES[choice]
            done.append({
                "case_id": item["case_id"], "action": args.action,
                "verdict": verdict, "seconds": round(elapsed, 1),
                "who": args.who, "evidence_count": len(item["evidence"]),
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
            print(f"  → {label}  ({elapsed:.1f}초)")
    except KeyboardInterrupt:
        print("\n\n중단했다. 여기까지 기록한다.")

    if not done:
        print("기록할 게 없다.")
        return 0

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "a", encoding="utf-8") as fh:
        for d in done:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    #: 보류는 시간 집계에서 뺀다 — 판단을 못 한 것이지 오래 걸린 게 아니다
    timed = [d["seconds"] for d in done if d["verdict"] != "skip"]
    print(f"\n{'='*40}")
    print(f"기록 {len(done)}건 (집계 대상 {len(timed)}건)")
    if timed:
        timed.sort()
        mid = timed[len(timed) // 2]
        print(f"  중앙값 {mid:.1f}초 = {mid/60:.2f}분")
        print(f"  평균   {sum(timed)/len(timed):.1f}초")
        print(f"  최소·최대 {timed[0]:.1f} · {timed[-1]:.1f}초")
        print(f"\n  ★unit-economics.md 의 추정치: "
              f"{'2분(120초)' if args.action=='respond' else '3분(180초)'}")
    print(f"\n→ {OUT}")
    print("  집계: python -m eval.timing.report_review_time")
    return 0


if __name__ == "__main__":
    sys.exit(main())
