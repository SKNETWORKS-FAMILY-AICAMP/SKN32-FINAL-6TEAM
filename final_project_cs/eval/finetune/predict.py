"""Generate Proposed+FT predictions for golden.jsonl using the stage-2 adapter.

Usage:
    python predict.py --adapter ckpt_stage2 --golden golden.jsonl --out ft_predictions.jsonl
"""
from __future__ import annotations

import argparse
import json
import re

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, BitsAndBytesConfig

from load_tok import load_tokenizer

SYSTEM_PROMPT = (
    "당신은 쇼핑몰 고객센터 상담 시스템입니다. 고객 문의를 읽고 "
    "다음 JSON 스키마로만 응답하세요: "
    '{"intent": "order|shipping|return|exchange|other", "issue_code": "string", '
    '"sentiment": "string", "next_action": "respond|wait_for_input|wait_for_approval|escalate|handoff", '
    '"answer": "고객에게 보낼 답변"}'
)


def _extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", required=True)
    p.add_argument("--golden", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--base", default="Qwen/Qwen2.5-7B-Instruct")
    args = p.parse_args()

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )
    tokenizer = load_tokenizer(args.base)
    model = AutoModelForCausalLM.from_pretrained(
        args.base, quantization_config=bnb_config, device_map="auto", torch_dtype=torch.bfloat16)
    model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()

    cases = [json.loads(l) for l in open(args.golden, encoding="utf-8") if l.strip()]
    written = 0
    parse_ok = 0
    with open(args.out, "w", encoding="utf-8") as out:
        for case in cases:
            messages = [{"role": "system", "content": SYSTEM_PROMPT},
                       {"role": "user", "content": case["message"]}]
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            with torch.no_grad():
                generated = model.generate(**inputs, max_new_tokens=300, temperature=0.0, do_sample=False)
            text = tokenizer.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
            parsed = _extract_json(text)
            row = {"case_id": case["case_id"], "arm": "Proposed+FT", "raw_output": text,
                   "prediction": parsed, "parse_ok": parsed is not None}
            if parsed is not None:
                parse_ok += 1
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1

    print(json.dumps({"written": written, "parse_ok": parse_ok}, ensure_ascii=False))


if __name__ == "__main__":
    main()
