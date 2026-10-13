"""원문 감사 결과에서 모델 식별자·읽기 범위·시험 원문만 분리 보존한다."""
import json
import sys
from pathlib import Path

base = Path(sys.argv[1])
messages = [json.loads(s) for s in Path(str(base) + "-review.jsonl").read_text(encoding="utf-8-sig").splitlines() if s.strip()]
result = next(m for m in reversed(messages) if m.get("type") == "result")
tools = {}
reads = []
outputs = []
for msg in messages:
    message = msg.get("message")
    content = message.get("content", []) if isinstance(message, dict) else []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use":
            tools[block["id"]] = block
            if block["name"] == "Read":
                reads.append(block["input"])
        if block.get("type") == "tool_result" and tools.get(block.get("tool_use_id"), {}).get("name") == "Bash":
            outputs.append(block)
metadata = {"requested_model": "claude-sonnet-5-5", "is_error": result.get("is_error"),
    "canonical_models": {k: v.get("canonicalModel") for k, v in result.get("modelUsage", {}).items()},
    "permission_denials": result.get("permission_denials"), "modelUsage": result.get("modelUsage"),
    "num_turns": result.get("num_turns"), "direct_Read_calls": reads,
    "tools": {name: sum(v["name"] == name for v in tools.values()) for name in {v["name"] for v in tools.values()}}}
Path(str(base) + "-model-metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
Path(str(base) + "-result.txt").write_text(result.get("result", ""), encoding="utf-8")
Path(str(base) + "-test-output.json").write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
start = json.loads(Path(str(base) + "-start-sha256.json").read_text(encoding="utf-8-sig"))
end = json.loads(Path(str(base) + "-end-sha256.json").read_text(encoding="utf-8-sig"))
end_map = {row["path"]: row["sha256"] for row in end}
diff = {row["path"]: {"start": row["sha256"], "end": end_map.get(row["path"])}
        for row in start if row["sha256"] != end_map.get(row["path"]) or row["sha256"] is None}
Path(str(base) + "-sha256-diff.json").write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"canonical_models": metadata["canonical_models"], "is_error": metadata["is_error"], "hash_changes_or_missing": list(diff), "tools": metadata["tools"]}, ensure_ascii=False))
