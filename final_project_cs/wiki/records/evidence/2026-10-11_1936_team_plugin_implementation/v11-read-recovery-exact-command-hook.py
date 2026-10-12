"""실제 독립 감사에서 지정한 합성 단위시험 외 Bash 실행을 차단한다."""
import json
import sys
payload=json.load(sys.stdin)
allowed='"C:/Users/playdata2/anaconda3/python.exe" wiki/records/evidence/2026-10-11_1936_team_plugin_implementation/v11-read-recovery-final-unit.py'
command=(payload.get("tool_input") or {}).get("command")
decision="allow" if payload.get("tool_name")=="Bash" and command==allowed else "deny"
print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":decision,"permissionDecisionReason":"Only the exact synthetic unit runner is authorized; no other shell command is allowed."}}))
