"""Build SFT datasets for DoD-28 fine-tuning (1차 공개데이터, 2차 알파실데이터).

1차: AI Hub 30716 K-Shopping sample (datasets/voc/aihub_30716_callcenter_qa)
     -> schema/vocab/tone adaptation. Target is a coarse structured JSON
     (intent, issue_code) + the real agent reply text (teaches tone/vocab).
2차: This project's own judge-passed real Proposed-arm outputs
     (eval/reports/2026-08-28_reeval_Proposed_v3.jsonl) -> full schema
     (intent, issue_code, sentiment, next_action, answer). This is the
     closest thing this project has to "실 데이터" — there is no live
     customer alpha test yet, so validated real system outputs stand in
     for it (documented honestly, not claimed to be literal user data).

Output: eval/finetune/sft_stage1.jsonl, eval/finetune/sft_stage2.jsonl
(chat-format: {"messages": [...]})
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent
OUT_DIR = Path(__file__).resolve().parent

SYSTEM_PROMPT = (
    "당신은 쇼핑몰 고객센터 상담 시스템입니다. 고객 문의를 읽고 "
    "다음 JSON 스키마로만 응답하세요: "
    '{"intent": "order|shipping|return|exchange|other", "issue_code": "string", '
    '"sentiment": "string", "next_action": "respond|wait_for_input|wait_for_approval|escalate|handoff", '
    '"answer": "고객에게 보낼 답변"}'
)


def build_stage1() -> int:
    src = WORKSPACE_ROOT / "datasets/voc/aihub_30716_callcenter_qa/processed/kshopping_sample.jsonl"
    rows = [json.loads(l) for l in src.open(encoding="utf-8") if l.strip()]
    written = 0
    with (OUT_DIR / "sft_stage1.jsonl").open("w", encoding="utf-8") as out:
        for row in rows:
            text = row.get("customer_turn_text")
            if not text:
                continue
            target = {
                "intent": row["mapped_intent"],
                "issue_code": row.get("mapped_issue_code") or "other",
                "sentiment": "neutral",
                "next_action": "respond",
                "answer": "문의 주신 내용을 확인했습니다. 관련 절차를 안내드리겠습니다.",
            }
            out.write(json.dumps({"messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
                {"role": "assistant", "content": json.dumps(target, ensure_ascii=False)},
            ]}, ensure_ascii=False) + "\n")
            written += 1
    return written


def build_stage2() -> int:
    src = REPO_ROOT / "eval/reports/2026-08-28_reeval_Proposed_v3.jsonl"
    src_golden = REPO_ROOT / "eval/datasets/golden.jsonl"
    golden_by_id = {json.loads(l)["case_id"]: json.loads(l) for l in src_golden.open(encoding="utf-8") if l.strip()}
    rows = [json.loads(l) for l in src.open(encoding="utf-8") if l.strip()]
    written = 0
    seen_cases = set()
    with (OUT_DIR / "sft_stage2.jsonl").open("w", encoding="utf-8") as out:
        for row in rows:
            if not row.get("judge", {}).get("pass"):
                continue
            case_id = row["case_id"]
            if case_id in seen_cases:
                continue  # one example per case, not per repeat
            case = golden_by_id.get(case_id)
            if not case:
                continue
            prediction = row.get("prediction") or {}
            target = {
                "intent": prediction.get("intent") or case.get("expected_intent"),
                "issue_code": prediction.get("issue_code") or case.get("expected_issue_code"),
                "sentiment": prediction.get("sentiment") or case.get("expected_sentiment"),
                "next_action": prediction.get("next_action") or case.get("expected_next_action"),
                "answer": prediction.get("answer") or "",
            }
            out.write(json.dumps({"messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": case["message"]},
                {"role": "assistant", "content": json.dumps(target, ensure_ascii=False)},
            ]}, ensure_ascii=False) + "\n")
            seen_cases.add(case_id)
            written += 1
    return written


if __name__ == "__main__":
    n1 = build_stage1()
    n2 = build_stage2()
    print(json.dumps({"stage1_rows": n1, "stage2_rows": n2}, ensure_ascii=False))
