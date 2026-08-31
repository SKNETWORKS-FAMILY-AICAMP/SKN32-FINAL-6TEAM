import json
from load_tok import load_tokenizer

tok = load_tokenizer("Qwen/Qwen2.5-3B-Instruct")
import sys
path = sys.argv[1] if len(sys.argv) > 1 else r"E:\dod28_ft\sft_stage3_train_v5.jsonl"
rows = [json.loads(l) for l in open(path, encoding="utf-8")]
lens = []
for r in rows:
    full_text = tok.apply_chat_template(r["messages"], tokenize=False)
    ids = tok(full_text)["input_ids"]
    lens.append(len(ids))
lens.sort()
print("n", len(lens), "min", lens[0], "median", lens[len(lens) // 2], "max", lens[-1], "p90", lens[int(len(lens) * 0.9)])
